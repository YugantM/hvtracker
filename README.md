# HVTracker — AI Agent Leaderboard

**Live:** [hvtracker.net](https://hvtracker.net)  
**Repo:** [github.com/YugantM/hvtracker](https://github.com/YugantM/hvtracker)

HVTracker is an open-source leaderboard that tracks the health and momentum of 65+ open-source AI agent repositories on GitHub. Scores update daily at 06:00 UTC, with rank-change deltas (▲▼) computed between runs.

---

## Table of contents

- [What it tracks](#what-it-tracks)
- [By category](#by-category)
- [How it works](#how-it-works)
- [Scoring formula](#scoring-formula)
- [Project structure](#project-structure)
- [Running locally](#running-locally)
- [Adding an agent](#adding-an-agent)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [data.json API](#datajson-api)
- [License & contributing](#license--contributing)

---

## What it tracks

For every agent repo in [`agents.json`](./agents.json), HVTracker fetches:

| Field | Source |
|---|---|
| **Stars** | `stargazers_count` |
| **Forks** | `forks_count` |
| **Last push** | `pushed_at` (shown with freshness dot: green ≤7d, olive ≤30d, brown ≤90d, gray >90d) |
| **4-week commits** | Sum of weekly commits from `/stats/commit_activity` |
| **Downloads (7d)** | Weekly downloads from npm and/or PyPI (summed if both), shown with source label ("npm", "pypi", or "npm+pypi") |
| **Language** | Primary language from GitHub |
| **Description** | Repo description (truncated to 120 chars) |
| **Open issues** | `open_issues_count` |

The **rank-change (Δ) column** compares the current ranking to the ranking stored in the previous `data.json`. Deltas display as:

- **▲N** (green) — moved up N positions
- **▼N** (red) — moved down N positions
- **—** (gray) — unchanged
- **NEW** (green badge) — first appearance in the leaderboard

Each agent also belongs to one of **8 categories** (shown as a badge in the table). Click a category pill at the top of the page to filter the leaderboard to a single category — ranks switch to **category rank** with the global rank displayed in small muted text beside it.

---

## By category

HVTracker organizes agents into 8 curated categories. The taxonomy is maintained in [`agents.json`](./agents.json) via a `category` field on each entry.

| Category | Count | Description |
|---|---|---|
| **Coding Agents** | 20 | AI pair programmers, code-generation agents, and IDE assistants that write, edit, and debug code |
| **Agent Frameworks** | 17 | Libraries and SDKs for building, orchestrating, and deploying AI agents |
| **Workflow Platforms** | 4 | End-to-end platforms for building LLM-powered applications with visual or declarative pipelines |
| **Browser & Computer Use** | 6 | Agents that interact with web browsers, desktop GUIs, or perform computer-use tasks |
| **LLM Gateways & Infra** | 4 | API gateways, sandboxes, monitoring, and infrastructure for LLM-powered agents |
| **Memory & Knowledge** | 5 | Persistent memory layers, knowledge bases, and personal AI assistants with long-term context |
| **Research & Data** | 5 | Autonomous research agents, web crawlers, data extraction, and model fine-tuning tools |
| **Multi-Agent Systems** | 4 | Frameworks for multi-agent collaboration, role-playing, and emergent agent societies |

### Proposing a new category

Categories are not automatically assigned — they're curated by the maintainers. To propose a new category:

1. Open a [GitHub issue](https://github.com/YugantM/hvtracker/issues) with the title `Category proposal: <name>`.
2. Explain what the new category covers, why existing categories don't fit, and list 3+ existing agents that would belong to it.
3. Maintainers will review and either add the category or suggest an alternative fit.

When adding a new agent to [`agents.json`](./agents.json), pick the most specific existing category. If unsure, mention it in your PR and maintainers will assign one.

---

## How it works

```
agents.json   ──┐
                 ├──►  fetch_and_build.py  ──►  index.html   (published via GitHub Pages)
previous         │                              data.json    (machine-readable API + delta baseline)
data.json (opt) ─┘
```

1. **`fetch_and_build.py`** reads the agent list from `agents.json`.
2. For each repo, it calls the GitHub API (parallel, 10 threads) to fetch stars, forks, commit activity, last push date, language, and description. If the agent has `npm_package` and/or `pypi_package` fields, it also fetches weekly download counts from the npm registry and PyPI (pypistats) APIs, summing them if both are present.
3. A **health score** (0–100) is computed from four sub-scores (see below).
4. Agents are sorted by score descending and assigned ranks.
5. The previous `data.json` is loaded to compute **rank deltas** (▲▼/—/NEW).
6. `index.html` is rendered from `template.html` via Jinja2.
7. `data.json` is written as a machine-readable snapshot of the full leaderboard.

The site is a single static HTML file served by **GitHub Pages**. Cloudflare provides DNS (CNAME record → GitHub Pages) and edge caching.

---

## Scoring formula

Each agent receives a composite **0–100** score from four components:

```
Score = stars(30) + freshness(25) + activity(25) + community(20)
```

| Component | Max | Formula |
|---|---|---|
| **Stars** | 30 | `min(30, ln(1 + stars) / ln(1 + 100000) × 30)` — logarithmic scale; 100k stars = 30 pts |
| **Freshness** | 25 | `max(0, 25 × (1 − days_since_push / 180))` — linear decay over 6 months |
| **Activity** | 25 | `min(25, ln(1 + recent_commits) / ln(1 + 100) × 25)` — commits in last 4 weeks; 100 = 25 pts |
| **Community** | 20 | `min(20, ln(1 + forks) / ln(1 + 20000) × 20)` — logarithmic scale; 20k forks = 20 pts |

Score pills on the table are color-coded: green (≥70), amber (≥45), gray (<45).

On viewports narrower than 640 px, the description column hides to keep the table usable on mobile screens. All columns remain horizontally scrollable.

---

## Project structure

```
hvtracker/
├── fetch_and_build.py      # Main build script — fetches GitHub data, scores, renders site
├── template.html           # Jinja2 template — design, CSS, client-side sort JS
├── agents.json             # Flat list of {repo, name} objects to track
├── index.html              # Generated output — the live leaderboard (committed to repo)
├── data.json               # Machine-readable snapshot — used as delta baseline (committed to repo)
├── requirements.txt        # Python dependencies (requests + jinja2 only)
├── CNAME                   # hvtracker.net → GitHub Pages
├── .github/workflows/
│   └── update.yml          # GitHub Actions — daily cron at 06:00 UTC + manual trigger
└── CLAUDE.md               # Karpathy behavioral guidelines (simplicity, surgical changes, goal-driven)
```

---

## Running locally

### Prerequisites

- Python 3.9+
- A [GitHub personal access token](https://github.com/settings/tokens) (classic) with `public_repo` scope (or `gh auth token` if GitHub CLI is installed)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/YugantM/hvtracker.git
cd hvtracker

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the build
# Option A: using GitHub CLI
export GITHUB_TOKEN=$(gh auth token)
# Option B: using a personal access token directly
export GITHUB_TOKEN=ghp_your_token_here

python fetch_and_build.py

# 4. Open the result
open index.html
```

The script prints one line per agent (`OK  owner/repo  score=NN.N`) and finishes with:

```
Wrote data.json with 65 agents.
Built index.html with 65 agents.
```

On the first run (no `data.json` exists), all agents show **NEW** in the delta column. Run it a second time to establish a baseline and see **—** (unchanged) for stable agents.

---

## Adding an agent

Edit [`agents.json`](./agents.json) and add a new entry:

```json
{ "repo": "owner/repo-name", "name": "Display Name" }
```

- **`repo`** — the GitHub owner/repo path (exactly as it appears in the URL)
- **`name`** — the display name shown in the leaderboard
- **`npm_package`** (optional) — the npm package name for fetching weekly download counts
- **`pypi_package`** (optional) — the PyPI package name for fetching weekly download counts

After adding, rebuild (`python fetch_and_build.py`) and open a pull request. Alternatively, the workflow will auto-rebuild and deploy when the PR is merged.

---

## CI/CD (GitHub Actions)

**Workflow file:** [`.github/workflows/update.yml`](.github/workflows/update.yml)

| Trigger | Behavior |
|---|---|
| **Schedule** — every day at 06:00 UTC | Fetches latest data, regenerates `index.html` + `data.json`, commits + pushes |
| **Manual** (`workflow_dispatch`) | Trigger from the Actions tab anytime |

The workflow prefers `secrets.GH_PAT` (a personal access token, 5,000 req/hr) and falls back to `secrets.GITHUB_TOKEN` (1,000 req/hr) for API authentication. Commit messages follow the format: `chore: regenerate leaderboard YYYY-MM-DD`.

---

## data.json API

The `data.json` file serves double duty:

1. **Delta baseline** — previous rankings are loaded on each run to compute ▲▼/—/NEW deltas.
2. **Machine-readable API** — consumers can fetch the raw JSON for their own tooling.

**Endpoint:** `https://raw.githubusercontent.com/YugantM/hvtracker/main/data.json`

**Schema:**

```jsonc
{
  "updated": "2026-05-23 02:47 UTC",
  "total": 65,
  "agents": [
    {
      "name": "Dify",
      "repo": "langgenius/dify",
      "url": "https://github.com/langgenius/dify",
      "rank": 1,
      "previous_rank": null,    // null if new (no previous entry)
      "rank_delta": null,       // null if new; positive = improved; negative = declined; 0 = unchanged
      "stars": 142288,
      "forks": 22379,
      "last_push": "2026-05-23",
      "days_ago": 0,
      "weekly_commits": 539,
      "score": 100.0,
      "description": "Production-ready platform for agentic workflow development.",
      "language": "TypeScript",
      "open_issues": 820,
      "npm_package": "",
      "pypi_package": "",
      "weekly_downloads": null
    }
    // ... more agents
  ]
}
```

---

## License & contributing

This project is open source. To contribute:

1. Add or update agents in [`agents.json`](./agents.json).
2. Rebuild locally to verify (`python fetch_and_build.py`).
3. Open a pull request.

When adding agents, follow these guidelines:

- The repo must be a legitimate, open-source AI agent project.
- Choose the most specific `category` from the 8 listed above. If unsure, leave a comment in your PR. Category assignments are validated against the canonical list.
- Verify the repo exists and is active on GitHub before adding.
- Keep the list sorted roughly by notability — the build script will sort by score automatically, but the source list should be curated.

---

## Constraints

- **No new dependencies** beyond `requests` + `jinja2` (no npm, no frameworks).
- **Page weight under 100 KB** (currently ~99 KB with 65 agents).
- **Free tiers only** — GitHub Pages, Cloudflare DNS, no paid services.
- **No secrets in the repo** — the workflow uses `secrets.GITHUB_TOKEN`.

---

Built with ♥ for the open-source AI agent community.
