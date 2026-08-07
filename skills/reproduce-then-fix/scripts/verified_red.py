#!/usr/bin/env python3
"""Supporting tool for the reproduce-then-fix skill: certify a test as verified-red.

A regression test that has never been seen failing proves nothing — it may pass
for reasons unrelated to the fix. This runs both halves of the certificate:

  1. RED   the test, without the fix, must fail
  2. GREEN the same test, with the fix, must pass

  verified_red.py --test-cmd "pytest tests/test_bug.py" --test-file tests/test_bug.py

**It never touches your working tree.** The red half runs in a throwaway `git
worktree` checked out at the base commit (the fix absent), into which only the
named test files are copied. Nothing is stashed, so an interrupted run cannot
strand your work; the worktree is removed in a finally block either way.

  --base REF        commit the fix is absent from (default: HEAD, i.e. the fix is
                    uncommitted; use HEAD~1 when the fix is the last commit)
  --test-file PATH  file to carry into the red run (repeatable; usually the test
                    holding the reproduction)
  --expect-red-exit forgiving mode: any non-zero red exit counts as failing
                    (default), or pass an exact code to require it
  --allow-red-error accept a red run that died on a missing import or collection
                    error, which is otherwise refused: the red worktree holds
                    only base plus --test-file, so a conftest or helper missing
                    from both fails the run without testing anything

`--test-cmd` runs through your shell, so it takes the command lines you would
type — pipes, `&&`, redirection. It therefore runs with your privileges: pass a
command you wrote, never one lifted from a repository, an issue, or a review
comment.

Exit codes: 0 certified · 1 usage/git error · 2 not certified (the red run
passed, or the green run failed) — the message says which half broke. Unknown
flags exit 2, from argparse itself.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The red worktree is base plus only the files named by --test-file. A conftest,
# fixture, or helper that lives in neither makes the red run die on the missing
# import rather than on the absent fix — a non-zero exit that looks exactly like
# a reproduction and certifies a test that never ran. Refused by default, since
# a false certificate is worse than no check at all.
INFRASTRUCTURE_RED = re.compile(
    r"ModuleNotFoundError|ImportError|No module named|ERR_MODULE_NOT_FOUND"
    r"|Cannot find module|ERROR collecting|errors during collection"
    r"|file or directory not found|no tests ran|collected 0 items"
    r"|command not found|SyntaxError",
    re.IGNORECASE,
)


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        sys.exit(f"error: git {' '.join(args[:3])} failed: {proc.stderr.strip()[:300]}")
    return proc


def run_test(command: str, cwd: Path, label: str, verbose: bool) -> tuple[int, str]:
    print(f"--- {label}: {command}  (in {cwd})", file=sys.stderr)
    # The shell is the interface here, not an injection path: --test-cmd is a
    # command line the operator writes ("pytest -k bug && ./check.sh"), run with
    # exactly the privilege of the shell that launched this tool. Splitting it
    # into argv instead would silently drop the chaining and redirection real
    # test commands use. Both halves run the identical string, so neither can
    # diverge from the other.
    # (Keep the nosec bare: bandit parses whatever trails it as further test ids.)
    proc = subprocess.run(  # nosec B602
        command, shell=True, cwd=str(cwd), capture_output=True, text=True
    )
    output = (proc.stdout + proc.stderr).strip()
    if verbose and output:
        print(output, file=sys.stderr)
    return proc.returncode, output


def certify(
    root: Path, base: str, test_cmd: str, test_files: list[Path],
    expect_red_exit: int | None, verbose: bool, allow_red_error: bool = False,
) -> dict:
    safe_files: list[Path] = []
    for relative in test_files:
        # The red run copies these into a throwaway worktree; an absolute path or
        # one containing ".." would read and write outside both roots, which is
        # exactly the isolation this tool promises.
        if relative.is_absolute():
            sys.exit(f"error: --test-file {relative} must be repository-relative, not absolute")
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root.resolve()):
            sys.exit(f"error: --test-file {relative} escapes the repository")
        if not resolved.is_file():
            sys.exit(f"error: --test-file {relative} does not exist in the working tree")
        safe_files.append(relative)
    test_files = safe_files

    tmp_parent = tempfile.mkdtemp(prefix="verified-red-")
    worktree = Path(tmp_parent) / "tree"
    result: dict = {"base": base, "testCommand": test_cmd,
                    "testFiles": [str(p) for p in test_files]}
    try:
        git(root, "worktree", "add", "--detach", "--quiet", str(worktree), base)
        for relative in test_files:
            target = worktree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, target)

        red_code, red_output = run_test(test_cmd, worktree, "RED (fix absent)", verbose)
        result["redExitCode"] = red_code
        result["redTail"] = red_output[-800:]
    finally:
        git(root, "worktree", "remove", "--force", str(worktree), check=False)
        shutil.rmtree(tmp_parent, ignore_errors=True)
        git(root, "worktree", "prune", check=False)

    green_code, green_output = run_test(test_cmd, root, "GREEN (fix present)", verbose)
    result["greenExitCode"] = green_code
    result["greenTail"] = green_output[-800:]

    red_ok = (red_code != 0) if expect_red_exit is None else (red_code == expect_red_exit)
    # A red run that never got as far as running the test is not a reproduction,
    # however non-zero it exited.
    unrelated = red_ok and not allow_red_error and bool(INFRASTRUCTURE_RED.search(red_output))
    green_ok = green_code == 0
    result["redFailedAsRequired"] = red_ok and not unrelated
    result["redFailedBeforeTesting"] = unrelated
    result["greenPassed"] = green_ok
    result["certified"] = red_ok and green_ok and not unrelated
    if unrelated:
        result["verdict"] = (
            "NOT CERTIFIED: the red run failed before it could test anything — the output reads "
            "as a missing import, module, or test file rather than as the bug. The red worktree "
            "is the base commit plus only the files named by --test-file, so pass every file the "
            "test needs (conftest.py, fixtures, helpers) that does not exist at base. Use "
            "--allow-red-error when the import failure *is* the bug you fixed."
        )
    elif not red_ok:
        result["verdict"] = (
            "NOT CERTIFIED: the test passed without the fix — it does not guard the behavior "
            "you fixed. Check that the reproduction actually exercises the changed path, and "
            "that --base really excludes the fix."
        )
    elif not green_ok:
        result["verdict"] = "NOT CERTIFIED: the test fails with the fix present — the fix is incomplete."
    else:
        result["verdict"] = "CERTIFIED: fails without the fix, passes with it."
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="HEAD", help="commit the fix is absent from")
    parser.add_argument("--test-cmd", required=True, help="command that runs the reproduction")
    parser.add_argument(
        "--test-file", type=Path, action="append", default=[], required=True,
        help="repo-relative test file to carry into the red run (repeatable)",
    )
    parser.add_argument("--expect-red-exit", type=int, default=None)
    parser.add_argument(
        "--allow-red-error", action="store_true",
        help="accept a red run that died on a missing import or collection error "
             "(only when that failure *is* the bug being fixed)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="show both runs' output")
    args = parser.parse_args()

    root = args.root.resolve()
    toplevel = git(root, "rev-parse", "--show-toplevel", check=False)
    if toplevel.returncode != 0:
        sys.exit(f"error: {root} is not a git repository")
    # A subdirectory root would copy test files relative to it while the red run
    # executes at the worktree root, so the two halves would not run the same
    # thing and could certify on a mismatch.
    resolved_top = Path(toplevel.stdout.strip()).resolve()
    if resolved_top != root:
        sys.exit(f"error: --root must be the repository toplevel ({resolved_top}), not a subdirectory")
    if args.expect_red_exit == 0:
        sys.exit("error: --expect-red-exit 0 would accept a passing red run, which certifies nothing")

    result = certify(
        root, args.base, args.test_cmd, args.test_file, args.expect_red_exit,
        args.verbose, args.allow_red_error,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\nred run  exit {result['redExitCode']}  (must be non-zero)")
        print(f"green run exit {result['greenExitCode']}  (must be zero)")
        print(f"\n{result['verdict']}")
    return 0 if result["certified"] else 2


if __name__ == "__main__":
    sys.exit(main())
