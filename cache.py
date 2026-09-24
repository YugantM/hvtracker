"""Tiny on-disk cache for external API responses used by the generator.

Wraps functions whose results are JSON-serializable. The app's refresh
subprocess sets HVT_CACHE_DIR to a folder on the persistent volume, so repeat
GitHub/npm/PyPI calls across batches are served locally. When it's unset
(tests, one-off local runs) the decorator is a transparent pass-through.

This replaced a Redis service in Sep 2026 (plan 3.5): Redis cost ~$1.55/mo
(11% of the bill) for a cache of ~40 MB that the volume already has room for.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import time

CACHE_DIR = os.environ.get("HVT_CACHE_DIR", "")
# Longest TTL in use is 24 h; anything untouched for two days is dead weight.
_PRUNE_AFTER = 2 * 86400
_pruned = False


def _path(key: str) -> str:
    return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest() + ".json")


def _prune() -> None:
    global _pruned
    _pruned = True
    cutoff = time.time() - _PRUNE_AFTER
    try:
        for name in os.listdir(CACHE_DIR):
            p = os.path.join(CACHE_DIR, name)
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
    except OSError:
        pass


def _get(key: str):
    try:
        with open(_path(key), encoding="utf-8") as f:
            entry = json.load(f)
    except (OSError, ValueError):
        return None
    return entry if entry.get("expires", 0) > time.time() else None


def _set(key: str, value, ttl: int) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not _pruned:
        _prune()
    p = _path(key)
    tmp = f"{p}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"expires": time.time() + ttl, "value": value}, f)
    os.replace(tmp, p)  # atomic: a reader never sees a half-written entry


def cached(prefix: str, ttl: int = 3600, skip_none: bool = False):
    """Cache a function's return value on disk keyed by its arguments.

    Only the positional args are used for the key, which fits the fetch_*
    helpers (keyed by owner/repo or package name).

    skip_none: when True, a None result is not cached — used for fetches where
    None means "rate-limited / unavailable" so a transient failure doesn't get
    cached as if it were the real value.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not CACHE_DIR:
                return fn(*args, **kwargs)
            key = f"hv:{prefix}:" + ":".join(str(a) for a in args)
            hit = _get(key)
            if hit is not None:
                return hit["value"]
            value = fn(*args, **kwargs)
            if skip_none and value is None:
                return value
            try:
                _set(key, value, ttl)
            except (OSError, TypeError, ValueError):
                pass
            return value
        return wrapper
    return decorator
