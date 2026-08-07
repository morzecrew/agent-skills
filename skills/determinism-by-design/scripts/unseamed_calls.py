#!/usr/bin/env python3
"""Supporting tool for the determinism-by-design skill: find unseamed nondeterminism.

Scans for direct calls to the sources that must route through a seam — wall
clock, randomness, UUIDs, environment, and real sleeping — so "every source is
injected" becomes a check instead of a habit.

  unseamed_calls.py [--root DIR] [--seam PREFIX ...] [--allow GLOB ...]
                    [--languages python,js,go,...] [--strict] [--json]

Findings inside a declared seam (`--seam src/pkg/clock.py`) are expected and are
reported separately from leaks. So are files matching `--allow` (tests and
scripts are allowed by default — a test *should* pin the clock, and this tool
would otherwise flag every fixture).

**Warn-first by design.** Without `--strict` it always exits 0: a first run over
an existing codebase finds real seams the tool cannot know about yet, and a check
that cries wolf gets deleted along with its protection. Tune `--seam`/`--allow`
until the leak list is true, *then* add `--strict` to CI (see
`ratchet-what-you-build`).

Exit codes: 0 scanned (warn mode, or strict with no leaks) · 1 usage error ·
2 leaks found under --strict. Unknown flags exit 2, from argparse itself.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# Each entry: (source kind, compiled pattern). Kept deliberately narrow — a
# pattern that fires on ordinary code costs more trust than the leak it catches.
PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": [
        ("clock", r"\b(?:datetime\.)?datetime\.(?:now|utcnow|today)\s*\("),
        ("clock", r"\btime\.(?:time|monotonic|perf_counter|time_ns)\s*\("),
        ("clock", r"\bdate\.today\s*\("),
        ("sleep", r"\b(?:time|asyncio)\.sleep\s*\("),
        ("random", r"\brandom\.(?:random|randint|choice|shuffle|uniform|sample|randrange)\s*\("),
        ("random", r"\bsecrets\.(?:token_hex|token_bytes|token_urlsafe|choice)\s*\("),
        ("uuid", r"\buuid\.uuid[14]\s*\("),
        ("env", r"\bos\.(?:getenv|environ)\b"),
    ],
    "js": [
        ("clock", r"\bDate\.now\s*\(|\b(?:new\s+)?Date\s*\(\s*\)"),
        ("clock", r"\bperformance\.now\s*\("),
        ("sleep", r"\bsetTimeout\s*\("),
        ("random", r"\bMath\.random\s*\("),
        ("uuid", r"\b(?:crypto\.)?randomUUID\s*\(|\buuidv4\s*\("),
        ("env", r"\bprocess\.env\b"),
    ],
    "go": [
        ("clock", r"\btime\.(?:Now|Since)\s*\("),
        ("sleep", r"\btime\.Sleep\s*\("),
        ("random", r"\brand\.(?:Int|Intn|Float64|Perm|Shuffle)\s*\("),
        ("uuid", r"\buuid\.New(?:V4)?\s*\("),
        ("env", r"\bos\.(?:Getenv|LookupEnv)\s*\("),
    ],
    "rust": [
        ("clock", r"\b(?:SystemTime|Instant)::now\s*\("),
        ("sleep", r"\bthread::sleep\s*\(|\btokio::time::sleep\s*\("),
        ("random", r"\bthread_rng\s*\(|\brand::random\s*\("),
        ("uuid", r"\bUuid::new_v4\s*\("),
        ("env", r"\benv::var\s*\("),
    ],
    "java": [
        ("clock", r"\bSystem\.(?:currentTimeMillis|nanoTime)\s*\(|\b(?:LocalDate|LocalDateTime|Instant)\.now\s*\("),
        ("sleep", r"\bThread\.sleep\s*\("),
        ("random", r"\bnew\s+Random\s*\(\s*\)|\bMath\.random\s*\("),
        ("uuid", r"\bUUID\.randomUUID\s*\("),
        ("env", r"\bSystem\.getenv\s*\("),
    ],
}

SUFFIX_LANGUAGE = {
    ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js", ".mjs": "js",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "java",
}

DEFAULT_ALLOW = [
    # Both rooted and nested forms: run from a package root, "tests/x.py" has no
    # leading segment for a "*/tests/*" pattern to match.
    "test/*", "tests/*", "*/test/*", "*/tests/*",
    "test_*", "*_test.*", "*.test.*", "*.spec.*", "*/conftest.py",
    "scripts/*", "*/scripts/*", "migrations/*", "*/migrations/*",
    "examples/*", "*/examples/*", "benchmarks/*", "*/benchmarks/*",
]

# Per language: "#" starts a comment in Python but declares a private field
# in JS/TS, where treating it as a comment hides real calls.
COMMENT_PREFIXES_BY_LANGUAGE = {
    "python": ("#",),
    "js": ("//", "*", "/*"),
    "go": ("//", "*", "/*"),
    "rust": ("//", "*", "/*"),
    "java": ("//", "*", "/*"),
}
COMMENT_PREFIXES = ("#", "//", "*", "/*")
# Anchored to a comment marker: a bare substring can be planted in a string
# literal on the same line to hide a real leak.
DIRECTIVE = re.compile(r"(?:#|//|/\*)[^\n]*\b(?:allow-unseamed|seam-exempt)\b")
TRIPLE_QUOTE = re.compile(r'"""|\'\'\'')
# Trailing comments only — a "#" inside a string literal keeps its line.
TRAILING_COMMENT = re.compile(r'\s+(?:#|//)(?![^\'"]*[\'"]\s*$).*$')
# Block comments carry directives in every C-family language.
# Not preceded by a quote on the line: a string may carry the marker, and
# treating it as a comment would let data disable the scan for its line.
BLOCK_COMMENT = re.compile(r'^[^\'"]*?(/\*.*?\*/)', re.S)


