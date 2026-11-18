#!/usr/bin/env python3
"""Turn one monthly A2A Agent Card study run into the files its post ships
(Phase 11 L: the A2A census as a monthly dated series).

Input is the study JSON the a2a-card-study workflow pushes to the `data` branch
(a2a-card-study/<date>.json), plus optionally the previous edition's run for the
trend. Writes, into the post's blog_static directory:

  metrics.json  every figure the post quotes: the frame, the study's metrics
                (all hosts and per source) and the change since the previous run
  hosts.csv     one row per host that serves an Agent Card, an AI Catalog or an
                MCP server card, with the checks behind each figure

Usage:
    git show origin/data:a2a-card-study/2026-11-01.json > /tmp/cur.json
    git show origin/data:a2a-card-study/2026-10-07.json > /tmp/prev.json
    python scripts/a2a_census_publish.py /tmp/cur.json --previous /tmp/prev.json \
        --out blog_static/state-of-public-a2a-agents-2026-11
"""
from __future__ import annotations

import argparse
import csv
import json
import os

TREND_KEYS = ("hosts", "reachable", "cards", "v1_valid", "signed", "signed_verified",
              "auth_declared", "auth_required", "ai_catalogs", "ai_catalogs_with_trust_manifest",
              "server_cards_found")

CSV_FIELDS = ("host", "sources", "card_url", "legacy_path_only", "protocol_version", "v1_valid",
              "v1_problems", "interfaces_https", "interfaces_same_site", "auth_types",
              "auth_required", "provider_declared", "skills", "signed", "algs", "key_source",
              "signature_verified", "verify_note", "ai_catalog", "catalog_lists_a2a",
              "trust_manifests", "signed_trust_manifests", "server_cards_checked",
              "server_cards_found")


def _join(values) -> str:
    return ";".join(str(v) for v in values or [])


def host_row(r: dict) -> dict:
    card = r.get("card") or r.get("legacy_card") or {}
    cat = r.get("catalog") or {}
    return {
        "host": r["host"],
        "sources": _join(r.get("sources")),
        "card_url": card.get("card_url", ""),
        "legacy_path_only": bool(r.get("legacy_card") and not r.get("card")),
        "protocol_version": card.get("protocol_version", ""),
        "v1_valid": card.get("v1_valid", ""),
        "v1_problems": _join(card.get("v1_problems")),
        "interfaces_https": card.get("interfaces_https", ""),
        "interfaces_same_site": card.get("interfaces_same_site", ""),
        "auth_types": _join(card.get("auth_types")),
        "auth_required": card.get("auth_required", ""),
        "provider_declared": card.get("provider_declared", ""),
        "skills": card.get("skills", ""),
        "signed": card.get("signed", ""),
        "algs": _join(card.get("algs")),
        "key_source": card.get("key_source") or "",
        "signature_verified": card.get("verified", "") if card.get("signed") else "",
        "verify_note": card.get("verify_note") or "",
        "ai_catalog": bool(cat),
        "catalog_lists_a2a": cat.get("lists_a2a", "") if cat else "",
        "trust_manifests": cat.get("trust_manifests", "") if cat else "",
        "signed_trust_manifests": cat.get("signed_trust_manifests", "") if cat else "",
        "server_cards_checked": r.get("server_cards_checked", 0),
        "server_cards_found": r.get("server_cards_found", 0),
    }


def build(cur: dict, prev: dict | None) -> tuple[dict, list[dict]]:
    rows = cur["rows"]
    cards = [r.get("card") or r.get("legacy_card") for r in rows if r.get("card") or r.get("legacy_card")]
    signed = [c for c in cards if c.get("signed")]
    catalogs = [r["catalog"] for r in rows if r.get("catalog")]
    detail = {
        "unverifiable_no_key_location": sum(1 for c in signed if c.get("key_source") == "kid only"),
        "did_not_verify": sum(1 for c in signed if not c.get("verified") and c.get("key_source") != "kid only"),
        "signature_algorithms": _count(a for c in signed for a in c.get("algs") or []),
        "v1_problems": _count(p for c in cards for p in c.get("v1_problems") or []),
        "zero_skills": sum(1 for c in cards if not c.get("skills")),
        "trust_manifests_total": sum(c.get("trust_manifests", 0) for c in catalogs),
        "signed_trust_manifests_total": sum(c.get("signed_trust_manifests", 0) for c in catalogs),
        "hosts_with_signed_trust_manifests": sum(1 for c in catalogs if c.get("signed_trust_manifests")),
    }
    metrics = {
        "study": cur.get("study"),
        "generated_at": cur.get("generated_at"),
        "finished_at": cur.get("finished_at"),
        "method": cur.get("method"),
        "license": "CC BY 4.0",
        "inputs": cur.get("inputs"),
        "metrics": cur.get("metrics"),
        "detail": detail,
    }
    if prev:
        a, b = prev["metrics"]["all"], cur["metrics"]["all"]
        metrics["previous"] = {"generated_at": prev.get("generated_at"), "inputs": prev.get("inputs"),
                               "all": {k: a.get(k) for k in TREND_KEYS}}
        metrics["change"] = {k: {"from": a.get(k), "to": b.get(k)} for k in TREND_KEYS}
    return metrics, [host_row(r) for r in rows]


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("study")
    ap.add_argument("--previous")
    ap.add_argument("--out", required=True, help="the post's blog_static directory")
    args = ap.parse_args()
    with open(args.study, encoding="utf-8") as f:
        cur = json.load(f)
    prev = None
    if args.previous:
        with open(args.previous, encoding="utf-8") as f:
            prev = json.load(f)
    metrics, rows = build(cur, prev)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(args.out, "hosts.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["host"]))
    print(f"{len(rows)} hosts -> {args.out}/hosts.csv; metrics -> {args.out}/metrics.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
