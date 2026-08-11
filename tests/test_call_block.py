"""Tests for decide-before-you-look/scripts/call_block.py.

The load-bearing check is arithmetic (C4): an 80% interval wider than the
decision band means the run cannot resolve anything. Everything else is
presence, and presence checks are only worth having if they cannot be
satisfied by a placeholder.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import git, git_repo, load_script, run_script

cb = load_script("decide-before-you-look", "call_block.py")

COMPLETE = """\
# CALL BLOCK — prefetch planner p99 — 2024-04-02T09:00Z

1. **Metric, with units:** p99 request latency, milliseconds
2. **Predicted number:** 140
3. **80% interval:** [120, 165]
4. **P(survives):** 0.6
5. **Likeliest reason this prediction is wrong:** the batching window collides with the
   existing readahead, so the two prefetchers queue behind each other
6. **Artifact on disk that could answer this without the run:** none —
   the traces record hit rate but never per-request latency

## Decision band

- **ALIVE** below 150ms, **DEAD** above 240ms
- **Band:** [150, 240]
"""


def codes(findings, level=None) -> list[str]:
    return [f["check"] for f in findings if level is None or f["level"] == level]


class TestCompleteBlock(unittest.TestCase):

    def test_a_complete_block_has_no_findings(self):
        self.assertEqual(cb.check(COMPLETE), [])

    def test_every_field_is_parsed(self):
        fields = cb.parse(COMPLETE)
        self.assertEqual(set(fields), set(cb.REQUIRED))
        self.assertEqual(fields["prediction"], "140")
        self.assertEqual(fields["probability"], "0.6")

    def test_a_heading_naming_a_field_does_not_consume_it(self):
        """`## Decision band` names the field and carries no value. Recording
        it masked the real line below and reported the field as missing while
        it sat in the document."""
        self.assertEqual(cb.parse(COMPLETE)["band"], "[150, 240]")

    def test_an_empty_labelled_line_does_not_consume_the_real_one(self):
        """The heading case above is caught by having no separator at all. This
        is the shape that needs the empty-value guard: a label WITH a colon and
        nothing after it, sitting above the line that carries the value."""
        text = COMPLETE.replace("## Decision band",
                                "**Decision band:**\n\n### bounds")
        self.assertEqual(cb.parse(text)["band"], "[150, 240]")
        self.assertEqual(codes(cb.check(text), "error"), [])


class TestPresence(unittest.TestCase):

    def drop(self, label: str) -> str:
        return "\n".join(line for line in COMPLETE.splitlines()
                         if label.lower() not in line.lower())

    def test_each_missing_line_is_reported(self):
        for label in ("Metric, with units", "Predicted number", "80% interval",
                      "P(survives)", "Likeliest reason", "Artifact on disk",
                      "Band:"):
            findings = cb.check(self.drop(label))
            self.assertIn("C1", codes(findings), label)

    def test_a_placeholder_artifact_is_not_an_answer(self):
        """This is the line that most often cancels the run, so a deferral
        must not read as a completed block."""
        for placeholder in ("TBD", "todo", "?", "N/A"):
            text = COMPLETE.replace("none —\n   the traces record hit rate but "
                                    "never per-request latency", placeholder)
            self.assertIn("C6", codes(cb.check(text)), placeholder)

    def test_none_with_a_reason_is_a_valid_answer(self):
        self.assertEqual(codes(cb.check(COMPLETE), "error"), [])


class TestProbability(unittest.TestCase):

    def with_p(self, value: str) -> str:
        return COMPLETE.replace("**P(survives):** 0.6", f"**P(survives):** {value}")

    def test_a_probability_outside_zero_to_one_is_rejected(self):
        for value in ("1.4", "-0.2", "60"):
            self.assertIn("C2", codes(cb.check(self.with_p(value))), value)

    def test_a_percentage_is_accepted(self):
        self.assertEqual(codes(cb.check(self.with_p("60%")), "error"), [])

    def test_the_bounds_are_inclusive(self):
        for value in ("0", "1", "0.0", "1.0"):
            self.assertEqual(codes(cb.check(self.with_p(value)), "error"), [], value)

    def test_a_probability_with_no_number_is_rejected(self):
        self.assertIn("C2", codes(cb.check(self.with_p("fairly likely"))))


class TestIntervalArithmetic(unittest.TestCase):
    """C4 — the check that decides whether the run is worth starting."""

    def block(self, interval: str, band: str = "[150, 240]") -> str:
        return (COMPLETE.replace("**80% interval:** [120, 165]",
                                 f"**80% interval:** {interval}")
                        .replace("**Band:** [150, 240]", f"**Band:** {band}"))

    def test_an_interval_wider_than_the_band_is_an_error(self):
        findings = cb.check(self.block("[90, 300]"))
        self.assertIn("C4", codes(findings))
        self.assertIn("cannot resolve anything", findings[0]["message"])

    def test_an_interval_exactly_as_wide_as_the_band_is_an_error(self):
        """Equal width resolves nothing either — the boundary belongs on the
        failing side, or the check passes the case it exists for."""
        self.assertIn("C4", codes(cb.check(self.block("[100, 190]"))))

    def test_a_narrower_interval_passes(self):
        self.assertEqual(codes(cb.check(self.block("[160, 200]")), "error"), [])

    def test_a_reversed_interval_is_read_as_a_range(self):
        self.assertEqual(codes(cb.check(self.block("[165, 120]")), "error"), [])

    def test_an_interval_that_is_not_two_numbers_is_rejected(self):
        for value in ("about 140", "[120]", "[1, 2, 3]"):
            self.assertIn("C3", codes(cb.check(self.block(value))), value)

    def test_a_non_numeric_band_warns_rather_than_passing_silently(self):
        """'not checked' and 'checked and fine' must not look the same."""
        findings = cb.check(self.block("[120, 165]", "above the same-run floor"))
        self.assertEqual(codes(findings, "error"), [])
        self.assertIn("C5", codes(findings, "warn"))

    def test_percent_signs_do_not_change_the_arithmetic(self):
        self.assertIn("C4", codes(cb.check(self.block("[6%, 35%]", "[10%, 20%]"))))


class TestPrecedence(unittest.TestCase):
    """C7 — the git timestamp is the only evidence the call preceded the data."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git_repo(self.root)

    def add(self, name: str, text: str = "x\n") -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", f"add {name}")
        return path

    def test_a_block_committed_before_the_result_passes(self):
        self.add("CALL_BLOCK.md", COMPLETE)
        self.add("RESULT.json")
        self.assertEqual(cb.check_precedence(self.root, Path("CALL_BLOCK.md"),
                                             Path("RESULT.json")), [])

    def test_a_block_committed_after_the_result_is_a_post_registration(self):
        self.add("RESULT.json")
        self.add("CALL_BLOCK.md", COMPLETE)
        findings = cb.check_precedence(self.root, Path("CALL_BLOCK.md"),
                                       Path("RESULT.json"))
        self.assertIn("C7", codes(findings))
        self.assertIn("post-registration", findings[0]["message"])

    def test_a_block_committed_together_with_the_result_is_rejected(self):
        """Same commit is not "before" — and same-second commits are why this
        compares ancestry rather than timestamps."""
        (self.root / "CALL_BLOCK.md").write_text(COMPLETE, encoding="utf-8")
        self.add("RESULT.json")
        findings = cb.check_precedence(self.root, Path("CALL_BLOCK.md"),
                                       Path("RESULT.json"))
        self.assertIn("C7", codes(findings))
        self.assertIn("same commit", findings[0]["message"])

    def test_a_result_that_does_not_exist_yet_is_the_correct_order(self):
        self.add("CALL_BLOCK.md", COMPLETE)
        self.assertEqual(cb.check_precedence(self.root, Path("CALL_BLOCK.md"),
                                             Path("RESULT.json")), [])

    def test_an_uncommitted_block_is_not_a_registration(self):
        self.add("RESULT.json")
        # written only after the result was committed, so `git add -A` in the
        # helper cannot sweep it in — an earlier version of this test committed
        # the block by accident and then asserted it was uncommitted
        (self.root / "CALL_BLOCK.md").write_text(COMPLETE, encoding="utf-8")
        findings = cb.check_precedence(self.root, Path("CALL_BLOCK.md"),
                                       Path("RESULT.json"))
        self.assertIn("C7", codes(findings))
        self.assertIn("not committed", findings[0]["message"])


