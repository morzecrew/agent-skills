"""Tests for flag-dont-flip/scripts/log_check.py.

Every check the script makes enforces a sentence in SKILL.md, so every test
here names the rule it is defending. The fixtures are whole logs rather than
fragments: the parser's job is to find entries inside a document that also
contains a title, a classes table, outcome tables and prose, and a fragment
would not exercise that.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from support import load_script, run_script

script = load_script("flag-dont-flip", "log_check.py")

ENTRY = """## D-001 — Retry budget scoped to batch, not message

- **Touches:** RFC 0014 §5.2, decisions row 4 (`ASSUMED`)
- **RFC said:** per-message retry counter
- **Built:** per-batch retry budget
- **Action:** departed
- **Evidence:** queue/consumer.py:1-4 — the counter is reset on redelivery
- **Because:** redelivery resets per-message counters, so a per-message counter
  cannot bound total work for a poison message
- **Class:** `spec-gap`
- **Consequence:** a poison message can consume up to N x batch attempts
- **Proposed row (RFC 0014):** `ASSUMED` — retry budget is per-batch
"""

OUTCOMES = """## Decision-row outcomes — 2026-08-21

| RFC | Row | Outcome | Grade | Decision | From |
|---|---|---|---|---|---|
| 0014 | 5 | Accepted | `ASSUMED` | Retry budget is per-batch | D-001 |
"""


def log(entries: str = ENTRY, drift: str = "**Drift count: 0.**",
        outcomes: str = OUTCOMES, unit: str = "# Wave 1 · Retry handling") -> str:
    return f"""# Execution log

Where building something disagreed with the design for it.

## Classes

| Class | Test | Meaning |
|---|---|---|
| `drift` | The RFC covered it and it was built otherwise | **A defect** |

{unit}

Branch `feature/wave-1`. RFC 0014 P1.

{drift}

