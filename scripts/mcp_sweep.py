#!/usr/bin/env python3
"""T1 sweep — cheap GitHub metadata for every MCP-registry candidate repo.

Enriches the ~14.7k distinct GitHub repos behind the official MCP registry with
the fields needed to rank and rubric-filter them, WITHOUT disturbing the quota
the agent roster's scorecard scan depends on.

Why GraphQL: the REST route is one request per repo (~14.7k requests, ~3h of a
PAT's 5k/hr). GraphQL batches N repos into one document, so the whole sweep
costs roughly 150 points of the 5k/hr GraphQL budget — a few minutes, ~3% of one
hour. Cost is never estimated here: every response carries `rateLimit.cost` and
`remaining`, and the sweep stops on its own floor.

Quota isolation (the whole point):
  * Reads MCP_GITHUB_TOKEN, NOT GITHUB_TOKEN — so it cannot silently spend the
    scorecard PAT's budget. Pass --allow-shared-token to override deliberately.
  * REST and GraphQL have SEPARATE 5k/hr budgets, so even on a shared token this
    sweep does not touch the REST quota the scorecard CLI burns.
  * Stops when remaining GraphQL points fall below --min-remaining.
  * Writes only its own output file. Touches nothing the render pipeline reads.

Usage:
    python3 scripts/mcp_sweep.py --dry-run            # plan + cost, zero calls
    MCP_GITHUB_TOKEN=ghp_... python3 scripts/mcp_sweep.py
    ... --limit 500                                   # bounded trial run
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

GRAPHQL = "https://api.github.com/graphql"

# Scalar-only fields: no connections, so a batch of N repos costs ~ceil(N/100)
# points. Everything here feeds either the inclusion rubric (licence, archived,
# fork, empty, disabled) or the adoption ranking (stars, pushedAt).
REPO_FIELDS = """
    nameWithOwner
    stargazerCount
    forkCount
    isArchived
    isFork
    isEmpty
    isDisabled
    isPrivate
    pushedAt
    createdAt
    diskUsage
    description
    primaryLanguage { name }
    licenseInfo { spdxId }
    owner { __typename login }
