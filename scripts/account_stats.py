#!/usr/bin/env python3
"""Watchlist funnel numbers: the success metrics in docs/mvp-watchlist-alerts-spec.md.

Reads Postgres directly (needs DATABASE_URL); nothing here is public. Digest
click-through is in GA (utm_campaign=watchlist-digest). Opens are not tracked:
that needs a tracking pixel, which the digests deliberately don't carry.

Usage: DATABASE_URL=... python scripts/account_stats.py [--days 7]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    stats = db.account_stats(args.days)
    if stats is None:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1
    d = stats["window_days"]
    share = (f"{100 * stats['users_watching'] / stats['users']:.0f}%" if stats["users"] else "n/a")
    print(f"users                  {stats['users']}  (+{stats['signups']} in {d}d)")
    print(f"tracking >=1 project   {stats['users_watching']}  ({share} of users)")
    print(f"watch adds             {stats['watch_adds']} in {d}d")
    print(f"alert email opt-ins    {stats['alert_subscribers']}")
    print(f"changes queued         {stats['alerts_queued']} in {d}d")
    print(f"changes emailed        {stats['alerts_emailed']} in {stats['digests_sent']} digest(s), {d}d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
