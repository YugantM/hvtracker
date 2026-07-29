# New agent candidates — 2026-07-09

`GITHUB_TOKEN=$(gh auth token) python3 discover_agents.py` found 561 repos,
416 novel against the current 347-entry `agents.json`, 381 passing the
script's automated pre-checks. A rubric-based text filter
(`docs/strict-inclusion-rubric.md`) removed 94 obvious out-of-scope repos
(collections, guides, skills, format specs, tools-for-agents), leaving 287
for review; 18 were manually vetted via the GitHub API.

This is a discovery report only. **`agents.json` was not changed** —
discovery proposes, owner decides (and applies via the add-agent runbook).

## The 2026 star-farm caveat (read first)

The `ai-agent` topic space is now heavily star-farmed. The top results by
stars are **not agents**: awesome-lists (`awesome-llm-apps` 117k⭐),
skills libraries (`agent-skills` 76k⭐, `claude-skills`), format specs
(`agents.md`, `design.md`), tools-for-agents (`beads`, `agent-browser`,
memory/context layers), and OpenClaw desktop clients. Many genuine-looking
repos are 2026-created with implausible star counts (e.g. `career-ops`:
59k⭐ three months after creation).

**Why this is safe for HVTracker anyway:** since scoring v4.1, popularity
ranks *below* audit signals and no longer lifts the score. A star-farmed
repo therefore lands at its true (usually low) trust once real signals
fill in — exposing inflated stars is on-brand for a trust registry, not a
risk to it. The filtering below is about the *inclusion rubric* (is it a
real agent?), not about star count.

## Recommended adds (P1 — verified real agents, credible, OSS-licensed)

| Project | Created | ⭐ | License | Why it passes |
| --- | --- | --- | --- | --- |
| [II-Agent](https://github.com/Intelligent-Internet/ii-agent) | 2025-04 | 3.4k | Apache-2.0 | General-purpose open-source AI agent, run/fork/extend, BYOK; first-party execution codebase. |
| [Integuru](https://github.com/Integuru-AI/Integuru) | 2024-10 | 4.6k | AGPL-3.0 | Autonomous agent that traverses a network-request dependency graph to generate runnable integration code — goal-directed, multi-step, tool-using. Oldest/most credible. |
| [DeepAnalyze](https://github.com/ruc-datalab/DeepAnalyze) | 2025-10 | 4.3k | MIT | "Agentic LLM for Autonomous Data Science" from RUC DataLab (real academic lab); deep-research + data tasks locally, no closed-source workflow. |
| [Grok CLI](https://github.com/superagent-ai/grok-cli) | 2025-07 | 3.2k | MIT | Terminal coding agent (org superagent-ai): tool rounds, sub-agents by default, search; published npm `grok-dev`. Community project, not a vendor wrapper. |

All four predate the star-farm era or come from a credible org, carry a
clear OSS license, and their READMEs confirm a first-party agent loop
(checked against implementation intent, not description alone). The
companion JSON has copy-ready `agents.json` entries.

## Manual-review items (P2/P3 — real but need an owner call)

- **[GenericAgent](https://github.com/lsdefine/GenericAgent)** (2026-01,
  13k⭐, MIT, PyPI `genericagent`) — general self-evolving agent with a
  first-party CLI loop, memory, plugins, reflection. Strong on the merits;
  held only because it is 2026-created with an implausibly high star count
  — confirm canonicity (not a renamed clone) before listing.
- **[Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)** (2026-04,
  19k⭐, MIT, PyPI `vibe-trading-ai`) — trading agent from **HKUDS**, the
  lab behind LightRAG (an existing HVTracker badge adopter), with a
  first-party `agent/` module and MCP support. Held because it is
  domain-specific (finance) and very recent.
- **[BettaFish](https://github.com/666ghj/BettaFish)** (2024-07, 42k⭐,
  GPL-2.0) — substantial multi-agent public-opinion-analysis system with
  first-party engines built "from 0, no framework". Age-credible; held
  because it is a domain application rather than a general agent/framework.
- **[Nexent](https://github.com/ModelEngine-Group/nexent)** (2025-04,
  5.6k⭐, MIT) — zero-code platform for generating agents. Held because it
  sits near the no-code-builder boundary — confirm it offers genuine
  agent-framework abstractions, not incidental agent support.

## Notable rejections (with reasons)

- `code-yeongyu/oh-my-openagent` (65k⭐) — no clear OSS license
  (NOASSERTION) **and** a TUI orchestrating *other* coding agents, not a
  first-party agent.
- `the-open-agent/openagent` (5.4k⭐) — 2020 creation date with a modern
  LLM/RAG description = canonicity red flag (likely renamed/repurposed).
- `elder-plinius/T3MP3ST` (4k⭐) — created 2026-07-02, days old with 4k
  stars; extreme star-farm, unassessable.
- `snarktank/ralph` (21k⭐) — stale (no push since 2026-02); viral, not
  maintained.
- `golutra/golutra` — NOASSERTION license.
- `NVIDIA/OpenShell` — runtime/sandbox for agents, no own loop (same class
  excluded on 2026-07-06).
- The bulk of the 287 survivors — skills/tools/templates/format-specs/
  OpenClaw-clients/media-generators — are rubric out-of-scope.

## If the owner approves adds

Follow the add-agent runbook (`deploy_mechanism` memory / CLAUDE.md): edit
`agents.json` only → one branch/PR → three gates → squash-merge →
(owner-instructed) `railway up` clean worktree → `railway restart` to score
the provisional rows. New agents land grade-D with `scorecard_score:null`
until the daily OSSF scan and a later deploy fill in sub-scores.