class TestCommandLine(unittest.TestCase):

    def write(self, text: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "CALL_BLOCK.md"
        path.write_text(text, encoding="utf-8")
        return path

    def run_cb(self, *args):
        return run_script("decide-before-you-look", "call_block.py", *args)

    def test_a_complete_block_exits_zero(self):
        proc = self.run_cb(str(self.write(COMPLETE)))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("can resolve its band", proc.stdout)

    def test_an_unresolvable_block_exits_one(self):
        text = COMPLETE.replace("[120, 165]", "[90, 300]")
        proc = self.run_cb(str(self.write(text)))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("C4", proc.stdout)

    def test_a_warning_alone_does_not_fail(self):
        text = COMPLETE.replace("**Band:** [150, 240]", "**Band:** above the floor")
        proc = self.run_cb(str(self.write(text)))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("warn", proc.stdout)

    def test_a_missing_file_refuses(self):
        proc = self.run_cb("/nonexistent/CALL_BLOCK.md")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REFUSE", proc.stderr)

    def test_json_output_is_machine_readable(self):
        text = COMPLETE.replace("[120, 165]", "[90, 300]")
        proc = self.run_cb(str(self.write(text)), "--json")
        self.assertEqual(json.loads(proc.stdout)[0]["check"], "C4")

    def test_the_template_names_every_required_field(self):
        proc = self.run_cb("--template")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(set(cb.parse(proc.stdout)), set(cb.REQUIRED))

    def test_the_template_is_not_itself_a_valid_registration(self):
        """It carries placeholders, and a placeholder must never validate —
        otherwise the first thing anyone runs teaches them it is done."""
        proc = self.run_cb(str(self.write(cb.TEMPLATE)))
        self.assertEqual(proc.returncode, 1)

    def test_a_path_is_required(self):
        self.assertNotEqual(self.run_cb().returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
