"""Evidence gate for scoring known advisories (docs/advisory-scoring-review-2026-09-28.md).

Fetches the live board, runs fetch_known_advisories over every listing with a
package id, recomputes every score from the same inputs, then applies each
candidate rule and prints what moves. Read-only: registry, OSV and
hvtracker.net GETs only.

Usage: python scripts/advisory_scoring_gate.py [--workers 8]
"""
import argparse
import collections
import concurrent.futures as cf
import copy
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_and_build as fab  # noqa: E402

RULES = {
    "R1 cap at C (critical/high)":
        lambda ts, w: min(ts, 64.9) if w in ("CRITICAL", "HIGH") else ts,
    "R2 penalty (-15/-8/-3/-1)":
        lambda ts, w: max(0.0, ts - {"CRITICAL": 15, "HIGH": 8, "MODERATE": 3, "LOW": 1}.get(w, 0)),
    "R3 cap by severity (crit C, high B)":
        lambda ts, w: min(ts, 64.9) if w == "CRITICAL" else (min(ts, 79.9) if w == "HIGH" else ts),
}


def grade(ts: float) -> str:
    return "A" if ts >= 80 else "B" if ts >= 65 else "C" if ts >= 50 else "D"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    rows0 = requests.get("https://hvtracker.net/data.json", headers={"User-Agent": "Mozilla/5.0"},
                         timeout=60).json()["agents"]
    with open(os.path.join(os.path.dirname(fab.__file__), "agents.json"), encoding="utf-8") as f:
        roster = json.load(f)

    def advisories(r):
        return r["repo"], fab.fetch_known_advisories(
            r["repo"], npm_package=r.get("npm_package") or "", pypi_package=r.get("pypi_package") or "",
            crate_package=r.get("crate_package") or "")

    todo = [r for r in rows0 if r.get("npm_package") or r.get("pypi_package") or r.get("crate_package")]
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        adv = dict(ex.map(advisories, todo))
    errors = [k for k, v in adv.items() if v and "error" in v]
    worst = {k: v["worst"] for k, v in adv.items() if v and v.get("found")}
    print(f"{len(todo)} listings with a package; {sum(1 for v in adv.values() if v and 'checked' in v)} "
          f"tied; {len(errors)} errors; {len(worst)} with advisories")

    base = copy.deepcopy(rows0)
    for row in base:
        t = fab.compute_trust_score(row)
        row["trust_confidence"], row["trust_breakdown"] = t["trust_confidence"], t["trust_breakdown"]
        row["trust_score"] = t["trust_score"]
        row["trust_score"] = fab.compute_trust_score_v2(row)["trust_score_v2"]
    drift = sum(1 for a, b in zip(base, rows0) if abs(a["trust_score"] - b["trust_score"]) > 0.05)
    print(f"recompute differs from live on {drift} of {len(base)} rows (must be 0)")

    def ranked(rows):
        for r in rows:
            r["evidence_grade"] = grade(r["trust_score"])
        fab.apply_listing_classes(rows, roster)
        fab.assign_ranks(rows)
        return {r["repo"]: r for r in rows}

    old = ranked(copy.deepcopy(base))
    for name, rule in RULES.items():
        rows = copy.deepcopy(base)
        for r in rows:
            r["trust_score"] = round(rule(r["trust_score"], worst.get(r["repo"])), 1)
        new = ranked(rows)
        print(f"\n== {name}")
        for cls in ("agent", "skill"):
            keys = [k for k in old if fab.listing_class(old[k]) == cls]
            changed = [k for k in keys if abs(new[k]["trust_score"] - old[k]["trust_score"]) > 0.05]
            bystanders = [abs(new[k]["rank"] - old[k]["rank"]) for k in keys if k not in changed]
            flips = collections.Counter(f'{old[k]["evidence_grade"]}->{new[k]["evidence_grade"]}'
                                        for k in keys if old[k]["evidence_grade"] != new[k]["evidence_grade"])
            print(f"  {cls}: {len(changed)} change, flips {dict(flips)}, bystanders max "
                  f"{max(bystanders) if bystanders else 0}")
            for k in sorted(changed, key=lambda k: old[k]["rank"]):
                o, n = old[k], new[k]
                print(f"    {o['name'][:24]:<24} {o['trust_score']:5.1f}->{n['trust_score']:5.1f} "
                      f"{o['evidence_grade']}->{n['evidence_grade']} rank {o['rank']}->{n['rank']} ({worst[k]})")
    return 1 if errors or drift else 0


if __name__ == "__main__":
    sys.exit(main())
