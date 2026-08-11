"""Tests for drift-to-gate/scripts/exception_creep.py.

Each shape is shown firing on the widening it targets and staying quiet on the
ordinary code that resembles it — a diff scanner that cries wolf is deleted, and
its findings go with it.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from support import commit_all, git, git_repo, load_script, run_script

ec = load_script("drift-to-gate", "exception_creep.py")


def diff(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


class ScanCase(unittest.TestCase):

    def checks(self, findings) -> list[str]:
        return [f["check"] for f in findings]


class TestSuppressions(ScanCase):

    def scan_added(self, line: str):
        return ec.scan(diff(f'''
            diff --git a/app.py b/app.py
            --- a/app.py
            +++ b/app.py
            @@ -1,2 +1,3 @@
             import os
            +{line}
             import sys
        '''))

    def test_each_silencer_is_reported(self):
        for line in ("import bad  # noqa: E402",
                     "x = y  # type: ignore[arg-type]",
                     "run(cmd, shell=True)  # nosec",
                     "/* eslint-disable no-eval */",
                     "// @ts-ignore",
                     "#[allow(dead_code)]",
                     "@SuppressWarnings(\"unchecked\")",
                     "@pytest.mark.xfail(reason='flaky')",
                     "@unittest.skip('later')",
                     "def f(): pass  # pylint: disable=missing-docstring"):
            self.assertEqual(self.checks(self.scan_added(line)), ["suppression"], line)

    def test_ordinary_code_is_not_a_silencer(self):
        for line in ("value = ignore_case(name)",
                     "logger.info('skipping empty rows')",
                     "results = [r for r in rows if r.ok]"):
            self.assertEqual(self.scan_added(line), [], line)

    def test_a_removed_silencer_is_not_reported(self):
        """Deleting a suppression is the gate being satisfied, not widened."""
        findings = ec.scan(diff('''
            diff --git a/app.py b/app.py
            --- a/app.py
            +++ b/app.py
            @@ -1,2 +1,1 @@
            -import bad  # noqa: E402
             import sys
        '''))
        self.assertEqual(findings, [])


class TestAllowlists(ScanCase):

    def test_a_new_exemption_collection_is_reported(self):
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            --- a/scan.py
            +++ b/scan.py
            @@ -3,2 +3,3 @@
             import re
            +EXEMPT_PATHS = {"vendor/", "legacy/"}
             PATTERN = re.compile("x")
        '''))
        self.assertEqual(self.checks(findings), ["allowlist-entry"])

    def test_an_entry_appended_to_an_existing_allowlist_is_reported(self):
        """The added line is a bare string with nothing incriminating about it.
        The collection's name lives in the hunk header git appends."""
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            --- a/scan.py
            +++ b/scan.py
            @@ -10,3 +10,4 @@ ALLOWED_IMPORTS = [
                 "os",
            +    "bc_data",  # grading only, see the RFC
                 "sys",
             ]
        '''))
        self.assertEqual(self.checks(findings), ["allowlist-entry"])
        self.assertEqual(findings[0]["line"], 11)

    def test_a_bare_string_in_an_unrelated_hunk_is_not_reported(self):
        findings = ec.scan(diff('''
            diff --git a/menu.py b/menu.py
            --- a/menu.py
            +++ b/menu.py
            @@ -10,3 +10,4 @@ COLOURS = [
                 "red",
            +    "green",
                 "blue",
             ]
        '''))
        self.assertEqual(findings, [])

    def test_ordinary_exception_handling_is_not_an_exemption(self):
        """Pins the vocabulary: "exceptions" plural and `exception_list` are
        allowlist names, bare "exception" is Python. Widen it to the singular
        and every try/except in every diff reports as an exemption — a scanner
        that cries wolf is deleted along with its findings."""
        findings = ec.scan(diff('''
            diff --git a/app.py b/app.py
            --- a/app.py
            +++ b/app.py
            @@ -5,2 +5,5 @@
             def load(path):
            +    try:
            +        return read(path)
            +    except Exception:
            +        raise LoadError(path)
        '''))
        self.assertEqual(findings, [])

    def test_a_plural_exceptions_collection_is_reported(self):
        findings = ec.scan(diff('''
            diff --git a/lint.py b/lint.py
            --- a/lint.py
            +++ b/lint.py
            @@ -1,1 +1,2 @@
             import sys
            +LINT_EXCEPTIONS = {"vendor/legacy.py"}
        '''))
        self.assertEqual(self.checks(findings), ["allowlist-entry"])

    def test_a_known_failures_list_is_reported(self):
        findings = ec.scan(diff('''
            diff --git a/ci.py b/ci.py
            --- a/ci.py
            +++ b/ci.py
            @@ -1,1 +1,2 @@
             import sys
            +KNOWN_FAILURES = ["test_flaky"]
        '''))
        self.assertEqual(self.checks(findings), ["allowlist-entry"])


class TestDeletedAssertions(ScanCase):

    def test_a_removed_assertion_is_reported(self):
        for line in ("    assert findings == []",
                     "        self.assertEqual(verdict, 'REFUSE')",
                     "    expect(result).toEqual(0);",
                     "    ASSERT_EQ(rc, 1);"):
            findings = ec.scan(diff(f'''
                diff --git a/t.py b/t.py
                --- a/t.py
                +++ b/t.py
                @@ -4,2 +4,1 @@
                -{line}
                 return findings
            '''))
            self.assertEqual(self.checks(findings), ["deleted-assertion"], line)

    def test_an_added_assertion_is_not_reported(self):
        findings = ec.scan(diff('''
            diff --git a/t.py b/t.py
            --- a/t.py
            +++ b/t.py
            @@ -4,1 +4,2 @@
            +    assert findings == []
             return findings
        '''))
        self.assertEqual(findings, [])

    def test_a_stripped_blank_context_line_still_advances_the_count(self):
        """A blank context line is a single space; editors and mail transports
        strip it to "". Falling through left the counters behind, so every
        later finding in the hunk was off by one per stripped blank."""
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            --- a/scan.py
            +++ b/scan.py
            @@ -10,4 +10,5 @@ ALLOWED_IMPORTS = [
                 "os",

                 "sys",
            +    "bc_data",
        '''))
        self.assertEqual([f["line"] for f in findings], [13])

    def test_the_reported_line_is_the_old_file_for_a_deletion(self):
        findings = ec.scan(diff('''
            diff --git a/t.py b/t.py
            --- a/t.py
            +++ b/t.py
            @@ -40,3 +7,2 @@
             before()
            -    assert ok
             after()
        '''))
        self.assertEqual(findings[0]["line"], 41)


