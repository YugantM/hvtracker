#!/usr/bin/env python3
""""Who ships your MCP servers?" provenance study over the official MCP registry.

Input is a registry pull CSV with the `packages` column (scripts/mcp_registry_pull.py).
The frame is every active server at its latest version.

Frame-wide, with no network:
  * source: what a user can audit (repository, package only, remote only)
  * namespace: for io.github.<owner>/* names (the registry verifies them by GitHub
    login), does that account own the repository the entry declares?

Seeded random sample (--sample servers), network reads only:
  * packages: does each npm/PyPI package's source link point back to the declared
    repository, and is its latest release attested?
  * repositories: does the declared repository exist publicly, is it archived,
    was it pushed in the last 90 days, and does the public OpenSSF Scorecard
    API have a result?

Reads the registry, npm, PyPI, api.scorecard.dev and (only for package links
that name another repository) GitHub's repo endpoint. Writes <out>.json with
the metrics and <out>.csv with one row per sampled server, for the dataset.

Usage:
    python scripts/provenance_study.py ~/hv_marketing/data/mcp-registry-2026-09-30.csv \
        --out /tmp/who-ships --sample 1000

The 2026-09-30 run is published as blog_static/who-ships-your-mcp-servers/
sample.csv and metrics.json.
"""
import argparse
import collections
import concurrent.futures as cf
import csv
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_and_build as fab  # noqa: E402

SEED = 20260930


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    """Share with a 95% Wilson interval, so sample figures are quoted honestly."""
    if not n:
        return {"k": 0, "n": 0, "share": None, "ci95": None}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "share": round(p, 4), "ci95": [round(c - h, 4), round(c + h, 4)]}


def source_kind(r: dict) -> str:
    if r["repo"] or r["non_github_repo"]:
        return "repository"
    if r["packages"]:
        return "package_only"
    return "remote_only" if r["remote_only"] == "yes" else "nothing_declared"


def namespace_kind(r: dict) -> str:
    """io.github.<owner>/* is granted by GitHub login as <owner> (or an org
    member); other namespaces are reverse-DNS domains verified by DNS/HTTP."""
    ns = r["name"].split("/", 1)[0].lower()
    if not ns.startswith("io.github."):
        return "domain"
    if not r["repo"]:
        return "github_no_repo"
    return "github_same_owner" if ns[len("io.github."):] == r["repo"].split("/", 1)[0] else "github_other_owner"


def current_name(repo: str) -> str | None:
    try:
        resp = requests.get(f"https://api.github.com/repos/{repo}", headers=fab.HEADERS, timeout=15)
        return resp.json().get("full_name") if resp.status_code == 200 else None
    except Exception:
        return None


def check_package(repo: str, pkg: str) -> dict:
    registry, name = pkg.split(":", 1)
    if registry == "npm":
        meta = fab.fetch_npm_package_metadata(name)
        attested = (meta.get("dist") or {}).get("attestations") is not None if meta else None
    elif registry == "pypi":
        meta = fab.fetch_pypi_package_metadata(name)
        attested = fab.fetch_pypi_provenance(name) if meta else None
    else:
        return {"package": pkg, "link": "not_checked", "attested": None}
    if meta is None:
        return {"package": pkg, "link": "unpublished", "attested": None}
    target = fab._normalize_github_repo_url(fab._package_source_url(registry, meta))
    if not target:
        link = "missing"
    elif not repo:
        link = "no_repo_declared"
    elif target == repo:
        link = "match"
    elif target.split("/", 1)[0] == repo.split("/", 1)[0]:
        link = "same_owner"
    elif (current_name(target) or "").lower() == (current_name(repo) or "-").lower():
        link = "match"  # one side is an old name GitHub redirects
    else:
        link = "other_repo"
    return {"package": pkg, "link": link, "target": target, "attested": bool(attested)}


def repo_facts(repos: list[str]) -> dict[str, dict | None]:
    """GraphQL, 50 repos per query: None = the declared repo doesn't resolve
    publicly (deleted, private or mistyped)."""
    facts = {}
    for i in range(0, len(repos), 50):
        part = repos[i:i + 50]
        query = "{" + " ".join(
            f'r{j}: repository(owner: {json.dumps(r.split("/", 1)[0])}, name: {json.dumps(r.split("/", 1)[1])})'
            " { pushedAt isArchived isFork }" for j, r in enumerate(part)) + "}"
        data = fab._gql_post(query, {}, fab.HEADERS) or {}
        facts.update({r: data.get(f"r{j}") for j, r in enumerate(part)})
    return facts


