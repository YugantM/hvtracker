# HVTracker AI Handover

This document is the working handover for coding agents taking over HVTracker. It should describe the current production shape, not the older GitHub Pages launch setup.

## Latest Task Log

- 2026-05-31: Merged the Railway migration into `main`. Production now runs behind FastAPI on Railway with a persistent volume, dynamic badge routes, submission/correction forms, and 2-hour refresh orchestration.
- 2026-05-31: Standardized social previews on `og-v2.png` and removed SVG badge previews from social metadata.
- 2026-05-31: Added an asset/template fingerprint so Railway deploys trigger a render-only rebuild when share metadata or templates change.

## 1. Project Purpose

HVTracker is a public trust registry for open-source AI agent projects, not a generic AI tools directory. It tracks agent frameworks, coding agents, workflow platforms, memory and knowledge tools, browser/computer-use projects, research/data agents, multi-agent systems, and related infrastructure.

The goal is to make HVTracker a trusted source for project health and operational trust using independently observable public signals: GitHub activity, freshness, package downloads, signed commits, provenance, OSSF Scorecard data, evidence depth, and category ranking.

## 2. Current Architecture

HVTracker is now a Railway-hosted web service with generated site output.

High-level flow:

```text
agents.json + cached signal files
        |
        v
fetch_and_build.py  <---- app.py triggers full/render/pending refreshes
        |
        v
/data/site (Railway volume)
  |- index.html
  |- data/latest.json
  |- agents/<slug>/index.html
  |- compare/<a>-vs-<b>/index.html
  |- blog/*
  |- output/history/<date>.json
  |- sitemap.xml

FastAPI (`app.py`) sits in front of the generated output and adds:
- `/healthz`
- `/api/*`
- `/badge/*`
- `/submit` and `/correct`
- `/compare/` interactive tool
```

The public site is still plain generated HTML with inline CSS and vanilla JavaScript, but production now has a thin backend for routing, submissions, badges, and refresh orchestration. There is still no React app, SPA router, or database-backed end-user UI.

## 3. Build And Deploy Flow

Local build:

```bash
python3 -m pip install -r requirements.txt
GITHUB_TOKEN="$(gh auth token)" python3 fetch_and_build.py
```

The build fetches live data and rewrites generated output, so expect data churn when running it.

Production deploy flow:

- Railway builds from `Dockerfile`
- FastAPI serves the site from the `/data/site` volume
- Startup seeds history snapshots when needed
- Startup triggers a render rebuild when templates/assets changed
- The in-process scheduler runs every 2 hours

GitHub automation that still matters:

- `.github/workflows/ci.yml` - tests and linting
- `.github/workflows/discover-agents.yml` - discovery support
- `.github/workflows/scorecard-scan.yml` - OSSF Scorecard refresh support

## 4. Important Files

- `fetch_and_build.py` - main generator. Fetches external data, computes scores/ranks, writes all generated public files.
- `app.py` - FastAPI entrypoint and Railway startup orchestration.
- `db.py` - Postgres-backed submission/correction storage.
- `storage.py` / `cache.py` - small persistence helpers for production runtime.
- `agents.json` - curated source list of tracked projects. Includes repo, display name, category, package metadata, and HN search terms where available.
- `template.html` - homepage leaderboard template with inline CSS and vanilla JS sorting/category filtering.
- `templates/agent.html.j2` - per-agent profile page template.
- `templates/methodology.html.j2` - methodology page template.
- `data.json` - generated machine-readable snapshot in local/dev contexts. Treat schema as public API.
- `output/history/*.json` - generated daily snapshots used for prior-rank deltas, cached download fallback, movers, and sparklines.
- `compare/index.html` - interactive compare tool source page.
- `robots.txt` - static robots policy pointing at sitemap.
- `og-v2.png` - current share-preview image.
- `README.md` - project overview. Some details may lag implementation.
- `docs/README.md` - docs index / lightweight repo wiki.
- `AGENTS.md` and `CLAUDE.md` - AI coding behavior guidelines.

## 5. Data Sources And Generated Data Files

Current external sources in `fetch_and_build.py`:

- GitHub REST API:
  - repo metadata
  - stars
  - forks
  - last push
  - language
  - description
  - open issues
  - commit activity
  - fallback recent commit count
  - signed commit ratio from recent commits
- npm registry:
  - last-week downloads
  - latest package provenance via `dist.attestations`
- PyPI / pypistats:
  - last-week downloads
  - latest package provenance via PyPI Simple API JSON
- Hacker News Algolia API:
  - 30-day story mention counts for configured search terms
- deps.dev:
  - OSSF Scorecard overall score and checks when available

Generated data/public files:

- `data.json` - canonical current API snapshot
- `output/history/YYYY-MM-DD.json` - daily historical snapshots
- `feed.json` - JSON Feed 1.1
- `sitemap.xml` - public URL discovery
- `index.html`, `methodology.html`, `output/methodology.html`, `agents/*/index.html` - generated HTML

Current snapshot characteristics observed during handover:

- 172 agents
- 14 categories
- 50 agents with weekly download data
- 54 agents with HN terms/results
- Trust fields include npm provenance, PyPI provenance, signed commit ratio, OSSF Scorecard score/checks

## 6. Scoring-Related Files

Scoring lives in `fetch_and_build.py`:

- `score_components(...)`
- `compute_score(...)`
- `score_class(...)`

Current score model is the HVTrust system documented in `README.md`, the methodology pages, and `fetch_and_build.py`. Treat those as the source of truth instead of the older launch-era health-score formula.

Do not change scoring weights, rank ordering, confidence gating, or evidence-grade semantics unless the user explicitly asks.

Scoring also affects:

- `data.json`
- `output/history/*.json`
- `template.html`
- `templates/agent.html.j2`
- `templates/methodology.html.j2`
- generated `index.html` and `agents/*/index.html`

## 7. HTML, Template, And UI Files

The UI is generated from:

- `template.html` - main leaderboard page
- `templates/agent.html.j2` - per-agent profile pages
- `templates/methodology.html.j2` - methodology page

Important UI behavior:

- Homepage has category pills and sortable table columns.
- Category filtering switches visible ranks to category rank plus muted global rank.
- Table uses horizontal scrolling on narrower viewports.
- Agent pages show rank, score breakdown, activity/reach, trust signals, rank trend, sibling links, and package links.
- Methodology documents scoring, data sources, trust signals, limitations, and versioning.

Keep UI changes small and static. Prefer plain HTML/CSS/JS. Do not introduce React, Next.js, bundlers, CSS frameworks, or client-side routing unless explicitly approved.

## 8. Current Risks And Fragile Areas

- `data.json` is a public API. Avoid removing or renaming fields. Prefer additive changes.
- Running the build rewrites many generated files and fetches live data, so diffs can become large and noisy.
- `README.md` says rank deltas compare against previous `data.json`, but the implementation now compares against the previous daily `output/history` snapshot.
- `sitemap.xml` is generated by `fetch_and_build.py`. If new static pages are added, update sitemap generation there as part of that page's PR.
- SEO metadata is duplicated between source templates and generated HTML. Prefer changing templates and regenerating generated pages.
- The build depends on multiple external APIs. Failures/rate limits can silently produce `None`, zero, or cached values.
- PyPI download fetching is intentionally serial and slow because of pypistats rate limits.
- OSSF Scorecard coverage through deps.dev is sparse in the current generated snapshot.
- There are no dedicated automated tests in the repo.
- There is no HTML validation tool checked into the project.
- Inline CSS/JS is simple but duplicated across templates, so broad styling changes can get repetitive.
- Generated history snapshots are considered important project IP. Do not delete them.

## 9. Visible Claude Code Changes

The actual Claude summary was not present in this repo; the earlier placeholder only said to paste it here. Visible git history suggests Claude Code recently made these changes:

- `feat: per-agent profile pages, sitemap, sibling links + cadence copy fixes`
- `feat: feed.json + polish (action bumps, days-ago copy, CI staging fix)`
- `fix: data quality - smarter commits fallback + low-confidence flag`
- `fix: rank deltas now compare against prior day's history snapshot`
- `feat: OG image for link previews + methodology_version in data snapshots`
- `feat: biggest movers strip + rank trend sparklines (Phase B)`
- `feat: supply chain trust signals - npm/PyPI provenance, OSSF Scorecard, signed commits (v2.0)`
- `fix: opt into Node.js 24 for GitHub Actions to silence deprecation warning`

