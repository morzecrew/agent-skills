"""Tests for flag-dont-flip/scripts/log_check.py.

Every check gets both directions — a log it must refuse and one it must pass.
The silence check additionally gets its skip case asserted separately from its
pass case, because "no decision declared an area" and "every area was covered"
are the two states this tool exists to keep apart.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from support import commit_all, git_repo, load_script, run_script

script = load_script("flag-dont-flip", "log_check.py")

ENTRY = """```divergence
decision: {decision}
grade: {grade}
class: {klass}
at: 2026-08-20T11:04:12Z
attempt: 1
claim: this deployment has no Redis service
evidence: {evidence}
action: {action}
{extra}```
"""


def entry(decision: str = "D-3", grade: str = "LOCKED", klass: str = "spec-gap",
          evidence: str = "infra/compose.yaml:1-3", action: str = "halted",
          extra: str = "") -> str:
    return ENTRY.format(decision=decision, grade=grade, klass=klass,
                        evidence=evidence, action=action, extra=extra)


def log(*entries: str, drift: int | None = 0) -> str:
    head = "# T-0142\n\n"
    if drift is not None:
        head += f"**Drift count: {drift}.**\n\n"
    return head + "\n".join(entries)


class Fixture(unittest.TestCase):
    """A throwaway tree with one real file for evidence to resolve against."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "infra").mkdir()
        (self.root / "infra" / "compose.yaml").write_text(
            "services:\n  db:\n    image: postgres\n", encoding="utf-8")
        (self.root / "logs").mkdir()
        self.addCleanup(self._tmp.cleanup)

    def audit(self, text: str, task: dict | None = None,
              touched: list[str] | None = None):
        path = self.root / "logs" / "T-0142.md"
        path.write_text(text, encoding="utf-8")
        return script.audit(path, self.root, task, touched)

    def codes(self, text: str, **kwargs) -> list[str]:
        problems, _ = self.audit(text, **kwargs)
        return sorted(p.code for p in problems)

    def skips(self, text: str, **kwargs) -> list[str]:
        _, skipped = self.audit(text, **kwargs)
        return [s.what for s in skipped]


