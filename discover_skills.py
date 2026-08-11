"""
discover_skills.py — search GitHub for agent-skill / plugin-bundle candidates.

A sibling of discover_agents.py for the SKILLS class: repos whose artifact an
agent executes (skill definitions, plugin bundles, marketplaces) rather than
repos that are themselves agents.

Two filters, in order:

  1. Eligibility — same machine-verifiable rubric as discover_agents.py
     (licensed, public, not archived, not a fork, pushed < 365d, star floor).

  2. Ripeness — does the repo carry STRUCTURAL evidence of being a skill, and
     how many of the scoring signals would actually fire? Per the #189 lesson,
     a bare CLAUDE.md / AGENTS.md / .claude/ means the authors *develop with* a
     coding agent — it is NOT evidence that the repo ships something an agent
     executes. Only functional paths count.

Output: skills-candidates.json — list of ripe candidates with their evidence
trail and projected signal coverage.

NEVER auto-adds to agents.json. Discovery proposes; owner decides.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

from discover_agents import REVIEWED_REJECTED

load_dotenv()

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

TOPICS = [
    "agent-skills",
    "claude-skills",
    "claude-code-skills",
    "agent-skill",
    "claude-plugin",
    "claude-code-plugin",
    "claude-code-hooks",
    "claude-code-commands",
    "agent-plugin",
    "skills",
]

KEYWORDS = [
    '"agent skills" in:name,description',
    '"claude skills" in:name,description',
    '"skill library" in:description',
    '"plugin marketplace" in:description agent',
]

# Structural evidence that the repo SHIPS something an agent executes.
# Ordered strongest first; a repo needs at least one STRONG or two WIRING hits.
STRONG_EVIDENCE = {
    ".claude-plugin/plugin.json": "ships a Claude Code plugin manifest",
    ".claude-plugin/marketplace.json": "ships a plugin marketplace manifest",
    "SKILL.md": "ships a skill definition (SKILL.md)",
}
WIRING_DIRS = {
    ".claude/skills/": "ships .claude/skills/",
    ".claude/commands/": "ships .claude/commands/",
    ".claude/agents/": "ships .claude/agents/",
    ".claude/hooks/": "ships .claude/hooks/",
    ".gemini/commands/": "ships .gemini/commands/",
    ".gemini/extensions/": "ships .gemini/extensions/",
}
# Present-but-meaningless on their own (#189): developing WITH an agent.
NON_EVIDENCE = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".cursorrules")

PACKAGE_MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "Cargo.toml")

MIN_STARS = 200  # discovery floor; the agent rubric uses 500 — owner sets the bar
SLEEP_BETWEEN = 3
OUTPUT_PATH = "skills-candidates.json"


def search_repos(query: str) -> list[dict]:
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    full_query = f"{query} stars:>{MIN_STARS} pushed:>{one_year_ago}"
    params = {"q": full_query, "sort": "stars", "order": "desc", "per_page": 100}
    try:
        r = requests.get(
            f"{GITHUB_API}/search/repositories", headers=HEADERS, params=params, timeout=20
        )
        if r.status_code == 422:
            print(f"  WARN: invalid query [{query}] — skipped")
            return []
        r.raise_for_status()
        return r.json().get("items", [])
    except Exception as e:
        print(f"  WARN: search failed [{query}]: {e}")
        return []


def passes_eligibility(repo: dict) -> bool:
    """Same machine-verifiable rubric as discover_agents.passes_eligibility."""
    if repo.get("archived") or repo.get("fork"):
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


def fetch_tree(full_name: str, branch: str) -> tuple[list[str], bool]:
    """Return (paths, truncated) for the repo's default branch."""
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{full_name}/git/trees/{branch}",
            headers=HEADERS,
            params={"recursive": "1"},
            timeout=30,
        )
        if r.status_code != 200:
            return [], False
        data = r.json()
        return [e.get("path", "") for e in data.get("tree", [])], bool(data.get("truncated"))
    except Exception:
        return [], False


