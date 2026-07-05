# HVTracker Product Plan — from v3.1.0 forward (2026 H2)

Baseline: **v3.1.0** (`main` @ `6e81b1181`, tagged 2026-07-01). This plan continues
the public `/roadmap` and the internal `growth-plan.md` / `trust-layer-execution.md`
tracks, folding them into one sequenced milestone plan and adding the feature depth
to move HVTracker from "trust leaderboard" to a two-sided AI-ecosystem platform.

## Where we're starting (confirmed against code)

| Area | State | Evidence |
|---|---|---|
| Supply-chain HVTrust v3 (5-dim score, grades A–D) | ✅ live | `/roadmap` "Now Shipped" |
| Runtime-trust **discovery** fields on profiles | ✅ live, not yet in rank | `render_state.json` runtime fields |
| Runtime-trust **calibration** (Score Lab, `trust_score_v2`) | 🟡 in progress | `compute_trust_score_v2` `fetch_and_build.py:1562`; `/score-lab` |
| Accounts + GitHub/Google OAuth, watchlist, notifications | ✅ shipped v3.1.0 | `auth.py` (`/api/notifications` :495) |
| Knowledge graph + ecosystem/org SEO pages | ✅ shipped | `build_graph` `:2968`, `build_ecosystem_pages` `:3029`, `build_org_pages` `:3065` |
| Public read API (`/api/v1/graph`, `/api/v1/agents`) | ✅ shipped | `app.py:761,774` |
| Trust layer P1 (signed attestation) / P2 (open lookup) / P3 (MCP verify) | ✅ shipped | `signing.py`, `open_lookup.py`, `mcp_trust.py` |
| Weekly-changes computation | ✅ exists | `compute_weekly_changes` `fetch_and_build.py:2167` |

## Guiding constraints (do not violate)

1. **The verdict stays open.** Verification + methodology + attestation format are public forever. Monetize operations/scale/privacy only (`trust-layer-execution.md` guardrail; `open-core.md`).
2. **Monetization is on hold** (visa). No paid-tier code, billing, or gated core until that unblocks. Optimize for free adoption + moat depth instead (`monetization-on-hold.md`).
3. **The moat is relationships + runtime trust + history — not the formula.** Every day history isn't captured is data lost forever; prefer features that deepen the graph and the time series.
4. **Never destabilise the leaderboard on a hunch.** Any change to production rank is evidence-gated (Score Lab upset review) and shipped as a *separate visible slice*, never a silent reweight.
5. **Execution rules:** one task = one branch (`feat/<id>`) = one PR off latest `main`. Never hand-edit generated output (`agents/`, `ecosystem/`, `org/`, `data/`, `sitemap.xml`, `index.html`, `blog/`, `compare/*-vs-*/`, `changes/`) — change the generator + re-render. Every PR ships with three gates green: `python -m pytest` && `python fetch_and_build.py --render-only` && `python tests/validate_html.py`. `main` is protected (PR-only).

---

## Milestone v3.2 — Retention & Freshness

**Theme:** turn the accounts/watchlist/notifications we just shipped into a reason to
return. Lowest risk, highest near-term leverage (retention ≈ 0 today). Reuses machinery
that already exists; ships no ranking change.

- **T2.1 — Watchlist notifications.** When a watched agent's `trust_score` or `rank`
  moves past a threshold, create an in-app notification. Build on `compute_weekly_changes`
  (`:2167`) for the per-agent diff and the existing notification store (`auth.py`
  `/api/notifications`). *Files:* `auth.py` (notification creation), a hook in the render/refresh
  path. *Accept:* a moved watched agent yields exactly one notification; unwatched moves yield none.
- **T2.2 — Public "What changed this week" page + RSS.** Render `compute_weekly_changes`
  output to `/changes/` (page exists) and add `changes/feed.xml` (RSS 2.0) if not yet present,
  linked via `<link rel="alternate">` and the sitemap. *Files:* `fetch_and_build.py`,
  `templates/changes.html.j2`. *Accept:* `xml.etree` parses the feed; `/changes/` in sitemap.
