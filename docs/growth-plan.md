# HVTracker Growth Plan — Knowledge Graph + Ecosystem SEO

Execution plan for Claude Code (Opus 4.6 medium / Sonnet 4.6 high — small prompts,
low token budget). Continues the numbering of the original improvement plan
(Phases 0–4 are done through 3.3).

**Strategic goal:** evolve from "trust leaderboard" to "AI ecosystem knowledge
graph." The moat is relationships (project→provider, project→MCP, project→org)
plus historical snapshots — not the scoring formula.

**Key fact that makes this cheap:** the relationship data ALREADY EXISTS.
`data.json` rows carry `external_service_dependencies.providers` (17 distinct
providers; OpenAI=181 projects, Anthropic=130, Postgres=97, Amazon Bedrock=84,
Google Gemini=67, Redis=53...), `mcp_server_support` (49 agents declared/verified),
`has_provenance`, `tool_plugin_surface`, and the org is the first half of the
`repo` slug. Daily full-row snapshots already land in `output/history/*.json`.
Phases 5–7 are pure normalization + page generation. **No new fetching.**

---

## How to execute this plan (read once)

Paste ONE task prompt per fresh session, prefixed with this header:

> Read CLAUDE.md first. Work on repo `YugantM/hvtracker`. One task = one branch
> = one PR; branch from `main` as `growth/<task-id>`. Never hand-edit generated
> output (`agents/`, `ecosystem/`, `use-cases/`, `data/`, `sitemap.xml`,
> `index.html`, `data.json`, `blog/`, `categories/`, `compare/*-vs-*/`,
> `movers/`) — change the generator (`fetch_and_build.py`, `templates/*.j2`)
> and re-render. Finish with all three gates green:
> `python -m pytest` && `python fetch_and_build.py --render-only` &&
> `python tests/validate_html.py`. Commit with a conventional message and push
> the branch. Do not push to `main`.

Per-task prompts below assume that header. They name exact files, functions,
and fields so the model does not need to explore. Do tasks in order inside a
phase; phases 5→6→7 are sequential, 8 and 9 are independent after 5.

---

## Phase 5 — Relationship layer (graph.json)

### Task 5.1 — Provider entity dictionary + graph builder

**Prompt:**

> In `fetch_and_build.py`, add a function `build_graph(rows)` near
> `build_use_case_pages` (line ~2627). Input: the same `rows` list. Output: a
> dict `{"schema_version": 1, "generated_at": ..., "entities": {...}, "edges": [...]}`.
> Entities: `projects` (repo, name, slug, trust_score, rank), `providers`
> (normalized from each row's `external_service_dependencies.providers` list —
> slugify with the repo's existing slug conventions, e.g. "Amazon Bedrock" →
> `amazon-bedrock`), `categories` (from `row["category"]`), `orgs` (from
> `row["repo"].split("/")[0]`). Edges as `{"src": "<repo>", "rel": ..., "dst": ...}`
> with rels: `USES_PROVIDER`, `IN_CATEGORY`, `OWNED_BY`, plus `SUPPORTS_MCP`
> when `row["mcp_server_support"]["status"]` is `declared` or `verified`, and
> `HAS_PROVENANCE` when `row["has_provenance"]` is truthy. Write the result to
> `data/graph.json` in the render step, right where `data.json` is written
> (search for `data.json` in the main render function). Add one pytest in
> `tests/` asserting: graph has >200 project entities, >10 provider entities,
> every edge src exists in entities, and `anthropic` provider has >50
> `USES_PROVIDER` edges. Keep the diff under ~120 lines. No new dependencies,
> no database — this is a render artifact like `data.json`.

→ verify: gates green; `python -c "import json; g=json.load(open('data/graph.json')); print(len(g['edges']))"` prints >700.

### Task 5.2 — Graph summary in daily history snapshots

**Prompt:**

> `output/history/<date>.json` snapshots are written in `fetch_and_build.py`
> (search for `output/history`). Add a top-level key `graph_summary` to each
> new snapshot: `{"providers": {"<slug>": <project_count>, ...}, "mcp_count": N,
> "provenance_count": N, "org_count": N}` computed from the `build_graph`
> output of Task 5.1. Do NOT rewrite existing snapshot files. Extend the
> existing history-related test (or add one) asserting the key exists in a
> freshly written snapshot. Diff under 40 lines.

→ verify: gates green; render a snapshot locally and confirm the key.

---

## Phase 6 — Ecosystem SEO pages (the traffic play)

This is the highest-traffic-impact phase. Target queries: "projects using
Anthropic", "OpenAI-based open source agents", "MCP compatible projects",
"<provider> AI agents". 17 provider pages + 1 MCP page + 1 index, each
listing 50–180 projects = large, unique, data-backed SEO surface that
regenerates every 2h.

### Task 6.1 — Ecosystem page generator + template

**Prompt:**

