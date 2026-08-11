"""Tests for negative-result-taxonomy/scripts/kill_ledger.py.

The ledger is itself a gate, so these follow the rule the sibling skill states:
every check must be provably able to REFUSE and provably able to PASS, and each
scar that produced a clause has a test that fails if the clause is removed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import load_script, run_script

kl = load_script("negative-result-taxonomy", "kill_ledger.py")

TICKET = {
    "status": "OPEN",
    "failing_prong": "closure 41% vs a 60% bar",
    "measured_cause": "END leaves priced at zero, measured over 3,627 decisions",
    "candidate_fix": "price the leaf; precedent: the gated rebuild",
    "cheapest_test": "re-run the 200-decision replay, 20 minutes",
}


class LedgerCase(unittest.TestCase):
    """Every case writes a real ledger on disk — the only thing the tool reads."""

    def audit(self, entries, *, files=(), **kwargs):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name in files:
            (root / name).write_text("owner ruling, in prose", encoding="utf-8")
        path = root / "KILL_LEDGER.json"
        path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        return kl.audit(path, **kwargs)

    def assertBlocks(self, result, needle):
        self.assertEqual(result["verdict"], "LOOP_DEBT", result)
        self.assertTrue(any(needle in d for d in result["defects"]),
                        f"{needle!r} not in {result['defects']}")


class TestFamilyDeath(LedgerCase):

    def test_family_dead_without_ceiling_blocks(self):
        r = self.audit([{"candidate": "cardsight-v1", "kill_class": "FAMILY_DEAD"}])
        self.assertBlocks(r, "EARNED")

    def test_family_dead_with_a_measured_ceiling_passes(self):
        r = self.audit([{"candidate": "cardsight-v1", "kill_class": "FAMILY_DEAD",
                         "ceiling_evidence": "10x oracle 7.0% [lo95 4.9%] vs a "
                                             "3.5% floor, bar 10.5%"}])
        self.assertEqual(r["verdict"], "OK", r)

    def test_a_falsy_ceiling_is_not_a_ceiling(self):
        """`str(None)` is "None", which is truthy. The naive form accepted the
        ledger's own idiom for "no value yet" as measured evidence."""
        for junk in (None, False, 0, [], {}, "", "   "):
            r = self.audit([{"candidate": "x-v1", "kill_class": "FAMILY_DEAD",
                             "ceiling_evidence": junk}])
            self.assertBlocks(r, "EARNED")

    def test_an_unknown_class_blocks(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DEAD"}])
        self.assertBlocks(r, "not one of")

    def test_historical_backfill_is_allowed_and_owes_nothing(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "UNCLASSIFIED_HISTORICAL"}])
        self.assertEqual(r["verdict"], "OK", r)


