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
- Never change production rank without an evidence gate (upset review);
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
  snapshot), `compute_trust_score_v2` (runtime calibration — IS the production
  trust_score/rank/grade since methodology v4.0).
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
  T2.1 ✅ #81 · T2.2 ✅ #82 · ticker ✅ #83 · T2.3 ✅ (weekly snapshot posts,
  deterministic, render-derived — no cron needed). Merged to `main`, NOT yet
  deployed (`railway up` pending).
- Cloudflare HTML/JSON edge-cache rule ✅ live in prod 2026-07-02 (dashboard,
  respects origin headers; TTFB 1.16s→~0.15s; auth/api/healthz stay uncached).
- 2026-07-02 batch (merged, awaiting the same pending deploy): #88 sitemap/feed
  Cache-Control · #89 runtime-drift snapshot-fields lock (T3.5 plumbing) ·
  #90 :root dedupe into site.css (only `--muted` stays as page override) ·
  #91 multi-stage Dockerfile (591MB; scorecard fetch now actually works —
  first deploy after this fetches fresh cache at build) · #92 T3.1 upset-review
  report → verdict NO-GO, T3.4 stays gated (drift dimension dominates).
- Deployed 2026-07-02: v3.2 batch (#81-#94) live + verified; branches pruned.
  GSC pass done narrowly (#94 — category titles; agent metadata already good).
- T3.2 ✅ /spec/runtime-trust v0.1 published (spec-matches-code test locks the
  §4 adjustment table to compute_trust_score_v2).
- T3.1 follow-up 2026-07-02: same-owner + repo-transfer drift false positives
  fixed (#96, #99), external_dependencies/tool_plugin_surface README-mention
  over-counting fixed (#98). Every one of the ~26 originally-flagged drift
  warnings traced to a false positive — zero real supply-chain risks found.
  Churn 19%→13%; root-caused the remainder to leaderboard density (median
  0.1pt gap between adjacent ranks), not remaining signal noise — see
  docs/t3.1-upset-review-2026-07-02.md addenda 1-4 for the full trail.
- T3.4 initial ship 2026-07-02: homepage default view flipped to the
  runtime-calibrated ranking with a toggle back to v1; server-rendered
  HTML/API/badges/signing stayed on v1. **Superseded same day** by an
  explicit owner decision to promote runtime calibration to the actual core
  ("switch to new scoring to the core... this being a legit profound change
  of the platform") — see the entry below.
- **T3.4 core swap 2026-07-02 (owner-confirmed, no heads-up to badge
  adopters):** `trust_score`/`rank`/`evidence_grade` ARE now runtime-
  calibrated everywhere — homepage, agent/category/org pages, `/data` API,
  sitemap, badge SVGs (`app.py` badge()), and signed credentials
  (`signing.py`, since it just reads `row["trust_score"]`). The old base
  score is preserved as `trust_score_historical_v1`/`rank_historical_v1`
  (comparison only, no longer live anywhere); `trust_score_v2`/`rank_v2` are
  now aliases of `trust_score`/`rank` for backward compat. The homepage
  toggle from the initial ship was repurposed: default view is just "the
  score" (no banner), with an opt-in "Compare to pre-calibration" view
  (`?compare=historical`) showing the old baseline. Score Lab's framing
  flipped from "hypothetical v2 preview" to "what changed at the cutover."
  `METHODOLOGY_VERSION` bumped v3.2→v4.0, which (a) resets every agent's
  rank-trend sparkline at this exact point (PR #100's mechanism) and (b)
  suppresses the day's trust_score/rank notification-bell events across the
  cutover (`derive_agent_events` methodology_by_date param) so the swap
  doesn't spam every watchlist with false-alarm deltas.
  **Concrete, confirmed consequence:** 27 agents flip letter grade (17
  downgrade) at the moment this deploys, including well-known projects that
  may have self-served a badge independently of any outreach — Google
  Genkit, Semantic Kernel, AutoGPT, Ollama, ECC, Hermes Agent, OpenClaw among
  them. Explicitly no announcement/changelog was made per owner instruction.
  Verified live end-to-end (full app, not just static render): homepage
  default, agent pages, Score Lab, `/badge/*.svg`, and `/api/v1/agents` all
  consistently return the new calibrated numbers; no server errors.
  Merged, NOT yet deployed.
- Post-swap cleanup 2026-07-03 (owner): per-row red "why" adjustment text
  removed from the leaderboard; Score Lab page RETIRED (template deleted,
  renderer actively removes score-lab/ from the output root, sitemap/nav/blog
  links cleaned incl. all 13 hand-written blog_static headers). The
  methodology page is now the canonical score-change reference — new
  "Runtime-Trust Calibration" section (#runtime-calibration) documents every
  adjustment value, and the formerly stale "descriptive only / do not affect
  rank" copy on methodology/agent/roadmap pages was corrected to match the
  v4.0 reality. Stale local artifacts deleted (bee-agent-framework agent
  page, i-am-bee org page, recently-active use-case) — the prod VOLUME may
  hold its own stale generated pages with dead /score-lab/ links; check at
  deploy.
- Next: T3.3 capability-surface page; internal-linking SEO pass (parked);
  consider fixing tool_plugin_surface's "search"/"code" pattern-mention
  breadth if it resurfaces in a future audit (currently gated behind real
  dependency evidence, so low-risk today).
