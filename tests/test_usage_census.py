"""Tests for less-code-same-behavior/scripts/usage_census.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_script, run_script

script = load_script("less-code-same-behavior", "usage_census.py")


class CensusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src" / "pkg").mkdir(parents=True)
        (self.root / "tests").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def census(self, symbol: str, internal: list[str] | None = None) -> dict:
        return script.census(self.root, symbol, internal or [])

    def test_attribute_access_is_not_missed(self):
        # The false positive that produced the skill's rule: a from-import grep
        # finds nothing, and the symbol looks dead while a live call sits behind
        # `module.symbol(...)`.
        self.write("src/pkg/engine.py", "def run_coverage(x):\n    return x\n")
        self.write("src/pkg/__init__.py", "from . import engine\nrun_coverage = engine.run_coverage\n")
        self.write("src/pkg/harness.py", "from . import engines\n\ndef go():\n    return engines.run_coverage(1)\n")

        result = self.census("run_coverage")
        kinds = result["counts"]["byKind"]
        self.assertGreaterEqual(kinds.get("attribute", 0), 1, "attribute access must be counted")
        self.assertGreaterEqual(kinds.get("definition", 0), 1)
        self.assertGreater(result["counts"]["total"], 1, "not dead")

    def test_facade_assignment_records_the_attribute_usage_too(self):
        # Regression: `symbol = module.symbol` counted only as a definition,
        # hiding the RHS usage that proves the symbol is reachable.
        self.write("src/pkg/mod.py", "def helper():\n    return 1\n")
        self.write("src/pkg/__init__.py", "from . import mod\nhelper = mod.helper\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertGreaterEqual(kinds.get("attribute", 0), 1)

    def test_async_def_is_a_definition(self):
        self.write("src/pkg/a.py", "async def fetch():\n    return 1\n")
        kinds = self.census("fetch")["counts"]["byKind"]
        self.assertEqual(kinds.get("definition", 0), 1, kinds)

    def test_js_declarations_are_recognized_as_declarations(self):
        # Regression: const/let/var were absent from the declaration set, so a
        # real JS declaration could never be an inference source while a plain
        # assignment elsewhere could.
        self.write("src/pkg/a.js", "const helper = () => 1;\n")
        self.assertIn("src/pkg/a.js", self.census("helper")["declarations"])

    def test_absent_symbol_reports_nothing(self):
        self.write("src/pkg/a.py", "def other():\n    return 1\n")
        result = self.census("run_coverage")
        self.assertEqual(result["counts"]["total"], 0)

    def test_internal_vs_external_split(self):
        self.write("src/pkg/thing.py", "def helper():\n    return 1\n")
        self.write("src/pkg/user.py", "from .thing import helper\n\nhelper()\n")
        self.write("tests/test_thing.py", "from src.pkg.thing import helper\n\nhelper()\n")

        result = self.census("helper", internal=["src/"])
        self.assertGreater(result["counts"]["internalUsage"], 0)
        self.assertGreater(result["counts"]["externalUsage"], 0)

    def test_standalone_reference_is_not_an_import(self):
        # Regression: a bare line holding just the symbol was classified as a
        # from-import, corrupting the per-pattern census.
        self.write("src/pkg/a.py", "def thing():\n    return 1\n")
        self.write("src/pkg/b.py", "value = [\n]\nthing\n")
        kinds = self.census("thing")["counts"]["byKind"]
        self.assertNotIn("from-import", kinds, kinds)

    def test_aliased_import_list_member(self):
        pats = script.build_patterns("helper")
        self.assertEqual(script.classify("    helper as h,", pats, True), "from-import")

    def test_string_reference_counted(self):
        self.write("src/pkg/reg.py", "def handler():\n    return 1\n")
        self.write("config/app.py", 'ENTRYPOINT = "handler"\n')
        self.assertGreaterEqual(self.census("handler")["counts"]["byKind"].get("string", 0), 1)

    def test_internal_prefixes_are_deduplicated(self):
        self.write("src/pkg/a.py", "def dup():\n    return 1\n")
        self.write("src/pkg/b.py", "dup = 2\n")
        prefixes = self.census("dup")["internalPrefixes"]
        self.assertEqual(len(prefixes), len(set(prefixes)))

    def test_binary_and_oversize_files_are_skipped(self):
        self.write("src/pkg/a.py", "def token():\n    return 1\n")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n token(")
        files = {hit["file"] for hit in self.census("token")["hits"]}
        self.assertNotIn("assets/logo.png", files)

    def test_exit_code_three_when_unreferenced(self):
        self.write("src/pkg/a.py", "x = 1\n")
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "nowhere_symbol", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("dynamic dispatch", result.stdout)

    def test_exit_code_zero_when_used(self):
        self.write("src/pkg/a.py", "def present():\n    return 1\n")
        self.write("src/pkg/b.py", "from .a import present\n\npresent()\n")
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "present", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 0)

    def test_definition_only_symbol_is_a_deletion_candidate(self):
        # Regression: exit 3 documents "no usage beyond its own definition", but
        # the status was based on the total, which counts the definition itself.
        self.write("src/pkg/a.py", "def present():\n    return 1\n")
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "present", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 3)

    def test_rejects_non_identifier(self):
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "mod.attr", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
