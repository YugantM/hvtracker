#!/usr/bin/env python3
"""T0 — pull the official MCP registry into the CSV the rest of the pipeline eats.

This is the step that was missing from the repo: mcp_sweep -> mcp_triage ->
mcp_ingest all start from a `mcp-registry-<date>.csv`, but the first pull
(2026-08-06, 20,326 servers) was done ad hoc. The registry grows ~300
servers/day, so re-pulling is a recurring job, not a one-off.

Two modes:

  --since RFC3339   delta pull via the API's `updated_since` filter. Minutes,
                    not half an hour, and it is what you want on a re-pull.
  (default)         full pull, `?version=latest`, pagination exhausted.

`version=latest` is not optional: without it the API paginates EVERY version of
every server and a single bulk publisher can occupy several consecutive pages.

The endpoint is erratically slow (~0.9s or ~15s, roughly half each), so a full
pull runs ~30 min. Rows are appended and flushed per page — a killed run keeps
what it collected. Costs zero GitHub quota; it never touches github.com.

Usage:
    python3 scripts/mcp_registry_pull.py --since 2026-08-06T00:00:00Z --out delta.csv
    python3 scripts/mcp_registry_pull.py --out ~/hv_marketing/data/mcp-registry-2026-09-01.csv
"""
import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request

API = "https://registry.modelcontextprotocol.io/v0/servers"
FIELDS = ["name", "repo_url", "repo_source", "package_registries",
          "remote_only", "status", "published_at"]


def fetch(params: dict, retries: int = 3) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "hvtracker-registry-pull"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}/{retries - 1} after {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return {}


def flatten(entry: dict) -> dict:
    """One CSV row per server, matching the 2026-08-06 pull's schema exactly."""
    srv = entry.get("server") or {}
    meta = (entry.get("_meta") or {}).get(
        "io.modelcontextprotocol.registry/official", {})
    repo = srv.get("repository") or {}
    pkgs = srv.get("packages") or []
    registries = sorted({p.get("registryType") or "" for p in pkgs} - {""})
    repo_url = (repo.get("url") or "").strip()
    return {
        "name": srv.get("name") or "",
        "repo_url": repo_url,
        "repo_source": repo.get("source") or "",
        "package_registries": "|".join(registries),
        # "remote-only" is the finding that matters: a URL that receives your
        # credentials and context, with no source and no package to audit.
        "remote_only": "yes" if (srv.get("remotes") and not repo_url and not pkgs) else "",
        "status": meta.get("status") or "",
        "published_at": (meta.get("publishedAt") or "")[:10],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output CSV path")
    ap.add_argument("--since", default="",
                    help="RFC3339 timestamp; delta pull of servers updated since then")
    ap.add_argument("--limit", type=int, default=100, help="page size (max 100)")
    ap.add_argument("--max-pages", type=int, default=0, help="stop early (0 = exhaust)")
    args = ap.parse_args()

    params = {"version": "latest", "limit": args.limit}
    if args.since:
        # NOTE: the API forces include_deleted=true whenever updated_since is
        # set, so a delta carries tombstones. Downstream gates on status.
        params["updated_since"] = args.since

    cursor, pages, total = "", 0, 0
    t0 = time.time()
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        while True:
            if cursor:
                params["cursor"] = cursor
            data = fetch(params)
            servers = data.get("servers") or []
            for entry in servers:
                w.writerow(flatten(entry))
            f.flush()
            total += len(servers)
            pages += 1
            print(f"page {pages}: {len(servers)} servers (total {total}, "
                  f"{time.time() - t0:.0f}s)", flush=True)
            cursor = (data.get("metadata") or {}).get("nextCursor") or ""
            if not cursor or not servers:
                break
            if args.max_pages and pages >= args.max_pages:
                print("stopped at --max-pages (pagination NOT exhausted)")
                break

    print(f"\nWrote {total} servers to {args.out} in {time.time() - t0:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