class TestDiffParsing(ScanCase):

    def test_findings_from_several_files_are_kept_apart(self):
        findings = ec.scan(diff('''
            diff --git a/one.py b/one.py
            --- a/one.py
            +++ b/one.py
            @@ -1,1 +1,2 @@
             import os
            +import bad  # noqa
            diff --git a/two.py b/two.py
            --- a/two.py
            +++ b/two.py
            @@ -1,1 +1,2 @@
             import os
            +ALLOWLIST = ["a"]
        '''))
        self.assertEqual([f["file"] for f in findings], ["one.py", "two.py"])

    def test_a_deleted_file_is_skipped(self):
        findings = ec.scan(diff('''
            diff --git a/gone.py b/gone.py
            deleted file mode 100644
            --- a/gone.py
            +++ /dev/null
            @@ -1,2 +0,0 @@
            -    assert ok
            -ALLOWLIST = []
        '''))
        self.assertEqual(findings, [])

    def test_an_empty_diff_is_clean(self):
        self.assertEqual(ec.scan(""), [])

    def test_a_brand_new_file_is_not_a_widening(self):
        """There was no check there to widen. Scanning new files reported this
        tool's own source forty-four times, which is the shape of a check
        nobody runs twice."""
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            new file mode 100644
            index 0000000..1111111
            --- /dev/null
            +++ b/scan.py
            @@ -0,0 +1,2 @@
            +ALLOWLIST = ["vendor/"]
            +import bad  # noqa
        '''))
        self.assertEqual(findings, [])

    def test_the_next_file_after_a_new_one_is_still_scanned(self):
        findings = ec.scan(diff('''
            diff --git a/new.py b/new.py
            --- /dev/null
            +++ b/new.py
            @@ -0,0 +1,1 @@
            +ALLOWLIST = ["vendor/"]
            diff --git a/old.py b/old.py
            --- a/old.py
            +++ b/old.py
            @@ -1,1 +1,2 @@
             import os
            +EXEMPT_PATHS = ["vendor/"]
        '''))
        self.assertEqual([f["file"] for f in findings], ["old.py"])

    def test_prose_files_are_skipped(self):
        for name in ("docs/policy.md", "NOTES.rst", "readme.TXT"):
            findings = ec.scan(diff(f'''
                diff --git a/{name} b/{name}
                --- a/{name}
                +++ b/{name}
                @@ -1,1 +1,2 @@
                 title
                +We keep an ALLOWLIST of exempt paths.
            '''))
            self.assertEqual(findings, [], name)

    def test_a_comment_about_allowlists_is_not_an_allowlist(self):
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            --- a/scan.py
            +++ b/scan.py
            @@ -1,1 +1,3 @@
             import os
            +# the exempt paths live in config, not here
            +// an allowlist would go here one day
        '''))
        self.assertEqual(findings, [])

    def test_a_suppression_is_still_caught_inside_a_comment(self):
        """Suppressions ARE comments — the comment filter must not swallow the
        one check whose whole subject is comment syntax."""
        findings = ec.scan(diff('''
            diff --git a/app.py b/app.py
            --- a/app.py
            +++ b/app.py
            @@ -1,1 +1,2 @@
             import os
            +# type: ignore
        '''))
        self.assertEqual(self.checks(findings), ["suppression"])

    def test_a_hunk_scoped_name_does_not_leak_into_the_next_hunk(self):
        findings = ec.scan(diff('''
            diff --git a/scan.py b/scan.py
            --- a/scan.py
            +++ b/scan.py
            @@ -10,2 +10,3 @@ ALLOWED_IMPORTS = [
                 "os",
            +    "bc_data",
             ]
            @@ -40,2 +41,3 @@ COLOURS = [
                 "red",
            +    "green",
             ]
        '''))
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0]["line"], 11)

    def test_render_says_so_when_clean(self):
        self.assertIn("clean", ec.render([]))

    def test_an_empty_input_is_genuinely_clean(self):
        self.assertIsNone(ec.unreadable(""))
        self.assertIsNone(ec.unreadable("   \n"))

    def test_a_readable_diff_is_not_called_unreadable(self):
        self.assertIsNone(ec.unreadable(diff('''
            diff --git a/a.py b/a.py
            --- a/a.py
            +++ b/a.py
            @@ -1,1 +1,1 @@
            -x
            +y
        ''')))

    def test_a_combined_merge_diff_refuses_rather_than_reporting_clean(self):
        """The three-column merge format parses to nothing here, and "nothing
        found" would be indistinguishable from the good news."""
        why = ec.unreadable(diff('''
            diff --cc scan.py
            index 111,222..333
            --- a/scan.py
            +++ b/scan.py
            @@@ -1,2 -1,2 +1,3 @@@
            ++ALLOWLIST = ["vendor/"]
        '''))
        self.assertIsNotNone(why)
        self.assertIn("combined", why)

    def test_input_that_is_not_a_diff_at_all_refuses(self):
        why = ec.unreadable("here are my changes: I added an allowlist\n")
        self.assertIsNotNone(why)
        self.assertIn("file headers", why)