def signed_commit_ratio(full_name: str) -> float | None:
    """Verified-signature ratio over the last 20 default-branch commits."""
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{full_name}/commits",
            headers=HEADERS,
            params={"per_page": 20},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        commits = r.json()
        if not commits:
            return None
        verified = sum(
            1 for c in commits if (c.get("commit", {}).get("verification") or {}).get("verified")
        )
        return round(verified / len(commits), 2)
    except Exception:
        return None


def classify(record: dict) -> tuple[str, str]:
    """Is the skill the repo's PRODUCT? Returns (class, reason).

    A SKILL.md existing somewhere is not enough. Three exclusions matter:

      mirror     — vendors hundreds of other people's skills. The trust
                   question belongs to the upstream authors, not the mirror;
                   scoring it would launder their provenance into one row.
      list       — awesome-*/curated index. No executable artifact at all.
      incidental — repo is about something else and happens to carry a skill
                   for its own development (the #189 lesson, one level up).
    """
    name = record["repo"].split("/")[-1].lower()
    desc = (record["description"] or "").lower()
    n = record["skill_md_count"]
    ratio = record["skill_ratio"]

    if name.startswith("awesome") or "awesome-" in name:
        return "list", "awesome-list — index, not an artifact"
    if any(p in desc for p in ("curated list", "curated collection", "a list of", "collection of awesome")):
        return "list", "described as a curated list"
    if n > 300:
        return "mirror", f"vendors {n} skills — mirror, provenance belongs upstream"
    if n == 0 and not record["skill_evidence"]:
        return "incidental", "no skill artifact"
    if not record["skills_at_root"] and ratio < 0.01 and record["tree_files"] > 200:
        return "incidental", f"{n} skill file(s) buried in a {record['tree_files']}-file repo"

    if record["has_plugin_manifest"]:
        return "plugin", "ships a plugin/marketplace manifest"
    if n >= 3:
        return "skill_collection", f"authored collection of {n} skills"
    return "single_skill", f"{n} focused skill(s)"


def assess_ripeness(paths: list[str]) -> dict:
    """Structural skill evidence + which scoring signals would fire."""
    evidence, strong, wiring = [], 0, 0

    for path in paths:
        base = path.rsplit("/", 1)[-1]
        for marker, why in STRONG_EVIDENCE.items():
            if path == marker or path.endswith("/" + marker) or base == marker:
                if why not in evidence:
                    evidence.append(why)
                    strong += 1
                break

    for prefix, why in WIRING_DIRS.items():
        if any(p.startswith(prefix) or ("/" + prefix) in p for p in paths):
            evidence.append(why)
            wiring += 1

    skill_files = sum(1 for p in paths if p.rsplit("/", 1)[-1] == "SKILL.md")
    ships_package = any(p in PACKAGE_MANIFESTS for p in paths)
    has_workflows = any(p.startswith(".github/workflows/") for p in paths)
    non_evidence_only = [n for n in NON_EVIDENCE if n in paths] if not evidence else []

    # Projected signal types (mirrors fetch_and_build.py signal_types, max 5).
    # GitHub repo data and supply-chain (OSSF Scorecard runs on any public repo)
    # always apply; HN mentions are configured per-listing, so excluded here.
    projected = 2
    if ships_package:
        projected += 1
    if has_workflows:
        projected += 1

    # Product-shape: is the skill surface at the repo root, or buried?
    skills_at_root = any(
        p.startswith(("skills/", ".claude/skills/", ".claude-plugin/", "plugins/"))
        or p == "SKILL.md"
        for p in paths
    )
    has_plugin_manifest = any(
        p.endswith((".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")) for p in paths
    )

    return {
        "skill_evidence": evidence,
        "evidence_strength": "strong" if strong else ("wiring" if wiring >= 2 else "weak"),
        "skill_md_count": skill_files,
        "tree_files": len(paths),
        "skill_ratio": round(skill_files / len(paths), 4) if paths else 0.0,
        "skills_at_root": skills_at_root,
        "has_plugin_manifest": has_plugin_manifest,
        "ships_package": ships_package,
        "has_workflows": has_workflows,
        "projected_signal_types": projected,
        "projected_coverage_grade": (
            "A" if projected >= 4 else "B" if projected == 3 else "C" if projected == 2 else "D"
        ),
        "non_evidence_only": non_evidence_only,
    }


