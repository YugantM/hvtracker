"""
auto_add_agents.py — check OSSF Scorecard for candidates in candidates.json,
then auto-add those with any score to agents.json.

Usage:
    python auto_add_agents.py [--dry-run]

Never removes existing agents. Skips repos already in agents.json.
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

DRY_RUN = "--dry-run" in sys.argv

# Category inference: ordered rules, first match wins
CATEGORY_RULES = [
    (["browser", "computer-use", "web-browser", "computer-use-agent"], "Browser & Computer Use"),
    (["coding-agent", "code-generation", "code-assistant", "ai-coding-assistant", "ai-coding"], "Coding Agents"),
    (["multi-agent", "multi-agent-system"], "Multi-Agent Systems"),
    (["memory", "knowledge-base", "personal-assistant", "long-term-memory"], "Memory & Knowledge"),
    (["workflow", "low-code", "no-code", "pipeline"], "Workflow Platforms"),
    (["llm-gateway", "inference", "observability", "monitoring", "sandbox"], "LLM Gateways & Infra"),
    (["research", "data-extraction", "web-crawler", "web-scraping", "fine-tuning"], "Research & Data"),
    (["agent-framework", "llm-agent", "agentic", "ai-agent", "autonomous-agent"], "Agent Frameworks"),
]

def infer_category(topics: list[str]) -> str:
    topic_set = {t.lower() for t in topics}
    for keywords, category in CATEGORY_RULES:
        if topic_set & set(keywords):
            return category
    return "Agent Frameworks"  # fallback


def fetch_scorecard(owner_repo: str) -> float | None:
    """Try deps.dev then securityscorecards.dev. Return score or None."""
    owner, repo = owner_repo.split("/", 1)

    # Primary: deps.dev
    try:
        r = requests.get(
            f"https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}",
            timeout=10,
        )
        if r.status_code == 200:
            sc = r.json().get("scorecard")
            if sc and sc.get("overallScore") is not None:
                return sc["overallScore"]
    except Exception:
        pass

    # Fallback: securityscorecards.dev
    try:
        r = requests.get(
            f"https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}",
            timeout=10,
        )
        if r.status_code == 200:
            score = r.json().get("score")
            if score is not None:
                return float(score)
    except Exception:
        pass

    return None


def main() -> None:
    with open("candidates.json") as f:
        candidates = json.load(f)

    with open("agents.json") as f:
        agents = json.load(f)

    existing = {a["repo"].lower() for a in agents}
    total = len(candidates)
    passed = []

    print(f"Checking OSSF Scorecard for {total} candidates...\n")

    for i, c in enumerate(candidates, 1):
        repo = c["repo"]
        print(f"[{i}/{total}] {repo:<55}", end=" ", flush=True)

        score = fetch_scorecard(repo)
        if score is not None:
            print(f"✓ score={score}")
            passed.append((c, score))
        else:
            print("— no score")

        if i < total:
            time.sleep(1.2)

    print(f"\n{len(passed)}/{total} candidates have an OSSF Scorecard score.\n")

    if not passed:
        print("Nothing to add.")
        return

    # Sort by score desc
    passed.sort(key=lambda x: x[1], reverse=True)

    added = []
    for c, score in passed:
        if c["repo"].lower() in existing:
            continue  # already tracked
        category = infer_category(c.get("topics", []))
        name = c["name"].replace("-", " ").replace("_", " ").title()
        entry = {"repo": c["repo"], "name": name, "category": category}
        if c.get("npm_package"):
            entry["npm_package"] = c["npm_package"]
        if c.get("pypi_package"):
            entry["pypi_package"] = c["pypi_package"]
        added.append(entry)
        existing.add(c["repo"].lower())

    print(f"Adding {len(added)} new agents to agents.json:\n")
    for e in added:
        print(f"  [{e['category']}] {e['repo']}  ({e['name']})")

    if DRY_RUN:
        print("\n--dry-run: no changes written.")
        return

    agents.extend(added)
    with open("agents.json", "w") as f:
        json.dump(agents, f, indent=2)

    print(f"\nDone. agents.json now has {len(agents)} entries.")


if __name__ == "__main__":
    main()
