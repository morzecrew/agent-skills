"""Tests for pr-review-loop/scripts/pr_loop.py.

Only the pure logic is covered here: everything that talks to `gh` needs a live
PR and lands in the manual smoke tests instead. Faking the GitHub API surface
would test the fake, not the tool.
"""

from __future__ import annotations

import contextlib
import time
import unittest
from datetime import datetime, timezone

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


class GhTimeoutTest(unittest.TestCase):
    def setUp(self):
        self.original = script.subprocess.run
        self.budgets: list[float] = []

    def tearDown(self):
        script.subprocess.run = self.original

    def block(self):
        def blocked(*args, **kwargs):
            self.assertIn("timeout", kwargs, "the call must be bounded")
            self.budgets.append(kwargs["timeout"])
            raise script.subprocess.TimeoutExpired(cmd="gh", timeout=kwargs["timeout"])

        script.subprocess.run = blocked

    def test_a_blocked_gh_call_fails_rather_than_hanging(self):
        # Regression: run_gh had no timeout, so cmd_wait could sail past the
        # deadline it was given and never emit the timeout result that says
        # what it was still waiting on.
        self.block()
        with self.assertRaises(script.GhUnavailable) as caught:
            script.run_gh(["api", "graphql"])
        self.assertIn("did not return", str(caught.exception))
        self.assertEqual(self.budgets, [float(script.GH_TIMEOUT_S)])

    def test_the_wait_budget_is_shared_across_the_calls_in_a_poll(self):
        # Regression: a fixed per-call cap let `wait --timeout-seconds 1` spend
        # the full cap on its first call, and a paginated fingerprint makes
        # several such calls per poll. One call proves only that a cap exists —
        # the budget has to *shrink* across successive calls to bound the poll.
        consumed: list[float] = []

        def slow(*args, **kwargs):
            consumed.append(kwargs["timeout"])
            time.sleep(0.05)
            raise script.subprocess.CalledProcessError(1, "gh")

        script.subprocess.run = slow
        with script.wait_budget(5):
            for _ in range(3):
                with contextlib.suppress(Exception):
                    script.run_gh(["api", "graphql"])
        self.assertEqual(len(consumed), 3)
        self.assertLessEqual(consumed[0], 5.0)
        self.assertLess(consumed[-1], consumed[0], "the budget must shrink as it is spent")

    def test_an_exhausted_budget_does_not_start_the_call(self):
        self.block()
        with script.wait_budget(0), self.assertRaises(script.GhUnavailable) as caught:
            script.run_gh(["api", "graphql"])
        self.assertIn("no time left", str(caught.exception))
        self.assertEqual(self.budgets, [], "no subprocess may be started")


class ReactRailTest(unittest.TestCase):
    """👎 is bot-only. The module otherwise avoids faking the API, but a rail
    that is only documented is not a rail — this asserts no POST is even
    attempted, which needs the author lookup stubbed."""

    def setUp(self):
        self.posted: list[list[str]] = []
        self.original_json, self.original_run = script.gh_json, script.run_gh
        script.run_gh = lambda args: self.posted.append(args) or ""

    def tearDown(self):
        script.gh_json, script.run_gh = self.original_json, self.original_run

    def stub_author(self, user: dict | None):
        script.gh_json = lambda args: {"user": user}

    def test_thumbs_down_on_a_human_is_refused(self):
        self.stub_author({"type": "User", "login": "octocat"})
        with self.assertRaises(SystemExit) as caught:
            script.cmd_react("o", "r", "review", 1, "down")
        self.assertIn("octocat", str(caught.exception))
        self.assertEqual(self.posted, [], "no reaction may be posted")

    def test_thumbs_down_on_a_bot_goes_through(self):
        # Assert the content and the target, not just that something was sent:
        # posting +1 for a "down" reaction, or hitting the wrong surface root,
        # would otherwise pass.
        self.stub_author({"type": "Bot", "login": "coderabbitai[bot]"})
        script.cmd_react("o", "r", "review", 7, "down")
        self.assertEqual(len(self.posted), 1)
        args = self.posted[0]
        self.assertIn("content=-1", args)
        self.assertIn("repos/o/r/pulls/comments/7/reactions", args)

    def test_thumbs_up_on_a_human_is_allowed(self):
        # 👍 acknowledges rather than dismisses, so it needs no author check.
        self.stub_author({"type": "User", "login": "octocat"})
        script.cmd_react("o", "r", "issue", 7, "up")
        self.assertEqual(len(self.posted), 1)
        args = self.posted[0]
        self.assertIn("content=+1", args)
        self.assertIn("repos/o/r/issues/comments/7/reactions", args)

    def test_unknown_author_is_refused_rather_than_assumed_a_bot(self):
        self.stub_author(None)
        with self.assertRaises(SystemExit):
            script.cmd_react("o", "r", "review", 1, "down")
        self.assertEqual(self.posted, [])


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


class QuietCreditTest(unittest.TestCase):
    """Arriving after the noise stopped should not cost a settle window."""

    def test_quiet_is_measured_from_the_last_write(self):
        now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(
            script.quiet_seconds("2026-08-09T11:58:00Z", now), 120.0, places=1
        )

    def test_a_future_timestamp_credits_nothing_rather_than_negative(self):
        # Clock skew must not hand out negative quiet, which would push the
        # settle window further out than observing honestly would.
        now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(script.quiet_seconds("2026-08-09T12:05:00Z", now), 0.0)

    def test_unknown_or_unparseable_timestamps_credit_nothing(self):
        now = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(script.quiet_seconds("", now), 0.0)
        self.assertEqual(script.quiet_seconds("not a date", now), 0.0)

    def test_latest_activity_prefers_the_newest_across_fields(self):
        items = [
            {"updated_at": "2026-08-09T10:00:00Z"},
            {"submitted_at": "2026-08-09T11:00:00Z"},
            {"created_at": "2026-08-09T09:00:00Z"},
        ]
        self.assertEqual(script.latest_activity(items), "2026-08-09T11:00:00Z")

    def test_latest_activity_of_nothing_is_empty(self):
        self.assertEqual(script.latest_activity([]), "")

    def test_credited_quiet_reaches_the_done_verdict_immediately(self):
        # A PR whose last comment landed well over a settle window ago is
        # already settled; the state machine should say so on the first poll
        # rather than watching for another 90 seconds to confirm it.
        settle, now = 90, 1000.0
        stable_since = now - script.quiet_seconds(
            "2026-08-09T11:00:00Z", datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
        )
        fingerprint = (1, 0, 0, (), (), ())
        state, _ = script.wait_verdict(
            {"pending": [], "clean": ["ci"], "attention": []},
            fingerprint, fingerprint, min(stable_since, now - settle), now, settle,
        )
        self.assertEqual(state, "done")


class SpeakersTest(unittest.TestCase):
    def test_logins_are_normalized_the_way_expect_bot_spells_them(self):
        items = [
            {"user": {"login": "CodeRabbitAI[bot]"}},
            {"user": {"login": "cubic-dev-ai[bot]"}},
            {"user": {"login": "Misery7100"}},
            {"user": None},
            {},
        ]
        self.assertEqual(
            script.speakers(items), {"coderabbitai", "cubic-dev-ai", "misery7100"}
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