class SchemaTest(Fixture):
    def test_a_complete_entry_passes(self) -> None:
        self.assertEqual(self.codes(log(entry())), [])

    def test_a_missing_field_is_s3(self) -> None:
        broken = entry().replace("attempt: 1\n", "")
        self.assertIn("S3", self.codes(log(broken)))

    def test_an_empty_field_is_s3(self) -> None:
        broken = entry().replace("claim: this deployment has no Redis service", "claim:")
        self.assertIn("S3", self.codes(log(broken)))

    def test_an_unknown_grade_is_s4(self) -> None:
        self.assertIn("S4", self.codes(log(entry(grade="PROBABLY"))))

    def test_an_unknown_class_is_s5(self) -> None:
        self.assertIn("S5", self.codes(log(entry(klass="annoying"))))

    def test_an_unknown_action_is_s6(self) -> None:
        self.assertIn("S6", self.codes(log(entry(action="pondered"))))

    def test_a_non_rfc3339_timestamp_is_s7(self) -> None:
        broken = entry().replace("2026-08-20T11:04:12Z", "August 20th")
        self.assertIn("S7", self.codes(log(broken)))

    def test_a_local_timestamp_without_offset_is_s7(self) -> None:
        broken = entry().replace("2026-08-20T11:04:12Z", "2026-08-20T11:04:12")
        self.assertIn("S7", self.codes(log(broken)))

    def test_a_non_utc_offset_is_s7(self) -> None:
        # The field table says UTC. Two entries stamped in different zones sort
        # wrongly against each other, and ordering is what the log is for.
        broken = entry().replace("2026-08-20T11:04:12Z", "2026-08-20T11:04:12+09:00")
        self.assertIn("S7", self.codes(log(broken)))

    def test_an_explicit_zero_offset_passes(self) -> None:
        good = entry().replace("2026-08-20T11:04:12Z", "2026-08-20T11:04:12+00:00")
        self.assertEqual(self.codes(log(good)), [])

    def test_fractional_seconds_pass(self) -> None:
        good = entry().replace("2026-08-20T11:04:12Z", "2026-08-20T11:04:12.318Z")
        self.assertEqual(self.codes(log(good)), [])

    def test_an_unclosed_fence_is_s0(self) -> None:
        # Without this the entry is not a block at all: no fields to check, no
        # drift to count, and the log passes with "Drift count: 0".
        text = "# T\n\n**Drift count: 0.**\n\n```divergence\ndecision: D-3\ngrade: LOCKED\n"
        self.assertIn("S0", self.codes(text))

    def test_a_closed_fence_is_not_reported_as_unclosed(self) -> None:
        self.assertNotIn("S0", self.codes(log(entry())))

    def test_attempt_zero_is_s8(self) -> None:
        broken = entry().replace("attempt: 1", "attempt: 0")
        self.assertIn("S8", self.codes(log(broken)))

    def test_a_line_that_is_not_a_field_is_s1(self) -> None:
        broken = entry().replace("action: halted\n", "action: halted\nthis is just prose\n")
        self.assertIn("S1", self.codes(log(broken)))

    def test_a_repeated_field_is_s2(self) -> None:
        broken = entry().replace("action: halted\n", "action: halted\naction: departed\n")
        codes = self.codes(log(broken))
        self.assertIn("S2", codes)

    def test_a_repeated_field_is_read_as_its_first_occurrence(self) -> None:
        # Taking the last would let an entry restate a legal action after the
        # illegal one that actually happened.
        broken = entry(grade="LOCKED", action="departed").replace(
            "action: departed\n", "action: departed\naction: halted\n")
        codes = self.codes(log(broken))
        self.assertIn("L1", codes)

    def test_an_unlisted_decision_without_a_proposal_is_s9(self) -> None:
        text = log(entry(decision="unlisted", grade="UNLISTED", action="decided"))
        self.assertIn("S9", self.codes(text))

    def test_an_unlisted_decision_with_a_proposal_passes(self) -> None:
        text = log(entry(decision="unlisted", grade="UNLISTED", action="decided",
                         extra="proposal: ASSUMED — sessions end on password change\n"))
        self.assertEqual(self.codes(text), [])

    def test_prose_outside_the_blocks_is_ignored(self) -> None:
        text = log(entry()) + "\n\nHalted here, and that is the right outcome.\n"
        self.assertEqual(self.codes(text), [])


class LegalityTest(Fixture):
    def test_every_grade_passes_with_its_own_action(self) -> None:
        for grade, action in script.LEGAL.items():
            extra = "proposal: x\n" if grade == "UNLISTED" else ""
            decision = "unlisted" if grade == "UNLISTED" else "D-3"
            with self.subTest(grade=grade):
                text = log(entry(decision=decision, grade=grade, action=action, extra=extra))
                self.assertEqual(self.codes(text), [])

    def test_departing_from_a_lock_is_l1(self) -> None:
        self.assertIn("L1", self.codes(log(entry(grade="LOCKED", action="departed"))))

    def test_halting_on_an_assumption_is_also_l1(self) -> None:
        # The symmetric failure: over-caution costs the round-trip the grading
        # existed to avoid, so it has to fail as loudly as the flip does.
        self.assertIn("L1", self.codes(log(entry(grade="ASSUMED", action="halted"))))

    def test_halting_on_an_open_row_is_l1(self) -> None:
        self.assertIn("L1", self.codes(log(entry(grade="OPEN", action="halted"))))

    def test_legality_is_not_reported_twice_for_an_unknown_grade(self) -> None:
        codes = self.codes(log(entry(grade="MAYBE")))
        self.assertIn("S4", codes)
        self.assertNotIn("L1", codes)


