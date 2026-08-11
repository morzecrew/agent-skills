#!/usr/bin/env python3
"""Validate a call block — the pre-run prediction, checked before the spend.

Six lines plus a decision band, and one of the checks is arithmetic rather
than presence:

  C1  every required line is present and carries a value
  C2  P(survives) is a probability
  C3  the 80% interval is two numbers, low then high
  C4  the interval is NARROWER than the decision band
  C5  the band or the interval could not be read as numbers — reported, never
      silently passed, because "not checked" and "checked and fine" must not
      look the same
  C6  the artifact line is answered ("none, because ..." is a valid answer;
      silence is not)
  C7  --committed-before RESULT: the block reached git before the result did

C4 is the one that pays for the tool. If your own 80% interval is wider than
the gap between alive and dead, both verdicts are consistent with what you
already believe, so the run cannot resolve anything and should not be run.
That is decidable from the block alone, before any machine time is spent.

Exit 0 clean (warnings allowed) · 1 findings · 2 unreadable input or git error.
Standard library only. No network.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Each field: (id, human label, patterns that introduce it). Matching is on the
# label text, so numbering and markdown decoration are free-form.
FIELDS = (
    ("metric", "the metric with units", (r"metric", r"primary number")),
    ("prediction", "the predicted number", (r"predict", r"point estimate")),
    ("interval", "the 80% interval", (r"80\s*%\s*interval", r"\binterval\b")),
    ("probability", "P(survives)", (r"p\s*\(\s*surviv", r"probability of surviv")),
    # Both spellings parse: a document written to the older label must not
    # stop validating because this template changed its wording.
    ("wrong", "the likeliest reason this prediction is wrong",
     (r"reason.*wrong", r"wrong.*reason")),
    ("artifact", "the artifact that could answer this without the run",
     (r"artifact", r"already on disk", r"without (?:the )?(?:run|machine)")),
    ("band", "the decision band", (r"decision band", r"\bband\b")),
)
REQUIRED = tuple(f[0] for f in FIELDS)

NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
# A label followed by a separator, then the value. Leading list markers, bold
# and numbering are stripped first, so `1. **80% interval:** [6%, 35%]` reads
# the same as `80% interval - [6%, 35%]`.
DECORATION = re.compile(r"^\s*(?:[-*+]\s*|\d+[.)]\s*)?[*_`#\s]*")
SEPARATOR = re.compile(r"^\s*[:\-—–]\s*")


def _strip(line: str) -> str:
    return DECORATION.sub("", line.rstrip())


def split_label(line: str) -> tuple[str, str] | None:
    """(label, value) around the first separator, or None if there is none.

    The separator is a colon, or a dash with spaces on both sides. Matching the
    field keyword and then taking the rest of the line was wrong in a way that
    looked right: `**Artifact already on disk ...:** none` yielded the value
    "already on disk ...:** none", which still contained every number the
    arithmetic needed, so the checks passed while the parse was nonsense.
    """
    colon = line.find(":")
    dash = min((m.start() for m in re.finditer(r"\s[—–-]\s", line)), default=-1)
    candidates = [i for i in (colon, dash) if i >= 0]
    if not candidates:
        return None
    cut = min(candidates)
    label = line[:cut]
    value = SEPARATOR.sub("", line[cut:], count=1)
    return label, re.sub(r"^[*_`)\]]*", "", value).strip(" *_`")


def parse(text: str) -> dict[str, str]:
    """Field id -> value, for every field this document names."""
    found: dict[str, str] = {}
    for raw in text.splitlines():
        split = split_label(_strip(raw))
        if split is None:
            continue
        label, value = split
        low = label.lower()
        for field, _label, patterns in FIELDS:
            # A heading that merely NAMES the field ("## Decision band") carries
            # no value. Recording it would mask the real line below and report
            # the field as missing while it sits in the document.
            if field in found or not value:
                continue
            if any(re.search(pattern, low) for pattern in patterns):
                found[field] = value
                break
    return found


def numbers(value: str) -> list[float]:
    return [float(n) for n in NUMBER.findall(value)]


def span(value: str) -> tuple[float, float] | None:
    """Two numbers read as an ordered range, or None."""
    found = numbers(value)
    if len(found) != 2:
        return None
    low, high = found
    return (low, high) if low <= high else (high, low)


def check(text: str) -> list[dict]:
    """Findings for one call block. Level is 'error' or 'warn'."""
    fields = parse(text)
    findings: list[dict] = []

    def add(level: str, code: str, message: str) -> None:
        findings.append({"level": level, "check": code, "message": message})

    for field, label, _patterns in FIELDS:
        if not fields.get(field):
            add("error", "C1", f"missing or empty: {label}")

    probability = fields.get("probability", "")
    if probability:
        values = numbers(probability)
        # `50%` and `0.5` are both meant; a percent sign is the only reliable
        # signal, since 1 is a legal probability and also a legal percentage.
        if not values:
            add("error", "C2", f"P(survives) carries no number: {probability!r}")
        else:
            value = values[0] / 100 if "%" in probability else values[0]
            if not 0.0 <= value <= 1.0:
                add("error", "C2", f"P(survives) is not a probability: {probability!r}")

    interval = span(fields.get("interval", ""))
    if fields.get("interval") and interval is None:
        add("error", "C3", f"the 80% interval needs exactly two numbers, got "
                           f"{fields['interval']!r}")

    band = span(fields.get("band", ""))
    if interval and band:
        interval_width = interval[1] - interval[0]
        band_width = band[1] - band[0]
        if interval_width >= band_width:
            add("error", "C4",
                f"the 80% interval ({interval_width:g} wide) is not narrower "
                f"than the decision band ({band_width:g} wide). Both verdicts "
                f"are consistent with what you already believe, so this run "
                f"cannot resolve anything — narrow the prediction, widen the "
                f"band, or do not run it.")
    elif fields.get("interval") and fields.get("band") and interval:
        add("warn", "C5",
            f"the decision band {fields['band']!r} is not two numbers, so the "
            f"interval-versus-band check did not run. State the band "
            f"numerically or say in the block why it cannot be.")

    artifact = fields.get("artifact", "")
    if artifact and artifact.lower().strip(" .") in {"tbd", "todo", "?", "n/a"}:
        add("error", "C6",
            f"the artifact line is deferred ({artifact!r}). 'none, because ...' "
            f"is a valid answer; a placeholder is not — this is the line that "
            f"most often cancels the run.")
    return findings


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def adding_commit(repo: Path, path: Path) -> str | None:
    """The commit that first added this path, or None if it is not in git."""
    proc = _git(repo, "log", "--diff-filter=A", "--format=%H", "--", str(path))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git log failed")
    shas = proc.stdout.split()
    return shas[-1] if shas else None       # oldest add, last in log order


def check_precedence(repo: Path, block: Path, result: Path) -> list[dict]:
    """C7 — the prediction must reach git before the data does.

    Ancestry, not timestamps: two commits made in the same second carry the
    same epoch, so a timestamp comparison called a correctly-ordered pair a
    post-registration. Being an ancestor is exact and has no clock in it.
    """
    block_at = adding_commit(repo, block)
    result_at = adding_commit(repo, result)
    if block_at is None:
        return [{"level": "error", "check": "C7",
                 "message": f"{block} is not committed. Its place in history is "
                            f"the only evidence that the call preceded the data; "
                            f"an uncommitted block is a note, not a registration."}]
    if result_at is None:
        return []                       # the data does not exist yet: correct order
    if _git(repo, "merge-base", "--is-ancestor", block_at, result_at).returncode == 0 \
            and block_at != result_at:
        return []
    same = " in the same commit as" if block_at == result_at else " at or after"
    return [{"level": "error", "check": "C7",
             "message": f"{block} entered git{same} {result}. A prediction "
                        f"committed once the result exists is a "
                        f"post-registration, whatever it is called."}]


TEMPLATE = """\
# CALL BLOCK — <what is being decided> — <ISO timestamp>

