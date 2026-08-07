"""Tests for reproduce-then-fix/scripts/verified_red.py."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from support import commit_all, git, git_repo, load_script, run_script

script = load_script("reproduce-then-fix", "verified_red.py")

BUGGY = "def clamp(x, lo, hi):\n    return min(x, hi)\n"
FIXED = "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n"
DISCRIMINATING_TEST = (
    "from app import clamp\n"
    "assert clamp(-5, 0, 10) == 0, 'lower bound not applied'\n"
)
BLIND_TEST = "from app import clamp\nassert clamp(5, 0, 10) == 5\n"


class VerifiedRedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git_repo(self.root)
        (self.root / "app.py").write_text(BUGGY)
        commit_all(self.root, "buggy")

    def tearDown(self):
        self.tmp.cleanup()

    def apply_fix(self) -> None:
        (self.root / "app.py").write_text(FIXED)

    def certify(self, test_body: str, name: str = "test_clamp.py", base: str = "HEAD") -> dict:
        (self.root / name).write_text(test_body)
        return script.certify(
            self.root, base, f"python3 {name}", [Path(name)], None, False
        )

    def test_real_fix_with_discriminating_test_is_certified(self):
        self.apply_fix()
        result = self.certify(DISCRIMINATING_TEST)
        self.assertTrue(result["certified"], result)
        self.assertNotEqual(result["redExitCode"], 0)
        self.assertEqual(result["greenExitCode"], 0)

    def test_blind_test_is_not_certified(self):
        # Passes with and without the fix: it guards nothing.
        self.apply_fix()
        result = self.certify(BLIND_TEST, name="test_blind.py")
        self.assertFalse(result["certified"])
        self.assertFalse(result["redFailedAsRequired"])
        self.assertIn("passed without the fix", result["verdict"])

    def test_incomplete_fix_is_not_certified(self):
        result = self.certify(DISCRIMINATING_TEST)  # no fix applied
        self.assertFalse(result["certified"])
        self.assertFalse(result["greenPassed"])
        self.assertIn("fix is incomplete", result["verdict"])

    def test_committed_fix_with_explicit_base(self):
        self.apply_fix()
        (self.root / "test_clamp.py").write_text(DISCRIMINATING_TEST)
        commit_all(self.root, "fix and test")
        result = script.certify(
            self.root, "HEAD~1", "python3 test_clamp.py", [Path("test_clamp.py")], None, False
        )
        self.assertTrue(result["certified"], result)

    def test_working_tree_is_never_modified(self):
        self.apply_fix()
        # Snapshot after staging the reproduction, so the comparison isolates
        # what certify() does rather than what this test's own setup does.
        (self.root / "test_clamp.py").write_text(DISCRIMINATING_TEST)
        before = (self.root / "app.py").read_text()
        status_before = git(self.root, "status", "--porcelain")

        script.certify(self.root, "HEAD", "python3 test_clamp.py", [Path("test_clamp.py")], None, False)

        self.assertEqual((self.root / "app.py").read_text(), before, "the fix must survive")
        changed = set(git(self.root, "status", "--porcelain").split()) - set(status_before.split())
        self.assertFalse(
            {entry for entry in changed if "__pycache__" not in entry},
            f"certify() altered tracked state: {changed}",
        )

    def test_no_worktree_is_left_behind(self):
        self.apply_fix()
        self.certify(DISCRIMINATING_TEST)
        listed = git(self.root, "worktree", "list")
        self.assertEqual(len(listed.strip().splitlines()), 1, listed)

    def test_worktree_is_cleaned_up_when_the_test_command_explodes(self):
        # The cleanup lives in a finally block; a command that cannot run must
        # not strand a worktree.
        self.apply_fix()
        (self.root / "t.py").write_text(DISCRIMINATING_TEST)
        script.certify(self.root, "HEAD", "this-command-does-not-exist", [Path("t.py")], None, False)
        self.assertEqual(len(git(self.root, "worktree", "list").strip().splitlines()), 1)

    def test_exact_red_exit_code_can_be_required(self):
        self.apply_fix()
        (self.root / "t.py").write_text("import sys\nsys.exit(3)\n")
        matching = script.certify(self.root, "HEAD", "python3 t.py", [Path("t.py")], 3, False)
        self.assertTrue(matching["redFailedAsRequired"])
        mismatched = script.certify(self.root, "HEAD", "python3 t.py", [Path("t.py")], 4, False)
        self.assertFalse(mismatched["redFailedAsRequired"])

    def test_missing_test_file_is_rejected(self):
        result = run_script(
            "reproduce-then-fix", "verified_red.py",
            "--test-cmd", "true", "--test-file", "nope.py", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist", result.stderr)

    def test_absolute_test_file_is_refused(self):
        result = run_script(
            "reproduce-then-fix", "verified_red.py",
            "--test-cmd", "true", "--test-file", "/etc/passwd", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("repository-relative", result.stderr)

    def test_parent_traversal_test_file_is_refused(self):
        result = run_script(
            "reproduce-then-fix", "verified_red.py",
            "--test-cmd", "true", "--test-file", "../outside.py", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("escapes the repository", result.stderr)

    def test_non_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as plain:
            result = run_script(
                "reproduce-then-fix", "verified_red.py",
                "--test-cmd", "true", "--test-file", "x.py", cwd=Path(plain),
            )
            self.assertEqual(result.returncode, 1)

    def test_cli_exit_code_two_when_not_certified(self):
        self.apply_fix()
        (self.root / "test_blind.py").write_text(BLIND_TEST)
        result = run_script(
            "reproduce-then-fix", "verified_red.py",
            "--test-cmd", "python3 test_blind.py", "--test-file", "test_blind.py", cwd=self.root,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
