# HVTracker — AI Agent Trust Registry

**Live:** [hvtracker.net](https://hvtracker.net)  
**Data API:** [hvtracker.net/data/latest.json](https://hvtracker.net/data/latest.json)

HVTracker tracks **171 open-source AI agents** across 14 categories and ranks them by evidence-weighted trust — not just stars or popularity. Signals refresh every 4 hours via staggered batch builds.

---

## What makes it different

Most "awesome lists" count stars. HVTracker measures **trust** across 5 dimensions:

| Dimension | Max | What it measures |
|---|---|---|
| **Activity** | 25 | Commit freshness + 4-week commit volume |
| **Adoption** | 20 | Stars + weekly downloads (npm/PyPI) |
| **Transparency** | 20 | License exists + docs + OSSF Scorecard |
| **Safety** | 20 | OSSF Scorecard + package provenance + signed commits |
| **Identity** | 15 | Evidence grade + listing verification status |

Each agent also gets an **evidence grade** (A/B/C/D) based on how many independent signal types are available — an agent with GitHub stats, downloads, OSSF Scorecard, provenance, and HN mentions earns an A; one with only GitHub data gets a D.

---

## Categories

| Category | Count |
|---|---|
| Agent Frameworks | 57 |
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
| Voice & Conversational | 1 |
| Sandboxes & Runtimes | 1 |
| Robotics & Embodied | 1 |

---

## Data signals

For every agent, HVTracker collects:

| Signal | Source |
|---|---|
| Stars, forks, language, license | GitHub REST API |
| 4-week commit activity | GitHub Stats API |
| Weekly downloads | npm Registry + PyPI (pypistats) |
| OSSF Scorecard | deps.dev API + weekly CLI scan |
| Package provenance | npm + PyPI attestation endpoints |
| Signed commit ratio | GitHub Commits API |
| HN mentions (30d) | Algolia HN Search API |
| Public actions (fingerprint) | GitHub Search API |

---

## How it works

```
agents.json ──┐
               ├──► fetch_and_build.py ──► index.html    (GitHub Pages)
history/    ───┤                           data.json     (public API)
scorecard-  ───┘                           data/agents/  (per-agent endpoints)
cache.json                                 data/build_report.json
```

1. `fetch_and_build.py` reads agents from `agents.json`
2. Fetches signals in parallel (10 threads for GitHub, serial for rate-limited APIs)
3. Computes health score (activity-based, 0-100) and HVTrust score (trust-based, 0-100)
4. Derives evidence grades and reputation events by diffing against prior snapshots
5. Renders `index.html` via Jinja2, writes `data.json` and per-agent endpoints
6. GitHub Pages serves the static site; signals refresh every 4 hours via staggered cron batches

### Staggered builds

171 agents are split into 6 batches (~29 each). Each batch runs every 4 hours, merging fresh data into `data.json`. Full refresh cycle completes in 24 hours. Each agent updates within 4 hours.

---

## Running locally

```bash
git clone https://github.com/YugantM/hvtracker.git
cd hvtracker
pip install -r requirements.txt

export GITHUB_TOKEN=$(gh auth token)  # or a personal access token
python fetch_and_build.py             # full build (~35 min for all agents)
python fetch_and_build.py --batch 1/6 # or just one batch (~6 min)

open index.html
```

---

## Submitting an agent

Use the [agent listing issue template](https://github.com/YugantM/hvtracker/issues/new?template=agent-listing.yml) to submit. Requirements:

- Public, non-archived GitHub repo
- At least one commit in the last 12 months
- Not already listed

Submissions are reviewed manually. See the [Listing Specification](https://hvtracker.net/spec/listing/v0.1) for lifecycle details.

---

## Data API

All data is open under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). CORS is open.

| Endpoint | Description |
|---|---|
| [`/data/latest.json`](https://hvtracker.net/data/latest.json) | Full snapshot — all agents with scores, signals, trust breakdowns |
| [`/data/agents/{slug}.json`](https://hvtracker.net/data/agents/dify.json) | Per-agent detail with 90-day history and reputation events |
| [`/data/build_report.json`](https://hvtracker.net/data/build_report.json) | Build integrity report — agent counts, warnings, failures |
| [`/data/signals/scorecard.json`](https://hvtracker.net/data/signals/scorecard.json) | OSSF Scorecard data for all agents |
| [`/data/signals/provenance.json`](https://hvtracker.net/data/signals/provenance.json) | Supply-chain provenance signals |

---

## Specifications

HVTracker publishes formal specs for its methodology and processes:

- [Methodology v2.2](https://hvtracker.net/spec/methodology/v2.2) — scoring formula
- [Eligibility v1.0](https://hvtracker.net/spec/eligibility/v1.0) — listing requirements
- [Listing v0.1](https://hvtracker.net/spec/listing/v0.1) — lifecycle states and transitions
- [Data Schema v2.0](https://hvtracker.net/spec/data-schema/v2.0) — API schema
- [Provenance v0.1](https://hvtracker.net/spec/provenance/v0.1) — provenance detection
- [Build Report v0.1](https://hvtracker.net/spec/build-report/v0.1) — build transparency

---

## Project structure

```
hvtracker/
├── fetch_and_build.py        # Core build — fetches, scores, renders
├── template.html             # Jinja2 template (leaderboard UI)
├── templates/agent.html.j2   # Per-agent profile template
├── agents.json               # Agent registry (171 active + 7 legacy)
├── specs.py                  # Specification page generator
├── scan_scorecards.py        # Weekly OSSF Scorecard CLI scan
├── discover_agents.py        # Weekly agent discovery via GitHub search
├── .github/workflows/
│   ├── update.yml            # Staggered builds — 6 batches every 4 hours
│   ├── scorecard-scan.yml    # Weekly OSSF scan (Wed 04:00 UTC)
│   └── discover-agents.yml   # Weekly discovery (Sun 12:00 UTC)
└── data/                     # Generated data endpoints (API)
```

---

## License

Open source. Data licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
