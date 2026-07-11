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

# Self-imposed wall-clock budget (seconds; 0 = unlimited). Hosted runners get
# reclaimed around the ~40-minute mark ("runner received a shutdown signal",
# exit 143) and a reclaimed job loses everything after its last cache write —
# so stop scanning BEFORE that and exit green with what we have. Unscanned
# repos keep their prior values via the merge job and go to the FRONT of the
# next run's queue (stalest-first ordering below).
TIME_BUDGET = int(os.environ.get("SCAN_TIME_BUDGET", "1800"))

# Consecutive per-repo timeouts almost always mean the GitHub API quota is
# exhausted (each stall burns the full SCAN_TIMEOUT of wall clock, which is
# what used to push shards into runner reclaim — observed kills came during
# the 4th-5th consecutive stall on 2026-07-11, so bail after 3). The next
# run starts with these repos via the stalest-first queue.
MAX_CONSECUTIVE_TIMEOUTS = 3


def find_scorecard_bin() -> str:
    """Return path to scorecard binary: ./scorecard first, then PATH."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    found = shutil.which("scorecard")
    if found:
        return found
    sys.exit("ERROR: scorecard binary not found. Place it in the repo root or add to PATH.")


SCAN_TIMEOUT = int(os.environ.get("SCORECARD_TIMEOUT", "300"))


def scan_repo(bin_path: str, owner_repo: str) -> dict | None:
    """Run scorecard against one repo. Returns {score, checks} or None on failure."""
    try:
        result = subprocess.run(
            [bin_path, f"--repo=github.com/{owner_repo}", "--format=json"],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
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
    # Optional: scan one shard of N via --shard K/N (1-based). Used by the
    # matrix CI job to split the full set so no single runner runs long enough
    # to be killed mid-scan. Shards are disjoint and cover every listed repo.
    shard = None
    for arg in sys.argv[1:]:
        if arg.startswith("--repo="):
            single_repo = arg.split("=", 1)[1]
        elif arg == "--repo" and sys.argv.index(arg) + 1 < len(sys.argv):
            single_repo = sys.argv[sys.argv.index(arg) + 1]
        elif arg.startswith("--shard="):
            shard = arg.split("=", 1)[1]
        elif arg == "--shard" and sys.argv.index(arg) + 1 < len(sys.argv):
            shard = sys.argv[sys.argv.index(arg) + 1]

    if shard:
        try:
            k, n = (int(x) for x in shard.split("/", 1))
        except ValueError:
            sys.exit(f"ERROR: --shard expects K/N (e.g. 1/4), got '{shard}'")
        if not (1 <= k <= n):
            sys.exit(f"ERROR: --shard K/N requires 1 <= K <= N, got '{shard}'")
        agents = [a for i, a in enumerate(agents) if i % n == (k - 1)]
        print(f"Shard {k}/{n}: {len(agents)} repos")
    elif single_repo:
        agents = [a for a in agents if a["repo"].lower() == single_repo.lower()]
        if not agents:
            sys.exit(f"ERROR: repo '{single_repo}' not found in agents.json")

    total = len(agents)
    results: dict[str, dict] = {}
    successes = 0

    # Prior cache (CI seeds it from the data branch): merge base for
    # single-repo/full runs, and the staleness index for shard ordering.
    existing: dict[str, dict] = {}
    if os.path.isfile(CACHE_PATH):
        try:
            with open(CACHE_PATH) as f:
                existing = json.load(f).get("agents", {})
        except (json.JSONDecodeError, OSError):
            pass

    # Stalest-first: never-scanned repos lead, then oldest scanned_at. With a
    # time budget in play this is what guarantees coverage converges — a repo
    # skipped by yesterday's cutoff is at the front of today's queue.
    if not single_repo:
        agents.sort(key=lambda a: existing.get(a["repo"], {}).get("scanned_at", ""))

    def write_cache() -> None:
        # A shard writes only its freshly-scanned repos; the CI merge job
        # overlays these onto the prior full cache (freshest-wins). Other
        # modes merge into the on-disk cache so single-repo/full runs are
        # self-contained.
        merged = results if shard else {**existing, **results}
        with open(CACHE_PATH, "w") as f:
            json.dump({"scanned_at": run_start, "agents": merged}, f, indent=2)

    run_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.monotonic()
    consecutive_timeouts = 0
    stopped_early = ""
    print(f"Scorecard scan started at {run_start} — {total} repos\n")

    for i, agent in enumerate(agents, 1):
        repo = agent["repo"]
        print(f"Scanning {i}/{total}: {repo} ...", end=" ", flush=True)

        before = time.monotonic()
        scan_result = scan_repo(bin_path, repo)
        timed_out = scan_result is None and time.monotonic() - before >= SCAN_TIMEOUT - 1

        if scan_result:
            scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            results[repo] = {**scan_result, "scanned_at": scanned_at}
            print(f"done (score: {scan_result['score']})")
            successes += 1
            consecutive_timeouts = 0
            # Persist after every success: a reclaimed runner (exit 143) then
            # costs only the in-flight repo, not the whole shard's work.
            write_cache()
        else:
            print("FAILED — skipped")
            consecutive_timeouts = consecutive_timeouts + 1 if timed_out else 0

        if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
            stopped_early = f"{consecutive_timeouts} consecutive timeouts (API quota likely exhausted)"
            break
        if TIME_BUDGET and time.monotonic() - t0 > TIME_BUDGET and i < total:
            stopped_early = f"time budget ({TIME_BUDGET}s) reached"
            break

        if i < total and not single_repo:
            time.sleep(SLEEP_BETWEEN)

    write_cache()
    if stopped_early:
        print(f"\nStopped early: {stopped_early}. Unscanned repos keep prior "
              f"values and lead the next run's stalest-first queue.")
    print(f"\nDone. {successes}/{total} repos scanned. Cache written to {CACHE_PATH}.")
    # Partial coverage is fine (self-heals stalest-first), but scanning
    # NOTHING means the scan itself is broken (dead token, broken CLI, full
    # quota outage) — fail loudly so the CI alert issue tracks it.
    if total and not successes:
        sys.exit("ERROR: 0 repos scanned this run.")


if __name__ == "__main__":
    main()
