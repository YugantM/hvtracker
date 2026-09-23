#!/usr/bin/env python3
"""Triage the MCP-registry candidates down to a T3-worthy shortlist.

NOT A TRUST SCORE. `compute_trust_score` needs OSSF Scorecard, provenance and
signed-commit data — Safety (25) and Identity (18), 43 of the 100 points. T1
sweep data can only fill Transparency, Maintenance and Adoption, so a
"HVTrust" computed here would top out near 32/100 and be incomparable to every
published score on the site. Publishing that number would break the one thing
the registry sells: that a score means the same thing everywhere.

What this does instead: apply the inclusion rubric as hard gates, then rank
survivors by a 0–100 `triage_score` built from the SAME curves the real scorer
uses (log1p stars over 100k, 180-day freshness ramp) so the ordering predicts
the real ranking. Its only job is choosing who earns the expensive Scorecard
scan.

Usage:
    python3 scripts/mcp_triage.py
    python3 scripts/mcp_triage.py --top 300 --per-owner 5
"""
import argparse
import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

GH = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", re.I)


def load_registry(path: str) -> dict[str, dict]:
    """repo_key -> registry facts (packages, publishers, server count, status)."""
    out: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = GH.search((row.get("repo_url") or "").strip())
            if not m:
                continue
            key = f"{m.group(1)}/{m.group(2)}".lower()
            e = out.setdefault(key, {"servers": 0, "pkgs": set(), "ns": set(),
                                     "any_active": False, "first_published": ""})
            e["servers"] += 1
            if row.get("package_registries"):
                e["pkgs"].update(p for p in row["package_registries"].split("|") if p)
            e["ns"].add((row.get("name") or "").split("/")[0])
            if row.get("status") == "active":
                e["any_active"] = True
            pub = row.get("published_at") or ""
            if pub and (not e["first_published"] or pub < e["first_published"]):
                e["first_published"] = pub
    return out


def days_since(ts: str | None) -> int:
    if not ts:
        return 9999
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 9999
    return max(0, (datetime.now(timezone.utc) - dt).days)


