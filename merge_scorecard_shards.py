"""Merge OSSF Scorecard shard caches onto a base cache (freshest-wins per repo).

Usage:
  python merge_scorecard_shards.py base.json shard1.json [shard2.json ...] > merged.json

Each input is {"scanned_at": ..., "agents": {"owner/repo": {score, checks, scanned_at}}}.
For every repo the entry with the newest per-repo scanned_at wins, so the base
preserves repos that no shard refreshed this run (e.g. a shard that failed),
while fresh shard results override stale base entries.
"""

import json
import sys
from datetime import datetime, timezone

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _ts(entry: dict) -> datetime:
    raw = entry.get("scanned_at")
    if not raw:
        return _EPOCH
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH


def merge(paths: list[str]) -> dict:
    merged: dict[str, dict] = {}
    for path in paths:
        with open(path) as f:
            agents = json.load(f).get("agents", {})
        for repo, entry in agents.items():
            cur = merged.get(repo)
            if cur is None or _ts(entry) >= _ts(cur):
                merged[repo] = entry
    return {
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agents": merged,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: merge_scorecard_shards.py base.json [shard.json ...]")
    json.dump(merge(sys.argv[1:]), sys.stdout, indent=2)
