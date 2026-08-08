#!/usr/bin/env python3
"""Supporting tool for the rfc-writer skill: allocate numbers and keep INDEX.md honest.

  check   validate the collection — index rows vs files (both directions),
          filename number vs H1 number, header status vs table status,
          duplicate numbers, and whether the claimed next-free number is free
  next    print the next free number (max existing + 1), zero-padded
  new     allocate the number, write NNNN-kebab-title.md from the skill's
          template, append the index row, and bump the next-free number

`check` and `next` are read-only. `new` writes two files (the RFC and the index).

The directory is discovered as rfcs/ or rfc/ under --root (default: cwd); the
index is INDEX.md, or README.md where a collection already uses it. Statuses are
compared by their emoji, since the prose after it carries free-form annotations
("✅ Complete — shipped 2026-06-29; only P5 remains").

Exit codes: 0 ok · 1 usage/IO error · 2 check found problems. Unknown flags exit
2, from argparse itself.

Everything this tool does is mechanical. Which number a design deserves, what
the one-liner says, and when a status changes stay in SKILL.md.
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: the lock degrades to none, the rollback stays.
    fcntl = None

STATUS_EMOJI = {"📝": "Draft", "🚧": "In progress", "✅": "Complete", "❌": "Rejected"}

RFC_FILENAME = re.compile(r"^(\d{4})-([a-z0-9-]+)\.md$")
H1_NUMBER = re.compile(r"^#\s+RFC\s+(\d{4})\b", re.M)
STATUS_LINE = re.compile(r"^-\s+\*\*Status:\*\*\s*(\S+)", re.M)
# Cells may contain an escaped pipe, so a cell is "anything but a delimiter,
# where a backslash escapes the next character". Reading with plain [^|]* ended
# the title cell at the escape and shifted every column after it.
CELL = r"(?:[^|\\]|\\.)*"
INDEX_ROW = re.compile(rf"^\|\s*\[(\d{{4}})\]\(([^)]+)\)\s*\|({CELL})\|({CELL})\|", re.M)
NEXT_FREE = re.compile(r"(next free number is\s+\*\*)(\d{4})(\*\*)", re.I)
TEMPLATE_BLOCK = re.compile(r"```markdown\n(.*?)\n```", re.S)
TEMPLATE_TITLE = "RFC NNNN — <Title>"


def fail(message: str) -> None:
    sys.exit(f"error: {message}")


def find_dir(root: Path) -> Path:
    for name in ("rfcs", "rfc"):
        candidate = root / name
        if candidate.is_dir():
            return candidate
    fail(f"no rfcs/ or rfc/ directory under {root}")


def find_index(rfc_dir: Path) -> Path:
    for name in ("INDEX.md", "README.md"):
        candidate = rfc_dir / name
        if candidate.is_file():
            return candidate
    fail(f"no INDEX.md or README.md in {rfc_dir}")


def escape_cell(text: str) -> str:
    """Make text safe for a GFM table cell: only the pipe needs escaping."""
    return text.replace("|", "\\|")


def numbered_files(rfc_dir: Path) -> dict[int, list[Path]]:
    """Every number on disk, with all the files claiming it."""
    found: dict[int, list[Path]] = {}
    for path in sorted(rfc_dir.glob("*.md")):
        match = RFC_FILENAME.match(path.name)
        if match:
            found.setdefault(int(match.group(1)), []).append(path)
    return found


def describe_duplicates(found: dict[int, list[Path]]) -> str:
    return "; ".join(
        f"{number:04d}: {', '.join(p.name for p in paths)}"
        for number, paths in sorted(found.items())
        if len(paths) > 1
    )


def rfc_files(rfc_dir: Path, strict: bool = True) -> dict[int, Path]:
    """Number -> file. `strict` fails on duplicates; `check` reports them instead.

    A duplicate is a validation finding, and `check` documents exit 2 for those.
    Failing hard here made it exit 1 — the code reserved for a usage or IO error
    — so a broken collection was indistinguishable from a broken invocation.
    """
    found = numbered_files(rfc_dir)
    if strict and (listed := describe_duplicates(found)):
        fail(f"duplicate RFC numbers on disk — {listed}")
    return {number: paths[0] for number, paths in found.items()}


def status_emoji(text: str) -> str | None:
    match = STATUS_LINE.search(text)
    if not match:
        return None
    token = match.group(1)
    return next((e for e in STATUS_EMOJI if token.startswith(e)), token)


def duplicate_row_numbers(index_text: str) -> list[int]:
    """Numbers appearing on more than one index row.

    index_rows() keys by number, so duplicates would silently collapse and the
    index contract of one row per RFC would go unchecked.
    """
    seen: dict[int, int] = {}
    for match in INDEX_ROW.finditer(index_text):
        number = int(match.group(1))
        seen[number] = seen.get(number, 0) + 1
    return sorted(number for number, count in seen.items() if count > 1)


def index_rows(index_text: str) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for match in INDEX_ROW.finditer(index_text):
        number = int(match.group(1))
        status = match.group(4).strip()
        rows[number] = {
            "link": match.group(2).strip(),
            "title": match.group(3).strip(),
            "status": next((e for e in STATUS_EMOJI if status.startswith(e)), status),
        }
    return rows


def claimed_next(index_text: str) -> int | None:
    match = NEXT_FREE.search(index_text)
    return int(match.group(2)) if match else None


def cmd_check(rfc_dir: Path) -> int:
    index_path = find_index(rfc_dir)
    index_text = index_path.read_text(encoding="utf-8")
    files = rfc_files(rfc_dir, strict=False)
    rows = index_rows(index_text)
    problems: list[str] = []

    for number, paths in sorted(numbered_files(rfc_dir).items()):
        if len(paths) > 1:
            problems.append(
                f"RFC {number:04d} is claimed by {len(paths)} files: "
                f"{', '.join(p.name for p in paths)}"
            )

    for number in duplicate_row_numbers(index_text):
        problems.append(f"{index_path.name}: RFC {number:04d} has more than one index row")

    for number in sorted(set(files) - set(rows)):
        problems.append(f"{files[number].name}: on disk but has no index row")
    for number in sorted(set(rows) - set(files)):
        problems.append(f"index row {number:04d} ({rows[number]['link']}): no such file")

    for number in sorted(set(files) & set(rows)):
        path = files[number]
        text = path.read_text(encoding="utf-8")
        h1 = H1_NUMBER.search(text)
        if not h1:
            problems.append(f"{path.name}: no '# RFC NNNN — Title' heading")
        elif int(h1.group(1)) != number:
            problems.append(f"{path.name}: H1 says RFC {h1.group(1)}, filename says {number:04d}")

        if rows[number]["link"] != path.name:
            problems.append(f"index row {number:04d}: links to {rows[number]['link']}, file is {path.name}")

        header_status = status_emoji(text)
        if header_status is None:
            problems.append(f"{path.name}: no '- **Status:**' line")
        elif header_status != rows[number]["status"]:
            problems.append(
                f"{number:04d}: header status {header_status} != index status {rows[number]['status']}"
            )

    claimed = claimed_next(index_text)
    highest = max(files) if files else 0
    if claimed is None:
        problems.append(f"{index_path.name}: no 'next free number is **NNNN**' statement")
    elif claimed in files:
        problems.append(f"{index_path.name}: claims {claimed:04d} is free, but that file exists")
    elif claimed <= highest:
        problems.append(
            f"{index_path.name}: claims next free is {claimed:04d}, but {highest:04d} is already taken"
        )

    for problem in problems:
        print(f"PROBLEM {problem}")
    verdict = "FAIL " if problems else "OK   "
    print(f"{verdict} {len(files)} RFC(s), {len(rows)} index row(s), {len(problems)} problem(s)")
    return 2 if problems else 0


def next_number(rfc_dir: Path) -> int:
    files = rfc_files(rfc_dir)
    on_disk = max(files) + 1 if files else 1
    index_path = next((rfc_dir / n for n in ("INDEX.md", "README.md") if (rfc_dir / n).is_file()), None)
    if index_path:
        claimed = claimed_next(index_path.read_text(encoding="utf-8"))
        if claimed is not None:
            # Whichever is higher: the index can be stale, and so can a gap on disk.
            return max(on_disk, claimed)
    return on_disk


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        fail("title produces an empty slug")
    return slug


def template_body(script_dir: Path) -> str:
    template = script_dir.parent / "references" / "rfc-template.md"
    if not template.is_file():
        fail(f"template not found at {template}")
    match = TEMPLATE_BLOCK.search(template.read_text(encoding="utf-8"))
    if not match:
        fail(f"no ```markdown skeleton block in {template}")
    return match.group(1)


def index_insert_position(lines: list[str], index_path: Path) -> int:
    """Where a new row goes: after the last row, or after the table separator."""
    last_row = max((i for i, line in enumerate(lines) if INDEX_ROW.match(line)), default=None)
    if last_row is not None:
        return last_row + 1
    header = next(
        (i for i, line in enumerate(lines) if set(line.strip()) <= set("|-: ") and "|" in line),
        None,
    )
    if header is None:
        fail(f"{index_path.name}: no index table to append to — add the table header first")
    return header + 1


@contextlib.contextmanager
def locked_index(index_path: Path):
    """Hold the index exclusively across the whole read-modify-write.

    Allocation and rewrite have to be one critical section. Two runs that pick
    different numbers still both rewrite the index, and without the lock the
    second write drops the first's row — losing the very record numbering is
    derived from. Reads elsewhere take no lock, so they cannot deadlock here.
    """
    with index_path.open("r+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def cmd_new(rfc_dir: Path, title: str, script_dir: Path, number: int | None = None) -> int:
    requested = number
    index_path = find_index(rfc_dir)
    with locked_index(index_path) as handle:
        # Allocate inside the lock: another run may have taken this number
        # between our reading the directory and our writing the row.
        number = next_number(rfc_dir) if requested is None else requested
        if not 1 <= number <= 9999:
            fail(f"--number must be between 1 and 9999 (got {number}) — RFC ids are four digits")
        existing = rfc_files(rfc_dir)
        if number in existing:
            # The identifier is the number, not the filename: a different slug at
            # the same number still produces two RFCs sharing one id.
            fail(f"RFC {number:04d} already exists as {existing[number].name}")
        path = rfc_dir / f"{number:04d}-{slugify(title)}.md"
        if path.exists():
            fail(f"{path.name} already exists")

        # Resolve everything that can fail *before* writing, so a missing index
        # or table cannot leave an orphan RFC file to clean up by hand.
        index_text = handle.read()
        insert_at = index_insert_position(index_text.splitlines(), index_path)

        template = template_body(script_dir)
        # An unchecked replace is silent when the template's placeholder is
        # edited: the RFC would ship with a literal "RFC NNNN — <Title>" H1,
        # and `check` would then report the file it just wrote as broken.
        if TEMPLATE_TITLE not in template:
            fail(
                f"references/rfc-template.md no longer contains the '{TEMPLATE_TITLE}' "
                "placeholder — restore it, or the H1 cannot be filled in"
            )
        body = template.replace(TEMPLATE_TITLE, f"RFC {number:04d} — {title}")
        try:
            # Exclusive create: two runs racing for the same number cannot both
            # win, which the existence check alone cannot guarantee.
            with path.open("x", encoding="utf-8") as rfc_handle:
                rfc_handle.write(body + "\n")
        except FileExistsError:
            fail(f"{path.name} was created by another process — re-run to take the next number")
        # A pipe in the title would open a new cell and shift every column after
        # it, so the row the checker reads back is not the row that was written.
        row = (
            f"| [{number:04d}]({path.name}) | {escape_cell(title)} | 📝 Draft "
            "| TODO: one-line summary |"
        )

        lines = index_text.splitlines()
        lines.insert(insert_at, row)

        # Only ever raise the claim: `new --number 3` on a collection already at
        # 0008 must not rewind the index to 0004.
        claimed = claimed_next(index_text) or 0
        next_free = max(number + 1, claimed)
        updated, bumped = NEXT_FREE.subn(
            lambda m: f"{m.group(1)}{next_free:04d}{m.group(3)}", "\n".join(lines)
        )
        # A no-op substitution used to pass silently, so `new` reported success
        # on an index carrying no claim at all — and the next run then allocated
        # from the files alone, which is what the claim exists to backstop.
        if not bumped:
            path.unlink(missing_ok=True)
            fail(
                f"{index_path.name} has no 'next free number is **NNNN**' line to update — "
                f"add one (see references/index-template.md); removed {path.name}"
            )
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(updated + "\n")
        except OSError as exc:
            # Pre-resolving lookups cannot cover a failing write (read-only
            # mount, full disk). An RFC with no index row is an orphan nothing
            # will point at, so undo the file we just created.
            path.unlink(missing_ok=True)
            fail(
                f"could not update {index_path.name}: {exc} — removed {path.name} "
                "so the collection stays consistent"
            )

    print(f"created {path}")
    print(f"updated {index_path} (row added, next free number -> {next_free:04d})")
    print("next: fill the Scope paragraph and the one-line index summary")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo root (default: cwd)")
    # Also accepted after the subcommand, which is where anyone would type it.
    # SUPPRESS matters: a real default here would overwrite the top-level value
    # whenever the flag was given before the subcommand instead.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS, help="repo root")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", parents=[common])
    sub.add_parser("next", parents=[common])
    new = sub.add_parser("new", parents=[common])
    new.add_argument("title")
    new.add_argument(
        "--number", type=int,
        help="use this number instead of the next free one (a reserved number, or "
             "re-creating a deleted RFC); refuses to overwrite an existing file",
    )

    args = parser.parse_args()
    rfc_dir = find_dir(args.root)

    if args.cmd == "check":
        return cmd_check(rfc_dir)
    if args.cmd == "next":
        print(f"{next_number(rfc_dir):04d}")
        return 0
    return cmd_new(rfc_dir, args.title, Path(__file__).resolve().parent, args.number)


if __name__ == "__main__":
    sys.exit(main())
