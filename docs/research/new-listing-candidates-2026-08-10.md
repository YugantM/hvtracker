# New listing candidates — 2026-08-10

**58 rows added to `agents.json` (1,227 → 1,285).** The row set is in the
companion [`new-listing-candidates-2026-08-10.json`](new-listing-candidates-2026-08-10.json),
checked for repo and display-name collisions against every existing row (the
name-collision hazard in `6f99eabf` — one real collision found and renamed).

Every row was README-vetted, not description-vetted, and every package
identifier was verified against the publishing registry before being wired.

Two sweeps, four days after the 2026-08-06 batch (`635557e5`, `d4556d88`, `6f99eabf`):

| Sweep | Method | Result |
| --- | --- | --- |
| Agents | `discover_agents.py` | 819 found → 499 novel → 453 pass pre-checks |
| MCP registry delta | `scripts/mcp_registry_pull.py --since 2026-08-06` (new) | 1,665 servers → 364 never-seen repos → 254 pass the rubric → **18 at ≥10 stars** |

---

## The headline: the official registry is not the MCP ecosystem

The 2026-08-06 ingest sourced all 682 MCP rows from `registry.modelcontextprotocol.io`.
Cross-checking that registry against what GitHub search returns for MCP servers
at ≥500 stars:

| Stars | Repos GitHub surfaces | Present in the official registry |
| --- | ---: | ---: |
| 10k+ | 5 | **0** |
| 5k–10k | 10 | **0** |
| 2k–5k | 42 | 4 |
| 1k–2k | 23 | 2 |
| 500–1k | 20 | 1 |
| **Total** | **100** | **7** |

**93 of the 100 most-starred MCP servers are absent from the official registry,
and none of them are on the board.** Meanwhile the registry population we did
ingest has a median of 1 star (`6f99eabf`). The registry verifies *identity*, not
adoption, and publishing to it is opt-in — so it systematically under-represents
exactly the servers users actually search for.

This is also a publishable finding in its own right, and it is reproducible by
anyone from two public sources.

---

## Recommended adds

### A. Agents and agent infrastructure (17)

README-vetted, not description-vetted — the standard set in `635557e5`.

