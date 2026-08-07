"""Tests for self-audit/scripts/audit_scope.py."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from support import commit_all, git_repo, load_script, run_script

script = load_script("self-audit", "audit_scope.py")

COBERTURA = """<?xml version="1.0" ?>
<coverage><sources><source>.</source></sources><packages><package><classes>
<class filename="{filename}"><lines>
{lines}
</lines></class></classes></package></packages></coverage>
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

    def test_unrelated_paths_do_not_match(self):
        coverage = {"other/project/thing.py": {1: 1}}
        self.assertIsNone(script.match_path("src/app.py", coverage))


if __name__ == "__main__":
    unittest.main()
