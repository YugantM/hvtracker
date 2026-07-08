# HVTracker Master Plan — 2026-07-07

**Status:** ACTIVE. Supersedes `product-plan-2026-h2.md` as the forward plan
(that file remains the v3.x historical record). Written to be executed by a
fresh AI session (Opus 4.8-class or better) with **zero prior context** —
everything needed to understand the project, its constraints, and the next
year of work is in this file plus `/CLAUDE.md`.

**How to use this document:** read §0 (orientation) and §7 (execution
protocol) fully. Then pick the highest-priority unfinished task in §6, do it
as one branch = one PR with the three gates green, and update the checkbox
here. Do not reorder phases without an owner decision. Do not deploy without
an explicit owner instruction.

---

## 0. Orientation — what this project is

**HVTracker** (https://hvtracker.net) is an independent, evidence-based
**trust registry for open-source AI agents**. It assigns each listed agent an
**HVTrust score** (0–100) computed from verifiable public signals (GitHub
activity, OSSF Scorecard, package provenance, signed commits, downloads,
runtime-capability analysis), a **trust grade** A–D (score band), and — since
2026-07-06 — a separate **coverage grade** A–D (breadth of independent
evidence). Scores are **runtime-trust calibrated** (methodology v4.2): a base
supply-chain score is adjusted by bounded bonuses/penalties for MCP support,
external-service dependencies, tool/plugin surface, and provenance drift, per
the published spec at `/spec/runtime-trust/v0.2/`.

- **Stack:** Python. FastAPI (`app.py`) serves a statically generated site
  produced by `fetch_and_build.py` (~6k lines — **never read it whole; grep
  for `def <name>`**). Jinja templates in `templates/`, homepage in
  `template.html`. Postgres for accounts/watchlists (falls back to files when
  `DATABASE_URL` unset). Deployed on Railway behind Cloudflare.
- **The owner** is a solo developer (Yugant) on a visa that **prohibits
  monetization** for now — no billing, paid tiers, or payment code of any
  kind until that changes. Engineering is done through AI coding sessions;
  every task in this plan is sized to be completable in one such session.
- **Non-negotiable rules** (from `/CLAUDE.md`, repeated because they are the
  ones a fresh session is most likely to violate):
  1. One task = one branch (`feat/<id>`) = one PR off latest `main`;
     squash-merge; linear history.
  2. **Merging ≠ deploying.** Deploy is a manual `railway up` from a clean
     worktree, only when the owner explicitly says so.
  3. Never hand-edit generated output (`agents/`, `ecosystem/`, `org/`,
     `data/`, `sitemap.xml`, `index.html`, `blog/`, `compare/*-vs-*/`,
     `changes/`) — change the generator and re-render.
  4. Never change production rank without an evidence gate (upset review);
     scoring changes ship as separate visible slices, never silent reweights.
  5. `output/history/*.json` daily snapshots are **irreplaceable IP — never
     delete** (see §5, risk R1).
  6. Every PR: `python -m pytest && python fetch_and_build.py --render-only
     && python tests/validate_html.py` all green, then
     `git checkout -- data/render_state.json og-v2.png` before committing.

---

## 1. State of the project — verified 2026-07-07

Everything in this section was checked against the live site or the repo
today, not copied from older docs.

### 1.1 Live product

| Fact | Value (verified 2026-07-07) |
|---|---|
| Listed agents | **319 live** (342 in catalog incl. legacy/delisted) |
| Categories | 16 (largest: Agent Frameworks 76, Coding Agents 40, Memory & Knowledge 27, Browser & Computer Use 24) |
| Methodology | **v4.2** (compounding-calibration bug fixed 2026-07-05) |
| Top of board | vercel-ai-sdk 95.2 · codex 94.3 · haystack 94.2 · n8n 91.3 · qwen-code 90.8 — defensible, no 100-pins |
| Trust grades (score band) | A 32 · B 58 · C 58 · D 171 |
| Coverage grades (evidence breadth) | A 108 · B 68 · C 52 · D 91 |
| Rows with MCP-support signal | 122 of 319 |
| History snapshots | **35 daily snapshots since 2026-05-23** (~26 MB) — the moat dataset |
| Refresh cadence | ~30-min signals refresh (subprocess-isolated since #106), healthz green, render in sync |
| Signed credentials | **Live and signing** — `trust_credential.signature` (Ed25519) present on agent JSON, key published in `/.well-known/hvtracker.json`, 7-day expiry, verified today |
| Machine surfaces | `/api/v1/agents`, `/api/v1/graph`, `/api/v1/mcp/verify`, `/data/agents/<slug>.json`, `llms.txt` (HTTP 200), `/.well-known/hvtracker.json`, RSS feeds |
| Deploy state | **Everything through PR #114 is deployed and live** (coverage grade, content-truth pass, GSC cleanup — verified via live API today). The trailing "MERGED, NOT yet deployed" bullet in CLAUDE.md is stale; fix it (task 0.2). |

### 1.2 Audience & engagement (baseline 2026-06-25, GA4 + Search Console)

- ~2,500 active users/30d, but **week-1 retention ≈ 1–2%** — visitors are
  one-and-done evaluators.
- Channels: Organic Social ~52%, Direct ~39%, **Organic Search only ~3%**.
- Search Console: 57 clicks / 10.6k impressions / 0.5% CTR / avg position ~17.
  The site ranks pos 5–9 for money queries ("is X safe", "X vs Y" — "genkit
  vs langchain" is position 1) but sits on page 2 for most.
- ~97% of origin traffic is bots/crawlers (GA counts humans; Railway counts
  everything). This is not a cost problem (bots ≈ $0.30–0.60/mo egress) but
  it IS a signal: **machines already consume this site more than humans do.**
  §3 builds the strategy on that fact instead of fighting it.
- Accounts/watchlist/notification-bell shipped v3.1 (2026-07-01) but are
  essentially idle — retention features exist, retention reasons don't yet.
- Badge adopters: 4 READMEs (Haystack, Composio, AIPass, LightRAG). ~90 repos
  reached in the June campaign; **spam-freeze caution is in effect** — no
  repeat cold outreach.

### 1.3 Money

- Railway bill: memory line ~$6.60 → **~$2.28/mo** after the subprocess-render
  fix (#106, verified −65% on 2026-07-06). Re-check due **2026-07-12**.
- Remaining always-on services: web, Redis, and **two Postgres instances** —
  one is likely orphaned (ids in `traffic-billing-analysis` memory; env
  `dfc35ffb-…`). Consolidating is the next meaningful cut (task 0.5).
- A $6 soft usage alert exists; no hard cap set.
- Total infra target: **stay under ~$10/mo indefinitely** (§4).

### 1.4 Recent history you must know before touching scoring

The last 10 days contained a profound scoring transition. A fresh session
that doesn't know this will misread the data:

1. **v4.0 (2026-07-02):** runtime calibration was promoted to be THE
   production score everywhere (site, API, badges, signed credentials). Owner
   decision, deliberately unannounced. 27 agents flipped letter grade.
2. **v4.1 (2026-07-05):** soft ceiling on bonuses + evidence-first tie
   breaking (`_rank_sort_key`), shared `=N` display ranks, MCP `declared`
   bonus zeroed.
3. **v4.2 (2026-07-05, same day):** a pre-existing **compounding bug** was
   found — each render layered the calibration adjustment on the previous
   render's already-calibrated score, ratcheting scores toward 100 over
   weeks. One-line fix (seed base score before the v2 call,
   `fetch_and_build.py` ~5100) + regression test
   `test_runtime_calibration_does_not_compound_across_renders`. The board
   corrected hard: 215/319 grade flips, mean |Δrank| ~61 — because the LIVE
   board had been wrong, not the corrected one.
4. Each version bump reset rank sparklines and suppressed that day's
   notification events (`METHODOLOGY_VERSION` mechanism, PR #100).

**Consequences that still matter:** (a) history snapshots before 2026-07-05
contain inflated scores — any trend feature (§6 Phase 3) must annotate or
segment at methodology boundaries, never chart across them naively;
(b) badge adopters may now display worse grades than when they adopted —
handle outreach with care (task 2.3); (c) `trust_score_v2`/`rank_v2` are
now backward-compat aliases of `trust_score`/`rank`, and
`trust_score_historical_v1` is comparison-only.

### 1.5 Content inventory & gaps

Live content surfaces: leaderboard + daily movers ticker; 319 agent pages;
16 category pages (+ per-category articles); compare pages (persisted across
renders since #114 so indexed URLs stop 404ing); ecosystem hub (17 provider
pages, MCP-compatible, no-API-keys); org pages; use-case pages; ~14 blog
posts (incl. the v4.2-correction announcement); `/changes/` weekly diff +
RSS; automated weekly trust-snapshot posts (deterministic, no LLM);
methodology (canonical score reference incl. `#runtime-calibration`); 5 spec
pages; roadmap; badges page.

Content is now **truthful** after the 2026-07-06 content-truth pass (README
v4 section, real cadence, live counts). Remaining known gaps:

- ~~GitHub repo About text still says "172+"~~ — verified already updated
  ("300+ … runtime-trust calibrated") on 2026-07-07.
- **The history dataset is invisible.** 35 days of daily snapshots power
  nothing user-facing except sparklines and the changes page. Biggest
  content gap on the site (Phase 3 fixes this).
- **Capability data is per-row only.** MCP/provider/tool-surface data exists
  on every agent row but there's no browsable "what can this agent touch"
  page (task 1.1 — already owner-approved as T3.3).
- Internal linking is thin — GSC shows 196 crawled/discovered-not-indexed
  pages, mostly weakly-linked (task 2.1).
- 15 hand-written blog feed items stamp `now_iso` on every render — feed
  lastmod churn (task 0.6, small).
- Roster freshness: research on 2026-07-06 identified **5 vetted new agents
  to add, 4 repository moves to apply** (`docs/research/
  new-agent-candidates-2026-07-06.md` + companion JSON with copy-ready
  entries) — not yet applied (task 0.4).

---

## 2. Ecosystem forecast — the 12–24 months this plan is built for

Written 2026-07-07. Re-examine quarterly (§8); if a numbered assumption here
breaks, revisit the phase that depends on it before continuing.

**F1. Agents move from demos to production, so trust becomes a budgeted
problem.** Enterprises adopting agent frameworks inherit an un-vetted supply
chain (the framework, its plugins, its MCP servers, its model providers).
Security/procurement teams will increasingly ask "which agents are safe to
allow?" — the exact question HVTracker answers. Demand for *evidence-based,
third-party* answers rises; demand for vibes-based "awesome lists" falls.

**F2. MCP stays the tool bus, and its registry problem gets worse before it
gets better.** Malicious/typosquatted MCP servers are a documented attack
class. Official registries (Anthropic's MCP registry and platform
equivalents) will solve *identity* ("this server is who it says") but not
*behavior over time* ("this server's capability surface drifted last
month"). HVTracker should position as the **behavioral/trust layer above
identity registries — complementary, not competing.** Interop with them;
never race them on breadth.

**F3. Discovery shifts from search engines to AI assistants.** A growing
share of "is X safe / X vs Y" questions get answered inside ChatGPT/Claude/
Gemini, zero-click. Classic SEO still pays in 2026 (and the GSC numbers say
there's easy headroom), but the compounding play is **being the source
machines cite**: stable APIs, `llms.txt`, signed machine-readable
credentials, dataset exports, a published spec. HVTracker's ~97%-bot traffic
is early evidence this is already the real audience.

**F4. The agent-framework long tail decays; value shifts from breadth to
depth.** Hundreds of 2024–25 frameworks are going dormant. A registry whose
only asset is breadth becomes a graveyard directory. The assets that
appreciate are **longitudinal**: drift detection, grade migrations, "this
agent was abandoned 8 months ago and here's the day it happened." Nobody can
backfill a time series they never collected — every day of snapshots widens
a gap competitors cannot close.

**F5. Regulation is a tailwind.** EU AI Act obligations phase in through
2026–27; procurement checklists and SBOM-style attestation requirements
spread. Independent, versioned, signed attestations about agent supply
chains map directly onto that demand — and monetize well once the visa
constraint lifts.

**F6. The platform-player risk is real but survivable.** GitHub, Anthropic,
OpenAI, or Google could ship agent trust signals natively. Defenses:
(a) **neutrality** — a platform ranking its own ecosystem is conflicted;
HVTracker isn't; (b) **cross-ecosystem coverage** — one place for npm+PyPI+
crates+MCP+GitHub signals; (c) **history** (F4); (d) **embeddedness** —
badges in READMEs, CI gates, MCP lookups create switching costs. If this
risk materializes, the correct response is interop (publish credentials in
their format) plus doubling down on history — not a breadth war.

### Where HVTracker sits, and the irreplaceability thesis

HVTracker is a solo-run, ~$5/mo-infra, 319-agent registry. It cannot win on
breadth, marketing, or headcount. It can win by becoming **the trust
primitive the agent ecosystem consults** — think "Certificate Transparency +
OSSF Scorecard, for AI agents." Three compounding assets make it
irreplaceable, in priority order:

1. **The time series** (append-only daily snapshots since 2026-05-23). Not
   buyable, not backfillable. Protect it (task 0.1 — currently it lives on a
   single Railway volume) and surface it (Phase 3).
2. **Embedded distribution.** Every README badge, CI trust gate, MCP verify
   call, and LLM citation is a small switching cost. Ten thousand small
   hooks beat one big feature (Phase 1).
3. **Verifiable neutrality.** Published methodology + versioned specs +
   Ed25519-signed credentials + honest public corrections (v4.2 was
   announced as a defect fix — that's the brand). Every transparent
   correction deepens this (task 2.5, corrections page).

Everything in §6 traces to strengthening one of these three assets.

---

## 3. Audiences & the engagement model

Three audiences, in order of strategic weight going forward:

**A. Machines (LLMs, crawlers, CI systems, MCP clients).** Already the
volume majority. They convert into human trust when an assistant cites
HVTracker or a CI gate blocks a risky dependency. KPI: API/MCP request
counts (add measurement — task 1.2), LLM citations observed, dataset
downloads. This audience compounds and has zero retention problem.

**B. Evaluating developers (humans, one-and-done by nature).** They arrive
from social/search with a question ("is X safe?", "X vs Y"), get an answer,
leave. Don't fight the one-and-done pattern with engagement gimmicks —
serve the question better than anyone (capability pages, compare pages),
then offer exactly one hook: *watch this agent* (bell alerts on real
changes: grade flips, drift, abandonment). KPI: GSC clicks & CTR, watchlist
adds, W1 retention (expect modest movement — 1–2% → 5% would be excellent).

**C. Maintainers of listed agents.** They care about their own listing.
Badges are the pull-loop; claim-your-project (v2, verified ownership) is
the participation loop; the corrections process is the fairness loop. KPI:
badge adopters (4 today), claims, correction requests handled. This
audience is small but each conversion is durable distribution (their README
advertises HVTracker).

**Explicitly deferred engagement machinery:** email digests (needs email
infra + EU double-opt-in; owner deferred 2026-06-25), gamification,
comments/community. Revisit email only after watchlist alerts demonstrably
work in-app.

---

## 4. Budget envelope & resource constraints

Hard constraints this plan is designed around:

| Constraint | Value | Implication |
|---|---|---|
| Infra spend | **< ~$10/mo** Railway + $0 Cloudflare free tier | No new always-on services. No graph DB (graph.json stays a render artifact until >50k edges). No hosted email. Prefer render-time artifacts over runtime compute. |
| Monetization | **Blocked (visa)** — timeline unknown | No billing code, no paid tiers, no API keys with quotas. But DO keep the open-core boundary (`docs/open-core.md`) intact so a paid layer can bolt on later without un-shipping anything: never promise "everything free forever"; keep extended history, alerting delivery, and bulk exports scoped as future paid surface. |
| Paid APIs / LLM calls in the pipeline | **None** | The weekly snapshot posts are deterministic by design — keep it that way. GitHub API stays within free limits via the sharded `data`-branch scan. |
| Engineering capacity | Solo owner + AI sessions | Every task below is one-PR-sized with named files and acceptance criteria. Anything bigger is split. Docs (this file, CLAUDE.md) ARE the team memory — update them as part of shipping, not after. |
| Cost levers already identified | Postgres consolidation (task 0.5); hard usage cap | Bill re-check due 2026-07-12; if the memory ratchet returns, re-open #106. |

Budget rule of thumb for new features: **if it adds an always-on process,
it's wrong; if it adds a render-time artifact or a static page, it's
probably right.**

---

## 5. Risk register

| # | Risk | Likelihood | Impact | Mitigation / response |
|---|---|---|---|---|
| R1 | **Loss of `output/history/` snapshots** (single Railway volume; local copies ad-hoc) | Low | **Catastrophic — the moat is gone** | Task 0.1 (offsite backup, automated) is the single highest-priority item in this plan. |
| R2 | Another scoring-integrity defect (v4.2-class) reaches prod and sits unnoticed | Medium | High — trust brand | Regression tests exist for compounding; add render-time board invariants that fail loud (task 0.3). Never ship rank changes without the evidence-gate ritual (§0 rule 4). |
| R3 | Platform player ships native agent trust scores | Medium | High | §2 F6 playbook: interop + history + neutrality. Do not breadth-race. |
| R4 | SEO decay / zero-click growth erodes the human funnel | High (gradual) | Medium | Phase 1 (machine surface) is the hedge; Phase 2 SEO work targets already-ranking queries (cheap wins), not new territory. |
| R5 | Defamation/complaint risk from low public grades | Low | Medium | Grades trace to public evidence only; corrections page (task 2.5) + keep-all-grades transparency policy (owner decision 2026-06-25). Never editorialize beyond the evidence. |
| R6 | Solo-maintainer bus factor | — | High | This document + CLAUDE.md + deterministic pipeline + R1 backups are the mitigation. Keep them current. |
| R7 | Badge adopters churn after v4.2 grade corrections | Medium | Low | Task 2.3 audits adopter grades before any outreach; lead with the trend badge (improving > absolute). |
| R8 | Railway bill creep | Low | Low | $6 soft alert live; re-checks scheduled; task 0.5 removes a whole service. |

---

## 6. The plan — phases, features, tasks

Phases are ordered by strategic priority, but tasks marked ∥ can run in any
order within their phase. Effort: S = trivial session, M = one full session,
L = split into 2–3 PRs. Every task ships with the three gates green (§0).

### Phase 0 — Protect & finish (do first, ~1 week)

Closes out committed work and eliminates the one catastrophic risk.

- [x] **0.1 Offsite history backup (R1) — DONE 2026-07-07.** Mechanism:
  **private repo `YugantM/hvtracker-history-backup`** (main repo is public,
  so the `data` branch would have exposed the full time series against the
  open-core boundary). A self-contained GitHub Actions workflow there runs
  daily at 23:23 UTC: fetches the last 8 days of
  `hvtracker.net/output/history/<date>.json` (self-healing lookback) plus
  `data/{seo_state,render_state,retired,latest}.json` over public HTTP — no
  secrets needed. Seeded with all **46 prod snapshots (2026-05-23→07-07,
  no gaps, 37 MB)**; manual dispatch run verified green on GitHub's runner.
  Restore procedure documented in that repo's README. *Two observations for
  the owner:* (a) the full history is publicly fetchable by date-guessable
  URL at `/output/history/<date>.json` — fine today, but it undercuts the
  future paid extended-history boundary; decide later whether to restrict.
  (b) prod held 46 snapshots vs 35 locally — the volume, not the local
  checkout, is canonical.
- [x] **0.2 Truth sweep — S.** Done 2026-07-07: fixed the stale "MERGED,
  NOT yet deployed" trailing bullet in CLAUDE.md (everything through #114
  verified live); GitHub About text found already updated ("300+ …
  runtime-trust calibrated") — no `gh repo edit` needed; this plan +
  the 2026-07-06 agent-candidates research committed to the repo.
- [x] **0.3 Board-integrity invariants — DONE 2026-07-07.**
  `check_board_invariants()` in `fetch_and_build.py` runs on the final
  ranked board each render: max trust_score ≥ 99.5, scores outside [0,100],
  mean |Δrank| > 15 vs prior snapshot without a `METHODOLOGY_VERSION`
  change, listed-count drop > 5%. Violations print a loud stderr block and
  land in `build_report.json` (`board_invariant_violations`); the build
  fails hard only with `HVT_STRICT_INVARIANTS=1` so an unattended prod
  refresh degrades to a loud report instead of stale data (flipping prod to
  strict is a later owner call). Tests: `tests/test_board_invariants.py`
  (8 cases, each defect class + healthy/growth/methodology-change paths).
- [x] **0.4 Roster refresh — DONE 2026-07-07.** Added the 5 P1 agents
  (mini-SWE-agent, Mistral Vibe, CowAgent, oh-my-pi, Solace Agent Mesh; all
  re-verified via live github.com redirects) and applied the 4 repo moves in
  place (sst/opencode→anomalyco/opencode, block/goose→aaif-goose/goose,
  OpenInterpreter/open-interpreter→openinterpreter/openinterpreter,
  strands-agents/sdk-python→strands-agents/harness-sdk) preserving verified
  package fields. Catalog 342→347; board 319→324. All 9 render provisional
  (score 0) until the next prod signals refresh scores them — standard
  add-agent flow. *Known trade-off:* rank-delta/sparkline history is keyed
  by repo, so the 4 moved agents show as NEW until history re-accumulates
  under the new key (slugs/URLs unchanged — no 404s). The 3 manual-review
  candidates (LobsterAI, Agent Orchestrator, Sandcastle) still await owner
  judgment per the research doc.
- [x] **0.5 Postgres consolidation — RESOLVED 2026-07-07 (owner-approved).**
  Verification found it was **already done**: the second Postgres
  (5431cb90…) was deleted 2026-06-21T23:25Z — the 2026-06-22 billing memory
  captured its final hours. The project now runs exactly 3 services (web,
  Postgres-6A6t, Redis); `web`'s `DATABASE_URL` confirmed pointing at
  `postgres-6a6t.railway.internal`. Safety data dump of the live accounts
  DB taken to `~/hvtracker-db-backups/hvtracker-accounts-2026-07-07.json`
  (8 tables; 5 users, 6 watchlist rows — contains emails, keep local).
  *Bonus finding:* the render pipeline already archives each day's history
  snapshot to the Railway bucket `hvtracker-archive`
  (`storage.py` / `fetch_and_build.py` ~5432; 39 objects, 37 MB) — so the
  moat now has volume + Railway-bucket + GitHub-private-repo (46/46
  snapshots) redundancy.
- [x] **0.6 Feed lastmod fix — DONE 2026-07-07.** The 13 hand-written
  `blog_feed_items` now carry their real publish dates (recovered from each
  post's JSON-LD `datePublished`) instead of `now_iso`. The two remaining
  `now_iso` uses are intentional: compare-article fallback and per-agent
  items whose content genuinely changes each render. Locked by
  `test_handwritten_feed_items_have_stable_dates` in `tests/test_api.py`.
- [x] **0.7 Bill re-check — DONE EARLY 2026-07-07 (owner moved it up).**
  Post-fix window 07-05 15:40 → 07-07 20:03 UTC (3,144 points): web avg
  **0.267 GB** (p95 0.322, max 0.742); daily means 0.228 → 0.277 → 0.271 —
  **flat, no slow ratchet**, spikes release. Postgres avg 0.039 GB, Redis
  0.031 GB. Total memory run-rate ≈ **$3.4/mo**; fix verdict unchanged:
  WORKING. Optional re-glance on 07-12 for the 7-day mark.

### Phase 1 — Trust as infrastructure (the irreplaceability play, ~3–4 weeks)

Theme: make HVTracker the thing machines consult, not just a site humans
visit. Every task turns an existing internal asset into an external,
embeddable surface. This phase is the direct answer to §2 F2/F3/F6.

- [x] **1.1 T3.3 capability-surface page — COMPLETE 2026-07-07 (1.1a hub +
  1.1b agent sections).** 1.1b: agent-page runtime panels now link each
  detected provider to its `/ecosystem/<slug>/` page (slug map passed from
  the generator, never slugified in Jinja) and the section intro links the
  capability matrix; Capabilities added to the shared `_site_header` nav.
  T3.3 acceptance fully met (hub + agent sections render, capabilities link
  to ecosystem pages, sitemap, validate_html). `/capabilities/` hub live:
  `build_capability_matrix(rows)` + `templates/capabilities.html.j2` — all
  324 agents × MCP status / provider chips (linked to ecosystem pages) /
  tool-plugin surface / provenance drift, trust-ranked with summary stats
  (70 implement MCP, 17 providers, 85 require keys, 24 drift warnings) and
  ItemList/Breadcrumb JSON-LD. Wired: sitemap, llms.txt, homepage nav
  (Ecosystem panel), .gitignore, validate_html sample; tests
  `tests/test_capabilities.py` (4) + serving test in test_api. Remaining
  1.1b: per-agent capability section in `templates/agent.html.j2` linking
  back to the hub + ecosystem pages.
- [ ] **1.2 API: documentation, stability promise, and measurement — M.**
  (a) A real `/api/` docs page (OpenAPI or hand-written — hand-written is
  fine and cheaper) covering `/api/v1/agents`, `/api/v1/graph`,
  `/api/v1/mcp/verify`, `/data/agents/<slug>.json`, the `.well-known`
  discovery doc, and the CC BY 4.0 data license + attribution rule.
  (b) A one-paragraph versioning policy (fields are add-only within v1;
  breaking changes bump the path). (c) Cheap usage measurement: a
  UA/path counter middleware or log-line so API/MCP call volume becomes a
  visible KPI (currently unmeasured). *Accept:* docs page live in nav +
  llms.txt; counter visible in logs or build report.
- [ ] **1.3 HVTracker MCP server, productized — M/L.** `/mcp` exists
  (in-memory, rate-limited, kill-switched). Make it a first-class product:
  tools `lookup_agent_trust(slug|repo|package)`, `verify_mcp_server(id)`,
  `compare_agents(a, b)`, each returning the signed credential fields +
  grades + capability summary. Then **list it in MCP registries/directories**
  so assistants discover it organically. This is the single most direct
  "assistants consult us at runtime" wedge. *Accept:* tools callable from a
  standard MCP client; README/docs page section; registry listing submitted.
- [ ] **1.4 CI trust gate (GitHub Action) — M, separate tiny repo.**
  `hvtrust-gate`: given agent slugs/packages in a workflow, fail or warn if
  grade < threshold or a drift flag is present. Pure API consumer — zero
  server cost, permissionless adoption, and every adopting repo embeds
  HVTracker in its CI (asset #2). Marketplace listing. *Accept:* action
  published; demo workflow in its README; hvtracker.net badges page links it.
- [x] **1.5 "Verify this score yourself" — DONE 2026-07-07.** New
  `#verify-yourself` section on the methodology page with a 12-line
  copy-paste verifier snippet, plus a fuller standalone reference verifier
  `scripts/verify_credential.py` (signature, evidence-hash, expiry, and
  delisted-revocation checks; certifi-aware for macOS Pythons; needs only
  `cryptography`). Verified against LIVE prod data (haystack,
  vercel-ai-sdk both verify OK; a tampered score fails both signature and
  evidence-hash). Byte-compatibility with the production signer locked by
  `tests/test_verify_credential_script.py` (7 cases).
- [x] **1.6 Quarterly dataset export — DONE 2026-07-07.**
  `write_dataset_export()` writes `/data/exports/hvtrust-<Y>-Q<n>.json.gz`
  + `.csv` (all public fields incl. flattened runtime capabilities, CC BY
  4.0, embedded suggested citation) every render; the file rolls within its
  quarter and freezes at its end-of-quarter state when renders move to the
  next quarter's filename. Linked from llms.txt and the `/data-api/` page
  (quarter computed at request time so the docs never go stale). Tests:
  `tests/test_dataset_export.py` (quarter labels, JSON/CSV shape,
  None-safety, same-quarter overwrite) + serving/docs assertions in
  test_api.

### Phase 2 — Sharpen the human funnel (~2–3 weeks, ∥ with late Phase 1)

Theme: convert the queries we already rank for; give the one-and-done
visitor exactly one durable hook (the watchlist).

- [ ] **2.1 Internal-linking pass — M.** Target the GSC
  crawled-not-indexed list (owner exports URL-level data from Search
  Console UI). Mesh: agent → category article → compare pairs → capability
  hub → ecosystem pages; related-agents block on agent pages (same
  category, adjacent rank). No new content, just links. *Accept:* every
  agent page gains ≥3 relevant internal links; validate_html green.
- [ ] **2.2 Compare surface v2 — M.** "X vs Y" queries are the best
  performers (genkit-vs-langchain = position 1). Add to compare pages: the
  capability diff (MCP/providers/tool surface side-by-side), coverage
  grades, and a one-line evidence-based verdict sentence derived from
  existing fields (template logic, no LLM). *Accept:* compare pages render
  the new blocks; pairs persist per the #114 seo_state mechanism.
- [ ] **2.3 Badge-adopter audit + trend badge — M.** Audit the 4 adopters'
  current grades post-v4.2 (some likely dropped). Ship a **trend badge**
  variant (grade + 30-day direction arrow) so improving projects have a
  reason to adopt regardless of absolute grade. Refresh the outreach target
  list from the corrected top-30 — but **respect the spam freeze**: only
  contact repos with an existing relationship or inbound signal. *Accept:*
  trend badge SVG live at `/badge/<slug>-trend.svg`; audit results appended
  to `badge-outreach-campaign` memory/doc.
- [ ] **2.4 Watchlist alerts that matter — M.** The bell currently derives
  from `recent_events`. Make the events worth watching: grade flips, drift
  flags raised/cleared, abandonment threshold crossed (no push > N months),
  new listing in a watched category. Uses `derive_agent_events` — extend
  event types, keep the methodology-cutover suppression intact. *Accept:*
  watch an agent, simulate an event in a test render, bell shows exactly one
  meaningful notification.
- [ ] **2.5 Corrections & appeals page — S.** Public, short: how to dispute
  a score/signal, what evidence is required, expected turnaround (solo-run,
  "within a week" honest). Every honest correction strengthens asset #3,
  and this page is the R5 (defamation-risk) mitigation. Link from footer +
  methodology. *Accept:* page live, linked, in sitemap.

### Phase 3 — History as product (~3–4 weeks, after 0.1 backup exists)

Theme: surface the only asset nobody can copy. **All trend features must
segment at METHODOLOGY_VERSION boundaries** (§1.4) — chart within eras,
annotate the cutovers, never smooth across them.

- [ ] **3.1 T3.5 runtime-drift monitoring — L.** Per-agent drift timeline
  from history snapshots (fields locked by #89): capability surface grew/
  shrank, provenance changes, maintainer inactivity onset. Render-time
  computation → agent-page section + `drift` event type feeding 2.4 bell
  alerts. *Accept:* an agent with a synthetic drift in test snapshots shows
  the timeline and emits one event.
- [ ] **3.2 `/trends/` + the "State of Agent Trust" quarterly report — L.**
  Ecosystem-level charts from snapshot history + `graph_summary`: MCP
  adoption %, provider share shifts, grade-distribution migration,
  abandonment rate by category. Then a quarterly deterministic report post
  (same machinery as weekly snapshot posts) — **the citation magnet**:
  journalists and LLMs cite "State of Agent Trust Q3 2026" and every
  citation points here (assets #1+#2). *Accept:* trends page renders from
  ≥2 snapshots with era boundaries marked; Q3 report generates on the
  quarter boundary with every figure traceable to snapshot data (reuse the
  fact-check test pattern from T2.3).
- [ ] **3.3 Public 90-day history API — M.** `/api/v1/agents/<slug>/history`
  serving the last 90 days of public fields per the open-core boundary
  (extended history stays reserved for a future paid layer — do not expose
  the full series). *Accept:* endpoint documented on the API page; window
  enforced by test.

### Phase 4 — Two-sided platform (gated: start only after Phases 1–2 ship
and either traffic doubles or maintainer inbound appears)

- [ ] **4.1 Maintainer claim v2 — L.** Verified GitHub-ownership claim
  (reuse v3.1 OAuth; require proof of repo admin/maintainer, e.g. verified
  org membership or a repo-side marker file), then: respond to drift flags,
  declare runtime fields **with evidence** (declarations without evidence
  display as claims, never affect score). The v3.1 lightweight claim was
  removed for good reasons — do not rebuild that version.
- [ ] **4.2 Incident annotations — M.** Curated, manually-added timeline
  notes on agent pages (CVE, major incident, ownership transfer) with
  sources. Manual and rare by design; no automation until volume demands it.
- [ ] **4.3 A2A / AgentCard interop — M, watch the ecosystem first.** If
  agent-to-agent identity cards standardize (trust-layer plan P4), emit
  HVTrust fields in that format. Only when there's a consumer.

### Standing decisions already made (do not relitigate)

- 2026-07-07 (owner): the three manual-review candidates — LobsterAI,
  Agent Orchestrator, Sandcastle — are **rejected, not listed**; denylisted
  in `discover_agents.py` `REVIEWED_REJECTED` so discovery can't re-propose.
- 2026-07-07 (owner): the publicly fetchable history paths
  (`/output/history/<date>.json`) **stay as they are** — no restriction for
  now; revisit only if/when a paid extended-history tier becomes real.

- Keep ALL grades public including D — transparency IS the product.
- Popularity stays below audit signals in tie-breaking (v4.1 owner call).
- No email digest until in-app alerts prove value.
- Deterministic content generation only — no LLM in the render pipeline.
- Graph stays a JSON render artifact (<50k edges).
- The verdict (verification + methodology + attestation format) is free
  forever; monetize operations/scale/privacy only (`open-core.md`).

### Owner-decision queue (blockers, ask when reached)

1. Backup mechanism for 0.1 (data branch vs object storage).
2. Postgres deletion go-ahead (0.5) after verification.
3. Code license choice before inviting external contributions
   (Apache-2.0 vs AGPL-3.0 — `open-core.md` tradeoffs; currently MIT).
4. Phase 4 gate assessment.
5. Monetization re-check when visa status changes — then and only then:
   API keys, extended history, alert delivery, per `open-core.md` ladder.

---

## 7. Execution protocol for a fresh session

1. Read `/CLAUDE.md` (bootstrap + hard rules), then this file's §0 and the
   current phase in §6. Trust these files; verify only what you change.
2. Pick the top unchecked task in the current phase. One task = one branch
   (`feat/<short-id>`) = one PR off latest `main`.
3. Before "done": `python -m pytest && python fetch_and_build.py
   --render-only && python tests/validate_html.py` — all green — then
   `git checkout -- data/render_state.json og-v2.png`.
4. Never `railway up` or any deploy/infra mutation without an explicit
   owner instruction in the current conversation.
5. After merge: tick the checkbox here (with date + PR#), update CLAUDE.md's
   "Now / next" section, and move anything learned-but-non-obvious into the
   appropriate doc. The docs are the team.
6. If a task turns out to require changing production rank/score semantics:
   STOP, produce an evidence-gate report first (model:
   `docs/t3.1-upset-review-2026-07-02.md`), and get an owner decision.

## 8. Metrics & checkpoints

Track these; they decide phase gates and the quarterly review:

| Metric | Baseline (date) | Direction that means "working" |
|---|---|---|
| GSC clicks / CTR / avg position | 57 / 0.5% / ~17 (2026-06-25) | ↑ / ↑ / ↓ after Phase 2; re-pull monthly |
| W1 retention | 1–2% (2026-06-25) | > 5% would be excellent; don't chase past that |
| Watchlist adds + active bells | ~0 | Any sustained growth after 2.4 |
| API + MCP call volume | unmeasured (fix in 1.2) | Establish baseline, then ↑ |
| Badge adopters | 4 (2026-07-06) | +1/month without spam |
| Listed agents | 319 (2026-07-07) | Slow, rubric-gated growth; quality > count |
| History depth | 35 days (2026-07-07) | +1/day forever; backup verified (0.1) |
| Railway bill | ~$2.28/mo memory line (2026-07-06) | < $10/mo total; checks on the 12th |

**Quarterly review ritual (next: early October 2026):** re-verify §1 numbers,
re-test §2's forecasts F1–F6, tick/replan §6, refresh this file's Status
line. If two consecutive quarters show no growth in machine-surface metrics
(API/MCP/citations), the irreplaceability thesis needs owner-level rethink —
that's the honest kill-criterion for Phase 1's bet.

---

*Document history: created 2026-07-07 from a verified live-state audit
(prod healthz, live API, credential-signature check) + all prior planning
docs (`product-plan-2026-h2.md`, `growth-plan.md`, `open-core.md`,
`trust-layer-execution.md`, `plan-2026-07-06-post-v4.2.md`).*