| Project | ⭐ | Licence | Last push | Category | Why it passes |
| --- | ---: | --- | --- | --- | --- |
| [Obscura](https://github.com/h4ckf0r0day/obscura) | 21,114 | Apache-2.0 | today | Browser & Computer Use | Rust headless browser engine built for agent automation; 46 contributors, 1.5k forks. Precedent: Steel Browser, BrowserOS. |
| [Camofox Browser](https://github.com/jo-inc/camofox-browser) | 8,479 | MIT | 6d | Browser & Computer Use | Anti-detection browser server for agents — accessibility snapshots, stable element refs, session isolation. |
| [Peekaboo](https://github.com/openclaw/Peekaboo) | 4,978 | MIT | today | Browser & Computer Use | macOS CLI + MCP server giving agents screen capture and UI control. |
| [agent-device](https://github.com/callstack/agent-device) | 4,040 | MIT | today | Browser & Computer Use | Device control (iOS/Android/HarmonyOS/TV/desktop) for coding agents; inspect-act-verify loop. Precedent: arbigent. |
| [bb-browser](https://github.com/epiral/bb-browser) | 6,038 | MIT | 73d | Browser & Computer Use | CLI + MCP server driving the user's real Chrome; 103 commands across 36 platforms. |
| [Argent](https://github.com/software-mansion/argent) | 1,938 | Apache-2.0 | today | Browser & Computer Use | Agentic toolkit for simulators, devices, TVs and Electron apps. **Resolves an Aug-6 HELD item.** |
| [Browser4](https://github.com/platonai/Browser4) | 1,098 | Apache-2.0 | today | Browser & Computer Use | AI-native browser engine for autonomous agents; continuous commit history predating 2025 (verified). |
| [Crabtalk](https://github.com/crabtalk/crabtalk) | 717 | MIT | today | Agent Frameworks | Agent daemon with its own runtime: built-in tools, task delegation, memory, MCP client, skills. |
| [Orkas](https://github.com/Orkas-AI/Orkas) | 1,129 | MIT | 12d | Multi-Agent Systems | Commander coordinates specialist agents; explicitly not a CLI wrapper — model calls go straight to the provider. |
| [WorldSeed](https://github.com/AIScientists-Dev/WorldSeed) | 807 | MIT | 94d | Multi-Agent Systems | Multi-agent world engine; agents run goal-directed work (autoresearch: 100 hypotheses, 86 experiments). Weakest of the three — 94 days stale. |
| [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) | 4,061 | MIT | 1d | Memory & Knowledge | MCP server + CLI indexing code into a graph for agent context. |
| [Code-Graph-RAG](https://github.com/vitali87/code-graph-rag) | 3,410 | MIT | today | Memory & Knowledge | Tree-sitter → Memgraph knowledge graph with agent tools for query and edit. Precedent: GraphRAG, LightRAG. |
| [Pond](https://github.com/tenequm/pond) | 35 | Apache-2.0 | 2d | Memory & Knowledge | Lossless agent-session storage, searchable over MCP. Low stars, but above the ≥10 floor used on 08-06. |
| [Titen](https://github.com/RamaAditya49/titen) | 10 | Apache-2.0 | today | Memory & Knowledge | Agent memory MCP server, drop-in for `@modelcontextprotocol/server-memory`. At the floor. |
| [Fence](https://github.com/fencesandbox/fence) | 895 | Apache-2.0 | 1d | Sandboxes & Runtimes | Network/filesystem sandbox and permission manager for CLI agents. Precedent: Container Use, OpenSandbox. |
| [Tura](https://github.com/Tura-AI/tura) | 549 | AGPL-3.0 | today | Coding Agents | Its own agent runtime harness, benchmarked as a peer to Codex CLI — replaces the CLI rather than wrapping it. |
| [Whale](https://github.com/usewhale/Whale) | 974 | MIT | today | Coding Agents | Terminal-first coding agent. |

### B. MCP servers — official-registry delta (7)

New to the registry since 08-06, dedicated servers, ≥10 stars, package
identifiers wired from registry metadata.

| Server | ⭐ | Pkg | Note |
| --- | ---: | --- | --- |
| [claude-prompts-mcp](https://github.com/minipuft/claude-prompts-mcp) | 185 | npm | Serves prompt templates and workflow chains — a server, not a prompt collection. |
| [zotero-mcp](https://github.com/kujenga/zotero-mcp) | 160 | PyPI | ⚠️ Display name collides with the listed `54yyyu/zotero-mcp`; proposed as "Zotero MCP (kujenga)". |
| [mcp-open-library](https://github.com/8enSmith/mcp-open-library) | 88 | npm | |
| [icloud-mcp](https://github.com/MrGo2/icloud-mcp) | 26 | npm | |
| [keenetic-mcp](https://github.com/salatmaster/keenetic-mcp) | 16 | npm | |
| [zigbee2mqtt-mcp](https://github.com/alexpfau/zigbee2mqtt-mcp) | 15 | npm | |
| [polymarket-agent-mcp](https://github.com/demwick/polymarket-agent-mcp) | 14 | npm | |

### C. Registry-invisible MCP servers and clients (34)

The addressable set is ~55 repos; this is the first wave, ordered by adoption.
All are licensed, unlisted, and absent from both registry pulls. Full list in the
companion JSON. Notable:

- **[MCP Java SDK](https://github.com/modelcontextprotocol/java-sdk)** (3,648⭐, official) —
  the roster already lists the C#, Python, TypeScript and Go SDKs. This is a plain hole.
- **[Xiaohongshu MCP](https://github.com/xpzouying/xiaohongshu-mcp)** (15,178⭐) — the
  single most-starred MCP server found anywhere in this sweep.
- **[ToolHive](https://github.com/stacklok/toolhive)** (1,998⭐) — MCP gateway class,
  which the owner ruled open in `d4556d88`.
- Long tail of dedicated servers with real adoption: TalkToFigma (6,961), MCP Obsidian
  (4,288), Spec Workflow (4,286), Excel (4,099), LinkedIn (3,071), shadcn-ui (2,927),
  Markdownify (2,908), Excalidraw (2,277), iOS Simulator (2,128), JADX (742),
  DaVinci Resolve (2,066), MCP Unity (1,862), MCP Brasil (1,714), Stealth Browser
  (1,588), MCP Language Server (1,575), Apple Docs (1,355), MySQL (1,353), CVE
  (1,112), Notion (919), NixOS (784).

**Held out of this wave, worth a second look:** `tadata-org/fastapi_mcp`
(11,977⭐) and `hangwin/mcp-chrome` (12,280⭐) are both well inside the rubric's
365-day activity floor but have not shipped in 259 and 216 days respectively.
They are two of the three most-adopted MCP projects found in the entire sweep, so
excluding them costs real coverage; including them means listing two projects
that may be drifting. Left out here so the decision is explicit rather than
buried in a 58-row batch.

---

## Package identifiers: verified, never guessed

35 of the 58 rows carry an npm/PyPI/crates.io identifier. Each one was accepted
only when the package's **own registry metadata declares the same GitHub repo**
(`repository`, `homepage`, `bugs`, `project_urls`). Nothing was inferred from a
name match.

This is not pedantry. `detect_package_provenance_drift` in `fetch_and_build.py`
compares a row's package source against its tracked repo and raises a drift
warning when they disagree — so a guessed identifier does not fail quietly, it
**publishes a false supply-chain accusation against someone else's project**,
the same false-positive class as #96–#99.

The first draft of this batch guessed four identifiers from repo names. Three
were wrong. Checking every candidate found six package names that belong to an
unrelated project:

| Row | Obvious package name | Actually belongs to |
| --- | --- | --- |
| `haris-musa/excel-mcp-server` | PyPI `excel-mcp-server` | `zavora-ai/excel-mcp-server` |
| `wshobson/maverick-mcp` | PyPI `maverick-mcp` | `airlock-labs/maverick-mcp` |
| `Pimzino/spec-workflow-mcp` | PyPI `spec-workflow-mcp` | `kingkongshot/specs-workflow-mcp` |
| `jo-inc/camofox-browser` | npm `camofox-browser` | `redf0x1/camofox-browser` (real one is `@askjo/camofox-browser`) |
| `xpzouying/xiaohongshu-mcp` | npm `xiaohongshu-mcp` | `not/xiaohongshu-mcp` |
| `fencesandbox/fence` | npm `fence` | `bhickey/fence` |

The 23 rows without an identifier keep none. They score on GitHub signals alone
and land at a lower coverage grade — which is honest, where a guess would not be.

**Dropped after README and repo review** (2 of the 60 first drafted):

- `alexander-zuev/supabase-mcp-server` (830⭐) — its README states the author no
  longer maintains it and directs users to Supabase's official server. Fails
  "active enough to justify active tracking".
- `zinja-coder/jadx-ai-mcp` (2,625⭐) — 29 MB of 100% Java: it carries the whole
  JADX decompiler, so its score would describe JADX rather than the MCP plugin.
  That is the parent-project class `6f99eabf` excluded (netdata, puter,
  oh-my-posh). Its companion `zinja-coder/jadx-mcp-server` (742⭐, 1.9 MB Python)
  **is** the dedicated server and is listed instead — the higher star count was
  the wrong row.

---

## Rejections — now recorded in `discover_agents.py`

Each is a repeat-surfacing candidate, so each is written into `REVIEWED_REJECTED`
with its reason. The next sweep will not re-propose them.

| Project | ⭐ | Why |
| --- | ---: | --- |
| [emdash](https://github.com/generalaction/emdash) | 5,381 | Desktop app running Claude Code/Codex/OpenCode in git worktrees — the #180 supervisory-harness class, same as superset, cmux, vibe-kanban. |
| [sv-number/mcp-server](https://github.com/sv-number/mcp-server) | 492 | **Adoption signal looks inorganic**: created 3 days ago, 492 stars, but 0 forks, 0 watchers, 0 issues, 1 contributor, 71 KB of code. |
| [keon/browser-control](https://github.com/keon/browser-control) | 3,127 | **Inherited stars**: repo created 2016-12-21 with *zero commits before 2025*. The 3,127 stars and 209 forks belong to the repo's previous life, not this Rust CLI. |
| [firerpa/lamda](https://github.com/firerpa/lamda) | 8,128 | Android automation/reverse-engineering framework (frida, mitmproxy, ADB). Agent support is incidental. |
| [mycoder](https://github.com/bhouston/mycoder) | 566 | Genuine coding agent with sub-agents and its own tool system, but 214 days since last push — fails "active enough to justify active tracking". |
| [MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline) | 2,466 | Self-declared fork of `666ghj/MiroFish`. **The upstream (70,842⭐, AGPL-3.0, active, unlisted) is the canonical candidate and is worth its own review** — GitHub search never surfaced it. |
| [sandboxd](https://github.com/tastyeffectco/sandboxd) | 887 | Aug-6 HELD item. Self-hosted AI app builder whose coding agent does the work; collides with the rubric's "general UI app builders" exclusion. |

## Borderline — owner call

- [dvalincode](https://github.com/arthurpanhku/dvalincode) (111⭐) — markets as an
  "AI coding agent" but the core is a deterministic, model-free security scanner
  that also ships an MCP server. Security & Guardrails if listed.
- [REA](https://github.com/morluto/rea) (170⭐) — agent-driven reverse engineering
  with its own investigation model and evidence records; positioned as tooling
  *for* your agent rather than as an agent.
- [SimWorld](https://github.com/SimWorld-AI/SimWorld) (749⭐) — UE-based simulator
  for evaluating agents. An environment, not an agent.

## Process gaps found

1. **Aug-6 rejections were never persisted** — *fixed here.* That batch reviewed
   269 candidates and added 41; the ~228 declines went only into the commit
   message, so today's sweep re-proposed them while `REVIEWED_REJECTED` still
   held just 7 entries, all from July. This batch's 7 declines are now recorded
   there. The Aug-6 declines remain unrecorded and will surface again — worth a
   backfill pass from that commit message.
2. **12 of the 13 Aug-6 HELD items are still unresolved.** Argent is resolved
   above (recommend add); `nitrostack`, `open-reverselab` and `py-xiaozhi`
   resurfaced again today.
3. **T0 had no script.** `mcp_sweep` → `mcp_triage` → `mcp_ingest` all start from
   a registry CSV that was produced ad hoc on 08-06. Added
   `scripts/mcp_registry_pull.py`; its `--since` delta mode pulled 4 days of
   registry growth in **16 seconds** versus ~33 minutes for a full pull, which
   makes the documented monthly re-pull cheap enough to run weekly.

---

## Wave 2 — 2026-08-10, the held-back candidates (21 rows, board 1,285 → 1,306)

Owner call: add the remaining new agents. This clears everything wave 1 held
back **as a legitimate candidate**, README-vetted and package-verified to the
same standard.

| Category | Rows | Notable |
| --- | ---: | --- |
| MCP Servers | 8 | Chrome MCP Server (12,280⭐), Obsidian Local REST API (2,775), DevDocs (2,098), webclaw (2,131) |
| Protocols & Tool Integration | 7 | FastAPI-MCP (11,977⭐), NitroStack (2,528), Jarvis Registry (2,881), MCP Hub + MCP Hub for Neovim |
| Multi-Agent Systems | 1 | **MiroFish (70,842⭐)** — the largest project found in either sweep |
| Security & Guardrails | 2 | DvalinCode, REA — the two wave-1 borderlines |
| Research & Data | 1 | Wisp Science |
| Observability & Evaluation | 1 | SimWorld — an agent evaluation environment |
| Voice & Conversational | 1 | py-xiaozhi |

Resolves four of the 13 candidates `635557e5` held for an owner call
(nitrostack, py-xiaozhi, and the two borderlines), and lists the MiroFish
upstream whose absence was the stated reason for rejecting its fork.

The two staleness holds are in: `hangwin/mcp-chrome` (216 days) and
`tadata-org/fastapi_mcp` (259 days). Both are well inside the 365-day floor and
among the three most-adopted MCP projects in the sweep; their freshness scores
will reflect the gap honestly.

8 of 21 carry a verified package identifier. One deliberate omission:
`0xMassi/webclaw` publishes `create-webclaw`, which verifies to the right repo
but is a *project scaffolder* — its download count would misrepresent the
project's adoption, so the row carries no identifier rather than a misleading
number.

### Still excluded, and why

- **The 7 in `REVIEWED_REJECTED`** — star-farming (`sv-number/mcp-server`),
  inherited stars (`keon/browser-control`), the supervisory-harness class
  (`emdash`), incidental agent support (`firerpa/lamda`), 214-day dormancy
  (`mycoder`), a fork whose upstream is now listed (`MiroFish-Offline`), and an
  app builder (`sandboxd`).
- **Maintainer-declared EOL** — `alexander-zuev/supabase-mcp-server`.
- **Parent projects whose MCP support is incidental** — `jscpd` (copy/paste
  detector), `opensumi/core` (IDE framework), `Vexa` (transcription API),
  `agentset` (RAG platform), `GoNavi` (database client),
  `zinja-coder/jadx-ai-mcp` (29 MB JADX fork).
- **Two held for a further call** — `repoprompt/repoprompt-ce` (orchestrates
  external CLI agents; may be #180 class) and `LING71671/open-reverselab` (a
  183-article knowledge base with MCP tools attached; the content is the bulk).
- **~86 agent-stream candidates that pass the automated pre-checks and fail the
  rubric** — Apache Doris, a streaming music player, a PHP testing framework,
  tutorial repos, web scrapers. These are what the rubric exists to exclude;
  listing them would change what the registry means.
