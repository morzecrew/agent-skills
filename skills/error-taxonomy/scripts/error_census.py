#!/usr/bin/env python3
"""Supporting tool for the error-taxonomy skill: census raise sites before a sweep.

Finds where errors are raised, groups them by **message family** as well as by
package, and lists the codes already in use. The message-family view is the point:
a census grouped only by package misses the small shared helpers that raise the
same thing from a corner nobody greps, and the same situation raised twelve
different ways is exactly what a taxonomy sweep exists to collapse.

  error_census.py [--root DIR] [--kind PATTERN ...] [--languages python,js,...]
                  [--min-cluster 2] [--json]

Message families are formed by normalizing away the parts that vary — quoted
values, numbers, and interpolations — so `f"unknown field {name}"` and
`f"unknown field {other!r}"` land in one family.

  --exclude GLOB  skip paths (commonly 'tests/*' — fixtures raise dummy errors)
  --kind PATTERN  regex naming the kinds/classes you want counted, e.g.
                  --kind 'exc\\.(\\w+)' or --kind 'raise (\\w+Error)'
                  (default: the exception class or factory in the raise)

Exit codes: 0 raise sites found · 1 usage error · 3 none found (check --languages
or the patterns for your stack). Unknown flags exit 2, from argparse itself.

The tool counts and clusters. Which kind each site *should* raise is the
classification test in SKILL.md, and only a reader can apply it.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAISE_PATTERNS: dict[str, str] = {
    "python": r"\braise\s+([A-Za-z_][\w.]*)",
    "js": r"\bthrow\s+new\s+([A-Za-z_][\w.]*)",
    "go": r"\b(errors\.New|fmt\.Errorf)\s*\(",
    "rust": r"\b(Err|panic!|bail!|ensure!)\s*[\(!]",
    # `new` optional for Kotlin, but the target must look like a type and be
    # constructed — otherwise a bare rethrow (`throw e;`) becomes its own kind.
    "java": r"\bthrow\s+(?:new\s+)?([A-Z][\w.]*)\s*\(",
}

SUFFIX_LANGUAGE = {
    ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "java",
}

MESSAGE = re.compile(r"""(?:f?["'])([^"']{4,200})["']""")
CODE_KWARG = re.compile(r"""\bcode\s*=\s*["']([\w.\-]+)["']""")

PLACEHOLDER = re.compile(r"\{[^}]*\}|%[sdrf]|\$\{[^}]*\}")
QUOTED = re.compile(r"""["'][^"']*["']""")
NUMBER = re.compile(r"\b\d+\b")
WHITESPACE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Collapse a message to its family: the wording without the varying parts."""
    text = PLACEHOLDER.sub("<>", message)
    text = QUOTED.sub("<>", text)
    text = NUMBER.sub("<>", text)
    text = WHITESPACE.sub(" ", text).strip().lower()
    return text.rstrip(".:! ")


TRIPLE_QUOTE = re.compile(r'"""|\'\'\'')


def code_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Drop comments and docstring bodies before counting raises.

    Prose and examples mention `raise ...` constantly; counting them inflates the
    census and invents message families that no call site produces.
    """
    kept: list[tuple[int, str]] = []
    in_docstring = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        delimits = bool(TRIPLE_QUOTE.match(stripped)) or bool(
            TRIPLE_QUOTE.search(stripped[-3:]) if len(stripped) >= 3 else False
        )
        quotes = len(TRIPLE_QUOTE.findall(stripped))
        was_in = in_docstring
        if delimits and quotes % 2:
            in_docstring = not in_docstring
        if was_in or (in_docstring and delimits and quotes % 2):
            continue
        # A docstring that opens and closes on one line never toggles the state,
        # but its prose still must not be scanned.
        if TRIPLE_QUOTE.match(stripped) and quotes >= 2 and quotes % 2 == 0:
            continue
        if stripped.startswith(("#", "//", "*", "/*")):
            continue
        kept.append((number, stripped))
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


def census(
    root: Path, languages: list[str], kind_patterns: list[str], exclude: list[str] | None = None
) -> dict:
    exclude = exclude or []
    raise_res = {
        language: re.compile(pattern)
        for language, pattern in RAISE_PATTERNS.items()
        if language in languages
    }
    kind_res = [re.compile(pattern) for pattern in kind_patterns]
    sites: list[dict] = []

    for path in tracked_files(root):
        language = SUFFIX_LANGUAGE.get(path.suffix.lower())
        if language not in raise_res:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        relative = str(path.relative_to(root))
        if any(fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern)
               for pattern in exclude):
            continue
        for number, stripped in code_lines(lines):
            match = raise_res[language].search(stripped)
            if not match:
                continue
            # The message often trails onto the next line — but only join when
            # the raise expression is still open, or an unrelated statement's
            # string is attributed to this raise.
            window = stripped
            if (
                number < len(lines)
                and not MESSAGE.search(stripped)
                and stripped.count("(") > stripped.count(")")
            ):
                window = stripped + " " + lines[number].strip()

            kind = None
            for kind_re in kind_res:
                found = kind_re.search(window)
                if found:
                    kind = found.group(1) if found.groups() else found.group(0)
                    break
            if kind is None:
                kind = (match.group(1) if match.groups() else "raise").split(".")[-1]

            message_match = MESSAGE.search(window)
            message = message_match.group(1) if message_match else ""
            code_match = CODE_KWARG.search(window)
            sites.append(
                {
                    "file": relative, "line": number, "kind": kind,
                    "code": code_match.group(1) if code_match else None,
                    "message": message, "family": normalize_message(message) if message else "",
                    "package": relative.split("/")[1] if relative.startswith("src/") and "/" in relative[4:]
                    else relative.split("/")[0],
                }
            )

    families: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        if site["family"]:
            families[site["family"]].append(site)

    return {
        "root": str(root),
        "counts": {
            "sites": len(sites),
            "byKind": dict(Counter(s["kind"] for s in sites).most_common()),
            "byPackage": dict(Counter(s["package"] for s in sites).most_common(12)),
            "withCode": sum(1 for s in sites if s["code"]),
            "distinctCodes": len({s["code"] for s in sites if s["code"]}),
        },
        "codes": dict(Counter(s["code"] for s in sites if s["code"]).most_common()),
        "families": {family: hits for family, hits in families.items()},
        "sites": sites,
    }


def render(result: dict, min_cluster: int) -> None:
    counts = result["counts"]
    print(f"{counts['sites']} raise site(s)")
    print(f"  with an explicit code: {counts['withCode']} across {counts['distinctCodes']} distinct code(s)")

    print("\nby kind:")
    for kind, count in list(counts["byKind"].items())[:15]:
        print(f"  {count:>5}  {kind}")

    print("\nby package:")
    for package, count in counts["byPackage"].items():
        print(f"  {count:>5}  {package}")

    clusters = sorted(
        ((family, hits) for family, hits in result["families"].items() if len(hits) >= min_cluster),
        key=lambda pair: -len(pair[1]),
    )
    print(f"\nmessage families appearing >= {min_cluster} times ({len(clusters)}):")
    for family, hits in clusters[:20]:
        kinds = sorted({hit["kind"] for hit in hits})
        files = sorted({hit["file"] for hit in hits})
        print(f"  {len(hits):>4}x  \"{family[:70]}\"")
        print(f"        kinds: {', '.join(kinds)}   files: {len(files)}")
        if len(kinds) > 1:
            print("        ^ one situation, several kinds — the same mistake answers differently per call site")
    if not clusters:
        print("  (none — every message is unique, so there is no family to collapse)")

    print(
        "\nGroup by message family as well as by package: a package-grouped census "
        "misses the shared helpers that raise from a corner nobody greps. Which kind "
        "each site should raise is the classification test, not this tool's call."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--kind", action="append", default=[], metavar="PATTERN",
        help="regex capturing the kind/factory to count (repeatable)",
    )
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="GLOB",
        help="skip paths matching this glob (repeatable; commonly 'tests/*' — "
             "test fixtures raise dummy errors that crowd the clusters)",
    )
    parser.add_argument("--languages", default=",".join(RAISE_PATTERNS))
    parser.add_argument("--min-cluster", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    languages = [name.strip() for name in args.languages.split(",") if name.strip()]
    unknown = [name for name in languages if name not in RAISE_PATTERNS]
    if unknown:
        sys.exit(f"error: unknown language(s): {', '.join(unknown)}")
    if not args.root.is_dir():
        sys.exit(f"error: {args.root} is not a directory")
    for pattern in args.kind:
        try:
            re.compile(pattern)
        except re.error as exc:
            sys.exit(f"error: --kind {pattern!r} is not a valid regex: {exc}")

    result = census(args.root.resolve(), languages, args.kind, args.exclude)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        render(result, args.min_cluster)
    return 0 if result["counts"]["sites"] else 3


if __name__ == "__main__":
    sys.exit(main())
