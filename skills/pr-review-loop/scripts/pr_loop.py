#!/usr/bin/env python3
"""Supporting tool for the pr-review-loop skill (GitHub via `gh` CLI, stdlib only).

Replaces hand-crafted API calls for the loop's mechanical steps:

  status   <pr>   one-shot snapshot: checks bucketed clean/pending/attention,
                  reviewers discovered (bots vs humans), unresolved thread count
  wait     <pr>   bounded poll until every check completes (step 1)
  collect  <pr>   every review thread (fully paginated, both levels), review
                  bodies, and issue comments, normalized to one JSON doc (step 2)
  react           👍/👎 on a comment, review or issue surface (step 5)
  reply    <pr>   in-thread reply to a review comment (step 5)
  resolve         resolve a review thread by GraphQL thread id (step 5, bots only)

Read subcommands are safe anywhere; react/reply/resolve write to the PR.
All output on stdout is JSON; progress goes to stderr.

Exit codes: 0 ok · 1 usage/gh error · 2 wait saw attention-needed conclusions ·
3 wait timed out with checks still pending.

Requires: `gh` installed and authenticated. Repo comes from the cwd, or
--repo owner/name.

The skill's judgment (verdicts, dedup into findings, human-vs-bot etiquette,
never-merge) stays in SKILL.md — this tool only makes the mechanics reliable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

CLEAN_CONCLUSIONS = {"SUCCESS", "NEUTRAL"}
PER_PAGE = 100

THREADS_QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes { databaseId url body author { login __typename } }
          }
        }
      }
    }
  }
}
"""