> Model this EXACTLY on the existing use-case machinery: read
> `build_use_case_pages` in `fetch_and_build.py` (line ~2627), its render loop
> (search `use-cases/`), its sitemap entries (search `use-cases/` near the
> sitemap list), and `templates/use_case.html.j2`. Create the parallel set:
> `build_ecosystem_pages(rows)` generating one page per provider found in
> `external_service_dependencies.providers` (17 currently — derive from data,
> do not hardcode the list), with slug = slugified provider name, title
> "Projects Using <Provider> — Trust-Ranked", description mentioning the count
> and that rankings are evidence-based. Sort member projects by trust_score
> desc; include ALL matching projects (not capped at 16 — these are directory
> pages). Render to `ecosystem/<slug>/index.html` plus an `ecosystem/index.html`
> hub listing all providers with counts, using a new
> `templates/ecosystem.html.j2` copied from `use_case.html.j2` and trimmed
> (drop the radar SVGs; keep header/nav/footer/table). Use
> `/static/site.css?v={{ css_hash }}` like other templates. Add JSON-LD
> `ItemList` (top 25 items, position/url/name) and one `FAQPage` block per
> page ("Which open-source AI projects use <Provider>?" answered with the top
> 5 names + count). Add the pages to the sitemap exactly where use-case pages
> are added. Add `ecosystem/` to the Dockerfile prebuilt output only if other
> generated dirs are listed there (check first — they likely are not, since
> the build renders them). Extend `tests/validate_html.py`'s sampled pages
> with `ecosystem/index.html` and one provider page.

→ verify: gates green; `ls ecosystem/ | wc -l` ≥ 18; `grep -c ItemList ecosystem/anthropic/index.html` ≥ 1.

### Task 6.2 — MCP + no-API-key discovery pages

**Prompt:**

> Extend `build_ecosystem_pages` from Task 6.1 with two non-provider pages
> using the same template and render loop: (1) slug `mcp-compatible`, title
> "MCP-Compatible AI Projects", filter: `row["mcp_server_support"]["status"]`
> in `{"declared","verified"}` (49 projects currently) — show the status and
> confidence columns; (2) slug `no-api-keys-required`, title "AI Agents That
> Run Without API Keys", filter:
> `row["external_service_dependencies"].get("requires_api_keys") is False`.
> Both appear on the `/ecosystem/` hub and in the sitemap automatically if
> 6.1 was built data-driven; if not, fix that instead of special-casing.
> Diff under 80 lines.

→ verify: gates green; both pages exist and list >10 projects each.

### Task 6.3 — Internal linking (agent → ecosystem)

**Prompt:**

> SEO goal: ~200 agent pages should link to the ecosystem hub pages they
> belong to. In `templates/agent.html.j2`, the page already renders provider
> info from `external_service_dependencies` (find that section). Make each
> provider name a link to `/ecosystem/<provider-slug>/`, and the MCP support
> indicator (if status declared/verified) a link to
> `/ecosystem/mcp-compatible/`. Compute the slugs in `fetch_and_build.py`
> where the agent page context is assembled and pass them in — do not slugify
> in Jinja. Also add one "Ecosystem" link to the site nav in
> `template.html` and `templates/agent.html.j2` ONLY (other templates as a
> follow-up, keep this diff small). Re-render regenerates all agent pages —
> that is expected and is the point.

→ verify: gates green; `grep -c '/ecosystem/' agents/haystack/index.html` ≥ 3 (or whichever agent has multiple providers).

### Task 6.4 — llms.txt + per-page meta polish

**Prompt:**

> Two small SEO artifacts. (1) Generate `llms.txt` at the site root from
> `fetch_and_build.py` (next to where `robots.txt` is COPY'd — note robots.txt
> is static, but llms.txt should be generated because it lists current pages):
> markdown per the llms.txt spec — site name, one-line description, then
> sections linking `/methodology`, `/ecosystem/`, `/use-cases/`,
> `/categories/...` (top-level only, not all 236 agent pages), and
> `/data-api`. Serve it in `app.py` the same way `robots.txt` is served (find
> that route/mount and mirror it). (2) On ecosystem pages from 6.1, ensure
> `<title>` ≤ 60 chars and meta description 140–160 chars mentioning the
> project count and "open source". Add llms.txt presence to the artifact
> assertions in `.github/workflows/ci.yml` build-smoke job (`test -s llms.txt`).

→ verify: gates green; `curl localhost:8000/llms.txt` returns markdown (run uvicorn locally).

---

## Phase 7 — Historical surface (freshness signals)

### Task 7.1 — Snapshot retention guarantee

**Prompt:**

> `output/history/` currently has ~18 daily snapshots and is the irreplaceable
> dataset — verify nothing ever prunes it. Read `cron_runner.sh` and the
> history-writing code in `fetch_and_build.py`; if any rotation/pruning exists,
> remove it and report; if none exists, just add a pytest asserting the
> history writer never deletes (e.g. write two fake snapshots to a tmp dir,
> run the writer, both survive). Also add a `# DO NOT PRUNE` comment at the
> write site explaining snapshots are an append-only dataset. Diff under 40
> lines. Report in the PR how many days of history exist and the per-day file
> size, so the user can project storage growth.

→ verify: gates green; new test passes.

### Task 7.2 — Weekly changes page + RSS feed

**Prompt:**

