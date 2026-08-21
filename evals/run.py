#!/usr/bin/env python3
"""Local behavioral evals for skills, driven by the locally authenticated `claude` CLI.

LOCAL-ONLY BY DESIGN: this never runs in CI. It shells out to `claude -p`,
which uses the developer's own Claude Code login — so no LLM API key ever
exists in this repository or its GitHub configuration.

Each case stages a temp project with the skill symlinked into
`.claude/skills/`, runs the prompt headlessly, and applies regex checks to
the output.

  python3 evals/run.py                       # all cases
  python3 evals/run.py --skill error-taxonomy
  python3 evals/run.py --case e1 --verbose
  python3 evals/run.py --baseline            # also run without the skill (informational)

Case modes:
  explicit — the prompt names the skill; tests that the skill's CONTENT
             produces the required behavior. Pass/fail.
  implicit — the prompt does not name the skill; tests TRIGGERING via the
             description. Informational only (reported, never fails the run),
             because triggering is probabilistic by nature.

Extra `claude` flags (e.g. a model override) via CLAUDE_EVAL_ARGS.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES_DIR = REPO / "evals" / "cases"
TIMEOUT_S = 300


def run_claude(prompt: str, workdir: Path, verbose: bool) -> str:
    cmd = ["claude", "-p", prompt, *shlex.split(os.environ.get("CLAUDE_EVAL_ARGS", ""))]
    try:
        proc = subprocess.run(
            cmd, cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return "<<TIMEOUT>>"
    except FileNotFoundError:
        sys.exit("claude CLI not found — install and log in to Claude Code first")
    out = proc.stdout.strip()
    if verbose:
        print(f"    --- output ---\n{out}\n    --------------")
    if proc.returncode != 0 and not out:
        return f"<<CLAUDE_ERROR rc={proc.returncode}: {proc.stderr.strip()[:300]}>>"
    return out


def stage(skill: str | None) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="skill-eval-")
    if skill is not None:
        skills_dir = Path(tmp.name) / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / skill).symlink_to(REPO / "skills" / skill)
    return tmp


def check_output(output: str, checks: list[dict]) -> list[tuple[str, bool]]:
    """Each check as (label, passed).

    `"absent": true` inverts the match: the case passes when the pattern is NOT
    found. That is what makes a mis-trigger case possible — a suite whose every
    assertion is "this word appeared" cannot fail for a skill that fires when it
    should not, and a check that cannot fail proves nothing.
    """
    results = []
    for chk in checks:
        flags = re.I if "i" in chk.get("flags", "") else 0
        found = re.search(chk["pattern"], output, flags | re.M) is not None
        absent = bool(chk.get("absent"))
        label = ("NOT " if absent else "") + chk["pattern"]
        results.append((label, found != absent))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", help="run only this skill's cases")
    ap.add_argument("--case", dest="case_id", help="run only the case with this id")
    ap.add_argument("--baseline", action="store_true", help="also run each case without the skill")
    ap.add_argument("--verbose", action="store_true", help="print model output")
    args = ap.parse_args()

    failures = 0
    ran = 0
    for case_file in sorted(CASES_DIR.glob("*.json")):
        spec = json.loads(case_file.read_text())
        skill = spec["skill"]
        if args.skill and skill != args.skill:
            continue
        if not (REPO / "skills" / skill).is_dir():
            sys.exit(f"{case_file.name}: unknown skill {skill!r}")
        for case in spec["cases"]:
            if args.case_id and case["id"] != args.case_id:
                continue
            ran += 1
            mode = case.get("mode", "explicit")
            label = f"{skill}/{case['id']} [{mode}]"
            print(f"RUN   {label}")
            with stage(skill) as tmp:
                out = run_claude(case["prompt"], Path(tmp), args.verbose)
            results = check_output(out, case["checks"])
            ok = all(passed for _, passed in results)
            for pattern, passed in results:
                print(f"      {'ok  ' if passed else 'MISS'} /{pattern}/")
            if ok:
                print(f"PASS  {label}")
            elif mode == "implicit":
                print(f"INFO  {label}: did not trigger/conform (informational)")
            else:
                failures += 1
                print(f"FAIL  {label}")
                if not args.verbose:
                    print(f"      output was: {out[:400]}")
            if args.baseline:
                with stage(None) as tmp:
                    base_out = run_claude(case["prompt"], Path(tmp), args.verbose)
                base_ok = all(p for _, p in check_output(base_out, case["checks"]))
                print(f"BASE  {label}: baseline {'ALSO PASSES (check may not discriminate)' if base_ok else 'fails, as expected'}")

    if ran == 0:
        sys.exit("no cases matched")
    print(f"\n{'FAIL' if failures else 'OK'}  {ran} case(s), {failures} failing (explicit mode)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
