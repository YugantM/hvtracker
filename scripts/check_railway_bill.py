#!/usr/bin/env python3
"""Project the current Railway billing-cycle spend and flag if it approaches
the Hobby hard cap ($15), which STOPS the services (downtime, not just a big
invoice). Run daily from CI; opens/updates a tracking issue on breach.

Auth: set RAILWAY_TOKEN to a Railway **project token** (dashboard → project →
Settings → Tokens). Account/session tokens expire daily and won't work in CI.
The token is sent as the `Project-Access-Token` header; if that 401s we retry
as `Authorization: Bearer` so a team token also works.

Exit 0 = under threshold, 2 = over threshold (CI treats 2 as "alert"),
1 = could not read usage (auth/network — also worth a nudge, but distinct).
"""
import json
import os
import sys
import urllib.request

PROJECT_ID = os.environ.get("RAILWAY_PROJECT_ID", "336fa70c-21a7-4524-984b-b6035ea42773")
CAP_DOLLARS = float(os.environ.get("RAILWAY_BILL_CAP", "15"))
ALERT_DOLLARS = float(os.environ.get("RAILWAY_BILL_ALERT", "12"))  # warn with headroom
API = "https://backboard.railway.com/graphql/v2"

# Railway Hobby rates → dollars per per-minute integral unit.
MINUTES_PER_MONTH = 730 * 60
RATES = {  # $/unit-month → $/unit-minute
    "MEMORY_USAGE_GB": 10.0 / MINUTES_PER_MONTH,
    "CPU_USAGE": 20.0 / MINUTES_PER_MONTH,
    "DISK_USAGE_GB": 0.15 / MINUTES_PER_MONTH,
}
EGRESS_RATE_PER_GB = 0.05  # NETWORK_TX_GB is a GB total, not an integral


def _query(token):
    q = (
        'query { estimatedUsage(projectId: "%s", measurements: '
        "[MEMORY_USAGE_GB, CPU_USAGE, DISK_USAGE_GB, NETWORK_TX_GB]) "
        "{ measurement estimatedValue } }" % PROJECT_ID
    )
    body = json.dumps({"query": q}).encode()
    for header in ("Project-Access-Token", "Authorization"):
        val = f"Bearer {token}" if header == "Authorization" else token
        req = urllib.request.Request(API, data=body, headers={
            "Content-Type": "application/json",
            # Railway's edge 403s the default python-urllib UA.
            "User-Agent": "hvtracker-bill-monitor/1.0",
            header: val})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read())
            if d.get("data", {}).get("estimatedUsage"):
                return d["data"]["estimatedUsage"]
        except Exception:
            continue
    return None


def main():
    token = os.environ.get("RAILWAY_TOKEN", "").strip()
    if not token:
        print("ERROR: RAILWAY_TOKEN not set")
        return 1
    usage = _query(token)
    if not usage:
        print("ERROR: could not read estimatedUsage (auth/network)")
        return 1
    by = {m["measurement"]: m["estimatedValue"] for m in usage}
    cost = {}
    for meas, rate in RATES.items():
        cost[meas] = by.get(meas, 0.0) * rate
    cost["NETWORK_TX_GB"] = by.get("NETWORK_TX_GB", 0.0) * EGRESS_RATE_PER_GB
    total = sum(cost.values())
    print(f"Projected Railway usage this cycle: ${total:.2f} (cap ${CAP_DOLLARS:.0f})")
    for k, v in sorted(cost.items(), key=lambda x: -x[1]):
        print(f"  {k:16} ${v:5.2f}")
    if total >= ALERT_DOLLARS:
        print(f"::ALERT:: projected ${total:.2f} >= ${ALERT_DOLLARS:.0f} "
              f"(cap ${CAP_DOLLARS:.0f} stops the services)")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