def triage_score(stars: int, days: int, has_license: bool, pkgs: set) -> float:
    """0–100. Same curves as compute_trust_score, reweighted to what T1 knows.

    Adoption 45 · Maintenance 35 · Transparency 20. Deliberately NOT the
    production weights — those reserve 43 points for evidence we don't have
    yet, and renormalising them here would imply a precision we can't back.
    """
    # Adoption — identical curve to compute_trust_score's stars01, plus a small
    # distribution bonus: shipping a package is real evidence of adoption, and
    # it's what makes T2 download data available later.
    stars01 = math.log1p(max(0, stars)) / math.log1p(100_000)
    adoption = min(1.0, stars01 + (0.15 if pkgs else 0.0)) * 45

    # Maintenance — the production 180-day freshness ramp. No commit data at
    # T1, so freshness carries the whole dimension.
    freshness01 = max(0.0, 1 - days / 180)
    maintenance = freshness01 * 35

    transparency = (20.0 if has_license else 0.0)
    return round(adoption + maintenance + transparency, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    base = os.path.expanduser("~/hv_marketing/data")
    ap.add_argument("--sweep", default=f"{base}/mcp-sweep-t1.json")
    ap.add_argument("--registry", default=f"{base}/mcp-registry-2026-08-06.csv")
    ap.add_argument("--roster", default=os.path.expanduser("~/hvtracker/agents.json"))
    ap.add_argument("--out", default=f"{base}/mcp-shortlist.csv")
    ap.add_argument("--top", type=int, default=300, help="size of the T3 shortlist")
    ap.add_argument("--per-owner", type=int, default=5,
                    help="max repos one GitHub owner may contribute (de-bulk)")
    ap.add_argument("--max-stale-days", type=int, default=365)
    args = ap.parse_args()

    sweep = json.load(open(args.sweep))
    reg = load_registry(args.registry)
    try:
        r = json.load(open(args.roster))
        rows = r if isinstance(r, list) else r.get("agents", r.get("data", []))
        existing = {(a.get("repo") or "").lower().removesuffix(".git") for a in rows}
    except (OSError, json.JSONDecodeError):
        existing = set()

    N = len(sweep)
    gates = Counter()
    survivors = []
    for s in sweep:
        key = f"{s['query_owner']}/{s['query_name']}".lower()
        facts = reg.get(key, {})
        # Hard gates, in reporting order. First failure wins so the funnel
        # sums to N — a repo can fail several at once.
        if not s.get("resolved"):
            gates["repo does not resolve (deleted/renamed/private)"] += 1
            continue
        if s.get("is_private"):
            gates["private"] += 1
            continue
        if s.get("is_disabled"):
            gates["disabled"] += 1
            continue
        if s.get("is_empty"):
            gates["empty repo"] += 1
            continue
        if s.get("archived"):
            gates["archived (rubric: non-archived required)"] += 1
            continue
        if s.get("is_fork"):
            gates["fork (no original agent logic)"] += 1
            continue
        if not s.get("license"):
            gates["no OSI license (rubric hard requirement)"] += 1
            continue
        d = days_since(s.get("pushed_at"))
        if d > args.max_stale_days:
            gates[f"no push in >{args.max_stale_days}d"] += 1
            continue
        if key in existing:
            gates["already in roster"] += 1
            continue

        repo = (s.get("repo") or key)
        survivors.append({
            "repo": repo,
            "triage_score": triage_score(s.get("stars") or 0, d,
                                         bool(s.get("license")), facts.get("pkgs", set())),
            "stars": s.get("stars") or 0,
            "days_since_push": d,
            "license": s.get("license"),
            "language": s.get("language"),
            "packages": "|".join(sorted(facts.get("pkgs", set()))) or "",
            "registry_servers": facts.get("servers", 0),
            "owner": repo.split("/")[0].lower(),
            "renamed": s.get("renamed"),
            "description": (s.get("description") or "")[:160].replace("\n", " "),
        })

    survivors.sort(key=lambda r: -r["triage_score"])

    # De-bulk AFTER ranking: one publisher owns 6.4% of the registry, and an
    # unfiltered top-N would hand them the leaderboard.
    per_owner: dict[str, int] = defaultdict(int)
    shortlist, capped = [], 0
    for r in survivors:
        if per_owner[r["owner"]] >= args.per_owner:
            capped += 1
            continue
        per_owner[r["owner"]] += 1
        shortlist.append(r)
        if len(shortlist) >= args.top:
            break

    print(f"=== FUNNEL: {N:,} swept repos ===")
    for reason, n in gates.most_common():
        print(f"  -{n:>6,}  {reason}")
    print(f"  {'=' * 40}\n  {len(survivors):>7,}  PASS all gates")
    print(f"  {capped:>7,}  deferred by --per-owner {args.per_owner} cap")
    print(f"  {len(shortlist):>7,}  SHORTLIST for T3 Scorecard\n")

    if survivors:
        buckets = Counter()
        for r in survivors:
            buckets["1000+" if r["stars"] >= 1000 else
                    "100-999" if r["stars"] >= 100 else
                    "10-99" if r["stars"] >= 10 else "<10"] += 1
        print("survivors by stars: " + " · ".join(
            f"{k}={buckets[k]:,}" for k in ("1000+", "100-999", "10-99", "<10")))
        print(f"shortlist score range: {shortlist[0]['triage_score']} "
              f"-> {shortlist[-1]['triage_score']}\n")
        print(f"{'score':>6} {'stars':>7} {'days':>5}  repo")
        for r in shortlist[:25]:
            print(f"{r['triage_score']:>6} {r['stars']:>7,} {r['days_since_push']:>5}  "
                  f"{r['repo']}")

    cols = ["repo", "triage_score", "stars", "days_since_push", "license", "language",
            "packages", "registry_servers", "owner", "renamed", "description"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(shortlist)
    full = args.out.replace(".csv", "-all-passing.csv")
    with open(full, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(survivors)
    print(f"\nwrote {args.out} ({len(shortlist):,})")
    print(f"wrote {full} ({len(survivors):,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
