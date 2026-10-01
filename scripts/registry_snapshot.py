#!/usr/bin/env python3
"""Snapshot the official MCP registry entries whose source repo HVTracker scores.

The registry feed (/registry/<policy>/v0.1/...) mirrors these entries with
HVTrust added under `_meta`, so it needs each entry's full server.json, not the
flattened columns mcp_registry_pull.py writes. This pulls every active server at
its latest version from the v0.1 API, keeps the ones whose repository URL is a
roster repo (current name or a `previous_repos` name), and writes them as the
API returned them. Runs daily from .github/workflows/registry-snapshot.yml,
which pushes the file to the `data` branch; the app pulls it before each
refresh. Costs no GitHub quota.

Usage:
    python scripts/registry_snapshot.py --out mcp-registry-snapshot.json
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_and_build as fab  # noqa: E402
from fetch_and_build import _normalize_github_repo_url  # noqa: E402

API = "https://registry.modelcontextprotocol.io/v0.1/servers"
OFFICIAL = "io.modelcontextprotocol.registry/official"


def fetch(params: dict, retries: int = 3) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "hvtracker-registry-snapshot"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}/{retries - 1} after {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return {}


def roster_repos(path: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    return {name.lower() for r in rows for name in [r["repo"], *(r.get("previous_repos") or [])]}


def keep(entry: dict, repos: set[str]) -> bool:
    server = entry.get("server") or {}
    status = ((entry.get("_meta") or {}).get(OFFICIAL) or {}).get("status")
    url = (server.get("repository") or {}).get("url") or ""
    return status == "active" and (_normalize_github_repo_url(url) or "") in repos


def owner_sites(entries: list[dict]) -> dict[str, str]:
    """GitHub profile website of each repo owner behind a domain-namespaced
    entry (com.example/...), for the feed's publisher check. Needs
    GITHUB_TOKEN; without one the map is empty and only repo homepages count."""
    owners = sorted({(_normalize_github_repo_url(e["server"]["repository"]["url"]) or "/").split("/")[0]
                     for e in entries if not e["server"]["name"].lower().startswith("io.github.")} - {""})
    if not fab.TOKEN:
        return {}
    sites = {}
    for i in range(0, len(owners), 50):
        part = owners[i:i + 50]
        query = "{" + " ".join(f"o{j}: repositoryOwner(login: {json.dumps(o)}) "
                               "{ ... on Organization { websiteUrl } ... on User { websiteUrl } }"
                               for j, o in enumerate(part)) + "}"
        data = fab._gql_post(query, {}, fab.HEADERS) or {}
        sites.update({o: (data.get(f"o{j}") or {}).get("websiteUrl") or "" for j, o in enumerate(part)})
    return {o: s for o, s in sites.items() if s}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--roster", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                     "agents.json"))
    args = ap.parse_args()

    repos = roster_repos(args.roster)
    params = {"version": "latest", "limit": 100}
    kept, seen, cursor = [], 0, ""
    while True:
        if cursor:
            params["cursor"] = cursor
        data = fetch(params)
        servers = data.get("servers") or []
        seen += len(servers)
        kept += [e for e in servers if keep(e, repos)]
        cursor = (data.get("metadata") or {}).get("nextCursor") or ""
        if not cursor or not servers:
            break
    if seen < 1000:
        raise SystemExit(f"only {seen} servers came back; refusing to overwrite the snapshot")
    kept.sort(key=lambda e: e["server"]["name"])
    doc = {"pulled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": API,
           "servers_seen": seen, "count": len(kept), "owner_sites": owner_sites(kept), "servers": kept}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(kept)} of {seen} registry servers point at a roster repo "
          f"({len(doc['owner_sites'])} owner websites) -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