class TestGitModes(unittest.TestCase):
    """The default path: read the repository, not a hand-written patch."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git_repo(self.root)
        (self.root / "scan.py").write_text('ALLOWED = ["os"]\nassert ok\n')
        commit_all(self.root, "seed")

    def run_ec(self, *args):
        return run_script("drift-to-gate", "exception_creep.py", *args,
                          cwd=self.root)

    def test_unstaged_changes_are_the_default(self):
        (self.root / "scan.py").write_text('ALLOWED = ["os", "bc_data"]\n')
        proc = self.run_ec()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("allowlist-entry", proc.stdout)
        self.assertIn("deleted-assertion", proc.stdout)

    def test_staged_changes_can_be_scanned(self):
        (self.root / "scan.py").write_text('ALLOWED = ["os"]\nassert ok\nx = 1  # noqa\n')
        git(self.root, "add", "-A")
        proc = self.run_ec("--staged")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("suppression", proc.stdout)

    def test_a_revision_range_can_be_scanned(self):
        (self.root / "scan.py").write_text('ALLOWED = ["os"]\nassert ok\ny = 2  # nosec\n')
        commit_all(self.root, "widen")
        proc = self.run_ec("main~1..main", "--json")
        self.assertEqual(json.loads(proc.stdout)[0]["check"], "suppression")

    def test_a_clean_range_exits_zero(self):
        (self.root / "notes.md").write_text("hello\n")
        commit_all(self.root, "notes")
        proc = self.run_ec("main~1..main")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("clean", proc.stdout)

    def test_an_unreadable_patch_refuses_at_the_command_line(self):
        """`unreadable()` being correct is worth nothing until the CLI acts on
        it — a verdict not wired to an exit code reports and does not refuse.
        Sabotage caught this: the check existed and main() ignored it."""
        combined = diff('''
            diff --cc scan.py
            --- a/scan.py
            +++ b/scan.py
            @@@ -1,2 -1,2 +1,3 @@@
            ++ALLOWLIST = ["vendor/"]
        ''')
        patch = self.root / "merge.diff"
        patch.write_text(combined)
        proc = self.run_ec("--patch", str(patch))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("combined", proc.stderr)
        self.assertNotIn("clean", proc.stdout)

    def test_a_bad_range_refuses_rather_than_reporting_clean(self):
        """Reporting "clean" because git failed is the worst possible answer."""
        proc = self.run_ec("no-such-ref..main")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REFUSE", proc.stderr)

    def test_a_patch_on_stdin_is_accepted(self):
        patch = diff('''
            diff --git a/app.py b/app.py
            --- a/app.py
            +++ b/app.py
            @@ -1,1 +1,2 @@
             import os
            +import bad  # noqa
        ''')
        script = (Path(__file__).resolve().parent.parent / "skills" /
                  "drift-to-gate" / "scripts" / "exception_creep.py")
        proc = subprocess.run(["python3", str(script), "--patch", "-"],
                              input=patch, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("suppression", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
