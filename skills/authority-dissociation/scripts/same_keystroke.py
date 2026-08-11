#!/usr/bin/env python3
"""Find self-attestation in git history — the claim and its evidence written together.

Two mechanical signatures, both of which mean "no independent party ever
touched this record":

  self-attested-commit  one commit writes both an attestation artifact and the
                        work it attests. This is the exact shape of the incident
                        this skill is named for: the status and the field
                        certifying it were written in the same keystroke, and
                        the control that read that field could not tell.

  self-attested-sequence
                        an attestation-only commit written by the same author
                        as the work it follows. This is the same failure with
                        the same-commit tell removed, which is what splitting
                        the commit in two buys and all it buys.

This reports STRUCTURE, not intent. A solo repository still lights up on
self-attested commits, and that is the honest answer to "is this independently
attested?" rather than a defect to suppress — the fix there is to claim no
independent attestation, not to silence the check.

Exit 0 clean · 1 findings · 2 git unavailable or not a repository.
Standard library only. No network.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

# Path fragments that name a record asserting someone approved, authorised, or
# certified something. Deliberately not "review": a review is a discussion, and
# matching it would bury the findings that matter under every code-review note.
EVIDENCE_PATTERNS = (
    "*approval*", "*approved*", "*ruling*", "*signoff*", "*sign-off*",
    "*sign_off*", "*signed-off*", "*attestation*", "*attested*", "*waiver*",
    "*authoriz*", "*authoris*", "*certification*", "*certified*", "*endorsement*",
)
# The unit separator, not NUL: a NUL cannot be passed in argv at all, so a
# --format carrying one dies before git sees it.
SEP = "\x1f"


class GitUnavailable(RuntimeError):
    """git is missing, or this is not a repository."""


def git(repo: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True)
    except FileNotFoundError as exc:                      # no git on PATH
        raise GitUnavailable("git is not installed") from exc
    if proc.returncode != 0:
        raise GitUnavailable(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def is_evidence(path: str, patterns: tuple[str, ...]) -> bool:
    """Does this path name an attestation record?

    Matched against the whole path and each component, case-insensitively, so
    both `approvals/2024-03-11.md` and `docs/RULING-14.md` are caught.
    """
    lowered = path.lower()
    parts = [lowered, *lowered.split("/")]
    return any(fnmatch.fnmatch(part, pattern)
               for part in parts for pattern in patterns)


def commits_in(repo: Path, rev_range: str | None) -> list[tuple[str, str, str]]:
    """(sha, author, subject), oldest first."""
    args = ["log", "--no-merges", "--reverse", f"--format=%H{SEP}%an <%ae>{SEP}%s"]
    if rev_range:
        args.append(rev_range)
    rows = []
    for line in git(repo, *args).splitlines():
        parts = line.split(SEP, 2)
        if len(parts) == 3:
            rows.append(tuple(part.strip() for part in parts))
    return rows


def files_in(repo: Path, sha: str) -> list[str]:
    """Paths a commit touched. A root commit has no parent to diff against."""
    out = git(repo, "show", "--name-only", "--format=", "--no-renames", sha)
    return [line.strip() for line in out.splitlines() if line.strip()]


def authors_of(repo: Path, path: str | None = None) -> list[str]:
    """Distinct authors of a path's revisions, or of the whole repository.

    No `--follow`: attestation files are short and often near-identical, so
    rename detection links unrelated approvals and imports the earlier file's
    author. That made a genuinely second-party attestation look co-authored.
    """
    args = ["log", "--format=%an <%ae>"]
    if path is not None:
        args += ["--", path]
    seen, ordered = set(), []
    for line in git(repo, *args).splitlines():
        name = line.strip()
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def scan(repo: Path, rev_range: str | None, patterns: tuple[str, ...]) -> list[dict]:
    findings: list[dict] = []
    # The most recent commit that changed something other than attestations —
    # the work an attestation-only commit is plausibly attesting.
    preceding: tuple[str, str, str] | None = None

    for sha, author, subject in commits_in(repo, rev_range):
        paths = files_in(repo, sha)
        evidence = [p for p in paths if is_evidence(p, patterns)]
        other = [p for p in paths if p not in set(evidence)]

        if evidence and other:
            findings.append({
                "check": "self-attested-commit",
                "commit": sha[:12],
                "author": author,
                "subject": subject[:120],
                "evidence": sorted(evidence)[:6],
                "attested": sorted(other)[:6],
                "message": (
                    f"one commit writes {len(evidence)} attestation file(s) and "
                    f"{len(other)} other file(s). The claim and the evidence for "
                    f"it were authored together, so the evidence certifies "
                    f"nothing a reader could not already see in the diff."),
            })
        elif evidence and preceding and preceding[1] == author:
            # Splitting the same work into two commits removes the tell and
            # nothing else: the same hand still wrote the work and its
            # certificate, with no second party between them.
            findings.append({
                "check": "self-attested-sequence",
                "commit": sha[:12],
                "author": author,
                "subject": subject[:120],
                "evidence": sorted(evidence)[:6],
                "attested": [f"{preceding[0][:12]} {preceding[2][:80]}"],
                "message": (
                    f"an attestation-only commit by {author}, immediately "
                    f"following that author's own change. Separate commits, one "
                    f"hand, no second party in between."),
            })

        if other:
            preceding = (sha, author, subject)
    return findings


def render(findings: list[dict]) -> str:
    if not findings:
        return "SAME KEYSTROKE — no self-attestation found"
    lines = [f"SAME KEYSTROKE — {len(findings)} finding(s)"]
    for f in findings:
        lines += [
            f"  {f['commit']}  [{f['check']}]  {f['subject']}",
            f"      by:          {f['author']}",
            f"      attestation: {', '.join(f['evidence'])}",
            f"      alongside:   {', '.join(f['attested'])}",
            f"      {f['message']}",
        ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Did anyone independent write the evidence?")
    parser.add_argument("range", nargs="?", default=None,
                        help="git revision range, e.g. main..HEAD "
                             "(default: the whole history)")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="repository to inspect (default: .)")
    parser.add_argument("--evidence-glob", action="append", default=[],
                        metavar="GLOB",
                        help="extra path glob naming an attestation record; "
                             "repeatable. Adds to the built-in set.")
    parser.add_argument("--only-glob", action="store_true",
                        help="use ONLY the supplied globs, not the built-ins")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    extra = tuple(g.lower() for g in args.evidence_glob)
    if args.only_glob and not extra:
        parser.error("--only-glob needs at least one --evidence-glob")
    patterns = extra if args.only_glob else EVIDENCE_PATTERNS + extra

    try:
        findings = scan(args.repo, args.range, patterns)
    except GitUnavailable as exc:
        print(f"SAME KEYSTROKE — REFUSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(findings, indent=2) if args.json else render(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