There is also a checkpoint commit on the current handover branch:

- `checkpoint: claude handover state`

Do not assume these changes are bug-free. Re-check generated output and data compatibility before building on them.

## 10. Recommended Next Implementation Tasks

1. Lightweight search/filter UX:
   - Add a simple text search input to the existing homepage table.
   - Integrate with current category filtering and sorting without adding dependencies.
   - Preserve the new homepage intro and keep search close to the leaderboard controls.

2. `data.json` API documentation page:
   - Add a static API docs page explaining endpoint, fields, versioning, examples, and compatibility rules.
   - Link it from footer and methodology.

3. Static discovery and docs consistency:
   - Verify README, footer links, feed link, and methodology are consistent with actual generation behavior.
   - Fix README/history delta mismatch if needed.

4. Compare mode:
   - Add a minimal static compare mode for 2-3 agents using existing generated row data.
   - Avoid historical/score logic changes in the first compare PR.

5. Build validation safety net:
   - Add lightweight checks for JSON schema shape, generated file existence, sitemap URL count, and basic HTML parseability.
   - Keep this separate from product changes.

Historical score tracking beyond the existing snapshots should wait until SEO, docs, search, and API clarity are stable.

## 11. Instructions For Future AI Coding Agents

- Start each task with `git status --short --branch`.
- Read this file before making changes.
- Keep changes small, reviewable, and commit-sized.
- Do not rewrite the architecture.
- Do not introduce React, Next.js, a backend, login, database, or payment system unless the user explicitly approves.
- Preserve the static-site deploy flow.
- Do not change scoring logic unless specifically asked.
- Treat `data.json` as a public API. Avoid breaking field names and types.
- Prefer additive fields and documentation over schema-breaking changes.
- Avoid editing generated files by hand. Change templates or `fetch_and_build.py`, then regenerate.
- If a docs-only task does not require regeneration, do not run the build just to create noise.
- If running the build, expect live data changes and inspect the generated diff carefully.
- After each completed task, update this file with what changed, risks found, and recommended next steps.
- Before major edits to `fetch_and_build.py`, `template.html`, or templates, explain the plan to the user.
- Use plain Python, HTML, CSS, and vanilla JavaScript unless there is a strong reason not to.

