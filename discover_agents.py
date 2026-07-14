"""
discover_agents.py — search GitHub for new AI agent candidates not yet in agents.json.

Output: candidates.json (if any found) — list of repos passing automated pre-checks.
Prints a summary to stdout.

NEVER auto-adds to agents.json. Discovery proposes; owner decides.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Repos the owner reviewed and rejected — never re-propose them. Keyed by
# lowercase "owner/name"; value records the decision for the audit trail.
# Add entries here whenever a manual-review candidate is declined.
REVIEWED_REJECTED = {
    "netease-youdao/lobsterai": (
        "2026-07-07 owner: rejected — OpenClaw is the execution runtime; "
        "thin-wrapper boundary (see docs/research/new-agent-candidates-2026-07-06.md)"
    ),
    "agentwrapper/agent-orchestrator": (
        "2026-07-07 owner: rejected — supervisory harness; external agents do "
        "the coding, lifecycle management not goal-directed orchestration"
    ),
    "mattpocock/sandcastle": (
        "2026-07-07 owner: rejected — sandbox automation delegating model "
        "interaction to coding-agent CLIs, not an agent framework"
    ),
    # 2026-07-14: the supervisory-harness class. Each of these is popular
    # (10k-30k stars) and resurfaces every sweep, but delegates the actual
    # agent work to an external coding-agent CLI — the same boundary that
    # disqualified agentwrapper/agent-orchestrator above.
    "iofficeai/aionui": (
        "2026-07-14 owner: rejected — desktop GUI wrapping OpenClaw/Claude "
        "Code/Codex; the wrapped CLI is the agent"
    ),
    "bloopai/vibe-kanban": (
        "2026-07-14 owner: rejected — kanban board that dispatches work to "
        "external coding agents; task management, not agent logic"
    ),
    "manaflow-ai/cmux": (
        "2026-07-14 owner: rejected — terminal emulator with tabs for coding "
        "agents; no agent logic of its own"
    ),
    "snarktank/ralph": (
        "2026-07-14 owner: rejected — loop that re-invokes Claude Code until a "
        "PRD is done; the loop is a harness, the CLI is the agent"
    ),
    "stablyai/orca": (
        "2026-07-14 owner: rejected — ADE for running a fleet of external "
        "coding agents in parallel; supervisory harness"
    ),
    "superset-sh/superset": (
        "2026-07-14 owner: rejected — editor for running many Claude Code/Codex "
        "instances; supervisory harness"
    ),
}

# Topics to query (one request each)
TOPICS = [
    "ai-agent",
    "coding-agent",
    "llm-agent",
    "autonomous-agent",
    "ai-coding-assistant",
    "agent-framework",
    "multi-agent",
    "agentic",
    "mcp-server",
    "mcp-servers",
    "model-context-protocol",
]

# Keyword searches (description field)
KEYWORDS = [
    '"AI agent" in:description',
    '"coding agent" in:description',
    '"autonomous agent" in:description',
    '"MCP server" in:description',
]

MIN_STARS = 500
SLEEP_BETWEEN = 3  # seconds between API calls (Search API: 30 req/min)
OUTPUT_PATH = "candidates.json"


def search_repos(query: str) -> list[dict]:
    """Run one GitHub search query, returning up to 100 results."""
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    full_query = f"{query} stars:>{MIN_STARS} pushed:>{one_year_ago}"
    params = {
        "q": full_query,
        "sort": "stars",
        "order": "desc",
        "per_page": 100,
    }
    try:
        r = requests.get(
            f"{GITHUB_API}/search/repositories",
            headers=HEADERS,
            params=params,
            timeout=20,
        )
        if r.status_code == 422:
            print(f"  WARN: invalid query [{query}] — skipped")
            return []
        r.raise_for_status()
        items = r.json().get("items", [])
        return items
    except Exception as e:
        print(f"  WARN: search failed [{query}]: {e}")
        return []


def passes_eligibility(repo: dict) -> bool:
    """
    Automated pre-checks (machine-verifiable MUST/SHOULD criteria from Eligibility Spec v1.0):
      §4.1.1 — has declared open-source license
      §4.1.2 — public repository (already guaranteed by Search API)
      §4.2.1 — pushed within last 365 days
      §5.1   — not archived
      §5.3   — not a fork (forks with zero independent commits are disqualifying)
    Plus floor of MIN_STARS stars.
    """
    if repo.get("archived"):
        return False
    if repo.get("fork"):
        return False
    if repo.get("stargazers_count", 0) < MIN_STARS:
        return False
    if repo.get("license") is None:
        return False
    pushed_at = repo.get("pushed_at", "")
    if pushed_at:
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - pushed_dt).days >= 365:
                return False
        except ValueError:
            pass
    return True


def load_existing_repos() -> set[str]:
    """Return set of lowercase repo paths already in agents.json."""
    try:
        with open("agents.json") as f:
            agents = json.load(f)
        return {a["repo"].lower() for a in agents}
    except Exception as e:
        print(f"WARN: could not load agents.json: {e}")
        return set()


def main() -> None:
    existing = load_existing_repos()
    print(f"Loaded {len(existing)} existing agents.\n")

    seen: dict[str, dict] = {}  # full_name.lower() -> repo dict

    # Topic searches
    for topic in TOPICS:
        query = f"topic:{topic}"
        print(f"Searching topic:{topic} ...", end=" ", flush=True)
        items = search_repos(query)
        new = sum(1 for it in items if it["full_name"].lower() not in seen)
        for it in items:
            seen.setdefault(it["full_name"].lower(), it)
        print(f"{len(items)} results, {new} new")
        time.sleep(SLEEP_BETWEEN)

    # Keyword searches
    for kw in KEYWORDS:
        print(f"Searching {kw!r} ...", end=" ", flush=True)
        items = search_repos(kw)
        new = sum(1 for it in items if it["full_name"].lower() not in seen)
        for it in items:
            seen.setdefault(it["full_name"].lower(), it)
        print(f"{len(items)} results, {new} new")
        time.sleep(SLEEP_BETWEEN)

    print(f"\nTotal unique repos found: {len(seen)}")

    # Filter out already-tracked repos and owner-rejected candidates
    novel = {k: v for k, v in seen.items() if k not in existing}
    print(f"New (not in agents.json): {len(novel)}")
    rejected_hits = sorted(k for k in novel if k in REVIEWED_REJECTED)
    if rejected_hits:
        novel = {k: v for k, v in novel.items() if k not in REVIEWED_REJECTED}
        print(f"Skipping {len(rejected_hits)} owner-rejected repo(s): {', '.join(rejected_hits)}")

    # Eligibility pre-checks
    candidates = []
    for repo_dict in novel.values():
        if passes_eligibility(repo_dict):
            lic = repo_dict.get("license") or {}
            candidates.append({
                "repo": repo_dict["full_name"],
                "name": repo_dict["name"],
                "description": (repo_dict.get("description") or "")[:140],
                "stars": repo_dict["stargazers_count"],
                "language": repo_dict.get("language") or "",
                "license": lic.get("spdx_id") or lic.get("name") or "Unknown",
                "last_push": (repo_dict.get("pushed_at") or "")[:10],
                "topics": repo_dict.get("topics", []),
                "url": repo_dict.get("html_url", ""),
            })

    # Sort by stars descending
    candidates.sort(key=lambda x: x["stars"], reverse=True)

    if candidates:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(candidates, f, indent=2)
        print(f"\nWrote {len(candidates)} candidates to {OUTPUT_PATH}.")
    else:
        # Remove stale candidates file if nothing found
        if os.path.exists(OUTPUT_PATH):
            os.remove(OUTPUT_PATH)
        print("\nNo new candidates found.")

    print(f"\nSummary: {len(seen)} found → {len(novel)} novel → {len(candidates)} pass pre-checks.")
    if candidates:
        print("\nTop 5 by stars:")
        for c in candidates[:5]:
            print(f"  {c['repo']:<50} ⭐{c['stars']:,}  {c['language']}")


if __name__ == "__main__":
    main()