Committed BEFORE the run.

1. **Metric, with units:** <what will be read, and in what unit>
2. **Predicted number:** <point estimate>
3. **80% interval:** [<low>, <high>]
4. **P(survives):** <0.0 - 1.0>
5. **Likeliest reason this prediction is wrong:** <the failure you would
   otherwise meet as a surprise and then explain away>
6. **Artifact on disk that could answer this without the run:** <path, or
   "none, because ...">

## Decision band

- **ALIVE** if <metric> is above <high bar>
- **DEAD** if below <low bar>
- **VOID** if <the instrument failed>: <control that must hold>
- **Band:** [<low bar>, <high bar>]

## If it comes back null

<where this effort goes instead — the next suspected cause down the list>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a pre-run call block, including whether the run "
                    "can resolve anything at all.")
    parser.add_argument("block", nargs="?", type=Path,
                        help="path to the call block")
    parser.add_argument("--committed-before", type=Path, default=None,
                        metavar="RESULT",
                        help="assert the block reached git before this result file")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="repository for the git checks (default: .)")
    parser.add_argument("--template", action="store_true",
                        help="print a blank call block and exit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.template:
        print(TEMPLATE, end="")
        return 0
    if args.block is None:
        parser.error("a call block path is required (or use --template)")

    try:
        text = args.block.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"CALL BLOCK — REFUSE: {exc}", file=sys.stderr)
        return 2

    findings = check(text)
    if args.committed_before is not None:
        try:
            findings += check_precedence(args.repo, args.block, args.committed_before)
        except (OSError, RuntimeError) as exc:
            print(f"CALL BLOCK — REFUSE: {exc}", file=sys.stderr)
            return 2

    errors = [f for f in findings if f["level"] == "error"]
    if args.json:
        print(json.dumps(findings, indent=2))
    elif not findings:
        print(f"CALL BLOCK — {args.block} is complete and can resolve its band")
    else:
        print(f"CALL BLOCK — {len(errors)} problem(s), "
              f"{len(findings) - len(errors)} warning(s)")
        for finding in findings:
            marker = "  " if finding["level"] == "error" else "  warn: "
            print(f"{marker}{finding['check']}: {finding['message']}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