- **T2.3 — Automated weekly/monthly trust-snapshot posts.** Productionise the
  prototype snapshot generator (was local WIP): grounded, **fact-checked** narrative
  (numbers injected, never invented; deterministic fallback if the LLM is unavailable)
  rendered into `blog_static/<slug>/` and wired into all four blog surfaces
  (`blog_index` card, `sitemap_urls`, `blog_feed_items`) per `blog-publish-pipeline.md`.
  Run on a weekly/monthly cron. *Accept:* post renders, appears in sitemap + feed, and a
  test asserts every figure in the prose traces to a snapshot value.
- **T2.4 — Debt / quick wins (parallel, hours each).**
  - ~~Cloudflare cache rule for HTML/JSON~~ ✅ done 2026-07-02 (dashboard, "use cache-control header if present, bypass if not" on both Edge/Browser TTL; TTFB 1.16s → ~0.15s on cache HIT; verified `/account`,`/api/*`,`/auth/*`,`/healthz` stay uncached).
  - Dedupe the inline `:root` accent blocks (~20 files) into `static/site.css` (handoff smell — makes every future theme change one file).
  - Multi-stage Dockerfile (BACKLOG 🟡 — shrink runtime image; Pillow/fonts to a builder stage).

*Exit criteria:* a logged-in user with a watchlist receives a weekly digest of real
changes through the bell + a public changes feed, and the site publishes an automated
weekly trust snapshot. No rank changes.

---

## Milestone v3.3 — Runtime Trust, Calibrated (the moat)

**Theme:** move runtime signals from *discovery* to *scored*, safely. This is the core
differentiator (nobody else scores runtime trust). Evidence-gated; the calibration engine
(`compute_trust_score_v2`) already exists — the pending work is the go/no-go and the safe rollout.

- **T3.1 — Calibration evidence + go/no-go (no production change).** From `trust_score_v2`
  (`:1562`, already computed per row), generate an **upset-review report**: largest v1→v2 rank
  swings, per-dimension attribution, and stability metrics. Write explicit go/no-go criteria
  (max acceptable churn, no A-grade project dropping >N ranks without cause). *Deliverable:* report doc.
- **T3.2 — Publish `/spec/runtime-trust`.** Add the runtime-trust methodology to `specs.py`
  and advertise it in `.well-known` (keeps the verdict open before it affects rank).
- **T3.3 — Per-agent capability-surface page/section.** Expand the runtime fields
  (`mcp_server_support`, `external_service_dependencies`, `tool_plugin_surface`, provenance
  drift) into a clear breakdown on `templates/agent.html.j2` + a dedicated capability view,
  each field linking to its ecosystem hub.
- **T3.4 — Fold runtime as a separate visible scoring slice** ✅ shipped 2026-07-02, then
  **fully promoted to the core same day** (see Done, "core swap"). `trust_score_v2` IS
  `trust_score`/`rank`/`evidence_grade` everywhere, including badges and signed credentials —
  not a toggle-gated alternate view. Public per-field explanations stay live on every row; the
  pre-calibration baseline is preserved for comparison (Score Lab), not silently discarded.
- **T3.5 — Runtime drift trend.** Use `output/history/*` snapshots to chart runtime-field
  drift over time on profiles (append-only history is the irreplaceable asset — start capturing
  the needed per-field summary in snapshots *now*, even before the page exists).

*Exit criteria:* runtime trust is either scored (as a separate slice, with a published spec
and explanations) or explicitly held with a documented reason — never silently half-applied.

---

## Milestone v3.4 — Ecosystem Depth & Developer Adoption

**Theme:** deepen the knowledge-graph moat and open developer adoption channels (still free tier).

- **T4.1 — Interactive ecosystem graph explorer.** Productionise `graph-viewer.html`
  against `data/graph.json` (`build_graph` `:2968`): a visual, shareable project ↔ provider ↔
  org ↔ MCP explorer with deep-links. High-value SEO + social surface; no new data.