def has_scorecard(repo: str) -> bool | None:
    try:
        resp = requests.get(f"https://api.scorecard.dev/projects/github.com/{repo}", timeout=20)
        return resp.status_code == 200 if resp.status_code in (200, 404) else None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--out", required=True, help="output path prefix (.json and .csv are added)")
    ap.add_argument("--sample", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    with open(os.path.expanduser(args.csv), encoding="utf-8") as f:
        raw = [r for r in csv.DictReader(f) if r["status"] == "active"]
    by_name = {}
    for r in raw:
        r["repo"] = fab._normalize_github_repo_url(r["repo_url"]) or ""
        r["non_github_repo"] = bool(r["repo_url"]) and not r["repo"]
        r["packages"] = [p for p in (r.get("packages") or "").split("|") if p]
        by_name[r["name"]] = r
    frame = sorted(by_name.values(), key=lambda r: r["name"])
    print(f"frame: {len(frame)} active servers")

    src = collections.Counter(source_kind(r) for r in frame)
    ns = collections.Counter(namespace_kind(r) for r in frame)
    gh_ns = [r for r in frame if namespace_kind(r) in ("github_same_owner", "github_other_owner")]

    sample = random.Random(SEED).sample(frame, min(args.sample, len(frame)))
    pkg_jobs = [(r["name"], r["repo"], p) for r in sample for p in r["packages"]
                if p.split(":", 1)[0] in ("npm", "pypi")]
    repos = sorted({r["repo"] for r in sample if r["repo"]})
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        pkg_results = list(ex.map(lambda j: (j[0], check_package(j[1], j[2])), pkg_jobs))
        sc = dict(zip(repos, ex.map(has_scorecard, repos)))
    facts = repo_facts(repos)
    live = [f for f in facts.values() if f]
    fresh_cut = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    checked = [p for _, p in pkg_results if p["link"] not in ("unpublished", "not_checked")]
    links = collections.Counter(p["link"] for p in checked)
    sc_known = [v for v in sc.values() if v is not None]

    metrics = {
        "frame": {"servers": len(frame), "source": dict(src), "namespace": dict(ns)},
        "remote_only": wilson(src["remote_only"], len(frame)),
        "no_auditable_source": wilson(src["remote_only"] + src["nothing_declared"], len(frame)),
        "github_namespace_other_owner": wilson(ns["github_other_owner"], len(gh_ns)),
        "sample": {"servers": len(sample), "seed": SEED, "packages_checked": len(checked),
                   "packages_unpublished": sum(1 for _, p in pkg_results if p["link"] == "unpublished"),
                   "repos": len(repos)},
        "package_links": dict(links),
        "package_links_back": wilson(links["match"], len(checked)),
        "package_link_names_other_repo": wilson(links["other_repo"], len(checked)),
        "package_attested": wilson(sum(1 for p in checked if p["attested"]), len(checked)),
        "public_scorecard": wilson(sum(sc_known), len(sc_known)),
        "repo_resolves": wilson(len(live), len(repos)),
        "repo_archived": wilson(sum(1 for f in live if f["isArchived"]), len(live)),
        "repo_fork": wilson(sum(1 for f in live if f["isFork"]), len(live)),
        "repo_pushed_90d": wilson(sum(1 for f in live if (f["pushedAt"] or "") >= fresh_cut), len(live)),
    }
    out = os.path.expanduser(args.out)
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    per_server = collections.defaultdict(list)
    for name, p in pkg_results:
        per_server[name].append(p)
    with open(out + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "repo", "source", "namespace", "repo_resolves", "pushed_at", "public_scorecard",
                    "packages", "package_links", "attested"])
        for r in sorted(sample, key=lambda r: r["name"]):
            ps = per_server.get(r["name"], [])
            f = facts.get(r["repo"]) if r["repo"] else None
            w.writerow([r["name"], r["repo"], source_kind(r), namespace_kind(r),
                        "" if not r["repo"] else bool(f), (f or {}).get("pushedAt") or "",
                        "" if not r["repo"] or sc.get(r["repo"]) is None else sc[r["repo"]],
                        "|".join(p["package"] for p in ps), "|".join(p["link"] for p in ps),
                        "|".join("" if p["attested"] is None else str(p["attested"]) for p in ps)])
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
