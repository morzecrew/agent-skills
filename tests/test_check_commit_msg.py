"""Tests for gitmoji-conventional/scripts/check_commit_msg.py."""

from __future__ import annotations

import unittest

from support import load_script

script = load_script("gitmoji-conventional", "check_commit_msg.py")
MAPPING = script.load_mapping(script.Path(script.__file__).resolve().parent)


def errors(message: str) -> list[str]:
    return [text for level, text in script.check_message(message, MAPPING) if level == "error"]


def warnings(message: str) -> list[str]:
    return [text for level, text in script.check_message(message, MAPPING) if level == "warn"]


class MappingTest(unittest.TestCase):
    def test_mapping_parses_from_the_reference(self):
        self.assertGreater(len(MAPPING), 50, "the official set is ~75 entries")
        self.assertEqual(MAPPING["✨"], "feat")
        self.assertEqual(MAPPING["🐛"], "fix")

    def test_breaking_emoji_is_deliberately_absent_from_the_mapping(self):
        # Its row reads "underlying type + !", not a concrete type. The checker
        # must special-case it *before* the membership test — see the regression
        # test below.
        self.assertNotIn("💥", MAPPING)


class BreakingChangeTest(unittest.TestCase):
    def test_breaking_commit_still_needs_a_real_type(self):
        # Regression: 💥 is deliberately absent from the mapping, and the branch
        # that handles it skipped the type check entirely — so any invented type
        # passed on the commit class most likely to be read later.
        self.assertIn(
            "C2", " ".join(errors("💥 bogus!: drop the v1 api")),
        )

    def test_breaking_commit_with_a_real_type_passes(self):
        self.assertEqual(errors("💥 feat!: drop the v1 api"), [])

    def test_miscased_marker_is_flagged_beside_a_correct_one(self):
        # Regression: the check was suppressed whenever any correct marker was
        # present, so a malformed footer rode along beside a well-formed one.
        message = "💥 feat!: drop it\n\nBREAKING CHANGE: gone\nBreaking change: also gone"
        self.assertTrue([e for e in errors(message) if "C5" in e and "uppercase" in e])

    def test_both_accepted_spellings_stay_clean(self):
        self.assertEqual(errors("💥 feat!: drop it\n\nBREAKING CHANGE: gone"), [])
        self.assertEqual(errors("💥 feat!: drop it\n\nBREAKING-CHANGE: gone"), [])


class ValidMessageTest(unittest.TestCase):
    def test_plain_feat(self):
        self.assertEqual(errors("✨ feat(api): add OAuth login support"), [])

    def test_emoji_with_variation_selector(self):
        self.assertEqual(errors("♻️ refactor(cache): extract eviction policy"), [])

    def test_revert(self):
        self.assertEqual(errors("⏪️ revert: add OAuth login support"), [])

    def test_breaking_change_with_all_three_signals(self):
        # Regression: the boom special case once sat behind the mapping
        # membership test, so every valid breaking commit was rejected as "not
        # an official gitmoji".
        message = (
            "💥 feat(api)!: redesign authentication API\n\n"
            "BREAKING CHANGE: endpoints now require OAuth2;\n"
            " API-key access is removed.\n"
        )
        self.assertEqual(errors(message), [])

    def test_breaking_on_a_fix(self):
        self.assertEqual(errors("💥 fix!: drop the legacy parser"), [])

    def test_body_after_blank_line(self):
        self.assertEqual(errors("✨ feat: add thing\n\nsome body text"), [])

    def test_git_written_messages_are_skipped(self):
        for message in ("Merge branch main into feature", "fixup! ✨ feat: x", "Revert \"x\""):
            with self.subTest(message=message):
                self.assertEqual(errors(message), [])


