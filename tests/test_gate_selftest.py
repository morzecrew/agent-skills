"""Tests for drift-to-gate/scripts/gate_selftest.py.

A tool that audits gates has to survive its own rule: every check here is shown
firing on the shape it targets AND staying quiet on the honest version of the
same code, because a checker stuck in either position gets switched off.
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from support import load_script, run_script

gs = load_script("drift-to-gate", "gate_selftest.py")


class AuditCase(unittest.TestCase):

    def write(self, source: str, name: str = "sample.py") -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / name
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def checks(self, findings) -> list[str]:
        return [f["check"] for f in findings]

    def audit_tests(self, source: str, **kwargs):
        return gs.run([], [self.write(source)], blocking=gs.BLOCKING_WORDS,
                      passing=gs.PASSING_WORDS, **{"min_blocking": 1, **kwargs})

    def audit_gate(self, source: str):
        return gs.run([self.write(source)], [], blocking=gs.BLOCKING_WORDS,
                      passing=gs.PASSING_WORDS, min_blocking=1)


class TestRubberStamp(AuditCase):

    BOTH = '''
        import unittest

        class T(unittest.TestCase):
            def test_it_passes(self):
                self.assertEqual(gate()["verdict"], "OK")

            def test_it_refuses(self):
                self.assertEqual(gate()["verdict"], "REFUSE")
    '''

    def test_a_suite_that_never_asserts_a_refusal_is_flagged(self):
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "OK")

                def test_b(self):
                    self.assertEqual(gate()["verdict"], "PASS")
        ''')
        self.assertIn("rubber-stamp", self.checks(findings))

    def test_a_suite_proving_both_directions_is_clean(self):
        self.assertEqual(self.audit_tests(self.BOTH), [])

    def test_a_suite_that_never_asserts_a_pass_is_flagged(self):
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "REFUSE")

                def test_b(self):
                    self.assertEqual(gate()["verdict"], "BLOCKED")
        ''')
        self.assertIn("never-passes", self.checks(findings))
        self.assertNotIn("rubber-stamp", self.checks(findings))

    def test_prose_is_not_evidence(self):
        """A docstring saying the gate must not fail would otherwise read as
        proof that the gate can refuse — the exact confusion this removes."""
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    """This must not FAIL, and must never REFUSE anything."""
                    # BLOCKED is mentioned here too, in a comment
                    self.assertEqual(gate()["verdict"], "OK")
        ''')
        self.assertIn("rubber-stamp", self.checks(findings))

    def test_assert_raises_counts_as_a_refusal(self):
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "OK")

                def test_b(self):
                    with self.assertRaises(ValueError):
                        gate(None)
        ''')
        self.assertEqual(findings, [])

    def test_a_non_zero_exit_code_counts_as_a_refusal(self):
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(run().returncode, 0)

                def test_b(self):
                    self.assertEqual(run().returncode, 1)
        ''')
        self.assertEqual(findings, [])

    def test_a_bare_number_is_not_an_exit_code(self):
        """`assertEqual(len(rows), 1)` must not read as a proof of refusal."""
        findings = self.audit_tests('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(len(gate()["rows"]), 1)
                    self.assertEqual(gate()["verdict"], "OK")
        ''')
        self.assertIn("rubber-stamp", self.checks(findings))

    def test_min_blocking_raises_the_bar(self):
        findings = self.audit_tests(self.BOTH, min_blocking=2)
        self.assertIn("rubber-stamp", self.checks(findings))
        self.assertIn("1 of which", findings[0]["message"])

    def test_a_module_with_no_tests_is_not_judged(self):
        self.assertEqual(self.audit_tests("value = 1\n"), [])


class TestStrandedEntrypoint(AuditCase):

    def test_an_entrypoint_above_later_classes_is_flagged(self):
        """One such file ran 12 tests, printed OK, and skipped 13."""
        findings = self.audit_tests('''
            import unittest

            class Early(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "OK")

                def test_b(self):
                    self.assertEqual(gate()["verdict"], "REFUSE")

            if __name__ == "__main__":
                unittest.main()

            class Late(unittest.TestCase):
                def test_c(self):
                    self.assertEqual(gate()["verdict"], "REFUSE")
        ''')
        self.assertIn("stranded-tests", self.checks(findings))
        stranded = next(f for f in findings if f["check"] == "stranded-tests")
        self.assertIn("'Late'", stranded["message"])

    def test_an_entrypoint_at_the_bottom_is_clean(self):
        self.assertEqual(self.audit_tests(TestRubberStamp.BOTH + '''
            if __name__ == "__main__":
                unittest.main()
        '''), [])


class TestSwallowedFailure(AuditCase):

    def test_a_broad_except_that_passes_is_flagged(self):
        findings = self.audit_gate('''
            def gate(rows):
                out = []
                for row in rows:
                    try:
                        out.append(parse(row))
                    except Exception:
                        pass
                return out
        ''')
        self.assertIn("swallowed-failure", self.checks(findings))
        self.assertIn("not a source that returned nothing", findings[0]["message"])

    def test_a_broad_except_that_returns_is_flagged_differently(self):
        findings = self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except Exception:
                    return {}
        ''')
        self.assertIn("cannot tell from a clean result", findings[0]["message"])

    def test_a_bare_except_is_flagged(self):
        findings = self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except:
                    return None
        ''')
        self.assertIn("swallowed-failure", self.checks(findings))

    def test_re_raising_is_not_swallowing(self):
        self.assertEqual(self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except Exception as exc:
                    raise RuntimeError(path) from exc
        '''), [])

    def test_recording_a_failing_verdict_is_not_swallowing(self):
        self.assertEqual(self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except Exception as exc:
                    return {"verdict": "REFUSE", "detail": str(exc)}
        '''), [])

    def test_a_narrow_except_is_not_flagged(self):
        self.assertEqual(self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except FileNotFoundError:
                    return None
        '''), [])

    def test_a_tuple_containing_exception_is_still_broad(self):
        findings = self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except (OSError, Exception):
                    return None
        ''')
        self.assertIn("swallowed-failure", self.checks(findings))


class TestUnwiredVerdict(AuditCase):

    def test_a_cli_that_can_never_exit_non_zero_is_flagged(self):
        findings = self.audit_gate('''
            import sys

            def main():
                print(verdict())
                return 0

            if __name__ == "__main__":
                sys.exit(main())
        ''')
        self.assertIn("unwired-verdict", self.checks(findings))

    def test_a_non_zero_return_is_wiring(self):
        self.assertEqual(self.audit_gate('''
            import sys

            def main():
                print(verdict())
                return 1 if broken() else 0

            if __name__ == "__main__":
                sys.exit(main())
        '''), [])

    def test_an_entrypoint_delegating_elsewhere_is_not_judged(self):
        """`main` is imported, so this file's exit code is decided in another
        one. Inventing a finding here is how a checker gets switched off."""
        self.assertEqual(self.audit_gate('''
            import sys
            from gate import main

            if __name__ == "__main__":
                sys.exit(main())
        '''), [])

    def test_a_dispatch_table_of_exit_codes_is_wiring(self):
        self.assertEqual(self.audit_gate('''
            import sys

            def main():
                sys.exit({"GO": 0, "HOLD": 1, "REFUSE": 2}[verdict()])

            if __name__ == "__main__":
                main()
        '''), [])

    def test_a_library_without_an_entrypoint_is_not_judged(self):
        self.assertEqual(self.audit_gate('''
            def gate():
                return {"verdict": "OK"}
        '''), [])


class TestRobustness(AuditCase):

    def test_a_file_that_does_not_parse_is_reported_not_raised(self):
        findings = gs.run([self.write("def gate(:\n")], [],
                          blocking=gs.BLOCKING_WORDS, passing=gs.PASSING_WORDS,
                          min_blocking=1)
        self.assertEqual(self.checks(findings), ["unreadable"])

    def test_a_missing_file_is_reported_not_raised(self):
        findings = gs.run([Path("/nonexistent/gate.py")], [],
                          blocking=gs.BLOCKING_WORDS, passing=gs.PASSING_WORDS,
                          min_blocking=1)
        self.assertEqual(self.checks(findings), ["unreadable"])

    def test_render_names_every_finding(self):
        findings = self.audit_gate('''
            def gate(path):
                try:
                    return load(path)
                except Exception:
                    return {}
        ''')
        rendered = gs.render(findings)
        self.assertIn("swallowed-failure", rendered)
        self.assertIn("1 finding(s)", rendered)

    def test_render_says_so_when_clean(self):
        self.assertIn("clean", gs.render([]))


class TestCommandLine(unittest.TestCase):

    def write(self, source: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "sample.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return path

    def run_gs(self, *args):
        return run_script("drift-to-gate", "gate_selftest.py", *args)

    def test_findings_exit_one(self):
        path = self.write('''
            def gate(path):
                try:
                    return load(path)
                except Exception:
                    return {}
        ''')
        proc = self.run_gs("--gate", str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("swallowed-failure", proc.stdout)

    def test_a_clean_gate_exits_zero(self):
        path = self.write('''
            def gate(path):
                return {"verdict": "OK"}
        ''')
        proc = self.run_gs("--gate", str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_json_output_is_machine_readable(self):
        path = self.write('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "OK")
        ''')
        proc = self.run_gs("--tests", str(path), "--json")
        self.assertEqual(json.loads(proc.stdout)[0]["check"], "rubber-stamp")

    def test_a_project_vocabulary_can_be_supplied(self):
        """A shop whose refusal is spelled some other way must be able to say
        so, rather than allowlisting itself out of the check."""
        path = self.write('''
            import unittest

            class T(unittest.TestCase):
                def test_a(self):
                    self.assertEqual(gate()["verdict"], "OK")

                def test_b(self):
                    self.assertEqual(gate()["verdict"], "NAK")
        ''')
        self.assertEqual(self.run_gs("--tests", str(path)).returncode, 1)
        proc = self.run_gs("--tests", str(path), "--blocking", "nak,halt")
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_at_least_one_path_is_required(self):
        proc = self.run_gs()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--gate", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
