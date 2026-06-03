# Legacy Audit — 2026-06-03

Purpose: verify whether repos currently marked `legacy` in `agents.json` still belong there.

Evidence source:

- GitHub repository metadata via `gh repo view --json ...`
- Repository README and LICENSE files for ambiguous scope/license cases

Current date used for the audit: **2026-06-03**

## Decision rule used

- **Restore to `listed`** only when all three are clearly true:
  - actively maintained (<365 days since last push)
  - public and not archived
  - still in scope as an AI agent or agent framework under the strict rubric

- **Keep `legacy`** when any of the following are true:
  - 365+ days since last meaningful push
  - archived
  - clearly outside the strict open-source AI agent / agent framework boundary

## Reclassified to listed

These were legacy in config but the current public evidence supports active listing.

| Repo | Why restore |
| --- | --- |
| `All-Hands-AI/OpenHands` | Active (`pushedAt` 2026-06-03), not archived, README clearly describes an agent SDK / CLI / local GUI. LICENSE shows MIT for the open-source portion outside `enterprise/`. |
| `princeton-nlp/SWE-agent` | Active (`pushedAt` 2026-06-01), not archived, clearly an autonomous software engineering agent. |
| `paul-gauthier/aider` | Active (`pushedAt` 2026-05-22), not archived, clearly an AI coding agent. |
| `i-am-bee/bee-agent-framework` | Active (`pushedAt` 2026-05-28), not archived, README clearly describes a toolkit for agents and multi-agent systems. |

## Kept as legacy

### Active but not suitable for restore

| Repo | Why keep legacy |
| --- | --- |
| `anthropics/claude-code` | Active, but locally classified with `license_override: proprietary`. This does not satisfy the strict open-source boundary. |
| `microsoft/guidance` | Active, but README describes a language/paradigm for steering LLMs rather than an agent or agent framework as narrowly defined in the rubric. |
| `microsoft/TaskWeaver` | Recently updated, but archived by maintainers. |

### Inactive / stale / archived

| Repo | Reason |
| --- | --- |
| `TransformerOptimus/SuperAGI` | 496 days since push |
| `smol-ai/developer` | 786 days since push |
| `kuafuai/DevOpsGPT` | 657 days since push; custom restrictive license text |
| `biobootloader/wolverine` | 816 days since push |
| `lavague-ai/LaVague` | 497 days since push |
| `entropy-research/Devon` | 372 days since push |
| `aymenfurter/microagents` | 809 days since push |
| `OpenBMB/AgentVerse` | 631 days since push |
| `AbanteAI/archive-old-cli-mentat` | archived |
| `langchain-ai/langgraph-codeact` | archived |
| `MinorJerry/WebVoyager` | 820 days since push |
| `nickscamara/open-deep-research` | 391 days since push |
| `protectai/rebuff` | archived |
| `idosal/AgentLLM` | 1037 days since push |
| `OpenBMB/XAgent` | 659 days since push |
| `agiresearch/OpenAGI` | 551 days since push |
| `xlang-ai/OpenAgents` | 561 days since push |
| `MineDojo/Voyager` | 790 days since push |
| `joonspk-research/generative_agents` | 666 days since push |
| `albertvillanova/tinyagents` | 379 days since push |
| `wisdom-pan/Agent_Hospital` | 614 days since push |

## Follow-up gap

The current production state model still overloads `legacy` to cover two different concepts:

- genuinely stale / archived projects
- active but intentionally excluded projects (for example proprietary or out-of-scope)

That should eventually be split into distinct public states such as `legacy` vs `rejected` / `delisted`, but no state-model expansion was done in this pass.
