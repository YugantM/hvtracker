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
./scripts/gates.sh
```
- Runs ruff → pytest → `--render-only` → `validate_html.py` with the `.venv`
  interpreter (bare `python` isn't on PATH; system `python3` lacks the deps),
  then restores the artifacts the render churns (`data/render_state.json`,
  `og-v2.png`, `scorecard-cache.json`) unless they were already dirty.
- CI runs the same on every PR (the render smoke too, unless MCP-only), plus
  compileall, pip-audit and shellcheck.
- A local render reports a board-churn invariant violation by design; check
  production's `/data/build_report.json`, not the local one.
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
  `derive_agent_events`, `select_stale_batch` (4 h batch rotation), `refresh_argv`.
- `app.py` — FastAPI serving, /healthz, scheduler (`_start_scheduler`: one 4 h job =
  batch + signals; standalone signals only if `SIGNALS_REFRESH_MIN` is set), boot
  refresh path (`_startup`).
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
- **Listing batches PAUSED (2026-10-02, owner).** Google recrawls only ~27
  sitemap URLs/day. A URL Inspection sweep on 2026-10-01 found 143 of 1,893
  sitemap URLs never crawled ("URL is unknown" / "Discovered – currently not
  indexed"), 22 of them from listing batches 1–2 (#296, #310); new rows only
  lengthen that queue. Resume when the batch 1–2 agent pages show as indexed
  in GSC URL Inspection and under ~2% of sitemap URLs are uncrawled (sweep:
  ~/hv_marketing/data/indexing-2026-10-01/inspect_bulk.py). Roster removals
  and fixes are not paused.
- Phase 9 MCP registry feed DEPLOYED 2026-10-02 (#312): /registry/<policy>
  v0.1 subregistry, publisher-tie rule for graded allowlists, daily
  registry-snapshot.yml → `data` branch. Watch the "registry" channel on
  /live/ for demand. Phase 8 "Citable provenance" (provenance study,
  chain-of-custody profiles, incident watch) DEPLOYED 2026-10-01. Earlier plans: Phase 7 https://claude.ai/artifact/92fZ6PMrVQUbPbrxQp7B8a,
  Phase 6 https://claude.ai/artifact/DVwRksqt544SfWmEKoLpVu. Open owner items
  and check dates: docs/changelog.md and docs/ctr-tests.md.
- MCP server runs SDK v2 (`MCPServer`): serves 2026-07-28 and 2025 clients;
  GET /mcp is 405 and `subscriptions/listen` is unregistered on purpose
  (both hang open under v2). Bumping SERVER_VERSION = mirror in
  YugantM/hvtracker-mcp, tag, re-dispatch publish-mcp-registry.yml.
- Titles/meta descriptions change ONLY via a logged CTR batch
  (`CTR_TEST_COMPARE` + docs/ctr-tests.md). Badge adopters live in
  `BADGE_ADOPTERS`, verified weekly by scripts/check_adopters.py.
- Sitemap `<lastmod>` comes from a per-page content fingerprint (#314). Any
  edit that changes every page of a type (a template line, sitewide markup)
  re-dates all of them unless you also bump `LASTMOD_FP_VERSION`, whose
  migration re-keys stored hashes on the first render and keeps the dates.
  Wrapping new text in `<!--lastmod:skip-->` is not enough: the change of
  surrounding whitespace counts (that re-dated 1,445 profiles on 3 Oct, #322).
- Dark mode is opt-in per page (`<html class="theme-auto">`); audit contrast
  before opting a page in. Grade colours are literal hex, never tokens.