class DriftCountTest(Fixture):
    def test_an_honest_zero_passes(self) -> None:
        self.assertEqual(self.codes(log(entry(), drift=0)), [])

    def test_a_missing_count_is_d1(self) -> None:
        self.assertIn("D1", self.codes(log(entry(), drift=None)))

    def test_a_missing_count_fails_even_with_no_entries(self) -> None:
        # An absent count and an honest zero must not be the same document.
        self.assertIn("D1", self.codes(log(drift=None)))

    def test_an_understated_count_is_d2(self) -> None:
        text = log(entry(klass="drift", grade="ASSUMED", action="departed"), drift=0)
        self.assertIn("D2", self.codes(text))

    def test_an_overstated_count_is_also_d2(self) -> None:
        self.assertIn("D2", self.codes(log(entry(), drift=3)))

    def test_the_last_declared_count_is_the_current_one(self) -> None:
        # The log is append-only, so revising the count means appending a new
        # line. Reading the first would force a later drift finding to choose
        # between failing this check and breaking append-only.
        text = ("# T\n\n**Drift count: 0.**\n\n"
                + entry(klass="drift", grade="ASSUMED", action="departed")
                + "\n**Drift count: 1.** Appended after the entry above.\n")
        self.assertEqual(self.codes(text), [])

    def test_a_stale_last_count_still_fails(self) -> None:
        text = ("# T\n\n**Drift count: 0.**\n\n"
                + entry(klass="drift", grade="ASSUMED", action="departed")
                + "\n**Drift count: 0.** Still claiming none.\n")
        self.assertIn("D2", self.codes(text))

    def test_a_matching_non_zero_count_passes(self) -> None:
        text = log(entry(klass="drift", grade="ASSUMED", action="departed"), drift=1)
        self.assertEqual(self.codes(text), [])


class EvidenceTest(Fixture):
    def test_a_single_line_citation_passes(self) -> None:
        self.assertEqual(self.codes(log(entry(evidence="infra/compose.yaml:2"))), [])

    def test_a_range_citation_passes(self) -> None:
        self.assertEqual(self.codes(log(entry(evidence="infra/compose.yaml:1-3"))), [])

    def test_a_trailing_note_after_a_citation_passes(self) -> None:
        text = log(entry(evidence="infra/compose.yaml:1-3 — no redis service defined"))
        self.assertEqual(self.codes(text), [])

    def test_a_sentence_is_e2(self) -> None:
        text = log(entry(evidence="Redis isn't available in this environment"))
        self.assertIn("E2", self.codes(text))

    def test_a_long_sentence_is_still_e2(self) -> None:
        # Length was never the test; locatability is.
        text = log(entry(evidence="the current architecture makes this impractical for now"))
        self.assertIn("E2", self.codes(text))

    def test_a_relative_path_escaping_root_is_e3(self) -> None:
        text = log(entry(evidence="../../etc/passwd:1"))
        self.assertIn("E3", self.codes(text))

    def test_an_absolute_path_is_e3(self) -> None:
        text = log(entry(evidence="/etc/passwd:1"))
        self.assertIn("E3", self.codes(text))

    def test_a_missing_file_is_e4(self) -> None:
        self.assertIn("E4", self.codes(log(entry(evidence="infra/absent.yaml:1"))))

    def test_a_line_past_end_of_file_is_e7(self) -> None:
        self.assertIn("E7", self.codes(log(entry(evidence="infra/compose.yaml:400"))))

    def test_a_range_past_end_of_file_is_e7(self) -> None:
        self.assertIn("E7", self.codes(log(entry(evidence="infra/compose.yaml:1-400"))))

    def test_an_inverted_range_is_e6(self) -> None:
        self.assertIn("E6", self.codes(log(entry(evidence="infra/compose.yaml:3-1"))))

    def test_a_command_with_output_passes(self) -> None:
        text = log(entry(evidence="`pnpm test auth.spec.ts` — 3 failed, ECONNREFUSED"))
        self.assertEqual(self.codes(text), [])

    def test_a_command_with_no_output_is_e1(self) -> None:
        self.assertIn("E1", self.codes(log(entry(evidence="`pnpm test auth.spec.ts`"))))

    def test_a_command_followed_only_by_punctuation_is_e1(self) -> None:
        self.assertIn("E1", self.codes(log(entry(evidence="`pnpm test auth.spec.ts` —"))))

    def test_a_symlink_out_of_root_is_e3(self) -> None:
        outside = Path(self._tmp.name).parent / "outside-target.txt"
        outside.write_text("secret\n", encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.root / "infra" / "link.yaml").symlink_to(outside)
        self.assertIn("E3", self.codes(log(entry(evidence="infra/link.yaml:1"))))


