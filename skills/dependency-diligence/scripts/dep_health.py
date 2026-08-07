#!/usr/bin/env python3
"""Supporting tool for the dependency-diligence skill: gather step-3 evidence.

Collects the facts a health check needs — release cadence, age, license,
transitive footprint, repository activity — so the evaluation argues from data
instead of impressions. It answers *none* of the questions that matter most:
whether the candidate can live inside your architectural constraints (step 1),
and how much of it you would actually use (step 2). Run those first; this is
only worth running on candidates that survived them.

  dep_health.py requests --ecosystem pypi
  dep_health.py express --ecosystem npm --json
  dep_health.py fastapi --ecosystem pypi --repo tiangolo/fastapi   # + git activity

Registry metadata comes from the public PyPI/npm JSON APIs over stdlib urllib;
`--repo owner/name` adds commit and release recency via `gh` when it is
authenticated. Nothing is installed and nothing is executed.

Exit codes: 0 fetched · 1 usage/network error · 3 package not found.

Everything printed is evidence, not a verdict. The four verdicts — adopt behind
a seam, take the idea not the dep, defer, reject — are yours to record.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

TIMEOUT_S = 20
USER_AGENT = "dep-health-check (agent-skills)"


def fetch_json(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        sys.exit(f"error: {url} returned HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        sys.exit(f"error: could not fetch {url}: {exc}")


def requirement_name(requirement: str) -> str:
    """The bare package name from a PEP 508 string.

    Specifiers need no whitespace (`urllib3<3,>=1.26`), so splitting on spaces
    alone leaves the version attached to the name.
    """
    return re.split(r"[\s<>=!~;,\[(]", requirement.strip(), maxsplit=1)[0]


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def days_since(moment: dt.datetime | None, now: dt.datetime) -> int | None:
    return None if moment is None else (now - moment).days


def summarize_pypi(payload: dict, now: dt.datetime) -> dict:
    info = payload.get("info") or {}
    releases: dict[str, list] = payload.get("releases") or {}
    dated: list[tuple[str, dt.datetime]] = []
    for version, files in releases.items():
        stamps = [parse_iso(f.get("upload_time_iso_8601")) for f in files or []]
        stamps = [s for s in stamps if s]
        if stamps:
            dated.append((version, min(stamps)))
    dated.sort(key=lambda pair: pair[1])

    latest = dated[-1] if dated else None
    year_ago = now - dt.timedelta(days=365)
    requires = info.get("requires_dist") or []
    return {
        "ecosystem": "pypi",
        "name": info.get("name"),
        "latestVersion": info.get("version"),
        "summary": (info.get("summary") or "").strip()[:200],
        "license": (info.get("license") or "").strip()[:80] or _classifier_license(info),
        "homepage": info.get("home_page") or (info.get("project_urls") or {}).get("Homepage"),
        "repository": _pypi_repo(info),
        "requiresPython": info.get("requires_python"),
        "directDependencies": len(requires),
        "dependencyNames": [requirement_name(d) for d in requires][:20],
        "releaseCount": len(dated),
        "firstRelease": dated[0][1].date().isoformat() if dated else None,
        "latestRelease": latest[1].date().isoformat() if latest else None,
        "daysSinceLatestRelease": days_since(latest[1], now) if latest else None,
        "releasesLastYear": sum(1 for _, when in dated if when >= year_ago),
        "yanked": bool(info.get("yanked")),
    }


def _classifier_license(info: dict) -> str:
    for classifier in info.get("classifiers") or []:
        if classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    return ""


def _pypi_repo(info: dict) -> str | None:
    urls = {k.lower(): v for k, v in (info.get("project_urls") or {}).items()}
    for key in ("repository", "source", "source code", "code", "github"):
        if key in urls:
            return urls[key]
    return None


def summarize_npm(payload: dict, now: dt.datetime) -> dict:
    times: dict[str, str] = payload.get("time") or {}
    versions = {v: parse_iso(t) for v, t in times.items() if v not in {"created", "modified"}}
    dated = sorted(((v, t) for v, t in versions.items() if t), key=lambda pair: pair[1])
    latest_tag = (payload.get("dist-tags") or {}).get("latest")
    latest_manifest = (payload.get("versions") or {}).get(latest_tag) or {}
    dependencies = latest_manifest.get("dependencies") or {}
    year_ago = now - dt.timedelta(days=365)
    repository = payload.get("repository")
    if isinstance(repository, dict):
        repository = repository.get("url")
    return {
        "ecosystem": "npm",
        "name": payload.get("name"),
        "latestVersion": latest_tag,
        "summary": (payload.get("description") or "").strip()[:200],
        "license": payload.get("license") if isinstance(payload.get("license"), str) else None,
        "homepage": payload.get("homepage"),
        "repository": repository,
        "directDependencies": len(dependencies),
        "dependencyNames": sorted(dependencies)[:20],
        "releaseCount": len(dated),
        "firstRelease": dated[0][1].date().isoformat() if dated else None,
        "latestRelease": dated[-1][1].date().isoformat() if dated else None,
        "daysSinceLatestRelease": days_since(dated[-1][1], now) if dated else None,
        "releasesLastYear": sum(1 for _, when in dated if when >= year_ago),
        "deprecated": bool(latest_manifest.get("deprecated")),
    }


def repo_activity(repo: str, now: dt.datetime) -> dict | None:
    """Commit/release recency via gh; None when gh is missing or unauthenticated."""
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}", "--jq",
         "{pushed_at:.pushed_at,archived:.archived,openIssues:.open_issues_count,stars:.stargazers_count}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    pushed = parse_iso(data.get("pushed_at"))
    contributors = subprocess.run(
        ["gh", "api", f"repos/{repo}/contributors?per_page=100", "--jq", "length"],
        capture_output=True, text=True,
    )
    return {
        "repo": repo,
        "archived": data.get("archived"),
        "lastPush": pushed.date().isoformat() if pushed else None,
        "daysSinceLastPush": days_since(pushed, now),
        "openIssues": data.get("openIssues"),
        "stars": data.get("stars"),
        "contributors": int(contributors.stdout.strip()) if contributors.returncode == 0
        and contributors.stdout.strip().isdigit() else None,
    }


def observations(summary: dict, activity: dict | None) -> list[str]:
    """Flat statements of fact worth a second look — never a recommendation."""
    notes: list[str] = []
    stale = summary.get("daysSinceLatestRelease")
    if stale is not None and stale > 730:
        notes.append(f"no release in {stale} days — confirm it is finished rather than abandoned")
    if summary.get("releasesLastYear") == 0 and summary.get("releaseCount", 0) > 0:
        notes.append("no releases in the last year")
    if summary.get("yanked") or summary.get("deprecated"):
        notes.append("the latest version is marked yanked/deprecated by its own publisher")
    if not summary.get("license"):
        notes.append("no license metadata — check the repository before adopting")
    if (summary.get("directDependencies") or 0) > 10:
        notes.append(
            f"{summary['directDependencies']} direct dependencies — each is one you adopt without diligence"
        )
    if activity:
        if activity.get("archived"):
            notes.append("the repository is archived")
        if activity.get("contributors") == 1:
            notes.append("a single contributor — bus factor of one")
        pushed = activity.get("daysSinceLastPush")
        if pushed is not None and pushed > 365:
            notes.append(f"no commits in {pushed} days")
    return notes


def render(summary: dict, activity: dict | None, notes: list[str]) -> None:
    print(f"{summary['name']} ({summary['ecosystem']})  latest {summary['latestVersion']}")
    if summary.get("summary"):
        print(f"  {summary['summary']}")
    print(f"\nlicense: {summary.get('license') or '(none declared)'}")
    print(f"repository: {summary.get('repository') or '(not declared)'}")
    print(
        f"releases: {summary['releaseCount']} total, {summary['releasesLastYear']} in the last year, "
        f"latest {summary.get('latestRelease')} ({summary.get('daysSinceLatestRelease')} days ago)"
    )
    print(f"direct dependencies: {summary['directDependencies']}")
    if summary["dependencyNames"]:
        print(f"  {', '.join(summary['dependencyNames'])}")
    if activity:
        print(
            f"\nrepository: last push {activity.get('lastPush')} "
            f"({activity.get('daysSinceLastPush')} days ago), "
            f"{activity.get('contributors')} contributor(s), {activity.get('openIssues')} open issues"
            + (", ARCHIVED" if activity.get("archived") else "")
        )
    elif summary.get("repository"):
        print("\nrepository activity: not fetched (pass --repo owner/name with gh authenticated)")

    if notes:
        print("\nworth a second look:")
        for note in notes:
            print(f"  - {note}")
    print(
        "\nThis is step 3 evidence only. The constraint test (can it live inside your "
        "architecture?) and the used-fraction test decide first, and the verdict — adopt "
        "behind a seam / take the idea / defer / reject — is yours to record."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("package")
    parser.add_argument("--ecosystem", choices=("pypi", "npm"), required=True)
    parser.add_argument("--repo", help="owner/name for repository activity via gh")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    if args.ecosystem == "pypi":
        payload = fetch_json(f"https://pypi.org/pypi/{args.package}/json")
        summarize = summarize_pypi
    else:
        payload = fetch_json(f"https://registry.npmjs.org/{args.package}")
        summarize = summarize_npm
    if payload is None:
        print(f"not found in {args.ecosystem}: {args.package}", file=sys.stderr)
        return 3

    summary = summarize(payload, now)
    repo = args.repo
    if not repo and summary.get("repository") and "github.com/" in (summary["repository"] or ""):
        tail = summary["repository"].split("github.com/", 1)[1]
        parts = [p for p in tail.replace(".git", "").split("/") if p]
        repo = "/".join(parts[:2]) if len(parts) >= 2 else None
    activity = repo_activity(repo, now) if repo else None
    notes = observations(summary, activity)

    if args.json:
        print(json.dumps({"summary": summary, "activity": activity, "observations": notes}, indent=2))
    else:
        render(summary, activity, notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
