# HVTracker

**AI Trust Registry for Open-Source Agents**

[hvtracker.net](https://hvtracker.net) ranks open-source AI agents by evidence-weighted trust signals, not GitHub hype.

HVTracker is an ever-growing leaderboard that tracks open-source AI agents across multiple categories and publishes public, machine-readable trust data for each project: activity, adoption, transparency, supply-chain safety, identity, provenance, evidence grade, and rank movement.

The core question is simple:

> Which open-source AI agent projects look active, adopted, transparent, and verifiable right now?

---

## Version 3.2

HVTracker v3.2 ships public runtime-trust discovery fields on agent profiles, a local score-lab preview for experimental ranking calibration, corrected multi-source package coverage, and refreshed methodology/roadmap documentation.

---

## What You Can Do

- Browse the live trust registry: [hvtracker.net](https://hvtracker.net)
- Compare agents side by side: [hvtracker.net/compare](https://hvtracker.net/compare/)
- Read category comparison guides: [hvtracker.net/blog](https://hvtracker.net/blog/)
- Use the public API: [hvtracker.net/data/latest.json](https://hvtracker.net/data/latest.json)
- Embed live trust badges in project READMEs

## Repository Docs

- [docs/README.md](docs/README.md) - repo docs index
- [docs/open-core.md](docs/open-core.md) - public/private product boundary
- [docs/AI_HANDOVER.md](docs/AI_HANDOVER.md) - implementation handover for coding agents
- [docs/launch-v1.md](docs/launch-v1.md) - launch and distribution notes

---

## Current Snapshot

- Active open-source AI agent projects (see [live count](https://hvtracker.net))
- Curated categories spanning coding agents, frameworks, infra, security, and more
- **2h** Railway refresh cadence
- **~24h** expected full data sweep across sources
- **90-day** per-agent history where available
- **184** JSON feed items across agents and comparison guides
- Railway-hosted site with a small FastAPI edge and generated public pages/data

Newly submitted agents are listed quickly using a pending-only refresh path, then normal cron jobs keep signals fresh.

---

## Why HVTracker Exists

Most AI agent directories are either manual lists or popularity rankings. Stars can tell you what is visible. They do not tell you whether a project has maintainers, a license, package provenance, signed commits, OSSF Scorecard data, or recent activity.

HVTracker combines curation with independently checkable public evidence. The default rank is **HVTrust**, a 0-100 score designed to reward verifiable trust signals and penalize thin evidence.

```text
HVTrust = gate(
  confidence x [ Safety(25) + Identity(18) + Transparency(17)
                 + Maintenance(20) + Adoption(20) ]
  - penalties
)
```

| Dimension | Max | What it measures |
|---|---:|---|
| Safety / Integrity | 25 | OSSF Scorecard, package provenance, signed commits |
| Identity / Provenance | 18 | Verified listing status and build provenance |
| Transparency | 17 | License and OSSF transparency checks |
| Maintenance | 20 | Freshness and recent commit activity |
| Adoption | 20 | Log-scaled, capped stars and package downloads |

Confidence is based on present vs applicable signal types. Thin evidence limits how high an agent can rank, even if it is popular.

Read the full methodology: [hvtracker.net/methodology](https://hvtracker.net/methodology)

---

## Evidence Grades

Each agent also receives an evidence grade so readers can separate score from evidence depth.

| Grade | Meaning |
|---|---|
| A | Broad independent signal coverage |
| B | Strong public evidence with some gaps |
| C | Basic public evidence |
| D | Mostly GitHub-only or thin evidence |

HVTracker is not a security certification. Missing provenance, Scorecard, or signature data can mean a signal is unavailable, not that a project is unsafe.

---

## Categories

| Category | Count |
|---|---:|
| Agent Frameworks | 58 |
| Coding Agents | 26 |
| Memory & Knowledge | 20 |
| Browser & Computer Use | 15 |
| Workflow Platforms | 13 |
| Observability & Evaluation | 12 |
| Research & Data | 8 |
| Security & Guardrails | 6 |
| LLM Gateways & Infra | 4 |
| Protocols & Tool Integration | 4 |
| Multi-Agent Systems | 3 |
| Robotics & Embodied | 1 |
| Voice & Conversational | 1 |
| Sandboxes & Runtimes | 1 |

---

## Public Data API

The public dataset is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). CORS is open for public endpoints.

| Endpoint | Description |
|---|---|
| [`/data/latest.json`](https://hvtracker.net/data/latest.json) | Current public trust registry snapshot |
| [`/data/agents/{slug}.json`](https://hvtracker.net/data/agents/dify.json) | Per-agent record with history, events, and trust credential |
| [`/data/build_report.json`](https://hvtracker.net/data/build_report.json) | Build integrity report |
| [`/data/signals/scorecard.json`](https://hvtracker.net/data/signals/scorecard.json) | OSSF Scorecard signal cache |
| [`/data/signals/provenance.json`](https://hvtracker.net/data/signals/provenance.json) | Package provenance signal cache |
| [`/feed.json`](https://hvtracker.net/feed.json) | JSON Feed with agents and comparison guides |
| [`/llms.txt`](https://hvtracker.net/llms.txt) | LLM-readable project summary and key links |

---

## Trust Badges

Listed projects can embed live HVTrust and evidence-grade badges.

```md
[![HVTrust](https://hvtracker.net/badge/<slug>.svg)](https://hvtracker.net/agents/<slug>/)
[![Evidence Grade](https://hvtracker.net/badge/<slug>-grade.svg)](https://hvtracker.net/agents/<slug>/)
```

Example:

```md
[![HVTrust](https://hvtracker.net/badge/dify.svg)](https://hvtracker.net/agents/dify/)
[![Evidence Grade](https://hvtracker.net/badge/dify-grade.svg)](https://hvtracker.net/agents/dify/)
```

The exact snippet is shown on every agent profile page.

---

## Open-Core Boundary

HVTracker uses an open-core model.

- Public: methodology, specs, curated registry entries, current trust scores, public profiles, correction flow, and the public data API.
- Private later: hosted alerts, watchlists, extended history, team workflows, and higher-volume API access.

The code in this repository remains under the repo's existing MIT license. Public registry data remains licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The brand, hosted service, private enrichment, and future enterprise workflows are not implicitly included in that public-data license.

Read [docs/open-core.md](docs/open-core.md) before widening the public API or changing what gets stored internally.

---

## SEO And Comparison Pages

HVTracker publishes crawlable, data-backed comparison pages:

- Category pages: `/categories/<category>/`
- Agent comparison pages: `/compare/<agent-a>-vs-<agent-b>/`
- Blog comparison guides: `/blog/<category>-top-agents/`

These pages are generated from the current registry data, included in `sitemap.xml`, and linked from `feed.json` and `llms.txt`.

---

## How It Works

```text
agents.json ──┐
               ├──> fetch_and_build.py ──> index.html
history/    ───┤                           agents/<slug>/index.html
scorecard-  ───┘                           data/latest.json
cache.json                                 data/agents/<slug>.json
```

1. `fetch_and_build.py` reads curated agents from `agents.json`.
2. Public APIs are fetched in parallel where safe and serially where rate limits require it.
3. HVTrust scores, evidence grades, rank deltas, trust breakdowns, and events are computed.
4. Static pages, JSON endpoints, badges, specs, feed files, sitemap, and build reports are generated.
5. Railway serves the generated site from a persistent volume and refreshes it on a 2-hour cadence.

### Build Modes

```bash
python fetch_and_build.py              # full refresh
python fetch_and_build.py --batch 1/6  # one staggered batch
python fetch_and_build.py --pending-only
python fetch_and_build.py --render-only
```

- `--pending-only` refreshes newly listed agents without running a full batch.
- `--render-only` rebuilds pages from cached render state without API calls.

---

## Running Locally

```bash
git clone https://github.com/YugantM/hvtracker.git
cd hvtracker
pip install -r requirements.txt

export GITHUB_TOKEN=$(gh auth token)  # or a personal access token
python fetch_and_build.py --render-only

python3 -m http.server 4173
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173).

### Local Docker Workflow

Use Docker when you want discovery, dry-run additions, renders, and the app
to run in the same local container environment.

```bash
docker compose up --build web
```

This serves the app at [http://127.0.0.1:8080](http://127.0.0.1:8080).

For registry work, run the tooling service against your checked-out repo so
changes to `agents.json` or `candidates.json` persist locally:

```bash
export GITHUB_TOKEN=...  # required for GitHub discovery/API-backed refreshes

docker compose run --rm tooling python discover_agents.py
docker compose run --rm tooling python auto_add_agents.py --dry-run
docker compose run --rm tooling python fetch_and_build.py --render-only
docker compose run --rm tooling python -m pytest tests/test_discovery.py tests/test_data_integrity.py
```

For manual candidate review, edit `docs/import-candidates.json` with either
`owner/name`, full GitHub URLs, or object entries, then query:

```bash
curl -s http://127.0.0.1:8080/api/import-candidates | python -m json.tool
curl -s "http://127.0.0.1:8080/api/import-candidates?status=new&tracked=false" | python -m json.tool
```

Notes:

- `tooling` bind-mounts the repo into `/workspace`, so file changes are written
  back to your local checkout.
- `auto_add_agents.py` writes to `agents.json` only without `--dry-run`.
- `fetch_and_build.py --render-only` stays local and avoids external API calls.

Production runs on Railway with:

- FastAPI for health, API, forms, and dynamic badge routes
- Generated site output stored on a persistent volume
- A 2-hour scheduler that refreshes one leaderboard batch per run

---

## Submit Or Correct An Agent

Use the [agent listing issue template](https://github.com/YugantM/hvtracker/issues/new?template=agent-listing.yml).

A listed project should be:

- A public, non-archived GitHub repository with an open-source license
- An AI agent or an agent framework whose primary purpose is agent construction
- Clearly agent-specific in its own codebase, not a general AI SDK, model repo, cookbook, or generic app framework
- Active within the last 12 months
- Not already listed

Include the canonical repository, preferred display name, category suggestion, package names, and any correction details.

For the strict plain-language boundary, see [docs/strict-inclusion-rubric.md](/Users/harsiddhipari/hv_tracker/docs/strict-inclusion-rubric.md).

---

## Specifications

- [Trust Credential v0.1](https://hvtracker.net/spec/trust-credential/v0.1)
- [Methodology v2.0](https://hvtracker.net/spec/methodology/v2.0)
- [Eligibility v1.0](https://hvtracker.net/spec/eligibility/v1.0)
- [Listing v0.1](https://hvtracker.net/spec/listing/v0.1)
- [Data Schema v0.1](https://hvtracker.net/spec/data-schema/v0.1)
- [Provenance v0.1](https://hvtracker.net/spec/provenance/v0.1)
- [Build Report v0.1](https://hvtracker.net/spec/build-report/v0.1)

---

## Repository Layout

```text
hvtracker/
├── fetch_and_build.py        # Core build, scoring, and rendering
├── template.html             # Main registry template
├── templates/                # Agent, category, blog, compare, and spec templates
├── agents.json               # Curated agent registry
├── specs.py                  # Specification content
├── scan_scorecards.py        # Weekly OSSF Scorecard scan
├── discover_agents.py        # Weekly discovery scan
├── docs/                     # Launch, research, and operating docs
├── data/                     # Generated public data endpoints
├── agents/                   # Generated per-agent pages
├── badge/                    # Generated SVG badges
└── blog/                     # Generated and static articles
```

---

## License

The public data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Review [docs/open-core.md](docs/open-core.md) before changing the public/private data boundary for a future company-backed edition.
