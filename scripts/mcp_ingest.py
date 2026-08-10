#!/usr/bin/env python3
"""Convert the triaged MCP shortlist into agents.json rows.

Follows the roster convention exactly (see commit d4556d88): rows carry only
repo/name/category/listing_status/tracking_mode plus any package identifiers.
Everything else — scores, stars, provenance — is fetched by the pipeline, and
rows land provisional until prod's startup repair-commits refresh scores them
(#158/#160).

Category is "MCP Servers", which the owner defines narrowly as *concrete
per-product servers* (playwright-mcp, blender-mcp, terraform-mcp-server) —
NOT frameworks, gateways or registries, which belong in "Protocols & Tool
Integration". The triage's dedicated-server filter targets that same
population, but the classification is heuristic: review before committing.

Package identifiers matter more than usual here. compute_trust_score's
confidence term counts *applicable* signal types, so a row with a known npm or
PyPI package can reach a higher coverage grade than a GitHub-only row. 90% of
the shortlist ships a package, so wiring these up is most of the evidence
depth available before Scorecard runs.

Usage:
    python3 scripts/mcp_ingest.py --dry-run
    python3 scripts/mcp_ingest.py --apply
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

REGISTRY_TYPE_TO_FIELD = {
    "npm": "npm_package",
    "pypi": "pypi_package",
    "cargo": "crate_package",
    "oci": "docker_image",
}


# The pipeline de-duplicates rows by display NAME and keeps the first — a row
# whose name collides is silently dropped, not renamed. That is harmless for
# agents (langchain, haystack are distinctive) and catastrophic here, because
# the MCP naming convention is literally <vendor>/mcp: 13 repos want the name
# "MCP" and 9 want "MCP Server". Measured on the first ingest attempt: 36 rows
# vanished, including containers/kubernetes-mcp-server at 1,889 stars.
# Anything in this set is owner-qualified unconditionally.
GENERIC_NAMES = {
    "mcp", "mcp server", "server", "mcp servers", "mcp service",
    "modelcontextprotocol", "model context protocol", "mcp tools", "tools",
}


def _titlecase(text: str) -> str:
    out = []
    for w in re.split(r"[-_.\s]+", text):
        if not w:
            continue
        out.append("MCP" if w.lower() == "mcp" else
                   w if (w[:1].isupper() and w[1:].lower() != w[1:]) else
                   w.capitalize())
    return " ".join(out)


def humanize(repo: str, registry_title: str | None) -> str:
    """Display name. Prefer a clean registry title, else humanise the repo name.

    Matches the existing rows' style: microsoft/playwright-mcp -> "Playwright MCP".
    Owner-qualifies generic names so <vendor>/mcp rows stay distinguishable.
    """
    owner, _, name = repo.partition("/")
    if registry_title:
        t = registry_title.strip()
        if (" " in t or not re.match(r"^[a-z0-9.\-]+$", t)) and 2 <= len(t) <= 60:
            if t.lower() not in GENERIC_NAMES:
                return t
    base = _titlecase(name) or name
    if base.lower() in GENERIC_NAMES:
        return f"{_titlecase(owner)} {base}".strip()
    return base


def dedupe_names(new_rows: list[dict], taken: set[str]) -> int:
    """Owner-qualify any name colliding with the roster or another new row.

    Returns how many were renamed. Runs AFTER all rows are built because a
    collision is only visible globally.
    """
    renamed = 0
    for row in new_rows:
        if row["name"].lower() not in taken:
            taken.add(row["name"].lower())
            continue
        owner = row["repo"].split("/", 1)[0]
        for candidate in (f"{_titlecase(owner)} {row['name']}",
                          f"{row['name']} ({owner})"):
            if candidate.lower() not in taken:
                row["name"] = candidate
                renamed += 1
                break
        else:  # both taken — fall back to the full repo path, always unique
            row["name"] = f"{row['name']} ({row['repo']})"
            renamed += 1
        taken.add(row["name"].lower())
    return renamed


def load_registry_packages(raw_path: str) -> tuple[dict, dict]:
    """repo_key -> {field: identifier}, and repo_key -> registry title."""
    gh = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$", re.I)
    pkgs: dict[str, dict] = {}
    titles: dict[str, str] = {}
    with open(raw_path) as f:
        entries = json.load(f)
    for e in entries:
        s = e.get("server") or {}
        m = gh.search(((s.get("repository") or {}).get("url") or "").strip())
        if not m:
            continue
        key = f"{m.group(1)}/{m.group(2)}".lower()
        titles.setdefault(key, s.get("title") or "")
        for p in s.get("packages") or []:
            field = REGISTRY_TYPE_TO_FIELD.get(p.get("registryType"))
            ident = p.get("identifier")
            if field and ident:
                pkgs.setdefault(key, {}).setdefault(field, ident)
    return pkgs, titles


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    base = os.path.expanduser("~/hv_marketing/data")
    ap.add_argument("--shortlist", default=f"{base}/mcp-shortlist-dedicated.csv")
    ap.add_argument("--registry-raw", required=True,
                    help="mcp_registry_raw.json (for package identifiers)")
    ap.add_argument("--agents", default=os.path.expanduser("~/hvtracker/agents.json"))
    ap.add_argument("--category", default="MCP Servers")
    ap.add_argument("--apply", action="store_true", help="write agents.json (default: dry run)")
    args = ap.parse_args()

    pkgs, titles = load_registry_packages(args.registry_raw)
    agents = json.load(open(args.agents))
    if not isinstance(agents, list):
        print("ERROR: agents.json is not a list", file=sys.stderr)
        return 2
    existing = {(a.get("repo") or "").lower() for a in agents}

    new, skipped = [], 0
    for r in csv.DictReader(open(args.shortlist)):
        repo = r["repo"]
        key = repo.lower()
        if key in existing:
            skipped += 1
            continue
        row = {
            "repo": repo,
            "name": humanize(repo, titles.get(key)),
            "category": args.category,
            "listing_status": "listed",
            "tracking_mode": "direct",
        }
        row.update(pkgs.get(key, {}))
        new.append(row)
        existing.add(key)

    # Must run before writing: a duplicate name is dropped by the render, not renamed.
    taken = {(a.get("name") or "").lower() for a in agents}
    renamed = dedupe_names(new, taken)
    print(f"name collisions resolved: {renamed:,}")

    field_counts = Counter(f for r in new for f in r if f in REGISTRY_TYPE_TO_FIELD.values())
    print(f"shortlist rows      : {skipped + len(new):,}")
    print(f"already in roster   : {skipped:,}")
    print(f"NEW rows to add     : {len(new):,}")
    print(f"roster {len(agents):,} -> {len(agents) + len(new):,}")
    print("package fields wired: " + (", ".join(f"{k}={v}" for k, v in field_counts.most_common())
                                      or "none"))
    print("\nsample:")
    for r in new[:6]:
        print("  " + json.dumps(r))

    if not args.apply:
        print("\nDRY RUN — agents.json untouched. Re-run with --apply.")
        return 0

    agents.extend(new)
    tmp = args.agents + ".tmp"
    with open(tmp, "w") as f:
        json.dump(agents, f, indent=2)
        f.write("\n")
    os.replace(tmp, args.agents)
    print(f"\nWROTE {args.agents} — {len(agents):,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
