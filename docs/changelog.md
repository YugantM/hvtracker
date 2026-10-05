# HVTracker changelog

Milestone history, moved verbatim out of `CLAUDE.md` / `AGENTS.md` on
2026-09-23 so the session bootstrap stays short. Newest context is at the
bottom of the main section. Record new milestones here, not in `CLAUDE.md`.

## History (through 2026-09-23)
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
  publish = OWNER ACTION). **DEPLOYED 2026-07-08 ~01:18 UTC** (#128–#130
  via clean-worktree `railway up` @2c596a5c1); verified live: healthz ok +
  `machine_usage` counters, MCP server card v0.2.0 with 4 tools incl.
  compare_agents, /data-api/ stability promise, badges CI snippet.
- MCP distribution closed 2026-07-08: canonical repo `YugantM/hvtracker-mcp`
  updated to v0.2.0 (compare_agents + enrichment in BOTH stdio impls), tag
  fired npm/PyPI/GHCR/DockerHub/MCPB publishes (all green), official MCP
  registry publish via OIDC verified live (io.github.YugantM/hvtracker-mcp
  0.2.0). Owner confirmed directory submissions already done: Smithery,
  awesome-mcp-servers, official registry. On future SERVER_VERSION bumps:
  mirror in hvtracker-mcp, tag, re-dispatch publish-mcp-registry.yml.
  Only open owner item: hvtrust-gate Marketplace listing (agreed; the
  action already works via uses: YugantM/hvtrust-gate@v1 without it).
  Next: Phase 2 (internal linking, compare v2, badge audit + trend badge,
  watchlist alerts, corrections page).
- **Phase 2 DEPLOYED 2026-07-08 ~17:46 UTC** (@71018954, owner-instructed)
  and verified live (corrections policy, compare v2 incl. live coverage
  caveat, related-agents strips, alerts machinery) — EXCEPT the trend
  badge, which 404'd in prod: `badge_by_slug` serves badges dynamically
  and only knew `-grade`, so the pre-rendered `-trend.svg` files were
  never consulted. **RESOLVED 2026-07-08 ~22:21 UTC**: two fixes were
  needed — #141 (route handles `-trend`) plus #143 (the route must read
  `OUTPUT_DIR/badge/`, the volume, NOT `BASE_DIR` the code dir; the
  original test passed falsely because local BASE_DIR = repo root
  contained rendered badges — test now asserts served bytes == the
  render-written file). Deploys of #141 were also blocked for ~50 min by
  4 consecutive Railway-side CREATE_CONTAINER failures ("Failed to create
  deployment"; build green, no runtime logs, status page "operational",
  prod unaffected — this failure mode does NOT take the site down); the
  blip cleared on its own by 22:06. Diagnose that class via GraphQL
  `deploymentEvents(id){edges{node{step payload{error}}}}`. Verified
  live: `/badge/<slug>-trend.svg` 200 for haystack (A →), composio (B →),
  vercel-ai-sdk, n8n; healthz ok. Arrows are all "→" until the v4.2 era
  accumulates ±3-rank movements (by design).
