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
- GSC cleanup SHIPPED + DEPLOYED 2026-07-06 (#114; owner: "execute the plan").
  Coverage export showed 913/1,558 known pages not indexed (87 404s, 328
  redirect pages, 196 crawled/discovered-not-indexed). Fixes: (1) published
  /compare/ pairs now PERSIST across renders while both agents stay listed in
  the same category — state in `data/seo_state.json` (gitignored, lives on the
  volume); rank shuffles no longer 404 indexed URLs. (2) sitemap <lastmod> is
  per-URL content-hashed (now_str-normalized) — only advances on real change;
  sitemap now written at END of main() so late-rendered pages hash correctly.
  (3) category-article datePublished stable (first render), dateModified only
  on pairing change. (4) app.py middleware: 301 /score-lab/→methodology
  #runtime-calibration, /spec/runtime-trust/v0.1/→v0.2, /org/i-am-bee/ +
  /use-cases/recently-active/→ index; 410 Gone for delisted agents via
  `data/retired.json` (written from legacy_rows each render; hard-deleted
  bee-agent-framework hardcoded) + compare URLs naming them — fires BEFORE the
  static mount so volume orphans can't shadow (this closed the "prod-volume
  orphan check" item). (5) category articles now link compare pairs in
  canonical alphabetical order. Tests: `tests/test_seo_cleanup.py` (3 renders,
  sentinel dates). Verified live: all 301/410s, healthz, 486-URL sitemap;
  this deploy also took #112/#113 live. Note: seo_state seeds all-today on
  first render — lastmod differentiation starts the next day. Follow-ups: 15
  hand-written feed items still stamp now_iso; GSC URL-level exports (owner,
  in Search Console UI) + "Validate fix" clicks on the 404/redirect buckets;
  internal-linking pass next.
- State verified live 2026-07-07: everything through #114 IS deployed
  (coverage grade + content-truth + GSC cleanup confirmed via live API);
  credential signing works end-to-end (`trust_credential.signature` verifies
  against the `.well-known` Ed25519 key); GitHub About text already updated
  to "300+ … runtime-trust calibrated".
- Next: **`docs/master-plan-2026-07-07.md` is the active plan** (supersedes
  product-plan-2026-h2 as forward plan; full verified state audit + ecosystem
  forecast + phased feature plan; per-task status lives in its checkboxes).
- **Phase 0 DEPLOYED 2026-07-07 ~20:35 UTC** (owner-instructed `railway up`
  from clean worktree @325cdbffd, then `railway restart` → pending-only
  scored all 9 provisional agents in one poll). Verified live: 324 agents /
  0 pending (strands-agents 82.7, oh-my-pi 73.9, mistral-vibe 73.2, goose
  69.1, open-interpreter 47.9, opencode 46.5, mini-swe-agent 43.4, cowagent
  24.5, solace-agent-mesh 68.9); methodology `#verify-yourself` live; feed
  dates stable; `board_invariant_violations: []` in live build_report;
  moved-agent pages 200; new-agent credential verifies via
  `scripts/verify_credential.py`. New agents' OSSF sub-scores fill in after
  the next daily scorecard scan (grade = score band since v4.0, so no
  provisional-D issue).
- **Phase 0 executed 2026-07-07** (#116–#120, merged, deployed above):
  offsite history backup live in private repo `hvtracker-history-backup`
  (daily GH Actions, 46 prod snapshots seeded, run verified green — external
  to this repo, no deploy needed); board-integrity invariants
  (`check_board_invariants`, loud in build_report.json,
  `HVT_STRICT_INVARIANTS=1` makes fatal); roster refresh (5 adds + 4 repo
  moves — catalog 347, board 324; all 9 render provisional until prod's next
  signals refresh scores them); hand-written feed items carry real publish
  dates; methodology `#verify-yourself` section + standalone
  `scripts/verify_credential.py` (plan 1.5, verified against live prod).
  Phase 0 CLOSED 2026-07-07 evening (owner decisions): Postgres
  consolidation verified ALREADY DONE (2nd instance deleted 06-21; 3
  services remain; accounts-DB safety dump local at ~/hvtracker-db-backups/);
  bill re-check early — web avg 0.267 GB flat post-fix, total memory
  run-rate ≈$3.4/mo, no ratchet; 3 manual-review candidates (LobsterAI,
  Agent Orchestrator, Sandcastle) REJECTED + denylisted in
  discover_agents.py REVIEWED_REJECTED; public /output/history/ paths stay
  as-is (owner). Render pipeline also already archives snapshots to Railway
  bucket hvtracker-archive (storage.py) — triple redundancy with the GH
  backup. Next code work: Phase 1 — T3.3 capability page (1.1), API docs +
  usage measurement (1.2), MCP server productization (1.3), CI trust gate
  (1.4), dataset exports (1.6).
- **Phase 1 first batch DEPLOYED 2026-07-08 ~00:45 UTC** (owner-instructed;
  #124–#126 via clean-worktree `railway up` @dd31a22bd). (1.1) `/capabilities/`
  capability matrix — all agents × MCP/providers/tool-surface/drift,
  provider chips link to /ecosystem/ pages, in nav + llms.txt + sitemap;
  agent-page runtime panels link providers + the matrix. (1.6) quarterly
  dataset export `/data/exports/hvtrust-<Y>-Q<n>.json.gz`+`.csv` (CC BY 4.0,
  embedded citation; rolls within quarter, freezes at quarter end), on
  llms.txt + /data-api/ (quarter substituted at request time). Verified
  live: healthz ok/324/in-sync, capabilities 200, haystack→/ecosystem/
  anthropic/ link, export downloads (17.7KB gz), docs + sitemap updated.
  With 1.5 (#120), Phase 1 remaining: 1.2 API docs+usage measurement,
  1.3 MCP productization, 1.4 CI trust gate.
- **Phase 1 COMPLETE (code) 2026-07-08** (#128 #129 + external repo; merged,
  NOT yet deployed unless noted): (1.2) /data-api/ documents the full
  machine surface + stability promise (v1 fields add-only); `machine_usage`
  counters (api_v1/mcp/data_json/exports) in /healthz. (1.3) MCP server
  v0.2.0 — new `compare_agents` tool; check_agent_trust returns
  coverage_grade + capabilities block + credential_url; registry-submission
  kit in docs/mcp-registry-listing.md (registry auth = OWNER ACTION).
  (1.4) public repo `YugantM/hvtrust-gate` (v1): CI trust-gate action,
  self-test green on GitHub runners; badges page links it (Marketplace
  publish = OWNER ACTION). Next: deploy #128/#129 batch when instructed;
  then Phase 2 (internal linking, compare v2, badge audit + trend badge,
  watchlist alerts, corrections page).
