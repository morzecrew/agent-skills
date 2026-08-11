#!/usr/bin/env python3
"""Report word-runs this repository shares with an outside corpus.

Skills here are distilled from private notes and internal write-ups. The rules
travel; the sentences are not ours to publish. Removing figures and domain
nouns is not enough — distinctive phrasing carries just as much of someone
else's document, and it survives a search for numbers untouched.

    python3 scripts/borrowed_prose.py --corpus ~/notes skills/foo/SKILL.md

Any run of >= 7 words shared with the corpus is reported. Universal Python
boilerplate is filtered; everything else is a passage to rewrite in your own
words or drop. Exit 0 clean, 1 findings, 2 nothing could be read.

Every path this tool takes to "clean" has to mean *checked and clean*. An
unreadable corpus, an unreadable target, and a corpus that matched nothing all
looked identical from the outside, so a scan that never compared anything
reported the same reassuring zero as a scan that did.

This is a local authoring aid, never CI: the corpus is private and must not
enter the repository.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CORPUS_SUFFIXES = {".md", ".py", ".json", ".txt", ".rst"}
MAX_CORPUS_BYTES = 400_000

# Openings that any two Python files share regardless of authorship. Matched as
# a PREFIX and then stripped: a run that merely begins with an idiom and
# continues into distinctive prose is reported from where the idiom ends, since
# dropping the whole run hid the borrowed half behind the universal one.
BOILER = re.compile(
    r"^(from future import|import |parser add argument|if name main|"
    r"tempfile import|path write text|re import sys|args parser parse args|"
    r"else 0 if name|json loads path read text|read text encoding utf 8|"
    r"int m group|str set str return|re compile r a za z0 9|"
    r"verdict if name main|parent mkdir parents true exist ok|"
    r"subprocess import sys from pathlib|return 0 if name main|"
    r"r for r in rows if r|self assertequal|self assertin|self asserttrue|"
    r"def test )")


def norm(text: str) -> str:
    """Letters, digits and single spaces — punctuation and case carry no claim."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def corpus_files(roots: list[Path]) -> list[Path]:
    """Every candidate file under the given files and directories."""
    found: list[Path] = []
    for root in roots:
        if root.is_file():
            found.append(root)
        elif root.is_dir():
            found += [q for q in root.rglob("*")
                      if q.is_file() and q.suffix in CORPUS_SUFFIXES
                      and q.stat().st_size < MAX_CORPUS_BYTES
                      and "/.git/" not in str(q)]
    return found


def build_index(files: list[Path], n: int) -> tuple[set[str], int, str]:
    """(n-grams, files read, last read error). Never raises on a bad file."""
    grams: set[str] = set()
    read = 0
    problem = ""
    for path in files:
        try:
            words = norm(path.read_text(errors="replace")).split()
        except (OSError, UnicodeError) as exc:      # recoverable only
            problem = f"{path}: {exc}"
            continue
        read += 1
        grams.update(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))
    return grams, read, problem


def spans(words: list[str], grams: set[str], n: int) -> list[tuple[int, int]]:
    """Half-open word ranges covered by at least one matching window.

    Windows are merged by COVERAGE, not by adjacency of their start positions.
    Jumping the cursor past a finished run skipped every start inside its tail:
    with runs `a..g` and `c..i` both in the corpus, the failed window at start 1
    moved the cursor beyond start 2, and the second match — the half that ran on
    past the first — was never reported at all.
    """
    last = len(words) - n
    merged: list[list[int]] = []
    for start in range(last + 1):
        if " ".join(words[start:start + n]) not in grams:
            continue
        if merged and start < merged[-1][1]:        # overlaps the open span
            merged[-1][1] = start + n
        else:
            merged.append([start, start + n])
    return [(a, b) for a, b in merged]


def surviving(words: list[str], n: int) -> list[str]:
    """The run with any leading boilerplate removed, or nothing if too little
    is left. A prefix of shared idiom does not excuse the sentence after it."""
    match = BOILER.match(" ".join(words))
    rest = words[len(match.group(0).split()):] if match else words
    return rest if len(rest) >= n else []


def runs_in(text: str, grams: set[str], n: int) -> list[str]:
    words = norm(text).split()
    found = []
    for start, end in spans(words, grams, n):
        run = surviving(words[start:end], n)
        if run:
            found.append(" ".join(run))
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="repository files to check")
    parser.add_argument("--corpus", action="append", required=True, type=Path,
                        help="a private file or directory to compare against; "
                             "repeatable")
    parser.add_argument("--words", type=int, default=7,
                        help="shortest run to report (default: 7)")
    args = parser.parse_args(argv)

    # A zero-word gram matches at every position without consuming anything, so
    # the scan advanced past nothing and ran until it was killed.
    if args.words < 1:
        parser.error("--words must be at least 1")

    files = corpus_files(args.corpus)
    if not files:
        print("borrowed-prose: no corpus files found", file=sys.stderr)
        return 2

    grams, read, problem = build_index(files, args.words)
    if not read:
        print(f"borrowed-prose: no corpus file could be read ({problem})",
              file=sys.stderr)
        return 2

    total = 0
    for name in args.files:
        try:
            text = Path(name).read_text(errors="replace")
        except OSError as exc:
            print(f"borrowed-prose: {exc}", file=sys.stderr)
            return 2
        runs = runs_in(text, grams, args.words)
        if runs:
            print(f"=== {name}")
            for run in runs:
                print(f"   [{len(run.split())}w] {run}")
            total += len(runs)
    print(f"TOTAL: {total} non-boilerplate run(s) of >= {args.words} words "
          f"against {read} corpus file(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
