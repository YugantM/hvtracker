"""Tiny Redis cache for external API responses used by the generator.

Wraps functions whose results are JSON-serializable. When REDIS_URL is unset
(local dev / CI) the decorator is a transparent pass-through, so behavior is
identical to the pre-migration generator.
"""
from __future__ import annotations

import functools
import json
import os

REDIS_URL = os.environ.get("REDIS_URL", "")

_client = None


def _redis():
    global _client
    if not REDIS_URL:
        return None
    if _client is None:
        import redis  # lazy import
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def cached(prefix: str, ttl: int = 3600, skip_none: bool = False):
    """Cache a function's return value in Redis keyed by its arguments.

    Only the first positional arg (plus any extra args) is used for the key,
    which fits the fetch_* helpers (keyed by owner/repo or package name).

    skip_none: when True, a None result is not cached — used for fetches where
    None means "rate-limited / unavailable" so a transient failure doesn't get
    cached as if it were the real value.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            r = _redis()
            if r is None:
                return fn(*args, **kwargs)
            key = f"hv:{prefix}:" + ":".join(str(a) for a in args)
            try:
                hit = r.get(key)
                if hit is not None:
                    return json.loads(hit)
            except Exception:
                return fn(*args, **kwargs)
            value = fn(*args, **kwargs)
            if skip_none and value is None:
                return value
            try:
                r.setex(key, ttl, json.dumps(value))
            except Exception:
                pass
            return value
        return wrapper
    return decorator
