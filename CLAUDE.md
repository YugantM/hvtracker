# CLAUDE.md

HVTracker (hvtracker.net) — AI-agent trust registry (HVTrust scores, grades A–D).
FastAPI + static-site generator, deployed on Railway. This file is the session
bootstrap: trust it instead of re-discovering the repo; verify only what you change.
Milestone history lives in `docs/changelog.md` — record new milestones there.

## Hard rules
- One task = one branch = one PR off latest `main`. `main` is PR-only,
  squash-merge (linear history). `main` == production (since #225).
- **Merging ≠ deploying.** Deploy only when the owner says so, only from `main`,
  following the runbook below. Never run mutating railway commands otherwise.
- Never hand-edit generated output (`agents/`, `ecosystem/`, `org/`, `data/`,
  `sitemap.xml`, `index.html`, `blog/`, `compare/*-vs-*/`, `changes/`) — change
  the generator + re-render.
- Never change production rank without an evidence gate (upset review);
  scoring changes ship as separate visible slices, never silent reweights.
- No `<title>`/meta-description changes except as a deliberate, measured SEO
  batch (the #114 churn lesson).
- Monetization on hold (visa): no billing/paid-tier code.
- `output/history/*.json` daily snapshots are irreplaceable IP — never delete.
  A snapshot that must not be compared against goes in
  `PARTIAL_SNAPSHOT_DATES` (fetch_and_build.py, mirrored in app.py).

## Gates — every PR, all green
```
python -m pytest && python fetch_and_build.py --render-only && python tests/validate_html.py
```
- CI runs pytest, `ruff check .`, compileall, pip-audit, shellcheck on PRs;
  the render + validate_html smoke runs only on `main` — run it locally for
  generator/template changes.
- `--render-only` churns tracked artifacts; restore before committing:
  `git checkout -- data/render_state.json og-v2.png`
- Tests need no Postgres (`db.py` falls back to `agents.json`); conftest sets
  `HVT_BOOT_REFRESH=0` so app startup never spawns real refreshes under pytest.
- `tests/test_predeploy_check.py` fails the PR if a runtime module or
  `BASE_DIR` asset isn't COPY'd by the Dockerfile (it copies by filename).

## Deploy runbook (owner-approved deploys only)
1. `git worktree add --detach ../hvtracker-deploy-<date> origin/main`; `cd` into it
   (`railway up <path>` from outside uploads nothing).
2. `python scripts/predeploy_check.py .` — must print OK (image contents +
   roster ≥ live `catalog_agents`).
3. Check `/healthz` `refresh_in_progress` is false — a deploy kills a running
   refresh (that is how 22 Sep went wrong).
4. `railway up --detach --project 336fa70c-21a7-4524-984b-b6035ea42773
   --environment production --service web`; poll `railway deployment list
   --service web` until SUCCESS (`--ci` exits 1 on log-stream errors even when fine).
5. Verify: `/healthz` `scheduler_running: true` with `scheduled_jobs`; boot log
   `[startup]` lines; later `/data/build_report.json` `board_invariant_violations: []`.
6. Rollback: GraphQL `deploymentRedeploy(id: "<last good>")` re-runs the old
   image; `railway redeploy` only re-runs the latest (possibly failed) one.

## Map — grep, don't read wholesale
- `fetch_and_build.py` (~8k lines) — the generator. Grep `def <name>`. Key:
  `compute_trust_score_v2` (IS production trust_score/rank/grade), `assign_ranks`,
  `check_board_invariants`, `compute_movers`, `load_history`/`_load_prior_snapshot`,
  `derive_agent_events`, `select_stale_batch` (2 h batch rotation), `refresh_argv`.
- `app.py` — FastAPI serving, /healthz, scheduler (`_start_scheduler`: 2 h batch,
  signals every `SIGNALS_REFRESH_MIN`=360 min), boot refresh path (`_startup`).
- `mcp_server.py` — MCP tools (dominant machine channel). `auth.py` — accounts,
  watchlist, notifications (needs DB). `db.py` + `schema.sql` — Postgres layer.
- `template.html` — homepage. `templates/*.j2` — all other pages. Grade-B color
  `#2c5282` is a design invariant.
- Blog post = 4 surfaces: `blog_static/<slug>/`, blog_index card, `sitemap_urls`,
  `blog_feed_items` (all wired in `fetch_and_build.py`).
- Scorecard data: our own CLI scan (hourly shards, runs from `main`) → `data` branch.

## Operations
- Railway project `hvtracker-cron`: services `web` (+ volume), Postgres, Redis.
  Hobby plan, **$15 hard cap stops the site**. Memory is most of the bill and
  is driven by scheduled re-renders (each rewrites the whole site).
- Monitors (GitHub Actions → issues): `bill-monitor` (`bill-alert`),
  `freshness-monitor` (`stale-data`). Read the Actions log for exact numbers.
- Prod is read-only checkable: `curl -A "Mozilla/5.0" https://hvtracker.net/healthz`
  (Cloudflare blocks default UAs). Railway traffic ≈97% bots; GA counts humans.
- History backups: volume, Railway bucket (`hvtracker-archive`, written each
  render), local mirror `~/hvtracker-backups/backup_history.sh`. The GitHub
  backup repo can't read the private `/output/history/` path — see changelog.
- Local: `./dev.sh` (Postgres :5433, Redis, uvicorn :8000; `HVT_DEV_AUTH=1` for
  Dev login). `.claude/launch.json` has preview configs.

## Working style
- State assumptions; ask only when interpretations genuinely diverge.
- Minimum code that solves the problem; no speculative features/abstractions.
- Surgical diffs: every changed line traces to the request; match existing style;
  mention unrelated dead code, don't delete it.
- Turn tasks into verifiable goals (test that reproduces → make it pass); run
  the gates before calling anything done.

## Now / next
- Active plan (phases, decisions, UI mockups):
  https://claude.ai/artifact/KfF5N95t1Y114J1nABMjfe — Phase 0 done and deployed
  2026-09-23; Phase 1 (guardrails) in progress; then Phase 2 (UI/UX), Phase 3
  (growth/durability).