- **T4.2 — Public API expansion (free, versioned).** Add documented read endpoints on top of
  `/api/v1/graph` + `/api/v1/agents` (per-provider, per-org, filtered queries), a proper
  `/api` docs page, and stable schemas. Note in each PR: auth/quotas for a future paid tier stay out of scope.
- **T4.3 — Maintainer-level data (opt-in, budgeted).** growth-plan Phase 8.2: top contributors
  per repo → `MAINTAINED_BY` edges in `build_graph`, cached under a stated GitHub API budget.
  Data first, pages later. Requires explicit opt-in (rate-limit cost).
- **T4.4 — Badge adoption engine.** New badge variants (trust-trend, category-rank), an
  embeddable widget, and a light second outreach wave (see `badge-outreach-campaign.md` — respect
  the spam-freeze caution; target new adopters, not repeat pings).

*Exit criteria:* the ecosystem is explorable visually and queryable via a documented free API;
badge adoption has a repeatable, non-spammy engine.

---

## Milestone v4.0 — Two-Sided Platform: Maintainer Self-Service & Identity

**Theme:** turn HVTracker from a registry *about* projects into a platform maintainers
*participate in*. Bigger, later; several items unblock only after traffic and/or monetization.

- **T4.0.1 — Maintainer claim, done right.** Re-introduce claiming (removed in v3.1.0) as
  verified GitHub-ownership: a maintainer proves the repo, then can declare runtime fields
  *with evidence* and respond to drift/provenance mismatches. Reuses the OAuth identity from v3.1.0.
- **T4.0.2 — Cryptographic identity gate.** Require Sigstore-style identity binding to reach the
  verified tier at the top of the leaderboard (builds on P1 `signing.py`).
- **T4.0.3 — Continuous behavioural signals (opt-in).** Lightweight runtime telemetry detecting
  when an agent's actual behaviour drifts from declared capabilities — no user data leaves the agent.
- **Deferred behind traffic + monetization unblock:** paid-tier plumbing (accounts/keys/metering/
  Stripe), extended history depth, higher-volume API, hosted alert delivery (email infra).
  Tracked in growth-plan 9.2; do not start without the visa/monetization gate clearing.

---

## Sequencing rationale

1. **v3.2 first** — it compounds the v3.1.0 accounts investment (currently idle), fixes the
   weakest metric (retention), is low-risk, and needs no ranking change. Fastest payback.