def strip_noise(lines: list[str], language: str = "python") -> list[tuple[int, str]]:
    """Drop comments and docstring bodies — prose naming a function is not a call.

    Documentation routinely mentions the very APIs this tool hunts ("defaults to
    ``time.monotonic()``"), and a scanner that flags prose gets muted.
    """
    kept: list[tuple[int, str]] = []
    in_docstring = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Only a delimiter that opens or closes the line toggles the state: a
        # triple-quote sequence *inside* an ordinary string would otherwise
        # swallow every following line.
        delimits = bool(TRIPLE_QUOTE.match(stripped)) or bool(
            TRIPLE_QUOTE.search(stripped[-3:]) if len(stripped) >= 3 else False
        )
        quotes = len(TRIPLE_QUOTE.findall(stripped))
        was_in = in_docstring
        if delimits and quotes % 2:
            in_docstring = not in_docstring
        # Skip lines inside a docstring *and* the line that opens one.
        if was_in or (in_docstring and delimits and quotes % 2):
            continue
        # A docstring that opens and closes on one line never toggles the state,
        # but its prose still must not be scanned.
        if TRIPLE_QUOTE.match(stripped) and quotes >= 2 and quotes % 2 == 0:
            continue
        prefixes = COMMENT_PREFIXES_BY_LANGUAGE.get(language, COMMENT_PREFIXES)
        if stripped.startswith(prefixes):
            continue
        # Split first, then look for the directive only in the comment: a string
        # containing a comment marker could otherwise exempt its own line.
        comment = TRAILING_COMMENT.search(stripped)
        block = BLOCK_COMMENT.match(stripped)
        if (comment and DIRECTIVE.search(comment.group(0))) or (
            block and DIRECTIVE.search(block.group(1))
        ):
            continue
        # A clock name mentioned in a trailing comment is prose, not a call.
        code = TRAILING_COMMENT.sub("", stripped).strip()
        if not code:
            continue
        kept.append((number, code))
    return kept


