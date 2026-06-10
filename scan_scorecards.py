"""
scan_scorecards.py — run OSSF Scorecard CLI against all agents in agents.json
and write results to scorecard-cache.json.

Expects:
  - ./scorecard binary in the current directory (or on PATH)
  - GITHUB_TOKEN env var set
  - agents.json in the current directory

Output: scorecard-cache.json
  {
    "scanned_at": "2026-05-28T04:00:00Z",
    "agents": {
      "owner/repo": {
        "score": 7.2,
        "checks": {"Code-Review": 8, "Maintained": 10, ...},
        "scanned_at": "2026-05-28T04:05:12Z"
      },
      ...
    }
  }
"""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

CACHE_PATH = "scorecard-cache.json"
SLEEP_BETWEEN = 1  # seconds between scans — burst throttle courtesy


def find_scorecard_bin() -> str:
    """Return path to scorecard binary: ./scorecard first, then PATH."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    found = shutil.which("scorecard")
    if found:
        return found
    sys.exit("ERROR: scorecard binary not found. Place it in the repo root or add to PATH.")


def scan_repo(bin_path: str, owner_repo: str) -> dict | None:
    """Run scorecard against one repo. Returns {score, checks} or None on failure."""
    try:
        result = subprocess.run(
            [bin_path, f"--repo=github.com/{owner_repo}", "--format=json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"  WARN: non-zero exit for {owner_repo}: {result.stderr[:120].strip()}")
            return None
        data = json.loads(result.stdout)
        score = data.get("score")
        checks = {c["name"]: c.get("score", -1) for c in data.get("checks", [])}
        return {"score": score, "checks": checks}
    except subprocess.TimeoutExpired:
        print(f"  WARN: timeout scanning {owner_repo}")
        return None
    except json.JSONDecodeError as e:
        print(f"  WARN: JSON parse error for {owner_repo}: {e}")
        return None
    except Exception as e:
        print(f"  WARN: unexpected error for {owner_repo}: {e}")
        return None


def main() -> None:
    bin_path = find_scorecard_bin()

    with open("agents.json") as f:
        agents = [a for a in json.load(f) if a.get("listing_status") == "listed"]

    # Optional: scan a single repo via --repo owner/name
    single_repo = None
    for arg in sys.argv[1:]:
        if arg.startswith("--repo="):
            single_repo = arg.split("=", 1)[1]
        elif arg == "--repo" and sys.argv.index(arg) + 1 < len(sys.argv):
            single_repo = sys.argv[sys.argv.index(arg) + 1]

    if single_repo:
        agents = [a for a in agents if a["repo"].lower() == single_repo.lower()]
        if not agents:
            sys.exit(f"ERROR: repo '{single_repo}' not found in agents.json")

    total = len(agents)
    results: dict[str, dict] = {}
    successes = 0

    # Load existing cache so single-repo runs merge into it
    existing: dict[str, dict] = {}
    if os.path.isfile(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                existing = json.load(f).get("agents", {})
        except (json.JSONDecodeError, OSError):
            pass

    run_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Scorecard scan started at {run_start} — {total} repos\n")

    for i, agent in enumerate(agents, 1):
        repo = agent["repo"]
        name = agent.get("name", repo)
        print(f"Scanning {i}/{total}: {repo} ...", end=" ", flush=True)

        scan_result = scan_repo(bin_path, repo)

        if scan_result:
            scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            results[repo] = {**scan_result, "scanned_at": scanned_at}
            print(f"done (score: {scan_result['score']})")
            successes += 1
        else:
            print("FAILED — skipped")

        if i < total and not single_repo:
            time.sleep(SLEEP_BETWEEN)

    merged = {**existing, **results}
    cache = {"scanned_at": run_start, "agents": merged}
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"\nDone. {successes}/{total} repos scanned. Cache written to {CACHE_PATH}.")


if __name__ == "__main__":
    main()