THREAD_COMMENTS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { databaseId url body author { login __typename } }
      }
    }
  }
}
"""

RESOLVE_MUTATION = """
mutation($thread: ID!) {
  resolveReviewThread(input: { threadId: $thread }) { thread { id isResolved } }
}
"""


def run_gh(args: list[str]) -> str:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("gh CLI not found — install it and run `gh auth login`")
    if proc.returncode != 0:
        shown = " ".join(args[:4])
        sys.exit(f"`gh {shown} …` failed (rc={proc.returncode}): {proc.stderr.strip()[:600]}")
    return proc.stdout


def gh_json(args: list[str]):
    out = run_gh(args)
    return json.loads(out) if out.strip() else None


def graphql(query: str, str_vars: dict[str, str], int_vars: dict[str, int]):
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in str_vars.items():
        args += ["-f", f"{key}={value}"]
    for key, value in int_vars.items():
        args += ["-F", f"{key}={value}"]
    return gh_json(args)["data"]


def rest_paginated(path: str) -> list:
    items: list = []
    page = 1
    while True:
        batch = gh_json(["api", f"{path}?per_page={PER_PAGE}&page={page}"])
        items.extend(batch)
        if len(batch) < PER_PAGE:
            return items
        page += 1


def resolve_repo(flag: str | None) -> tuple[str, str]:
    if flag:
        if "/" not in flag:
            sys.exit("--repo must be owner/name")
        owner, name = flag.split("/", 1)
        return owner, name
    data = gh_json(["repo", "view", "--json", "owner,name"])
    return data["owner"]["login"], data["name"]


def rest_is_bot(user: dict | None) -> bool:
    user = user or {}
    return user.get("type") == "Bot" or user.get("login", "").endswith("[bot]")


def gql_is_bot(author: dict | None) -> bool:
    author = author or {}
    return author.get("__typename") == "Bot" or author.get("login", "").endswith("[bot]")


def normalize_gql_comment(node: dict) -> dict:
    author = node.get("author") or {}
    return {
        "databaseId": node.get("databaseId"),
        "author": author.get("login"),
        "isBot": gql_is_bot(author),
        "url": node.get("url"),
        "body": node.get("body"),
    }


def collect_threads(owner: str, repo: str, pr: int) -> list[dict]:
    threads: list[dict] = []
    cursor: str | None = None
    while True:
        str_vars = {"owner": owner, "repo": repo}
        if cursor:
            str_vars["after"] = cursor
        conn = graphql(THREADS_QUERY, str_vars, {"pr": pr})["repository"]["pullRequest"]["reviewThreads"]
        for node in conn["nodes"]:
            comments = [normalize_gql_comment(c) for c in node["comments"]["nodes"]]
            inner = node["comments"]["pageInfo"]
            while inner["hasNextPage"]:
                inner_vars = {"id": node["id"], "after": inner["endCursor"]}
                tail = graphql(THREAD_COMMENTS_QUERY, inner_vars, {})["node"]["comments"]
                comments.extend(normalize_gql_comment(c) for c in tail["nodes"])
                inner = tail["pageInfo"]
            threads.append(
                {
                    "threadId": node["id"],
                    "isResolved": node["isResolved"],
                    "isOutdated": node["isOutdated"],
                    "path": node.get("path"),
                    "line": node.get("line"),
                    "comments": comments,
                }
            )
        if not conn["pageInfo"]["hasNextPage"]:
            return threads
        cursor = conn["pageInfo"]["endCursor"]


def collect_all(owner: str, repo: str, pr: int, unresolved_only: bool) -> dict:
    threads = collect_threads(owner, repo, pr)
    if unresolved_only:
        threads = [t for t in threads if not t["isResolved"]]
    reviews = [
        {
            "id": r["id"],
            "author": (r.get("user") or {}).get("login"),
            "isBot": rest_is_bot(r.get("user")),
            "state": r.get("state"),
            "body": r.get("body") or "",
        }
        for r in rest_paginated(f"repos/{owner}/{repo}/pulls/{pr}/reviews")
    ]
    issue_comments = [
        {
            "id": c["id"],
            "author": (c.get("user") or {}).get("login"),
            "isBot": rest_is_bot(c.get("user")),
            "url": c.get("html_url"),
            "body": c.get("body") or "",
        }
        for c in rest_paginated(f"repos/{owner}/{repo}/issues/{pr}/comments")
    ]
    return {"reviewThreads": threads, "reviews": reviews, "issueComments": issue_comments}


def check_snapshot(owner: str, repo: str, pr: int) -> dict:
    view = gh_json(
        ["pr", "view", str(pr), "-R", f"{owner}/{repo}", "--json", "statusCheckRollup,reviewDecision"]
    )
    pending, clean, attention = [], [], []
    for item in view.get("statusCheckRollup") or []:
        if item.get("__typename") == "StatusContext":
            name = item.get("context", "<status>")
            state = item.get("state", "")
            if state in {"PENDING", "EXPECTED"}:
                pending.append(name)
            elif state == "SUCCESS":
                clean.append(name)
            else:
                attention.append({"name": name, "conclusion": state})
            continue
        name = item.get("name", "<check>")
        if item.get("status") != "COMPLETED":
            pending.append(name)
        elif item.get("conclusion") in CLEAN_CONCLUSIONS:
            clean.append(name)
        else:
            attention.append({"name": name, "conclusion": item.get("conclusion")})
    return {"pending": pending, "clean": clean, "attention": attention,
            "reviewDecision": view.get("reviewDecision")}


def cmd_status(owner: str, repo: str, pr: int) -> dict:
    snapshot = check_snapshot(owner, repo, pr)
    collected = collect_all(owner, repo, pr, unresolved_only=False)
    # GraphQL logins omit the "[bot]" suffix REST includes — normalize for dedup.
    authors: dict[str, bool] = {}
    for thread in collected["reviewThreads"]:
        for comment in thread["comments"]:
            if comment["author"]:
                authors[comment["author"].removesuffix("[bot]")] = comment["isBot"]
    for item in collected["reviews"] + collected["issueComments"]:
        if item["author"]:
            authors[item["author"].removesuffix("[bot]")] = item["isBot"]
    snapshot["reviewers"] = {
        "bots": sorted(a for a, bot in authors.items() if bot),
        "humans": sorted(a for a, bot in authors.items() if not bot),
    }
    snapshot["unresolvedThreads"] = sum(
        1 for t in collected["reviewThreads"] if not t["isResolved"]
    )
    return snapshot


def cmd_wait(owner: str, repo: str, pr: int, timeout_s: int, interval_s: int) -> int:
    deadline = time.monotonic() + timeout_s
    while True:
        snapshot = check_snapshot(owner, repo, pr)
        if not snapshot["pending"]:
            print(json.dumps(snapshot, indent=2))
            return 2 if snapshot["attention"] else 0
        if time.monotonic() >= deadline:
            print(json.dumps(snapshot, indent=2))
            print(f"timed out with {len(snapshot['pending'])} check(s) still pending", file=sys.stderr)
            return 3
        print(f"waiting: {len(snapshot['pending'])} pending — {', '.join(snapshot['pending'][:5])}",
              file=sys.stderr)
        time.sleep(interval_s)


def cmd_react(owner: str, repo: str, surface: str, comment_id: int, reaction: str) -> dict:
    root = "pulls" if surface == "review" else "issues"
    content = "+1" if reaction == "up" else "-1"
    run_gh(["api", "-X", "POST", f"repos/{owner}/{repo}/{root}/comments/{comment_id}/reactions",
            "-f", f"content={content}"])
    return {"reacted": content, "surface": surface, "commentId": comment_id}


def cmd_reply(owner: str, repo: str, pr: int, comment_id: int, body: str) -> dict:
    created = gh_json(["api", "-X", "POST",
                       f"repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies",
                       "-f", f"body={body}"])
    return {"replied": True, "commentId": comment_id, "url": created.get("html_url")}


def cmd_resolve(thread_id: str) -> dict:
    data = graphql(RESOLVE_MUTATION, {"thread": thread_id}, {})
    return {"resolved": data["resolveReviewThread"]["thread"]["isResolved"], "threadId": thread_id}


def read_body(args: argparse.Namespace) -> str:
    if args.body is not None:
        return args.body
    with open(args.body_file, encoding="utf-8") as handle:
        return handle.read()


def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", help="owner/name (default: repo of the cwd)")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("status", "collect"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("pr", type=int)
    sub.choices["collect"].add_argument("--unresolved-only", action="store_true")

    p = sub.add_parser("wait", parents=[common])
    p.add_argument("pr", type=int)
    p.add_argument("--timeout-seconds", type=int, default=600)
    p.add_argument("--interval-seconds", type=int, default=60)

    p = sub.add_parser("react", parents=[common])
    p.add_argument("--surface", choices=("review", "issue"), required=True)
    p.add_argument("--comment-id", type=int, required=True)
    p.add_argument("--reaction", choices=("up", "down"), required=True)

    p = sub.add_parser("reply", parents=[common])
    p.add_argument("pr", type=int)
    p.add_argument("--comment-id", type=int, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--body")
    group.add_argument("--body-file")

    p = sub.add_parser("resolve", parents=[common])
    p.add_argument("--thread-id", required=True)

    args = parser.parse_args()
    if args.cmd == "resolve":
        print(json.dumps(cmd_resolve(args.thread_id), indent=2))
        return 0

    owner, repo = resolve_repo(args.repo)
    if args.cmd == "status":
        print(json.dumps(cmd_status(owner, repo, args.pr), indent=2))
    elif args.cmd == "collect":
        print(json.dumps(collect_all(owner, repo, args.pr, args.unresolved_only), indent=2))
    elif args.cmd == "wait":
        return cmd_wait(owner, repo, args.pr, args.timeout_seconds, args.interval_seconds)
    elif args.cmd == "react":
        print(json.dumps(cmd_react(owner, repo, args.surface, args.comment_id, args.reaction), indent=2))
    elif args.cmd == "reply":
        print(json.dumps(cmd_reply(owner, repo, args.pr, args.comment_id, read_body(args)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
