# CLAUDE.md

HVTracker (hvtracker.net) — AI-agent trust registry (HVTrust scores, grades A–D).
FastAPI + static-site generator, deployed on Railway. This file is the session
bootstrap: trust it instead of re-discovering the repo; verify only what you change.

## Hard rules
- One task = one branch (`feat/<id>`) = one PR off latest `main`. `main` is
  PR-only, squash-merge (linear history), 0 approvals required, CI not a gate.
- **Merging ≠ deploying.** Deploy is manual `railway up` from a clean worktree.
  NEVER deploy or run railway commands unless explicitly told.
- Never hand-edit generated output (`agents/`, `ecosystem/`, `org/`, `data/`,
  `sitemap.xml`, `index.html`, `blog/`, `compare/*-vs-*/`, `changes/`) — change
  the generator + re-render.
- Never change production rank without an evidence gate (Score Lab upset review);
  scoring changes ship as separate visible slices, never silent reweights.
- Monetization on hold (visa): no billing/paid-tier code.
- `output/history/*.json` daily snapshots are irreplaceable IP — never delete.

## Gates — every PR, all three green
```
python -m pytest && python fetch_and_build.py --render-only && python tests/validate_html.py
```
- CI additionally runs `ruff check .` (Python only), compileall, shellcheck.
- `--render-only` churns generated artifacts; restore before committing:
  `git checkout -- data/render_state.json og-v2.png`
- `index.html`, `methodology.html`, `output/` are gitignored (server-rendered).
- Tests need no Postgres: `db.py` falls back to `agents.json` when DATABASE_URL
  is unset; `tests/test_api.py` builds the site into a tmp OUTPUT_DIR.

## Map — grep, don't read wholesale
- `fetch_and_build.py` (~280KB, ~6k lines) — the generator. NEVER read whole;
  grep `def <name>`. Key: `compute_weekly_changes` (/changes/ + RSS via
  `build_changes_rss`), `compute_movers` (daily gainers/losers ticker, `limit`
  param), `derive_agent_events` (threshold events → `recent_events` → bell
  notifications), `_load_prior_snapshot` (rank Δ vs yesterday's history
  snapshot), `compute_trust_score_v2` (Score Lab calibration, not in prod rank).
- `app.py` — FastAPI serving, /healthz, 30-min signals-refresh scheduler.
- `auth.py` — OAuth/password accounts, watchlist, `/api/notifications`
  (derive-on-read from `recent_events` in `data/latest.json`; needs DB for
  sign-in). `auth.js` — header widget incl. notification bell.
- `db.py` — Postgres layer + file fallback. `schema.sql` idempotent DDL.
- `template.html` — homepage (leaderboard, Δ column, ticker). `templates/*.j2`
  — all other pages. Grade-B color #2c5282 is a design invariant.
- Blog post = 4 surfaces: `blog_static/<slug>/`, blog_index card, `sitemap_urls`,
  `blog_feed_items` (all wired in `fetch_and_build.py`).
- Scorecard data comes from our own CLI scan via the `data` branch (not deps.dev).

## Local dev & checks
- `./dev.sh` — full stack: Postgres :5433, Redis, uvicorn :8000; with
  HVT_DEV_AUTH=1 use "Dev login" on /login (no OAuth needed).
- `.claude/launch.json` — preview configs (e.g. static-site on :8011).
- Prod is read-only checkable: `curl -A "Mozilla/5.0" https://hvtracker.net/healthz`
  (Cloudflare blocks default UAs). Railway traffic ≈97% bots; GA counts humans.

## Working style
- State assumptions; ask only when interpretations genuinely diverge.
- Minimum code that solves the problem; no speculative features/abstractions.
- Surgical diffs: every changed line traces to the request; match existing style;
  mention unrelated dead code, don't delete it.
- Turn tasks into verifiable goals (test that reproduces → make it pass); run
  the three gates before calling anything done.

## Now / next (update as milestones ship)
- Plan: `docs/product-plan-2026-h2.md`. v3.2 (Retention & Freshness) underway:
  T2.1 ✅ #81 · T2.2 ✅ #82 · ticker ✅ #83 (merged, NOT yet deployed).
- Next: T2.3 deterministic weekly trust-snapshot post (no LLM v1); Cloudflare
  HTML/JSON edge-cache rule (user's dashboard task); GSC page-2 metadata pass.