class InvalidMessageTest(unittest.TestCase):
    def assert_flags(self, message: str, code: str) -> None:
        found = errors(message)
        self.assertTrue(found, f"expected {code} for {message!r}, got no errors")
        self.assertTrue(
            any(text.startswith(code) for text in found),
            f"expected {code} for {message!r}, got {found}",
        )

    def test_unparseable_subject(self):
        self.assert_flags("just some words", "C1")

    def test_unofficial_emoji(self):
        self.assert_flags("🍔 feat: add burger", "C2")

    def test_emoji_type_mismatch(self):
        self.assert_flags("✨ fix(auth): reject expired tokens", "C3")

    def test_breaking_emoji_without_bang(self):
        self.assert_flags("💥 feat(api): redesign auth", "C4")

    def test_bang_without_breaking_emoji(self):
        self.assert_flags("✨ feat(api)!: redesign auth", "C4")

    def test_breaking_footer_without_bang(self):
        self.assert_flags("💥 feat: redesign\n\nBREAKING CHANGE: it broke", "C4")

    def test_lowercase_breaking_token(self):
        self.assert_flags("💥 feat!: redesign\n\nbreaking change: it broke", "C5")

    def test_unindented_footer_continuation(self):
        # The exact trailer-folding bug this skill's own example once had.
        message = (
            "💥 feat!: redesign auth\n\n"
            "BREAKING CHANGE: endpoints now require OAuth2;\n"
            "API-key access is removed.\n"
        )
        self.assert_flags(message, "C5")

    def test_prose_paragraph_opening_with_a_capitalized_word_is_not_a_trailer(self):
        # Regression: git reads trailers only from the last paragraph, so a body
        # paragraph beginning "Also:" must not be scanned for folding. Found by
        # running this checker over the repository's own history.
        message = (
            "✅ test: add coverage\n\n"
            "Also: the poller now waits for quiescence rather than\n"
            "completion, because a check can go green early.\n\n"
            "Co-Authored-By: Someone <someone@example.com>\n"
        )
        self.assertEqual(errors(message), [])

    def test_breaking_phrase_in_an_earlier_paragraph_is_prose(self):
        # Regression: the token scan covered the whole body, so an explanatory
        # paragraph failed the hook.
        message = (
            "✨ feat: add thing\n\n"
            "BREAKING CHANGE: was considered and rejected for this change.\n\n"
            "Co-Authored-By: X <x@y>\n"
        )
        self.assertEqual(errors(message), [])

    def test_final_prose_paragraph_opening_with_also_is_accepted(self):
        # Regression, second time: restricting the scan to the last paragraph
        # was not enough while any capitalized word plus a colon counted as a
        # trailer token. Only real trailers do now.
        message = (
            "✨ feat: add thing\n\n"
            "Also: the poller waits for quiescence rather than completion,\n"
            "because a check can go green early.\n"
        )
        self.assertEqual(errors(message), [])

    def test_hyphenated_trailers_are_recognized_by_shape(self):
        # A short whitelist dropped canonical keys like Helped-by; trailers are
        # matched by their token shape instead.
        message = "✨ feat: x\n\nHelped-by: Someone <s@e>\nunindented continuation\n"
        self.assertTrue(any(t.startswith("C5") for t in errors(message)), errors(message))

    def test_lowercase_hyphenated_prose_is_not_a_trailer(self):
        # Regression: matching hyphenated tokens case-insensitively caught prose
        # like "well-known:" and failed legitimate messages.
        message = "✨ feat: x\n\nwell-known: this is prose\ncontinuing unindented here.\n"
        self.assertEqual(errors(message), [])

    def test_past_tense_description(self):
        self.assert_flags("✨ feat(api): added OAuth login support", "C6")

    def test_trailing_period(self):
        self.assert_flags("✨ feat(api): add OAuth login support.", "C6")

    def test_body_without_blank_line(self):
        self.assert_flags("✨ feat(api): add login\nbody right after", "C7")

    def test_empty_message(self):
        self.assert_flags("", "C1")

    def test_whitespace_only_description(self):
        # Regression: description.split()[0] raised IndexError on "✨ feat:  ".
        self.assert_flags("✨ feat:  \n\nbody", "C6")


def body(*lines: str) -> str:
    return "✨ feat(api): add a thing\n\n" + "\n".join(lines)


