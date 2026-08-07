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


if __name__ == "__main__":
    unittest.main()
