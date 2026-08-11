#!/usr/bin/env python3
"""Validate a ledger of negative results — a kill is a diagnosis, not a terminus.

Reads one JSON ledger (see references/ledger-schema.md) and answers three
questions the individual verdicts cannot:

  DEFECTS   an unearned FAMILY_DEAD, a DESIGN_DEAD with no redesign ticket or an
            incomplete one, an invalid status, a funding or retirement whose
            ruling artifact does not exist, an UNDECIDABLE with no priced way
            out, and a family that died twice on the same prong from the same
            cause with no ceiling test ever run.

  OWED      every OPEN or FUNDED ticket, listed on EVERY run — including runs
            where the ledger is otherwise red. A funded test that has not run is
            not progress; it is progress that has been bought, and parking the
            owed list in the pass branch hides all debt behind one unrelated
            defect, exactly when the ledger is in its worst shape.

  METER     tickets opened against tickets attempted over a window. If the first
            greatly exceeds the second, the process is over-tuned and the rule
            itself needs amending. A loop rule that produces paperwork instead
            of attempts has failed on its own terms.

Exit 0 = OK, 1 = defects, 2 = the ledger could not be read (a gate that cannot
read its input rules on nothing rather than ruling on nothing).

Standard library only. No network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

VALID_CLASSES = ("FAMILY_DEAD", "DESIGN_DEAD", "INSTRUMENT_VOID",
                 "UNDECIDABLE", "UNCLASSIFIED_HISTORICAL")
# The two that are deaths. INSTRUMENT_VOID (the instrument was broken) and
# UNDECIDABLE (the instrument was sound but underpowered) never count as one.
DEATH_CLASSES = ("FAMILY_DEAD", "DESIGN_DEAD")

# Widening the vocabulary means adding to a BUCKET, never to the accepted set:
# a status that let a line read as settled by promising to pay for the test
# would be a way to clear debt by intending to.
OWED_STATUS = ("OPEN", "FUNDED")
CLOSED_STATUS = ("ATTEMPTED", "RETIRED_BY_OWNER")
VALID_STATUS = OWED_STATUS + CLOSED_STATUS
# Statuses that are claims about what a PERSON decided, so they owe an artifact
# outside this file. No agent funds or retires its own ticket.
RULED_STATUS = ("FUNDED", "RETIRED_BY_OWNER")

TICKET_PROSE = ("failing_prong", "measured_cause", "candidate_fix", "cheapest_test")
POWER_PLAN_FIELDS = ("achieved_mde", "required_mde", "units_needed",
                     "cost_estimate", "cheaper_alternative", "recommendation")

# planner-v1 and planner-v2 are one family; probe-p1 and probe-p2 too.
VERSION_SUFFIX = re.compile(r"-(?:v|p|r)\d+$", re.IGNORECASE)
ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

DEFAULT_WINDOW_DAYS = 14        # a fortnight, per the anti-bureaucracy tripwire
DEFAULT_METER_RATIO = 3.0
METER_FLOOR = 3                 # below this the ratio is noise, not a signal


def text(value) -> str:
    """A field that must carry prose, or "" when it carries nothing.

    Anything that is not a non-empty string reads as ABSENT. This is deliberate
    and load-bearing: `str(None)` is `"None"`, which is truthy, so the naive
    `str(v).strip()` form accepted a JSON null — the idiom for "no value yet" —
    as a recorded decision, and handed every writer a one-word escape from its
    own debt. `false`, `0`, `[]` and `{}` fall the same way.
    """
    return value.strip() if isinstance(value, str) else ""


def family_of(entry: dict) -> str:
    """The idea this build belongs to. Explicit `family` wins; otherwise strip a
    trailing version suffix, so sibling builds group without bookkeeping."""
    declared = text(entry.get("family"))
    if declared:
        return declared
    return VERSION_SUFFIX.sub("", text(entry.get("candidate")) or "?")


def _norm(value) -> str:
    """Whitespace- and case-insensitive form, for comparing two prose fields."""
    return " ".join(text(value).lower().split())


def _date(value, *, exact: bool = False):
    """The date in `value`, or None.

    Ledger fields are read as a PREFIX on purpose: `opened_utc` is documented as
    `YYYY-MM-DD`, and a full ISO timestamp is the likely deviation, so demanding
    an exact match would silently drop real tickets out of the meter. A value
    typed on the command line gets `exact=True`, because there the only thing a
    trailing suffix can mean is a typo, and accepting `2026-08-11junk` as a date
    is how a window silently ends somewhere the caller did not ask for.
    """
    raw = text(value)
    m = ISO_DATE.fullmatch(raw) if exact else ISO_DATE.match(raw)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _dict(value) -> dict | None:
    return value if isinstance(value, dict) else None


def _check_ticket(name: str, cls: str, entry: dict, ledger_path: Path,
                  ruling_root: Path, defects: list, owed: list) -> dict | None:
    """Score one entry's ticket. Returns the ticket dict when it is usable.

    The ticket is read on EVERY class, not only on DESIGN_DEAD. Reading it only
    where it is REQUIRED leaves a funded ticket on a non-owing class invisible:
    neither a defect nor a debt, which is the one state a ledger must not have.
    """
    raw = entry.get("ticket")
    if raw is None:
        if cls == "DESIGN_DEAD":
            defects.append(
                f"{name}: DESIGN_DEAD with no redesign ticket — the mechanism "
                f"worked and this build did not, so name the fix")
        return None
    ticket = _dict(raw)
    if ticket is None:
        defects.append(f"{name}: ticket must be an object, got "
                       f"{type(raw).__name__} {raw!r}")
        return None

    status = ticket.get("status")
    if status is None or (isinstance(status, str) and not status.strip()):
        defects.append(f"{name}: ticket carries no status — one of "
                       f"{list(VALID_STATUS)}")
    elif not isinstance(status, str):
        # A membership test against a set HASHES its left operand, so an
        # unhashable status would raise here rather than be rejected — and one
        # raise inside a gate wrapped in a blanket `except` reported every check
        # clean. A malformed row must block loudly, never take the gate down.
        defects.append(f"{name}: ticket status must be a string, got "
                       f"{type(status).__name__} {status!r}")
    elif status.strip() not in VALID_STATUS:
        defects.append(f"{name}: ticket status {status.strip()!r} is invalid — "
                       f"the vocabulary is {list(VALID_STATUS)}, and it widens "
                       f"by adding to a bucket, never by free text")
    else:
        state = status.strip()
        if state in RULED_STATUS:
            _check_ruling(name, state, ticket, ledger_path, ruling_root, defects)
        if state in OWED_STATUS:
            note = text(ticket.get("note")) or text(ticket.get("failing_prong"))
            owed.append(f"{name} [{state}]: {note or 'no note'}")

    if cls == "DESIGN_DEAD":
        missing = [f for f in TICKET_PROSE if not text(ticket.get(f))]
        if missing:
            defects.append(
                f"{name}: redesign ticket is missing {missing} — a ticket "
                f"without a measured cause produces a rebuild founded on a "
                f"guess, which is how one family dies four times")
    return ticket


def _check_ruling(name: str, state: str, ticket: dict, ledger_path: Path,
                  ruling_root: Path, defects: list) -> None:
    """`FUNDED` and `RETIRED_BY_OWNER` are claims about a person's decision.

    A non-empty field inside the very file being written is bookkeeping in the
    costume of authentication: the keystroke that writes the status writes the
    evidence for it. Requiring a separate artifact is a speed bump — one the
    named person can read and repudiate — not a lock.
    """
    ref = text(ticket.get("owner_ruling"))
    if not ref:
        defects.append(
            f"{name}: {state} with no owner_ruling — only the decision-maker "
            f"funds or retires a ticket, and the ruling must name a file "
            f"outside this ledger")
        return
    root = ruling_root.resolve()
    path = (root / ref).resolve()
    if path == ledger_path.resolve():
        defects.append(f"{name}: owner_ruling points at the ledger itself — the "
                       f"ruling must live outside the file it authorises")
    elif not path.is_relative_to(root):
        # An absolute path or `../../elsewhere` leaves the configured ruling
        # directory entirely, so the "artifact" can be any file on the machine.
        # A speed bump that accepts /etc/hostname is not a speed bump.
        defects.append(f"{name}: owner_ruling {ref!r} resolves outside "
                       f"{root} — name a path within the ruling directory")
    elif not path.is_file():
        # `exists()` is true for a directory, so `owner_ruling: "."` passed.
        reason = "is a directory, not a ruling" if path.exists() else "does not exist"
        defects.append(f"{name}: owner_ruling {ref!r} {reason} "
                       f"(looked in {root})")


def _check_zombies(entries: list, defects: list, warnings: list) -> None:
    """A redesign that dies on the SAME prong from the SAME cause consumes a
    milestone, and the next step is a ceiling test — never a third variant.

    No single verdict can see this. It is the census that finds it: one family
    in the ledger this rule came from had died four times on one prong without a
    ceiling measurement ever being run.
    """
    families: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fam = families.setdefault(family_of(entry),
                                  {"deaths": 0, "ceiling": False, "pairs": Counter()})
        # Only a FAMILY_DEAD entry's ceiling clears a family. Accepting it from
        # any class handed every repeat death an escape: add `ceiling_evidence`
        # prose to the second DESIGN_DEAD and the anti-zombie defect vanishes,
        # which is a way to clear the debt by asserting the thing the ceiling
        # was supposed to prove.
        if text(entry.get("kill_class")) == "FAMILY_DEAD" \
                and text(entry.get("ceiling_evidence")):
            fam["ceiling"] = True
        if text(entry.get("kill_class")) not in DEATH_CLASSES:
            continue
        fam["deaths"] += 1
        ticket = _dict(entry.get("ticket")) or {}
        prong, cause = _norm(ticket.get("failing_prong")), _norm(ticket.get("measured_cause"))
        if prong and cause:
            fam["pairs"][(prong, cause)] += 1

    for name, fam in sorted(families.items()):
        if fam["ceiling"]:
            continue
        repeats = [n for n in fam["pairs"].values() if n >= 2]
        if repeats:
            defects.append(
                f"family {name!r}: {max(repeats)} deaths on the same prong from "
                f"the same cause with no ceiling measurement anywhere — the next "
                f"step is a CEILING test, never a third variant")
        elif fam["deaths"] >= 3:
            warnings.append(
                f"family {name!r}: {fam['deaths']} deaths and no ceiling "
                f"measurement anywhere in the family. Ask what the mechanism "
                f"could do with perfect information before building a fourth.")


def _meter(entries: list, now: dt.date, window_days: int, ratio: float) -> dict:
    """Tickets opened against tickets attempted, over a window."""
    start = now - dt.timedelta(days=window_days)
    opened = attempted = 0
    for entry in entries:
        ticket = _dict(entry.get("ticket")) if isinstance(entry, dict) else None
        if not ticket:
            continue
        if (d := _date(ticket.get("opened_utc"))) and start <= d <= now:
            opened += 1
        if text(ticket.get("status")) == "ATTEMPTED":
            if (d := _date(ticket.get("closed_utc"))) and start <= d <= now:
                attempted += 1
    out = {"window_days": window_days, "as_of": now.isoformat(),
           "opened": opened, "attempted": attempted, "over_tuned": False}
    if opened >= METER_FLOOR and opened >= ratio * attempted:
        out["over_tuned"] = True
        out["detail"] = (
            f"{opened} ticket(s) opened against {attempted} attempted in "
            f"{window_days} days. The check is over-tuned: amend the rule rather "
            f"than letting it accumulate paperwork instead of attempts.")
    return out


def audit(path: Path, *, ruling_root: Path | None = None, now: dt.date | None = None,
          window_days: int = DEFAULT_WINDOW_DAYS,
          ratio: float = DEFAULT_METER_RATIO) -> dict:
    """The whole ledger, scored. Never raises on a malformed ledger."""
    result: dict = {"check": "kill_ledger", "ledger": str(path)}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {**result, "verdict": "REFUSE", "detail": f"{path} does not exist"}
    except (OSError, ValueError) as exc:
        return {**result, "verdict": "REFUSE", "detail": f"ledger unreadable: {exc}"}

    entries = doc if isinstance(doc, list) else (doc.get("entries") if isinstance(doc, dict) else None)
    if not isinstance(entries, list):
        return {**result, "verdict": "REFUSE",
                "detail": "ledger has no `entries` array"}

    ruling_root = ruling_root or path.parent
    defects: list[str] = []
    warnings: list[str] = []
    owed: list[str] = []

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            defects.append(f"entry #{index}: must be an object, got "
                           f"{type(entry).__name__}")
            continue
        name = text(entry.get("candidate")) or f"entry #{index}"
        cls = text(entry.get("kill_class"))
        if cls not in VALID_CLASSES:
            defects.append(f"{name}: kill_class {entry.get('kill_class')!r} is "
                           f"not one of {list(VALID_CLASSES)}")
            cls = ""

        if cls == "FAMILY_DEAD" and not text(entry.get("ceiling_evidence")):
            defects.append(
                f"{name}: FAMILY_DEAD without ceiling_evidence — family death is "
                f"EARNED by a measured ceiling (an oracle run whose lower bound "
                f"fails the bar against a same-run floor), never asserted")
        if cls and cls != "FAMILY_DEAD" and text(entry.get("ceiling_evidence")):
            # Silently ignoring it would hide the misclassification: a measured
            # ceiling that fails its bar IS a family death, and one that passes
            # is not ceiling evidence at all.
            defects.append(
                f"{name}: ceiling_evidence on a {cls} entry — the field is "
                f"FAMILY_DEAD-only. Escalate the class with the evidence, or "
                f"record the measurement somewhere it is not read as a ceiling.")
        if cls == "UNDECIDABLE":
            plan = _dict(entry.get("power_plan"))
            if plan is None:
                defects.append(
                    f"{name}: UNDECIDABLE with no power_plan — 'we could not "
                    f"tell' owes the number it would take to tell, so parking "
                    f"it is a choice against a price rather than a shrug")
            else:
                missing = [f for f in POWER_PLAN_FIELDS if not text(plan.get(f))]
                if missing:
                    defects.append(f"{name}: power_plan is missing {missing}")

        _check_ticket(name, cls, entry, path, ruling_root, defects, owed)

        base = _dict(entry.get("base"))
        if base is not None and not text(base.get("evidence")):
            warnings.append(
                f"{name}: base recorded with no evidence it is stronger. "
                f"Stacking and building forward look identical from outside; "
                f"the difference is whether the base has a banked measurement or a "
                f"passed gate behind it.")

    _check_zombies(entries, defects, warnings)
    meter = _meter(entries, now or dt.datetime.now(dt.timezone.utc).date(),
                   window_days, ratio)
    if meter["over_tuned"]:
        warnings.append(meter["detail"])

    result.update({"entries": len(entries), "defects": defects,
                   "owed": owed, "warnings": warnings, "meter": meter,
                   "verdict": "LOOP_DEBT" if defects else "OK"})
    if defects:
        result["detail"] = (
            f"{len(defects)} defect(s) in {len(entries)} entries. A kill is a "
            f"diagnosis, not a terminus: classify it, and if the design died "
            f"while the mechanism worked, name the fix.")
    return result


def render(result: dict) -> str:
    lines = [f"KILL LEDGER — {result['verdict']}"]
    if result["verdict"] == "REFUSE":
        lines.append(f"  {result['detail']}")
        return "\n".join(lines)
    meter = result["meter"]
    lines.append(f"  {result['entries']} entries · {len(result['defects'])} defect(s) "
                 f"· {len(result['owed'])} owed ticket(s)")
    if result["defects"]:
        lines.append("")
        lines.append("DEFECTS")
        lines += [f"  {d}" for d in result["defects"]]
    # OWED rides EVERY run, red or green. It reached the reader only by breaking
    # the gate once; fixing the gate would then have made real debt less visible
    # than the bug had been.
    if result["owed"]:
        lines.append("")
        lines.append("OWED — do not report these lines closed while they stand")
        lines += [f"  {o}" for o in result["owed"]]
    if result["warnings"]:
        lines.append("")
        lines.append("WARNINGS")
        lines += [f"  {w}" for w in result["warnings"]]
    lines.append("")
    lines.append(f"METER — {meter['opened']} opened / {meter['attempted']} attempted "
                 f"in {meter['window_days']} days to {meter['as_of']}")
    return "\n".join(lines)


TEMPLATES = {
    "entry": {
        "candidate": "",
        "family": "",
        "kill_class": "DESIGN_DEAD",
        "verdict_artifact": "",
        "ceiling_evidence": None,
        "base": {"artifact": "", "sha256": "", "evidence": ""},
        "ticket": {
            "status": "OPEN",
            "failing_prong": "which bar failed, with the measured number and the bar",
            "measured_cause": "the mechanism of failure, measured — never a guess",
            "candidate_fix": "the change, and whether its shape has a precedent here",
            "cheapest_test": "the test that settles it, with its cost in minutes",
            "prediction": "the call, made before the test runs",
            "opened_utc": "",
            "closed_utc": None,
            "owner_ruling": None,
            "note": "",
        },
        "power_plan": None,
    },
    "ticket": {
        "status": "OPEN",
        "failing_prong": "",
        "measured_cause": "",
        "candidate_fix": "",
        "cheapest_test": "",
        "prediction": "",
        "opened_utc": "",
        "closed_utc": None,
        "owner_ruling": None,
        "note": "",
    },
    "power-plan": {
        "achieved_mde": "the effect size this run could actually resolve",
        "required_mde": "the effect size the question needs",
        "units_needed": "how much more, in the units actually spent",
        "cost_estimate": "what that costs",
        "cheaper_alternative": "the smaller question that could be answered instead",
        "recommendation": "RUN | SHRINK | PARK, and why",
    },
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a ledger of negative results (a kill is a diagnosis).")
    parser.add_argument("ledger", nargs="?", type=Path,
                        help="path to the JSON ledger")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--ruling-root", type=Path, default=None,
                        help="resolve owner_ruling paths against this directory "
                             "(default: the ledger's own directory)")
    parser.add_argument("--now", default=None, metavar="YYYY-MM-DD",
                        help="end of the meter window (default: today, UTC)")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS,
                        help=f"meter window (default: {DEFAULT_WINDOW_DAYS})")
    parser.add_argument("--meter-ratio", type=float, default=DEFAULT_METER_RATIO,
                        help="opened:attempted ratio that reads as over-tuned "
                             f"(default: {DEFAULT_METER_RATIO})")
    parser.add_argument("--template", choices=sorted(TEMPLATES),
                        help="print a blank scaffold and exit")
    args = parser.parse_args(argv)

    if args.template:
        print(json.dumps(TEMPLATES[args.template], indent=2))
        return 0
    if args.ledger is None:
        parser.error("a ledger path is required (or use --template)")

    now = None
    if args.now:
        now = _date(args.now, exact=True)
        if now is None:
            parser.error(f"--now {args.now!r} is not a YYYY-MM-DD date")

    result = audit(args.ledger, ruling_root=args.ruling_root, now=now,
                   window_days=args.window_days, ratio=args.meter_ratio)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return {"OK": 0, "LOOP_DEBT": 1, "REFUSE": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
