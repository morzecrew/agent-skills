"""Tests for authority-dissociation/scripts/same_keystroke.py.

Every case builds a real repository, because the checks read git and nothing
else. Each shape is shown firing and the honest counterpart shown clean — a
detector that also fires on a correct second-party attestation would train
everyone to ignore it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import git, git_repo, load_script, run_script

sk = load_script("authority-dissociation", "same_keystroke.py")


class RepoCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        git_repo(self.root)
        self.write("code.py", "v1\n")
        self.commit("seed")

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def author(self, name: str, email: str) -> None:
        git(self.root, "config", "user.name", name)
        git(self.root, "config", "user.email", email)

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", message)

    def remove(self, path: str) -> None:
        git(self.root, "rm", "-q", path)

    def scan(self, rev_range=None, patterns=sk.EVIDENCE_PATTERNS, explicit=()):
        return sk.scan(self.root, rev_range, patterns, explicit)

    def checks(self, findings) -> list[str]:
        return [f["check"] for f in findings]


class TestSameCommit(RepoCase):

    def test_work_and_its_approval_in_one_commit_is_flagged(self):
        self.write("code.py", "v2\n")
        self.write("approvals/2024-03-11.md", "approved\n")
        self.commit("add the feature, approved")
        findings = self.scan()
        self.assertEqual(self.checks(findings), ["self-attested-commit"])
        self.assertEqual(findings[0]["evidence"], ["approvals/2024-03-11.md"])
        self.assertEqual(findings[0]["attested"], ["code.py"])

    def test_an_attestation_only_commit_by_another_author_is_clean(self):
        self.write("code.py", "v2\n")
        self.commit("add the feature")
        self.author("Second Party", "second@example.com")
        self.write("approvals/2024-03-11.md", "approved\n")
        self.commit("approve the feature")
        self.assertEqual(self.scan(), [])

    def test_a_commit_with_no_attestation_is_not_examined(self):
        self.write("code.py", "v2\n")
        self.commit("ordinary work")
        self.assertEqual(self.scan(), [])

    def test_the_author_is_reported(self):
        self.write("code.py", "v2\n")
        self.write("approvals/a.md", "ok\n")
        self.commit("both")
        self.assertIn("Test", self.scan()[0]["author"])

    def test_deleting_an_approval_alongside_work_is_not_attesting(self):
        """`--name-only` cannot tell writing a record from removing one, so
        clearing out stale approvals was reported as manufacturing them."""
        self.write("approvals/old.md", "approved\n")
        self.commit("an old approval")
        git(self.root, "tag", "cut")
        self.remove("approvals/old.md")
        self.write("code.py", "v2\n")
        self.commit("drop the stale approval and change the code")
        self.assertEqual(self.scan("cut..HEAD"), [])

    def test_a_deletion_does_not_hide_a_written_approval_in_the_same_commit(self):
        self.write("approvals/old.md", "approved\n")
        self.commit("an old approval")
        git(self.root, "tag", "cut")
        self.remove("approvals/old.md")
        self.write("approvals/new.md", "approved again\n")
        self.write("code.py", "v2\n")
        self.commit("replace the approval and change the code")
        findings = self.scan("cut..HEAD")
        self.assertEqual(self.checks(findings), ["self-attested-commit"])
        self.assertEqual(findings[0]["evidence"], ["approvals/new.md"])


class TestSplitCommit(RepoCase):
    """Committing the attestation separately removes the tell and nothing else."""

    def test_the_same_author_attesting_their_own_previous_commit_is_flagged(self):
        self.write("code.py", "v2\n")
        self.commit("add the feature")
        self.write("approvals/a.md", "approved\n")
        self.commit("approve it")
        findings = self.scan()
        self.assertEqual(self.checks(findings), ["self-attested-sequence"])
        self.assertIn("add the feature", findings[0]["attested"][0])

    def test_a_second_party_between_them_is_clean(self):
        self.write("code.py", "v2\n")
        self.commit("add the feature")
        self.author("Second Party", "second@example.com")
        self.write("approvals/a.md", "approved\n")
        self.commit("approve it")
        self.assertEqual(self.scan(), [])

    def test_a_second_party_approval_in_between_breaks_the_sequence(self):
        """The finding says "no second party in between". Carrying the older
        work forward past an intervening approval made that sentence false:
        B's approval is the independent step the check looks for."""
        self.write("code.py", "v2\n")
        self.commit("A does the work")
        self.author("Second Party", "second@example.com")
        self.write("approvals/by-b.md", "approved\n")
        self.commit("B approves")
        self.author("Test", "t@example.com")
        self.write("approvals/by-a.md", "approved too\n")
        self.commit("A approves later")
        self.assertEqual(self.scan(), [])

    def test_a_second_attestation_by_the_same_author_is_reported_once(self):
        self.write("code.py", "v2\n")
        self.commit("the work")
        self.write("approvals/a.md", "approved\n")
        self.commit("approve it")
        self.write("approvals/b.md", "approved again\n")
        self.commit("approve it again")
        self.assertEqual(self.checks(self.scan()), ["self-attested-sequence"])

    def test_attesting_someone_elses_work_much_later_is_clean(self):
        self.write("code.py", "v2\n")
        self.commit("first author's work")
        self.author("Second Party", "second@example.com")
        self.write("other.py", "x\n")
        self.commit("second author's work")
        self.author("Test", "t@example.com")
        self.write("approvals/a.md", "approved\n")
        self.commit("first author approves the second author's work")
        self.assertEqual(self.scan(), [],
                         "the preceding change was not this author's own")


