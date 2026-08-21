#!/usr/bin/env python3
"""Structural validator for the skills collection.

Deterministic, stdlib-only checks — no LLM involved. Exit 0 = all green.

Errors (fail the run):
  E1  skills/<name>/ has no SKILL.md
  E2  frontmatter malformed (missing/unterminated, or missing name/description)
  E3  frontmatter name does not match the folder name
  E4  name is not kebab-case
  E5  description is empty, multi-line, or over 300 characters
  E6  body has no H1 title
  E7  frontmatter has no roles, or names a role outside the vocabulary
  E8  a "## Related skills" entry names a skill that does not exist
  E9  a relative link in a skill's .md files resolves to nothing inside the repo
  E10 a file in references/ is never mentioned in its SKILL.md
  E11 README.md "Available Skills" is out of sync with skills/ (either direction)
  E12 a bundled script does not compile (python) or parse (shell, javascript)
  E13 a skill ships scripts/ that its SKILL.md never mentions
  E14 gate is missing, or names no script, or is none without a gate_reason
  E15 body still carries a trigger section, at any heading level
  E16 a frontmatter value is unquoted where YAML would not read it as text

Warnings (reported, do not fail):
  W1  body is over the token budget
  W2  SKILL.md exceeds 500 lines
  W3  a bundled JavaScript file could not be checked (node not installed)

The description budget is the reason E5 is 300 and not the format's own 1024.
Every description sits in the agent's context in every session whether its
skill fires or not, so the collection pays for all of them all the time; a body
is paid only on trigger. Triggers are all a description is for — E15 exists
because the same triggers restated as a body section get paid twice.
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
TRIGGER_SECTION = re.compile(r"^(do not )?use (this skill )?when\b", re.I)
MAX_DESCRIPTION = 300
MAX_BODY_TOKENS = 1500
# Rough, and deliberately so: the budget is an order-of-magnitude guard, and a
# real tokenizer would make the check depend on a package this repo does not have.
CHARS_PER_TOKEN = 4
ROLES = {"implement", "review", "revert", "author"}
REF_MENTION = re.compile(r"references/([A-Za-z0-9._-]+\.md)")
FENCED = re.compile(r"^```.*?^```", re.M | re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
# A markdown link that points at something in the repository. Anchors and shell
# variables are not ours to resolve, and neither is any URI scheme or a
# protocol-relative `//host/x` — matching only http and mailto meant `ftp:` and
# `tel:` were checked as if they were file paths.
URI_OR_PROTOCOL_RELATIVE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|//)")
RELATIVE_LINK = re.compile(r"\[[^\]]*\]\((?!#|\$)([^)\s]+)\)")
BACKTICK = re.compile(r"`([a-z0-9-]+)`")

errors: list[str] = []
warnings: list[str] = []


def err(code: str, msg: str) -> None:
    errors.append(f"{code}: {msg}")


def warn(code: str, msg: str) -> None:
    warnings.append(f"{code}: {msg}")


# An unquoted frontmatter value is a YAML *plain scalar*, and a plain scalar
# ends at the first structural character rather than at the end of the line.
# This parser used to read the rest of the line verbatim, which made it more
# permissive than every real YAML parser: two descriptions carrying a literal
# `Attributes: ` and `:raises: ` passed here and could not be loaded at all by
# the installer. A validator looser than the consumer reports green about a
# file nobody downstream can read.
PLAIN_HAZARDS = (
    (re.compile(r":(?=\s|$)"), "a colon before whitespace or end-of-line opens a nested mapping"),
    (re.compile(r"(?:^|\s)#"), "a '#' after whitespace starts a comment and truncates the value"),
    (re.compile(r"^[#&*!|>%@`]"), "the first character is a YAML indicator"),
    (re.compile(r"^[-?](?=\s|$)"), "a leading '-' or '?' starts a block sequence or a complex key"),
)

# A bare token YAML resolves to a bool, a null or a number is not text, and the
# two parsers do not even agree on which tokens those are: `no` is a string
# under YAML 1.2 (the installer) and False under YAML 1.1 (PyYAML). Refusing
# the union means a value is text under both or refused under both.
YAML_NOT_TEXT = re.compile(
    r"""^(?:
        true | false | yes | no | on | off | y | n |    # bool, 1.2 and 1.1
        null | ~ |                                      # null
        [-+]? (?: [0-9][0-9_]* (?:\.[0-9_]*)? | \.[0-9][0-9_]* ) (?:[eE][-+]?[0-9]+)? |
        [-+]? 0[xX][0-9a-fA-F_]+ | [-+]? 0[oO][0-7_]+ | [-+]? 0b[01_]+ |
        [-+]? \.(?: inf | nan )
    )$""",
    re.VERBOSE | re.IGNORECASE,
)


# `roles` is the only field whose value is a collection. Every other field is
# text, so a flow collection there is a value this validator measures as a
# string and the installer loads as a list or a mapping.
COLLECTION_FIELDS = frozenset({"roles"})

# ...and the exemption has to be narrow, because `check_roles` reaches its list
# through `strip("[]")`. That reads a quoted `'[implement]'` (a string to YAML),
# a bare `implement` (a string to YAML) and an unclosed `[implement` (a parse
# error to YAML) as the same one-item list. The shape is settled here instead,
# before anything splits on commas.
FLOW_SEQUENCE = re.compile(r"^\[[^\[\]{}]*\]$")


def scalar_value(raw: str, where: str, key: str) -> str:
    """The text a YAML parser would read out of one frontmatter value.

    Quoted values are unquoted so the length and content checks measure the
    description rather than its punctuation. `roles: [a, b]` is handed on
    untouched for its own check to read. Anything left is plain, and is
    refused if YAML would read it as something other than that text.
    """
    if key in COLLECTION_FIELDS:
        if not FLOW_SEQUENCE.match(raw):
            err("E16", f"{where}: {key} must be a flow sequence like [implement, review] — "
                       "a quoted or bare value is a string to YAML, not a list")
        return raw
    if raw[:1] in ("[", "{"):
        err("E16", f"{where}: {key} is a YAML collection where text is required")
        return raw
    for quote in ("'", '"'):
        if not raw.startswith(quote):
            continue
        if len(raw) < 2 or not raw.endswith(quote):
            err("E16", f"{where}: {key} opens with {quote} and never closes")
            return raw
        inner = raw[1:-1]
        if quote == "'" and any(len(run) % 2 for run in re.findall(r"'+", inner)):
            err("E16", f"{where}: {key} is single-quoted with an apostrophe that is not "
                       "doubled — YAML ends the scalar there and rejects the rest")
            return inner.replace("''", "'")
        if quote == '"' and "\\" in inner:
            err("E16", f"{where}: {key} is double-quoted with a backslash escape — "
                       "single-quote it rather than have this parser approximate one")
            return inner
        return inner.replace("''", "'") if quote == "'" else inner
    for pattern, why in PLAIN_HAZARDS:
        if pattern.search(raw):
            err("E16", f"{where}: {key} is unquoted and {why} — quote the value")
            break
    else:
        if YAML_NOT_TEXT.match(raw):
            err("E16", f"{where}: {key} is the bare token {raw!r}, which YAML types as a "
                       "bool, a null or a number rather than text — quote it")
    return raw


def parse_frontmatter(text: str, where: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        err("E2", f"{where}: no frontmatter opener")
        return None
    raw: dict[str, str] = {}
    blocks: set[str] = set()
    for line in lines[1:]:
        if line.strip() == "---":
            for key in sorted(blocks):
                err("E16", f"{where}: {key} has nothing after the colon and an indented "
                           "block under it — YAML reads a list or a mapping, not text")
            # Scalars are read after the whole block, so a value continued onto
            # a second line is judged whole: judging the first line alone would
            # call a legal wrapped quote unterminated.
            return {k: scalar_value(v, where, k) for k, v in raw.items()}
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            raw[m.group(1)] = m.group(2).strip()
        elif line.startswith((" ", "\t")) and raw:
            last = list(raw)[-1]
            # An indented line continues a value only if there was a value. Under
            # a bare `key:` it opens a nested collection, and joining it with a
            # newline fabricates a scalar no parser will produce.
            if not raw[last]:
                blocks.add(last)
            raw[last] += "\n" + line.strip()
    err("E2", f"{where}: frontmatter never closed")
    return None


def section_names(body: str, levels: str = "2") -> set[str]:
    """Headings at the given level, or `"2-6"` for every level below the title.

    E15 needs the wide reading: `### Use this skill when` restates the trigger
    just as expensively as `##` does, and matching only `##` let it through.
    """
    pattern = r"^##\s+(.+)$" if levels == "2" else r"^#{2,6}\s+(.+)$"
    return {m.group(1).strip() for m in re.finditer(pattern, body, re.M)}


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


def broken_links(page: Path, repo: Path) -> list[str]:
    """Relative link targets in one markdown file that resolve to nothing.

    Fenced blocks and inline code are stripped first: both carry link-shaped
    text that is not a link — a template's `[0001](0001-kebab-title.md)` row, or
    a dispatch table written `handlers[kind](payload)`.
    """
    try:
        text = page.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    prose = INLINE_CODE.sub("", FENCED.sub("", text))
    base = repo.resolve()
    missing = []
    for match in RELATIVE_LINK.finditer(prose):
        target = match.group(1).split("#", 1)[0]
        if not target or URI_OR_PROTOCOL_RELATIVE.match(target):
            continue
        for start in (page.parent, repo):
            try:
                resolved = (start / target).resolve()
            except OSError:
                continue
            if resolved.is_relative_to(base) and resolved.exists():
                break
        else:
            missing.append(target)
    return missing


def check_roles(fm: dict[str, str], where: str) -> None:
    raw = fm.get("roles", "").strip()
    if not raw:
        err("E7", f"{where}: frontmatter has no roles")
        return
    named = [r.strip() for r in raw.strip("[]").split(",") if r.strip()]
    if not named:
        err("E7", f"{where}: roles is empty")
    for role in named:
        if role not in ROLES:
            err("E7", f"{where}: role {role!r} is not one of {sorted(ROLES)}")


def check_gate(fm: dict[str, str], where: str, all_scripts: set[str]) -> None:
    gate = fm.get("gate", "").strip()
    if not gate:
        err("E14", f"{where}: frontmatter has no gate (name the enforcing check, or 'none')")
        return
    if gate == "none":
        # A skill with no gate is a hope, and the justification is what makes
        # that an admission rather than an oversight.
        if not fm.get("gate_reason", "").strip():
            err("E14", f"{where}: gate is none, which needs a gate_reason saying why")
        return
    if fm.get("gate_reason", "").strip():
        err("E14", f"{where}: gate {gate!r} is named, so gate_reason does not apply")
    if gate not in all_scripts:
        err("E14", f"{where}: gate {gate!r} names no script in the collection")


def bundled_gates() -> set[str]:
    """Gate names a skill may claim: the kebab-cased stem of any bundled script."""
    names = set()
    for script in SKILLS_DIR.glob("*/scripts/*"):
        if script.is_file() and not script.name.startswith("."):
            names.add(script.stem.replace("_", "-"))
    for script in (REPO / "scripts").glob("*"):
        if script.is_file() and not script.name.startswith("."):
            names.add(script.stem.replace("_", "-"))
    return names


def check_skill(skill_dir: Path, all_names: set[str], all_scripts: set[str]) -> None:
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
        elif len(desc) > MAX_DESCRIPTION:
            err("E5", f"{where}: description is {len(desc)} chars (max {MAX_DESCRIPTION})")
        check_roles(fm, where)
        check_gate(fm, where, all_scripts)

    body = re.sub(r"\A---.*?^---\s*$", "", text, count=1, flags=re.M | re.S)
    if not re.search(r"^# .+$", body, re.M):
        err("E6", f"{where}: no H1 title")
    for heading in sorted(section_names(body, levels="2-6")):
        if TRIGGER_SECTION.match(heading):
            err("E15", f"{where}: body still carries '## {heading}' — triggers belong in the description")
    budget = len(body) // CHARS_PER_TOKEN
    if budget > MAX_BODY_TOKENS:
        warn("W1", f"{where}: body is ~{budget} tokens (budget {MAX_BODY_TOKENS}) — move detail to references/")
    if len(text.splitlines()) > 500:
        warn("W2", f"{where}: over 500 lines")

    for ref in related_entries(body):
        if ref not in all_names:
            err("E8", f"{where}: Related skills names nonexistent skill `{ref}`")

    for fname in set(REF_MENTION.findall(text)):
        if not (skill_dir / "references" / fname).is_file():
            err("E9", f"{where}: mentions references/{fname}, which does not exist")

    # Every .md in the skill, not only SKILL.md: a section moved into
    # references/ carries its links with it, and a `references/x.md` link that
    # was correct in SKILL.md resolves to references/references/x.md there.
    for page in sorted(skill_dir.rglob("*.md")):
        for target in broken_links(page, REPO):
            rel = page.relative_to(REPO)
            err("E9", f"{rel}: link target {target!r} does not exist")

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
    all_scripts = bundled_gates()
    for skill_dir in skill_dirs:
        check_skill(skill_dir, all_names, all_scripts)
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
