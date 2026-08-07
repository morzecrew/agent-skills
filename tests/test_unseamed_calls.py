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

    def test_comments_are_dropped(self):
        kept = script.strip_noise(["# time.time()", "// Date.now()", "x = 1"])
        self.assertEqual([text for _, text in kept], ["x = 1"])

    def test_directive_exempts_a_line(self):
        kept = script.strip_noise(["t = time.time()  # allow-unseamed: real clock on purpose"])
        self.assertEqual(kept, [])

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

    def test_other_languages(self):
        self.write("web/app.js", "const t = Date.now();\nconst r = Math.random();\n")
        self.write("svc/main.go", "t := time.Now()\n")
        js = self.scan(languages=["js"])
        self.assertEqual(js["counts"]["leaks"], 2)
        go = self.scan(languages=["go"])
        self.assertEqual(go["counts"]["leaks"], 1)

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