class BodyLengthTest(unittest.TestCase):
    """C8/C9/C10 — a commit body explains a change; it is not a document."""

    def test_a_body_at_the_hard_cap_passes(self):
        message = body(*[f"line {n}" for n in range(script.BODY_HARD_CAP)])
        self.assertEqual(errors(message), [])

    def test_a_body_over_the_hard_cap_fails(self):
        message = body(*[f"line {n}" for n in range(script.BODY_HARD_CAP + 1)])
        self.assertTrue(any(text.startswith("C8") for text in errors(message)))

    def test_blank_lines_do_not_count_against_the_cap(self):
        lines = []
        for n in range(script.BODY_HARD_CAP):
            lines += [f"line {n}", ""]
        self.assertEqual(errors(body(*lines)), [])

    def test_the_soft_cap_warns_without_failing(self):
        message = body(*[f"line {n}" for n in range(script.BODY_SOFT_CAP + 1)])
        self.assertEqual(errors(message), [])
        self.assertTrue(any(text.startswith("C9") for text in warnings(message)))

    def test_footers_are_exempt(self):
        """A long trailer block is metadata, not prose — charging the cap for
        it would penalise exactly the machine-readable part."""
        lines = [f"line {n}" for n in range(script.BODY_HARD_CAP)]
        lines += ["", "Closes #1", "Refs: abc123",
                  "Co-Authored-By: Someone <a@b.c>",
                  "Co-Authored-By: Another <d@e.f>"]
        self.assertEqual(errors(body(*lines)), [])

    def test_a_trailing_prose_paragraph_is_not_treated_as_footers(self):
        """Only a paragraph that is entirely trailers is exempt. Dropping any
        final paragraph would exempt the prose the cap exists to catch."""
        lines = [f"line {n}" for n in range(script.BODY_HARD_CAP)]
        lines += ["", "One more closing thought that is not a trailer."]
        self.assertTrue(any(text.startswith("C8") for text in errors(body(*lines))))

    def test_fenced_blocks_are_exempt(self):
        """The declared way to carry evidence a commit genuinely needs."""
        lines = ["why this changed", "", "```"]
        lines += [f"    frame {n}" for n in range(40)]
        lines += ["```"]
        self.assertEqual(errors(body(*lines)), [])

    def test_an_unclosed_fence_does_not_swallow_the_rest_of_the_body(self):
        lines = ["```", "evidence"] + [f"line {n}" for n in range(30)]
        self.assertEqual(errors(body(*lines)), [],
                         "an unclosed fence exempts what follows — a known,"
                         " visible hole, not a silent one")

    def test_a_long_body_line_warns(self):
        message = body("x " * 60)
        self.assertEqual(errors(message), [])
        self.assertTrue(any(text.startswith("C10") for text in warnings(message)))

    def test_an_unbreakable_token_does_not_warn(self):
        """A URL cannot be wrapped; flagging it teaches people to ignore C10."""
        message = body("https://example.com/" + "a" * 90)
        self.assertEqual(warnings(message), [])

    def test_no_body_is_fine(self):
        self.assertEqual(errors("✨ feat(api): add a thing"), [])
        self.assertEqual(warnings("✨ feat(api): add a thing"), [])

    def test_the_caps_are_ordered(self):
        self.assertLess(script.BODY_SOFT_CAP, script.BODY_HARD_CAP)

    def test_the_cap_still_rejects_the_shape_it_was_written_for(self):
        """Pins the VALUE, not just the mechanism.

        Every other test here is written relative to BODY_HARD_CAP, so raising
        the constant keeps them all green — and raising it by four is exactly
        how this rule would be neutered, since the session-narrative bodies
        that prompted it ran 22-29 lines. This asserts the two cases the number
        was chosen from: an essay fails, and a body the size of this
        repository's median passes.
        """
        narrative = [
            "Adversarial pass over the branch, following the ten passes.",
            "Four findings, all fixed here.",
            "",
            "PROSE — two claims repeated a source headline without the",
            "correction that followed it, and the two skills then narrated",
            "the same event incompatibly:",
            "",
            "  * the first said a person funded several tests; the source's",
            "    own amendment records that this did not happen. The",
            "    vocabulary gap was real; the event was not.",
            "  * the second repeated a founding document's headline count,",
            "    which a later census corrected in both directions.",
            "",
            "COVERAGE — four detection branches had no test, including the",
            "render block that is the whole non-blocking visibility channel",
            "this skill argues for. Tests added for each.",
            "",
            "REFUSAL — the scanner parsed merge diffs to nothing and said",
            "clean, which is indistinguishable from the good news. It now",
            "refuses on input it cannot read.",
            "",
            "Sabotage of the audit's own fixes caught two being vacuous,",
            "which is the reason that pass exists at all. One passed with",
            "the branch deleted because a literal was the real evidence,",
            "and the other was tested as a function while main() ignored it.",
            "",
            "33 mutations run across the three scripts, 33 caught, and the",
            "coverage pass is recorded in the branch notes.",
        ]
        # Self-checking: an earlier version of this fixture was 16 lines and
        # quietly asserted nothing. A fixture whose size is the point must
        # state its size.
        measured = len([line for line in narrative if line.strip()])
        self.assertEqual(measured, 22, "fixture must stay essay-sized")
        self.assertTrue(any(text.startswith("C8") for text in errors(body(*narrative))),
                        "the cap must reject a 22-line session narrative")

        ordinary = [f"a line about why the change was made {n}" for n in range(9)]
        self.assertEqual(errors(body(*ordinary)), [],
                         "the cap must accept a body the size of this repo's median")


class SeverityTest(unittest.TestCase):
    def test_long_subject_warns_but_does_not_fail(self):
        # The skill's cap is "<= 72 when possible"; a validator must not harden
        # a rule its skill deliberately hedged.
        message = "✨ feat(api): " + "x" * 80
        self.assertEqual(errors(message), [])
        self.assertTrue(any(text.startswith("C6") for text in warnings(message)))


if __name__ == "__main__":
    unittest.main()