class SilenceTest(Fixture):
    TASK = {"id": "T-0142", "decisions": [
        {"id": "D-3", "grade": "LOCKED", "paths": ["src/session/**"]},
        {"id": "D-4", "grade": "ASSUMED", "paths": ["src/db/**"]},
        {"id": "D-5", "grade": "LOCKED"},
    ]}

    def test_a_touched_locked_area_with_no_entry_is_q1(self) -> None:
        codes = self.codes(log(), task=self.TASK, touched=["src/session/store.py"])
        self.assertIn("Q1", codes)

    def test_a_touched_locked_area_with_an_entry_passes(self) -> None:
        codes = self.codes(log(entry(decision="D-3")), task=self.TASK,
                           touched=["src/session/store.py"])
        self.assertEqual(codes, [])

    def test_an_untouched_locked_area_needs_no_entry(self) -> None:
        codes = self.codes(log(), task=self.TASK, touched=["README.md"])
        self.assertEqual(codes, [])

    def test_a_touched_assumed_area_needs_no_entry(self) -> None:
        codes = self.codes(log(), task=self.TASK, touched=["src/db/models.py"])
        self.assertEqual(codes, [])

    def test_a_decision_with_no_paths_is_skipped_not_passed(self) -> None:
        skipped = self.skips(log(), task=self.TASK, touched=["src/session/store.py"])
        self.assertIn("D-5", skipped)

    def test_without_a_task_the_check_is_skipped_not_passed(self) -> None:
        self.assertIn("silence", self.skips(log()))

    def test_without_a_diff_the_check_is_skipped_not_passed(self) -> None:
        self.assertIn("silence", self.skips(log(), task=self.TASK))

    def test_a_double_star_pattern_matches_the_directory_itself(self) -> None:
        self.assertTrue(script.matches("src/session", "src/session/**"))

    def test_a_double_star_pattern_does_not_match_a_sibling_prefix(self) -> None:
        # `src/session/**` must not swallow `src/sessions-legacy/`.
        self.assertFalse(script.matches("src/sessions-legacy/a.py", "src/session/**"))

    def test_a_plain_glob_still_works(self) -> None:
        self.assertTrue(script.matches("src/a.py", "src/*.py"))

    def test_an_unknown_task_grade_is_q2_not_a_silent_skip(self) -> None:
        # A typo'd grade removed the decision from the check entirely, and the
        # run still reported OK.
        task = {"decisions": [{"id": "D-3", "grade": "LOCKD", "paths": ["src/**"]}]}
        self.assertIn("Q2", self.codes(log(), task=task, touched=["src/a.py"]))

    def test_a_valid_non_locked_grade_is_still_out_of_scope(self) -> None:
        task = {"decisions": [{"id": "D-4", "grade": "ASSUMED", "paths": ["src/**"]}]}
        self.assertEqual(self.codes(log(), task=task, touched=["src/a.py"]), [])

    def test_a_decision_without_an_id_is_an_error_not_a_skip(self) -> None:
        task = {"decisions": [{"grade": "LOCKED", "paths": ["src/**"]}]}
        with self.assertRaises(ValueError):
            self.audit(log(), task=task, touched=["src/a.py"])

    def test_decisions_that_are_not_a_list_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            self.audit(log(), task={"decisions": "D-3"}, touched=["src/a.py"])


