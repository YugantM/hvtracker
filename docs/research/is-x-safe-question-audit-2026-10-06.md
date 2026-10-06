# "Is X safe?" question audit

**Date:** 2026-10-06
**Purpose:** Q4 plan workstream E1 (plan: https://claude.ai/artifact/89TFKpJfa8ce92uKowefQk, approved 6 Oct). Map what people searching "is X safe?" want to know against what an HVTracker profile shows them, so the gap decides the shape of E2 (hosted-service facts) and E3 (what a tool can touch).
**Scope:** read-only research. Nothing here changes scores, titles or meta descriptions.

## Summary

1. **Safety searches land on profiles and nowhere else.** From 6 Jul to 3 Oct, queries with safety intent produced 5,892 impressions and 123 clicks, 99.5% of them on `/agents/<slug>/` pages (185 distinct profiles).
2. **Composio is almost all of the clicks.** It took 97 of the 123 (2,679 impressions, position 5.1, CTR 3.6%). Every other page: 3,213 impressions, 26 clicks, a 0.8% CTR, mostly at positions 6–15.
3. **What outranks us answers four things we don't show:** the vulnerability history and which version fixes it; what the tool exposes or can reach by default; who runs the hosted service and what it is certified for; and how to run it safely.
4. **What we show is deep on one question nobody else answers** (who ships the code and whether the release chain is intact), shallow or missing on the four above:
   - The hero verdict is one of three sentences picked by score band. Composio, Ollama and Desktop Commander all read "Promising trust profile, but some evidence still deserves review."
   - Advisories appear only for the latest release of a roster package, and **23 of the top 39 safety pages show no advisory information at all.** That includes Ollama (31 OSV records as a Go module), Open WebUI (316 OSV records on PyPI) and AnythingLLM (25 maintainer advisories).
   - The runtime surface (providers, MCP, plugin surface) sits in a collapsed fold near the bottom, and **we hold no reliable data on shell, file, network or credential access.** `tool_plugin_surface.tool_tags` is set on 291 of 1,346 agent listings, but it records which libraries a project depends on (`database` 146, `browser` 119, `code` 55, `shell` 32, `search` 29, `filesystem` 10). It misses the obvious cases: Desktop Commander, Cline and Codex have no tags.
   - The FAQ answers provenance, Scorecard, licence and signed-commit questions. No safety query in the window asks any of them.
5. **Decisions this audit makes for the plan** (details in the last section):
   - E2 list: keep 6 of the approved 10, and swap the 4 with no measurable demand (n8n, Daytona, Mem0, Browser Use) for Codex, LiveKit Agents, Kilo Code and Freebuff.
   - E3 becomes curated, sourced access facts for the top safety pages, in the same reviewed file as E2, instead of an automatic sitewide line.
   - A new item, E4 (advisory history from OSV), is proposed for owner approval.

## Method

- **Search demand:** Search Console, `query × page`, web, 2026-07-06 to 2026-10-03, query regex `safe|secur|trust|legit|risk|malware|virus|scam|privacy|danger|review|vulnerab|cve|exploit|permission|audit` → 423 rows. A second pull gives all-query impressions for the E2 candidate profiles.
- **What the page shows:** live HTML of `/agents/composio/`, `/agents/ollama/` and `/agents/desktop-commander-mcp/` on 6 Oct; section order from the `h1`–`h3` sequence. The verdict logic is in `agent_review_insights()` (`fetch_and_build.py`).
- **What outranks us:** web searches for "is composio safe", "is ollama safe", "is anythingllm safe" and "is desktop commander mcp safe" on 6 Oct, reading what the top answers cover. That search tool isn't Google's SERP, so this shows what other sites cover, not their exact rank.
- **Advisory data:** the `advisories` field on live `/api/v1/agents`; GitHub's repository security-advisories API (published advisories, capped at 100 per repo); the OSV query API for five packages.

## 1. What people ask

| Modifier in the query | Impressions | Clicks | Distinct queries |
|---|---:|---:|---:|
| "is X safe / secure" | 4,593 | 116 | 207 |
| security / safety (as a noun: "dify security") | 571 | 0 | 64 |
| legit / scam | 251 | 1 | 8 |
| trust / trusted / trustworthy / trust center | 211 | 1 | 43 |
| safe to use / install / download | 141 | 3 | 19 |
| review(s) | 96 | 3 | 28 |
| vulnerability / CVE / exploit | 79 | 0 | 25 |
| privacy, data, malware, virus, audit, risk | 9 | 0 | 7 |

The rows overlap (one query can match two modifiers). Notable single queries: "is composio legit", "is composio trustworthy", "livekit trust center", "can codex be trusted", "data safety" (Headroom), "librechat vulnerabilities", and "cve-2025-53967 figma-developer-mcp command injection".

## 2. Where they land

The top 25 safety-intent profiles. *Maintainer advisories* are the repository's published GitHub security advisories; they are not shown anywhere on our profiles today.

| Profile | Safety impr. | Clicks | Pos. | Product type | Advisory block today | Maintainer advisories (all / last 12 mo) |
|---|---:|---:|---:|---|---|---|
| [`composio`](https://hvtracker.net/agents/composio/) | 2,679 | 97 | 5.1 | Hosted platform + SDKs; brokers auth to third-party apps | latest release checked, none found | 0 / 0 |
| [`codex`](https://hvtracker.net/agents/codex/) | 266 | 0 | 19.6 | Local CLI + OpenAI-hosted service | latest release checked, none found | 1 / 0 |
| [`ollama`](https://hvtracker.net/agents/ollama/) | 228 | 0 | 14.2 | Self-hosted model server | none shown | 0 / 0 (OSV: 31) |
| [`anythingllm`](https://hvtracker.net/agents/anythingllm/) | 201 | 2 | 8.3 | Desktop app / self-hosted server | none shown | 25 / 23 |
| [`opencode`](https://hvtracker.net/agents/opencode/) | 145 | 0 | 11.1 | Local coding agent (CLI) | none shown | 3 / 3 |
| [`livekit-agents`](https://hvtracker.net/agents/livekit-agents/) | 125 | 0 | 22.2 | Framework; LiveKit Cloud hosting | latest release checked, none found | 1 / 1 |
| [`humanlayer`](https://hvtracker.net/agents/humanlayer/) | 102 | 0 | 59.4 | Coding-agent tooling | none shown | 0 / 0 |
| [`desktop-commander-mcp`](https://hvtracker.net/agents/desktop-commander-mcp/) | 100 | 4 | 4.7 | Local MCP server with terminal and file access | none shown | 0 / 0 (OSV: 2 on its npm package) |
| [`freebuff`](https://hvtracker.net/agents/freebuff/) | 95 | 2 | 7.8 | Coding agent (backend to verify) | none shown | 0 / 0 |
| [`cline`](https://hvtracker.net/agents/cline/) | 89 | 0 | 8.7 | Local coding agent (VS Code), optional hosted provider | latest release checked, none found | 3 / 3 |
| [`open-webui`](https://hvtracker.net/agents/open-webui/) | 82 | 1 | 10.1 | Self-hosted web UI / server | none shown | 100+ / 100+ (OSV: 316) |
| [`cherry-studio`](https://hvtracker.net/agents/cherry-studio/) | 74 | 2 | 6.3 | Desktop app | none shown | 4 / 1 |
| [`ai-town`](https://hvtracker.net/agents/ai-town/) | 69 | 1 | 5.1 | Deployable starter kit | none shown | 0 / 0 |
| [`blender-mcp`](https://hvtracker.net/agents/blender-mcp/) | 65 | 1 | 7.6 | Local MCP server controlling Blender | none shown | 0 / 0 |
| [`firecrawl`](https://hvtracker.net/agents/firecrawl/) | 64 | 0 | 8.7 | Hosted API + self-hostable server | latest release checked, none found | 4 / 2 |
| [`headroom`](https://hvtracker.net/agents/headroom/) | 63 | 0 | 6.2 | Local proxy / library | latest release checked, none found | 1 / 1 |
| [`autocve`](https://hvtracker.net/agents/autocve/) | 53 | 0 | 39.0 | CLI (queries are name lookups) | none shown | 0 / 0 |
| [`agent-reach`](https://hvtracker.net/agents/agent-reach/) | 49 | 7 | 2.9 | Local CLI reading social platforms | none shown | 0 / 0 |
| [`figma-context-mcp`](https://hvtracker.net/agents/figma-context-mcp/) | 49 | 0 | 69.5 | Local MCP server (queries are CVE news) | none shown | 1 / 0 |
| [`openshell`](https://hvtracker.net/agents/openshell/) | 45 | 0 | 6.7 | Agent sandbox runtime | latest release checked, none found | 0 / 0 |
| [`ckan-mcp-server`](https://hvtracker.net/agents/ckan-mcp-server/) | 42 | 0 | 9.8 | MCP server | latest release checked, none found | 15 / 15 |
| [`qwen-code`](https://hvtracker.net/agents/qwen-code/) | 42 | 0 | 7.8 | Local CLI; hosted Qwen models | latest release checked, none found | 0 / 0 |
| [`odysseus`](https://hvtracker.net/agents/odysseus/) | 41 | 0 | 10.7 | Self-hosted AI workspace | none shown | 0 / 0 |
| [`ongrid`](https://hvtracker.net/agents/ongrid/) | 40 | 0 | 5.0 | Ops agent with infrastructure access via chat apps | none shown | 0 / 0 |
| [`aider`](https://hvtracker.net/agents/aider/) | 38 | 0 | 6.4 | Local CLI | latest release checked, 2 found | 0 / 0 |

Across the top 39 safety pages: the advisory check ran for 16 and was skipped for 23. 15 of the 39 repositories publish their own security advisories (also AutoGPT 42, LibreChat 29, Dify 21 and Roo Code 11, just below the top 25).

**The questions differ by product type.** The pages split into three groups:

- **Local tools with system access** (Desktop Commander, OpenCode, Cline, Codex CLI, Aider, Blender MCP, Agent Reach, OpenShell): can it run commands or change files without asking, does it phone home, which credentials does it read?
- **Self-hosted servers** (Ollama, Open WebUI, AnythingLLM, LibreChat, Dify, Langflow): which versions had vulnerabilities, and is it safe to expose to a network?
- **Hosted services** (Composio, Firecrawl, LiveKit, Codex cloud, Kilo, Kimi): can I trust the company with my data and tokens, and what is it certified for?

## 3. What the top answers cover (6 Oct)

| Query | What the ranking answers lead with |
|---|---|
| is composio safe | A vendor security profile ("security score 31%, SOC 2 compliant"; unknowns listed for encryption, RBAC and audit logs) and a package scan of `composio-langchain` |
| is ollama safe | Default exposure (the API listens on localhost unless `OLLAMA_HOST` is changed), the "Bleeding Llama" vulnerability of May 2026 (9.1), the CVE count since 2024 and patch speed, "safe if kept updated" |
| is anythingllm safe | Version-by-version vulnerabilities with the fixing release ("use 1.13.0 or later"); data stays on your own infrastructure |
| is desktop commander mcp safe | Its npm advisories by version; the project's own SECURITY.md saying its restrictions are guardrails, not a hardened boundary; "run it in Docker for isolation" |

None of them covers who ships the code, whether releases are signed or attested, or how a score changes over time. That remains ours alone.

## 4. What our profile shows, in order

Composio, top to bottom (Ollama and Desktop Commander have the same structure):

1. **Hero:** name, description, category, licence; "Is Composio safe?" followed by the score-band verdict sentence; chips for Scorecard, Provenance, Signed commits, Last push and Advisories (the Advisories chip is missing when no check ran); score, grade, rank, coverage; an "In detail" paragraph listing the same signals.
2. How Composio could raise its score.
3. Chain of custody: source, review and release, published packages, what you install today (advisories on the latest release), changes, evidence, how to verify it, and "What this score doesn't check", which sends readers to a content scanner.
4. Category comparison; where the score comes from; Quick Trust Read; Rank Trend; Activity & Reach; Analysis.
5. **Common questions:** "Does it publish package provenance? Does it have an OpenSSF Scorecard? Is it maintained? What licence? Are commits signed?"
6. **AI agent surface** (collapsed): MCP support, external services (OpenAI; API keys required), plugin surface. Each item says "Detailed evidence is not shown in the public view."
7. Maintainer box, reputation timeline, badge embed, related agents.

## 5. Gap table

| What the searcher wants | Who asks it most | What we show today | Where it is | Data we hold | Gap |
|---|---|---|---|---|---|
| A direct answer | everyone | One of three score-band sentences | hero | score, grade | **Generic.** It doesn't name the deciding facts |
| Vulnerability history and the safe version | self-hosted servers, local tools | Advisories affecting the latest release of a roster package only | hero chip, custody | OSV for npm/PyPI/crates roster packages | **Missing for 23 of the top 39;** no history anywhere |
| What it can touch (shell, files, network, credentials) | local tools, MCP servers | Providers, API-key marker, MCP and plugin presence | collapsed fold near the bottom | providers, `requires_api_keys`, MCP status, dependency-based `tool_tags` | **No reliable access data** (`tool_tags` reflects libraries used, and misses Desktop Commander, Cline and Codex) |
| Where data goes | hosted services, desktop apps | Providers list | collapsed fold | providers | Partial; nothing on telemetry or the vendor's own cloud |
| Who runs the service, and what it is certified for | hosted services | Nothing | — | homepage URL | **Missing** (this is E2) |
| How to run it safely | self-hosted servers, local tools | "Run a content scanner" | custody footnote | none | Missing |
| The project's own security stance (SECURITY.md, disclosure policy) | all | Indirectly via the Scorecard `Security-Policy` check | custody evidence | Scorecard check result | Shown as a score input, never as its content |
| Who ships it, and is the release chain intact | nobody asks this directly | Chain of custody, in depth | middle of page | all | **Our differentiator.** Keep it, but it shouldn't be the first thing a safety searcher has to read through |

## 6. Decisions for E2 and E3

### E2: hosted-service facts. Revised list of 10

Safety-intent and all-query impressions, 6 Jul – 3 Oct:

| Keep | Safety impr. | All impr. | Why |
|---|---:|---:|---|
| Composio | 2,679 | 4,259 | Most of our safety clicks; "legit" and "trustworthy" queries |
| Cline | 89 | 238 | Company with a hosted provider and an enterprise tier |
| Firecrawl | 64 | 112 | Hosted API |
| Dify | 30 | 100 | Dify Cloud; "dify security" queries |
| E2B | — | 173 | Runs untrusted code on its cloud; position 7.9 |
| Claude Code | — | 133 | Closed-source exemplar (the repo carries no OSS licence); position 6.8 |

| Add | Safety impr. | All impr. | Why |
|---|---:|---:|---|
| Codex | 266 | 637 | "can codex be trusted", "codex security"; CLI plus OpenAI-hosted cloud tasks |
| LiveKit Agents | 125 | 266 | "livekit trust center" asks for exactly the E2 facts |
| Freebuff | 95 | 118 | "The free coding agent": who pays for it, and where the code goes. Verify the hosted backend before including it |
| Kilo Code | 36 | 140 | Company platform and gateway behind an open extension |

| Drop | Safety impr. | All impr. | Why |
|---|---:|---:|---|
| n8n | 0 | 28 | No demand on our page |
| Daytona | 0 | 18 | No demand |
| Mem0 | 0 | 55 | No safety demand |
| Browser Use | 0 | 71 | Position 21.8; no safety demand |

The dropped four can come back in a later batch if the pilot works.

### E3: curated, not automatic

A sitewide "What it can touch" line built from existing data would be empty or misleading on most pages. We don't detect shell, file, network or credential access; `tool_tags` says which libraries a project uses, which is a different thing. E3 becomes a short set of **sourced access facts**, kept in the same reviewed data file as E2 and written only for the top safety pages (the 25 above minus the four with no reachable demand: HumanLayer, AutoCVE and Figma Context MCP at positions 39–70, and AI Town, whose queries are about a game). Each fact quotes the project's own README, docs or SECURITY.md, with a date:

- runs shell commands (with or without confirmation)
- reads or writes files outside its project
- listens on a network port, and the default bind address
- stores or brokers credentials or OAuth tokens
- where prompts and data are sent (vendor cloud, model provider, telemetry)
- the project's stated security boundary ("guardrails, not a sandbox")

Facts render near the top of the profile, above the custody section, only on pages that have them, so other pages keep their sitemap dates. A sitewide template change still needs a `LASTMOD_FP_VERSION` bump and `scripts/lastmod_diff.py` before merging. Facts never change scores.

### E4 (proposed, needs owner approval): advisory history from OSV

The largest single gap is the one in the advisory column. Proposal:

- Show the listing's **OSV advisory history** (count, most recent date, worst severity, link) next to the existing "affects the latest release" check. OSV only, because Phase 7 found GitHub's repo-level `patched_versions` unreliable (Cline showed "unpatched critical" while OSV was clean). So the history line makes **no claim about patch status**; the latest-release check stays the only "affects what you install" signal.
- Extend the check to Go modules (Ollama: 31 OSV records) and fix the roster package-id gaps found here:
  - Desktop Commander has no npm id (`@wonderwhy-er/desktop-commander`, 2 OSV records).
  - Open WebUI lists both an npm and a PyPI id, and neither package links back to the repo, so `package_is_the_listing()` rejects both and no check runs (316 OSV records on PyPI `open-webui`).
  - OpenCode (npm `opencode-ai`) also shows no advisory block; the cause is unconfirmed, likely the same.
- Adding a package id also feeds download counts into the score, so the roster fixes need the usual evidence gate. The history line itself is display-only.

### Verdict sentence and FAQ (for the E2/E3 PR, not separately)

On pages with curated facts, the hero answer leads with the deciding facts instead of the score-band sentence. For example (illustrative wording, not a quote): "No published advisory affects the current release; 31 were published since 2024, the latest in July 2026. It listens on localhost unless you change `OLLAMA_HOST`." Those pages' FAQ asks the questions searchers ask: can it run commands, does my data leave my machine, has it had vulnerabilities, who runs the service. The provenance questions move below. Titles and meta descriptions stay untouched; they change only through a logged CTR batch.

## Measurement for the pilot

- Pilot pages: the 10 E2 profiles plus the E3 pages, once deployed.
- Control: profiles at similar positions with safety impressions but no curated facts.
- Readout at 28 days (plan: mid-December): CTR and engaged-session rate, pilot vs control, per `docs/ctr-tests.md` conventions. A content change can still move CTR through snippet changes, so log the deploy date there.

## Data files

The raw Search Console export and the per-page aggregation stay outside the repo (they contain query strings). Rerun them from the Method section.
