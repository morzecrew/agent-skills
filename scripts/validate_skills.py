#!/usr/bin/env python3
"""Structural validator for the skills collection.

Deterministic, stdlib-only checks — no LLM involved. Exit 0 = all green.

Errors (fail the run):
  E1  skills/<name>/ has no SKILL.md
  E2  frontmatter malformed (missing/unterminated, or missing name/description)
  E3  frontmatter name does not match the folder name
  E4  name is not kebab-case
  E5  description is empty, multi-line, or over 1024 characters
  E6  body has no H1 title
  E7  body has no "## Use this skill when" section
  E8  a "## Related skills" entry names a skill that does not exist
  E9  a relative link to references/ points at a missing file
  E10 a file in references/ is never mentioned in its SKILL.md
  E11 README.md "Available Skills" is out of sync with skills/ (either direction)
  E12 a bundled script does not compile (python) or parse (shell, javascript)
  E13 a skill ships scripts/ that its SKILL.md never mentions

Warnings (reported, do not fail):
  W1  body has no "## Do not use this skill when" section
  W2  SKILL.md exceeds 500 lines
  W3  a bundled JavaScript file could not be checked (node not installed)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"
README = REPO / "README.md"

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REF_MENTION = re.compile(r"references/([A-Za-z0-9._-]+\.md)")
BACKTICK = re.compile(r"`([a-z0-9-]+)`")

errors: list[str] = []
warnings: list[str] = []


def err(code: str, msg: str) -> None:
    errors.append(f"{code}: {msg}")


def warn(code: str, msg: str) -> None:
    warnings.append(f"{code}: {msg}")


def parse_frontmatter(text: str, where: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        err("E2", f"{where}: no frontmatter opener")
        return None
    fields: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
        elif line.startswith((" ", "\t")) and fields:
            # continuation line -> the previous value was not single-line
            fields[list(fields)[-1]] += "\n" + line.strip()
    err("E2", f"{where}: frontmatter never closed")
    return None


def section_names(body: str) -> set[str]:
    return {m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", body, re.M)}


def related_entries(body: str) -> list[str]:
    m = re.search(r"^## Related skills\s*$(.*?)(?=^## |\Z)", body, re.M | re.S)
    if not m:
        return []
    names = []
    for line in m.group(1).splitlines():
        if line.lstrip().startswith("- "):
            tick = BACKTICK.search(line)
            if tick:
                names.append(tick.group(1))
    return names


def check_skill(skill_dir: Path, all_names: set[str]) -> None:
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        err("E1", f"skills/{name}: missing SKILL.md")
        return
    text = skill_md.read_text(encoding="utf-8")
    where = f"skills/{name}/SKILL.md"

    fm = parse_frontmatter(text, where)
    if fm is not None:
        if "name" not in fm or "description" not in fm:
            err("E2", f"{where}: frontmatter must carry name and description")
        if fm.get("name") and fm["name"] != name:
            err("E3", f"{where}: frontmatter name {fm['name']!r} != folder {name!r}")
        if not KEBAB.match(name):
            err("E4", f"skills/{name}: folder name is not kebab-case")
        desc = fm.get("description", "")
        if not desc:
            err("E5", f"{where}: empty description")
        elif "\n" in desc:
            err("E5", f"{where}: description must be a single line")
        elif len(desc) > 1024:
            err("E5", f"{where}: description is {len(desc)} chars (max 1024)")

    body = re.sub(r"\A---.*?^---\s*$", "", text, count=1, flags=re.M | re.S)
    if not re.search(r"^# .+$", body, re.M):
        err("E6", f"{where}: no H1 title")
    sections = section_names(body)
    if "Use this skill when" not in sections:
        err("E7", f"{where}: missing '## Use this skill when'")
    if "Do not use this skill when" not in sections:
        warn("W1", f"{where}: no '## Do not use this skill when'")
    if len(text.splitlines()) > 500:
        warn("W2", f"{where}: over 500 lines")

    for ref in related_entries(body):
        if ref not in all_names:
            err("E8", f"{where}: Related skills names nonexistent skill `{ref}`")

    for fname in set(REF_MENTION.findall(text)):
        if not (skill_dir / "references" / fname).is_file():
            err("E9", f"{where}: mentions references/{fname}, which does not exist")

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_file in sorted(refs_dir.glob("*.md")):
            if ref_file.name not in text:
                err("E10", f"skills/{name}: references/{ref_file.name} never mentioned in SKILL.md")

    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script in sorted(scripts_dir.iterdir()):
            if script.name.startswith(".") or script.is_dir():
                continue
            if script.suffix == ".py":
                try:
                    # Raw bytes: compile() honors a PEP 263 coding cookie, while a
                    # forced UTF-8 decode would reject a valid non-UTF-8 script.
                    compile(script.read_bytes(), str(script), "exec")
                except (SyntaxError, ValueError) as exc:
                    # ValueError covers source containing NUL, which is a
                    # malformed script — an ordinary finding, not a traceback.
                    err("E12", f"skills/{name}/scripts/{script.name} does not compile: {exc}")
            elif script.suffix in {".js", ".mjs", ".cjs"}:
                try:
                    proc = subprocess.run(
                        ["node", "--check", str(script)], capture_output=True, text=True
                    )
                except FileNotFoundError:
                    # No node here: say so rather than passing silently, since a
                    # stderr substring test would also swallow real parse errors.
                    warn("W3", f"skills/{name}/scripts/{script.name}: node not installed, not checked")
                else:
                    if proc.returncode != 0:
                        err("E12", f"skills/{name}/scripts/{script.name} does not parse: {proc.stderr.strip()[:160]}")
            elif script.suffix in {".sh", ".bash"}:
                proc = subprocess.run(
                    ["bash", "-n", str(script)], capture_output=True, text=True
                )
                if proc.returncode != 0:
                    err("E12", f"skills/{name}/scripts/{script.name} has a syntax error: {proc.stderr.strip()[:160]}")
            if script.name not in text:
                err("E13", f"skills/{name}: scripts/{script.name} never mentioned in SKILL.md")


def check_readme(all_names: set[str]) -> None:
    text = README.read_text(encoding="utf-8")
    m = re.search(r"^## Available Skills\s*$(.*)\Z", text, re.M | re.S)
    if not m:
        err("E11", "README.md: no '## Available Skills' section")
        return
    listed = set(re.findall(r"\]\(skills/([^/)]+)/\)", m.group(1)))
    for name in sorted(all_names - listed):
        err("E11", f"README.md: skill {name!r} has no Available Skills entry")
    for name in sorted(listed - all_names):
        err("E11", f"README.md: entry {name!r} has no skills/{name} directory")


def main() -> int:
    skill_dirs = sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir())
    all_names = {d.name for d in skill_dirs}
    for skill_dir in skill_dirs:
        check_skill(skill_dir, all_names)
    check_readme(all_names)

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    total = f"{len(skill_dirs)} skills checked: {len(errors)} errors, {len(warnings)} warnings"
    print(("FAIL  " if errors else "OK    ") + total)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