def load_existing_repos() -> set[str]:
    try:
        with open("agents.json") as f:
            agents = json.load(f)
        return {a["repo"].lower() for a in agents}
    except Exception as e:
        print(f"WARN: could not load agents.json: {e}")
        return set()


SCOREABLE = ("plugin", "skill_collection", "single_skill")


def deep_check(repo: dict) -> dict:
    """Fetch the tree, assess ripeness, classify. One or two API calls."""
    full_name = repo["full_name"]
    paths, truncated = fetch_tree(full_name, repo.get("default_branch") or "main")
    record = {
        "repo": full_name,
        "name": repo["name"],
        "description": (repo.get("description") or "")[:200],
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "last_push": (repo.get("pushed_at") or "")[:10],
        "topics": repo.get("topics", []),
        "url": repo.get("html_url"),
        "tree_truncated": truncated,
        **assess_ripeness(paths),
    }
    record["class"], record["class_reason"] = classify(record)
    if record["class"] in SCOREABLE:
        record["signed_commits_ratio"] = signed_commit_ratio(full_name)
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap repos deep-checked (0 = all)")
    ap.add_argument("--refine", metavar="PATH", help="re-check an existing candidate file")
    args = ap.parse_args()

    if not TOKEN:
        print("ERROR: GITHUB_TOKEN not set — search would be rate-limited to 10/min.")
        sys.exit(1)

    if args.refine:
        with open(args.refine) as f:
            prior = json.load(f)
        items = [
            {
                "full_name": r["repo"],
                "name": r["name"],
                "description": r.get("description"),
                "stargazers_count": r.get("stars", 0),
                "language": r.get("language"),
                "license": {"spdx_id": r.get("license")},
                "pushed_at": r.get("last_push", ""),
                "topics": r.get("topics", []),
                "html_url": r.get("url"),
                "default_branch": None,
            }
            for r in prior
        ]
        print(f"Refining {len(items)} prior candidates.\n")
    else:
        existing = load_existing_repos()
        print(f"Loaded {len(existing)} existing listings.\n")
        seen: dict[str, dict] = {}
        for query in [f"topic:{t}" for t in TOPICS] + KEYWORDS:
            print(f"Searching {query} ...")
            for repo in search_repos(query):
                key = repo["full_name"].lower()
                if key in existing or key in REVIEWED_REJECTED or key in seen:
                    continue
                if passes_eligibility(repo):
                    seen[key] = repo
            time.sleep(SLEEP_BETWEEN)
        print(f"\n{len(seen)} eligible repos not already listed. Deep-checking trees...\n")
        items = sorted(seen.values(), key=lambda r: -r.get("stargazers_count", 0))

    if args.limit:
        items = items[: args.limit]

    ripe, excluded = [], []
    for i, repo in enumerate(items, 1):
        record = deep_check(repo)
        (ripe if record["class"] in SCOREABLE else excluded).append(record)
        print(
            f"  [{i}/{len(items)}] {record['repo']:<46} "
            f"{record['class']:<16} cov={record['projected_coverage_grade']} "
            f"skills={record['skill_md_count']}"
        )

    ripe.sort(key=lambda r: (-r["projected_signal_types"], -r["stars"]))
    with open(OUTPUT_PATH, "w") as f:
        json.dump(ripe, f, indent=2)

    by_class: dict[str, int] = {}
    for r in ripe + excluded:
        by_class[r["class"]] = by_class.get(r["class"], 0) + 1

    print(f"\n{'=' * 70}")
    print(f"SCOREABLE: {len(ripe)}  ·  excluded: {len(excluded)}")
    for k in sorted(by_class, key=lambda k: -by_class[k]):
        mark = "✓" if k in SCOREABLE else "✗"
        print(f"  {mark} {k:<18} {by_class[k]}")
    print(f"\nWritten to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
