# Plan: Move History Storage To Railway

## Goal

Stop treating historical leaderboard snapshots as Git-tracked generated files.
Move history into Railway-managed storage so the product can:

- keep GitHub focused on code and curated seed data
- expose only a free 30-day history window through the public API
- preserve longer retention privately for future commercial use

## Target model

- GitHub:
  - application code
  - templates
  - curated registry seed data (`agents.json`)
- Railway Postgres:
  - daily per-agent history
  - refresh run metadata
  - optional precomputed reputation events
- Optional private archive storage:
  - raw full snapshots for recovery/audit
- Public API:
  - last 30 days only

## Recommended schema direction

1. `refresh_runs`
   - one row per refresh/build
   - stores run mode, timestamps, success/failure, generated snapshot date

2. `agent_history_daily`
   - one row per agent per snapshot day
   - stores rank, trust score, evidence grade, key signals, and enough data to
     rebuild trend lines without reading Git history

3. Optional `agent_events`
   - stores derived timeline events
   - useful if event derivation becomes expensive at read time

## Product boundary

- Free public access:
  - current leaderboard
  - current per-agent record
  - 30-day history via API
- Private/commercial later:
  - history beyond 30 days
  - bulk exports
  - premium monitoring/alerts/watchlists

## Migration plan

### Phase 1: Add storage without changing public behavior

- add new Postgres tables
- backfill them from existing `output/history/*.json`
- dual-write every new refresh to both filesystem and Postgres

Success check:
- every new daily snapshot exists in Postgres
- current site behavior stays unchanged

### Phase 2: Switch reads to Postgres

- move trend calculations, movers, and event derivation to DB-backed reads
- make `/data/agents/<slug>.json` pull 30-day history from Postgres
- keep filesystem history only as short-term compatibility/cache

Success check:
- agent trend/timeline pages render from DB-backed history
- public API returns only the allowed 30-day window

### Phase 3: Remove Git-tracked history dumps

- stop committing generated history files to the repo
- stop relying on repo history snapshots for deploy recovery
- optionally keep raw snapshots in private object storage instead

Success check:
- production no longer depends on committed `output/history/*.json`
- deploys recover from Railway-managed state, not GitHub-generated artifacts

## Notes

- Do not start by storing only giant raw JSON blobs in Postgres.
  Queryable per-agent daily rows are the better primary model.
- If raw snapshots are still useful for audit/recovery, keep them in private
  archive storage, not as public repo artifacts.
- Lowest-risk first implementation:
  - schema
  - backfill script
  - dual-write on refresh