class TestRedesignTicket(LedgerCase):

    def test_design_dead_without_a_ticket_blocks(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD"}])
        self.assertBlocks(r, "no redesign ticket")

    def test_design_dead_with_a_complete_ticket_passes(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(TICKET)}])
        self.assertEqual(r["verdict"], "OK", r)
        self.assertEqual(len(r["owed"]), 1)

    def test_a_ticket_missing_its_measured_cause_blocks(self):
        for field in kl.TICKET_PROSE:
            ticket = dict(TICKET, **{field: None})
            r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                             "ticket": ticket}])
            self.assertBlocks(r, field)

    def test_a_ticket_object_without_a_status_blocks(self):
        ticket = dict(TICKET)
        ticket.pop("status")
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": ticket}])
        self.assertBlocks(r, "carries no status")

    def test_an_invented_status_blocks(self):
        """The vocabulary widens by adding to a bucket, not by free text."""
        for bogus in ("DONE", "CLOSED", "IN_PROGRESS", "funded", "PAID"):
            r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                             "ticket": dict(TICKET, status=bogus)}])
            self.assertBlocks(r, "is invalid")

    def test_a_non_string_status_blocks_and_never_raises(self):
        """A set membership test hashes its operand; the tuple `in` it replaced
        did not. One raise inside a gate reported every check clean."""
        for junk in ([{"a": 1}], {"a": 1}, 7, True):
            r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                             "ticket": dict(TICKET, status=junk)}])
            self.assertBlocks(r, "must be a string")

    def test_a_ticket_that_is_not_an_object_blocks(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": "OPEN"}])
        self.assertBlocks(r, "must be an object")

    def test_closed_states_are_settled_and_silent(self):
        for state in ("ATTEMPTED", "RETIRED_BY_OWNER"):
            r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                             "ticket": dict(TICKET, status=state,
                                            owner_ruling="ruling.md")}],
                           files=["ruling.md"])
            self.assertEqual(r["verdict"], "OK", state)
            self.assertEqual(r["owed"], [], state)

    def test_the_buckets_partition_the_vocabulary(self):
        """A fifth word added to only one of the three places that read the
        vocabulary is how a bucket split silently stops meaning anything."""
        self.assertEqual(set(kl.OWED_STATUS) | set(kl.CLOSED_STATUS),
                         set(kl.VALID_STATUS))
        self.assertEqual(set(kl.OWED_STATUS) & set(kl.CLOSED_STATUS), set())
        self.assertTrue(set(kl.RULED_STATUS) <= set(kl.VALID_STATUS))


class TestFunding(LedgerCase):

    FUNDED = dict(TICKET, status="FUNDED", owner_ruling="rulings/2026-08-07.md")

    def test_funded_is_owed_and_stays_owed_even_when_it_is_a_defect(self):
        """FUNDED means the test was paid for and has not run. A state that let
        a line read as settled by promising to pay would be a way to clear debt
        by intending to — so it is owed whether or not its ruling checks out."""
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(self.FUNDED)}])
        self.assertEqual(r["verdict"], "LOOP_DEBT")     # the ruling file is absent
        self.assertTrue(any("[FUNDED]" in o for o in r["owed"]), r["owed"])

    def test_funded_without_a_ruling_blocks(self):
        ticket = dict(self.FUNDED)
        ticket.pop("owner_ruling")
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": ticket}])
        self.assertBlocks(r, "no owner_ruling")

    def test_a_falsy_ruling_does_not_count(self):
        for junk in (None, False, 0, [], {}, "", "   "):
            r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                             "ticket": dict(self.FUNDED, owner_ruling=junk)}])
            self.assertBlocks(r, "no owner_ruling")

    def test_a_ruling_naming_a_file_that_does_not_exist_blocks(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(self.FUNDED)}])
        self.assertBlocks(r, "does not exist")

    def test_a_ruling_that_exists_passes(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(self.FUNDED, owner_ruling="ruling.md")}],
                       files=["ruling.md"])
        self.assertEqual(r["verdict"], "OK", r)
        self.assertEqual(len(r["owed"]), 1)

    def test_a_ruling_pointing_at_the_ledger_itself_blocks(self):
        """The keystroke that writes the status must not also write its own
        evidence — that is bookkeeping in the costume of authentication."""
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(self.FUNDED,
                                        owner_ruling="KILL_LEDGER.json")}])
        self.assertBlocks(r, "outside the file it authorises")

    def test_a_ticket_is_read_on_every_class_not_only_where_required(self):
        """A funded ticket on a class that owes none was previously invisible:
        neither a defect nor a debt, the one state a ledger must not have."""
        r = self.audit([{"candidate": "bilinear-p1", "kill_class": "INSTRUMENT_VOID",
                         "ticket": dict(self.FUNDED, owner_ruling="ruling.md")}],
                       files=["ruling.md"])
        self.assertEqual(r["verdict"], "OK", r)
        self.assertEqual(len(r["owed"]), 1)
        self.assertIn("bilinear-p1", r["owed"][0])


