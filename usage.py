"""Durable machine-channel usage counters for the public /live/ surface.

Two things are counted, and the difference matters enough that the public page
labels both:

  * **requests** — raw HTTP hits on a machine surface (``/mcp``, ``/api/v1/*``,
    ``/data/*.json``, exports), counted in app.py's middleware. In stateless
    Streamable HTTP a single real tool call costs ~2-3 requests of protocol
    chatter, so this number OVERSTATES how much work was actually asked for.
  * **tool calls** — recorded from inside the MCP tool functions themselves in
    mcp_server.py, so one increment is exactly one answered question. This is
    the honest headline number.

Counts accumulate in memory and flush to Postgres on a timer (one upsert per
hour-bucket per channel, not one write per request) so the page survives
restarts without putting the request path on the DB. Without a DB the same
rollup persists to a JSON file on the volume, like verify_log.

Nothing user-identifying is stored: no IPs, no arguments, no headers — only
the channel/tool name and the hour it happened in.
"""
from __future__ import annotations

import json
import os
import threading
from collections import deque
from datetime import datetime, timedelta, timezone

import db

# Channels tracked for raw requests. MCP tool calls are stored in the same
# rollup under a "tool:<name>" channel so one table serves both.
REQUEST_CHANNELS = ("mcp", "api_v1", "data_json", "exports")
TOOL_PREFIX = "tool:"

# How many recent tool calls the live feed shows. Tool name + timestamp only.
RECENT_CALLS = 40

# Snapshot cache TTL. The page polls, and every viewer would otherwise hit
# Postgres; the numbers are a rollup, so a few seconds of staleness is free.
_SNAPSHOT_TTL_SECONDS = 10

_lock = threading.Lock()
# {(hour_bucket_iso, channel): count} accumulated since the last flush.
_pending: dict[tuple[str, str], int] = {}
_recent_calls: deque = deque(maxlen=RECENT_CALLS)
_path: str | None = None
_fallback: dict[str, dict[str, int]] | None = None
_snapshot_cache: tuple[float, dict] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _bucket(dt: datetime) -> str:
    return dt.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")


