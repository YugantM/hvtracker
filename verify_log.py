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

import db

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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _persist() -> None:
    """Write the ring-buffer to the volume. Caller must hold _lock."""
    try:
        os.makedirs(os.path.dirname(_path), exist_ok=True)
        with open(_path, "w", encoding="utf-8") as f:
            json.dump(list(_log), f)
    except OSError:
        pass


def record(repo: str, name: str | None, grade: str | None, trusted: bool,
           provisional: bool, stars: int | None) -> None:
    """Append a CLIENT-initiated check (deduped by repo, newest wins).

    Persists to Postgres when configured (Railway); otherwise falls back to the
    on-disk JSON ring-buffer (local/dev).
    """
    if db.enabled():
        try:
            db.record_verify_check(repo, name, grade, trusted, provisional, stars)
            return
        except Exception:
            pass  # fall through to the JSON buffer if the DB write fails
    if _log is None:
        return
    now = _now()
    with _lock:
        prior = next((e for e in _log if e.get("repo") == repo), None)
        entry = {
            "repo": repo,
            "name": name or (prior or {}).get("name")
            or (repo.split("/")[-1] if repo else repo),
            "grade": grade,
            "trusted": bool(trusted),
            "provisional": bool(provisional),
            "stars": stars,
            "checks": int((prior or {}).get("checks") or 0) + 1,
            "checked_at": now,
            "refreshed_at": now,
        }
        kept = [e for e in _log if e.get("repo") != repo]
        _log.clear()
        _log.extend(kept)
        _log.append(entry)
        _persist()


def refresh(repo: str, name: str | None, grade: str | None, trusted: bool,
            stars: int | None) -> None:
    """Re-evaluate an existing entry's data without counting it as a check.

    Mirrors db.refresh_verify_check for the file fallback: updates the verdict
    fields and `refreshed_at`, leaves `checked_at`/`checks`/position alone, and
    never creates an entry.
    """
    if db.enabled():
        try:
            db.refresh_verify_check(repo, name, grade, trusted, stars)
            return
        except Exception:
            pass
    if _log is None:
        return
    with _lock:
        for e in _log:
            if e.get("repo") == repo:
                if name:
                    e["name"] = name
                e["grade"] = grade
                e["trusted"] = bool(trusted)
                e["stars"] = stars
                e["refreshed_at"] = _now()
                _persist()
                return


def recent(limit: int = MAX_ENTRIES) -> list[dict]:
    """Most-recent-first list of the last successful checks."""
    if db.enabled():
        try:
            rows = db.recent_verify_checks(limit)
            if rows is not None:
                return rows
        except Exception:
            pass
    if _log is None:
        return []
    with _lock:
        return list(_log)[-limit:][::-1]