"""


def load_candidates(path: str) -> list[tuple[str, str]]:
    """Distinct (owner, name) pairs from the registry CSV, order preserved."""
    import csv
    import re

    gh = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", re.I)
    seen, out = set(), []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = gh.search((row.get("repo_url") or "").strip())
            if not m:
                continue
            owner, name = m.group(1), m.group(2)
            key = f"{owner}/{name}".lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((owner, name))
    return out


def build_query(batch: list[tuple[str, str]]) -> str:
    """One document, one alias per repo. json.dumps quotes/escapes the args."""
    parts = ["query {", "  rateLimit { cost remaining resetAt }"]
    for i, (owner, name) in enumerate(batch):
        parts.append(
            f"  r{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
            f"{{{REPO_FIELDS}}}"
        )
    parts.append("}")
    return "\n".join(parts)


def post(query: str, token: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "hvtracker-mcp-sweep",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def flatten(node: dict | None, owner: str, name: str) -> dict:
    """One output row. Missing repo => resolved=False (deleted, renamed, private)."""
    if not node:
        return {"query_owner": owner, "query_name": name, "resolved": False}
    lic = (node.get("licenseInfo") or {}).get("spdxId")
    return {
        "query_owner": owner,
        "query_name": name,
        "resolved": True,
        # nameWithOwner is canonical — differs from the query when GitHub
        # followed a rename, which is itself worth knowing.
        "repo": node.get("nameWithOwner"),
        "renamed": (node.get("nameWithOwner") or "").lower() != f"{owner}/{name}".lower(),
        "stars": node.get("stargazerCount"),
        "forks": node.get("forkCount"),
        "archived": node.get("isArchived"),
        "is_fork": node.get("isFork"),
        "is_empty": node.get("isEmpty"),
        "is_disabled": node.get("isDisabled"),
        "is_private": node.get("isPrivate"),
        "pushed_at": node.get("pushedAt"),
        "created_at": node.get("createdAt"),
        "disk_kb": node.get("diskUsage"),
        "description": node.get("description"),
        "language": (node.get("primaryLanguage") or {}).get("name"),
        "license": lic if lic and lic != "NOASSERTION" else None,
        "owner_type": (node.get("owner") or {}).get("__typename"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates",
                    default=os.path.expanduser("~/hv_marketing/data/mcp-registry-2026-08-06.csv"))
    ap.add_argument("--out", default=os.path.expanduser("~/hv_marketing/data/mcp-sweep-t1.json"))
    ap.add_argument("--batch", type=int, default=50,
                    help="repos per GraphQL document (default 50; 100 risks query-size limits)")
    ap.add_argument("--limit", type=int, default=0, help="cap repos processed (0 = all)")
    ap.add_argument("--min-remaining", type=int, default=500,
                    help="stop when GraphQL points remaining drop below this (default 500)")
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--dry-run", action="store_true", help="plan only, zero API calls")
    ap.add_argument("--allow-shared-token", action="store_true",
                    help="permit falling back to GITHUB_TOKEN (default: refuse)")
    args = ap.parse_args()

    cands = load_candidates(args.candidates)
    if args.limit:
        cands = cands[:args.limit]
    nbatches = (len(cands) + args.batch - 1) // args.batch

    print(f"candidates : {len(cands):,} distinct repos")
    print(f"batches    : {nbatches:,} x {args.batch}")
    print(f"est. cost  : ~{nbatches:,} points of 5,000/hr GraphQL "
          f"({nbatches / 5000 * 100:.1f}% of one hour)")
    print(f"output     : {args.out}")

    if args.dry_run:
        print("\nDRY RUN — no API calls made.")
        print("Sample of what would be queried:")
        for o, n in cands[:5]:
            print(f"  {o}/{n}")
        return 0

    token = os.environ.get("MCP_GITHUB_TOKEN") or ""
    if not token and args.allow_shared_token:
        token = os.environ.get("GITHUB_TOKEN") or ""
        if token:
            print("\nWARNING: using shared GITHUB_TOKEN (--allow-shared-token).")
    if not token:
        print("\nERROR: set MCP_GITHUB_TOKEN (a separate read-only PAT).\n"
              "       Refusing to fall back to GITHUB_TOKEN — that is the scorecard\n"
              "       scan's budget. Pass --allow-shared-token to override.\n"
              "       Note: GraphQL and REST have separate 5k/hr budgets, so even\n"
              "       a shared token would not touch the scorecard CLI's REST quota.",
              file=sys.stderr)
        return 2

    # Resume: never re-query a repo already resolved in a previous run.
    rows: dict[str, dict] = {}
    if os.path.isfile(args.out):
        try:
            rows = {f"{r['query_owner']}/{r['query_name']}".lower(): r
                    for r in json.load(open(args.out))}
            print(f"resuming   : {len(rows):,} already swept")
        except (json.JSONDecodeError, OSError, KeyError):
            rows = {}
    todo = [(o, n) for o, n in cands if f"{o}/{n}".lower() not in rows]
    print(f"to sweep   : {len(todo):,}\n")

    def save() -> None:
        tmp = args.out + ".tmp"
        with open(tmp, "w") as f:
            json.dump(list(rows.values()), f)
        os.replace(tmp, args.out)  # atomic: a crash never leaves a half file

    t0, errors, stopped = time.monotonic(), 0, None
    for bi in range(0, len(todo), args.batch):
        batch = todo[bi:bi + args.batch]
        try:
            doc = post(build_query(batch), token)
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode(errors="replace")
            if e.code in (403, 429):
                stopped = f"HTTP {e.code} (secondary rate limit): {body}"
                break
            errors += 1
            print(f"  HTTP {e.code} on batch {bi // args.batch}: {body}")
            if errors > 10:
                stopped = "too many HTTP errors"
                break
            time.sleep(5)
            continue
        except Exception as e:  # noqa: BLE001 — network variance, keep going
            errors += 1
            print(f"  error on batch {bi // args.batch}: {e}")
            if errors > 10:
                stopped = "too many errors"
                break
            time.sleep(5)
            continue

        data = doc.get("data") or {}
        # Per-alias NOT_FOUND arrives as an `errors` entry with data.rN = null.
        # That is a normal, expected result (deleted/renamed/private repo), not
        # a failure — flatten() records it as resolved=False.
        for i, (owner, name) in enumerate(batch):
            rows[f"{owner}/{name}".lower()] = flatten(data.get(f"r{i}"), owner, name)

        rl = data.get("rateLimit") or {}
        remaining = rl.get("remaining")
        done = len(rows)
        if (bi // args.batch) % 20 == 0 or done >= len(cands):
            print(f"  {done:,}/{len(cands):,} repos | cost={rl.get('cost')} "
                  f"remaining={remaining} | {time.monotonic() - t0:.0f}s")
            save()

        if isinstance(remaining, int) and remaining < args.min_remaining:
            stopped = f"quota floor reached (remaining={remaining}, resets {rl.get('resetAt')})"
            break
        time.sleep(args.sleep)

    save()
    resolved = sum(1 for r in rows.values() if r.get("resolved"))
    print(f"\nswept {len(rows):,} repos in {time.monotonic() - t0:.0f}s "
          f"({resolved:,} resolved, {len(rows) - resolved:,} missing)")
    if stopped:
        print(f"STOPPED EARLY: {stopped}")
        print("Re-run the same command to resume — completed repos are skipped.")
    print(f"written: {args.out}  @ {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