> Build `/changes/` — a generated page diffing the newest snapshot in
> `output/history/` against the one ~7 days older (fall back to oldest if <7
> days exist). Sections: newly listed projects, trust-score moves ≥3 points
> (up and down separately), provenance gained, MCP support gained (needs
> Task 5.2's `graph_summary` or per-row fields — read both snapshots' agent
> rows and compare directly, that's simpler). Reuse the visual style of
> `templates/movers.html.j2` (read it first) as a new `templates/changes.html.j2`.
> Also emit `changes/feed.xml` — RSS 2.0, one item per section heading with
> the date, absolute URLs to hvtracker.net. Link the feed via
> `<link rel="alternate" type="application/rss+xml">` in the changes page head
> and add `/changes/` to the sitemap and the homepage nav in `template.html`.
> Add the page to `tests/validate_html.py` samples.

→ verify: gates green; `python -c "import xml.etree.ElementTree as ET; ET.parse('changes/feed.xml')"` succeeds.

---

## Phase 8 — Org entities (cheap — no API needed)

### Task 8.1 — Organization pages

**Prompt:**

> The org is `row["repo"].split("/")[0]`. Generate `/org/<owner>/` pages for
> every org with ≥2 listed projects (use the `OWNED_BY` edges from
> `data/graph.json` / `build_graph` of Task 5.1). Same machinery as Task 6.1
> (read `build_ecosystem_pages` and its template). Page: org name, project
> count, combined stars, table of their projects with trust scores. Index at
> `/org/` listing qualifying orgs by total trust. Sitemap entries like the
> ecosystem ones. On agent pages (`templates/agent.html.j2`), link the owner
> half of the repo slug to its org page when the org page exists (pass an
> `org_slug_or_none` from the build context). Skip orgs with 1 project — no
> thin pages.

→ verify: gates green; orgs with ≥2 projects each have a page; no single-project org pages exist.

### Task 8.2 — [OPTIONAL] Maintainer-level data

Requires new GitHub API fetching (contributors endpoint), rate-limit budget,
and caching design. Do NOT start without explicit user opt-in and a stated
API budget. If opted in: fetch top-3 contributors per repo in the existing
batch fetch path (read how `fetch_and_build.py --batch` does GitHub calls and
caches them), store in `data/signals/maintainers.json`, add
`MAINTAINED_BY` edges in `build_graph`. No pages yet — data first.

---

## Phase 9 — Open-core API surface

### Task 9.1 — Read-only graph + agents API

**Prompt:**

> Add two GET endpoints to `app.py` following the existing static-file-serving
> pattern (find how `data.json` is served from `OUTPUT_DIR`):
> `/api/v1/graph` → serves `data/graph.json`; `/api/v1/agents` → serves
> `data.json`. Both: `Cache-Control: public, max-age=900`,
> `Access-Control-Allow-Origin: *`, JSON content type. Document both on the
> existing `/data-api` page (find where its HTML is built in `app.py` — it is
> an inline string) with one curl example each. Add pytest cases in the style
> of `tests/test_api.py`: 200, correct content-type, CORS header present.
> Note in the PR: auth/quotas for a paid tier are intentionally out of scope.

→ verify: gates green; `curl -s localhost:8000/api/v1/graph | python -m json.tool | head` works.

### Task 9.2 — [USER-SIDE, no code] Paid-tier checklist

Not promptable — product decisions. When ready, define: alert delivery
channel (email infra), Stripe vs Railway-native billing, API key issuance,
and which history depth stays free. Revisit after Phases 5–7 ship and
traffic data exists.

---

## Execution order and why

| Order | Task | Impact | Cost |
|------:|------|--------|------|
| 1 | 5.1 graph.json | Foundation for everything below | Small |
| 2 | 6.1 provider pages | Biggest SEO surface (17 hub pages) | Medium |
| 3 | 6.2 MCP/no-key pages | 2 more high-intent pages | Tiny |
| 4 | 6.3 internal linking | Makes Google rank the hub pages | Small |
| 5 | 6.4 llms.txt + meta | AI-crawler discoverability | Tiny |
| 6 | 5.2 snapshot graph summary | Starts edge history NOW (can't backfill) | Tiny |
| 7 | 7.1 retention guarantee | Protects the moat dataset | Tiny |
| 8 | 7.2 changes page + RSS | Freshness signal + repeat visitors | Medium |
| 9 | 8.1 org pages | More graph surface, zero new data | Small |
| 10 | 9.1 public API | Developer adoption channel | Small |
| — | 8.2, 9.2 | Only on explicit request | — |

Note: 5.2 ranks above its phase position because historical edge data cannot
be recreated later — every day it isn't running is data lost forever.

## What this plan deliberately does NOT do

- No graph database, no Neo4j, no new infra — `graph.json` is a render
  artifact like `data.json`. Revisit only if edge count exceeds ~50k.
- No scoring-formula changes (per the original plan's exclusion).
- No changes to the Postgres schema — relationships are derived, not stored;
  the source of truth remains the fetch pipeline.
- No speculative "Models" or "Packages" entities — add entity types only when
  a page or API consumer needs them.
- No paid-tier code until traffic justifies it (9.2 is a checklist).
