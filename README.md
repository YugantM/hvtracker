# HVTracker

**AI Agent Trust Registry**

**Live:** [hvtracker.net](https://hvtracker.net)  
**Public data API:** [hvtracker.net/data/latest.json](https://hvtracker.net/data/latest.json)

HVTracker ranks open-source AI agent projects by evidence-weighted trust, not only stars. The v1 launch tracks **171 agents** across **14 categories**, with public signals for activity, adoption, transparency, safety, identity, provenance, and rank movement.

The goal is simple: help builders, researchers, and security-minded teams answer, "Which AI agent projects look active, adopted, transparent, and verifiable right now?"

---

## V1 Snapshot

- **171** active open-source AI agent projects
- **14** curated categories
- **6** staggered refresh batches per day
- **90-day** per-agent history where available
- Public JSON endpoints for the leaderboard, per-agent records, build reports, and selected signal files

Signals refresh every 4 hours in batches. A full refresh cycle completes in 24 hours.

---

## What Makes It Different

Most agent lists are manually curated directories or popularity rankings. HVTracker combines curation with independently checkable public signals:

| Dimension | Max | What it measures |
|---|---:|---|
| **Activity** | 25 | Commit freshness and 4-week development activity |
| **Adoption** | 20 | Stars and package downloads where available |
| **Transparency** | 20 | License, documentation, and OSSF Scorecard visibility |
| **Safety** | 20 | OSSF Scorecard, provenance, and signed commits |
| **Identity** | 15 | Evidence grade and listing verification status |

Each agent also receives an **evidence grade**:

| Grade | Meaning |
|---|---|
| A | Multiple independent signal types are available |
| B | Strong public evidence, with some signal gaps |
| C | Basic public evidence |
| D | Mostly GitHub-only evidence |

---

## Categories

| Category | Count |
|---|---:|
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

## Public Signals

| Signal | Source |
|---|---|
| Stars, forks, language, license, last push | GitHub REST API |
| 4-week commit activity | GitHub Stats API and recent commits fallback |
| Weekly downloads | npm Registry and PyPI/pypistats |
| OSSF Scorecard | deps.dev API and weekly CLI scan |
| Package provenance | npm and PyPI attestation endpoints |
| Signed commit ratio | GitHub Commits API |
| Hacker News mentions (30d) | Algolia HN Search API |
| Public action fingerprints | GitHub Search API |

HVTracker is not a security certification. Missing provenance, Scorecard, or signature data can mean the signal is unavailable, not that a project is unsafe.

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
3. Scores, evidence grades, trust breakdowns, rank deltas, and per-agent histories are computed.
4. Static pages, JSON endpoints, feed files, specs, sitemap, and build reports are generated.
5. GitHub Pages serves the static site.

---

## Running Locally

```bash
git clone https://github.com/YugantM/hvtracker.git
cd hvtracker
pip install -r requirements.txt

export GITHUB_TOKEN=$(gh auth token)  # or a personal access token
python fetch_and_build.py             # full build
python fetch_and_build.py --batch 1/6 # one refresh batch

python3 -m http.server 4173
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173).

---

## Submitting Or Correcting An Agent

Use the [agent listing issue template](https://github.com/YugantM/hvtracker/issues/new?template=agent-listing.yml). A listed project should be:

- A public, non-archived GitHub repository
- Related to AI agents or agent infrastructure
- Active within the last 12 months
- Not already listed

Include the canonical repository, preferred display name, category suggestion, package names, and any correction details.

---

## Public Data API

The v1 public dataset is available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). CORS is open for public endpoints.

| Endpoint | Description |
|---|---|
| [`/data/latest.json`](https://hvtracker.net/data/latest.json) | Current public leaderboard snapshot |
| [`/data/agents/{slug}.json`](https://hvtracker.net/data/agents/dify.json) | Per-agent public detail with history and events |
| [`/data/build_report.json`](https://hvtracker.net/data/build_report.json) | Build integrity report |
| [`/data/signals/scorecard.json`](https://hvtracker.net/data/signals/scorecard.json) | OSSF Scorecard signal cache |
| [`/data/signals/provenance.json`](https://hvtracker.net/data/signals/provenance.json) | Package provenance signal cache |

---

## Specifications

- [Methodology v2.2](https://hvtracker.net/spec/methodology/v2.2) - scoring formula and signal definitions
- [Eligibility v1.0](https://hvtracker.net/spec/eligibility/v1.0) - listing requirements
- [Listing v0.1](https://hvtracker.net/spec/listing/v0.1) - listing lifecycle
- [Data Schema v2.0](https://hvtracker.net/spec/data-schema/v2.0) - public API schema
- [Provenance v0.1](https://hvtracker.net/spec/provenance/v0.1) - provenance detection
- [Build Report v0.1](https://hvtracker.net/spec/build-report/v0.1) - build transparency

---

## Launch And Business Notes

- [V1 launch checklist and zero-budget marketing plan](docs/launch-v1.md)
- [Open-core and company-readiness notes](docs/open-core.md)

---

## Repository Layout

```text
hvtracker/
├── fetch_and_build.py        # Core build, scoring, and rendering
├── template.html             # Leaderboard template
├── templates/agent.html.j2   # Per-agent profile template
├── templates/methodology.html.j2
├── agents.json               # Curated agent registry
├── specs.py                  # Specification page generator
├── scan_scorecards.py        # Weekly OSSF Scorecard scan
├── discover_agents.py        # Weekly discovery scan
├── docs/                     # Launch, research, and operating docs
├── data/                     # Generated public data endpoints
└── agents/                   # Generated per-agent pages
```

---

## License

The v1 public data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Review [docs/open-core.md](docs/open-core.md) before changing the public/private data boundary for a future company-backed edition.
