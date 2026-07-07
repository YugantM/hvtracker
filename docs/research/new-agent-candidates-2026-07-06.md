# New agent candidates — 2026-07-06

`python3 discover_agents.py` found 558 repositories, of which 424 were not
literal repository matches in `agents.json`; 389 passed the script's automated
pre-checks. Manual review applied `docs/strict-inclusion-rubric.md` to repository
purpose, license, activity, runnable distribution, first-party implementation,
and the agent/framework tests.

This is a discovery report only. `agents.json` was not changed.

## Recommended adds

| Priority | Project | Why it passes |
| --- | --- | --- |
| P1 | [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) | Runnable coding agent with a first-party iterative loop, shell actions, state handling, prompts, and agent tests. |
| P1 | [Mistral Vibe](https://github.com/mistralai/mistral-vibe) | Tested CLI agent loop with task breakdown, code/shell/version-control tools, and subagent delegation. |
| P1 | [CowAgent](https://github.com/zhayujie/CowAgent) | First-party planning, tool execution, memory, knowledge, and self-evolution code; no longer merely a chat integration. |
| P1 | [oh-my-pi](https://github.com/can1357/oh-my-pi) | Substantial coding-agent harness with persistent execution, code and browser tools, memory, and isolated subagents. |
| P1 | [Solace Agent Mesh](https://github.com/SolaceLabs/solace-agent-mesh) | Agent-specific framework with an orchestrator, peer delegation, tools/plugins, lifecycle configuration, and multi-step workflows. |

The companion JSON contains copy-ready `agents.json` objects. They deliberately
use only verified package identifiers and the registry's existing
`listing_status`/`tracking_mode` conventions.

## Manual-review items

> **RESOLVED 2026-07-07 (owner): all three rejected — do not list.** None of
> them were ever on the leaderboard; the decision is recorded mechanically in
> `discover_agents.py` `REVIEWED_REJECTED` so discovery cannot re-propose
> them. (The five recommended adds shipped in PR #119 the same day.)

- [LobsterAI](https://github.com/netease-youdao/LobsterAI) performs multi-step
  desktop work and has substantial local session, memory, permission, skill,
  and workflow code. Its README explicitly identifies OpenClaw as the execution
  runtime. Confirm the remaining first-party orchestration clears the rubric's
  thin-wrapper exclusion before listing it separately from OpenClaw.
- [Agent Orchestrator](https://github.com/AgentWrapper/agent-orchestrator) has
  substantial agent adapters, isolated workspace management, lifecycle state,
  and automatic CI/review/conflict feedback loops. External coding agents do
  the actual coding, so confirm its automated loop represents goal-directed
  orchestration rather than only agent process management.
- [Sandcastle](https://github.com/mattpocock/sandcastle) implements iterative
  sandbox execution, lifecycle hooks, completion signals, persistent
  workspaces, and packaged agent workflows. It delegates model interaction to
  coding-agent CLIs and intentionally avoids task-management abstractions, so
  its classification as an agent framework needs an owner judgment.

## Duplicates and repository moves

These appeared novel only because `discover_agents.py` compares repository
strings. GitHub resolves each existing registry URL to the candidate's current
canonical repository:

| Existing `agents.json` repository | Current GitHub repository | Action |
| --- | --- | --- |
| `sst/opencode` | `anomalyco/opencode` | Repository move; update the existing entry separately, do not add a duplicate. |
| `block/goose` | `aaif-goose/goose` | Repository move; update the existing entry separately, do not add a duplicate. |
| `OpenInterpreter/open-interpreter` | `openinterpreter/openinterpreter` | Repository rename; update the existing entry separately, do not add a duplicate. |
| `strands-agents/sdk-python` | `strands-agents/harness-sdk` | Repository/monorepo move; update the existing Strands Agents entry separately, preserving its verified PyPI and npm fields. |

No move was applied in this research-only task.

## Exclusions

The following representative high-ranked discoveries fail the strict rubric:

- Collections, tutorials, prompts, or skills rather than standalone agents:
  `Shubhamsaboo/awesome-llm-apps`, `dair-ai/Prompt-Engineering-Guide`,
  `addyosmani/agent-skills`, `microsoft/ai-agents-for-beginners`,
  `hesreallyhim/awesome-claude-code`, `wshobson/agents`,
  `NirDiamant/GenAI_Agents`, and `ashishpatel26/500-AI-Agents-Projects`.
- Tools for agents without their own autonomous loop:
  `vercel-labs/agent-browser`, `googleworkspace/cli`,
  `gastownhall/beads`, `OpenViking`, `OpenSandbox`, `NVIDIA/OpenShell`,
  `memvid/memvid`, and `MemTensor/MemOS`.
- Agent-adjacent applications whose primary purpose is not agent construction
  or autonomous task execution: `nexu-io/open-design`, `siyuan-note/siyuan`,
  `hugohe3/ppt-master`, `presenton/presenton`, and
  `krillinai/KrillinAI`.
- Models, training systems, or evaluation infrastructure:
  `2noise/ChatTTS`, `microsoft/agent-lightning`, `rllm-org/rllm`,
  `areal-project/AReaL`, and `algorithmicsuperintelligence/openevolve`.

## Verification notes

- GitHub repository metadata was captured on 2026-07-06 and checked for a
  public, non-archived primary repository, recognized open-source license, and
  recent push activity.
- README claims were checked against implementation and test paths in each
  repository tree; descriptions alone were not accepted as evidence.
- Package identities were checked against PyPI or npm:
  `mini-swe-agent` 2.4.4, `mistral-vibe` 2.19.0,
  `solace-agent-mesh` 1.28.4, `@oh-my-pi/pi-coding-agent` 16.3.10,
  `@aoagents/ao` 0.10.0, and `@ai-hero/sandcastle` 0.12.0.
- Case-insensitive repository matching against all 342 current
  `agents.json` entries found no direct duplicate among the five recommended
  adds or three manual-review items.
- The generated `candidates.json` scratch output is intentionally not part of
  the research deliverable.
