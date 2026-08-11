#!/usr/bin/env python3
"""Scan a diff for a check being widened rather than satisfied.

The tell is exact: a check you wrote fails on your own change, and the fix
begins "but in this case it's fine." It may well be fine. The check's value was
never about this case — a scan that returns clean AFTER subtracting a list of
declared exceptions proves only that whoever added the last exception remembered
to declare it.

Three shapes, all read off the diff:

  suppression        an inline silencer added — noqa, type: ignore, nosec,
                     eslint-disable, #[allow(...)], @SuppressWarnings, a skipped
                     or xfailed test.
  allowlist-entry    a line added to (or naming) an allowlist, exemption list,
                     waiver, or known-failures collection.
  deleted-assertion  an assertion removed from a test. Enforcement can be
                     weakened by subtraction as easily as by exception.

Every finding is a QUESTION, not automatically a defect: exceptions are
sometimes right. The answer belongs in the change description, where a reviewer
can see it — which is the whole point, since the alternative is that it is
visible nowhere.

Standard library only. Reads `git diff`, or a unified diff on stdin.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SUPPRESSION = re.compile(
    r"""(?ix)
    \#\s*noqa | \#\s*type:\s*ignore | \#\s*nosec | \#\s*pragma:\s*no\s*cover
  | \#\s*pylint:\s*disable | \#\s*ruff:\s*noqa | \#\s*mypy:\s*ignore
  | eslint-disable | @ts-(?:ignore|nocheck|expect-error) | istanbul\s+ignore
  | //\s*nolint | \#\[allow\( | \#\[cfg_attr\([^)]*allow
  | @SuppressWarnings | @Suppress\b
  | @unittest\.skip | @pytest\.mark\.(?:skip|xfail) | \bxit\( | \bxdescribe\(
  | \.skip\s*\( | \bskipTest\(
    """)

# These names live inside SNAKE_CASE identifiers — ALLOWED_IMPORTS,
# LINT_EXCEPTIONS, PATH_EXCLUDED — and "_" is a word character, so `\b` matches
# nothing that matters here. The boundary that works is "not a letter".
ALLOWLIST = re.compile(
    r"""(?ix)
    allow_?(?:list|ed) | white_?list | safe_?list | permit_?list
  | exempt\w* | exclusion\w* | (?<![a-z])excluded?(?![a-z])
  | (?<![a-z])waiv(?:er|ers|ed)(?![a-z])
  | ignore(?:d|s)?_(?:files|paths|rules|errors|list)
  | known_(?:failures|issues|bad|broken) | expected_failures
  | grandfather\w* | carve_?out | legacy_(?:exceptions|allowed)
  | suppressions? | bypass(?:es|ed)?
    # PLURAL only, and the qualified singular. Bare "exception" would match
    # `except Exception:` and `raise Exception(...)`, so every try/except in
    # every diff would report as an exemption — and a scanner that cries wolf
    # is deleted along with its findings.
  | (?<![a-z])exceptions(?![a-z]) | exception_(?:list|paths|rules|files)
    """)

ASSERTION = re.compile(
    r"""(?x)
    ^\s*(?: assert\b | self\.assert | cls\.assert | expect\s*\( | should\.
          | require\s*\( | ASSERT_[A-Z] | EXPECT_[A-Z] | t\.(?:Error|Fatal)f?\(
          | chai\.expect | \.toEqual\( | \.toThrow\( )
    """)
# A bare string element on its own line: the shape of an entry appended to an
# existing allowlist, where the collection's NAME is elsewhere in the hunk.
ENTRY = re.compile(r"""^\s*[-+]?\s*["'][^"']*["'],?\s*(?:\#.*|//.*)?$""")

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")
# A comment that talks ABOUT allowlists is prose, not an entry in one. Left in
# and this tool reports its own source file forty times, which is the shape of
# a check nobody runs twice. Suppressions are exempt — those ARE comments.
COMMENT_ONLY = re.compile(r"""^\s*(?:\#|//|/\*|\*(?!/)|<!--|--\s|;{1,2}\s)""")
# Prose files hold no check to widen.
PROSE_SUFFIXES = (".md", ".rst", ".txt", ".adoc", ".org")


def read_diff(args) -> str:
    """The unified diff to scan, from stdin or from git."""
    if args.patch:
        return sys.stdin.read() if str(args.patch) == "-" else \
            Path(args.patch).read_text(encoding="utf-8", errors="replace")
    cmd = ["git", "-C", str(args.repo), "diff", "--unified=3", "--no-color"]
    if args.staged:
        cmd.append("--cached")
    if args.range:
        cmd.append(args.range)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return proc.stdout


def parse(diff: str):
    """Yield (path, hunk_lines) where each hunk line is (sign, lineno, text).

    `lineno` is the NEW file's line for context and additions, and the OLD
    file's line for deletions — the number a reader needs to find it.
    """
    path = None
    old = new = 0
    born = False
    current: list[tuple[str, int, str]] = []
    for raw in diff.splitlines():
        if raw.startswith("--- "):
            # `--- /dev/null` means the file is NEW. A new file cannot be a
            # check being widened — there was no check there to widen — and
            # scanning one reports every mention of the vocabulary it contains.
            born = raw[4:].strip() == "/dev/null"
        elif raw.startswith("+++ "):
            if path and current:
                yield path, current
            target = raw[4:].strip()
            path = None if born or target == "/dev/null" else re.sub(r"^b/", "", target)
            if path and path.lower().endswith(PROSE_SUFFIXES):
                path = None       # prose holds no check to widen
            current = []
        elif (m := HUNK.match(raw)):
            if path and current:
                yield path, current
            old, new = int(m.group(1)), int(m.group(2))
            # git appends the enclosing section to the @@ header. That is often
            # where the allowlist's NAME lives — the entry added below it is a
            # bare string with nothing incriminating about it — so the header
            # rides along as hunk context. Sign "@" so the per-line scan skips it.
            current = [("@", new, m.group(3))]
        elif path is None or raw.startswith(("diff ", "index ", "new file",
                                             "deleted file", "similarity ",
                                             "rename ", "old mode", "new mode",
                                             "Binary files")):
            continue
        elif raw.startswith("+"):
            current.append(("+", new, raw[1:]))
            new += 1
        elif raw.startswith("-"):
            current.append(("-", old, raw[1:]))
            old += 1
        elif raw.startswith(" "):
            current.append((" ", new, raw[1:]))
            old += 1
            new += 1
    if path and current:
        yield path, current


def scan(diff: str) -> list[dict]:
    findings = []
    for path, lines in parse(diff):
        # Hunk-scoped context: an entry added to an existing allowlist carries
        # no allowlist word of its own — the collection's name is a few lines up,
        # unchanged, and only the surrounding hunk can supply it.
        named_here = any(ALLOWLIST.search(text) for _, _, text in lines)
        for sign, lineno, text in lines:
            if sign == "+" and SUPPRESSION.search(text):
                findings.append(_finding(
                    "suppression", path, lineno, text,
                    "an inline silencer was added. Does the code now satisfy "
                    "the check, or has the check been told to look away here?"))
            elif sign == "+" and not COMMENT_ONLY.match(text) and (
                    ALLOWLIST.search(text)
                    or (named_here and ENTRY.match(text))):
                findings.append(_finding(
                    "allowlist-entry", path, lineno, text,
                    "an exemption was added or extended. Fix the code, not the "
                    "check — and if the exception is genuine, make the gate "
                    "re-verify it so a stale waiver fails when reality changes."))
            elif sign == "-" and ASSERTION.match(text):
                findings.append(_finding(
                    "deleted-assertion", path, lineno, text,
                    "an assertion was removed. Enforcement weakens by "
                    "subtraction as easily as by exception."))
    return findings


COMBINED = re.compile(r"^(?:@@@|diff --cc )", re.M)
FILE_HEADER = re.compile(r"^\+\+\+ ", re.M)


def unreadable(diff: str) -> str | None:
    """Why this input cannot be scanned, or None.

    Reporting "clean" because the parser understood nothing is the worst answer
    a check can give — it is indistinguishable from the good news. Combined
    diffs (`git diff --cc`, merge commits) use a three-column format this
    parser does not read, and would otherwise come back silently empty.
    """
    if not diff.strip():
        return None                      # genuinely no changes
    if COMBINED.search(diff):
        return ("combined (merge) diff format is not supported — scan the "
                "merge's parents individually")
    if not FILE_HEADER.search(diff):
        return "no unified-diff file headers found in the input"
    return None


def _finding(check: str, path: str, line: int, text: str, message: str) -> dict:
    return {"check": check, "file": path, "line": line,
            "text": text.strip()[:160], "message": message}


def render(findings: list[dict]) -> str:
    if not findings:
        return "EXCEPTION CREEP — clean"
    lines = [f"EXCEPTION CREEP — {len(findings)} finding(s) to answer in the "
             f"change description"]
    for f in findings:
        lines.append(f"  {f['file']}:{f['line']}  [{f['check']}]")
        lines.append(f"      {f['text']}")
        lines.append(f"      {f['message']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Is a check being widened instead of satisfied?")
    parser.add_argument("range", nargs="?", default=None,
                        help="git revision range, e.g. main..HEAD "
                             "(default: unstaged changes)")
    parser.add_argument("--staged", action="store_true",
                        help="scan the staged changes instead")
    parser.add_argument("--patch", default=None, metavar="FILE",
                        help="read a unified diff from FILE, or - for stdin")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="repository to run git in (default: .)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        diff = read_diff(args)
    except (OSError, RuntimeError) as exc:
        print(f"EXCEPTION CREEP — REFUSE: {exc}", file=sys.stderr)
        return 2
    if (why := unreadable(diff)):
        print(f"EXCEPTION CREEP — REFUSE: {why}", file=sys.stderr)
        return 2
    findings = scan(diff)
    print(json.dumps(findings, indent=2) if args.json else render(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
