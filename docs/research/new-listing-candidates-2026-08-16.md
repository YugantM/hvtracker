# New listings — 2026-08-16 (board 1,454 → 1,490)

36 rows: 25 agents/MCP + 11 skills. Same standard as the 08-10 batch — README
read, repo and display name checked against every existing row, package
identifier accepted only on a declared-repo match.

## The finding: a missing plural hid the biggest launch in the ecosystem

`deepseek-ai/deepseek-harness` — 130k stars, MIT, first-party DeepSeek, three
days old — was invisible to **every** sweep we run.

Its topics are `ai-agents`, `cordis`, `dsh`, `dsh-plugin`. Every sweep searched
`topic:ai-agent`, singular. GitHub topics are exact strings, so the plural never
matched. Its description — "DeepSeek Harness: Everything is a Plugin." — matches
none of the keyword queries either, because a harness announcement does not need
to say "AI agent".

Probing 20 adjacent topics, **all 20 were missing from the sweeps**, and between
them they reach **536 novel repos** the pipeline could not see:

| topic | novel repos | topic | novel repos |
| --- | ---: | --- | ---: |
| `claude-code` | 68 | `mcp-client` | 39 |
| `autonomous-agents` | 60 | `harness` | 36 |
| `multi-agent-systems` | 57 | `agent-memory` | 35 |
| `skill` | 54 | `agent-orchestration` | 31 |
| `coding-agents` | 50 | `dsh` / `dsh-plugin` | 22 / 41 |
| `mcp` | 50 | `llm-agents` | 40 |
| `ai-agents` | 48 | `agent-harness` | 15 |

Fixing the vocabulary took the agent sweep from 828 found / 364 candidates to
**1,255 found / 697 candidates**. The rule now recorded in `discover_agents.py`:
add the plural whenever you add a singular, and expect a first-party launch to
carry its own vendor tag (`dsh`) before it adopts the generic ones.

## Two new pipeline pieces

- **`discover_recent.py`** — the sweeps sort by stars, which answers "what is
  big" and structurally cannot answer "what is new": a repo published last week
  competes on a cumulative metric against four-year-old projects. This one
  searches `created:>DATE` and ranks by **stars per day**. deepseek-harness
  scores 38,946/day. The same number flags inorganic growth — it independently
  re-derives the `sv-number/mcp-server` rejection shape (adoption with no forks,
  issues or watchers behind it).
- **`scripts/verify_package_identifiers.py`** — the 08-10 verifier, promoted out
  of a scratchpad that did not survive the week. It exists because a guessed
  identifier does not fail quietly: `detect_package_provenance_drift` turns it
  into a published false supply-chain accusation against a third party.

## What the verifier caught this time

**npm `deepseek-harness` is squatted** by an unrelated account
(`henryz838978/deepseek-harness`). The official package is `@deepseek-ai/dsh`.
Wiring the obvious name onto the headline row would have attached a stranger's
package to DeepSeek's harness and fired a drift warning at them.

It only surfaced after fixing a second gap: the verifier did not parse `npx`,
which is *the* install idiom for Node CLIs and MCP servers. That one omission
hid the official package of a 130k-star project.

18 of 36 rows carry a verified identifier; 18 carry none rather than a guess.

## The batch

**Agents (11)** — DeepSeek Harness (130,279⭐, Coding Agents), Honcho (6,671,
Memory), Ouroboros (5,466, Coding Agents), OpenScience (3,246, Research), Kiro
Crew (2,932, Coding Agents), Qwen Audio Agent (2,155, Voice), IWE (1,513,
Memory), SandBase Harness (600, Frameworks), Rakazo (529, Multi-Agent), HOL
Guard (437, Security), Hexis (68, Protocols).

**MCP servers (14)** — from the registry delta since 08-10: 2,526 servers → 921
repos new to us → 683 pass the rubric → 37 at ≥10 stars. Microsoft 365 (913),
Upstash, SAS, After Effects, Starwind UI, SageMath, MCP Hangar, Agent Memory,
Bagel, RU Marketplace, Transcriptor, Arr, Loomle, Webhook.

**Skills (11)** — a DeepSeek Harness plugin ecosystem that did not exist a week
ago: DSH Web UI (3,403), DSH Better Sidebar (1,622), DSH TUI (1,535), DSH Market,
DSH Vision Toolkit, Agent Vision Toolkit, Working Activity — plus
**QwenLM/Qwen-MM-Plugins** (2,616, first-party Qwen, installs into Claude Code,
Codex, OpenClaw, Gemini CLI, DSH, pi), SimpleEnglish, jakubkrehel/skills,
anti-slop.

## Excluded

- **#180 supervisory-harness class** — `anywhere-labs/deepseek-harness-desktop`
  (8,794⭐; Electron wrapper that runs the official harness unchanged, the
  `aionui` precedent) and `makecindy/cindy` (2,088; "the first supported
  harnesses are Claude Code and Codex", native harness not yet built).
- **Lists** — `awesome-dsh-plugin` (4,974), `awesome-deepseek-harness`,
  `awesome-dsh-plugins`.
- **No detectable licence** — `dsh-anchored-standard` (3,000), `zhuzhiliao`.
- **Out of scope** — `genoffice` (office suite), `trycompai/crm`, `img2threejs`.
- **Held for an owner call** — `yc-software/qm` (13,689; "pick your own harness
  and model" reads as delegation, but it ships substantial scoped-workspace,
  memory and permission logic of its own).

### One that needs a policy decision, not a rubric decision

`guillaumemeyer/watermarks-remover` (11,079⭐, 2,150 stars/day, MIT) strips
multi-vendor AI provenance marks — the C2PA-style signals that say a thing was
machine-generated. It is a legitimate, popular open-source project and it would
pass the rubric on its own terms. It is also, specifically, a tool for removing
provenance, on a registry whose product is provenance. Left out pending an owner
ruling rather than decided quietly in either direction.