class TestVisibility(LedgerCase):

    def test_owed_tickets_stay_visible_when_the_ledger_is_red(self):
        """"Listed on every run" means every run. Parked in the pass branch,
        one unrelated defect hid every owed ticket behind it — the debt
        disappearing exactly when the ledger was in its worst shape."""
        r = self.audit([
            {"candidate": "x-v1", "kill_class": "DESIGN_DEAD", "ticket": dict(TICKET)},
            {"candidate": "broken-v1", "kill_class": "FAMILY_DEAD"},
        ])
        self.assertEqual(r["verdict"], "LOOP_DEBT")
        self.assertEqual(len(r["owed"]), 1)
        self.assertIn("OWED", kl.render(r))

    def test_the_rendered_report_carries_the_owed_list(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "DESIGN_DEAD",
                         "ticket": dict(TICKET)}])
        self.assertIn("do not report these lines closed", kl.render(r))

    def test_the_rendered_report_carries_the_warnings(self):
        """A detection branch: it only runs when there is something to warn
        about, which is exactly the code that must not be dead. The coverage
        pass found it untested — warnings are this ledger's whole non-blocking
        visibility channel."""
        r = self.audit([{"candidate": "x-v1", "kill_class": "INSTRUMENT_VOID",
                         "base": {"artifact": "champ.tar.gz"}}])
        rendered = kl.render(r)
        self.assertIn("WARNINGS", rendered)
        self.assertIn("stronger", rendered)


class TestAntiZombie(LedgerCase):

    def twice(self, **overrides):
        base = {"kill_class": "DESIGN_DEAD", "ticket": dict(TICKET)}
        return [dict(base, candidate="turn-planner-v1"),
                dict(base, candidate="turn-planner-v2", **overrides)]

    def test_two_deaths_on_the_same_prong_and_cause_block(self):
        r = self.audit(self.twice())
        self.assertBlocks(r, "CEILING test, never a third variant")

    def test_a_ceiling_measurement_anywhere_in_the_family_clears_it(self):
        entries = self.twice()
        entries.append({"candidate": "turn-planner-v3", "kill_class": "FAMILY_DEAD",
                        "ceiling_evidence": "oracle 6.1% [lo95 4.0%] vs a 9% bar"})
        self.assertEqual(self.audit(entries)["verdict"], "OK")

    def test_the_comparison_ignores_case_and_whitespace(self):
        ticket = dict(TICKET,
                      failing_prong="  CLOSURE 41%   vs a 60% BAR ",
                      measured_cause=TICKET["measured_cause"].upper())
        r = self.audit(self.twice(ticket=ticket))
        self.assertBlocks(r, "same prong")

    def test_a_different_cause_is_a_different_death(self):
        r = self.audit(self.twice(
            ticket=dict(TICKET, measured_cause="the pool, measured at 5.5x")))
        self.assertEqual(r["verdict"], "OK", r)

    def test_three_deaths_without_a_ceiling_warn_without_blocking(self):
        entries = [{"candidate": f"outcome-train-v{n}", "kill_class": "DESIGN_DEAD",
                    "ticket": dict(TICKET, measured_cause=f"cause {n}")}
                   for n in (1, 2, 3)]
        r = self.audit(entries)
        self.assertEqual(r["verdict"], "OK", r)
        self.assertTrue(any("no ceiling measurement" in w for w in r["warnings"]))

    def test_the_family_defaults_from_the_version_suffix(self):
        self.assertEqual(kl.family_of({"candidate": "root-scout-v12"}), "root-scout")
        self.assertEqual(kl.family_of({"candidate": "bilinear-p1"}), "bilinear")
        self.assertEqual(kl.family_of({"candidate": "closer"}), "closer")

    def test_an_explicit_family_wins(self):
        self.assertEqual(
            kl.family_of({"candidate": "alpha-v1", "family": "outcome-training"}),
            "outcome-training")
        r = self.audit([dict(candidate="alpha-v1", family="one",
                             kill_class="DESIGN_DEAD", ticket=dict(TICKET)),
                        dict(candidate="alpha-v2", family="two",
                             kill_class="DESIGN_DEAD", ticket=dict(TICKET))])
        self.assertEqual(r["verdict"], "OK", "different families, not a zombie")