def tracked_files(root: Path) -> list[Path]:
    """Tracked files when git is available, else a plain filesystem walk.

    git can be absent entirely (containers, minimal CI images); without this
    guard FileNotFoundError aborts the run before the documented fallback.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files"], capture_output=True, text=True, timeout=60
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return [root / line for line in proc.stdout.splitlines() if line.strip()]
    return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def matches_any(relative: str, globs: list[str]) -> bool:
    name = Path(relative).name
    return any(fnmatch.fnmatch(relative, g) or fnmatch.fnmatch(name, g) for g in globs)


def scan(
    root: Path, languages: list[str], seams: list[str], allow: list[str]
) -> dict:
    compiled = {
        language: [(kind, re.compile(pattern)) for kind, pattern in entries]
        for language, entries in PATTERNS.items()
        if language in languages
    }
    leaks: list[dict] = []
    in_seam: list[dict] = []
    allowed_files: set[str] = set()
    allowed_hits = 0
    scanned = 0

    for path in tracked_files(root):
        language = SUFFIX_LANGUAGE.get(path.suffix.lower())
        if language not in compiled:
            continue
        relative = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        is_seam = any(relative.startswith(prefix) for prefix in seams)
        is_allowed = matches_any(relative, allow)

        for number, stripped in strip_noise(text.splitlines(), language):
            # Every distinct kind on the line, not just the first: one line can
            # read the clock and the environment at once.
            seen_kinds: set[str] = set()
            for kind, pattern in compiled[language]:
                if kind in seen_kinds or not pattern.search(stripped):
                    continue
                seen_kinds.add(kind)
                hit = {
                    "file": relative, "line": number, "kind": kind,
                    "language": language, "text": stripped[:140],
                }
                if is_seam:
                    in_seam.append(hit)
                elif is_allowed:
                    allowed_files.add(relative)
                    allowed_hits += 1
                else:
                    leaks.append(hit)

    by_kind: dict[str, int] = {}
    for leak in leaks:
        by_kind[leak["kind"]] = by_kind.get(leak["kind"], 0) + 1
    return {
        "root": str(root), "filesScanned": scanned,
        "seams": seams, "allowGlobs": allow,
        "counts": {
            "leaks": len(leaks), "insideSeams": len(in_seam),
            "allowedFiles": len(allowed_files), "allowedHits": allowed_hits, "byKind": by_kind,
        },
        "leaks": leaks, "insideSeams": in_seam,
    }


def render(result: dict, strict: bool) -> None:
    counts = result["counts"]
    print(
        f"scanned {result['filesScanned']} file(s): {counts['leaks']} unseamed call(s), "
        f"{counts['insideSeams']} inside declared seams, "
        f"{counts['allowedHits']} in {counts['allowedFiles']} allowed file(s)"
    )
    if result["seams"]:
        print(f"seams: {', '.join(result['seams'])}")
    else:
        print("seams: (none declared — everything outside allowed files counts as a leak)")

    if counts["byKind"]:
        print("\nby source:")
        for kind, count in sorted(counts["byKind"].items(), key=lambda kv: -kv[1]):
            print(f"  {kind:<7} {count}")

    if result["leaks"]:
        print("\nunseamed calls:")
        for leak in result["leaks"][:40]:
            print(f"  {leak['file']}:{leak['line']}  [{leak['kind']}]  {leak['text']}")
        if len(result["leaks"]) > 40:
            print(f"  ... {len(result['leaks']) - 40} more")
        print(
            "\nEach is either a real leak (route it through the seam) or a seam this run "
            "does not know about (add --seam, or mark the line 'allow-unseamed' with a reason)."
        )
    if not strict and result["leaks"]:
        print("\nwarn mode: exiting 0. Tune --seam/--allow until this list is true, then add --strict.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--seam", action="append", default=[], metavar="PREFIX",
        help="path prefix that is allowed to touch the real source (repeatable)",
    )
    parser.add_argument(
        "--allow", action="append", default=[], metavar="GLOB",
        help="extra path globs to exempt (repeatable; added to the defaults)",
    )
    parser.add_argument(
        "--languages", default=",".join(PATTERNS),
        help=f"comma-separated subset of: {', '.join(PATTERNS)}",
    )
    parser.add_argument("--no-default-allow", action="store_true", help="drop the built-in exemptions")
    parser.add_argument("--strict", action="store_true", help="exit 2 when leaks remain")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    languages = [name.strip() for name in args.languages.split(",") if name.strip()]
    unknown = [name for name in languages if name not in PATTERNS]
    if unknown:
        sys.exit(f"error: unknown language(s): {', '.join(unknown)}")
    if not args.root.is_dir():
        sys.exit(f"error: {args.root} is not a directory")

    allow = list(args.allow) if args.no_default_allow else DEFAULT_ALLOW + list(args.allow)
    result = scan(args.root.resolve(), languages, args.seam, allow)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        render(result, args.strict)
    return 2 if (args.strict and result["leaks"]) else 0


if __name__ == "__main__":
    sys.exit(main())
