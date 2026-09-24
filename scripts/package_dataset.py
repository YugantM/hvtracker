"""Package a frozen quarterly HVTrust export for a Zenodo deposit (plan 3.3).

    python scripts/package_dataset.py 2026-Q3

Downloads hvtrust-<quarter>.json.gz and .csv from hvtracker.net, checks they
agree, and writes dist/hvtrust-<quarter>/ with the two files, a README (data
dictionary, method, licence, citation) and .zenodo.json (deposit metadata),
plus a .zip of the folder. Upload the zip's contents on zenodo.org; the
.zenodo.json values are what to paste into the form. Run it only after the
quarter has ended: an export keeps refreshing until then.
"""
import csv
import gzip
import io
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://hvtracker.net/data/exports"

FIELDS = {
    "rank": "Position on the agent board by HVTrust score (1 = highest).",
    "display_rank": "Rank as shown on the site; tied scores share a rank.",
    "slug": "Stable identifier; the project's page is https://hvtracker.net/agents/<slug>/.",
    "name": "Project name.",
    "repo": "GitHub repository (owner/name).",
    "category": "HVTracker category (e.g. MCP Servers, Coding Agents).",
    "trust_score": "HVTrust score, 0-100: base score over five dimensions plus a bounded runtime calibration.",
    "evidence_grade": "Score band: A >= 80, B >= 65, C >= 50, D < 50.",
    "coverage_grade": "How many independent public signal types verify the project: A >= 4, B = 3, C = 2, D = 1.",
    "trust_confidence": "Share of applicable signal types present (0.4-1.0); scales the base score.",
    "stars": "GitHub stars at export time.",
    "weekly_downloads": "Weekly package downloads (npm, PyPI, crates.io, ...); empty if no package.",
    "license_spdx": "Declared licence (SPDX id); empty if none detected.",
    "has_provenance": "Whether published packages carry build-provenance attestations.",
    "scorecard_score": "OpenSSF Scorecard aggregate, 0-10; empty if not scanned.",
    "signed_commits_ratio": "Share of recent commits that are signed, 0-1.",
    "mcp_status": "Model Context Protocol server support detected: implemented, declared or none.",
    "provider_count": "Number of external LLM/API providers the project depends on at runtime.",
    "requires_api_keys": "Whether the project needs third-party API keys to run.",
    "plugin_system": "Plugin or extension surface: marketplace, extension-based, declared or none.",
    "drift_status": "Whether published package metadata matches the tracked repo: match, partial, warning, unknown or not_applicable.",
    "listing_status": "listed or warning (a listed project with an open review flag).",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (hvtracker dataset packager)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def readme(label, doc):
    rows = "\n".join(f"| `{k}` | {v} |" for k, v in FIELDS.items())
    cite = f"{BASE}/hvtrust-{label}.json.gz"  # Zenodo shows the DOI beside it
    return f"""# HVTrust quarterly export {label}

Independent trust scores for {doc['count']} open-source AI agent projects
(agents, frameworks, MCP servers and coding agents), as published on
https://hvtracker.net at the end of {label}.

- Generated: {doc['generated_at']} (methodology {doc['methodology_version']})
- Files: `hvtrust-{label}.json.gz` (full document with metadata) and
  `hvtrust-{label}.csv` (same records, one row per project)
- Method: https://hvtracker.net/methodology/. Every point comes from public,
  checkable signals: OpenSSF Scorecard, package provenance, signed commits,
  licence, maintenance and adoption. Nothing is self-reported and no
  placement is paid.
- Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)

## Cite

HVTracker ({label[:4]}). *HVTrust quarterly export {label}* [Data set]. {cite}

## Fields

| Field | Meaning |
|---|---|
{rows}
"""


def zenodo(label, doc):
    return {
        "upload_type": "dataset",
        "title": f"HVTrust quarterly export {label}: trust scores for open-source AI agent projects",
        "creators": [{"name": "HVTracker"}],
        "description": (f"End-of-quarter snapshot of HVTrust scores for {doc['count']} open-source AI agent "
                        "projects (agents, frameworks, MCP servers, coding agents), computed from public, "
                        "checkable signals (OpenSSF Scorecard, package provenance, signed commits, licence, "
                        f"maintenance, adoption). Methodology {doc['methodology_version']}: "
                        "https://hvtracker.net/methodology/"),
        "license": "cc-by-4.0",
        "access_right": "open",
        "publication_date": doc["generated_at"][:10],
        "keywords": ["AI agents", "software supply chain", "open source security", "OpenSSF Scorecard",
                     "MCP", "trust scores"],
        "related_identifiers": [
            {"identifier": "https://hvtracker.net/methodology/", "relation": "isDocumentedBy", "resource_type": "publication"},
            {"identifier": f"{BASE}/hvtrust-{label}.json.gz", "relation": "isIdenticalTo", "resource_type": "dataset"},
        ],
        "version": label,
    }


def main(label, out_root=ROOT):
    if not re.fullmatch(r"\d{4}-Q[1-4]", label):
        raise SystemExit("usage: package_dataset.py YYYY-Qn")
    year, q = int(label[:4]), int(label[-1])
    now = datetime.now(timezone.utc)
    if (now.year, (now.month - 1) // 3 + 1) <= (year, q):
        raise SystemExit(f"{label} hasn't ended yet; its export still changes on every render.")
    try:
        raw = fetch(f"{BASE}/hvtrust-{label}.json.gz")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"No export for {label} ({e.code}); quarterly exports began with 2026-Q3.")
    doc = json.loads(gzip.decompress(raw))
    csv_bytes = fetch(f"{BASE}/hvtrust-{label}.csv")
    csv_rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    if len(csv_rows) != doc["count"] or len(doc["agents"]) != doc["count"]:
        raise SystemExit(f"JSON ({doc['count']}) and CSV ({len(csv_rows)}) disagree; re-fetch later.")
    out = os.path.join(out_root, "dist", f"hvtrust-{label}")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f"hvtrust-{label}.json.gz"), "wb") as f:
        f.write(raw)
    with open(os.path.join(out, f"hvtrust-{label}.csv"), "wb") as f:
        f.write(csv_bytes)
    with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme(label, doc))
    with open(os.path.join(out, ".zenodo.json"), "w", encoding="utf-8") as f:
        json.dump(zenodo(label, doc), f, indent=2)
    zip_path = shutil.make_archive(out, "zip", out)
    print(f"{doc['count']} projects -> {out}\n{zip_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