class TestMeter(LedgerCase):

    def opened(self, n, when="2026-08-06"):
        return [{"candidate": f"c{i}-v1", "kill_class": "DESIGN_DEAD",
                 "ticket": dict(TICKET, opened_utc=when)} for i in range(n)]

    def test_many_opened_and_none_attempted_reads_as_over_tuned(self):
        r = self.audit(self.opened(4), now=kl._date("2026-08-11"))
        self.assertTrue(r["meter"]["over_tuned"], r["meter"])
        self.assertTrue(any("over-tuned" in w for w in r["warnings"]))

    def test_a_balanced_window_is_quiet(self):
        entries = self.opened(3) + [
            {"candidate": f"done{i}-v1", "kill_class": "DESIGN_DEAD",
             "ticket": dict(TICKET, status="ATTEMPTED", closed_utc="2026-08-07",
                            owner_ruling=None)} for i in range(2)]
        r = self.audit(entries, now=kl._date("2026-08-11"))
        self.assertFalse(r["meter"]["over_tuned"], r["meter"])

    def test_an_impossible_date_is_ignored_rather_than_crashing(self):
        """`2026-13-45` matches the shape and is not a date. A meter that
        raises here takes the whole ledger check down with it."""
        self.assertIsNone(kl._date("2026-13-45"))
        r = self.audit(self.opened(4, when="2026-02-31"),
                       now=kl._date("2026-08-11"))
        self.assertEqual(r["verdict"], "OK", r)
        self.assertEqual(r["meter"]["opened"], 0)

    def test_tickets_outside_the_window_do_not_count(self):
        r = self.audit(self.opened(4, when="2026-01-01"),
                       now=kl._date("2026-08-11"))
        self.assertEqual(r["meter"]["opened"], 0)
        self.assertFalse(r["meter"]["over_tuned"])

    def test_two_opened_is_below_the_noise_floor(self):
        r = self.audit(self.opened(2), now=kl._date("2026-08-11"))
        self.assertFalse(r["meter"]["over_tuned"], r["meter"])


class TestPowerPlan(LedgerCase):

    PLAN = {f: f"{f} value" for f in kl.POWER_PLAN_FIELDS}

    def test_undecidable_without_a_plan_blocks(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "UNDECIDABLE"}])
        self.assertBlocks(r, "no power_plan")

    def test_an_incomplete_plan_blocks_and_names_the_gaps(self):
        for field in kl.POWER_PLAN_FIELDS:
            plan = dict(self.PLAN)
            plan[field] = "  "
            r = self.audit([{"candidate": "x-v1", "kill_class": "UNDECIDABLE",
                             "power_plan": plan}])
            self.assertBlocks(r, field)

    def test_a_priced_way_out_passes(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "UNDECIDABLE",
                         "power_plan": dict(self.PLAN)}])
        self.assertEqual(r["verdict"], "OK", r)

    def test_undecidable_is_not_counted_as_a_death(self):
        """Two undecidables on one prong are not a zombie family — nothing
        died, and the way out is a price, not a redesign."""
        r = self.audit([{"candidate": "x-v1", "kill_class": "UNDECIDABLE",
                         "power_plan": dict(self.PLAN), "ticket": dict(TICKET)},
                        {"candidate": "x-v2", "kill_class": "UNDECIDABLE",
                         "power_plan": dict(self.PLAN), "ticket": dict(TICKET)}])
        self.assertEqual(r["verdict"], "OK", r)


