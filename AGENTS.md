# AGENTS.md

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
- Scoring v4.1 2026-07-05 (owner: fix the "three 100s, different ranks looks
  rigged" report): `compute_trust_score_v2` now applies a SOFT CEILING —
  positive bonuses scaled by `min(1,(100-base)/20)` (full ≤80, zero at 100),
  penalties absolute — so bonuses can't clamp strong agents onto an identical
  100.0. Ties break EVIDENCE-FIRST via `_rank_sort_key` (trust_score →
  confidence → scorecard → signed-commits → momentum → stars → slug; popularity
  RETAINED but below audit signals, per owner) and display at a shared `=N`
  rank (`display_rank`/`is_tied` on rows, wired in template + the JS
  updateRankDisplay global branch). Hardening: MCP `declared` bonus +1.0→0
  (only `implemented` scores). METHODOLOGY_VERSION v4.0→v4.1 (sparkline reset +
  cutover notification suppression). Spec bumped v0.1→v0.2 (Active), well-known
  + methodology + roadmap links updated; the old /spec/runtime-trust/v0.1/ is a
  stale volume orphan at deploy (like score-lab). Evidence gate (isolated
  OLD-vs-NEW on identical bases): 0 agents move >10 ranks, 4 grade flips (all
  downward corrections from removing MCP-declared inflation). Deployed
  2026-07-05 (#107 + ticker-scroll fix #108) — but a worse, pre-existing
  compounding bug surfaced immediately after; see v4.2.
- Scoring v4.2 2026-07-05 (owner: "leaderboard too different" investigation):
  root-caused the inflated live board to a COMPOUNDING bug — the build loop
  never seeded `row["trust_score"]` with the freshly-computed base before
  `compute_trust_score_v2` read it, so the bounded ±adjustment layered on the
  PRIOR build's already-calibrated score and ratcheted every render toward the
  0/100 rails (humanlayer: real base 50.9 → prod 100.0, reported adj 0.0;
  ratchet sim 50.9→70.9→88.7→98.6→99.6). v4.1's soft ceiling only froze the
  drift near the top, it never undid it — that's why the board looked "too
  different." Fix is one line: seed the base into `row["trust_score"]` before
  the v2 call (`fetch_and_build.py` ~5100) so each build is idempotent;
  regression test `test_runtime_calibration_does_not_compound_across_renders`
  locks non-compounding + idempotency. METHODOLOGY_VERSION v4.1→v4.2 (sparkline
  reset + cutover notification suppression). Evidence gate (recompute the whole
  board correctly): max de-inflates to ~92.8, 0 pinned ≥99.5, sensible top
  (vercel-ai-sdk/codex/haystack/n8n/pydanticai); mean |Δrank| ~61, 215/319
  grade flips — huge because the LIVE board was wrong, not the corrected one.
  Methodology changelog + policy-log updated. Deployed 2026-07-05 per owner.
- Bill fix VERIFIED 2026-07-06 (Railway metrics API): web-service RAM avg
  0.660→0.228 GB (−65%) after #106 subprocess refresh; flat baseline, spikes
  release. Est. memory cost $6.60→$2.28/mo. Re-check 2026-07-12; next lever
  is consolidating the two Postgres services.
- Evidence-coverage grade SHIPPED 2026-07-06 (#112, T3.3 slice, owner: "create
  a real coverage grade"): `coverage_grade(signal_types)` A≥4/B3/C2/D1 counts
  INDEPENDENT public signal types (GitHub always, downloads, supply-chain,
  behavioural, HN) — separate from `evidence_grade` (score band). Live dist
  A/B/C/D=108/68/52/91 (vs evidence_grade 32/58/58/171). On agent pages (hero
  + how-to-read) and public API (`coverage_grade`/`signal_types`/`signal_coverage`).
  No change to trust_score/rank/evidence_grade.
- Content-truth pass + v4.2 announcement SHIPPED 2026-07-06 (owner chose blog
  + real coverage grade over changelog-only/reword): README v3.1→v4 section,
  base+calibration formula, two-grades table, categories→live link, cadence
  2h→~30min, live-count 172→300+; methodology FAQ/updates cadence fixed;
  GitHub About still to update via `gh repo edit` (see below). New blog post
  `blog_static/calibration-fix-and-coverage-grade/` announces the v4.2
  compounding fix + coverage grade, wired to all 4 surfaces (post/index
  card/sitemap/feed).
- UI/UX fix batches DEPLOYED 2026-07-23 (owner-approved): #198 (P0 bugs —
  category invisible grades, Last Push sort, hero grid, stale methodology/
  roadmap/blog copy; AA contrast tokens in site.css; keyboard-accessible
  filters/sort; `<main id="main">` on 17 page types; shared
  `_site_header.html.j2`; auth.js popover fixes) and #199 (skip link,
  aria-current nav, blog snapshot/quarterly full chrome, GA localhost guard
  everywhere, branded /correct//submit, category internal links on org/
  ecosystem/use_case, unified grade pills + legends, table scope attrs,
  compare coverage outlined chip, movers empty states, 26px tap targets).
  Verified live end-to-end via cache-busted origin curls (edge cache serves
  stale HTML for its TTL — always verify with a `?cb=` query string): css
  hash matched local build, grade pills on category+org pages, blog chrome,
  /submit//correct branding. Deferred UI items (need generator edits,
  avoided to not collide with stashed roster WIP): llms.txt v0.1→v0.2 spec
  link 404, agent sibling-list activity score unlabeled, footer/analytics
  partial extraction, score-color threshold centralization, Activity Score
  visual demotion, bell glyph ◉→SVG, compare tray mobile overlap.
