"""Tests for rfc-writer/scripts/rfc_index.py."""

from __future__ import annotations

import contextlib
import io
import re
import tempfile
import threading
import unittest
from pathlib import Path

from support import SKILLS, load_script, run_script

script = load_script("rfc-writer", "rfc_index.py")
SCRIPT_DIR = SKILLS / "rfc-writer" / "scripts"

INDEX = """# RFCs

The next free number is **0003**.

## Index

| # | Title | Status | One-line |
|---|---|---|---|
| [0001](0001-alpha.md) | Alpha | 📝 Draft | first |
| [0002](0002-beta.md) | Beta | ✅ Complete | second |

## Status legend

- 📝 **Draft**
"""

ALPHA = "# RFC 0001 — Alpha\n\n- **Status:** 📝 Draft\n- **Scope:** x\n"
BETA = "# RFC 0002 — Beta\n\n- **Status:** ✅ Complete — shipped 2026-01-01; only P5 remains\n"


class RfcCollectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.rfcs = self.root / "rfcs"
        self.rfcs.mkdir()
        (self.rfcs / "INDEX.md").write_text(INDEX, encoding="utf-8")
        (self.rfcs / "0001-alpha.md").write_text(ALPHA, encoding="utf-8")
        (self.rfcs / "0002-beta.md").write_text(BETA, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self) -> int:
        # cmd_check reports to stdout; swallow it so expected failures don't
        # read as test failures in CI output.
        with contextlib.redirect_stdout(io.StringIO()):
            return script.cmd_check(self.rfcs)

    def test_healthy_collection_passes(self):
        self.assertEqual(self.check(), 0)

    def test_status_compared_by_emoji_not_prose(self):
        # "✅ Complete — shipped …; only P5 remains" must still match "✅ Complete".
        self.assertEqual(script.status_emoji(BETA), "✅")

    def test_file_without_index_row(self):
        (self.rfcs / "0009-orphan.md").write_text("# RFC 0009 — Orphan\n\n- **Status:** 📝 Draft\n", encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_index_row_without_file(self):
        (self.rfcs / "0002-beta.md").unlink()
        self.assertEqual(self.check(), 2)

    def test_h1_number_disagrees_with_filename(self):
        (self.rfcs / "0001-alpha.md").write_text(ALPHA.replace("RFC 0001", "RFC 0099"), encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_header_status_disagrees_with_table(self):
        (self.rfcs / "0001-alpha.md").write_text(ALPHA.replace("📝 Draft", "❌ Rejected"), encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_claimed_next_number_is_taken(self):
        (self.rfcs / "INDEX.md").write_text(INDEX.replace("**0003**", "**0002**"), encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_claimed_next_number_below_highest(self):
        (self.rfcs / "INDEX.md").write_text(INDEX.replace("**0003**", "**0001**"), encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_next_number_prefers_the_higher_of_disk_and_index(self):
        self.assertEqual(script.next_number(self.rfcs), 3)
        (self.rfcs / "INDEX.md").write_text(INDEX.replace("**0003**", "**0099**"), encoding="utf-8")
        self.assertEqual(script.next_number(self.rfcs), 99)

    def test_duplicate_numbers_on_disk_are_fatal(self):
        (self.rfcs / "0001-duplicate.md").write_text(ALPHA, encoding="utf-8")
        with self.assertRaises(SystemExit):
            script.rfc_files(self.rfcs)

    def test_new_allocates_creates_and_indexes(self):
        result = run_script("rfc-writer", "rfc_index.py", "new", "Gamma Design", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        created = self.rfcs / "0003-gamma-design.md"
        self.assertTrue(created.is_file())
        self.assertIn("# RFC 0003 — Gamma Design", created.read_text())
        index = (self.rfcs / "INDEX.md").read_text()
        self.assertIn("| [0003](0003-gamma-design.md) | Gamma Design | 📝 Draft |", index)
        self.assertIn("next free number is **0004**", index)
        self.assertEqual(self.check(), 0, "new must leave the collection consistent")

    def test_new_at_an_explicit_number(self):
        result = run_script("rfc-writer", "rfc_index.py", "new", "Reserved", "--number", "7", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.rfcs / "0007-reserved.md").is_file())

    def test_new_refuses_to_overwrite_an_existing_rfc(self):
        # Reachable only via --number: the automatic allocation always exceeds
        # the highest number on disk, so this guard needs the override to be
        # exercised rather than left as unreachable defensive code.
        result = run_script("rfc-writer", "rfc_index.py", "new", "Alpha", "--number", "1", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertEqual((self.rfcs / "0001-alpha.md").read_text(), ALPHA, "must not clobber")

    def test_number_must_be_a_four_digit_id(self):
        # Regression: 0, negatives and >9999 produced filenames RFC_FILENAME
        # cannot match, leaving an orphan the checker then reports.
        for bad in ("0", "-1", "99999"):
            with self.subTest(number=bad):
                result = run_script(
                    "rfc-writer", "rfc_index.py", "new", "X", "--number", bad, cwd=self.root
                )
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("four digits", result.stderr)
        self.assertEqual(sorted(p.name for p in self.rfcs.glob("*.md")),
                         ["0001-alpha.md", "0002-beta.md", "INDEX.md"])

    def test_explicit_number_never_lowers_the_next_free_claim(self):
        # Regression: `new --number 3` on a collection at 0008 rewound the claim
        # to 0004, and cmd_check then reported the index as broken.
        run_script("rfc-writer", "rfc_index.py", "new", "Low", "--number", "1", cwd=self.root)
        run_script("rfc-writer", "rfc_index.py", "new", "Reserved", "--number", "5", cwd=self.root)
        index = (self.rfcs / "INDEX.md").read_text()
        self.assertIn("next free number is **0006**", index)
        run_script("rfc-writer", "rfc_index.py", "new", "Lower", "--number", "3", cwd=self.root)
        self.assertIn("next free number is **0006**", (self.rfcs / "INDEX.md").read_text())

    def test_missing_index_leaves_no_orphan_file(self):
        # Regression: the RFC was written before the index was resolved, so a
        # missing table left an orphan on disk.
        (self.rfcs / "INDEX.md").write_text("# RFCs\n\nThe next free number is **0003**.\n", encoding="utf-8")
        result = run_script("rfc-writer", "rfc_index.py", "new", "Orphan", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.rfcs / "0003-orphan.md").exists(), "no orphan RFC may survive")

    def test_root_is_accepted_after_the_subcommand(self):
        # Regression: --root was top-level only, so the form anyone would type
        # failed outright with "unrecognized arguments".
        for args in (["check", "--root", str(self.root)], ["--root", str(self.root), "check"]):
            with self.subTest(args=args):
                result = run_script("rfc-writer", "rfc_index.py", *args)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_root_before_the_subcommand_is_not_clobbered(self):
        # The subcommand's own --root must not overwrite the top-level value
        # with a default when it is absent.
        result = run_script("rfc-writer", "rfc_index.py", "--root", str(self.root), "next")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "0003")

    def test_template_without_its_placeholder_is_refused(self):
        # Regression: the substitution was unchecked, so an edited template
        # produced an RFC whose H1 was still the literal placeholder — which
        # `check` then reported as a broken file the tool had just written.
        template = SCRIPT_DIR.parent / "references" / "rfc-template.md"
        original = template.read_text(encoding="utf-8")
        template.write_text(original.replace("RFC NNNN — <Title>", "RFC ???"), encoding="utf-8")
        try:
            result = run_script("rfc-writer", "rfc_index.py", "new", "Doomed", cwd=self.root)
        finally:
            template.write_text(original, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("placeholder", result.stderr)
        self.assertFalse((self.rfcs / "0003-doomed.md").exists())

    def test_duplicate_numbers_are_a_check_finding_not_a_usage_error(self):
        # Regression: failing hard inside rfc_files exited 1, the code reserved
        # for a usage or IO error, so a broken collection was indistinguishable
        # from a broken invocation. `check` documents exit 2 for findings.
        (self.rfcs / "0001-duplicate-slug.md").write_text(ALPHA, encoding="utf-8")
        result = run_script("rfc-writer", "rfc_index.py", "check", cwd=self.root)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("0001", result.stdout)

    def test_pipe_in_a_title_does_not_corrupt_the_row(self):
        # Regression: an unescaped pipe opened a new cell and shifted every
        # column after it, so the row read back was not the row written.
        result = run_script(
            "rfc-writer", "rfc_index.py", "new", "Sharding | Rebalancing", cwd=self.root
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        index = (self.rfcs / "INDEX.md").read_text(encoding="utf-8")
        row = next(line for line in index.splitlines() if "0003" in line)
        self.assertIn(r"Sharding \| Rebalancing", row)
        delimiters = len(re.findall(r"(?<!\\)\|", row))
        self.assertEqual(delimiters, 5, f"exactly five unescaped delimiters: {row}")
        self.assertEqual(self.check(), 0, "the collection must stay consistent")

    def test_index_without_a_next_free_claim_is_refused(self):
        # Regression: the substitution silently did nothing, so `new` reported
        # success while leaving the index with no claim to allocate from.
        (self.rfcs / "INDEX.md").write_text(
            "# RFCs\n\n## Index\n\n| # | Title | Status | One-line |\n|---|---|---|---|\n",
            encoding="utf-8",
        )
        result = run_script("rfc-writer", "rfc_index.py", "new", "Claimless", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("next free number", result.stderr)
        self.assertFalse((self.rfcs / "0003-claimless.md").exists(), "no orphan may survive")

    def test_failed_index_write_removes_the_new_rfc(self):
        # Regression: pre-resolving lookups covered a missing index, not a
        # failing write. A full disk or read-only mount left the RFC on disk
        # with no row and no next-free bump — an orphan nothing points at.
        index_text = (self.rfcs / "INDEX.md").read_text(encoding="utf-8")

        class FullDisk:
            def read(self):
                return index_text

            def seek(self, *args):
                pass

            def truncate(self, *args):
                pass

            def write(self, *args):
                raise OSError("No space left on device")

        @contextlib.contextmanager
        def failing_lock(_path):
            yield FullDisk()

        original = script.locked_index
        script.locked_index = failing_lock
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                script.cmd_new(self.rfcs, "Doomed", SCRIPT_DIR)
        finally:
            script.locked_index = original

        self.assertFalse((self.rfcs / "0003-doomed.md").exists(), "no orphan RFC may survive")
        self.assertEqual((self.rfcs / "INDEX.md").read_text(encoding="utf-8"), index_text)

    @unittest.skipIf(script.fcntl is None, "no fcntl on this platform")
    def test_index_lock_excludes_a_concurrent_writer(self):
        # Allocation and rewrite must be one critical section: two runs that
        # read the index concurrently both rewrite it, and the second write
        # drops the first's row — losing what numbering is derived from.
        index = self.rfcs / "INDEX.md"
        entered = threading.Event()

        def contender():
            with script.locked_index(index):
                entered.set()

        with script.locked_index(index):
            thread = threading.Thread(target=contender, daemon=True)
            thread.start()
            self.assertFalse(
                entered.wait(0.5), "a second writer entered while the index was locked"
            )
        self.assertTrue(entered.wait(5), "the lock must be released on exit")
        thread.join(timeout=5)

    def test_number_already_taken_is_refused_whatever_the_slug(self):
        # Regression: the guard compared filenames, so a different title at the
        # same number produced two RFCs sharing one identifier.
        result = run_script("rfc-writer", "rfc_index.py", "new", "Totally Different", "--number", "1", cwd=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists as 0001-alpha.md", result.stderr)

    def test_duplicate_index_rows_are_reported(self):
        # Regression: index_rows keys by number, so duplicates collapsed and the
        # one-row-per-RFC contract went unchecked.
        index = (self.rfcs / "INDEX.md").read_text()
        (self.rfcs / "INDEX.md").write_text(
            index.replace(
                "| [0002](0002-beta.md) | Beta | ✅ Complete | second |",
                "| [0002](0002-beta.md) | Beta | ✅ Complete | second |\n"
                "| [0002](0002-beta.md) | Beta again | ✅ Complete | dup |",
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.check(), 2)

    def test_slugify(self):
        self.assertEqual(script.slugify("Portable Export & Import!"), "portable-export-import")
        with self.assertRaises(SystemExit):
            script.slugify("!!!")


class EmptyCollectionTest(unittest.TestCase):
    def test_new_into_an_empty_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfcs = root / "rfcs"
            rfcs.mkdir()
            (rfcs / "INDEX.md").write_text(
                "# RFCs\n\nThe next free number is **0001**.\n\n"
                "## Index\n\n| # | Title | Status | One-line |\n|---|---|---|---|\n\n"
                "## Status legend\n\n- 📝 **Draft**\n",
                encoding="utf-8",
            )
            result = run_script("rfc-writer", "rfc_index.py", "new", "First", cwd=root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((rfcs / "0001-first.md").is_file())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(script.cmd_check(rfcs), 0)


if __name__ == "__main__":
    unittest.main()
