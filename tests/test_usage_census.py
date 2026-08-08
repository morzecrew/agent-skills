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

    def test_root_declaration_does_not_mark_every_file_internal(self):
        # Regression: representing the scan root as "" made startswith("") true
        # for every path, silently zeroing externalUsage.
        self.write("root.py", "def helper():\n    return 1\n")
        self.write("pkg/a.py", "helper = 2\n")
        self.write("other/b.py", "from root import helper\n\nhelper()\n")
        result = self.census("helper")
        self.assertNotIn("", result["internalPrefixes"])
        self.assertGreater(result["counts"]["externalUsage"], 0)

    def test_sibling_directory_sharing_a_prefix_is_external(self):
        # Regression: a raw string prefix made `--internal pkg` swallow
        # `pkg2/`, scoring external usage as internal — and that split is what
        # the shim-or-delete decision turns on.
        self.write("pkg/thing.py", "def helper():\n    return 1\n")
        self.write("pkg/inside.py", "from .thing import helper\n\nhelper()\n")
        self.write("pkg2/outside.py", "from pkg.thing import helper\n\nhelper()\n")
        result = self.census("helper", internal=["pkg"])
        scopes = {h["file"]: h["scope"] for h in result["hits"]}
        self.assertEqual(scopes["pkg2/outside.py"], "external")
        self.assertEqual(scopes["pkg/inside.py"], "internal")
        self.assertGreater(result["counts"]["externalUsage"], 0)

    def test_scan_root_prefix_marks_everything_internal(self):
        # Regression: `--internal .` reduced to the empty string and marked
        # every hit external, inverting the split it was asked to define.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "from .a import helper\n\nhelper()\n")
        for prefix in (".", "./"):
            with self.subTest(prefix=prefix):
                counts = self.census("helper", internal=[prefix])["counts"]
                self.assertGreater(counts["internalUsage"], 0)
                self.assertEqual(counts["externalUsage"], 0)

    def test_prefix_matches_with_or_without_a_trailing_slash(self):
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "from .a import helper\n\nhelper()\n")
        for prefix in ("src", "src/", "./src"):
            with self.subTest(prefix=prefix):
                result = self.census("helper", internal=[prefix])
                self.assertGreater(result["counts"]["internalUsage"], 0)
                self.assertEqual(result["counts"]["externalUsage"], 0)

    def test_repository_tracking_nothing_is_refused_not_walked(self):
        # Regression: an empty `git ls-files` fell through to the filesystem
        # walk, scanning the ignored files tracked mode promised to skip — and
        # reporting from an unscanned tree would call live symbols deletable.
        from support import git_repo

        git_repo(self.root)
        (self.root / ".gitignore").write_text("ignored/\n")
        self.write("ignored/vendor.py", "def helper():\n    return 1\n")
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "helper", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("no tracked files", result.stderr)

    def test_go_receiver_method_is_a_definition(self):
        # Regression: `func (r *Runtime) Helper()` scored as a call, so the
        # declaration counted as usage of itself and an unused method could
        # never reach the exit-3 deletion candidate this tool exists to find.
        self.write("src/pkg/runtime.go", "func (r *Runtime) Helper() error {\n\treturn nil\n}\n")
        kinds = self.census("Helper")["counts"]["byKind"]
        self.assertEqual(kinds.get("definition", 0), 1, kinds)
        self.assertNotIn("call", kinds, kinds)

    def test_unused_go_method_is_a_deletion_candidate(self):
        self.write("src/pkg/runtime.go", "func (r *Runtime) Helper() error {\n\treturn nil\n}\n")
        result = run_script(
            "less-code-same-behavior", "usage_census.py", "Helper", "--root", str(self.root)
        )
        self.assertEqual(result.returncode, 3, result.stdout)

    def test_js_function_declaration_is_a_definition(self):
        for source in ("function Helper() {}", "async function Helper() {}", "export function Helper() {}"):
            with self.subTest(source=source):
                self.write("src/pkg/a.js", source + "\n")
                kinds = self.census("Helper")["counts"]["byKind"]
                self.assertEqual(kinds.get("definition", 0), 1, kinds)

    def test_comment_mentions_are_not_usage(self):
        # Regression: a symbol named only in comments counted as a reference,
        # producing the false not-dead verdict the tool exists to prevent.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "# helper is dead, remove it\nx = 1\n")
        self.write("src/pkg/c.js", "// helper()\nconst y = 2;\n")
        result = self.census("helper")
        self.assertEqual(result["counts"]["byKind"].get("comment", 0), 2, result["counts"])
        self.assertEqual(result["counts"]["internalUsage"] + result["counts"]["externalUsage"], 0)

    def test_marker_inside_a_string_does_not_truncate_the_line(self):
        # The call must sit on the same line as the string holding the marker:
        # on its own line it survives even a quote-unaware truncator, and the
        # test would pass without exercising the thing it names.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", 'value = call("#nope") or helper()\n')
        self.assertGreaterEqual(self.census("helper")["counts"]["byKind"].get("call", 0), 1)

    def test_block_comment_mentions_are_not_usage(self):
        # Regression: /* helper */ reached classify() and counted as a live
        # reference, so a dead symbol named in one dodged the exit-3 verdict.
        self.write("src/pkg/a.js", "function helper() { return 1; }\n")
        self.write("src/pkg/b.js", "/* helper() is gone */\nconst x = 1;\n")
        self.write("src/pkg/c.js", "/*\n * helper is described here\n */\nconst y = 2;\n")
        result = self.census("helper")
        self.assertEqual(result["counts"]["internalUsage"] + result["counts"]["externalUsage"], 0,
                         result["counts"])

    def test_a_block_opener_inside_a_line_comment_does_not_swallow_the_file(self):
        # Regression: block comments were scanned before line comments, so a
        # `/*` sitting inside a `// …` comment opened a block that ran to the
        # end of the file — and every live reference below it went uncounted,
        # which is the false-dead verdict that ends in a delete.
        self.write("src/pkg/a.js", "function helper() { return 1; }\n")
        self.write("src/pkg/b.js", "// see /* the note above\nhelper();\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertGreaterEqual(kinds.get("call", 0), 1, kinds)

    def test_single_quoted_string_protects_a_comment_marker(self):
        # Regression: the lifetime fix made `'` never open a string, but
        # Python, JavaScript and PHP quote ordinary strings with it — so a `#`
        # or `//` *inside* one truncated the line and dropped the live call
        # after it, which is the same false-dead verdict from the other side.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "value = call('#nope') or helper()\n")
        self.write("src/pkg/c.js", "const s = '// nope'; helper();\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertGreaterEqual(kinds.get("call", 0), 2, kinds)

    def test_a_python_comment_is_still_stripped(self):
        # The control for the above: `'` opening strings must not stop real
        # line comments being removed.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "x = 1  # helper is dead, remove it\n")
        counts = self.census("helper")["counts"]
        self.assertEqual(counts["internalUsage"] + counts["externalUsage"], 0, counts)

    def test_rust_lifetimes_do_not_suppress_comment_stripping(self):
        # Regression: `'a` opened a quote that never closed, so the rest of
        # the line counted as string content and a block comment after it went
        # unstripped — its mentions then scored as live usage.
        self.write("src/pkg/a.rs", "pub fn helper() -> u32 { 1 }\n")
        self.write("src/pkg/b.rs", "fn take<'a>(x: &str) {} /* helper is described here */\n")
        self.write("src/pkg/c.rs", "'outer: loop { /* helper */ break 'outer; }\n")
        counts = self.census("helper")["counts"]
        self.assertEqual(counts["internalUsage"] + counts["externalUsage"], 0, counts)

    def test_a_quote_inside_a_character_literal_does_not_open_a_string(self):
        # The literal has to contain a quote character for this to bite: if
        # `'"'` is not consumed as a unit, the inner `"` opens a string that
        # runs to the end of the line and hides the comment behind it, so the
        # commented-out mention counts as live.
        self.write("src/pkg/a.rs", "pub fn helper() -> u32 { 1 }\n")
        self.write("src/pkg/b.rs", "let q = '\"'; /* helper */\n")
        counts = self.census("helper")["counts"]
        self.assertEqual(counts["internalUsage"] + counts["externalUsage"], 0, counts)

    def test_generator_declaration_without_a_space_is_a_definition(self):
        self.write("src/pkg/a.js", "function*helper() { yield 1; }\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertEqual(kinds.get("definition", 0), 1, kinds)
        self.assertNotIn("call", kinds, kinds)

    def test_code_after_a_block_comment_on_one_line_still_counts(self):
        self.write("src/pkg/a.js", "function helper() { return 1; }\n")
        self.write("src/pkg/b.js", "/* note */ helper();\n")
        self.assertGreaterEqual(self.census("helper")["counts"]["byKind"].get("call", 0), 1)

    def test_python_floor_division_is_not_read_as_a_comment(self):
        # `//` is a comment in JS but floor division in Python; stripping it
        # everywhere would drop a real reference.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "n = total // helper\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertNotIn("comment", kinds, kinds)

    def test_right_hand_side_of_a_definition_is_recorded(self):
        # Regression: first match wins, so a definition line stopped there and
        # the call on its right-hand side was lost.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "from .a import helper\n\nhelper = wrap(helper())\n")
        kinds = self.census("helper")["counts"]["byKind"]
        self.assertGreaterEqual(kinds.get("call", 0), 1, kinds)

    def test_import_list_member_beside_neighbours(self):
        # Regression: only a lone symbol on its own line counted as an import.
        pats = script.build_patterns("helper")
        for line in ("    helper, other,", "    other, helper", "    helper as h, other,"):
            with self.subTest(line=line):
                self.assertEqual(script.classify(line, pats, True), "from-import")

    def test_non_ascii_tracked_paths_are_not_skipped(self):
        # Regression: git C-quotes such names ("caf\303\251.py") unless -z is
        # passed. The quoted name resolved to nothing, so the file was skipped
        # in silence — and a symbol referenced only there read as unused.
        from support import commit_all, git_repo

        git_repo(self.root)
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/café.py", "from .a import helper\n\nhelper()\n")
        commit_all(self.root, "add a non-ascii filename")
        result = self.census("helper")
        files = {hit["file"] for hit in result["hits"]}
        self.assertIn("src/pkg/café.py", files, files)
        self.assertGreater(result["counts"]["internalUsage"] + result["counts"]["externalUsage"], 0)

    def test_recorded_paths_are_posix(self):
        # The scope tests split on "/", so a platform separator in the stored
        # path would break the internal/external split.
        self.write("src/pkg/a.py", "def helper():\n    return 1\n")
        self.write("src/pkg/b.py", "from .a import helper\n\nhelper()\n")
        for hit in self.census("helper")["hits"]:
            self.assertNotIn("\\", hit["file"])
            self.assertIn("/", hit["file"])

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
