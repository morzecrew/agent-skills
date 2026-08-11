"""Tests for scripts/borrowed_prose.py.

This tool exists to answer one question — did any of this sentence come from
somewhere else — so the failures worth testing are the ones that answer "no"
without having looked: a corpus nothing could be read from, a run whose second
half is never examined, and a scan that never terminates at all.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import load_repo_script, run_repo_script

bp = load_repo_script("borrowed_prose.py")

WORDS = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"


def index(text: str, n: int = 7) -> set[str]:
    words = bp.norm(text).split()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


class TestNormalization(unittest.TestCase):

    def test_case_and_punctuation_do_not_hide_a_match(self):
        self.assertEqual(bp.norm("The **Rule**, travels!"), "the rule travels")

    def test_whitespace_collapses(self):
        self.assertEqual(bp.norm("a\n\n  b\tc"), "a b c")


class TestRuns(unittest.TestCase):

    def test_a_shared_run_is_reported_with_its_length(self):
        runs = bp.runs_in(WORDS, index(WORDS), 7)
        self.assertEqual(runs, [bp.norm(WORDS)])

    def test_unshared_text_reports_nothing(self):
        self.assertEqual(bp.runs_in("wholly unrelated words written here today "
                                    "by someone else entirely", index(WORDS), 7), [])

    def test_a_run_shorter_than_the_window_is_not_a_run(self):
        self.assertEqual(bp.runs_in("alpha beta gamma delta", index(WORDS), 7), [])

    def test_an_overlapping_second_match_is_not_skipped(self):
        """The cursor used to jump past a finished run, so every window start
        inside its tail went unexamined and the text the second match ran on
        into was reported as original."""
        corpus = index("a b c d e f g", 7) | index("c d e f g h i", 7)
        self.assertEqual(bp.runs_in("a b c d e f g h i", corpus, 7),
                         ["a b c d e f g h i"])

    def test_two_genuinely_separate_runs_stay_separate(self):
        left, right = "one two three four five six seven", \
                      "ten twenty thirty forty fifty sixty seventy"
        text = f"{left} UNIQUEGAP {right}"
        self.assertEqual(bp.runs_in(text, index(left) | index(right), 7),
                         [left, right])


class TestBoilerplate(unittest.TestCase):

    def test_a_universal_idiom_alone_is_filtered(self):
        text = "read_text(encoding='utf-8')"
        self.assertEqual(bp.runs_in(text, index(text), 4), [])

    def test_distinctive_text_after_an_idiom_survives(self):
        """Filtering on the run's prefix discarded the whole run, so a borrowed
        sentence hid behind whichever stock line happened to precede it."""
        text = ("read text encoding utf 8 and then a distinctive borrowed "
                "clause carries on well past it")
        runs = bp.runs_in(text, index(text), 7)
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0].startswith("and then a distinctive"), runs)

    def test_the_filter_applies_to_the_prefix_only(self):
        self.assertEqual(bp.surviving("self assertequal".split(), 7), [])


class TestCorpusIndex(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_unreadable_files_are_counted_as_unread(self):
        bad = self.root / "notes.md"
        bad.mkdir()                     # a directory reads as an OSError
        grams, read, problem = bp.build_index([bad], 7)
        self.assertEqual((grams, read), (set(), 0))
        self.assertIn("notes.md", problem)

    def test_only_known_suffixes_and_small_files_are_indexed(self):
        (self.root / "keep.md").write_text(WORDS, encoding="utf-8")
        (self.root / "skip.bin").write_text(WORDS, encoding="utf-8")
        (self.root / "huge.md").write_text("x" * (bp.MAX_CORPUS_BYTES + 1),
                                           encoding="utf-8")
        found = [p.name for p in bp.corpus_files([self.root])]
        self.assertEqual(found, ["keep.md"])


class TestCommandLine(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_bp(self, *args, timeout=20):
        return run_repo_script("borrowed_prose.py", *args, timeout=timeout)

    def test_a_shared_run_exits_one(self):
        corpus = self.write("corpus.md", WORDS)
        target = self.write("target.md", WORDS)
        proc = self.run_bp("--corpus", str(corpus), str(target))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("TOTAL: 1", proc.stdout)

    def test_unshared_text_exits_zero(self):
        corpus = self.write("corpus.md", WORDS)
        target = self.write("target.md", "nothing here resembles the corpus at all")
        proc = self.run_bp("--corpus", str(corpus), str(target))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("TOTAL: 0", proc.stdout)

    def test_a_non_positive_window_is_a_usage_error(self):
        """`--words 0` matched the empty gram everywhere and advanced past
        nothing, so the scan ran until somebody killed it."""
        corpus = self.write("corpus.md", WORDS)
        target = self.write("target.md", WORDS)
        for value in ("0", "-3"):
            proc = self.run_bp("--corpus", str(corpus), str(target),
                               "--words", value)
            self.assertEqual(proc.returncode, 2, value)
            self.assertIn("at least 1", proc.stderr)

    def test_an_empty_corpus_refuses_rather_than_reporting_clean(self):
        proc = self.run_bp("--corpus", str(self.root / "absent"),
                           str(self.write("target.md", WORDS)))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("no corpus files", proc.stderr)

    def test_a_corpus_nothing_can_be_read_from_refuses(self):
        """Zero shared runs because zero files were compared is not a clean
        result, and it must not print like one."""
        (self.root / "corpus").mkdir()
        locked = self.root / "corpus" / "unreadable.md"
        locked.write_text(WORDS, encoding="utf-8")
        locked.chmod(0o000)
        self.addCleanup(locked.chmod, 0o600)
        try:
            locked.read_text()
        except OSError:
            pass
        else:
            self.skipTest("running as a user that permissions cannot stop")
        proc = self.run_bp("--corpus", str(self.root / "corpus"),
                           str(self.write("target.md", WORDS)))
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("could be read", proc.stderr)

    def test_an_unreadable_target_refuses(self):
        proc = self.run_bp("--corpus", str(self.write("corpus.md", WORDS)),
                           str(self.root / "missing.md"))
        self.assertEqual(proc.returncode, 2, proc.stdout)

    def test_the_corpus_file_count_is_reported(self):
        corpus = self.write("corpus.md", WORDS)
        proc = self.run_bp("--corpus", str(corpus),
                           str(self.write("target.md", "unrelated prose here")))
        self.assertIn("against 1 corpus file(s)", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
