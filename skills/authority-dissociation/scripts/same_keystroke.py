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
# Extensions whose files are program source. `authorization.py`,
# `approval-handler/index.go` and `certified_client/main.rs` IMPLEMENT this
# vocabulary rather than record anyone's ruling, and treating them as
# attestations lit up every repository that has an auth module — burying the
# findings that matter, which is the failure this pattern list already avoids
# by leaving "review" out. A glob the caller supplied explicitly still matches
# them: they know their own layout.
CODE_SUFFIXES = (
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go", ".rs", ".java",
    ".kt", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".scala", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss", ".vue", ".svelte",
)
# The unit separator, not NUL: a NUL cannot be passed in argv at all, so a
# --format carrying one dies before git sees it.
SEP = "\x1f"
# Statuses that mean the commit WROTE this path. A commit deleting a stale
# approval is not an attestation, and counting it as one reported the tidying
# of old records as the very failure the records were kept to prevent.
WRITTEN = ("A", "M")


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


def is_evidence(path: str, patterns: tuple[str, ...],
                explicit: tuple[str, ...] = ()) -> bool:
    """Does this path name an attestation record?

    Matched against the whole path and each component, case-insensitively, so
    both `approvals/2024-03-11.md` and `docs/RULING-14.md` are caught. On a
    program-source path only `explicit` — the globs the caller passed on the
    command line — applies; see CODE_SUFFIXES.
    """
    lowered = path.lower()
    usable = explicit if lowered.endswith(CODE_SUFFIXES) else patterns
    parts = [lowered, *lowered.split("/")]
    return any(fnmatch.fnmatch(part, pattern)
               for part in parts for pattern in usable)


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


def files_in(repo: Path, sha: str) -> list[tuple[str, str]]:
    """(status, path) for everything a commit touched, oldest form first.

    Status, not just the name: `--name-only` cannot tell writing a record from
    deleting one, and only a written record attests anything.
    """
    out = git(repo, "show", "--name-status", "--format=", "--no-renames", sha)
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip() and parts[-1].strip():
            rows.append((parts[0].strip()[0], parts[-1].strip()))
    return rows


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


def _split(repo: Path, sha: str, patterns: tuple[str, ...],
           explicit: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """(attestations written, other paths touched) for one commit."""
    touched = files_in(repo, sha)
    evidence = sorted({path for status, path in touched
                       if status in WRITTEN and is_evidence(path, patterns, explicit)})
    other = sorted({path for _status, path in touched
                    if not is_evidence(path, patterns, explicit)})
    return evidence, other


def _before(repo: Path, rev_range: str | None, patterns: tuple[str, ...],
            explicit: tuple[str, ...]) -> tuple[str, str, str] | None:
    """The work commit immediately before a range, when there is one.

    `main..HEAD` iterates only what is inside the range, so a sequence whose
    work commit is `main` itself and whose approval is the first commit in the
    range came back clean — the shape most likely to be scanned, reported as
    the shape it was scanned for.
    """
    inside = commits_in(repo, rev_range)
    if not inside:
        return None
    try:
        row = git(repo, "log", "--no-merges", "-1",
                  f"--format=%H{SEP}%an <%ae>{SEP}%s", f"{inside[0][0]}^")
    except GitUnavailable:                  # a root commit has no parent
        return None
    parts = row.strip().split(SEP, 2)
    if len(parts) != 3:
        return None
    sha, author, subject = (part.strip() for part in parts)
    evidence, other = _split(repo, sha, patterns, explicit)
    return (sha, author, subject) if other and not evidence else None


def scan(repo: Path, rev_range: str | None, patterns: tuple[str, ...],
         explicit: tuple[str, ...] = ()) -> list[dict]:
    findings: list[dict] = []
    # The work commit DIRECTLY before this one. Any attestation commit in
    # between ends the relationship: an approval by a second party sitting
    # between the work and a later approval by its author is exactly the
    # independent step the check exists to look for, and carrying the older
    # work forward past it reported "no second party in between" about a
    # history that had one.
    preceding = _before(repo, rev_range, patterns, explicit)

    for sha, author, subject in commits_in(repo, rev_range):
        evidence, other = _split(repo, sha, patterns, explicit)

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

        preceding = (sha, author, subject) if other and not evidence else None
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
                             "repeatable. Adds to the built-in set, and unlike "
                             "the built-ins it also matches program source.")
    parser.add_argument("--only-glob", action="store_true",
                        help="use ONLY the supplied globs, not the built-ins")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    extra = tuple(g.lower() for g in args.evidence_glob)
    if args.only_glob and not extra:
        parser.error("--only-glob needs at least one --evidence-glob")
    patterns = extra if args.only_glob else EVIDENCE_PATTERNS + extra

    try:
        findings = scan(args.repo, args.range, patterns, extra)
    except GitUnavailable as exc:
        print(f"SAME KEYSTROKE — REFUSE: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(findings, indent=2) if args.json else render(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
