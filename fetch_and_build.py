#!/usr/bin/env python3
"""Fetch GitHub data for tracked agents and render index.html."""

import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from jinja2 import Environment, FileSystemLoader

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_repo(owner_repo: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner_repo}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def get_commit_activity(owner_repo: str) -> list:
    """Return list of weekly commit-count dicts for the last 52 weeks."""
    url = f"{GITHUB_API}/repos/{owner_repo}/stats/commit_activity"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json() or []
        if r.status_code == 202:
            # GitHub is computing stats asynchronously; wait and retry
            time.sleep(5 * (attempt + 1))
            continue
        # Any other failure: skip gracefully
        return []
    return []


def compute_score(repo: dict, weeks: list) -> float:
    stars = repo["stargazers_count"]
    forks = repo["forks_count"]

    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since = (datetime.now(timezone.utc) - pushed_at).days

    recent_commits = sum(w["total"] for w in weeks[-4:]) if weeks else 0

    # Stars: log scale up to 30 pts (100k stars = 30 pts)
    stars_score = min(30, math.log1p(stars) / math.log1p(100_000) * 30)

    # Freshness: linear decay over 180 days, up to 25 pts
    freshness_score = max(0.0, 25 * (1 - days_since / 180))

    # Activity: log scale commits last 4 weeks, up to 25 pts (100 commits = 25 pts)
    activity_score = min(25, math.log1p(recent_commits) / math.log1p(100) * 25)

    # Community: log scale forks, up to 20 pts (20k forks = 20 pts)
    community_score = min(20, math.log1p(forks) / math.log1p(20_000) * 20)

    return round(stars_score + freshness_score + activity_score + community_score, 1)


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")


def days_ago(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def freshness_class(d: int) -> str:
    if d <= 7:
        return "fresh"
    if d <= 30:
        return "recent"
    if d <= 90:
        return "aging"
    return "stale"


def score_class(s: float) -> str:
    if s >= 70:
        return "score-high"
    if s >= 45:
        return "score-mid"
    return "score-low"


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_path = os.path.join(script_dir, "agents.json")

    with open(agents_path) as f:
        agents = json.load(f)

    # De-duplicate by repo path (agents.json may have accidental dupes)
    seen: set[str] = set()
    deduped = []
    for a in agents:
        key = a["repo"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    agents = deduped

    def fetch_one(agent: dict) -> dict | None:
        repo_id = agent["repo"]
        name = agent.get("name", repo_id.split("/")[1])
        try:
            repo = get_repo(repo_id)
        except requests.HTTPError as e:
            print(f"SKIP {repo_id}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"ERROR {repo_id}: {e}", file=sys.stderr)
            return None

        weeks = get_commit_activity(repo_id)
        recent_commits = sum(w["total"] for w in weeks[-4:]) if weeks else 0
        score = compute_score(repo, weeks)
        d = days_ago(repo["pushed_at"])
        print(f"OK  {repo_id:<45} score={score:5.1f}")
        return {
            "name": name,
            "repo": repo_id,
            "url": repo["html_url"],
            "stars": repo["stargazers_count"],
            "stars_fmt": fmt_num(repo["stargazers_count"]),
            "forks": repo["forks_count"],
            "forks_fmt": fmt_num(repo["forks_count"]),
            "last_push": fmt_date(repo["pushed_at"]),
            "days_ago": d,
            "freshness_class": freshness_class(d),
            "weekly_commits": recent_commits,
            "score": score,
            "score_class": score_class(score),
            "description": (repo.get("description") or "")[:120],
            "language": repo.get("language") or "",
            "open_issues": repo.get("open_issues_count", 0),
        }

    rows = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, a): a for a in agents}
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.append(result)

    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    env = Environment(loader=FileSystemLoader(script_dir), autoescape=True)
    tmpl = env.get_template("template.html")
    html = tmpl.render(
        rows=rows,
        updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total=len(rows),
    )

    out_path = os.path.join(script_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nBuilt index.html with {len(rows)} agents.")


if __name__ == "__main__":
    main()