class TestEvidenceDetection(unittest.TestCase):

    def matches(self, path: str) -> bool:
        return sk.is_evidence(path, sk.EVIDENCE_PATTERNS)

    def test_attestation_shapes_are_recognized(self):
        for path in ("approvals/2024-03-11.md", "docs/RULING-14.md",
                     "SIGNOFF.txt", "ops/waivers/db.yaml",
                     "security/authorization-note.md", "CERTIFIED.md",
                     "deep/nested/sign_off/entry.json"):
            self.assertTrue(self.matches(path), path)

    def test_ordinary_paths_are_not(self):
        for path in ("src/app.py", "tests/test_app.py", "README.md",
                     "docs/architecture.md", ".github/workflows/ci.yml"):
            self.assertFalse(self.matches(path), path)

    def test_review_is_deliberately_not_evidence(self):
        """A review is a discussion. Matching it would bury the findings that
        matter under every code-review note in the repository."""
        self.assertFalse(self.matches("docs/review-notes.md"))

    def test_program_source_is_not_an_attestation_record(self):
        """These implement the vocabulary rather than record a ruling, and
        matching them made every repository with an auth module light up."""
        for path in ("src/authorization.py", "approval-handler/index.go",
                     "certified_client/main.rs", "lib/signoff.ts",
                     "scripts/waiver.sh"):
            self.assertFalse(self.matches(path), path)

    def test_an_explicit_glob_still_matches_program_source(self):
        """The caller knows their own layout; the built-in vocabulary does not."""
        self.assertTrue(sk.is_evidence("src/authorization.py",
                                       sk.EVIDENCE_PATTERNS + ("*authoriz*",),
                                       ("*authoriz*",)))
        self.assertFalse(sk.is_evidence("src/authorization.py",
                                        sk.EVIDENCE_PATTERNS + ("*ruling*",),
                                        ("*ruling*",)))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(self.matches("Approvals/Q3.md"))
        self.assertTrue(self.matches("docs/Sign-Off.md"))


class TestCustomGlobs(RepoCase):

    def test_an_extra_glob_widens_the_set(self):
        self.write("code.py", "v2\n")
        self.write("gates/verdict.json", "{}\n")
        self.commit("work plus verdict")
        self.assertEqual(self.scan(), [])
        widened = self.scan(patterns=sk.EVIDENCE_PATTERNS + ("*verdict*",))
        self.assertEqual(self.checks(widened), ["self-attested-commit"])

    def test_only_glob_replaces_the_builtins(self):
        self.write("code.py", "v2\n")
        self.write("approvals/a.md", "ok\n")
        self.commit("work plus approval")
        self.assertEqual(sk.scan(self.root, None, ("*verdict*",)), [],
                         "the built-in patterns must not apply")


class TestRange(RepoCase):

    def test_a_range_limits_what_is_examined(self):
        self.write("code.py", "v2\n")
        self.write("approvals/old.md", "ok\n")
        self.commit("old self-attestation")
        git(self.root, "tag", "cut")
        self.write("code.py", "v3\n")
        self.commit("later work only")
        self.assertEqual(self.scan("cut..HEAD"), [])
        self.assertEqual(len(self.scan()), 1)

    def test_work_just_outside_the_range_still_anchors_a_sequence(self):
        """`main..HEAD` is the way this is actually invoked, and it saw only
        what was inside the range — so a sequence whose work commit is the
        range's own base came back clean, which is the one answer it must
        never give by construction."""
        self.write("code.py", "v2\n")
        self.commit("the work")
        git(self.root, "tag", "cut")
        self.write("approvals/a.md", "approved\n")
        self.commit("approve it")
        self.assertEqual(self.checks(self.scan("cut..HEAD")),
                         ["self-attested-sequence"])

    def test_an_attestation_just_outside_the_range_does_not_anchor_one(self):
        self.write("code.py", "v2\n")
        self.commit("the work")
        self.write("approvals/a.md", "approved\n")
        self.commit("approve it")
        git(self.root, "tag", "cut")
        self.write("approvals/b.md", "approved again\n")
        self.commit("approve it again")
        self.assertEqual(self.scan("cut..HEAD"), [])

    def test_a_range_whose_first_commit_is_the_root_is_handled(self):
        """`rev-parse HEAD^` fails on a root commit; the scan must not."""
        self.assertEqual(self.scan("HEAD"), [])


class TestCommandLine(RepoCase):

    def run_sk(self, *args):
        return run_script("authority-dissociation", "same_keystroke.py",
                          *args, cwd=self.root)

    def test_findings_exit_one(self):
        self.write("code.py", "v2\n")
        self.write("approvals/a.md", "ok\n")
        self.commit("work plus approval")
        proc = self.run_sk()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("self-attested-commit", proc.stdout)

    def test_a_clean_history_exits_zero(self):
        self.write("code.py", "v2\n")
        self.commit("ordinary work")
        proc = self.run_sk()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("no self-attestation", proc.stdout)

    def test_json_output_is_machine_readable(self):
        self.write("code.py", "v2\n")
        self.write("approvals/a.md", "ok\n")
        self.commit("work plus approval")
        proc = self.run_sk("--json")
        self.assertEqual(json.loads(proc.stdout)[0]["check"], "self-attested-commit")

    def test_a_directory_that_is_not_a_repository_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_script("authority-dissociation", "same_keystroke.py",
                              "--repo", tmp)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("REFUSE", proc.stderr)

    def test_only_glob_without_a_glob_is_a_usage_error(self):
        proc = self.run_sk("--only-glob")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--evidence-glob", proc.stderr)

    def test_render_says_so_when_clean(self):
        self.assertIn("no self-attestation", sk.render([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