## Verification Commands

Recommended local verification commands:

```bash
git status --short --branch
python3 -m pip install -r requirements.txt
GITHUB_TOKEN="$(gh auth token)" python3 fetch_and_build.py
python3 -m json.tool data.json >/tmp/hvtracker-data.json
python3 -m json.tool feed.json >/tmp/hvtracker-feed.json
python3 - <<'PY'
from pathlib import Path
from xml.etree import ElementTree as ET

root = ET.parse("sitemap.xml").getroot()
ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
urls = [loc.text for loc in root.findall(".//sm:loc", ns)]
assert "https://hvtracker.net/" in urls
assert "https://hvtracker.net/methodology" in urls
assert all(url.startswith("https://hvtracker.net/") for url in urls)
robots = Path("robots.txt").read_text()
assert "User-agent: *" in robots
assert "Allow: /" in robots
assert "Sitemap: https://hvtracker.net/sitemap.xml" in robots
print(f"sitemap/robots checks passed ({len(urls)} URLs)")
PY
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("data.json").read_text())
assert data["total"] == len(data["agents"])
assert data["total"] == 65
required = {"name", "repo", "url", "rank", "score", "category"}
for agent in data["agents"]:
    missing = required - set(agent)
    assert not missing, (agent.get("name"), missing)

assert Path("index.html").exists()
assert Path("methodology.html").exists()
assert Path("sitemap.xml").exists()
assert Path("feed.json").exists()
assert len(list(Path("agents").glob("*/index.html"))) == data["total"]
print("basic generated output checks passed")
PY
python3 -m http.server 8000
```

Then open `http://localhost:8000` and check:

- homepage loads
- category filters work
- table sorting works
- an agent page loads
- methodology page loads
- mobile width still scrolls the table cleanly
