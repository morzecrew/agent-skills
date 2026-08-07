"""Tests for determinism-by-design/scripts/unseamed_calls.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_script, run_script

script = load_script("determinism-by-design", "unseamed_calls.py")


class StripNoiseTest(unittest.TestCase):
    def test_docstring_prose_is_not_code(self):
        source = [
            "def f():",
            '    """Defaults to time.monotonic() in prose.',
            "",
            "    Also mentions random.random() here.",
            '    """',
            "    return time.monotonic()",
        ]
        kept = script.strip_noise(source)
        self.assertEqual([number for number, _ in kept], [1, 6])

    def test_comments_are_dropped_per_language(self):
        self.assertEqual(
            [t for _, t in script.strip_noise(["# time.time()", "x = 1"], "python")], ["x = 1"]
        )
        self.assertEqual(
            [t for _, t in script.strip_noise(["// Date.now()", "x = 1"], "js")], ["x = 1"]
        )

    def test_hash_is_a_private_field_in_javascript_not_a_comment(self):
        # Regression: language-agnostic prefixes hid real calls in JS private
        # field initializers.
        self.assertEqual(len(script.strip_noise(["#count = Date.now();"], "js")), 1)
        self.assertEqual(script.strip_noise(["#count = 1"], "python"), [])

    def test_directive_exempts_a_line(self):
        kept = script.strip_noise(["t = time.time()  # allow-unseamed: real clock on purpose"])
        self.assertEqual(kept, [])

    def test_directive_must_be_in_a_comment(self):
        # Regression: a bare substring match let a string literal on the same
        # line hide a real leak from the scanner.
        self.assertEqual(script.strip_noise(['t = time.time()  # allow-unseamed: on purpose']), [])
        kept = script.strip_noise(['t = time.time(); label = "allow-unseamed"'])
        self.assertEqual(len(kept), 1, "a string literal must not exempt the line")

    def test_triple_quote_inside_a_string_does_not_swallow_the_file(self):
        # Regression: any line containing the marker toggled docstring state, so
        # a normal string hid every following line from the scanner.
        kept = script.strip_noise(['marker = "he said ...\'\'\' here"', "t = time.time()"])
        self.assertEqual(len(kept), 2, kept)

    def test_trailing_comment_mention_is_not_a_call(self):
        # Regression: a clock name in an inline comment was reported as a leak,
        # so strict mode could fail on prose.
        self.assertEqual(script.strip_noise(["x = 1  # time.time() mentioned"]), [(1, "x = 1")])

    def test_single_line_triple_quote_does_not_toggle(self):
        kept = script.strip_noise(['x = """literal"""', "y = time.time()"])
        self.assertEqual(len(kept), 2)


class ScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def scan(self, languages=("python",), seams=(), allow=None) -> dict:
        return script.scan(
            self.root, list(languages), list(seams),
            script.DEFAULT_ALLOW if allow is None else list(allow),
        )

    def test_detects_each_python_source(self):
        self.write("src/a.py", "import time, random, uuid, os\n")
        self.write("src/clock.py", "t = time.time()\n")
        self.write("src/rng.py", "r = random.random()\n")
        self.write("src/ids.py", "i = uuid.uuid4()\n")
        self.write("src/cfg.py", "v = os.getenv('X')\n")
        self.write("src/nap.py", "time.sleep(1)\n")
        kinds = self.scan()["counts"]["byKind"]
        for kind in ("clock", "random", "uuid", "env", "sleep"):
            self.assertIn(kind, kinds, f"{kind} not detected")

    def test_seam_files_are_reported_separately(self):
        self.write("src/seam/time_source.py", "def now():\n    return time.time()\n")
        without = self.scan()
        self.assertEqual(without["counts"]["leaks"], 1)
        with_seam = self.scan(seams=["src/seam/"])
        self.assertEqual(with_seam["counts"]["leaks"], 0)
        self.assertEqual(with_seam["counts"]["insideSeams"], 1)

    def test_tests_are_allowed_by_default(self):
        self.write("tests/test_thing.py", "import time\nt = time.time()\n")
        self.assertEqual(self.scan()["counts"]["leaks"], 0)
        self.assertEqual(self.scan(allow=[])["counts"]["leaks"], 1)

    def test_allowed_files_counts_files_not_hits(self):
        # Regression: the counter incremented per call, so one file with three
        # exempt calls was reported as three allowed files.
        self.write("tests/test_thing.py", "import time\na = time.time()\nb = time.time()\nc = time.time()\n")
        counts = self.scan()["counts"]
        self.assertEqual(counts["allowedFiles"], 1)
        self.assertEqual(counts["allowedHits"], 3)

    def test_other_languages(self):
        self.write("web/app.js", "const t = Date.now();\nconst r = Math.random();\n")
        self.write("svc/main.go", "t := time.Now()\n")
        js = self.scan(languages=["js"])
        self.assertEqual(js["counts"]["leaks"], 2)
        go = self.scan(languages=["go"])
        self.assertEqual(go["counts"]["leaks"], 1)

    def test_bare_js_date_constructor_is_a_clock_read(self):
        self.write("web/a.js", "const t = Date();\n")
        self.assertEqual(self.scan(languages=["js"])["counts"]["leaks"], 1)

    def test_root_relative_allow_globs(self):
        # Run from a package root, "tests/x.py" has no leading segment for a
        # "*/tests/*" pattern to match.
        self.write("tests/t.py", "import time\nt = time.time()\n")
        self.write("scripts/s.py", "import time\nt = time.time()\n")
        self.assertEqual(self.scan()["counts"]["leaks"], 0)

    def test_every_kind_on_a_line_is_reported(self):
        self.write("src/a.py", "import time, os\nv = os.getenv('X') or time.time()\n")
        kinds = self.scan()["counts"]["byKind"]
        self.assertIn("clock", kinds)
        self.assertIn("env", kinds)

    def test_language_filter_excludes_others(self):
        self.write("web/app.js", "const t = Date.now();\n")
        self.write("src/a.py", "t = time.time()\n")
        self.assertEqual(self.scan(languages=["python"])["counts"]["leaks"], 1)

    def test_clean_codebase_reports_nothing(self):
        self.write("src/a.py", "def add(x, y):\n    return x + y\n")
        self.assertEqual(self.scan()["counts"]["leaks"], 0)

    def test_warn_mode_exits_zero_and_strict_exits_two(self):
        self.write("src/a.py", "import time\nt = time.time()\n")
        warn = run_script(
            "determinism-by-design", "unseamed_calls.py", "--root", str(self.root), "--languages", "python"
        )
        self.assertEqual(warn.returncode, 0)
        self.assertIn("warn mode", warn.stdout)

        strict = run_script(
            "determinism-by-design", "unseamed_calls.py",
            "--root", str(self.root), "--languages", "python", "--strict",
        )
        self.assertEqual(strict.returncode, 2)

    def test_strict_exits_zero_when_clean(self):
        self.write("src/a.py", "x = 1\n")
        result = run_script(
            "determinism-by-design", "unseamed_calls.py",
            "--root", str(self.root), "--languages", "python", "--strict",
        )
        self.assertEqual(result.returncode, 0)

    def test_unknown_language_is_rejected(self):
        result = run_script(
            "determinism-by-design", "unseamed_calls.py", "--root", str(self.root), "--languages", "cobol"
        )
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
