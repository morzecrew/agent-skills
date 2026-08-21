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

# Every RFC carries a graded decision table: `cmd_check` requires it, because
# it is the one section the skill says a minimal RFC still keeps.
DECISIONS = """
## 11. Decisions

| # | Grade | Decision |
|---|---|---|
| 1 | `LOCKED` | The thing is done the way it is done. |
"""

ALPHA = "# RFC 0001 — Alpha\n\n- **Status:** 📝 Draft\n- **Scope:** x\n" + DECISIONS
BETA = ("# RFC 0002 — Beta\n\n- **Status:** ✅ Complete — shipped 2026-01-01; "
        "only P5 remains\n" + DECISIONS)


class Collection:
    """The throwaway collection every group below works against.

    Deliberately not a TestCase: subclassing one re-runs every inherited test
    in each subclass, which triples the suite's runtime to prove the same
    things three times.
    """

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


class RfcCollectionTest(Collection, unittest.TestCase):
    def test_healthy_collection_passes(self):
        self.assertEqual(self.check(), 0)

    def test_status_compared_by_emoji_not_prose(self):
        # "✅ Complete — shipped …; only P5 remains" must still match "✅ Complete".
        self.assertEqual(script.status_emoji(BETA), "✅")

    def test_file_without_index_row(self):
        (self.rfcs / "0009-orphan.md").write_text(
            "# RFC 0009 — Orphan\n\n- **Status:** 📝 Draft\n" + DECISIONS, encoding="utf-8")
        self.assertEqual(self.check(), 2)

    def test_a_non_numbered_file_is_not_an_rfc(self):
        """Only `NNNN-*.md` files are RFCs. Anything else in the directory — a
        README, a diagram, notes — needs no index row and takes no number. That
        used to be incidental (`RFC_FILENAME` requires a 4-digit prefix), and a
        documented behaviour with no test is one an unrelated change to the
        glob can silently break."""
        before = script.next_number(self.rfcs)
        (self.rfcs / "NOTES.md").write_text(
            "# Notes\n\nScratch, not a design.\n", encoding="utf-8")
        self.assertEqual(self.check(), 0, "it is not an orphan RFC")
        self.assertEqual(script.next_number(self.rfcs), before,
                         "it must not consume a number")

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
        #
        # The damaged template goes in a throwaway copy of the scripts
        # directory, never in the working repository: an earlier version of
        # this test edited the tracked rfc-template.md and restored it in a
        # finally block, so an interrupt or a parallel run could leave the real
        # template corrupted for every later test and user.
        real = SCRIPT_DIR.parent / "references" / "rfc-template.md"
        fake_script_dir = self.root / "fake-skill" / "scripts"
        fake_script_dir.mkdir(parents=True)
        (self.root / "fake-skill" / "references").mkdir()
        (self.root / "fake-skill" / "references" / "rfc-template.md").write_text(
            real.read_text(encoding="utf-8").replace("RFC NNNN — <Title>", "RFC ???"),
            encoding="utf-8",
        )

        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
            script.cmd_new(self.rfcs, "Doomed", fake_script_dir)
        self.assertIn("placeholder", str(caught.exception))
        self.assertFalse((self.rfcs / "0003-doomed.md").exists())
        self.assertIn("RFC NNNN — <Title>", real.read_text(encoding="utf-8"),
                      "the tracked template must never be touched by a test")

    def one_liner_row(self, text: str) -> None:
        """Rewrite RFC 0001's index row to carry `text` as its one-liner."""
        index = self.rfcs / "INDEX.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "| [0001](0001-alpha.md) | Alpha | 📝 Draft | first |",
                f"| [0001](0001-alpha.md) | Alpha | 📝 Draft | {text} |",
            ),
            encoding="utf-8",
        )

    def test_index_rows_expose_the_one_liner(self):
        rows = script.index_rows((self.rfcs / "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual(rows[1]["oneLiner"], "first")

    def test_a_row_without_a_one_liner_still_parses(self):
        # The column is optional so existing indexes keep working; a legacy
        # three-cell row reads as an empty one-liner, not as a missing row.
        rows = script.index_rows("| [0005](0005-x.md) | X | 📝 Draft |\n")
        self.assertEqual(rows[5]["oneLiner"], "")
        self.assertEqual(rows[5]["title"], "X")

    def test_a_row_missing_its_pipe_does_not_swallow_the_next(self):
        # Regression: cells could span newlines, so the optional one-liner
        # group ran past a malformed row and consumed the row beneath it. The
        # parser then reported the wrong row as absent, and the insertion
        # position for a new RFC was computed from a table it had misread.
        rows = script.index_rows(
            "| [0001](0001-a.md) | Alpha | 📝 Draft | first\n"
            "| [0002](0002-b.md) | Beta | ✅ Complete | second |\n"
        )
        self.assertIn(2, rows, "the well-formed row below must survive")
        self.assertEqual(rows[2]["oneLiner"], "second")

    def test_an_overlong_one_liner_warns_without_failing(self):
        # The index is re-read on every lookup, so a cell that grows into a
        # summary is charged to every consultation. It is a cost, not a broken
        # collection: the writer judges whether this design needs the words.
        self.one_liner_row("x " * 200)
        result = run_script("rfc-writer", "rfc_index.py", "check", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ceiling", result.stdout)
        self.assertIn("move the detail into the RFC", result.stdout)

    def test_a_one_liner_past_the_target_warns_more_gently(self):
        self.one_liner_row("y " * 120)  # 240 chars: over target, under ceiling
        result = run_script("rfc-writer", "rfc_index.py", "check", "--root", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertIn(f"target {script.ONE_LINER_TARGET}", result.stdout)
        self.assertNotIn("ceiling", result.stdout)

    def test_a_routing_one_liner_is_silent(self):
        self.one_liner_row("Get a backup off the machine that took it")
        result = run_script("rfc-writer", "rfc_index.py", "check", "--root", str(self.root))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("WARN", result.stdout)

    def test_the_new_placeholder_states_the_constraint(self):
        # A writer who never runs `check` should still meet the rule, so the
        # placeholder carries it rather than leaving it to be discovered.
        run_script("rfc-writer", "rfc_index.py", "new", "Gamma", cwd=self.root)
        row = next(
            line for line in (self.rfcs / "INDEX.md").read_text(encoding="utf-8").splitlines()
            if "0003" in line
        )
        self.assertIn(str(script.ONE_LINER_TARGET), row)
        # The ceiling too: naming only the target tells authors that 201-300
        # is invalid, when the checker merely warns there.
        self.assertIn(str(script.ONE_LINER_CEILING), row)
        self.assertIn("one sentence", row)

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
        # The failure is injected at replace_index rather than at a handle's
        # write: a buffered write usually reports a full disk at flush or
        # close, so a test that only breaks write() would miss the real case.
        index_text = (self.rfcs / "INDEX.md").read_text(encoding="utf-8")

        def full_disk(_path, _text):
            raise OSError("No space left on device")

        original = script.replace_index
        script.replace_index = full_disk
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                script.cmd_new(self.rfcs, "Doomed", SCRIPT_DIR)
        finally:
            script.replace_index = original

        self.assertFalse((self.rfcs / "0003-doomed.md").exists(), "no orphan RFC may survive")
        self.assertEqual(
            (self.rfcs / "INDEX.md").read_text(encoding="utf-8"), index_text,
            "a failed update must leave the index exactly as it was",
        )
    def test_a_failed_atomic_write_leaves_no_temp_file(self):
        # The real path, not a stub: the previous assertion sat in the test
        # that replaces replace_index wholesale, so it could never have seen a
        # temp file whether or not one was cleaned up.
        index_path = self.rfcs / "INDEX.md"
        before = index_path.read_text(encoding="utf-8")
        original_replace = script.os.replace

        def failing_replace(*_args):
            raise OSError("No space left on device")

        script.os.replace = failing_replace
        try:
            with self.assertRaises(OSError):
                script.replace_index(index_path, "# never lands\n")
        finally:
            script.os.replace = original_replace

        self.assertEqual(index_path.read_text(encoding="utf-8"), before)
        leftovers = [p.name for p in self.rfcs.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [], "no temp file may survive a failed replace")

    def test_index_keeps_its_mode_across_a_replace(self):
        # Regression: the temp file is created 0600, so an index that was
        # world-readable stopped being so after the first `new`.
        index_path = self.rfcs / "INDEX.md"
        index_path.chmod(0o644)
        script.replace_index(index_path, "# replaced\n")
        self.assertEqual(index_path.stat().st_mode & 0o777, 0o644)

    def test_index_replace_is_atomic_and_leaves_no_temp_file(self):
        # Rewriting in place truncated the old contents before the new ones
        # were durable. The replace either happens whole or not at all.
        index_path = self.rfcs / "INDEX.md"
        script.replace_index(index_path, "# replaced\n")
        self.assertEqual(index_path.read_text(encoding="utf-8"), "# replaced\n")
        self.assertEqual([p.name for p in self.rfcs.iterdir() if p.name.endswith(".tmp")], [])

    def test_title_ending_in_a_backslash_does_not_corrupt_the_row(self):
        # Regression: escaping only the pipe turned a trailing backslash into
        # an escaped backslash followed by a live delimiter.
        # The backslash must abut the pipe: with a space between them the
        # escape never collides, and the test would pass either way.
        result = run_script("rfc-writer", "rfc_index.py", "new", r"Windows C:\|Notes", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        index = (self.rfcs / "INDEX.md").read_text(encoding="utf-8")
        row = next(line for line in index.splitlines() if "0003" in line)
        # Drop escaped pairs, then every pipe left is a real delimiter.
        bare = re.sub(r"\\.", "", row)
        self.assertEqual(bare.count("|"), 5, f"exactly five delimiters: {row}")
        self.assertEqual(self.check(), 0, "the collection must stay consistent")

    @unittest.skipIf(script.fcntl is None, "no fcntl on this platform")
    def test_a_replaced_index_is_relocked_before_use(self):
        # Regression: the lock was held on the inode that os.replace unlinks,
        # so a waiter that opened the file first would acquire the lock on a
        # file no longer at this path, read the pre-update contents, and commit
        # them over the row just written. The waiter must notice and start
        # again on the file that is actually there now.
        index_path = self.rfcs / "INDEX.md"
        read_by_waiter: list[str] = []
        opened_old_inode = threading.Event()
        original_acquire = script.acquire_lock

        # Without this the test covers the regression path only when the
        # threads happen to interleave that way: if the replace lands first,
        # the waiter opens the *new* inode, takes an uncontended lock, and
        # never exercises the recheck. Signalling after the open and before
        # the blocking acquire pins the order that matters.
        def signalling_acquire(handle):
            opened_old_inode.set()
            original_acquire(handle)

        def waiter():
            with script.locked_index(index_path) as handle:
                read_by_waiter.append(handle.read())

        with script.locked_index(index_path):
            script.acquire_lock = signalling_acquire
            try:
                thread = threading.Thread(target=waiter, daemon=True)
                thread.start()
                self.assertTrue(
                    opened_old_inode.wait(5), "the waiter never opened the index"
                )
                # It now holds the inode we are about to unlink.
                script.replace_index(index_path, "# committed by the first writer\n")
            finally:
                script.acquire_lock = original_acquire

        thread.join(timeout=10)
        self.assertEqual(len(read_by_waiter), 1, "the waiter must have run")
        self.assertIn(
            "committed by the first writer", read_by_waiter[0],
            "the waiter read the replaced inode and would have clobbered the update",
        )

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


class ContentFixture(Collection):
    def write_alpha(self, body: str) -> None:
        (self.rfcs / "0001-alpha.md").write_text(
            "# RFC 0001 — Alpha\n\n- **Status:** 📝 Draft\n" + body, encoding="utf-8")

    def problems(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            script.cmd_check(self.rfcs)
        return buffer.getvalue()


class DecisionTableTest(ContentFixture, unittest.TestCase):
    """`check` reads the RFC's contents, not only its filename and status."""

    def test_a_graded_table_passes(self):
        self.assertEqual(self.check(), 0)

    def test_no_decisions_section_fails(self):
        self.write_alpha("\n## 5. Design\n\nSome design.\n")
        self.assertEqual(self.check(), 2)
        self.assertIn("no Decisions section", self.problems())

    def test_an_empty_decisions_table_fails(self):
        self.write_alpha("\n## 11. Decisions\n\n| # | Grade | Decision |\n|---|---|---|\n")
        self.assertEqual(self.check(), 2)
        self.assertIn("no table with", self.problems())

    def test_an_ungraded_row_fails(self):
        self.write_alpha(DECISIONS.replace("`LOCKED`", "probably fine"))
        self.assertEqual(self.check(), 2)
        self.assertIn("not one of LOCKED", self.problems())

    def test_a_row_graded_with_an_invented_word_fails(self):
        self.write_alpha(DECISIONS.replace("`LOCKED`", "`SETTLED`"))
        self.assertEqual(self.check(), 2)

    def test_every_grade_in_the_vocabulary_passes(self):
        for grade in script.GRADES:
            with self.subTest(grade=grade):
                self.write_alpha(DECISIONS.replace("`LOCKED`", f"`{grade}`"))
                self.assertEqual(self.check(), 0)

    def test_a_bold_grade_passes(self):
        self.write_alpha(DECISIONS.replace("`LOCKED`", "**LOCKED**"))
        self.assertEqual(self.check(), 0)

    def test_the_section_number_does_not_matter(self):
        self.write_alpha(DECISIONS.replace("## 11. Decisions", "## Decisions"))
        self.assertEqual(self.check(), 0)

    def test_an_alternatives_table_alone_is_not_a_decision_table(self):
        # Reading every three-column table under the heading turned an
        # alternatives table into decision rows, failing a sound RFC.
        self.write_alpha("\n## 11. Decisions\n\n| Option | Why rejected | Cost |\n"
                         "|---|---|---|\n| A queue | ordering is lost | high |\n")
        self.assertEqual(self.check(), 2)
        self.assertIn("no table with", self.problems())

    def test_a_trailing_table_under_the_same_heading_is_not_read_as_decisions(self):
        self.write_alpha(DECISIONS + "\nRisks:\n\n| Risk | Likelihood | Impact |\n"
                         "|---|---|---|\n| Drift | low | high |\n")
        self.assertEqual(self.check(), 0)

    def test_a_fourth_column_does_not_break_the_table(self):
        self.write_alpha("\n## 11. Decisions\n\n| # | Grade | Decision | Consequence |\n"
                         "|---|---|---|---|\n| 1 | `LOCKED` | X. | Y. |\n")
        self.assertEqual(self.check(), 0)

    def test_a_following_section_does_not_contribute_rows(self):
        # A table under a later heading must not be read as more decisions.
        # Three columns on purpose: a narrower table cannot match the row
        # pattern at all, so it would pass whether the boundary held or not.
        self.write_alpha(DECISIONS + "\n## 12. Phasing\n\n"
                         "| P | Lands | Gated on |\n|---|---|---|\n| 1 | the store | nothing |\n")
        self.assertEqual(self.check(), 0)


    def test_grade_in_a_later_column_is_read(self):
        # Six of the graded tables in the collection this gate was written for
        # put Grade third, behind the decision itself. Reading the second cell
        # positionally failed every one of them while their rows were graded
        # correctly, so the column is found by its heading, not its index.
        self.write_alpha("\n## 11. Decisions\n\n| # | Decision | Grade | Why |\n"
                         "|---|---|---|---|\n| 1 | The thing. | `LOCKED` | Because. |\n")
        self.assertEqual(self.check(), 0)

    def test_an_ungraded_row_in_a_later_grade_column_still_fails(self):
        # Letting the column move must not cost the check its teeth.
        self.write_alpha("\n## 11. Decisions\n\n| # | Decision | Grade | Why |\n"
                         "|---|---|---|---|\n| 1 | The thing. | probably fine | Because. |\n")
        self.assertEqual(self.check(), 2)
        self.assertIn("not one of LOCKED", self.problems())

    def test_a_table_with_no_grade_heading_is_still_not_a_decision_table(self):
        # Finding the column by name must not start accepting tables that
        # never named one -- that is the ungraded collection this gate exists
        # to report.
        self.write_alpha("\n## 11. Decisions\n\n| # | Decision | Why |\n"
                         "|---|---|---|\n| 1 | The thing. | Because. |\n")
        self.assertEqual(self.check(), 2)
        self.assertIn("no table with", self.problems())

class LinkTargetTest(ContentFixture, unittest.TestCase):
    def test_a_resolving_link_passes_quietly(self):
        (self.root / "src").mkdir()
        (self.root / "src" / "real.py").write_text("x\n", encoding="utf-8")
        self.write_alpha(DECISIONS + "\nSee [the code](src/real.py).\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_dangling_link_in_a_draft_is_a_warning(self):
        # A design may cite a file it proposes to create.
        self.write_alpha(DECISIONS + "\nSee [the code](src/planned.py).\n")
        self.assertEqual(self.check(), 0)
        self.assertIn("link target", self.problems())

    def test_a_dangling_link_in_a_complete_rfc_is_a_problem(self):
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\nSee [the code](src/never_built.py).\n", encoding="utf-8")
        self.assertEqual(self.check(), 2)
        self.assertIn("RFC is Complete", self.problems())

    def test_a_target_that_escapes_the_root_is_a_problem(self):
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\n[out](../../../../../../etc/hostname)\n", encoding="utf-8")
        self.assertEqual(self.check(), 2)
        self.assertIn("does not resolve inside the repository", self.problems())

    def test_a_non_http_uri_scheme_is_not_checked(self):
        self.write_alpha(DECISIONS + "\n[a](ftp://h/x) [b](tel:+15550100)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_protocol_relative_url_is_not_checked(self):
        self.write_alpha(DECISIONS + "\n[a](//cdn.example.com/x.png)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_external_urls_are_not_checked(self):
        self.write_alpha(DECISIONS + "\n[spec](https://example.invalid/x) [mail](mailto:a@b.c)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_bare_anchor_is_not_checked(self):
        self.write_alpha(DECISIONS + "\n[above](#decisions)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_an_anchor_on_a_real_file_resolves_to_the_file(self):
        self.write_alpha(DECISIONS + "\n[beta](0002-beta.md#decisions)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_link_relative_to_the_repo_root_resolves(self):
        (self.root / "README.md").write_text("x\n", encoding="utf-8")
        self.write_alpha(DECISIONS + "\n[readme](README.md)\n")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())


    def test_a_link_inside_a_code_fence_is_not_checked(self):
        # A fenced block samples what some *other* file will contain, so its
        # relative links resolve from that file's directory, not this one's.
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\n```markdown\n[commands](commands.md#init)\n```\n",
            encoding="utf-8")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_generic_signature_in_a_fence_is_not_a_link(self):
        # `Register[T any](v View[T])` matches [text](target) exactly, and the
        # target it yields is the bare word `v`.
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\n```go\nfunc Register[T any](v View[T])\n```\n",
            encoding="utf-8")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_a_dangling_link_after_a_fence_closes_is_still_checked(self):
        # Stripping fences must not swallow the rest of the document with them.
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\n```go\nx := 1\n```\n\nSee [the code](src/never_built.py).\n",
            encoding="utf-8")
        self.assertEqual(self.check(), 2)
        self.assertIn("RFC is Complete", self.problems())

    def test_a_tilde_fence_also_hides_its_links(self):
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\n~~~markdown\n[commands](commands.md#init)\n~~~\n",
            encoding="utf-8")
        self.assertEqual(self.check(), 0)
        self.assertNotIn("link target", self.problems())

    def test_an_unclosed_fence_hides_only_what_follows_it(self):
        # An unterminated fence runs to end of file. The link before it is
        # still the author's own prose and is still checked.
        (self.rfcs / "0002-beta.md").write_text(
            BETA + "\nSee [the code](src/never_built.py).\n\n```go\nx := 1\n",
            encoding="utf-8")
        self.assertEqual(self.check(), 2)
        self.assertIn("RFC is Complete", self.problems())

if __name__ == "__main__":
    unittest.main()
