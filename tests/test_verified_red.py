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

    def test_red_run_that_cannot_import_is_not_a_reproduction(self):
        # Regression: the red worktree is base plus only --test-file, so a
        # helper that exists solely in the working tree made the red run die on
        # the import. That non-zero exit looked exactly like a reproduction and
        # certified a test that never ran — worse than running no check at all.
        (self.root / "helper.py").write_text("VALUE = 0\n")  # never committed
        self.apply_fix()
        (self.root / "t.py").write_text("import helper\n" + DISCRIMINATING_TEST)
        result = script.certify(self.root, "HEAD", "python3 t.py", [Path("t.py")], None, False)
        self.assertFalse(result["certified"], result)
        self.assertTrue(result["redFailedBeforeTesting"])
        self.assertIn("--test-file", result["verdict"])

    def test_import_failure_can_be_accepted_when_it_is_the_bug(self):
        (self.root / "helper.py").write_text("VALUE = 0\n")
        self.apply_fix()
        (self.root / "t.py").write_text("import helper\n" + DISCRIMINATING_TEST)
        result = script.certify(
            self.root, "HEAD", "python3 t.py", [Path("t.py")], None, False, True
        )
        self.assertTrue(result["certified"], result)

    def test_carrying_the_helper_across_certifies_normally(self):
        # The remedy the verdict names must actually work.
        (self.root / "helper.py").write_text("VALUE = 0\n")
        self.apply_fix()
        (self.root / "t.py").write_text("import helper\n" + DISCRIMINATING_TEST)
        result = script.certify(
            self.root, "HEAD", "python3 t.py", [Path("t.py"), Path("helper.py")], None, False
        )
        self.assertTrue(result["certified"], result)
        self.assertFalse(result["redFailedBeforeTesting"])

    def test_shell_command_lines_are_honored(self):
        # --test-cmd is a shell command line by contract — operators chain and
        # redirect in it. Running it as a split argv instead would feed "&&" to
        # python3 as a filename, so both halves would fail for the wrong reason.
        self.apply_fix()
        (self.root / "t.py").write_text(DISCRIMINATING_TEST)
        result = script.certify(
            self.root, "HEAD", "python3 t.py && echo chained", [Path("t.py")], None, False
        )
        self.assertTrue(result["certified"], result)
        self.assertIn("chained", result["greenTail"])

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "no symlink support")
    def test_symlinked_directory_in_base_cannot_be_written_through(self):
        # Regression: the source was checked for containment but the
        # destination was not, so a committed symlinked directory carried the
        # copy straight out of the throwaway worktree.
        with tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir)
            # The symlink is committed, so it exists in the base checkout the
            # red run copies into...
            (self.root / "tests").symlink_to(outside, target_is_directory=True)
            commit_all(self.root, "commit a symlinked tests dir")
            # ...but the working tree holds a real directory, so the source
            # passes its own containment check and only the destination
            # traverses the link.
            (self.root / "tests").unlink()
            (self.root / "tests").mkdir()
            (self.root / "tests" / "t.py").write_text(DISCRIMINATING_TEST)
            self.apply_fix()

            with self.assertRaises(SystemExit) as caught:
                script.certify(
                    self.root, "HEAD", "python3 tests/t.py", [Path("tests/t.py")], None, False
                )
            self.assertIn("symlink", str(caught.exception))
            self.assertEqual(list(outside.iterdir()), [], "nothing may be written outside")

    def test_a_hung_run_is_killed_and_not_counted_as_red(self):
        # Regression: neither run had a timeout, so a hanging reproduction hung
        # the certifier — and a hang that exits non-zero would read as red.
        # The verdict has to name the timeout: `certified` is False here anyway
        # because the green half hangs too, so asserting only that would pass
        # whether or not the timeout was ever taken into account.
        self.apply_fix()
        (self.root / "t.py").write_text("import time\ntime.sleep(120)\n")
        result = script.certify(
            self.root, "HEAD", "python3 t.py", [Path("t.py")], None, False, False, 2
        )
        self.assertFalse(result["certified"], result)
        self.assertTrue(result["redTimedOut"])
        self.assertIn("killed after", result["verdict"].lower())
        self.assertNotIn("fix is incomplete", result["verdict"])

    def test_missing_git_is_reported_not_raised(self):
        # Regression: git can be absent entirely (containers, minimal CI
        # images). The documented contract is exit 1 for a usage error, and
        # usage_census already guards the same call.
        original = script.subprocess.run

        def no_git(*args, **kwargs):
            raise FileNotFoundError("git")

        script.subprocess.run = no_git
        try:
            with self.assertRaises(SystemExit) as caught:
                script.git(self.root, "rev-parse", "--show-toplevel")
        finally:
            script.subprocess.run = original
        self.assertIn("git not found", str(caught.exception))

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

    def test_expect_red_exit_zero_is_refused(self):
        # Regression: it made "red" mean "passed", certifying nothing.
        (self.root / "t.py").write_text(DISCRIMINATING_TEST)
        result = run_script(
            "reproduce-then-fix", "verified_red.py", "--test-cmd", "true",
            "--test-file", "t.py", "--expect-red-exit", "0", cwd=self.root,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("certifies nothing", result.stderr)

    def test_subdirectory_root_is_refused(self):
        # The red run executes at the worktree root, so a subdirectory root
        # would run something different from the green half.
        sub = self.root / "pkg"
        sub.mkdir()
        (sub / "t.py").write_text(DISCRIMINATING_TEST)
        result = run_script(
            "reproduce-then-fix", "verified_red.py", "--test-cmd", "true",
            "--test-file", "t.py", cwd=sub,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("toplevel", result.stderr)

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