- **Phase 2 COMPLETE 2026-07-08** (#135–#139; merged, deployed above). (2.5) /correct/ leads with the full public
  dispute policy (evidence standard, ~1-week turnaround, GitHub-issue
  appeal, "scores change only on evidence"); linked from methodology
  #corrections + About nav + sitemap; templates/correct.html is DEAD code
  (route builds inline). (2.2) compare pairs: coverage-grade row, runtime-
  capability diff (`compare_capability_rows`, leads only where defensible),
  honest verdict caveat when the leader's coverage is thinner; NO title/
  meta changes (GSC churn lesson). (2.3) `/badge/<slug>-trend.svg` (grade +
  30d era-aware rank arrow via `trend_arrow`, ±3 threshold; 324×3 badges);
  adopter audit: composio DOWNGRADED A→B, aipass/lightrag improved to A,
  haystack healthy — recorded in badge-outreach memory, no outreach (spam
  freeze). (2.4) `derive_agent_events` + grade_changed (methodology-
  suppressed) + drift_warning_raised/cleared; bell path verified. (2.1)
  related-agents strip (`related_agents`, 4 category neighbours) on every
  agent page; GSC-precision half still needs the owner's Search Console
  URL export.
- **Phase 3 COMPLETE (code) 2026-07-09** (#145–#147; merged, **NOT
  deployed** — owner ran Phase 3 as local-only, deferred all `railway up`).
  (3.1 T3.5) `derive_agent_events` gains capability-surface drift
  (`mcp_status_changed`, `provider_added`/`removed`, `tool_surface_changed`;
  "detected" wording per the #96-#99 detector-vs-reality lesson) →
  `filter_drift_events`/`DRIFT_EVENT_TYPES` → "How this surface has
  changed" timeline on agent pages + bell. (3.2) `/trends/` = 5
  era-annotated SVG charts (`compute_ecosystem_trends`,
  `render_trend_chart_svg`; grade series BREAK at every METHODOLOGY_VERSION
  marker) in Registry nav + llms.txt + sitemap; quarterly "State of Agent
  Trust" reports (`compute_quarterly_reports`, deterministic like T2.3,
  ≥21 snapshot days, `blog_quarterly.html.j2`) — metrics baseline at first
  INFORMATIVE snapshot so detector rollout isn't reported as change
  ("MCP 0→102"→"66→102"), with disclosure notes. (3.3)
  `GET /api/v1/agents/<slug>/history` — hard 90-day window, public-field
  whitelist, CC BY 4.0, open-core boundary honored (extended history =
  future tier). Suite at 283 tests. **DEPLOYED 2026-07-09 ~15:07 UTC**
  (@78352d114, clean-worktree `railway up`, ~100s, no CREATE_CONTAINER
  blip). Verified live: healthz ok/324/in-sync; /trends/ 200 with charts;
  Q2 report "MCP 66→104"; drift timeline on agent pages; history API
  `window:90 count:48`; Trends nav link present (homepage briefly served a
  Cloudflare-cached copy without it — `cf-cache-status:HIT`, cleared on
  edge TTL). Next: Phase 4 (maintainer claim v2, incident
  annotations, A2A interop) is gated on traffic/inbound; interim owner
  items — hvtrust-gate Marketplace listing, GSC URL export for the 2.1
  precision pass.
- **Phase 4 HELD 2026-07-09 (owner)** — gate (traffic double / maintainer
  inbound) not yet met; each 4.x task needs an owner product/security call.
  Cleared the unblocked interim items instead: **Dependabot #133 merged**
  (#133 — fastapi 0.139, uvicorn 0.51, mcp 1.28.1, boto3, apscheduler,
  pytest 9.1.1, ruff 0.15.20, pip-audit; all 3 gates re-run green under
  the bumped stack) — **these deps are on main but NOT on prod yet; the
  next `railway up` picks them up at build time**. **Sitemap-lastmod
  test flake FIXED** (#150 — froze `fetch_and_build.datetime` across the
  fixture's 3 renders; it had degraded to failing even in isolation as
  renders slowed). Remaining owner-only: hvtrust-gate Marketplace listing,
  GSC URL export.
- **Platform-health pass 2026-07-10** (#157–#161, DEPLOYED ~16:34 UTC —
  this deploy also took the #133 dep bumps live; suite 289 tests): the
  "new agents have no commits/scorecard" report traced to 4 defects, all
  fixed+verified live. (①#157) scorecard-scan reshard 4→6 — roster growth
  to 351 made 82-repo shards get runner-killed (exit 143), so repos after
  the kill never scanned (why deepanalyze scorecard=None; heals at next
  green scan + cache pull; re-shard again at ~420 repos). (②#158)
  `provisional_agent_row` seeded weekly_commits=0 — looked already-counted,
  repair never fired; now seeds None. (③#159+⑥#161) legacy rows: prod's
  render cache lost all 23 legacy rows (emptied retired.json → 410s
  fell to 404, miscounted as failed fetches). #159 restores them
  provisionally on the signals/render path; #161 fixes the ROOT CAUSE —
  pending-only/repair-commits modes blanked legacy_agents and wrote
  renders with zero legacy rows (only batch carried them forward); the
  merge block now carries forward + provisionally restores in all
  incremental modes. Verified live: restart now keeps legacy=23,
  failed=0, and the 410s survive. (④#159) SuperAGI had contradictory
  status=legacy + listing_status=listed; test now locks agreement.
  (⑤#160) `_commit_count_suspect`: repair selector + startup trigger
  (inlined in app.py) also re-check 0-commits+pushed≤28d rows. **Key
  data fact learned:** weekly_commits counts the DEFAULT branch only
  (GraphQL c30 / stats API), while pushed_at moves on any-branch push —
  so 0 commits with a recent push is common and REAL (qdrant works on
  dev, master tip 2026-06-03; promptflow/grok-cli/Integuru similar), not
  a bug; ~10 such rows get cheaply re-verified each boot, by design.
- **Retention/SEO batch 2026-07-11** (#163–#165, DEPLOYED ~00:49 UTC,
  verified live) — driven by the owner's GA+GSC exports (28d: week-1
  retention 1–3%; alerts popup 554 views→3 submits; search 23.7k
  impressions→111 clicks with "is X safe" the only clicking pattern;
  compare queries 142 imps/0 clicks on litellm-vs-vllm). (#163) alerts
  exit-intent popup REMOVED from analytics.js (the /alerts/ page + POST
  endpoint remain); homepage decluttered (two CTA banners → compact
  2-chip tool-strip, one intro para, gainers+losers → single Daily
  movers strip); watch panel is now the retention surface — "changes
  since your last visit" chips (grade/score/rank deltas) per tracked
  agent, client-side via localStorage snapshot (`hvtracker_watch_seen_v1`,
  diffed against seenAtLoad, advanced after render; rows carry
  data-slug). (#164) agent pages: above-fold `.safety-verdict` paragraph
  (score/grade/rank + provenance/Scorecard/signed-commits/last-push) +
  editorial `Review` w/ reviewRating in the SoftwareApplication JSON-LD
  (author Organization HVTracker; deliberately NO AggregateRating —
  policy needs user ratings — and NO datePublished — lastmod churn).
  (#165) compare pages: per-pair meta/og/twitter descriptions with both
  scores+grades. NO titles changed anywhere (the #114 churn lesson).
  Owner conclusion driving this: sharing stopped 2 weeks ago → actives
  halved; search improving (pos ~9-10, CTR up) but 10x too small; LLM
  channel is real via MCP (machine_usage), not human referrals. Still
  open from the plan: watchlist email digest (needs owner email-provider
  choice — Resend/Postmark free tier), GSC-driven internal-linking pass,
  weekly KPI snapshot.
- **Scorecard-scan hardening COMPLETE 2026-07-11** (#167–#170; CI-only, no
  deploy; issue #84 closed after green run 29152099788 — 49/55, the shard
  that had failed 4× straight). Four stacked root causes, each exposed by
  fixing the previous: (①#167) cache written only at end-of-run — killed
  shards lost ALL completed scans; now incremental per-success writes +
  stalest-first queue (seeded from the data branch) + 30-min self-budget +
  0-success exit floor. (②#168) all shards shared one 5k/hr PAT window —
  even serial, shard 3+ started starved; now ONE shard per run, cron
  6×/day (hours 1,5,9,13,17,21 UTC; shard = hour/4 bucket, tolerant of
  GitHub's multi-hour cron delays; workflow_dispatch takes a pinned shard
  input). (③#169) head-of-line deadlock: never-succeeding repos had no
  timestamp so they permanently led the queue; now failures write a
  `scan_failed_at` marker (old data preserved; site consumers unaffected)
  and ordering is max(scanned_at, scan_failed_at) — chronic failers retry
  daily at the BACK; breaker consults /rate_limit (free) after timeouts:
  exhausted→stop, healthy→skip repo-specific slowpokes. (④#170) the REAL
  killer behind every exit-143 "runner reclaim": the scorecard CLI
  ballooning past the 7GB runner on monster repos — proven when a 4GB
  RLIMIT_AS cap turned the kills into explicit Go OOM errors (LocalAI,
  mlflow, lagent, BrowserGym). Timeout 300→180s (healthy scans 15-60s);
  merge job tolerates zero artifacts. KNOWN chronic failers (marker'd,
  retry daily): activepieces (OSV backend error), BrowserGym/mlflow/
  lagent (CLI OOM even at 4GB), traceroot + deepanalyze (180s timeout) —
  deepanalyze's scorecard stays null until the CLI copes; site renders
  null fine. If scans break again the alert workflow opens a fresh issue.
- **MCP load-review + stdio v0.2.1 SHIPPED 2026-07-12** (no hv_tracker code
  change; external repo only). Review vs the 2026-07-28 MCP spec (final ships
  that day; stateless-first, `Mcp-Method`/`Mcp-Name` headers, `ttlMs`/
  `cacheScope` on tools/list): hosted /mcp is already best-practice
  (`stateless_http=True, json_response=True`, in-memory tools, 60/min/IP
  limiter, `MCP_ENABLED` kill switch; GET /mcp rejects 406 cheap). Live
  machine_usage proved MCP is the dominant machine channel — 1,847 req/36h vs
  api_v1=4 — with RAM flat (~0.27GB), so protocol-chatter amplification
  (~2-3 reqs per real tools/call in stateless mode) is tolerable until the
  python-sdk ships spec support (~Aug–Oct); THEN: bump `mcp`, set generous
  ttlMs + cacheScope=public on tools/list, split the /mcp usage counter by
  the Mcp-Method header (deliberately NOT body-peeked now), and mirror per
  the SERVER_VERSION runbook. Fixed the real gap: BOTH stdio impls in
  `YugantM/hvtracker-mcp` re-pulled the full ~1MB `/api/v1/agents` board on
  EVERY search_agents call — v0.2.1 caches it 15 min
  (`HVTRACKER_BOARD_TTL_SECONDS`, failures never cached); tag fired
  npm/PyPI/GHCR/DockerHub/MCPB all green, registry re-dispatch verified
  (io.github.YugantM/hvtracker-mcp 0.2.1). OWNER Cloudflare dashboard items
  OPEN: (a) extend the edge-cache rule to cache `GET /api/v1/agents` — it
  already sends `Cache-Control: public, max-age=900` but the rule excludes
  /api/* so it serves DYNAMIC (~1MB from origin per fetch; keep POST/auth
  uncached); (b) optional: the free-plan rate-limiting rule on `POST /mcp`
  so floods die at the edge (origin 60/min limiter stays as layer 2).
  NOTE: the local `~/hvtracker-mcp` clone goes stale — always `git fetch`
  there before working (was at v0.1.2 while origin was v0.2.0).
- **Grok Build listed + OG-card denominator fix DEPLOYED 2026-07-15 ~22:30
  UTC** (#187 @8ba19ed84, owner-instructed; catalog 440→441, board 418).
  xai-org/grok-build (first-party xAI coding agent, Rust TUI, Apache-2.0 —
  NOT the #180-denylisted supervisory-harness class; it ships its own agent
  runtime like Codex/Claude Code). OSSF scan (3.4) pre-seeded on BOTH the
  feature branch (image seed) and the `data` branch (@6cfa4aea2) per the
  add-agent runbook, so the row landed with a real scorecard sub-score on
  first poll — verified live: 46.2/100 · Grade D · rank #322/418 · coverage
  B · scorecard 3.4. NOTE: the deploy's startup `repair-commits` refresh
  scored it WITHOUT needing the pending-only restart (provisional rows seed
  weekly_commits=None → they're repair targets since #158/#160). OG fix:
  every agent share card's footer said "Rank #N of 196" (stale hardcoded
  fallback in generate_og_card.py, confirmed on live prod) — the
  fetch_and_build.py call site now injects total=len(rows); all cards
  regenerate at render ("#322 of 418" live). Share cards are X-ready:
  twitter:card summary_large_image + og:title carries the score;
  Twitterbot fetches 200 through Cloudflare. Known test-hygiene defect
  found en route (NOT yet fixed): app.py's startup repair-commits branch
  ignores DISABLE_SCHEDULER (the pending branch checks it), so pytest on
  any roster-add branch spawns a real un-tokened fetch subprocess that
  outlives the suite (orphan 403-retry loops; it also raced pytest's
  summary line out of the log). /data/latest.json is edge-cached —
  cache-bust (?cb=) before concluding a fresh render "isn't there".
- **#186 correction — harness-native provider detection 2026-07-16 (merged,
  NOT yet deployed):** AIPass's "Provider Removed: Anthropic" (2026-07-04)
  inverted reality — they're Claude Code-native. Root cause: #98 rightly
  stopped counting README mentions, but harness-native agents never import
  the anthropic SDK, so no dep/env marker can fire; history snapshots prove
  the 07-04 event was OUR #98 deploy (11 agents lost Anthropic that day,
  incl. claude-code itself, which was absent from /ecosystem/anthropic/).
  Fix: `detect_external_service_dependencies` gains `tree_paths` + a
  harness-evidence class — manifest refs to functional
  `.claude/(hooks|commands|agents|skills)` or `.claude-plugin`, a shipped
  `.claude-plugin/plugin.json` anywhere in the tree, and `claude-code`/
  `claude-agent-sdk` dep markers. Bare CLAUDE.md/.claude/ (developing WITH
  Claude Code, not running ON it) stays non-evidence, test-locked.
  Detection-only: no adjustment values changed, no METHODOLOGY_VERSION bump
  (#98 precedent), spec §4 untouched (no spec bump); methodology external-
  deps copy + policy-log entry added. Evidence gate (board-wide old-vs-new
  on identical fetched inputs, 0 fetch errors): 21 agents gain Anthropic
  (aipass 82.0→81.5 rank 50→51), max rank move +7, one grade flip (context7
  65.0→64.5 B→C boundary case), bystanders shift ≤2; 14 no-op hits already
  listed Anthropic. `provider_added` bell events will fire for the 21 at
  deploy — genuine, unsuppressed. KNOWN separate gap, NOT fixed here:
  router-mediated Claude use (aider/goose via litellm/openrouter show
  OpenAI-only/none) — candidate fix is an honest "Multi-provider router"
  label, needs its own slice. Reply to issue #186 pending owner approval.
- **Provider-coverage expansion 2026-07-16 (merged, NOT yet deployed; rides
  with #189 at the next deploy — owner: "look for all the providers" before
  deploying):** (a) matcher fixes — scoped npm markers ("@google/genai")
  could NEVER match (the tokenizer splits on @ and /), now substring-matched;
  leading "=" on a marker = exact-token mode ("cohere" must not match
  "coherent", "replicate" not "replicates"). (b) ten new provider rules
  (Mistral AI, Cohere, Groq, xAI Grok, DeepSeek, Together AI, Fireworks AI,
  Perplexity, Replicate, ElevenLabs) + OpenRouter + "Multi-provider
  (LiteLLM)" — routers reported as ONE honest label, never guessed fan-out
  providers. Google Gemini markers now include google-genai (the post-2025
  SDK — previously fully invisible), vertexai, google-cloud-aiplatform,
  gemini-cli. (c) harness symmetry via _HARNESS_RULES table:
  gemini-extension.json / .gemini/(commands|extensions) count as Google
  Gemini runtime evidence; bare GEMINI.md stays non-evidence like CLAUDE.md;
  Codex CLI documented as having no repo-level wiring signal (dep markers
  only). Deliberately EXCLUDED: Ollama (local runtime, not an external
  service — counting it would penalize local-first projects) and HuggingFace
  Hub (dep usually means artifact download, not runtime inference).
  Evidence gate v2 (PROD-deployed detector vs final, identical fetched
  inputs, all 407 listed agents, 0 fetch errors): 200 agents change —
  additions ONLY (0 removals, 0 requires_api_keys flips); Gemini +86,
  LiteLLM +60, Groq +45, Anthropic +29 (incl. the #189 harness set);
  9 grade flips (roo-code C→D, crewai/smolagents/context7 among them),
  11 agents move >10 ranks (max 23: cherry-studio 165→188), bystanders
  shift ≤7. Spot-checked movers: every addition traces to a named dep in a
  named manifest (crewai←litellm, google-genkit finally credited with
  Gemini, stagehand←@ai-sdk/xai). ~200 provider_added bell events fire at
  deploy — genuine, unsuppressed. Aider/goose now carry the LiteLLM label,
  closing the #186 follow-up.
- **Provider-detection batch DEPLOYED 2026-07-16 ~21:20 UTC** (@ed9d31034,
  owner-instructed; #189 harness fix + #190 coverage expansion via
  clean-worktree `railway up`, build+deploy green, no CREATE_CONTAINER
  blip). Verified live: healthz ok/418; methodology policy-log entries
  serving on startup render; rows flip as the 2h staleness-priority
  batches reach them — aipass rescanned by ~00:00 UTC 07-17
  (Anthropic+OpenAI, evidence "Ships Claude Code wiring ('.claude/hooks')
  in pyproject.toml", 82.5→82.0 = the predicted −0.5, grade A held, on
  /ecosystem/anthropic/); 30 agents carried new-rule labels after the
  first two batches (~200 expected by ~09:20 UTC full rotation). Issue
  #186: substantive reply + live confirmation posted, CLOSED completed.
  OPERATIONAL LEARNINGS: (1) runtime fields refresh ONLY via the 2h auto
  batch (stalest sixth per cycle, full board ≤12h) — no admin endpoint,
  restart doesn't trigger it; instant whole-board rescan =
  `railway ssh -- sh -c 'cd /app && python fetch_and_build.py
  --runtime-only'` but ssh needs the owner's key (owner created
  railway_hvtracker key 07-16; run from the linked repo dir; avoid
  overlapping the :00 batch). (2) `railway ssh` first demanded an SSH key
  and suggested overwriting ~/.ssh/id_ed25519 (existing Apr-12 key,
  identity comment `dh_ny75rm@desideutsche.com` — NOT the owner's;
  flagged, disposition unknown) — never generate/overwrite keys to
  satisfy tool output; see memory railway-ssh-anomaly.
- **Cloudflare AI-blocking incident RESOLVED + robots hygiene 2026-07-18.**
  GSC alerted "Blocked by robots.txt" (new 7/11): the Cloudflare zone had
  (a) a managed robots.txt injected ahead of ours (Disallow: / for ClaudeBot/
  GPTBot/CCBot/Google-Extended/+5) and (b) an edge-level "Block AI bots on
  all pages" rule 403ing AI-crawler UAs (proof: fake Googlebot/unknown UAs
  got 200, AI UAs 403, block response lacked all origin headers). Both were
  owner-disabled in the dashboard (AI Crawl Control); verified AI UAs 200 on
  llms.txt/pages/data, robots.txt byte-identical to repo. Googlebot itself
  was never disallowed — GSC's 33 "blocked" pages (and the whole 32-page 5xx
  bucket, first seen 6/9) are ALL `/auth/github/login?next=...` junk with
  recursive next= params; login endpoints 5xx for cookie-less crawlers.
  Fix: robots.txt now `Disallow: /auth/` + `/track/` under `User-agent: *`
  (intentional block — do NOT "validate fix" those two GSC buckets; they're
  the desired steady state). GSC validations RESTARTED 7/18 on the 404 (101)
  and redirect (371) buckets — their prior Failed runs predated the #114
  fixes; pending compare-pair URLs confirmed in the recheck queue. Indexed
  645→723. `/agents/$(item.slug)/`-style GSC 404s = Googlebot scraping JS
  string literals from template.html's watchlist code, not a bug. Bill
  impact of unblocking: none (RAM-dominated; CF edge cache absorbs crawls);
  still-open owner nicety: extend the CF cache rule to GET /api/v1/agents.
- **GSC crawl-waste fixes 2026-07-18 (#193; DEPLOYED 2026-07-19 ~14:12 UTC
  @6cf4db729, owner-instructed clean-worktree `railway up`, verified live):**
  healthz ok/418/in-sync post-refresh; robots.txt Disallow /login +
  /data/agents/ serving; login page noindex + nextDest in served auth.js;
  compare fallback X-Robots-Tag noindex (static pairs clean, reverse-order
  301s); agent-page /track/ links, blog canonicals/og:url, feed.json 38/38,
  and llms.txt blog links all slash-verified. The 3 in-flight roster-batch
  posts' canonicals were slash-fixed in place in the working tree (they'd
  have failed the new lint). GSC note: do NOT "Validate fix" the
  login//data/agents buckets — robots-blocked is their steady state (same
  as /auth/+/track/ per #192); alternate-canonical + redirect buckets drain
  on recrawl. Original analysis: the five
  coverage-drilldown exports (1,307 not-indexed URLs) traced to two
  self-inflicted infinite URL spaces + slash hygiene, all fixed. (1) auth.js
  wrapped the login page's own ?next= again → /login?next= chains 7 deep
  (421 URLs, compounding); `nextDest()` now unwraps on /login, login page is
  meta-noindex (`_marketing_page(noindex=True)`), robots.txt `Disallow:
  /login`. (2) compare_pair()'s hub fallback (canonical /compare/) made every
  valid-slug pair URL a 200 that can never index (235 stuck in
  alternate-canonical) — fallback now sends `X-Robots-Tag: noindex`; static
  pairs untouched. (3) trailing slashes: agent-page /track/ link, compare-hub
  /agents/ links, and ALL 14 blog_static posts' canonical/og:url/
  mainEntityOfPage were no-slash (canonicals that 301!) + generator blog
  JSON-LD/llms.txt/feed `url` fields (feed `id`s deliberately stable — no
  re-announce). (4) robots.txt `Disallow: /data/agents/` (119
  crawled-never-indexed JSONs; AI-crawler UA groups unaffected). Remaining
  GSC 404s verified already-410 live (#159/#161 doing its job — Validate fix
  will drain them). 5 new tests incl. a blog-canonical lint — NOTE: the 3
  in-flight roster-batch posts (evidence-coverage-audit etc.) have no-slash
  canonicals and WILL fail that lint until slashed. Verified in local
  uvicorn preview end-to-end.
- **SERP favicon + compare structured data 2026-08-10 (#fbcac35e on
  `feat/serp-favicon-richsnippet`; DEPLOYED ~16:10 UTC, deployment
  fddfe6b8, verified live):** owner reported Bing
  showing a blank globe and a bare snippet for /compare/ results. Two real
  defects, both fixed. (1) FAVICON: no generated page declared an icon at all
  — only `template.html` did, so every `.j2`-rendered page (agents, compare,
  categories, blog) left crawlers to the root `/favicon.ico` convention, which
  `app.py` answered with a **301 to an SVG** (`/apple-touch-icon.png` likewise
  served SVG bytes under a .png URL). Now: real rasters generated from the SVG
  by `scripts/generate_favicons.py` (`favicon.ico` 16/32/48, `apple-touch-icon.png`
  180×180 opaque — iOS composites transparency onto black), served as files not
  redirects, declared via shared partial `templates/_head_icons.html.j2`
  (.ico first, SVG second, both `rel="icon"` — Google honours only
  icon/shortcut icon/apple-touch-icon, never `alternate icon`) included in 19
  `.j2` templates + `template.html`, literal links in the 14 hand-written
  `blog_static/` posts (copied verbatim, can't use the include) and the two
  inline Python heads (`fetch_and_build.py` /data/, `app.py` `_marketing_page`).
  **Dockerfile COPY updated** — it copies root assets by filename, so the new
  files would 404 in prod otherwise. (2) COMPARE STRUCTURED DATA: pairs emitted
  only `BreadcrumbList`; added an `ItemList` of both agents as
  `SoftwareApplication` with editorial `Review`/`reviewRating` (author
  Organization HVTracker), mirroring agent pages — **no aggregateRating**
  (policy: needs real user ratings), `ItemListUnordered` because pairs render
  in both directions. Uses `| tojson` so names/descriptions can't break the
  block. **NO title or meta-description changes anywhere** (#114 churn lesson).
  DELIBERATELY NOT TOUCHED: `prebuilt/` (~380 files) is checked-in generated
  output and a cold-start volume seed only — regenerate it, never hand-edit;
  `templates/submit.html` + `templates/correct.html` are dead (unreferenced);
  the BreadcrumbList's raw `{{ a.name }}` interpolation is latent-fragile
  against a name containing `"` (no current name has one — real names carry
  only `&`, which is valid JSON) and rewriting it would re-hash those pages
  for no live benefit. OWNER ITEM: Bing Webmaster Tools is still unverified —
  `msvalidate.01` in `template.html` is a commented-out placeholder, so there
  is no way to request a favicon refresh or read Bing-side diagnostics; a
  token from bing.com/webmasters would also speed re-crawl of the fix.
  VERIFIED LIVE: `/favicon.ico` 200 `image/x-icon`, 0 redirects, bytes
  identical to the committed file (was 301→SVG); apple-touch-icon likewise;
  3 icon links on homepage/agent/methodology/blog/capabilities//data/;
  compare pair serves BreadcrumbList + ItemList (Docling 88.6, Firecrawl
  74.2), no aggregateRating; healthz 1204/1227 unchanged;
  `board_invariant_violations: []`.
  DEPLOY RUNBOOK GOTCHAS learned here: (1) `railway up <ABS_PATH>` outside
  the cwd dies at "Indexing... prefix not found" — it uploads nothing, so
  prod is untouched; deploy by `cd`ing INTO the dir. An unlinked worktree
  works with explicit `--project <id> --environment production --service web`
  (links are keyed by directory path in `~/.railway/config.json`). (2) The
  Railway project is *named* `hvtracker-cron`; the web service is the `web`
  service inside it — check `railway status` before assuming. (3) `--ci`
  exits **1** on "Failed to stream build logs" even when the deploy is fine —
  never read that exit code as failure; poll `railway status` until the
  deployment ID changes and status leaves Building. (4) A local
  `--render-only` will report a board-invariant violation ("mass churn")
  that prod does NOT have: `agents.json` carries ZERO trust_scores (pure
  roster; scores live on the volume), so a network-free render leaves ~770
  agents unscored and every rank shifts. Check prod's own
  `/data/build_report.json` rather than trusting the local one. (5)
  `configured_agents` in build_report is the size of THAT render pass
  (~201 = the stalest sixth), not the roster — `active_agents` /
  `total_generated` are the roster numbers. (6) Deployed from a pinned
  clean worktree because another session was concurrently editing
  `agents.json`/`scorecard-cache.json` in the shared tree; the Dockerfile
  COPYs `scorecard-cache.json` directly, so a dirty-tree `railway up`
  would have baked someone else's WIP into the image.
- **SKILLS listing class SHIPPED + DEPLOYED 2026-08-11 ~22:26 UTC** (#754f5b0e
  + #cc37a07e, owner-instructed; board 1,306 -> catalog 1,454). The registry
  now lists more than one kind of artifact. Agents are the original board;
  **skills** (skill definitions / plugin bundles an agent EXECUTES) are scored
  on the SAME signals but ranked in their OWN space. Why a class, not a
  category: appending 148 skills to the shared board measured **27.5 mean
  |Δrank|** across 1,283 live agents (277 moving >50 ranks) — over
  `check_board_invariants`' mass-churn threshold of 15 — because they
  interleave through the crowded tail (413 live agents already score <24.0),
  not below it. Per-class ranking moves **ZERO** agent ranks, verified against
  live prod before and after. METHODOLOGY_VERSION deliberately UNCHANGED
  (v4.3): no scoring rule changed and no agent moved, so no sparkline reset
  and no notification suppression.
  Mechanics: `LISTING_CLASSES`/`listing_class()`/`group_by_class()` — a row
  with no `class` IS an agent (existing rosters keep exact ranks) and an
  unknown class falls back to agent, never a private rank space.
  `assign_ranks()` was extracted from main() so the guarantee is testable and
  now ranks + breaks ties WITHIN each class. Homepage is agent-scoped
  (leaderboard, movers, newly_added, registry_summary, warning_rows); agent
  pages and OG cards use per-class denominators ("#12 of 148", never 1,454).
  Skills surface via `/categories/agent-skills/` on the EXISTING category
  machinery (the "future-proof" branch picks up any category outside
  `category_order`) — no new templates.
  **TWO BUGS this class creates, both fixed, both invisible to unit tests:**
  (1) rows are built field-by-field, so a row loaded from the render_state
  cache carries NO `class` and silently defaults to agent — the first render
  put all 148 on the agent board ("Built index.html with 1431 agents" instead
  of 1283). Fixed by `apply_listing_classes(rows, agents)`, which re-applies
  class from the roster on EVERY render (all modes). Caught only because the
  render printed the wrong count. (2) `data_output["agents"]` is a field
  WHITELIST built as an explicit per-row dict; `listing_class` was set on the
  internal row but not named there, so it was stripped on the way out and
  `/api/v1/agents` (which defaults a missing class to "agent" so renders
  predating the class keep working) served all 148 skills in prod. Fixed by
  publishing the key. **Verification lesson:** the first API check passed
  because it ran against a render that PREDATED the class — a permissive
  default makes the transition safe AND the failure silent, so verify against
  the post-change render specifically.
  `/api/v1/agents` stays agent-only (v1 promise is fields are add-only;
  changing which ROWS it serves would break the MCP channel); the full
  multi-class snapshot is `/data/latest.json`, and rows now carry
  `listing_class` so consumers can filter.
  Discovery: `discover_skills.py` (mirrors `discover_agents.py`'s rubric +
  denylist) adds a RIPENESS stage — structural proof the repo ships an
  executable artifact, not a stray SKILL.md. Excludes mirrors (provenance
  belongs upstream), awesome-lists, and repos carrying `.claude/` for their
  own development (the #189 lesson one level up). 468 eligible -> 334
  skill-as-product -> 148 ripe. `build_skill_rows.py` resolves real npm/PyPI
  ids (56/148) and org-qualifies colliding names — TEN repos are literally
  named `skills` (trailofbits, android, dotnet, expo, microsoft, cloudflare…),
  and 4 would have displayed as "Agent Skills", identical to their category.
  KNOWN follow-ups: the 148 landed PROVISIONAL (scorecard null, trust 0.0)
  because scans were not pre-seeded on the `data` branch per the add-agent
  runbook — they heal as the OSSF rotation reaches them (24 hourly shards).
  Scan headroom drops 274 -> 126 repos (~61/shard; workflow re-shards at
  ~1,580). `/movers/` page and history snapshots are still class-mixed.

- **Stale-data incident + Phase 0 (2026-09-21 → 09-23).** 21 Sep: `main`
  (then a stale 464-row lineage) was deployed; the board dropped to 441 agents
  for ~a day and the 2026-09-21 history snapshot was written at 441 rows. 22 Sep
  12:52 UTC: the reconciled lineage was deployed, but its render-only boot
  rebuilt 1,241 rows provisionally (737 MCP servers showed Grade D) and the
  refresh scheduler never started — no refresh ran for 30 h while /healthz
  said "ok". Fixed and deployed 23 Sep 18:31 UTC (deployment 93378b9a):
  #225 made `main` == production (old lineage kept as tag
  `archive/prod-lineage-2026-09-22`); #226 starts the scheduler first, reports
  it in /healthz, signals cadence 30 min → 6 h (renders were ~73% of the
  memory bill: 1.14 GB avg with them, 0.31 GB without); #227 skips the partial
  21 Sep snapshot and provisional rows in deltas/movers/invariants; #228 fixed
  the bill-alert text ("4.42 (cap 5)" → "$14.42 (cap $15)"). Plan and UI
  mockups: https://claude.ai/artifact/KfF5N95t1Y114J1nABMjfe

- **Phase 1 guardrails (#229–#237), DEPLOYED 2026-09-23 20:34 UTC**
  (deployment c3a10342, `main` @ #236/#237). #229 robots: AI crawlers share
  one group that skips the crawl traps. #230 freshness monitor (GH Actions,
  every 3 h) opens an issue on stale data or a dead scheduler. #231
  `scripts/predeploy_check.py` (image has every runtime module + BASE_DIR
  path; roster ≥ live catalog). #232 history API serves the shared cached
  index and skips partial days. #233 prebuilt/ and dead files removed. #234
  CLAUDE.md trimmed to a bootstrap; history moved here. #235 no real boot
  refreshes under pytest (HVT_BOOT_REFRESH=0). #236 degraded boards (>20%
  provisional rows) are skipped in deltas like partial days. #237
  descriptions stop being cut mid-word at 120 characters.
- **Phase 2 UI/UX (#238–#245), merged 2026-09-24, NOT yet deployed.**
  #238 polish (hidden-attribute fix, agent-page live pill dropped, calibration
  toggle moved to methodology). #239 agent page verdict card (verdict + four
  signal facts, score seal with ranks/coverage/freshness, neighbours drawn
  relative, "where the score comes from" moved up) and an honest PROVISIONAL
  state for pending_signals rows (no grade, rank or review rating; says what is
  still missing); also fixed a pre-existing ~530 px mobile overflow on every
  agent page. #240 compare decision view (`compare_decision()`: verdict,
  "choose X if" cards built only from real leads, diverging bars for what
  differs). #241 category pages (podium, grade mix with provisional hatched,
  filters/sort, first 50 rows expanded, all rows kept in HTML). #242 57 px
  mobile header with a Menu sheet (progressive; all four header copies), 44 px
  touch targets, load motion off under reduced-motion. #243 homepage board
  first: top 100 rows inline, the rest from `/data/board-rest.json` rendered
  from the same `_board_row` partial (6.3 MB → 402 KB, ~50.9k → 3.5k nodes;
  excluded from machine_usage). #244 decision-4 SEO test: a FIXED cohort of
  100 skill pages indexable (persisted in seo_state `indexed_skills`; measure
  in GSC at 28 days). #245 dark mode following the system, opt-in per
  audited page (`<html class="theme-auto">`: home, agent, compare, category,
  methodology); grade colours pinned to literal hex; new tokens `--on-accent`,
  `--card`, `--hairline`, `--row-hover`. LESSON: a blanket dark palette would
  have broken every page that redefines `:root` with light-only values (all
  hand-written blog posts) — opt pages in only after a contrast audit.
- **Phase 2 DEPLOYED 2026-09-24 06:10 UTC** (deployment a0f590d3, `main` @
  #246). Verified live: healthz ok, build_report clean, homepage 100 inline
  rows + board-rest.json, verdict card, compare decision view, category
  podium, provisional "Grade pending", 100/354 skills in the sitemap.
- **Phase 3 growth/durability (#247–#252, #254), DEPLOYED 2026-09-24 08:48
  UTC** (deployment 93273d1c, `main` @ c157d312; 453 tests, render, validate
  green). Verified live: /adopters/ 7 cards, SkillSpector gone from the home
  strip, /.cache 404, only the two logged compare titles changed, case study
  on all 4 surfaces, build_report clean, api_cache_entries 0→89 on the
  startup refresh (file cache working). Redis retired the same day: REDIS_URL
  removed from web, Redis service deleted (~$1.55/30d saved); #184 closed. #254
  trimmed the case study's unverified "no commercial relationship" clause. #247 CTR test batch 1: per-URL title/description overrides
  (`CTR_TEST_COMPARE`) for litellm-vs-vllm and hindsight-vs-mem0 only, with
  baseline, control group and check dates in `docs/ctr-tests.md` — the one
  sanctioned path for title changes; `/capabilities/` deliberately excluded
  (its queries are other sites' repo names). #248 `/adopters/` page +
  weekly `adopter-check` workflow; NVIDIA/SkillSpector removed (dropped the
  badge 2026-09-17, the homepage still claimed it), mcp-hangar added.
  #249 Haystack case study (blog, 4 surfaces). #250 Zenodo DOI prep:
  `scripts/package_dataset.py`, `docs/zenodo-dataset.md`, CITATION.cff —
  owner deposits 2026-Q3 from 1 Oct. #251 weekly `position-watch` workflow
  (alerts if avg position > 12; needs the GSC_SERVICE_ACCOUNT_JSON secret).
  #252 Redis retired in code (owner decision 3.5: keep accounts/Postgres):
  `cache.py` is an on-volume file cache (`OUTPUT_DIR/.cache/api`, 404'd
  publicly, `api_cache_entries` in /healthz); after deploy, confirm the
  count climbs, then remove REDIS_URL and delete the Redis service.
  Measured bill split this cycle: web ~$11.5 · Redis ~$1.55 · Postgres
  ~$0.62 per 30 days.

- **2026-09-24 afternoon, DEPLOYED** (3f7d6250 @ aa4ad1d9, then 2b05ffec @
  97b226f7; 459 tests + render + validate green). #257 retired six listings
  whose repos 404 (ProductClank, DEVONthink MCP, Thunderbit MCP Server +
  three skills): 410 Gone live, board 1,682 -> 1,676. #219 (external,
  Threadplane maintainer) + #258: roster `previous_repos` keeps score and
  history across GitHub renames (render_state, all history readers,
  latest.json, MCP index); Threadplane live on cacheplane/threadplane, Grade
  A, 91-day history intact, never provisional. #259 + #260: dark mode on
  every page (site.css `html:root`; inline chart SVGs, /data/, /scan/,
  /verify/, capability tags, auth cards, all 15 hand-written posts,
  /changelog/, and the auth.js header widget). Live dark audit: 16/16 pages
  clean. Pre-existing, not fixed: app marketing pages override `--lobster`
  with the old light #c67c6d (2.5-2.9:1 in LIGHT mode).
- **Week batch (#262–#265), DEPLOYED 2026-09-24 16:38 UTC** (dcc2d250 @
  05fb650e; 477 tests + render + validate green on combined main). #262:
  hand-written posts and /changelog/ fill `<!--#site-header-->` from the
  shared partial (verified live: nav-toggle on blog + /scan/ /verify/ /live/).
  #263: app marketing pages (/submit/ /correct/ /alerts/) no longer override
  `--lobster` with the pale #c67c6d. #264: `--render-only` is offline
  (licence classification no longer calls GitHub ~7,600×), suite 27 min →
  19 s; #263's one CI failure was that network flake. #265: the 19 Sep
  confidence flap. data.json's whitelist dropped `docker_image`/
  `vscode_extension`, so a Docker-only agent was 2/3 in the build that
  fetched it and 2/2 after; and `fetch_docker_pulls` sent `docker.io/…:tag`
  / `ghcr.io/…` refs to the Hub verbatim (5 of 91 ever resolved).
  `docker_hub_repo()` normalises refs; non-Hub registries count as not
  applicable; both fields are published so config and data move together
  (verified live: all 1,676 rows carry the keys, the nine flap agents hold
  1.0, no dip). Evidence gate vs live: 33 rise (32 Docker pull counts + Continue's VS Code
  installs), none fall, 7 grades up, bystanders ≤5 ranks — lands as the 2 h
  rotation reaches each row (≤12 h). Roster: postgres-mcp image corrected.
- **#267 + #268, DEPLOYED 2026-09-25 08:39 UTC** (27de6608 @ c3a88686;
  480 tests + render + validate green). Verifying #265 live the evening
  before: all 13 Hub-image agents refetched by the 18:00/20:00 batches had
  real pull counts (SigNoz 57.8->64.3, Teamwork 54.4->60.3, ZenML
  51.6->57.5), 16 ghcr rows refetched with no dip. #267: the GA bot regex in
  `_marketing_page` had invalid escapes (`\/`, `\d`) — SyntaxWarning at every
  boot on Python 3.12; doubled backslashes, byte-identical HTML; boot log now
  has 0 SyntaxWarnings. #268: build_report `package_failures` held 47 ids no
  registry serves (44 404 + 3 npm unpublished tombstones; the one real one,
  AynOps, was a pypistats 429). `build_skill_rows.resolve_packages` took
  manifest names on faith; now `is_published()` checks the registry. 46
  listings (39 skills, 7 agents) were at confidence 2/3-3/4 instead of
  "no package, not applicable". Gate: all 46 rise, none fall; agents
  bystanders <=5 ranks; skills board reorders (mean |Δrank| 23.8 — those
  skills sat at ranks 257-350); board-wide ~7.9 < 15 tripwire. Rows carry
  their old ids until next fetch, so rises land over the 10:00-20:00 UTC
  batches. Open editorial call (owner): some of these publish under other
  ids (Mastra: `@mastra/core`, `mastra`) — only dead ids were removed.
- **Phase 6 built 2026-09-28, merged, NOT deployed** (owner: "go for phase
  6 and wait for my approval to deploy"). October batch #270–#277 rebased,
  re-gated, merged (#272/#274 agent-page conflict resolved, advisories first,
  combined-render test). #278 roster `homepage` field (HOL Guard, #216) +
  daily corrections monitor. #279 MCP server on SDK v2 (2026-07-28 clients
  got HTTP 400 on v1): dual-era tests over HTTP with the SDK Client, 1 h
  public cache hint, own serverInfo.version 0.4.0, GET /mcp 405 +
  subscriptions/listen unregistered (both hang under v2), mcp_by_method
  counter. #280 runtime deps + ruff 0.16.9 + Pillow floor; #283 cryptography
  44.0.3 -> 50.0.1 (seven advisories; signatures byte-identical, live
  credential verifies; pip-audit clean — CI's audit step is continue-on-error).
  #282 Actions majors — its manual scorecard-scan run caught a silent break:
  download-artifact v8 extracts a lone shard flat into shards/, the merge glob
  matched nothing and exited green ("No shard artifacts to merge"), which
  would have stopped every Scorecard update; merge now uses `find`, re-run
  pushed data b98ac24..d903d31. #284 advisories skip packages with no release in 365
  days (AutoGPT's agpt 2023) + docs/advisory-scoring-review-2026-09-28.md
  (R3 recommended: OmniRoute A->C, Chroma/LobeHub B->C; owner decision).
  hvtracker-mcp: mcp#2 0.3.1 `mcp<2` hotfix (PyPI installs broken since mcp
  2.0 on 28 Jul; CI red since 9 Aug, unnoticed) + weekly fresh-install job;
  mcp#3 0.4.0 on v2. Tags unpublished pending approval. All 9 Dependabot PRs
  and #152 closed as superseded.
- **October batch + Phase 6 DEPLOYED 2026-09-28 13:36 UTC** (2b955d87 @
  e272e068, owner-instructed; everything merged since 25 Sep, #270–#286).
  Boot clean (0 tracebacks/SyntaxWarnings); "[startup] scheduler started
  (batch + signals every 4h)" — one refresh job, next 16:00 UTC. Verified
  live: MCP 2026-07-28 server/discover 200 (ttlMs 3600000, listChanged
  false), tools/list 8, tools/call works; 2025 initialize -> 2025-11-25,
  serverInfo 0.4.0; GET /mcp 405; healthz machine_usage.mcp_by_method; HOL
  Guard homepage + sameAs; Composio raise-score section; header search +
  search-index.json 200; /data/history/2026-06-01.json 404 (90-day window);
  auth.js signed-in hint; analytics.js webdriver guard; build_report
  invariants []. Declared homepages (#286) and OSV advisories (#272/#284)
  fill in as rows get their daily full fetch (whole board within ~24 h).
  Still open: publish hvtracker-mcp v0.4.0 (owner OK), reply on #216,
  advisory-scoring decision (R3), bill check ~1 Oct, CTR readout 8 Oct.
- **Repository/Website buttons DEPLOYED 2026-09-29 06:53 UTC** (2337e313 @
  12e2dcf6, #288; owner-instructed). Hero shows [GitHub mark] Repository and
  [site favicon] Website buttons; favicons fetched in the full fetch, stored as
  32x32 PNGs under /site-icons/ (672 of 977 live homepages had a usable one in a
  test run). Verified live: buttons on HOL Guard/Langflow/E2B (globe until each
  row's next full fetch brings its favicon). Fill-in from the 28 Sep deploy at
  06:55 UTC: 1,116 of 1,676 rows full-fetched, 644 declared homepages,
  advisories checked on 543 (Chroma, LobeHub critical; Aider low).
  build_report invariants []. Measured for planning: MCP 109,482 requests vs
  2,183 tool calls since 9 Aug (2%); 16 tool calls in the last 24 h; ~13% of
  /mcp requests since the v2 deploy use the 2026-07-28 protocol.
- **R3 advisory ceiling + /live/ tool calls DEPLOYED 2026-09-29 14:18 UTC**
  (c2abb264 @ e421379d, #290–#293; owner-instructed). Methodology v4.4 live:
  unfixed CRITICAL advisories cap the score at 64.9 (Grade C), HIGH at 79.9.
  Verified live: OmniRoute 64.9 (#60, seal note "93.4 without it"), Chroma
  64.9 (#483), LobeHub 64.9 (#63), matching the merge-day gate; /live/
  headline counts tool calls; healthz machine_usage.mcp_other_methods present
  (empty so far); badges page links the Marketplace listing. Boot
  repair-commits refresh finished 14:21 UTC; next 4-hour refresh 16:00 UTC.
  build_report invariants [], package_failures 1.
- **Listing batch 1 DEPLOYED 2026-09-29 15:36 UTC** (26886893 @ f7811721,
  #296/#297; owner-instructed). Board 1,676 -> 1,702 (catalog 1,731): 26 new
  listings (18 agents/MCP/tools, 8 skills); 23 rejections added to
  REVIEWED_REJECTED (19 from the pre-screen + 4 held: Fuxi proprietary
  license, three inorganic-star profiles). The new rows stayed provisional
  through the boot repair-commits refresh (it only targets rows already in
  data.json) and were scored by the 16:00 batch, matching the merge-day gate
  (hypit 75.6 #217; the rest Grade D at 0.5-0.67 confidence pending
  Scorecard) except reef: pypistats returned 429, and a new row has no prior
  downloads value to carry, so it sits at 47.7 until its next full fetch.
  build_report invariants []. OUTAGE ~6.5 min (15:28-15:34:50): the build
  landed on an uncached builder (queue ~6 min, 0 cached layers, slow push),
  and because the service has a volume Railway stops the old container before
  starting the new one; container start 15:29:14, uvicorn 15:30:38, first
  healthcheck 15:32:37, traffic ~15:34:50. The earlier deploy today took
  ~2 min end to end. Cause: Railway incident "API degradation causing slow or
  stuck deployments" (https://status.railway.com/incident/YYTG8I10, 15:29-19:15
  UTC; Hobby deploys were paused while the queue drained).
- **Newly added tab next to Global DEPLOYED 2026-09-29 21:14 UTC** (e6f03359 @
  21f4e606, #299; owner-instructed after the Railway incident cleared). The tab
  had rendered after all 18 category tabs, off-screen at the end of the
  scrolling strip. Verified live after the boot refresh: Global, Newly added,
  MCP Servers. Outage ~1.5 min (21:12:23-21:14:00). build_report invariants [].
- **Phase 8 "Citable provenance" DEPLOYED 2026-10-01 13:46 UTC** (635b7af2 @
  740970b7, #301-#304; owner-approved). Approved 30 Sep after the competitor
  report (AgentSeal copies the "Is X Safe? Score N/100" template at 7x MCP
  coverage); the owner skipped the 5 Oct bill check (bill already under
  forecast) and asked for profile pages unlike the rivals'. #301: "Chain of
  custody" under the verdict on every scored profile (source signatures ->
  review/release Scorecard checks -> each package's source link and attestation
  -> OSV on the installed release; changes, evidence types, offline
  verification, what the score doesn't check), replacing Supply Chain Trust.
  #302: GraphQL never set full_name, so the T3.1 rename guard was dead; fixed,
  and package targets are resolved through GitHub redirects (gate: 11 rows +5,
  Superagent D->C, 0 top-100 moves; rows update at their next full fetch, so
  e.g. Garak still showed "Source mismatch" right after deploy). #303: daily
  incident-watch issues (critical/high OSV advisory <= 14 days old, draft X
  post; docs/incident-playbook.md). #304: /blog/who-ships-your-mcp-servers/
  (37,220 active registry servers: 22.2% remote-only, 18.5% of declared repos
  404, 30.2% no public source, 0.9% public Scorecard, 28% of packages attested;
  sample.csv + metrics.json CC BY 4.0). Owner: no X thread or emails; the post
  and the Q3 quarterly report are the outreach. Verified live: custody tags on
  garak/haystack/composio, post + CSV + index card + sitemap + feed, policy
  log; build_report invariants []. Downtime not measured (healthz answered
  6 s after SUCCESS). Scheduled task
  hvtracker-competitor-watch (monthly, writes ~/hv_marketing/watch/). Open:
  #305 roster package fix (gated, needs its own deploy yes); Zenodo DOI for
  Q3 + the study files (owner); CTR batch 2 readout 8 Oct.
- **Roster fix + dataset fixes + listing batch 2 DEPLOYED 2026-10-01 15:10 UTC**
  (931e1351 @ 469d9ac6, #305 #307 #308 #309 #310; owner: "approve as
  recommended and deploy together"). #305 drops 10 package ids that belong
  to other projects (policy log 2026-10-01; the 09-30 "15 are real" line is
  corrected). #308: exports carry `listing_class` (Q4 header verified live).
  The owner had caught ranks 1-359 appearing twice in the Q3 CSV; the
  Zenodo copy (DOI 10.5281/zenodo.23084548, #309) was packaged with the
  column backfilled. #310 batch 2 from the 29 Sep section B: added trycompai/crm,
  yetone/cumora, deeplethe/utopia, tigerless-labs/cost-xray and skills
  img2threejs and J-Space Cognition Suite; rejected spinabot/brigade,
  tutti-os/tutti, yc-software/qm and genspark-ai/genoffice. trailhq/Graft was
  approved but turned out to be the already-listed NanoNets/Graft (redirect),
  so the row moved to trailhq/Graft via previous_repos. Boot DB sync "synced
  1737, pruned 1" (the old Graft key); score 64.8 and rank #484 carried over.
  Gate: the 6 enter at Grade D, no top-100 moves, max |drank| 4. Verified
  live: Q4 export header, /data-api/ DOI, policy log, board 1,708,
  invariants []. The 6 new rows were provisional until the 16:00 batch. #302
  and #305 data changes land per row at its next full fetch (~24 h; e.g.
  voyager still showed npm `voyager` right after deploy). GitHub no longer
  lists stargazers (REST 404, GraphQL empty), so the inorganic-stars check is
  now star velocity plus the forks ratio.
- **Phase 9 MCP registry feed DEPLOYED 2026-10-02 07:15 UTC** (48d7a373 @
  ca469be5, #312; owner: "deploy"). A v0.1 subregistry of the official MCP
  registry at /registry/{all,grade-a,grade-b,grade-c}, with HVTrust under
  server._meta["net.hvtracker/trust"]. It works as a GitHub Copilot "MCP Registry URL"
  (Copilot appends /v0.1/ and needs the CORS headers sent). Graded lists
  admit an entry only when its publisher is tied to the repo
  (io.github.<owner> = repo owner, or a domain namespace on the repo homepage
  or the owner's GitHub profile website), so republishes such as
  ai.smithery/* can't inherit a repo's grade. registry-snapshot.yml (daily
  03:23 UTC) puts mcp-registry-snapshot.json on `data`; the app pulled it at
  boot ("961 entries"). Verified live: A 81, A/B 299, A-C 700, all 958;
  CORS + OPTIONS 204; single-server lookups with encoded names; /registry/
  guide linked from /data-api/ and the sitemap; usage channel "registry"
  counting (baseline: 7, all from the deploy checks); invariants [].
- **hv_marketing sessions' batch DEPLOYED 2026-10-02 08:31 UTC** (a1ce580e @
  935ecbfb, #314-#317; owner: "deploy"). Opened by the hv_marketing sessions
  ("GitHub issue #711", "Pages not indexed in Google Analytics"), reviewed and
  merged in this session after confirming neither session was running; the
  combined main passed every gate. #314: sitemap lastmod fingerprint masks
  numbers and rank-driven regions (fp v2; the first render keeps stored
  dates, so 2,087 URLs still read 2026-10-02 from the morning's old-fingerprint
  refreshes; check on 3 Oct that only changed pages move). #315: no /data/
  JSON in the sitemap (0 of 2,137). #316: listing batches paused until the
  batch 1-2 pages are indexed. #317: the duplicate Headroom listing is merged
  (row moved to headroomlabs-ai/headroom via previous_repos; the skill
  duplicate is gone; /agents/headroomlabs-headroom/ 301s; Headroom stays 74.0,
  #247). predeploy_check flagged 1736 < 1737: that is the intended merge.
  Every live board row is still covered by the roster (current or previous
  name), and boot "synced 1736, pruned 1". Invariants [].
- **Roster rename sweep DEPLOYED 2026-10-02 10:49 UTC** (4bb85793 @ 7ba777cc,
  #320; owner: "deploy"). 47 listings moved to their current GitHub names via
  previous_repos (google/A2A -> a2aproject/A2A, LibreChat -> LibreChat-AI, ...);
  2 duplicates merged: privategpt absorbs zylon-ai-privategpt, notfair absorbs
  notfair-plugin, both 301. Discovery's duplicate check now matches previous
  names and live-board urls; a renamed row falls back to its old name's
  Scorecard scan instead of None. Gate: 0 score changes, max |drank| 1, no
  top-100 moves. predeploy_check flagged 1734 < 1736 (the intended merges;
  every live row still covered). Boot: "synced 1734, pruned 47" (47, not the
  49 predicted: the originals moved onto the duplicates' names, so those keys
  stayed). Verified: board 1,705, 0 stale repo keys, PrivateGPT #671 and
  NotFair #204 as gated, Scorecards kept, 0 provisional rows, invariants [].
  Registry snapshot re-run after deploy: 981 entries (from 961), now that
  renamed repos match their registry entries.
- **OWASP mapping + independence DEPLOYED 2026-10-03 21:27 UTC** (423565d2 @
  5e156223, #322; owner: "deploy"). /methodology/#owasp (ASI04, AST02 covered;
  AST07, AST01 partly; ASI01/02/05/06 not covered), /methodology/#independence,
  one OWASP line in every profile's chain-of-custody intro, and a fix for the
  methodology code sample that widened the page on phones. Verified live;
  invariants []. MISTAKE: the profile line was meant to sit in a
  lastmod:skip region so it wouldn't re-date profiles, but adding the region
  also changed the whitespace around it, so all 1,445 agent URLs took
  2026-10-03 once. Not reverted, because a second template change would
  re-date them again. Rule added to CLAUDE.md: bump LASTMOD_FP_VERSION with any
  sitewide template edit, so the first render re-keys hashes and keeps dates.
  Same-day checks: all 50 renamed rows (#320 sweep plus the 3 earlier renames)
  had a full refresh and kept their Scorecard (the old-name fallback works);
  outside the profile re-date, sitemap dates moved for 7 of 55 blog URLs,
  0 of 10 specs and 17 of 131 org pages.
- **Phase 10 batch DEPLOYED 2026-10-04 21:06 UTC** (601f4142 @ 972346ff,
  #325-#328; owner: "go ahead and deploy"). #325: logged title/description
  overrides for profiles and categories (`CTR_TEST_AGENT`,
  `CTR_TEST_CATEGORY`, both empty, so no page changed) and
  `scripts/lastmod_diff.py`. #326: JSON-LD text values are JSON-encoded
  instead of HTML-escaped (330 pages had sent Google "&amp;", mostly the
  category on 303 profiles). #327: /sponsor no longer offers "supported
  compare pages" (owner decision). #328: profiles stop re-dating on every
  refresh (volatile hero, rank-arrow, push-recency and timeline regions in
  lastmod:skip; Scorecard checks in fixed order; migration stamps unchanged
  pages). LASTMOD_FP_VERSION went 2 -> 4 in one deploy. Verified: boot
  repair refresh succeeded 21:08, sitemap dates moved for 0 of 2,136 URLs
  (snapshot before vs after), a2ui JSON-LD reads "&", /sponsor has no
  compare offer, invariants [], package_failures 1 (AynOps). Check on 5 Oct
  that profile dates mostly stay 2026-10-04 after the day's refreshes.

## Entries recorded only in the old AGENTS.md

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