{entries}
{outcomes}
"""


class Case(unittest.TestCase):
    """A log in a throwaway tree, so evidence paths can genuinely resolve."""

    def setUp(self):
        self.room = TemporaryDirectory()
        self.root = Path(self.room.name)
        (self.root / "queue").mkdir()
        (self.root / "queue" / "consumer.py").write_text("a\nb\nc\nd\n", encoding="utf-8")
        rfcs = self.root / "rfcs"
        rfcs.mkdir()
        (rfcs / "0014-retry-handling.md").write_text(
            "# RFC 0014\n\n## 11. Decisions\n\n"
            "| # | Grade | Decision |\n| --- | --- | --- |\n"
            "| 1 | `LOCKED` | Dead-letter queue is per-topic. |\n"
            "| 4 | `ASSUMED` | Retry counter is per message. |\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.room.cleanup()

    def check(self, text: str, *args: str) -> tuple[int, str]:
        path = self.root / "EXECUTION-LOG.md"
        path.write_text(text, encoding="utf-8")
        done = run_script("flag-dont-flip", "log_check.py", str(path),
                          "--root", str(self.root), *args)
        return done.returncode, done.stdout + done.stderr


class CleanLogTest(Case):
    def test_a_well_formed_log_passes(self):
        code, out = self.check(log(), "--rfc-dir", str(self.root / "rfcs"), "--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("1 unit(s), 1 entr(ies)", out)

    def test_an_empty_log_is_not_a_failure(self):
        """A log with a unit and nothing to report is the honest zero case."""
        code, out = self.check(log(entries="", outcomes=""))
        self.assertEqual(code, 0, out)


class LegalityTest(Case):
    """The rule the skill is named for, and the only one a tool can decide."""

    def test_departing_from_a_locked_row_fails(self):
        code, out = self.check(log(ENTRY.replace("row 4 (`ASSUMED`)", "row 1 (`LOCKED`)")))
        self.assertEqual(code, 1)
        self.assertIn("only `halted` is legal", out)

    def test_halting_on_an_assumed_row_fails_too(self):
        """Over-caution is a failure, not a safe default: it buys a round-trip
        the grading existed to avoid."""
        code, out = self.check(log(ENTRY.replace("**Action:** departed",
                                                 "**Action:** halted")))
        self.assertEqual(code, 1)
        self.assertIn("over-caution", out.lower())

    def test_each_grade_admits_exactly_its_own_action(self):
        for grade, action in (("LOCKED", "halted"), ("ASSUMED", "departed"),
                              ("OPEN", "decided")):
            entry = (ENTRY.replace("(`ASSUMED`)", f"(`{grade}`)")
                          .replace("**Action:** departed", f"**Action:** {action}"))
            code, out = self.check(log(entry))
            self.assertEqual(code, 0, f"{grade}/{action}: {out}")

    def test_an_unknown_action_is_named(self):
        code, out = self.check(log(ENTRY.replace("**Action:** departed",
                                                 "**Action:** proceeded")))
        self.assertEqual(code, 1)
        self.assertIn("action `proceeded`", out)

    def test_an_unlisted_decision_has_no_grade_to_check(self):
        """`OPEN` means the author looked; unlisted means nobody did, and there
        is no grade to be legal against."""
        entry = ENTRY.replace("RFC 0014 §5.2, decisions row 4 (`ASSUMED`)",
                              "nothing in the decision table covers this — unlisted")
        code, out = self.check(log(entry))
        self.assertEqual(code, 0, out)


class SchemaTest(Case):
    def test_every_required_field_is_required(self):
        for field in ("Touches", "RFC said", "Built", "Action", "Evidence",
                      "Because", "Class", "Consequence"):
            line = next(l for l in ENTRY.splitlines() if l.startswith(f"- **{field}:**"))
            code, out = self.check(log(ENTRY.replace(line + "\n", "")))
            self.assertEqual(code, 1, f"{field} was not required")
            self.assertIn(field, out)

    def test_found_stands_in_for_built(self):
        """Some departures discover what already exists; "Built" would be a
        small lie in the field a reader checks first."""
        code, out = self.check(log(ENTRY.replace("- **Built:**", "- **Found:**")))
        self.assertEqual(code, 0, out)

    def test_an_unknown_class_is_named(self):
        code, out = self.check(log(ENTRY.replace("`spec-gap`", "`untidy`")))
        self.assertEqual(code, 1)
        self.assertIn("class `untidy`", out)

    def test_a_wrapped_field_value_is_not_read_as_missing(self):
        self.assertEqual(self.check(log())[0], 0)

    def test_the_missing_field_is_named_the_way_the_template_writes_it(self):
        """A checker that asks for `Rfc Said` sends the reader hunting for a
        field that does not exist."""
        line = "- **RFC said:** per-message retry counter\n"
        _, out = self.check(log(ENTRY.replace(line, "")))
        self.assertIn("`RFC said`", out)
        self.assertNotIn("Rfc Said", out)


class EvidenceTest(Case):
    def test_a_path_that_does_not_exist_fails(self):
        code, out = self.check(log(ENTRY.replace("queue/consumer.py:1-4",
                                                 "queue/nope.py:1-4")))
        self.assertEqual(code, 1)
        self.assertIn("not in the tree", out)

    def test_a_line_range_past_the_end_of_the_file_fails(self):
        code, out = self.check(log(ENTRY.replace("queue/consumer.py:1-4",
                                                 "queue/consumer.py:1-90")))
        self.assertEqual(code, 1)
        self.assertIn("4-line file", out)

    def test_a_claim_is_not_evidence(self):
        code, out = self.check(log(ENTRY.replace(
            "queue/consumer.py:1-4 — the counter is reset on redelivery", "not available")))
        self.assertEqual(code, 1)
        self.assertIn("nothing anyone could re-run", out)

    def test_a_command_with_its_output_is_evidence(self):
        code, out = self.check(log(ENTRY.replace(
            "queue/consumer.py:1-4 — the counter is reset on redelivery",
            "`pytest tests/api/auth.py` — 3 failed, ECONNREFUSED 127.0.0.1:6379")))
        self.assertEqual(code, 0, out)


class NumberingTest(Case):
    """RFC decision rows cite these identifiers."""

    def test_a_reused_number_fails(self):
        code, out = self.check(log(ENTRY + "\n" + ENTRY))
        self.assertEqual(code, 1)
        self.assertIn("reused", out)

    def test_a_gap_in_the_sequence_fails(self):
        second = ENTRY.replace("## D-001 —", "## D-004 —")
        code, out = self.check(log(ENTRY + "\n" + second, outcomes=""))
        self.assertEqual(code, 1)
        self.assertIn("D-002", out)
        self.assertIn("D-003", out)

    def test_consecutive_numbers_pass(self):
        second = ENTRY.replace("## D-001 —", "## D-002 —")
        code, out = self.check(log(ENTRY + "\n" + second, outcomes=""), "--strict")
        self.assertEqual(code, 1, "the strict run should still flag the proposals")
        self.assertNotIn("gap in the sequence", out)


class DriftCountTest(Case):
    def test_a_unit_with_no_drift_count_fails(self):
        code, out = self.check(log(drift="Branch notes with no count."))
        self.assertEqual(code, 1)
        self.assertIn("no drift count", out)

    def test_a_count_of_zero_beside_a_drift_entry_fails(self):
        """The count is the number the practice is measured by; a zero that is
        not true is worse than no count at all."""
        code, out = self.check(log(ENTRY.replace("`spec-gap`", "`drift`")))
        self.assertEqual(code, 1)
        self.assertIn("carries 1 entry(ies) classed `drift`", out)

    def test_an_honest_non_zero_count_passes(self):
        code, out = self.check(log(ENTRY.replace("`spec-gap`", "`drift`"),
                                   drift="**Drift count: 1** — D-001, against wave 1."))
        self.assertEqual(code, 0, out)

    def test_an_entry_outside_any_unit_is_reported(self):
        text = log(entries="", drift="**Drift count: 0.**").replace(
            "# Wave 1 · Retry handling", "PLACEHOLDER") + "\n" + ENTRY
        code, out = self.check(text)
        self.assertEqual(code, 1)
        self.assertIn("before any unit heading", out)


class ProposalTest(Case):
    def test_an_unanswered_proposal_warns_but_does_not_fail(self):
        """A proposal made today may simply not be answered yet; a log where
        none is ever answered is the failure mode the skill names last."""
        code, out = self.check(log(outcomes=""))
        self.assertEqual(code, 0)
        self.assertIn("warn", out)
        self.assertIn("no outcomes table answers", out)

    def test_strict_turns_that_warning_into_a_failure(self):
        code, _ = self.check(log(outcomes=""), "--strict")
        self.assertEqual(code, 1)

    def test_a_refusal_answers_a_proposal_as_well_as_an_acceptance(self):
        refused = OUTCOMES.replace(
            "| 0014 | 5 | Accepted | `ASSUMED` | Retry budget is per-batch | D-001 |",
            "| 0014 | — | Refused | — | per-batch budget; author prefers a ceiling | D-001 |")
        code, out = self.check(log(outcomes=refused), "--strict")
        self.assertEqual(code, 0, out)

    def test_an_entry_proposing_nothing_needs_no_outcome(self):
        entry = "\n".join(l for l in ENTRY.splitlines()
                          if not l.startswith("- **Proposed row"))
        code, out = self.check(log(entry, outcomes=""), "--strict")
        self.assertEqual(code, 0, out)


class CitationTest(Case):
    def rfcs(self) -> str:
        return str(self.root / "rfcs")

    def test_a_cited_rfc_that_does_not_exist_fails(self):
        code, out = self.check(log(ENTRY.replace("RFC 0014", "RFC 0099")),
                               "--rfc-dir", self.rfcs())
        self.assertEqual(code, 1)
        self.assertIn("not in", out)

    def test_a_cited_row_the_table_does_not_have_fails(self):
        code, out = self.check(log(ENTRY.replace("row 4 (`ASSUMED`)", "row 9 (`ASSUMED`)")),
                               "--rfc-dir", self.rfcs())
        self.assertEqual(code, 1)
        self.assertIn("rows: 1, 4", out)

    def test_a_grade_that_has_since_changed_is_not_a_finding(self):
        """The log records the grade in force when the executor acted. Grades
        change; comparing them would report an honest record as a defect."""
        entry = (ENTRY.replace("row 4 (`ASSUMED`)", "row 1 (`ASSUMED`)")
                      .replace("**Action:** departed", "**Action:** departed"))
        code, out = self.check(log(entry), "--rfc-dir", self.rfcs())
        self.assertEqual(code, 0, out)

    def test_citations_are_only_checked_when_asked_for(self):
        code, out = self.check(log(ENTRY.replace("RFC 0014", "RFC 0099")))
        self.assertEqual(code, 0, out)


class BacklinkTest(Case):
    """The direction that rots without anyone noticing.

    A merge between two units that both claimed the next number forces one of
    them to renumber, and every RFC row citing the old one now points at a
    stranger's entry — which reads as provenance and carries none.
    """

    def cite(self, text: str) -> None:
        rfc = self.root / "rfcs" / "0014-retry-handling.md"
        rfc.write_text(rfc.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_a_row_citing_a_real_entry_passes(self):
        self.cite("\n| 5 | `ASSUMED` | Per-batch budget. Added by execution "
                  "2026-08-21 — see [EXECUTION-LOG.md](EXECUTION-LOG.md) D-001. |\n")
        code, out = self.check(log(), "--rfc-dir", str(self.root / "rfcs"))
        self.assertEqual(code, 0, out)

    def test_a_row_citing_an_entry_that_does_not_exist_fails(self):
        self.cite("\n| 5 | `ASSUMED` | Per-batch budget. Added by execution "
                  "2026-08-21 — see [EXECUTION-LOG.md](EXECUTION-LOG.md) D-024. |\n")
        code, out = self.check(log(), "--rfc-dir", str(self.root / "rfcs"))
        self.assertEqual(code, 1)
        self.assertIn("D-024", out)
        self.assertIn("0014-retry-handling.md:", out, "the row has to be locatable")

    def test_a_d_number_on_a_line_that_never_names_the_log_is_left_alone(self):
        """An RFC is free to use `D-` for its own purposes."""
        self.cite("\nSee diagram D-024 in the appendix.\n")
        code, out = self.check(log(), "--rfc-dir", str(self.root / "rfcs"))
        self.assertEqual(code, 0, out)

    def test_the_log_is_not_scanned_against_itself(self):
        """It cites its own numbers on nearly every line."""
        (self.root / "rfcs" / "EXECUTION-LOG.md").write_text(
            "see EXECUTION-LOG.md D-999\n", encoding="utf-8")
        code, out = self.check(log(), "--rfc-dir", str(self.root / "rfcs"))
        self.assertEqual(code, 0, out)

    def test_backlinks_are_only_checked_when_the_rfcs_are_named(self):
        self.cite("\nsee [EXECUTION-LOG.md](EXECUTION-LOG.md) D-024\n")
        code, out = self.check(log())
        self.assertEqual(code, 0, out)


class CommandLineTest(Case):
    def test_an_unreadable_log_exits_two_rather_than_pretending_it_passed(self):
        done = run_script("flag-dont-flip", "log_check.py", str(self.root / "nope.md"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("cannot read", done.stderr)

    def test_the_summary_line_never_disagrees_with_the_exit_code(self):
        """The line is for a person and the code is for CI. Found by sabotage:
        the two were computed from separate copies of one condition, so a
        strict run could print `ok` and exit 1."""
        cases = [
            (log(), (), 0),
            (log(outcomes=""), (), 0),                      # warning, not strict
            (log(outcomes=""), ("--strict",), 1),           # same warning, strict
            (log(ENTRY.replace("**Action:** departed", "**Action:** proceeded")), (), 1),
        ]
        for text, args, expected in cases:
            code, out = self.check(text, *args)
            self.assertEqual(code, expected, out)
            verdict = out.splitlines()[0]
            self.assertIn("FAIL" if expected else "ok", verdict)
            if not expected:
                self.assertNotIn("FAIL", verdict)


if __name__ == "__main__":
    unittest.main()
