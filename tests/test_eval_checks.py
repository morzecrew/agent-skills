"""Tests for evals/run.py's check evaluation.

The eval harness itself is local-only — it needs an authenticated `claude` CLI,
so CI never runs it. `check_output` is pure, though, and it is what decides
whether a case passed; an inverted assertion getting this wrong would report a
skill as clean while it misfired.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eval_run", REPO / "evals" / "run.py")
script = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = script
spec.loader.exec_module(script)


class CheckOutputTest(unittest.TestCase):
    def passed(self, output: str, checks: list[dict]) -> list[bool]:
        return [ok for _, ok in script.check_output(output, checks)]

    def test_a_present_pattern_passes(self) -> None:
        self.assertEqual(self.passed("guard clause", [{"pattern": "guard"}]), [True])

    def test_a_missing_pattern_fails(self) -> None:
        self.assertEqual(self.passed("nothing here", [{"pattern": "guard"}]), [False])

    def test_absent_passes_when_the_pattern_is_missing(self) -> None:
        self.assertEqual(
            self.passed("nothing here", [{"pattern": "guard", "absent": True}]), [True])

    def test_absent_fails_when_the_pattern_is_present(self) -> None:
        self.assertEqual(
            self.passed("guard clause", [{"pattern": "guard", "absent": True}]), [False])

    def test_absent_false_behaves_like_a_normal_check(self) -> None:
        self.assertEqual(
            self.passed("guard", [{"pattern": "guard", "absent": False}]), [True])

    def test_the_i_flag_is_honored(self) -> None:
        self.assertEqual(self.passed("GUARD", [{"pattern": "guard", "flags": "i"}]), [True])
        self.assertEqual(self.passed("GUARD", [{"pattern": "guard"}]), [False])

    def test_multiline_anchors_work(self) -> None:
        self.assertEqual(self.passed("first\nsecond", [{"pattern": "^second"}]), [True])

    def test_an_absent_check_is_labelled_so_a_reader_can_tell(self) -> None:
        labels = [label for label, _ in script.check_output(
            "x", [{"pattern": "a"}, {"pattern": "b", "absent": True}])]
        self.assertEqual(labels, ["a", "NOT b"])

    def test_checks_are_reported_in_order(self) -> None:
        results = self.passed("alpha", [{"pattern": "alpha"}, {"pattern": "beta"}])
        self.assertEqual(results, [True, False])


class CaseFileTest(unittest.TestCase):
    """Every shipped case file must be loadable and name a skill that exists."""

    def test_every_case_file_is_valid(self) -> None:
        import json
        cases_dir = REPO / "evals" / "cases"
        files = sorted(cases_dir.glob("*.json"))
        self.assertTrue(files, "no eval case files")
        for path in files:
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                skill = data["skill"]
                self.assertTrue((REPO / "skills" / skill).is_dir(),
                                f"{path.name} names skill {skill!r}, which does not exist")
                self.assertEqual(path.stem, skill, "file name must match its skill")
                ids = [case["id"] for case in data["cases"]]
                self.assertEqual(len(ids), len(set(ids)), "duplicate case ids")
                for case in data["cases"]:
                    self.assertIn(case.get("mode", "explicit"), {"explicit", "implicit"})
                    self.assertTrue(case["checks"], f"case {case['id']} asserts nothing")
                    for chk in case["checks"]:
                        script.re.compile(chk["pattern"])


if __name__ == "__main__":
    unittest.main()
