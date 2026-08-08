"""Tests for self-audit/scripts/audit_scope.py."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from support import commit_all, git, git_repo, load_script, run_script

script = load_script("self-audit", "audit_scope.py")

COBERTURA = """<?xml version="1.0" ?>
<coverage><sources><source>.</source></sources><packages><package><classes>
<class filename="{filename}"><lines>
{lines}
</lines></class></classes></package></packages></coverage>
"""

# coverage.py emits exactly this DOCTYPE, naming a DTD ElementTree never fetches.
DOCTYPE_COBERTURA = """<?xml version="1.0" ?>
<!DOCTYPE coverage SYSTEM 'http://cobertura.sourceforge.net/xml/coverage-04.dtd'>
<coverage><sources><source>.</source></sources><packages><package><classes>
<class filename="{filename}"><lines>
{lines}
</lines></class></classes></package></packages></coverage>
"""

# Four levels of nesting: &d; expands to roughly 10KB from ~300 bytes. The
# point is the multiplier, not this size — each further level multiplies by ten
# again, and the author of the report chooses how many to write.
BILLION_LAUGHS = """<?xml version="1.0" ?>
<!DOCTYPE coverage [
 <!ENTITY a "aaaaaaaaaa">
 <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
 <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
 <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
]>
<coverage><sources><source>&d;</source></sources><packages/></coverage>
"""


class CategorizeTest(unittest.TestCase):
    def test_paths_are_bucketed(self):
        cases = {
            "src/app.py": "source",
            "tests/test_app.py": "test",
            "src/app_test.go": "test",
            "docs/guide.md": "docs",
            "README.md": "docs",
            "pyproject.toml": "config",
            ".github/workflows/ci.yml": "ci",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(script.categorize(path), expected)


class GitScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git_repo(self.root)
        (self.root / "src").mkdir()
        (self.root / "src" / "app.py").write_text("def existing():\n    return 1\n")
        commit_all(self.root, "base")

    def tearDown(self):
        self.tmp.cleanup()

    def add_function(self) -> None:
        with (self.root / "src" / "app.py").open("a") as handle:
            handle.write(
                "def added(x):\n"
                "    if x > 0:\n"
                "        return x\n"
                "    if x == -999:\n"
                '        raise ValueError("detection branch")\n'
                "    return 0\n"
            )
        commit_all(self.root, "add function")

    def test_added_lines_are_extracted_from_the_diff(self):
        self.add_function()
        added = script.added_lines(self.root, "main~1", "HEAD")
        self.assertEqual(added["src/app.py"], [3, 4, 5, 6, 7, 8])

    def test_scope_reports_commits_and_kinds(self):
        self.add_function()
        (self.root / "docs").mkdir()
        (self.root / "docs" / "x.md").write_text("hi\n")
        commit_all(self.root, "docs")
        result = run_script(
            "self-audit", "audit_scope.py", "scope", "--base", "main~2", "--json", cwd=self.root
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["commits"]), 2)
        self.assertIn("source", payload["byKind"])
        self.assertIn("docs", payload["byKind"])

    def coverage_file(self, hits: dict[int, int], filename: str = "src/app.py") -> Path:
        lines = "\n".join(f'<line number="{n}" hits="{h}"/>' for n, h in sorted(hits.items()))
        path = self.root / "coverage.xml"
        path.write_text(COBERTURA.format(filename=filename, lines=lines))
        return path

    def test_patch_coverage_counts_only_added_lines(self):
        # Pre-existing lines 1-2 are covered; added 3-5 covered, 6-8 not.
        # Project coverage would be 5/8; patch coverage must be 3/6.
        self.add_function()
        report = self.coverage_file({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 0, 7: 0, 8: 0})
        with contextlib.redirect_stdout(io.StringIO()):
            code = script.cmd_patch_coverage(self.root, "main~1", "HEAD", report, None, True)
        self.assertEqual(code, 0)

    def test_patch_coverage_json_reports_uncovered_lines(self):
        self.add_function()
        self.coverage_file({1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 0, 7: 0, 8: 0})
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", "--json", cwd=self.root,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["measuredLines"], 6)
        self.assertEqual(payload["coveredLines"], 3)
        self.assertEqual(payload["patchCoverage"], 50.0)
        self.assertEqual(payload["files"][0]["uncovered"], [6, 7, 8])

    def test_min_threshold_fails_below(self):
        self.add_function()
        report = self.coverage_file({3: 1, 4: 1, 5: 1, 6: 0, 7: 0, 8: 0})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.cmd_patch_coverage(self.root, "main~1", "HEAD", report, 80.0, True), 2)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.cmd_patch_coverage(self.root, "main~1", "HEAD", report, 40.0, True), 0)

    def test_nothing_measured_is_not_a_vacuous_hundred_percent(self):
        # Regression: reporting 100% for zero measured lines is the vacuous pass
        # the skill's own rules forbid.
        self.add_function()
        self.coverage_file({1: 1}, filename="totally/other.py")
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", "--json", cwd=self.root,
        )
        payload = json.loads(result.stdout)
        self.assertIsNone(payload["patchCoverage"])
        self.assertEqual(payload["measuredLines"], 0)
        self.assertGreater(payload["addedLines"], 0)
        self.assertIn("WARNING", result.stderr)

    def test_min_cannot_be_cleared_when_nothing_was_measured(self):
        self.add_function()
        report = self.coverage_file({1: 1}, filename="totally/other.py")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.cmd_patch_coverage(self.root, "main~1", "HEAD", report, 80.0, True), 2)

    def test_entity_declaring_report_is_refused(self):
        # ElementTree expands declared entities, tenfold per nesting level.
        self.add_function()
        (self.root / "coverage.xml").write_text(BILLION_LAUGHS)
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("declares XML entities", result.stderr)

    def test_a_comment_cannot_hide_the_entity_declarations(self):
        # Regression: the guard located the prolog with a regex, and any
        # comment holding a '<' ended that scan early — so a DOCTYPE placed
        # after one was never examined and the declarations sailed through.
        self.add_function()
        hidden = BILLION_LAUGHS.replace(
            '<?xml version="1.0" ?>\n', '<?xml version="1.0" ?>\n<!-- <coverage> -->\n'
        )
        (self.root / "coverage.xml").write_text(hidden)
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("declares XML entities", result.stderr)

    def test_an_ordinary_comment_containing_a_tag_still_parses(self):
        # The guard must not over-refuse: a comment with a '<' in it is fine.
        self.add_function()
        path = self.root / "coverage.xml"
        lines = "\n".join(f'<line number="{n}" hits="1"/>' for n in (3, 4, 5, 6, 7, 8))
        path.write_text(
            COBERTURA.format(filename="src/app.py", lines=lines).replace(
                '<?xml version="1.0" ?>\n', '<?xml version="1.0" ?>\n<!-- <x> -->\n'
            )
        )
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", "--json", cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["patchCoverage"], 100.0)

    def test_external_dtd_doctype_still_parses(self):
        # The guard must reject declarations, not DTDs: coverage.py's own
        # reports carry a DOCTYPE, and refusing those would refuse real input.
        self.add_function()
        path = self.root / "coverage.xml"
        lines = "\n".join(f'<line number="{n}" hits="1"/>' for n in (3, 4, 5, 6, 7, 8))
        path.write_text(DOCTYPE_COBERTURA.format(filename="src/app.py", lines=lines))
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", "--json", cwd=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["patchCoverage"], 100.0)

    def test_lcov_and_suffix_path_matching(self):
        self.add_function()
        report = self.root / "lcov.info"
        report.write_text(
            "SF:/ci/build/workspace/src/app.py\n"
            "DA:3,1\nDA:4,1\nDA:5,1\nDA:6,0\nDA:7,0\nDA:8,0\nend_of_record\n"
        )
        parsed = script.parse_lcov(report)
        self.assertIn("/ci/build/workspace/src/app.py", parsed)
        matched = script.match_path("src/app.py", parsed)
        self.assertIsNotNone(matched, "a report rooted elsewhere must still match by suffix")
        self.assertEqual(matched[6], 0)

    def test_ambiguous_suffix_matches_are_refused(self):
        # Regression: two report paths sharing a longest suffix silently used
        # the first, so coverage from an unrelated module could report a pass.
        coverage = {"a/src/app.py": {1: 1}, "b/src/app.py": {1: 0}}
        self.assertIsNone(script.match_path("src/app.py", coverage))
        self.assertIsNotNone(script.match_path("src/app.py", {"ci/src/app.py": {1: 1}}))

    def test_deletion_marker_is_recognized_by_the_header_parser(self):
        # `+++ /dev/null` marks a deleted file. Unmatched, it left the parser
        # pointing at the file before it. No lines are misattributed today —
        # with --unified=0 a deletion's hunk is always `+0,0`, so the stale
        # pointer receives an empty range — but the parser should not depend
        # on that to be correct, and a later change to the diff flags would.
        self.assertIsNotNone(script.DIFF_HEADER.match("+++ /dev/null"))
        self.assertIsNone(script.DIFF_HEADER.match("+++ not a diff header"))

        # End to end, with a deletion that actually appears in the diff: the
        # file has to exist at the base and be gone at HEAD, or git omits it
        # entirely and no `+++ /dev/null` header is ever produced.
        (self.root / "z_doomed.py").write_text("a = 1\nb = 2\n")
        commit_all(self.root, "add a file that the range will delete")
        # The resolved sha, not the symbolic ref: "HEAD" would still mean HEAD
        # after the commits below, and the diff would be empty.
        base = git(self.root, "rev-parse", "HEAD").strip()
        self.add_function()
        (self.root / "z_doomed.py").unlink()
        commit_all(self.root, "delete it")

        diff = git(self.root, "diff", "--unified=0", "--no-color", f"{base}...HEAD")
        self.assertIn("+++ /dev/null", diff, "the diff must contain a deletion header")

        added = script.added_lines(self.root, base, "HEAD")
        self.assertEqual(added.get("src/app.py"), [3, 4, 5, 6, 7, 8])
        self.assertNotIn("z_doomed.py", added, "a deletion adds no lines")

    def test_non_ascii_paths_survive_the_diff(self):
        # Regression: git C-quotes non-ASCII paths in diff headers unless
        # core.quotePath=false, and the quoted name matched nothing downstream.
        (self.root / "café.py").write_text("x = 1\n")
        commit_all(self.root, "add a non-ascii filename")
        self.assertIn("café.py", script.added_lines(self.root, "main~1", "HEAD"))

    def test_lcov_by_any_extension_is_not_sent_to_the_xml_parser(self):
        # Regression: dispatch keyed on ".info", so coverage.lcov and lcov.dat
        # reached the XML parser and died with a ParseError traceback.
        self.add_function()
        for name in ("coverage.lcov", "lcov.dat", "coverage.info"):
            with self.subTest(name=name):
                report = self.root / name
                report.write_text("SF:src/app.py\nDA:3,1\nDA:4,0\nend_of_record\n")
                with contextlib.redirect_stdout(io.StringIO()):
                    code = script.cmd_patch_coverage(self.root, "main~1", "HEAD", report, None, True)
                self.assertEqual(code, 0)

    def test_unparseable_report_reports_rather_than_tracebacks(self):
        self.add_function()
        report = self.root / "coverage.xml"
        report.write_text("this is not xml at all\n")
        result = run_script(
            "self-audit", "audit_scope.py", "patch-coverage",
            "--base", "main~1", "--report", "coverage.xml", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("not parseable XML", result.stderr)

    def test_filename_alone_does_not_identify_a_file(self):
        # Regression: any shared suffix won, so src/app.py matched other/app.py
        # and reported a different module's coverage as its own.
        self.assertIsNone(script.match_path("src/app.py", {"other/app.py": {1: 1}}))
        self.assertIsNone(script.match_path("src/deep/app.py", {"vendor/app.py": {1: 0}}))

    def test_root_level_file_still_matches_on_its_name(self):
        # Its name is the whole path, so a one-component match is the most any
        # report could offer — refusing it would measure nothing.
        self.assertIsNotNone(script.match_path("setup.py", {"repo/setup.py": {1: 1}}))

    def test_unrelated_paths_do_not_match(self):
        coverage = {"other/project/thing.py": {1: 1}}
        self.assertIsNone(script.match_path("src/app.py", coverage))


if __name__ == "__main__":
    unittest.main()