def init(output_dir: str) -> None:
    """Load the file-fallback rollup (idempotent; no-op when Postgres is on)."""
    global _path, _fallback
    if _fallback is not None:
        return
    _path = os.path.join(output_dir, "data", "usage_rollup.json")
    try:
        with open(_path, encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            loaded = {}
    except (OSError, json.JSONDecodeError, TypeError):
        loaded = {}
    _fallback = loaded


def bump(channel: str, n: int = 1) -> None:
    """Count `n` raw requests on a machine channel. Never raises."""
    if not channel:
        return
    key = (_bucket(_now()), channel)
    with _lock:
        _pending[key] = _pending.get(key, 0) + n


def record_tool_call(tool: str) -> None:
    """Count one answered MCP tool call and add it to the live feed.

    Called from inside each tool function, so it counts real work rather than
    protocol chatter. Only the tool name is retained — never its arguments.
    """
    if not tool:
        return
    now = _now()
    key = (_bucket(now), f"{TOOL_PREFIX}{tool}")
    with _lock:
        _pending[key] = _pending.get(key, 0) + 1
        _recent_calls.append({
            "tool": tool,
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })


def flush() -> int:
    """Persist accumulated counts. Returns the number of rows written.

    On failure the pending counts are put BACK so a transient DB blip delays
    the rollup instead of silently losing it.
    """
    with _lock:
        if not _pending:
            return 0
        batch = list(_pending.items())
        _pending.clear()
    rows = [(bucket, channel, count) for (bucket, channel), count in batch]
    try:
        if db.enabled():
            db.add_usage_counts(rows)
        else:
            _flush_to_file(rows)
        return len(rows)
    except Exception:
        with _lock:
            for (bucket, channel), count in batch:
                key = (bucket, channel)
                _pending[key] = _pending.get(key, 0) + count
        return 0


def _flush_to_file(rows: list[tuple[str, str, int]]) -> None:
    """File fallback for local/dev: same hour-bucket rollup as Postgres."""
    if _fallback is None or _path is None:
        return
    for bucket, channel, count in rows:
        slot = _fallback.setdefault(bucket, {})
        slot[channel] = slot.get(channel, 0) + count
    # Keep the file bounded — the live page only ever reads the last 24h, and
    # the all-time totals are carried in a dedicated bucket.
    cutoff = _bucket(_now() - timedelta(days=30))
    totals = _fallback.setdefault("total", {})
    for bucket in [b for b in _fallback if b not in ("total",) and b < cutoff]:
        for channel, count in _fallback.pop(bucket).items():
            totals[channel] = totals.get(channel, 0) + count
    os.makedirs(os.path.dirname(_path), exist_ok=True)
    tmp = f"{_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_fallback, f)
    os.replace(tmp, _path)


def _read_rollup(hours: int) -> tuple[dict[str, int], list[dict]]:
    """(all-time totals by channel, hourly series for the last `hours`)."""
    if db.enabled():
        totals = db.usage_totals() or {}
        series = db.usage_series(hours) or []
        return totals, series
    if _fallback is None:
        return {}, []
    totals: dict[str, int] = {}
    for bucket, counts in _fallback.items():
        for channel, count in counts.items():
            totals[channel] = totals.get(channel, 0) + count
    since = _bucket(_now() - timedelta(hours=hours - 1))
    series = [
        {"bucket": bucket, "counts": dict(counts)}
        for bucket, counts in sorted(_fallback.items())
        if bucket != "total" and bucket >= since
    ]
    return totals, series


def _counting_since() -> str | None:
    """Date (UTC) of the oldest bucket in the rollup, or None when empty."""
    try:
        if db.enabled():
            oldest = db.usage_oldest_bucket()
        else:
            buckets = [b for b in (_fallback or {}) if b != "total"]
            oldest = min(buckets) if buckets else None
        return oldest[:10] if oldest else None
    except Exception:
        return None


def snapshot(hours: int = 24) -> dict:
    """Public payload for /api/v1/usage and the /live/ page.

    Includes counts still pending in memory so the page reacts within a poll
    or two of a real call instead of waiting for the next flush.
    """
    global _snapshot_cache
    now = _now()
    cached = _snapshot_cache
    # Keyed by `hours` as well as time — otherwise a ?hours=1 request would be
    # served from cache to the next ?hours=24 caller.
    if (cached is not None and cached[1].get("window_hours") == hours
            and (now.timestamp() - cached[0]) < _SNAPSHOT_TTL_SECONDS):
        return cached[1]

    totals, series = _read_rollup(hours)
    with _lock:
        pending = dict(_pending)
        recent = list(_recent_calls)[::-1]

    # Fold pending into both the totals and the newest bucket of the series.
    by_bucket = {row["bucket"]: dict(row.get("counts") or {}) for row in series}
    for (bucket, channel), count in pending.items():
        totals[channel] = totals.get(channel, 0) + count
        by_bucket.setdefault(bucket, {})
        by_bucket[bucket][channel] = by_bucket[bucket].get(channel, 0) + count

    # Zero-fill the whole window so the series always has one point per hour.
    # Without this a quiet period collapses the chart to a couple of points and
    # a single busy hour renders as one full-width block.
    top = now.replace(minute=0, second=0, microsecond=0)
    buckets = [_bucket(top - timedelta(hours=h)) for h in range(hours - 1, -1, -1)]

    def _sum(channels, scope) -> int:
        return sum(int(scope.get(c) or 0) for c in channels)

    tools_total = {c[len(TOOL_PREFIX):]: int(n) for c, n in totals.items()
                   if c.startswith(TOOL_PREFIX)}
    tools_window: dict[str, int] = {}
    requests_window = 0
    hourly = []
    for bucket in buckets:
        counts = by_bucket.get(bucket) or {}
        reqs = _sum(REQUEST_CHANNELS, counts)
        calls = 0
        for channel, n in counts.items():
            if channel.startswith(TOOL_PREFIX):
                tool = channel[len(TOOL_PREFIX):]
                tools_window[tool] = tools_window.get(tool, 0) + int(n)
                calls += int(n)
        requests_window += reqs
        hourly.append({"bucket": bucket, "requests": reqs, "tool_calls": calls})

    payload = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": hours,
        # Oldest bucket we hold. The machine surfaces served traffic long
        # before this rollup existed, so the totals below are "since we
        # started counting", not "since launch" — say so rather than let the
        # number read as all of history.
        "counting_since": _counting_since(),
        "totals": {
            "tool_calls": sum(tools_total.values()),
            "requests": _sum(REQUEST_CHANNELS, totals),
            "by_channel": {c: int(totals.get(c) or 0) for c in REQUEST_CHANNELS},
            "by_tool": dict(sorted(tools_total.items(), key=lambda kv: -kv[1])),
        },
        "window": {
            "tool_calls": sum(tools_window.values()),
            "requests": requests_window,
            "by_tool": dict(sorted(tools_window.items(), key=lambda kv: -kv[1])),
            "hourly": hourly,
        },
        "recent_calls": recent,
        # Stated on the page so "requests" is never read as "tool calls".
        "note": ("`requests` counts raw HTTP hits on the machine surfaces; one "
                 "MCP tool call costs several in stateless mode. `tool_calls` "
                 "counts answered tool invocations and is the real workload."),
    }
    _snapshot_cache = (now.timestamp(), payload)
    return payload