2. **v3.3 second** — the moat, but it must follow calibration evidence; doing it earlier risks
   shipping a rank change on a hunch (constraint #4).
3. **v3.4 third** — adoption/SEO depth compounds over months, so start the graph/API/badge
   surfaces once retention and the scoring story are solid.
4. **v4.0 last** — two-sided features and identity gates are heavier and partly gated on
   monetization; they land on a mature base.

The one item that jumps its slot: **start capturing runtime-drift per-field summaries in
history snapshots during v3.2** (part of T2.x plumbing), because that time series can't be
backfilled later.

## Deferred / explicitly out of scope (for now)

- Any paid tier, billing, or gated core (monetization hold).
- Graph database / new infra — `graph.json` stays a render artifact until edges exceed ~50k.
- Scoring-formula changes outside the calibrated runtime slice (T3.4).
- Hosted email digest delivery — v3.2's digest is on-site (notifications + RSS), no email infra.

## Risk register

| Item | Risk | Mitigation |
|---|---|---|
| T3.4 runtime → production rank | Leaderboard churn erodes trust | Evidence gate (T3.1), separate visible slice, flagged staged cutover, keep old rank one release |
| T2.3 snapshot-blog LLM narrative | Invented figures | Numbers injected + fact-check pass + deterministic fallback; test asserts every figure traces to data |
| T4.3 maintainer data | GitHub API rate-limit / cost | Opt-in only, stated budget, cache-first |
| T4.0.1 claim re-introduction | Same UX issues that got it removed | Rebuild on verified OAuth ownership, not the old lightweight flow |

---

## Done

- **T2.1** watchlist-notification regression tests — 2026-07-01, PR #81 (feature already existed; tests lock acceptance criteria)
- **T2.2** changes-feed XML-escaping fix + parse test — 2026-07-02, PR #82 (page/RSS/sitemap already existed)
- **Homepage daily-movers ticker** (gainers + losers scrolling strips) — 2026-07-02, PR #83
- **T2.3** automated weekly trust-snapshot posts — 2026-07-02, PR #86 (deterministic v1, render-derived from history snapshots, no LLM/cron; fact-check test included)
- **CLAUDE.md/AGENTS.md rewritten as project bootstrap** — 2026-07-02, PR #85
- **Sitemap/feed Cache-Control** — 2026-07-02, PR #88 (closes the edge-cache BYPASS gap)
- **Runtime-drift snapshot-fields lock (T3.5 plumbing)** — 2026-07-02, PR #89 (fields were already captured; test prevents silent loss)
- **T2.4 `:root` dedupe** — 2026-07-02, PR #90 (paper/ink family → site.css; score-lab/spec families are separate systems, left as-is)
- **T2.4 multi-stage Dockerfile** — 2026-07-02, PR #91 (605→591MB; fixed scorecard fetch that had silently never worked — curl absent in python:slim)
- **T3.1 upset-review report** — 2026-07-02, PR #92 (`docs/t3.1-upset-review-2026-07-02.md`; verdict **NO-GO** as calibrated: drift dimension dominates, 6 A-grade unreviewed droppers; T3.4 stays gated)
- **T3.1 false-positive audit (3 rounds)** — 2026-07-02, PRs #96, #98, #99 (same-owner + repo-transfer drift false positives; external_dependencies/tool_plugin_surface README-mention over-counting. Every one of ~26 flagged warnings traced to a false positive, zero real risks found. Churn 19%→13%; remainder root-caused to leaderboard density, not signal noise — addenda 1-4 in the report)
- **T3.2** `/spec/runtime-trust` v0.1 — 2026-07-02, PR #95 (spec-matches-code test)
- **Sparkline methodology-version reset** — 2026-07-02, PR #100 (rank-trend charts restart at a scoring-methodology change instead of showing a misleading bump; prep for T3.4's cutover)
- **T3.4 (initial)** fold runtime as the default homepage view — 2026-07-02 (client-side toggle only; server-rendered HTML/API/badges/signing stayed v1). Superseded same day.
- **T3.4 (core swap)** — 2026-07-02, owner-confirmed full promotion, no adopter heads-up: `trust_score`/`rank`/`evidence_grade` are now runtime-calibrated everywhere (leaderboard, agent/category/org pages, `/data` API, badges, signed credentials). Old base preserved as `trust_score_historical_v1`/`rank_historical_v1` for Score Lab comparison only. `METHODOLOGY_VERSION` v3.2→v4.0 (resets rank-trend sparklines at the cutover, suppresses the cutover day's trust/rank notification events). **Confirmed consequence:** 27 agents flip letter grade (17 downgrade) the moment this deploys, incl. Google Genkit, Semantic Kernel, AutoGPT, Ollama — no announcement made, per explicit owner instruction. Verified live end-to-end via the full app (homepage, agent pages, Score Lab, badge SVGs, public API all consistent).

**v3.2 exit criteria status:** changes feed + weekly snapshot ✅ shipped to `main` (NOT yet deployed — manual `railway up` pending). Cloudflare cache rule ✅ live in prod 2026-07-02 (independent of the code deploy — a dashboard/edge change, doesn't need `railway up`). Remaining from T2.4: `:root` dedupe, multi-stage Dockerfile.

---

*Update this file as milestones ship (move done tasks to a "## Done" list with date + PR).
Engineering debt that isn't product-facing stays in `docs/BACKLOG.md`.*
