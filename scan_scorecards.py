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

# Fallback breaker for when the rate-limit API can't be consulted: repeated
# timeouts burn SCAN_TIMEOUT of wall clock each, which is what used to push
# runners into reclaim. When the API IS reachable it answers authoritatively
# (see _quota_starved) and this counter never accumulates.
MAX_CONSECUTIVE_TIMEOUTS = 3


def _quota_starved() -> bool | None:
    """After a timeout, ask GitHub whether the token is rate-limited.

    /rate_limit is free (doesn't count against quota). Distinguishes quota
    starvation — where every subsequent repo will stall too, so continuing
    just burns runner wall clock — from a repo-specific slow scan (huge
    repo, wedged check) that should simply be skipped. Returns True/False,
    or None when the check itself fails (caller falls back to counting).
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.github.com/rate_limit",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            remaining = json.load(r).get("resources", {}).get("core", {}).get("remaining")
        if remaining is None:
            return None
        return remaining < 100
    except Exception:
        return None


def find_scorecard_bin() -> str:
    """Return path to scorecard binary: ./scorecard first, then PATH."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    found = shutil.which("scorecard")
    if found:
        return found
    sys.exit("ERROR: scorecard binary not found. Place it in the repo root or add to PATH.")


# 180s: healthy scans finish in 15-60s; anything past 3 minutes never
# completes (observed). Every stalled repo at the front of the queue extends
# the window in which a hosted-runner kill can strike before the first
# success is persisted, so shorter timeouts directly shrink kill exposure
# (2026-07-11: three runs died inside stall zones at minutes 8-25).
SCAN_TIMEOUT = int(os.environ.get("SCORECARD_TIMEOUT", "180"))

# Cap the scorecard subprocess's address space. Huge repos can balloon the
# CLI's memory past the runner's 7GB and take the whole runner down — the
# "shutdown signal" kills repeatedly coincided with the same monster repos
# (mudler/LocalAI twice on 2026-07-10/11). With a cap the CLI dies alone,
# the repo records a failure marker, and the run continues.
SCAN_MEM_LIMIT = int(os.environ.get("SCORECARD_MEM_LIMIT", str(4 * 1024**3)))


def _limit_memory() -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (SCAN_MEM_LIMIT, SCAN_MEM_LIMIT))
    except Exception:
        pass  # non-Linux or restricted environment — run uncapped


def scan_repo(bin_path: str, owner_repo: str) -> dict | None:
    """Run scorecard against one repo. Returns {score, checks} or None on failure."""
    try:
        result = subprocess.run(
            [bin_path, f"--repo=github.com/{owner_repo}", "--format=json"],
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
            preexec_fn=_limit_memory,
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

    # Stalest-first: never-ATTEMPTED repos lead, then oldest attempt. The key
    # is max(scanned_at, scan_failed_at) — failed attempts count as attempts,
    # so a repo that consistently times out (huge repo, wedged check, OSV
    # backend errors) is demoted behind everything healthy instead of
    # permanently blocking the front of the queue (2026-07-11: four such
    # repos deadlocked shard 3 — each run burned its budget on them, they
    # never earned a timestamp, so they led the queue again next run).
    if not single_repo:
        agents.sort(key=lambda a: max(
            existing.get(a["repo"], {}).get("scanned_at") or "",
            existing.get(a["repo"], {}).get("scan_failed_at") or "",
        ))

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
            # Record the failed attempt (keeping any prior data) so the
            # stalest-first ordering demotes this repo for ~a day instead of
            # letting it block the queue front. Site consumers ignore the
            # marker: they key on score/scanned_at.
            failed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            results[repo] = {**(existing.get(repo) or {}), "scan_failed_at": failed_at}
            write_cache()
            if timed_out:
                starved = _quota_starved()
                if starved is True:
                    stopped_early = "GitHub API quota exhausted (rate_limit check)"
                    break
                # Repo-specific timeout (quota is fine): skip it and move on.
                consecutive_timeouts = consecutive_timeouts + 1 if starved is None else 0
            else:
                consecutive_timeouts = 0

        if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
            stopped_early = f"{consecutive_timeouts} consecutive timeouts (rate-limit state unknown)"
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
