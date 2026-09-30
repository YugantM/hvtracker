"""Evidence gate for the drift rename guard (Phase 8).

The GraphQL fetch path never set full_name, so a renamed or transferred repo's
packages were flagged as provenance drift (-5) and skipped by the advisory
check. This re-runs both checks for every listing the live board flags, with
the tracked repo's current name and the package-target resolver, recomputes
every score from the same inputs, and prints what moves. Read-only: GitHub,
registry, OSV and hvtracker.net GETs only.

Usage: python scripts/drift_rename_gate.py
"""
import collections
import copy
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_and_build as fab  # noqa: E402


def main() -> int:
    rows0 = requests.get("https://hvtracker.net/data.json", headers={"User-Agent": "Mozilla/5.0"},
                         timeout=60).json()["agents"]
    with open(os.path.join(os.path.dirname(fab.__file__), "agents.json"), encoding="utf-8") as f:
        roster = json.load(f)

    base = copy.deepcopy(rows0)
    for row in base:
        t = fab.compute_trust_score(row)
        row["trust_confidence"], row["trust_breakdown"] = t["trust_confidence"], t["trust_breakdown"]
        row["trust_score"] = t["trust_score"]
        row["trust_score"] = fab.compute_trust_score_v2(row)["trust_score_v2"]
    off = sum(1 for a, b in zip(base, rows0) if abs(a["trust_score"] - b["trust_score"]) > 0.05)
    print(f"recompute differs from live on {off} of {len(base)} rows (must be 0)")

    flagged = [r for r in rows0 if (r.get("package_provenance_drift") or {}).get("status") == "warning"]
    fixed = {}
    for r in flagged:
        pkgs = dict(npm_package=r.get("npm_package") or "", pypi_package=r.get("pypi_package") or "",
                    crate_package=r.get("crate_package") or "")
        canonical = fab._current_repo_name(r["repo"])
        drift = fab.fetch_package_provenance_drift(r["repo"], tracked_repo_canonical=canonical, **pkgs)
        adv = fab.fetch_known_advisories(r["repo"], tracked_repo_canonical=canonical, **pkgs)
        fixed[r["repo"]] = (drift, adv)
        print(f"  {r['slug']:<28} warning -> {drift['status']:<8} advisories "
              f"{'error' if adv and 'error' in adv else (adv or {}).get('worst') or 'none'}")

    def ranked(rows):
        for r in rows:
            r["evidence_grade"] = fab.grade_for_score(r["trust_score"])
        fab.apply_listing_classes(rows, roster)
        fab.assign_ranks(rows)
        return {r["repo"]: r for r in rows}

    old = ranked(copy.deepcopy(base))
    rows = copy.deepcopy(base)
    for r in rows:
        if r["repo"] in fixed:
            drift, adv = fixed[r["repo"]]
            r["package_provenance_drift"] = drift
            if adv is not None and "error" not in adv:
                r["advisories"] = adv
            t = fab.compute_trust_score(r)
            r["trust_score"] = t["trust_score"]
            r["trust_score"] = fab.compute_trust_score_v2(r)["trust_score_v2"]
    new = ranked(rows)

    for cls in ("agent", "skill"):
        keys = [k for k in old if fab.listing_class(old[k]) == cls]
        changed = [k for k in keys if abs(new[k]["trust_score"] - old[k]["trust_score"]) > 0.05]
        bystanders = [abs(new[k]["rank"] - old[k]["rank"]) for k in keys if k not in changed]
        flips = collections.Counter(f'{old[k]["evidence_grade"]}->{new[k]["evidence_grade"]}'
                                    for k in keys if old[k]["evidence_grade"] != new[k]["evidence_grade"])
        top100 = sum(1 for k in keys if old[k]["rank"] <= 100 and new[k]["rank"] != old[k]["rank"])
        print(f"\n{cls}: {len(changed)} change, flips {dict(flips)}, bystanders max "
              f"{max(bystanders) if bystanders else 0}, mean |drank| "
              f"{sum(bystanders) / len(bystanders) if bystanders else 0:.2f}, top-100 rows moved {top100}")
        for k in sorted(changed, key=lambda k: old[k]["rank"]):
            o, n = old[k], new[k]
            print(f"    {o['name'][:26]:<26} {o['trust_score']:5.1f}->{n['trust_score']:5.1f} "
                  f"{o['evidence_grade']}->{n['evidence_grade']} rank {o['rank']}->{n['rank']}")
    return 1 if off else 0


if __name__ == "__main__":
    sys.exit(main())
