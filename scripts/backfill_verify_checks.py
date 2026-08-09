#!/usr/bin/env python3
"""One-time correction for verify_checks rows inflated by the nightly refresh.

Until the checked_at/refreshed_at split, the daily verify-feed refresh job
called verify_log.record() for every provisional row. record() means "a client
asked about this repo", so each nightly pass bumped `checks` and restamped
`checked_at` — pinning the same provisional repos to the top of the public
feed with identical timestamps and inflating their check counts by roughly one
per day since the job shipped (2026-06-19, commit 39dd8c8e).

This script estimates and removes the machine-generated portion:

    bot_writes  = whole days between max(first_checked, JOB_START) and now
    real_checks = max(1, checks - bot_writes)

It is an ESTIMATE, not a reconstruction — the individual writes were never
distinguished, so exact human counts are unrecoverable. It is deliberately
conservative: it never drops a row below 1, never touches non-provisional rows
(the job never wrote them), and never invents checks it cannot justify.

`checked_at` is intentionally left alone. It is already wrong for these rows,
but any "corrected" value would be a guess; leaving it lets the rows age
naturally down the feed now that nothing restamps them.

Usage (dry run prints the plan and changes nothing):

    python scripts/backfill_verify_checks.py
    python scripts/backfill_verify_checks.py --apply

Requires DATABASE_URL. Safe to re-run: once `refreshed_at` is set, rows are
skipped, so a second pass cannot double-subtract.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402

# First deploy of the nightly refresh job that mis-recorded refreshes as checks.
JOB_START = datetime(2026, 6, 19, tzinfo=timezone.utc)


def plan() -> list[dict]:
    """Rows needing correction, with the estimated split. Read-only."""
    now = datetime.now(timezone.utc)
    with db._connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT repo, checks, first_checked, checked_at, refreshed_at "
            "FROM verify_checks WHERE provisional = true ORDER BY checks DESC"
        )
        rows = cur.fetchall()

    out = []
    for repo, checks, first_checked, checked_at, refreshed_at in rows:
        if refreshed_at is not None:
            continue  # already corrected by a previous run of this script
        start = max(first_checked or JOB_START, JOB_START)
        bot_writes = max(0, (now - start).days)
        corrected = max(1, int(checks or 1) - bot_writes)
        if corrected == checks:
            continue
        out.append({
            "repo": repo,
            "checks": int(checks or 0),
            "bot_writes": bot_writes,
            "corrected": corrected,
            "checked_at": checked_at,
        })
    return out


def apply(rows: list[dict]) -> None:
    """Write the corrected counts and stamp refreshed_at so re-runs are no-ops."""
    with db._connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "UPDATE verify_checks SET checks = %s, refreshed_at = COALESCE(refreshed_at, checked_at) "
            "WHERE repo = %s",
            [(r["corrected"], r["repo"]) for r in rows],
        )
        conn.commit()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the corrections (default is a dry run)")
    args = ap.parse_args()

    if not db.enabled():
        print("DATABASE_URL is not set — nothing to do.", file=sys.stderr)
        return 1

    rows = plan()
    if not rows:
        print("No provisional rows need correction.")
        return 0

    width = max(len(r["repo"]) for r in rows)
    print(f"{'repo':<{width}}  {'stored':>6}  {'bot':>5}  {'corrected':>9}")
    print("-" * (width + 26))
    for r in rows:
        print(f"{r['repo']:<{width}}  {r['checks']:>6}  {r['bot_writes']:>5}  {r['corrected']:>9}")
    removed = sum(r["checks"] - r["corrected"] for r in rows)
    print("-" * (width + 26))
    print(f"{len(rows)} row(s); {removed} machine-generated check(s) to remove.")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to commit.")
        return 0

    apply(rows)
    print(f"\nApplied to {len(rows)} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
