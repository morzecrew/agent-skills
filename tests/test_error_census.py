"""Tests for error-taxonomy/scripts/error_census.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_script, run_script

script = load_script("error-taxonomy", "error_census.py")


class NormalizeMessageTest(unittest.TestCase):
    def test_interpolations_collapse_to_one_family(self):
        self.assertEqual(
            script.normalize_message("unknown field {name}"),
            script.normalize_message("unknown field {other!r}"),
        )

    def test_numbers_and_quoted_values_collapse(self):
        self.assertEqual(
            script.normalize_message("limit 5 exceeds 100"),
            script.normalize_message("limit 9 exceeds 250"),
        )

    def test_case_and_trailing_punctuation_ignored(self):
        self.assertEqual(
            script.normalize_message("Timeout must be positive."),
            script.normalize_message("timeout must be positive"),
        )

    def test_genuinely_different_messages_stay_apart(self):
        self.assertNotEqual(
            script.normalize_message("unknown field {x}"),
            script.normalize_message("unknown table {x}"),
        )


class CensusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def census(self, kinds=(r"exc\.(\w+)",), exclude=()) -> dict:
        return script.census(self.root, ["python"], list(kinds), list(exclude))

    def test_counts_raise_sites_by_kind(self):
        self.write("src/a.py", 'raise exc.validation("limit must be positive")\n')
        self.write("src/b.py", 'raise exc.internal("unreachable")\n')
        result = self.census()
        self.assertEqual(result["counts"]["sites"], 2)
        self.assertEqual(result["counts"]["byKind"], {"validation": 1, "internal": 1})

    def test_same_situation_raised_as_two_kinds_clusters_together(self):
        # The finding a taxonomy sweep exists to make.
        self.write("src/a.py", 'raise exc.configuration("Timeout must be positive")\n')
        self.write("src/b.py", 'raise exc.internal("timeout must be positive")\n')
        families = self.census()["families"]
        family = families["timeout must be positive"]
        self.assertEqual(len(family), 2)
        self.assertEqual({hit["kind"] for hit in family}, {"configuration", "internal"})

    def test_codes_are_collected(self):
        self.write("src/a.py", 'raise exc.precondition("nope", code="query_feature_unsupported")\n')
        result = self.census()
        self.assertEqual(result["counts"]["withCode"], 1)
        self.assertIn("query_feature_unsupported", result["codes"])

    def test_message_on_the_following_line_is_found(self):
        self.write("src/a.py", 'raise exc.validation(\n    "cursor token is malformed"\n)\n')
        families = self.census()["families"]
        self.assertIn("cursor token is malformed", families)

    def test_falls_back_to_the_exception_class_without_kind_patterns(self):
        self.write("src/a.py", 'raise ValueError("bad value")\n')
        self.assertEqual(self.census(kinds=())["counts"]["byKind"], {"ValueError": 1})

    def test_dotted_exception_classes_are_shortened(self):
        self.write("src/a.py", 'raise mod.CustomError("bad")\n')
        self.assertIn("CustomError", self.census(kinds=())["counts"]["byKind"])

    def test_comments_are_ignored(self):
        self.write("src/a.py", '# raise exc.internal("not real")\nx = 1\n')
        self.assertEqual(self.census()["counts"]["sites"], 0)

    def test_trailing_comment_is_not_a_raise_site(self):
        self.write("src/a.py", 'x = 1  # raise exc.internal("not real")\n')
        self.assertEqual(self.census()["counts"]["sites"], 0)

    def test_exclude_glob_skips_paths(self):
        self.write("src/a.py", 'raise exc.internal("real")\n')
        self.write("tests/test_a.py", 'raise exc.internal("boom")\n')
        self.assertEqual(self.census()["counts"]["sites"], 2)
        self.assertEqual(self.census(exclude=["tests/*"])["counts"]["sites"], 1)

    def test_go_and_rust_kinds_are_captured(self):
        self.write("svc/a.go", 'return fmt.Errorf("bad input")\n')
        self.write("svc/b.rs", 'bail!("bad input");\n')
        go = script.census(self.root, ["go"], [], [])
        # Dotted names are shortened, as they are for Python classes.
        self.assertIn("Errorf", go["counts"]["byKind"])
        rust = script.census(self.root, ["rust"], [], [])
        self.assertIn("bail!", rust["counts"]["byKind"])

    def test_next_line_is_only_joined_while_the_call_is_open(self):
        # Regression: an unrelated following statement's string was attributed
        # to the preceding raise, inventing a message family.
        self.write("src/a.py", 'raise exc.internal()\nlog.info("unrelated message here")\n')
        families = self.census()["families"]
        self.assertNotIn("unrelated message here", families)

    def test_other_languages(self):
        self.write("web/a.ts", 'throw new TypeError("bad input");\n')
        result = script.census(self.root, ["js"], [], [])
        self.assertEqual(result["counts"]["byKind"], {"TypeError": 1})

    def test_kotlin_throw_without_new(self):
        self.write("app/a.kt", 'throw IllegalStateException("bad")\n')
        result = script.census(self.root, ["java"], [], [])
        self.assertIn("IllegalStateException", result["counts"]["byKind"])

    def test_bare_rethrow_is_not_a_kind(self):
        # Regression: making `new` optional for Kotlin also matched `throw e;`,
        # inventing a kind named after the variable.
        self.write("app/a.java", "try { f(); } catch (IOException e) { throw e; }\n")
        self.assertEqual(script.census(self.root, ["java"], [], [])["counts"]["sites"], 0)

    def test_package_qualified_exception_is_captured(self):
        # Regression: requiring an uppercase first character skipped
        # java.io.IOException, whose package segment is lowercase.
        self.write("app/a.java", 'throw new java.io.IOException("bad");\n')
        self.assertIn("IOException", script.census(self.root, ["java"], [], [])["counts"]["byKind"])

    def test_raises_mentioned_in_docstrings_are_not_counted(self):
        self.write(
            "src/a.py",
            'def f():\n    """Callers raise exc.internal("boom") on failure."""\n    return 1\n',
        )
        self.assertEqual(self.census()["counts"]["sites"], 0)

    def test_exit_three_when_nothing_found(self):
        self.write("src/a.py", "x = 1\n")
        result = run_script(
            "error-taxonomy", "error_census.py", "--root", str(self.root), "--languages", "python"
        )
        self.assertEqual(result.returncode, 3)

    def test_invalid_kind_regex_is_rejected(self):
        result = run_script(
            "error-taxonomy", "error_census.py", "--root", str(self.root), "--kind", "(unclosed"
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a valid regex", result.stderr)


if __name__ == "__main__":
    unittest.main()
