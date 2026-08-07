"""Tests for pr-review-loop/scripts/pr_loop.py.

Only the pure logic is covered here: everything that talks to `gh` needs a live
PR and lands in the manual smoke tests instead. Faking the GitHub API surface
would test the fake, not the tool.
"""

from __future__ import annotations

import unittest

from support import load_script

script = load_script("pr-review-loop", "pr_loop.py")


class BotIdentityTest(unittest.TestCase):
    def test_rest_bot_detection(self):
        self.assertTrue(script.rest_is_bot({"type": "Bot", "login": "coderabbitai[bot]"}))
        self.assertTrue(script.rest_is_bot({"type": "User", "login": "greptile-apps[bot]"}))
        self.assertFalse(script.rest_is_bot({"type": "User", "login": "octocat"}))
        self.assertFalse(script.rest_is_bot(None))

    def test_graphql_bot_detection(self):
        self.assertTrue(script.gql_is_bot({"__typename": "Bot", "login": "coderabbitai"}))
        self.assertTrue(script.gql_is_bot({"__typename": "User", "login": "x[bot]"}))
        self.assertFalse(script.gql_is_bot({"__typename": "User", "login": "octocat"}))

    def test_comment_normalization(self):
        node = {
            "databaseId": 5,
            "author": {"login": "coderabbitai", "__typename": "Bot"},
            "url": "https://example/1",
            "body": "text",
        }
        self.assertEqual(
            script.normalize_gql_comment(node),
            {"databaseId": 5, "author": "coderabbitai", "isBot": True,
             "url": "https://example/1", "body": "text"},
        )

    def test_missing_author_does_not_crash(self):
        # Deleted accounts come back as author: null.
        normalized = script.normalize_gql_comment({"databaseId": 1, "author": None, "url": None, "body": ""})
        self.assertIsNone(normalized["author"])
        self.assertFalse(normalized["isBot"])


class SurfaceDigestTest(unittest.TestCase):
    """Any new, edited, or replied-to comment must move the fingerprint.

    Regression: the fingerprint sampled `last: 20` per surface, so activity on
    an older thread changed no total and moved no timestamp, and `wait` could
    report settled while comments were still arriving.
    """

    def items(self, count: int = 25) -> list[dict]:
        return [
            {"id": i, "updated_at": "2026-01-01T00:00:00Z", "body": f"comment {i}"}
            for i in range(count)
        ]

    def test_a_reply_past_the_twentieth_item_moves_the_fingerprint(self):
        before = self.items()
        after = before + [{"id": 99, "updated_at": "2026-01-01T00:01:00Z", "body": "reply"}]
        self.assertNotEqual(script.surface_digest(before), script.surface_digest(after))

    def test_editing_the_oldest_comment_moves_the_fingerprint(self):
        before = self.items()
        after = [dict(item) for item in before]
        after[0]["body"] = "edited well after the window moved on"
        self.assertNotEqual(script.surface_digest(before), script.surface_digest(after))

    def test_an_edit_that_leaves_the_timestamp_alone_still_moves_it(self):
        # A REST review exposes submitted_at, which a body edit never touches,
        # so timestamps alone cannot carry this signal.
        before = [{"id": 1, "submitted_at": "2026-01-01T00:00:00Z", "body": "looks good"}]
        after = [{"id": 1, "submitted_at": "2026-01-01T00:00:00Z", "body": "actually, one thing"}]
        self.assertNotEqual(script.surface_digest(before), script.surface_digest(after))

    def test_ordering_alone_does_not_move_it(self):
        items = self.items(5)
        self.assertEqual(
            script.surface_digest(items), script.surface_digest(list(reversed(items)))
        )


class WaitVerdictTest(unittest.TestCase):
    """The poll loop's state machine: checks complete, then comments must settle."""

    PENDING = {"pending": ["ci"], "attention": [], "clean": []}
    COMPLETE = {"pending": [], "attention": [], "clean": ["ci"]}

    def test_pending_checks_block_and_reset_the_settle_clock(self):
        state, stable = script.wait_verdict(self.PENDING, (1, 1, 1), (1, 1, 1), 100.0, 200.0, 90)
        self.assertEqual(state, "pending-checks")
        self.assertIsNone(stable)

    def test_new_comments_restart_the_settle_window(self):
        state, stable = script.wait_verdict(self.COMPLETE, (2, 1, 1), (1, 1, 1), 100.0, 200.0, 90)
        self.assertEqual(state, "settling")
        self.assertEqual(stable, 200.0, "the clock restarts when counts move")

    def test_first_stable_observation_starts_the_window(self):
        state, stable = script.wait_verdict(self.COMPLETE, (1, 1, 1), None, None, 200.0, 90)
        self.assertEqual(state, "settling")
        self.assertEqual(stable, 200.0)

    def test_still_settling_before_the_window_elapses(self):
        state, stable = script.wait_verdict(self.COMPLETE, (1, 1, 1), (1, 1, 1), 200.0, 250.0, 90)
        self.assertEqual(state, "settling")
        self.assertEqual(stable, 200.0, "the clock must not restart while counts hold")

    def test_done_once_counts_hold_for_the_settle_window(self):
        state, _ = script.wait_verdict(self.COMPLETE, (1, 1, 1), (1, 1, 1), 200.0, 300.0, 90)
        self.assertEqual(state, "done")

    def test_a_check_completing_green_is_not_enough_on_its_own(self):
        # The reason this state machine exists: a reviewer's check often goes
        # green before its review is posted.
        state, _ = script.wait_verdict(self.COMPLETE, (1, 1, 1), None, None, 0.0, 90)
        self.assertNotEqual(state, "done")


if __name__ == "__main__":
    unittest.main()