class TaskFileTest(unittest.TestCase):
    def parse(self, text: str) -> dict:
        return script.parse_yaml_subset(text)

    def test_the_documented_yaml_shape_parses(self) -> None:
        parsed = self.parse(
            "id: T-0142\n"
            "decisions:\n"
            "  - id: D-3\n"
            "    grade: LOCKED\n"
            '    paths: ["infra/**", "src/session/**"]\n'
            "  - id: D-4\n"
            "    grade: ASSUMED\n"
            "    paths:\n"
            "      - src/db/**\n"
            "      - src/orm/**\n"
            "  - id: D-5\n"
            "    grade: OPEN\n"
        )
        self.assertEqual(parsed["id"], "T-0142")
        self.assertEqual([d["id"] for d in parsed["decisions"]], ["D-3", "D-4", "D-5"])
        self.assertEqual(parsed["decisions"][0]["paths"], ["infra/**", "src/session/**"])
        self.assertEqual(parsed["decisions"][1]["paths"], ["src/db/**", "src/orm/**"])
        self.assertNotIn("paths", parsed["decisions"][2])

    def test_a_nested_list_does_not_swallow_the_next_item(self) -> None:
        # The bug this guards: `paths:` opening a list that then collects the
        # following `- id:` line, silently merging two decisions into one.
        parsed = self.parse(
            "decisions:\n"
            "  - id: D-1\n"
            "    paths:\n"
            "      - a/**\n"
            "  - id: D-2\n"
        )
        self.assertEqual(len(parsed["decisions"]), 2)
        self.assertEqual(parsed["decisions"][0]["paths"], ["a/**"])

    def test_an_empty_nested_list_does_not_swallow_the_next_decision(self) -> None:
        # `paths:` with nothing under it used to adopt the following `- id:`
        # line as a path, which deleted that decision from the silence check.
        parsed = self.parse("decisions:\n  - id: D-1\n    paths:\n  - id: D-2\n")
        self.assertEqual([d["id"] for d in parsed["decisions"]], ["D-1", "D-2"])
        self.assertEqual(parsed["decisions"][0]["paths"], [])

    def test_two_empty_nested_lists_in_a_row_stay_separate(self) -> None:
        parsed = self.parse(
            "decisions:\n  - id: D-1\n    paths:\n  - id: D-2\n    paths:\n  - id: D-3\n")
        self.assertEqual([d["id"] for d in parsed["decisions"]], ["D-1", "D-2", "D-3"])

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        parsed = self.parse("# a task\n\nid: T-1 # trailing\n")
        self.assertEqual(parsed["id"], "T-1")

    def test_an_anchor_is_refused_not_stringified(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("id: &name T-1\n")

    def test_an_alias_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("id: *name\n")

    def test_a_block_scalar_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("id: |\n  T-1\n")

    def test_a_multi_document_file_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("---\nid: T-1\n")

    def test_a_flow_mapping_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("decisions: {id: D-3}\n")

    def test_a_nested_flow_list_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("paths: [[a], [b]]\n")

    def test_tab_indentation_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("decisions:\n\t- id: D-1\n")

    def test_a_list_item_with_no_key_above_it_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("- a\n")

    def test_an_indented_key_with_no_item_open_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.parse("id: T-1\n  nested: 1\n")

    def test_json_and_yaml_agree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            as_json = Path(tmp) / "t.json"
            as_yaml = Path(tmp) / "t.yaml"
            payload = {"id": "T-1", "decisions": [{"id": "D-3", "grade": "LOCKED",
                                                   "paths": ["src/**"]}]}
            as_json.write_text(json.dumps(payload), encoding="utf-8")
            as_yaml.write_text(
                "id: T-1\ndecisions:\n  - id: D-3\n    grade: LOCKED\n"
                '    paths: ["src/**"]\n', encoding="utf-8")
            self.assertEqual(script.load_task(as_json), script.load_task(as_yaml))


class CommandLineTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        git_repo(self.root)
        (self.root / "logs").mkdir()
        (self.root / "infra").mkdir()
        (self.root / "src").mkdir()
        (self.root / "infra" / "compose.yaml").write_text("a\nb\nc\n", encoding="utf-8")
        (self.root / "src" / "store.py").write_text("x\n", encoding="utf-8")
        commit_all(self.root, "🔧 chore: base")
        (self.root / "tasks").mkdir()
        (self.root / "tasks" / "T.json").write_text(json.dumps(
            {"id": "T", "decisions": [{"id": "D-3", "grade": "LOCKED", "paths": ["src/**"]}]}
        ), encoding="utf-8")

    def touch_src(self) -> None:
        (self.root / "src" / "store.py").write_text("x\ny\n", encoding="utf-8")
        commit_all(self.root, "✨ feat: work")

    def cli(self, *args: str):
        return run_script("flag-dont-flip", "log_check.py", *args, cwd=self.root)

    def test_a_clean_log_exits_zero(self) -> None:
        (self.root / "logs" / "T.md").write_text(log(entry()), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_a_failing_log_exits_two(self) -> None:
        (self.root / "logs" / "T.md").write_text(
            log(entry(grade="LOCKED", action="departed")), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("L1", proc.stdout)

    def test_the_silence_check_runs_against_a_real_diff(self) -> None:
        self.touch_src()
        (self.root / "logs" / "T.md").write_text(log(), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".",
                        "--task", "tasks/T.json", "--base", "HEAD~1")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("Q1", proc.stdout)

    def test_the_silence_check_passes_when_the_entry_is_there(self) -> None:
        self.touch_src()
        (self.root / "logs" / "T.md").write_text(log(entry()), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".",
                        "--task", "tasks/T.json", "--base", "HEAD~1")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_base_without_task_is_a_usage_error(self) -> None:
        # A diff with no declared areas cannot decide anything, and exiting 0
        # there would report a silence check that never ran as one that passed.
        (self.root / "logs" / "T.md").write_text(log(entry()), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".", "--base", "HEAD")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--base needs --task", proc.stderr)

    def test_a_missing_log_is_a_usage_error(self) -> None:
        proc = self.cli("--log", "logs/absent.md", "--root", ".")
        self.assertEqual(proc.returncode, 1)

    def test_an_unreadable_base_ref_is_a_usage_error(self) -> None:
        (self.root / "logs" / "T.md").write_text(log(entry()), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".",
                        "--task", "tasks/T.json", "--base", "no-such-ref")
        self.assertEqual(proc.returncode, 1)

    def test_a_malformed_task_file_is_a_usage_error_not_a_pass(self) -> None:
        (self.root / "tasks" / "bad.yaml").write_text("id: &a T\n", encoding="utf-8")
        (self.root / "logs" / "T.md").write_text(log(entry()), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".", "--task", "tasks/bad.yaml")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("outside the supported subset", proc.stderr)

    def test_json_output_carries_the_codes(self) -> None:
        (self.root / "logs" / "T.md").write_text(
            log(entry(grade="LOCKED", action="departed")), encoding="utf-8")
        proc = self.cli("--log", "logs/T.md", "--root", ".", "--json")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertEqual([p["code"] for p in payload["problems"]], ["L1"])

    def test_unknown_flags_exit_two(self) -> None:
        proc = self.cli("--log", "logs/T.md", "--nonsense")
        self.assertEqual(proc.returncode, 2)


class TemplateShapeTest(unittest.TestCase):
    """The template in references/ must pass the checker it documents."""

    def test_the_templates_blocks_parse_and_are_legal(self) -> None:
        reference = (Path(__file__).resolve().parent.parent / "skills" / "flag-dont-flip"
                     / "references" / "log-template.md")
        blocks = script.parse_blocks(reference.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(blocks), 2)
        for line, fields in blocks:
            with self.subTest(line=line):
                self.assertEqual(script.check_schema(line, fields), [])
                self.assertEqual(script.check_legality(line, fields), [])


class KindTest(Fixture):
    """The `kind` axis (contradicted / departed / resolved / blocked) records
    what happened to the decision; `class` records what it says about the
    design process. One of the two is required; both may appear."""

    @staticmethod
    def kind_entry(kind: str, **kwargs: str) -> str:
        # A kind-only entry: `kind` present, `class` absent.
        return entry(extra=f"kind: {kind}\n", **kwargs).replace("class: spec-gap\n", "")

    def test_a_kind_only_entry_passes_schema(self) -> None:
        text = log(self.kind_entry("contradicted", grade="LOCKED", action="halted"))
        self.assertEqual(self.codes(text), [])

    def test_an_entry_with_neither_kind_nor_class_is_s10(self) -> None:
        broken = entry().replace("class: spec-gap\n", "")
        self.assertIn("S10", self.codes(log(broken)))

    def test_an_unknown_kind_is_s11(self) -> None:
        self.assertIn("S11", self.codes(log(entry(extra="kind: pondered\n"))))

    def test_a_close_out_carrying_a_class_is_s12(self) -> None:
        """The pair is a route around the grade table: `resolved` skips it, so
        `class: drift` would record a contradiction and take the attesting
        exemption in one entry. Without `kind` the same fields are L1."""
        text = log(entry(extra="kind: resolved\n", grade="LOCKED",
                         action="decided").replace("class: spec-gap", "class: drift"))
        self.assertIn("S12", self.codes(text))

    def test_a_close_out_carrying_any_class_is_s12(self) -> None:
        for klass in ("drift", "discovery", "spec-gap", "irreducible"):
            with self.subTest(klass=klass):
                text = log(entry(extra="kind: resolved\n", grade="LOCKED",
                                 action="decided").replace("class: spec-gap", f"class: {klass}"))
                self.assertIn("S12", self.codes(text))

    def test_mixed_axes_stay_legal_for_other_kinds(self) -> None:
        """S12 is about close-outs only — `contradicted` and `departed` carry
        both axes, which is what the orthogonality is for."""
        for kind, grade, action in (("contradicted", "LOCKED", "halted"),
                                    ("departed", "ASSUMED", "departed")):
            with self.subTest(kind=kind):
                text = log(entry(extra=f"kind: {kind}\n", grade=grade, action=action))
                self.assertEqual(self.codes(text), [])

    def test_a_resolved_close_out_on_a_lock_passes(self) -> None:
        # The compliance attestation the silence check can be satisfied with:
        # LOCKED area touched, decision honored, action `decided`.
        text = log(self.kind_entry("resolved", grade="LOCKED", action="decided"))
        self.assertEqual(self.codes(text), [])

    def test_a_resolved_close_out_may_not_halt(self) -> None:
        text = log(self.kind_entry("resolved", grade="OPEN", action="halted"))
        self.assertIn("L1", self.codes(text))

    def test_blocked_licenses_halted_on_any_grade(self) -> None:
        text = log(self.kind_entry("blocked", grade="ASSUMED", action="halted"))
        self.assertEqual(self.codes(text), [])

    def test_blocked_work_that_carries_on_is_l1(self) -> None:
        text = log(self.kind_entry("blocked", grade="ASSUMED", action="departed"))
        self.assertIn("L1", self.codes(text))

    def test_a_kind_only_entry_never_counts_as_drift(self) -> None:
        # Drift is a `class` judgement; an entry with no class cannot add to
        # the declared count.
        text = log(self.kind_entry("contradicted", grade="LOCKED", action="halted"), drift=0)
        self.assertEqual(self.codes(text), [])

    def test_a_resolved_close_out_satisfies_the_silence_check(self) -> None:
        task = {"id": "T-0142", "decisions": [
            {"id": "D-3", "grade": "LOCKED", "paths": ["infra/**"]},
        ]}
        close_out = self.kind_entry("resolved", grade="LOCKED", action="decided")
        codes = self.codes(log(close_out), task=task, touched=["infra/compose.yaml"])
        self.assertEqual(codes, [])

    def test_both_axes_together_pass(self) -> None:
        text = log(entry(extra="kind: contradicted\n"))
        self.assertEqual(self.codes(text), [])


class DocumentedExampleTest(unittest.TestCase):
    """The worked example in references/log-template.md must pass this checker.

    Nothing else catches it drifting: the checker does not cross-check an
    entry's `grade` against the task file, and the structural validator does not
    execute examples. A skeleton a reader copies has to be one that validates.
    """

    TEMPLATE = (Path(__file__).resolve().parent.parent / "skills" / "flag-dont-flip"
                / "references" / "log-template.md")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        page = self.TEMPLATE.read_text(encoding="utf-8")
        self.log = re.search(r"````markdown\n(.*?)````", page, re.S).group(1)
        self.task_json = re.search(r"```json\n(.*?)```", page, re.S).group(1)
        self.task_yaml = re.search(r"```yaml\n(.*?)```", page, re.S).group(1)

        git_repo(self.root)
        for cited, lines in (("infra/compose.yaml", 40),
                             ("src/db/migrations/0007_sessions.py", 20)):
            target = self.root / cited
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n" * lines, encoding="utf-8")
        (self.root / "rfcs").mkdir()
        (self.root / "rfcs" / "0014-session-storage.md").write_text("no match here\n",
                                                                   encoding="utf-8")
        (self.root / "log.md").write_text(self.log, encoding="utf-8")
        (self.root / "task.json").write_text(self.task_json, encoding="utf-8")
        (self.root / "task.yaml").write_text(self.task_yaml, encoding="utf-8")
        commit_all(self.root, "🔧 chore: base")
        # Touch both areas the example's entries claim to have touched, so the
        # silence check has something to be silent about.
        for cited in ("infra/compose.yaml", "src/db/migrations/0007_sessions.py"):
            path = self.root / cited
            path.write_text(path.read_text(encoding="utf-8") + "y\n", encoding="utf-8")
        commit_all(self.root, "✨ feat: work")

    def check(self, task: str):
        return run_script("flag-dont-flip", "log_check.py", "--log", "log.md",
                          "--root", ".", "--task", task, "--base", "main",
                          cwd=self.root)

    def test_the_example_validates_against_the_json_task_file(self) -> None:
        proc = self.check("task.json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_example_validates_against_the_yaml_task_file(self) -> None:
        """The two task-file forms are documented as equivalent."""
        proc = self.check("task.yaml")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_two_task_file_forms_declare_the_same_decisions(self) -> None:
        """The page presents JSON and YAML as interchangeable, so a decision
        added to one and not the other makes half the documentation wrong."""
        self.assertEqual(script.load_task(self.root / "task.json"),
                         script.load_task(self.root / "task.yaml"))

    def test_every_graded_decision_the_example_cites_is_declared(self) -> None:
        """The defect this pins: the close-out cited a decision the task file
        graded differently, so the page contradicted its own rule that `grade`
        is copied from the task."""
        declared = {d["id"]: d["grade"] for d in json.loads(self.task_json)["decisions"]}
        cited = re.findall(r"^decision: (\S+)\ngrade: (\S+)$", self.log, re.M)
        self.assertTrue(cited, "the example carries no entries to check")
        for decision, grade in cited:
            with self.subTest(decision=decision):
                if decision == "unlisted":
                    # The one citation with no row by definition — that is what
                    # UNLISTED means, so the task file must not declare it.
                    self.assertEqual(grade, "UNLISTED")
                    self.assertNotIn(decision, declared)
                    continue
                self.assertIn(decision, declared,
                              "the example cites a decision its task file never declares")
                self.assertEqual(grade, declared[decision])


if __name__ == "__main__":
    unittest.main()
