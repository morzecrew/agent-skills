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


class SeverityTest(unittest.TestCase):
    def test_long_subject_warns_but_does_not_fail(self):
        # The skill's cap is "<= 72 when possible"; a validator must not harden
        # a rule its skill deliberately hedged.
        message = "✨ feat(api): " + "x" * 80
        self.assertEqual(errors(message), [])
        self.assertTrue(any(text.startswith("C6") for text in warnings(message)))


if __name__ == "__main__":
    unittest.main()