- Prod-volume orphan check DONE at the 2026-07-23 deploy: /score-lab/ → 301
  /methodology/#runtime-calibration, /spec/runtime-trust/v0.1/ → 301 v0.2,
  /org/i-am-bee/ → 301 /org/, /agents/bee-agent-framework/ → 410
  (retired.json), /use-case/recently-active/ → 404. Zero action needed.
  GitHub About text already says "300+" (done at some point before
  2026-07-23 — plan item closed).
- **Verify-feed timestamp fix + /live/ usage surface 2026-08-09** (merged,
  NOT deployed). Reported symptom: the /verify/ "Recently checked" feed showed
  most entries with the same elapsed time. Root cause: `_refresh_verify_feed`
  (nightly, hour=4 UTC) called `verify_log.record()` — the CLIENT-check writer
  — for every provisional row, so each night restamped `checked_at` and bumped
  `checks` on all of them. They landed 9-in-9-seconds, rendered identical
  "Nh ago", held feed slots 1-9 permanently (the target query's `ORDER BY
  checked_at ASC` + sequential restamping is order-preserving), and inflated
  `checks` to 11-51 vs 1-7 on untouched curated rows — ~50 daily self-writes
  since the job shipped 2026-06-19 (39dd8c8e). All 9 were grade C because
  `open_lookup.py:72` can only emit C/D, so the top of the feed read as a wall
  of identical rows. Star data was never wrong (spot-checked vs GitHub).
  Fix: split the column meanings — `checked_at`/`checks` mean "a client asked"
  and only `record()` writes them; new `refreshed_at` + `db.refresh_verify_check`
  / `verify_log.refresh()` carry "we revalidated our own data", never insert,
  never reorder. `verify_check_targets` now orders by
  `COALESCE(refreshed_at, checked_at)`; the job keys the UPDATE on the row it
  selected, not `v["resolved"]` (a transferred repo would no-op and strand the
  row head-of-line — the #169 failure mode). `name` is COALESCEd both paths
  (refresh had been nulling curated display names). Feed UI now shows "checked
  Xd ago" with "revalidated Yh ago" as separate metadata.
  `scripts/backfill_verify_checks.py` (dry-run default, re-run safe) estimates
  and removes the machine-generated `checks`; **it needs DATABASE_URL and has
  NOT been run — owner action.** `checked_at` on those 9 rows is left as-is
  (any corrected value would be a guess; they now age down naturally).
  NEW /live/ surface: `usage.py` counts machine channels durably —
  `usage_hourly(bucket, channel, count)` rollup, flushed once a minute (not
  per request) with a volume-JSON fallback and a shutdown flush. Two numbers,
  deliberately distinct on the page: `tool_calls` (recorded INSIDE each
  mcp_server.py tool, so one increment = one answered question) and
  `requests` (raw HTTP, inflated ~2-3x by stateless MCP chatter). Extracted
  `_check_agent_trust` so `compare_agents` counts once, not three times.
  `/api/v1/usage` is excluded from its own counters so the page can't inflate
  what it reports. `/live/` = odometer + 24h zero-filled hourly chart + tool
  breakdown + live call feed (**tool name and timestamp only — never
  arguments, IPs, or anything identifying**); compact live strips on /verify/
  and the homepage. Verified locally end-to-end against a real uvicorn +
  29 real MCP JSON-RPC tool calls: 29 calls → 29 counted, 30 requests
  (29 + `initialize`), api_v1 stayed 0, counts survived SIGTERM→restart.
  LESSON: the odometer's count-up animation must commit its value BEFORE
  animating — `requestAnimationFrame` never fires in a hidden tab, which
  silently froze the headline number while the rest of the page updated.
- Next: bill re-check (was due 2026-07-12, now overdue — Railway metrics
  API, memory baseline after #106); T3.3 capability-surface PAGE (grade
  shipped, page pending); internal-linking SEO pass; badge-adopter audit;
  later T3.5 drift monitoring, Postgres consolidation. Roster-batch WIP
  sits in `git stash` ("roster-batch WIP") + untracked blog_static drafts/
  candidates.json — do NOT commit or deploy those accidentally; deploy only
  from a clean worktree (`git worktree add --detach <path> main`, link with
  `railway link -p 336fa70c-… -e dfc35ffb-… -s web`, then `railway up
  --detach`).
