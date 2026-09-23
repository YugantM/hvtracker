#!/usr/bin/env python3
"""Alarm when hvtracker.net serves stale data or its refresh scheduler is down.

On 22 Sep 2026 the refresh scheduler never started after a deploy, and the
site served day-old data for 30+ hours while /healthz still answered "ok".
Nothing noticed. Run this from CI every few hours; the workflow opens (or
updates) a `stale-data` issue on alert and closes it once healthy again.

Exit 0 = healthy, 2 = alert, 1 = /healthz could not be read (also an alert).
"""
import json
import os
import sys
import time
import urllib.request

URL = os.environ.get("HEALTHZ_URL", "https://hvtracker.net/healthz")
MAX_AGE_HOURS = float(os.environ.get("MAX_DATA_AGE_HOURS", "12"))


def evaluate(h: dict, max_age_hours: float = MAX_AGE_HOURS) -> list[str]:
    """Human-readable problems with a /healthz payload; empty = healthy."""
    problems: list[str] = []
    # Missing key (older deploys) is not an alarm; an explicit False is.
    if h.get("scheduler_running") is False:
        problems.append(
            f"refresh scheduler is not running (scheduler_error: {h.get('scheduler_error')})"
        )
    age = h.get("data_age_seconds")
    if age is None:
        problems.append("data age is unknown (no parseable `updated` timestamp)")
    elif age > max_age_hours * 3600:
        problems.append(f"data is {age / 3600:.1f} h old (limit {max_age_hours:g} h)")
    if h.get("last_refresh_succeeded") is False:
        problems.append(
            f"last refresh failed (mode {h.get('last_refresh_mode')}: {h.get('last_refresh_error')})"
        )
    return problems


def main() -> int:
    req = urllib.request.Request(
        f"{URL}?nocache={int(time.time())}",
        # Cloudflare blocks the default python-urllib user agent.
        headers={"User-Agent": "Mozilla/5.0 (hvtracker-freshness-monitor)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            h = json.load(resp)
    except Exception as e:
        print(f"ERROR: could not read {URL}: {e}")
        return 1
    age = h.get("data_age_seconds")
    print(f"updated: {h.get('updated')} "
          f"(age {'?' if age is None else f'{age / 3600:.1f} h'})")
    print(f"scheduler_running: {h.get('scheduler_running')}  "
          f"refresh_in_progress: {h.get('refresh_in_progress')}  "
          f"last_refresh: {h.get('last_refresh_mode')} succeeded={h.get('last_refresh_succeeded')}")
    for job, nxt in sorted((h.get("scheduled_jobs") or {}).items()):
        print(f"  next {job}: {nxt}")
    problems = evaluate(h)
    if problems:
        print("::ALERT::")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
