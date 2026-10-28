#!/usr/bin/env python3
"""Alarm when hvtracker.net serves stale data or pages, its refresh scheduler
is down, or its offsite history backup fails.

On 22 Sep 2026 the refresh scheduler never started after a deploy, and the
site served day-old data for 30+ hours while /healthz still answered "ok".
Nothing noticed. From 22 to 28 Oct 2026 every refresh crashed after writing
data.json, so /healthz kept reporting fresh data while every page stayed at
21 Oct (#380). So this also checks the render itself: build_report.json and
sitemap.xml, the render's last write. Run this from CI every few hours; the
workflow opens (or updates) a `stale-data` issue on alert and closes it once
healthy again.

Exit 0 = healthy, 2 = alert, 1 = /healthz could not be read (also an alert).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

SITE = os.environ.get("SITE_URL", "https://hvtracker.net").rstrip("/")
URL = os.environ.get("HEALTHZ_URL", f"{SITE}/healthz")
MAX_AGE_HOURS = float(os.environ.get("MAX_DATA_AGE_HOURS", "12"))
# Two 4 h refresh slots plus an hour: one skipped render stays quiet, the
# second in a row alerts.
MAX_RENDER_AGE_HOURS = float(os.environ.get("MAX_RENDER_AGE_HOURS", "9"))
# Cloudflare blocks the default python-urllib user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (hvtracker-freshness-monitor)"}


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


def _hours_old(value: str | None, parse, now: datetime) -> float | None:
    if not value:
        return None
    try:
        return (now - parse(value)).total_seconds() / 3600
    except (TypeError, ValueError):  # unparseable, or no timezone
        return None


def evaluate_report(report: dict, now: datetime,
                    max_age_hours: float = MAX_RENDER_AGE_HOURS) -> list[str]:
    """Problems in /data/build_report.json, which /healthz cannot see."""
    problems: list[str] = []
    generated = report.get("generated_at")
    age = _hours_old(generated, lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")), now)
    if age is None:
        problems.append(f"site render age is unknown (build_report generated_at: {generated})")
    elif age > max_age_hours:
        problems.append(f"site render is {age:.1f} h old "
                        f"(build_report generated_at {generated}, limit {max_age_hours:g} h)")
    # Missing key (renders before #385) is not an alarm; "disabled" means no
    # bucket is configured.
    archive = report.get("history_archive")
    if isinstance(archive, str) and archive.startswith("failed"):
        problems.append(f"offsite history backup is failing (build_report history_archive: {archive})")
    return problems


def evaluate_sitemap(last_modified: str | None, now: datetime,
                     max_age_hours: float = MAX_RENDER_AGE_HOURS) -> list[str]:
    """build_report.json is written before the pages and sitemap.xml last, so
    a render that dies in between shows up only here."""
    age = _hours_old(last_modified, parsedate_to_datetime, now)
    if age is None:
        return [f"sitemap.xml age is unknown (Last-Modified: {last_modified})"]
    if age > max_age_hours:
        return [f"sitemap.xml, the render's last write, is {age:.1f} h old "
                f"(Last-Modified {last_modified}, limit {max_age_hours:g} h)"]
    return []


def _fetch(url: str, method: str = "GET"):
    req = urllib.request.Request(f"{url}?nocache={int(time.time())}",
                                 headers=HEADERS, method=method)
    return urllib.request.urlopen(req, timeout=30)


def main() -> int:
    try:
        with _fetch(URL) as resp:
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
    now = datetime.now(timezone.utc)
    try:
        with _fetch(f"{SITE}/data/build_report.json") as resp:
            report = json.load(resp)
    except Exception as e:
        problems.append(f"could not read {SITE}/data/build_report.json: {e}")
    else:
        print(f"build_report generated_at: {report.get('generated_at')}  "
              f"history_archive: {report.get('history_archive')}")
        problems += evaluate_report(report, now)
    try:
        with _fetch(f"{SITE}/sitemap.xml", method="HEAD") as resp:
            last_modified = resp.headers.get("Last-Modified")
    except Exception as e:
        problems.append(f"could not read {SITE}/sitemap.xml: {e}")
    else:
        print(f"sitemap.xml Last-Modified: {last_modified}")
        problems += evaluate_sitemap(last_modified, now)
    if problems:
        print("::ALERT::")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("healthy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
