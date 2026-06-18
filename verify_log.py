"""Public 'recently checked' log for the verify feature (transparency).

Every SUCCESSFUL check (a real verdict — curated or provisional) is recorded
and shown publicly in the last-100 feed. Public-by-default is the policy:
a private check requires the paid tier (future) or a public submission. The
log is a small JSON ring-buffer persisted on the volume so it survives
restarts; the newest entry per repo is kept so the feed shows distinct repos.
"""
from __future__ import annotations

import json
import os
import threading
from collections import deque
from datetime import datetime, timezone

MAX_ENTRIES = 100

_lock = threading.Lock()
_log: deque | None = None
_path: str | None = None


def init(output_dir: str) -> None:
    """Load the persisted feed (idempotent)."""
    global _log, _path
    if _log is not None:
        return
    _path = os.path.join(output_dir, "data", "verify_recent.json")
    try:
        with open(_path, encoding="utf-8") as f:
            items = json.load(f)
        if not isinstance(items, list):
            items = []
    except (OSError, json.JSONDecodeError, TypeError):
        items = []
    _log = deque(items[-MAX_ENTRIES:], maxlen=MAX_ENTRIES)


def record(repo: str, name: str | None, grade: str | None, trusted: bool,
           provisional: bool, stars: int | None) -> None:
    """Append a successful check (deduped by repo, newest wins)."""
    if _log is None:
        return
    entry = {
        "repo": repo,
        "name": name or (repo.split("/")[-1] if repo else repo),
        "grade": grade,
        "trusted": bool(trusted),
        "provisional": bool(provisional),
        "stars": stars,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with _lock:
        kept = [e for e in _log if e.get("repo") != repo]
        _log.clear()
        _log.extend(kept)
        _log.append(entry)
        try:
            os.makedirs(os.path.dirname(_path), exist_ok=True)
            with open(_path, "w", encoding="utf-8") as f:
                json.dump(list(_log), f)
        except OSError:
            pass


def recent(limit: int = MAX_ENTRIES) -> list[dict]:
    """Most-recent-first list of the last successful checks."""
    if _log is None:
        return []
    with _lock:
        return list(_log)[-limit:][::-1]
