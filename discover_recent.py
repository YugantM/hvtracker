"""
discover_recent.py — find RECENTLY CREATED agent / MCP / skill repos.

discover_agents.py and discover_skills.py both sort by stars, which answers
"what is big" and structurally cannot answer "what is new": a repo published
last week competes against four-year-old projects on a cumulative metric. That
is how deepseek-ai/deepseek-harness (130k stars, three days old) and the class
of fast risers behind it get found only by accident.

This sweep inverts the axis. It searches by `created:>DATE` across the agent,
MCP and skill topic sets, then ranks by **stars per day** rather than stars, so
a two-week-old project with 4k stars outranks a four-year-old one with 40k.

Velocity cuts both ways, and that is deliberate. The same number that surfaces
a real launch also exposes the inorganic ones: 2026-08-10 rejected
sv-number/mcp-server at 492 stars in 3 days with 0 forks, 0 watchers and 1
contributor. So every candidate carries forks/watchers/contributors-adjacent
context, and a `suspect` flag fires when adoption arrives without any of the
engagement that normally comes with it.

Output: recent-candidates.json. Proposes only; never writes agents.json.

Usage:
    python3 discover_recent.py --days 45
    python3 discover_recent.py --days 90 --min-stars 200 --class mcp
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from discover_agents import REVIEWED_REJECTED, passes_eligibility

load_dotenv()

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Topic/keyword sets per artifact class, so one sweep covers the whole board.
QUERIES = {
    "agent": [
        "topic:ai-agent", "topic:ai-agents", "topic:coding-agent",
        "topic:coding-agents", "topic:llm-agent", "topic:llm-agents",
        "topic:autonomous-agent", "topic:autonomous-agents",
        "topic:agent-framework", "topic:multi-agent",
        "topic:multi-agent-systems", "topic:agentic", "topic:agent-harness",
        "topic:agent-orchestration", "topic:claude-code",
        "topic:dsh", "topic:dsh-plugin",
        '"AI agent" in:description', '"coding agent" in:description',
        '"agent harness" in:description',
    ],
    "mcp": [
        "topic:mcp-server", "topic:mcp-servers", "topic:model-context-protocol",
        "topic:mcp", "topic:mcp-client", "topic:mcp-tools",
        '"MCP server" in:description',
    ],
    "skill": [
        "topic:agent-skills", "topic:claude-skills", "topic:claude-code-skills",
        "topic:agent-skill", "topic:claude-plugin", "topic:claude-code-plugin",
        "topic:skill", "topic:agent-plugins",
        '"agent skill" in:description', '"skills for" in:description',
    ],
}

SLEEP_BETWEEN = 3  # Search API: 30 req/min
OUTPUT_PATH = "recent-candidates.json"


def search(query: str, since: str, min_stars: int) -> list[dict]:
    full = f"{query} created:>{since} stars:>{min_stars}"
    try:
        r = requests.get(
            f"{GITHUB_API}/search/repositories",
            headers=HEADERS,
            params={"q": full, "sort": "stars", "order": "desc", "per_page": 100},
            timeout=20,
        )
        if r.status_code == 422:
            print(f"  WARN: invalid query [{query}] — skipped")
            return []
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"  WARN: search failed [{query}]: {e}")
        return []


def age_days(created_at: str) -> float:
    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return max(0.5, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


def load_roster() -> set[str]:
    try:
        with open("agents.json") as f:
            return {a["repo"].lower() for a in json.load(f)}
    except Exception as e:
        print(f"WARN: could not load agents.json: {e}")
        return set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=45, help="only repos created within N days")
    ap.add_argument("--min-stars", type=int, default=100,
                    help="star floor (lower than the agent sweep: new repos have not accumulated)")
    ap.add_argument("--class", dest="cls", choices=[*QUERIES, "all"], default="all")
    args = ap.parse_args()

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    roster = load_roster()
    print(f"Roster: {len(roster)} rows. Looking for repos created since {since} "
          f"with >{args.min_stars} stars.\n")

    classes = list(QUERIES) if args.cls == "all" else [args.cls]
    seen: dict[str, dict] = {}
    hint: dict[str, set] = {}
    for cls in classes:
        for q in QUERIES[cls]:
            items = search(q, since, args.min_stars)
            fresh = sum(1 for it in items if it["full_name"].lower() not in seen)
            for it in items:
                key = it["full_name"].lower()
                seen.setdefault(key, it)
                hint.setdefault(key, set()).add(cls)
            print(f"  [{cls}] {q:<44} {len(items):>3} results, {fresh:>3} new")
            time.sleep(SLEEP_BETWEEN)

    print(f"\nUnique repos: {len(seen)}")
    novel = {k: v for k, v in seen.items() if k not in roster}
    print(f"Not already listed: {len(novel)}")
    rejected = sorted(k for k in novel if k in REVIEWED_REJECTED)
    if rejected:
        novel = {k: v for k, v in novel.items() if k not in REVIEWED_REJECTED}
        print(f"Skipping {len(rejected)} owner-rejected: {', '.join(rejected)}")

    out = []
    for key, repo in novel.items():
        if not passes_eligibility(repo):
            continue
        days = age_days(repo["created_at"])
        stars = repo["stargazers_count"]
        forks = repo.get("forks_count") or 0
        watchers = repo.get("subscribers_count")  # absent on search payloads
        issues = repo.get("open_issues_count") or 0
        # Adoption with no engagement behind it. Real projects at this star
        # level attract forks and issues; a farmed one usually has neither.
        suspect = stars >= 200 and forks <= 2 and issues == 0
        lic = repo.get("license") or {}
        out.append({
            "repo": repo["full_name"],
            "name": repo["name"],
            "description": (repo.get("description") or "")[:160],
            "stars": stars,
            "stars_per_day": round(stars / days, 1),
            "age_days": round(days, 1),
            "forks": forks,
            "open_issues": issues,
            "watchers": watchers,
            "suspect_velocity": suspect,
            "language": repo.get("language") or "",
            "license": lic.get("spdx_id") or lic.get("name") or "Unknown",
            "created": repo["created_at"][:10],
            "last_push": (repo.get("pushed_at") or "")[:10],
            "topics": repo.get("topics", []),
            "class_hint": sorted(hint.get(key, [])),
            "url": repo.get("html_url", ""),
        })

    out.sort(key=lambda x: -x["stars_per_day"])
    with open(OUTPUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {len(out)} candidates to {OUTPUT_PATH}.")
    flagged = [c for c in out if c["suspect_velocity"]]
    if flagged:
        print(f"{len(flagged)} flagged suspect_velocity (stars with no forks/issues) — verify before listing.")
    print(f"\n{'repo':<44}{'stars':>8}{'/day':>9}{'age':>6}  class")
    for c in out[:25]:
        flag = "  ⚠ suspect" if c["suspect_velocity"] else ""
        print(f"{c['repo']:<44}{c['stars']:>8,}{c['stars_per_day']:>9,.0f}{c['age_days']:>6.0f}  "
              f"{','.join(c['class_hint'])}{flag}")


if __name__ == "__main__":
    main()