class TestBase(LedgerCase):

    def test_a_base_without_evidence_warns_and_does_not_block(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "INSTRUMENT_VOID",
                         "base": {"artifact": "champ.tar.gz", "sha256": "ab"}}])
        self.assertEqual(r["verdict"], "OK", r)
        self.assertTrue(any("stronger" in w for w in r["warnings"]))

    def test_a_base_with_evidence_is_quiet(self):
        r = self.audit([{"candidate": "x-v1", "kill_class": "INSTRUMENT_VOID",
                         "base": {"artifact": "champ.tar.gz", "sha256": "ab",
                                  "evidence": "banked read 724.1 over 51 games"}}])
        self.assertEqual(r["warnings"], [])


class TestMalformedInput(unittest.TestCase):
    """A gate that cannot read its input must rule on nothing, loudly."""

    def audit_text(self, text, name="KILL_LEDGER.json"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            return kl.audit(path)

    def test_a_missing_ledger_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = kl.audit(Path(tmp) / "nope.json")
        self.assertEqual(r["verdict"], "REFUSE")
        self.assertIn("does not exist", r["detail"])

    def test_unparseable_json_refuses(self):
        r = self.audit_text("{not json")
        self.assertEqual(r["verdict"], "REFUSE")

    def test_a_ledger_with_no_entries_array_refuses(self):
        r = self.audit_text(json.dumps({"note": "hello"}))
        self.assertEqual(r["verdict"], "REFUSE")

    def test_a_bare_list_is_accepted_as_the_entries(self):
        r = self.audit_text(json.dumps([{"candidate": "x-v1",
                                         "kill_class": "INSTRUMENT_VOID"}]))
        self.assertEqual(r["verdict"], "OK", r)

    def test_an_entry_that_is_not_an_object_blocks(self):
        r = self.audit_text(json.dumps({"entries": ["x-v1"]}))
        self.assertEqual(r["verdict"], "LOOP_DEBT")
        self.assertIn("must be an object", r["defects"][0])

    def test_an_empty_ledger_passes(self):
        r = self.audit_text(json.dumps({"entries": []}))
        self.assertEqual(r["verdict"], "OK", r)

    def test_the_refusal_renders_without_a_traceback(self):
        r = self.audit_text("{not json")
        self.assertIn("REFUSE", kl.render(r))


class TestCommandLine(unittest.TestCase):

    def ledger(self, tmp, entries):
        path = Path(tmp) / "KILL_LEDGER.json"
        path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        return path

    def run_kl(self, *args):
        return run_script("negative-result-taxonomy", "kill_ledger.py", *args)

    def test_a_clean_ledger_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.ledger(tmp, [{"candidate": "x-v1",
                                      "kill_class": "INSTRUMENT_VOID"}])
            proc = self.run_kl(str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_defect_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.ledger(tmp, [{"candidate": "x-v1",
                                      "kill_class": "FAMILY_DEAD"}])
            proc = self.run_kl(str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("EARNED", proc.stdout)

    def test_an_unreadable_ledger_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = self.run_kl(str(Path(tmp) / "missing.json"))
        self.assertEqual(proc.returncode, 2)

    def test_json_output_is_machine_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.ledger(tmp, [{"candidate": "x-v1",
                                      "kill_class": "FAMILY_DEAD"}])
            proc = self.run_kl(str(path), "--json")
        self.assertEqual(json.loads(proc.stdout)["verdict"], "LOOP_DEBT")

    def test_every_template_is_valid_json(self):
        for name in ("entry", "ticket", "power-plan"):
            proc = self.run_kl("--template", name)
            self.assertEqual(proc.returncode, 0, name)
            json.loads(proc.stdout)

    def test_a_bad_now_is_rejected_rather_than_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.ledger(tmp, [])
            proc = self.run_kl(str(path), "--now", "last tuesday")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("YYYY-MM-DD", proc.stderr)

    def test_a_ledger_path_is_required(self):
        proc = self.run_kl()
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
