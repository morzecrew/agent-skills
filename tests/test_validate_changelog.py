"""Tests for keep-a-changelog/scripts/validate_changelog.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_script

script = load_script("keep-a-changelog", "validate_changelog.py")

GOOD = """# Changelog

## [Unreleased]

### Added

- A new thing.

## [1.1.0] - 2026-02-01

### Fixed

- A bug.

## [1.0.0] - 2026-01-01 [YANKED]

### Added

- First release.

[unreleased]: https://x/compare/v1.1.0...HEAD
[1.1.0]: https://x/compare/v1.0.0...v1.1.0
[1.0.0]: https://x/releases/tag/v1.0.0
"""


class ChangelogTest(unittest.TestCase):
    def check(self, text: str, house_rules: bool = False) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(text, encoding="utf-8")
            return script.validate(path, house_rules)

    def assert_flags(self, text: str, code: str, house_rules: bool = False) -> None:
        found = self.check(text, house_rules)
        self.assertTrue(
            any(problem.startswith(code) for problem in found),
            f"expected {code}, got {found}",
        )

    def test_valid_changelog_is_clean(self):
        self.assertEqual(self.check(GOOD), [])

    def test_missing_unreleased(self):
        self.assert_flags(GOOD.replace("## [Unreleased]", "## Whats new"), "S1")

    def test_malformed_heading(self):
        self.assert_flags(GOOD.replace("## [1.1.0] - 2026-02-01", "## 1.1.0 (Feb 2026)"), "S2")

    def test_impossible_date(self):
        self.assert_flags(GOOD.replace("2026-02-01", "2026-02-30"), "S3")

    def test_non_iso_date(self):
        # Parses as a heading, then fails the date check — the more precise
        # diagnosis of the two.
        self.assert_flags(GOOD.replace("2026-02-01", "01/02/2026"), "S3")

    def test_versions_out_of_order(self):
        swapped = GOOD.replace("## [1.1.0] - 2026-02-01", "## [0.9.0] - 2026-02-01")
        self.assert_flags(swapped, "S4")

    def test_unknown_category(self):
        self.assert_flags(GOOD.replace("### Fixed", "### Bugfixes"), "S5")

    def test_duplicate_version(self):
        self.assert_flags(GOOD.replace("## [1.0.0] - 2026-01-01 [YANKED]", "## [1.1.0] - 2026-01-01"), "S6")

    def test_link_reference_missing(self):
        self.assert_flags(GOOD.replace("[1.0.0]: https://x/releases/tag/v1.0.0", ""), "S7")

    def test_link_reference_orphaned(self):
        self.assert_flags(GOOD.replace("[1.0.0]: https", "[9.9.9]: https"), "S7")

    def test_link_checks_skipped_when_no_references_used(self):
        # A collection that simply does not use link references must not be
        # nagged into adding them.
        without = GOOD[: GOOD.index("[unreleased]:")].rstrip() + "\n"
        self.assertEqual([p for p in self.check(without) if p.startswith("S7")], [])

    def test_non_semver_version_rejected(self):
        self.assert_flags(GOOD.replace("## [1.1.0] -", "## [1.2] -"), "S2")

    def test_fenced_examples_are_not_scanned(self):
        # Regression: a changelog documenting its own format had its examples
        # read as real categories and stacked bullets.
        with_example = GOOD.replace(
            "- A new thing.",
            "- Documenting the format:\n\n```text\n### Bugfixes\n- one\n- two\n```",
        )
        found = self.check(with_example, house_rules=True)
        self.assertEqual([p for p in found if p.startswith(("S5", "H1"))], [], found)

    def test_unreleased_must_be_first(self):
        moved = "# Changelog\n\n## [1.0.0] - 2026-01-01\n\n### Added\n\n- x\n\n## [Unreleased]\n"
        self.assert_flags(moved, "S1")

    def test_duplicate_unreleased_sections(self):
        self.assert_flags(GOOD.replace("## [1.1.0] - 2026-02-01", "## [Unreleased]"), "S1")

    def test_compact_iso_date_rejected(self):
        # date.fromisoformat accepts 20260101; the spec's YYYY-MM-DD does not.
        self.assert_flags(GOOD.replace("2026-02-01", "20260201"), "S3")

    def test_link_definitions_inside_a_fence_are_illustrations(self):
        illustrated = GOOD.replace(
            "- A new thing.",
            "- Example:\n\n```text\n[9.9.9]: https://example/compare\n```",
        )
        self.assertEqual([p for p in self.check(illustrated) if p.startswith("S7")], [])

    def test_tilde_fenced_headings_are_not_sections(self):
        fenced = "# CL\n\n## [Unreleased]\n\n### Added\n\n- x\n\n~~~text\n## [9.9.9] - not-a-date\n~~~\n"
        self.assertEqual(self.check(fenced), [])

    def test_fence_closes_only_on_its_own_character(self):
        # Regression: treating ``` and ~~~ interchangeably let a ~~~ line inside
        # a backtick block end it early and leak its contents.
        text = ("# CL\n\n## [Unreleased]\n\n### Added\n\n- x\n\n"
                "```text\n~~~\n## [9.9.9] - not-a-date\n```\n")
        self.assertEqual(self.check(text), [])

    def test_shorter_inner_fence_does_not_close_the_block(self):
        # GFM: a closing fence must use the same character and be at least as
        # long as the opener, with nothing after it.
        text = ("# CL\n\n## [Unreleased]\n\n### Added\n\n- x\n\n"
                "````text\n```\n## [9.9.9] - not-a-date\n````\n")
        self.assertEqual(self.check(text), [])

    def test_over_indented_fence_is_content_not_a_delimiter(self):
        # GFM allows at most three spaces. Treating a deeper line as an opener
        # would swallow the real structure after it — so the assertion is that
        # the bad heading is still seen, not merely that the file parses.
        text = ("# CL\n\n## [Unreleased]\n\n### Added\n\n- x\n\n"
                "    ```text\n    stuff\n\n## Bogus Heading\n")
        self.assertTrue(any(p.startswith("S2") for p in self.check(text)))

    def test_backtick_in_info_string_is_not_an_opener(self):
        text = ("# CL\n\n## [Unreleased]\n\n### Added\n\n- x\n\n"
                "```js `inline`\n\n## Bogus Heading\n")
        self.assertTrue(any(p.startswith("S2") for p in self.check(text)))

    def test_legitimately_indented_fence_still_hides_its_example(self):
        # The hidden heading sits at column 0: indented inside the fence it would
        # not match `^##` either way, and the test could not fail.
        text = ("# CL\n\n## [Unreleased]\n\n### Added\n\n- x:\n\n"
                "  ```text\n## Bogus Heading\n  ```\n")
        self.assertEqual(self.check(text), [])

    def test_yanked_tag_accepted(self):
        self.assertNotIn("S2", " ".join(self.check(GOOD)))

    def test_code_fences_are_not_parsed_as_headings(self):
        # Column 0 inside the fence, so removing fence handling makes this fail.
        with_fence = GOOD.replace(
            "- A new thing.",
            "- A new thing.\n\n  ```text\n## [not-a-heading] - nope\n  ```",
        )
        self.assertEqual([p for p in self.check(with_fence) if p.startswith("S2")], [])


    def test_prerelease_with_build_metadata_is_valid_semver(self):
        # Regression: one combined group accepted a prerelease or build
        # metadata but not both, rejecting a version SemVer allows.
        text = GOOD.replace("[1.1.0] - 2026-02-01", "[1.1.0-rc.1+build.5] - 2026-02-01")
        text = text.replace("[1.1.0]: https", "[1.1.0-rc.1+build.5]: https")
        self.assertEqual([p for p in self.check(text) if p.startswith("S2")], [])

    def test_malformed_semver_is_rejected(self):
        # Regression: the loose character class accepted leading zeroes and
        # empty identifiers, which SemVer tooling rejects — and core_version
        # then ordered them as though they were versions.
        for bad in ("01.2.3", "1.0.0-01", "1.0.0-rc..1", "1.0.0-"):
            with self.subTest(version=bad):
                self.assertFalse(script.VERSION.match(bad), bad)
        for good in ("1.0.0", "v1.0.0", "1.0.0-rc.1", "1.0.0-rc.1+build.5", "1.0.0-0a"):
            with self.subTest(version=good):
                self.assertTrue(script.VERSION.match(good), good)

    def test_prerelease_case_is_significant(self):
        # SemVer compares prerelease identifiers case-sensitively, so
        # 1.0.0-RC.1 and 1.0.0-rc.1 are different releases; folding case
        # rejected a valid file as containing duplicates.
        text = GOOD.replace("## [1.1.0] - 2026-02-01", "## [1.0.0-RC.1] - 2026-02-01")
        text = text.replace("[1.1.0]: https", "[1.0.0-RC.1]: https")
        text = text.replace("## [1.0.0] - 2026-01-01 [YANKED]", "## [1.0.0-rc.1] - 2026-01-01")
        text = text.replace("[1.0.0]: https", "[1.0.0-rc.1]: https")
        self.assertEqual([p for p in self.check(text) if p.startswith("S6")], [])

    def test_indented_link_definitions_are_seen(self):
        # Regression: anchored at column 0, an indented set read as "no link
        # definitions at all" — and S7 skips itself entirely in that case, so
        # the check silently disabled rather than failing. Every definition is
        # indented here: leaving one at column 0 would keep S7 alive and the
        # test would pass either way.
        text = GOOD.replace("[unreleased]: ", "  [unreleased]: ")
        text = text.replace("[1.1.0]: ", "  [1.1.0]: ")
        text = text.replace("[1.0.0]: https://x/releases/tag/v1.0.0", "  [nonsense]: https://x/y")
        self.assert_flags(text, "S7")

    def test_prerelease_ranks_below_its_own_release(self):
        # Regression: comparing only the numeric core made 1.0.0-rc.1 and
        # 1.0.0 equal, so a prerelease listed above its release passed S4.
        text = GOOD.replace("## [1.1.0] - 2026-02-01", "## [1.0.0-rc.1] - 2026-02-01")
        text = text.replace("[1.1.0]: https", "[1.0.0-rc.1]: https")
        self.assert_flags(text, "S4")

    def test_release_above_its_prerelease_is_correct_order(self):
        text = GOOD.replace("## [1.0.0] - 2026-01-01 [YANKED]", "## [1.0.0-rc.1] - 2026-01-01")
        text = text.replace("[1.0.0]: https", "[1.0.0-rc.1]: https")
        text = text.replace("## [1.1.0] - 2026-02-01", "## [1.0.0] - 2026-02-01")
        text = text.replace("[1.1.0]: https", "[1.0.0]: https")
        self.assertEqual([p for p in self.check(text) if p.startswith("S4")], [])

    def test_duplicate_version_across_a_v_prefix(self):
        # Regression: keying on the raw heading made [1.0.0] and [v1.0.0] look
        # like different releases.
        text = GOOD.replace("## [1.1.0] - 2026-02-01", "## [v1.0.0] - 2026-02-01")
        self.assert_flags(text, "S6")


class HouseRulesTest(unittest.TestCase):
    def check(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(text, encoding="utf-8")
            return script.validate(path, True)

    def test_house_rules_are_off_by_default(self):
        stacked = GOOD.replace("- A new thing.", "- One thing.\n- Another thing.")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(stacked, encoding="utf-8")
            self.assertEqual([p for p in script.validate(path, False) if p.startswith("H")], [])

    def test_stacked_bullets_flagged(self):
        stacked = GOOD.replace("- A new thing.", "- One thing.\n- Another thing.")
        self.assertTrue(any(p.startswith("H1") for p in self.check(stacked)))

    def test_overlong_entry_flagged(self):
        long_entry = "- " + "x" * 400
        self.assertTrue(any(p.startswith("H2") for p in self.check(GOOD.replace("- A new thing.", long_entry))))

    def test_too_many_sentences_flagged(self):
        wordy = "- One. Two. Three. Four."
        self.assertTrue(any(p.startswith("H3") for p in self.check(GOOD.replace("- A new thing.", wordy))))

    def test_placeholder_entry_is_exempt(self):
        placeholder = GOOD.replace("- A new thing.", "- ...")
        self.assertEqual([p for p in self.check(placeholder) if p.startswith("H")], [])

    def test_bullet_stacked_on_a_continuation_line_is_flagged(self):
        # Regression: H1 compared adjacent bullet lines, so an entry that ran
        # onto a continuation line hid the stacking that follows it.
        stacked = GOOD.replace("- A new thing.", "- One thing.\n  continued here.\n- Another thing.")
        self.assertTrue(any(p.startswith("H1") for p in self.check(stacked)), self.check(stacked))

    def test_properly_spaced_continuation_stays_clean(self):
        spaced = GOOD.replace("- A new thing.", "- One thing.\n  continued here.\n\n- Another thing.")
        self.assertEqual([p for p in self.check(spaced) if p.startswith("H1")], [])

    def test_unindented_line_ends_the_entry(self):
        # Regression: the fold walked past a non-continuation line, so a later
        # indented line was appended to the earlier bullet — text the entry
        # never had, then measured against H2 and H3.
        lines = ["- short entry", "not indented, so not a continuation", "  " + "x" * 400]
        text = GOOD.replace("- A new thing.", "\n".join(lines))
        self.assertEqual([p for p in self.check(text) if p.startswith("H2")], [])

    def test_abbreviation_is_not_a_sentence_boundary(self):
        # Regression: "e.g." counted as a sentence end, inflating the count and
        # failing entries that obeyed H3.
        entry = "- Adds a thing, e.g. a widget, i.e. the small kind, etc. and more."
        self.assertEqual([p for p in self.check(GOOD.replace("- A new thing.", entry)) if p.startswith("H3")], [])

    def test_real_sentences_are_still_counted(self):
        self.assertTrue(
            any(p.startswith("H3") for p in self.check(GOOD.replace("- A new thing.", "- One. Two. Three. Four.")))
        )


if __name__ == "__main__":
    unittest.main()
