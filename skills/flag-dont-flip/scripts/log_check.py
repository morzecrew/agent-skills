#!/usr/bin/env python3
"""Checks an execution log against the rules flag-dont-flip states (stdlib only).

The skill is a convention, and a convention with no gate decays into an
optional one (`ratchet-what-you-build`). Every check below enforces a sentence
that already appears in SKILL.md; none of them invents a rule.

  schema      every D-entry carries the fields a reader checks first
  legality    the recorded action is one the grade permits — the rule this
              skill is named for, and the only one a tool can settle
  evidence    a `path:line` reference lands in a real file; a command brings
              back enough output to be worth running again
  numbering   D-NNN identifiers are unique and continuous across the file,
              because RFC decision rows cite them
  drift       every unit declares a drift count, including zero, and the
              number it declares matches the entries classed `drift`
  proposals   a proposed row that no outcomes table answers is reported
              (a warning: a proposal made today may simply not be answered
              yet, while a log where none is ever answered is the failure
              mode SKILL.md names last)

Deliberately NOT checked: whether an entry's grade matches the RFC's decision
table today. The log records the grade that was in force when the executor
acted, and grades change; comparing them would flag an honest historical
record as wrong. With --rfc-dir the citation is checked for existence only.

  log_check.py rfcs/EXECUTION-LOG.md --rfc-dir rfcs/
  log_check.py rfcs/EXECUTION-LOG.md --strict     # warnings fail too

Exit 0 clean, 1 problems found, 2 the log could not be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GRADES = {"LOCKED", "ASSUMED", "OPEN"}
CLASSES = {"discovery", "spec-gap", "drift", "irreducible"}
ACTIONS = {"halted", "departed", "decided"}

# The grade-to-action pairing from SKILL.md, in the one shape a tool can decide.
LEGAL = {"LOCKED": {"halted"}, "ASSUMED": {"departed"}, "OPEN": {"decided"}}
WHY_ILLEGAL = {
    "LOCKED": "carrying on past a lock that reality contradicted is the move this gate exists to stop",
    "ASSUMED": "over-caution: you were licensed to depart from this one",
    "OPEN": "over-caution: the RFC delegated this decision to execution",
}

REQUIRED = ("touches", "rfc said", "because", "class", "consequence", "action", "evidence")
# Printed back the way the template writes them; `str.title()` renders "RFC
# said" as "Rfc Said", and a checker that misspells the field it is asking for
# makes the reader hunt for a field that does not exist.
LABEL = {"touches": "Touches", "rfc said": "RFC said", "because": "Because",
         "class": "Class", "consequence": "Consequence", "action": "Action",
         "evidence": "Evidence"}
# `Built:` becomes `Found:` where nothing was built — the template says so, and
# a departure that only discovered something would otherwise carry a small lie
# in the field a reader checks first.
BUILT_OR_FOUND = ("built", "found")

ENTRY = re.compile(r"^##\s+D-(\d+)\s*[—–-]\s*(.*)$")
BULLET = re.compile(r"^[-*]\s+\*\*([^*]+?):\*\*\s*(.*)$")
DRIFT = re.compile(r"\*\*Drift count:\s*(\d+)")
GRADE_IN = re.compile(r"`(LOCKED|ASSUMED|OPEN)`")
PATH_REF = re.compile(r"^([^\s:`]+):(\d+)(?:-(\d+))?")
CITES_RFC = re.compile(r"RFC\s+(\d{1,4})\b")
CITES_ROW = re.compile(r"row\s+(\d+)", re.I)
RFC_ROW = re.compile(r"^\|\s*(\d+)\s*\|")
MENTIONS_D = re.compile(r"\bD-(\d+)\b")


class Problem:
    def __init__(self, where: str, message: str, warning: bool = False):
        self.where, self.message, self.warning = where, message, warning

    def __str__(self) -> str:
        mark = "warn" if self.warning else "err "
        return f"  {mark}  {self.where}: {self.message}"


def normalize(field: str) -> str:
    """`Proposed row (RFC 0014)` and `Proposed row` are the same field."""
    return field.split("(")[0].strip().lower()


def parse(text: str) -> tuple[list[dict], list[dict], set[int], list[Problem]]:
    """Units, entries, the D-numbers some outcomes table answers, and problems."""
    units: list[dict] = []
    entries: list[dict] = []
    answered: set[int] = set()
    problems: list[Problem] = []
    unit: dict | None = None
    entry: dict | None = None
    field: str | None = None
    in_outcomes = False
    seen_title = False

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()

        if line.startswith("# "):
            # The document has one title and then a sequence of units.
            entry, field, in_outcomes = None, None, False
            if not seen_title:
                seen_title = True
                continue
            unit = {"title": line[2:].strip(), "line": number, "drift": None,
                    "entries": []}
            units.append(unit)
            continue

        if line.startswith("## "):
            entry, field = None, None
            in_outcomes = line[3:].strip().lower().startswith("decision-row outcomes")
            match = ENTRY.match(line)
            if match:
                entry = {"n": int(match.group(1)), "title": match.group(2).strip(),
                         "line": number, "fields": {}, "unit": unit}
                entries.append(entry)
                if unit is None:
                    problems.append(Problem(
                        f"D-{match.group(1)}",
                        "appears before any unit heading — an entry belongs to the unit "
                        "whose drift count counts it",
                    ))
                else:
                    unit["entries"].append(entry)
            continue

        if in_outcomes:
            answered.update(int(d) for d in MENTIONS_D.findall(line))
            continue

        drift = DRIFT.search(line)
        if drift and unit is not None and unit["drift"] is None:
            unit["drift"] = int(drift.group(1))
            continue

        if entry is not None:
            bullet = BULLET.match(line)
            if bullet:
                field = normalize(bullet.group(1))
                entry["fields"][field] = bullet.group(2).strip()
            elif field and line.strip() and line.startswith((" ", "\t")):
                # A wrapped field value; the template wraps at the margin.
                entry["fields"][field] += " " + line.strip()
            elif not line.strip():
                field = None

    return units, entries, answered, problems


def check_entry(entry: dict, root: Path) -> list[Problem]:
    where = f"D-{entry['n']:03d}"
    fields = entry["fields"]
    problems = []

    for name in REQUIRED:
        if not fields.get(name):
            problems.append(Problem(where, f"missing required field `{LABEL[name]}`"))
    if not any(fields.get(name) for name in BUILT_OR_FOUND):
        problems.append(Problem(where, "missing required field `Built` (or `Found`)"))

    klass = (fields.get("class") or "").strip("`. ").split("`")[0].strip("`. ")
    if fields.get("class") and klass not in CLASSES:
        problems.append(Problem(where, f"class `{klass}` not in {sorted(CLASSES)}"))

    action = (fields.get("action") or "").strip("`. ").lower()
    if fields.get("action") and action not in ACTIONS:
        problems.append(Problem(where, f"action `{action}` not in {sorted(ACTIONS)}"))

    grade_match = GRADE_IN.search(fields.get("touches", ""))
    if grade_match and action in ACTIONS:
        grade = grade_match.group(1)
        if action not in LEGAL[grade]:
            legal = " or ".join(sorted(LEGAL[grade]))
            problems.append(Problem(
                where,
                f"{grade} decision recorded action `{action}`, only `{legal}` is legal "
                f"— {WHY_ILLEGAL[grade]}",
            ))

    problems += check_evidence(entry, root)
    return problems


def check_evidence(entry: dict, root: Path) -> list[Problem]:
    where = f"D-{entry['n']:03d}"
    evidence = (entry["fields"].get("evidence") or "").strip().strip("`")
    if not evidence:
        return []
    ref = PATH_REF.match(evidence)
    if not ref:
        # A command and its output. There is nothing to resolve, so ask instead
        # for enough of it to run again — a sentence about why something is hard
        # belongs in `Because`, which is the field for sentences.
        if len(evidence) < 20:
            return [Problem(where, "evidence carries nothing anyone could re-run")]
        return []

    path = root / ref.group(1)
    if not path.exists():
        return [Problem(where, f"evidence path `{ref.group(1)}` is not in the tree")]
    start, end = int(ref.group(2)), int(ref.group(3) or ref.group(2))
    try:
        lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError as broken:
        return [Problem(where, f"evidence path `{ref.group(1)}` would not open: {broken}")]
    if start < 1 or end > max(lines, 1):
        return [Problem(where, f"evidence points at lines {start}-{end}, past the end of "
                       f"a {lines}-line file")]
    return []


def check_numbering(entries: list[dict]) -> list[Problem]:
    problems = []
    seen: dict[int, int] = {}
    for entry in entries:
        if entry["n"] in seen:
            problems.append(Problem(
                f"D-{entry['n']:03d}",
                f"reused (already at line {seen[entry['n']]}) — RFC rows cite these "
                "identifiers, and a number meaning two things breaks every citation",
            ))
        seen[entry["n"]] = entry["line"]
    numbers = sorted(seen)
    if numbers:
        missing = [n for n in range(numbers[0], numbers[-1] + 1) if n not in seen]
        if missing:
            shown = ", ".join(f"D-{n:03d}" for n in missing[:5])
            problems.append(Problem(
                "numbering",
                f"gap in the sequence: {shown}{'…' if len(missing) > 5 else ''} — "
                "numbers run continuously across the file and are never reset",
            ))
    return problems


def check_units(units: list[dict]) -> list[Problem]:
    problems = []
    for unit in units:
        where = f"unit {unit['title']!r}"
        if unit["drift"] is None:
            problems.append(Problem(
                where,
                "no drift count — it is written even at zero, because a missing count "
                "and an honest zero are indistinguishable to a reader",
            ))
            continue
        drifted = [e for e in unit["entries"]
                   if (e["fields"].get("class") or "").strip("`. ") == "drift"]
        if unit["drift"] != len(drifted):
            named = ", ".join(f"D-{e['n']:03d}" for e in drifted) or "none"
            problems.append(Problem(
                where,
                f"declares drift count {unit['drift']} but carries {len(drifted)} "
                f"entry(ies) classed `drift` ({named})",
            ))
    return problems


def check_proposals(entries: list[dict], answered: set[int]) -> list[Problem]:
    return [
        Problem(
            f"D-{entry['n']:03d}",
            "proposed a decision row that no outcomes table answers — accepted and "
            "refused are both outcomes; neither is silence",
            warning=True,
        )
        for entry in entries
        if entry["fields"].get("proposed row") and entry["n"] not in answered
    ]


def check_citations(entries: list[dict], rfc_dir: Path) -> list[Problem]:
    """Cited RFCs and rows exist. Grades are NOT compared — see the module docstring."""
    problems = []
    for entry in entries:
        touches = entry["fields"].get("touches", "")
        where = f"D-{entry['n']:03d}"
        rfc = CITES_RFC.search(touches)
        if not rfc:
            continue
        number = rfc.group(1).zfill(4)
        matches = sorted(rfc_dir.glob(f"{number}-*.md"))
        if not matches:
            problems.append(Problem(where, f"cites RFC {number}, which is not in {rfc_dir}"))
            continue
        row = CITES_ROW.search(touches)
        if not row:
            continue
        rows = {RFC_ROW.match(line).group(1)
                for line in matches[0].read_text(encoding="utf-8").splitlines()
                if RFC_ROW.match(line)}
        if row.group(1) not in rows:
            problems.append(Problem(
                where, f"cites RFC {number} row {row.group(1)}, which its decision table "
                       f"does not have (rows: {', '.join(sorted(rows, key=int)) or 'none'})"))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path, help="the execution log, e.g. rfcs/EXECUTION-LOG.md")
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="resolve evidence paths against this directory")
    parser.add_argument("--rfc-dir", type=Path,
                        help="also check that cited RFCs and rows exist")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args()

    try:
        text = args.log.read_text(encoding="utf-8")
    except OSError as unreadable:
        print(f"error: cannot read {args.log}: {unreadable}", file=sys.stderr)
        return 2

    units, entries, answered, problems = parse(text)
    for entry in entries:
        problems += check_entry(entry, args.root)
    problems += check_numbering(entries)
    problems += check_units(units)
    problems += check_proposals(entries, answered)
    if args.rfc_dir:
        problems += check_citations(entries, args.rfc_dir)

    errors = [p for p in problems if not p.warning]
    warnings = [p for p in problems if p.warning]
    # One verdict, read twice: the summary line is for a person and the exit
    # code is for CI, and a second copy of this condition is a way for the two
    # to disagree about the same log.
    failed = bool(errors) or (bool(warnings) and args.strict)
    counted = f"{len(units)} unit(s), {len(entries)} entr(ies)"
    print(f"decisions-reported  {'FAIL' if failed else 'ok  '}  {args.log}  ({counted})")
    for problem in sorted(problems, key=lambda p: (p.warning, p.where)):
        print(problem)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
