# Eligibility Sweep — 2026-05-25

**Scope:** All 98 agents in agents.json  
**Spec applied:** Eligibility Specification v1.0 (docs/drafts/eligibility-v1.0-draft.md)  
**Status:** Awaiting owner approval before any changes to agents.json

---

## Summary

| Outcome | Count |
|---|---|
| Disqualify — archived (criterion 5.1) | 4 |
| Remove — not an agent (criteria 4.1.4 / 4.1.5) | 12 |
| Move to legacy — inactive ≥365 days (criterion 4.2.1) | 7 |
| Keep — borderline, defensible, owner should confirm | 5 |
| Clean — no issues | ~70 |

**Projected active agent count after sweep:** ~75–79 agents + legacy section

---

## Section 1 — Disqualify: Archived Repositories (criterion 5.1)

These repos have `archived: true` on the GitHub API. Criterion 5.1 is a disqualification rule that takes precedence over all eligibility criteria.

| Agent | Repo | Archived | Last pushed | Recommendation |
|---|---|---|---|---|
| GPT Engineer | AntonOsika/gpt-engineer | Yes | 2025-05-14 | **REMOVE** |
| Automata | emrgnt-cmplxty/Automata | Yes | 2023-09-05 | **REMOVE** |
| OpenGPTs | langchain-ai/opengpts | Yes | 2025-06-26 | **REMOVE** |
| TaskWeaver | microsoft/TaskWeaver | Yes | 2026-03-23 | **REMOVE** |

**Notes:**
- GPT Engineer: The repo description reads "CLI platform to experiment with codegen. Precursor to: https://lovable.dev" — the project has officially migrated to a hosted product.
- Automata: 992 days since last push (also flagged by the 365d inactivity check).
- OpenGPTs: Archived by LangChain, users are directed to LangGraph instead.
- TaskWeaver: Microsoft archived the project in early 2026.

---

## Section 2 — Remove: Does Not Meet Agent Criteria (criteria 4.1.4 / 4.1.5)

These projects fail the agent characteristics criterion (4.1.4: must satisfy at least 2 of autonomous execution, tool use, goal-directed planning) or the non-trivial implementation criterion (4.1.5: must contain agent logic in its own codebase).

### 2.1 Benchmark / evaluation suite

| Agent | Repo | Issue | Recommendation |
|---|---|---|---|
| AgentBench | THUDM/AgentBench | Benchmark evaluation suite for LLMs, not an agent itself. Provides test environments. | **REMOVE** |

**Criterion violated:** 4.1.4 — AgentBench does not autonomously execute tasks; it administers tests to evaluate other systems. A benchmark does not satisfy (a) autonomous execution, nor (c) goal-directed planning. Only (b) tool use is arguable (it invokes environments), which per the spec is insufficient alone.

### 2.2 Tools / scrapers (not agents)

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| GPT Crawler | BuilderIO/gpt-crawler | "Crawl a site to generate knowledge files to create your own custom GPT from a URL" | **REMOVE** |
| Resume Matcher | srbhr/Resume-Matcher | "Improve your resumes with Resume Matcher. Get insights, keyword suggestions and tune your resumes" | **REMOVE** |

**Criterion violated:**
- GPT Crawler: Single-purpose web scraping tool with no autonomous execution or goal-directed planning. Only performs one step: crawl a URL. Fails 4.1.4 (only satisfies (b) loosely), fails 4.1.5 (no planning loop or execution engine). Category was "Research & Data" which is borderline, but the project itself is a one-shot tool.
- Resume Matcher: Resume/job-description comparison utility. No autonomous task execution, no tool use in the agent sense, no planning. Clearly fails 4.1.4. Category was "Research & Data" — it's a data matching tool.

### 2.3 Fine-tuning / training toolkit

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| LLaMA-Factory | hiyouga/LLaMA-Factory | Model fine-tuning framework ("Efficient Finetuning of 100+ LLMs") | **REMOVE** |

**Criterion violated:** 4.1.4 — LLaMA-Factory is a model training and fine-tuning toolkit. It does not execute agent tasks; it prepares models for use by other systems. Fails (a), (b) in the agent sense, and (c). 4.1.5 also fails as there is no agent execution loop. Category was "Research & Data."

**Note:** GitHub API returned empty fields for this repo — possible API issue. The project is well-known as a fine-tuning toolkit at https://github.com/hiyouga/LLaMA-Factory.

### 2.4 Deprecated project

| Agent | Repo | GitHub description | Recommendation |
|---|---|---|---|
| Vision Agent | landing-ai/vision-agent | "This tool has been deprecated. Use Agentic Document Extraction instead." | **REMOVE** |

**Criterion violated:** Not a hard spec failure (project is not archived; last push 2026-01-29, 115 days ago). However:
- The maintainers have explicitly deprecated the project and directed users to a different product ("Agentic Document Extraction"), which appears to be a hosted/commercial service rather than an open-source agent.
- This is a near-equivalent to criterion 5.5 (maintainer withdrawal) in spirit — the maintainers have abandoned the open-source project in favor of a hosted replacement.
- Owner decision: remove, or keep with a "deprecated" annotation. The recommendation is **REMOVE** because the project's own README redirects users away from it.

### 2.5 Observability / monitoring SDK (not an agent)

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| AgentOps | AgentOps-AI/agentops | "Python SDK for AI agent monitoring, LLM cost tracking, benchmarking, and more." | **REMOVE** |

**Criterion violated:** 4.1.4 — AgentOps monitors agents; it does not execute tasks autonomously. It has no autonomous execution (a), no goal-directed planning (c). Observability tooling satisfies (b) only loosely (it hooks into LLM calls). Per 4.1.4: "A system that satisfies only (b) — tool use — without (a) or (c) is a tool-augmented chatbot, not an agent."

**Note:** The HN count (currently 1077) is also a false positive — see Section 5 below.

### 2.6 Browser infrastructure (not an agent)

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| Steel Browser | steel-dev/steel-browser | "Open Source Browser API for AI Agents & Apps. Steel Browser is a batteries-included browser sandbox" | **REMOVE** |
| Chrome DevTools MCP | ChromeDevTools/chrome-devtools-mcp | "Chrome DevTools for coding agents" | **REMOVE** |

**Criterion violated:** 4.1.4 / 4.1.5 — Both are infrastructure/tooling that agents can use, not agents themselves.
- Steel Browser is a headless browser sandbox API — a platform on which agents run.
- Chrome DevTools MCP is an MCP server exposing Chrome DevTools to agents — pure tool infrastructure.
Neither executes multi-step tasks autonomously, neither has planning or goal decomposition.

### 2.7 Non-autonomous applications

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| LlamaCoder | Nutlope/llamacoder | "Open source Claude Artifacts – built with Llama 3.1 405B" | **REMOVE** |
| Tabby | TabbyML/tabby | "Self-hosted AI coding assistant" | **REMOVE** |

**Criterion violated:**
- LlamaCoder: A single-page web app that generates React components via LLM. One-shot code generation with no multi-step execution, no tool use, no planning loop. Fails 4.1.4 on all three criteria. Fails 4.1.5.
- Tabby: A self-hosted code completion engine (autocomplete). Autocomplete is not autonomous task execution — it responds to cursor position, not goals. No planning, no tool use in the agent sense. Fails 4.1.4.

### 2.8 LLM interface CLI (borderline, lean-remove)

| Agent | Repo | Description | Recommendation |
|---|---|---|---|
| LLM | simonw/llm | "Access large language models from the command-line" | **REMOVE** |

**Criterion violated:** 4.1.4 — simonw/llm is primarily a CLI interface for sending prompts to LLMs and receiving responses. It has tool use via plugins, but it does not satisfy (a) autonomous execution or (c) goal-directed planning in its own codebase. Per the spec: "A system that satisfies only (b) — tool use — without (a) or (c) is a tool-augmented chatbot, not an agent, and is not eligible."

**Counter-argument for keeping:** The project has expanded into scripting, logging, and a plugin ecosystem. If `llm --continue` or chained commands constitute autonomous execution, it could borderline qualify. Owner should decide.

---

## Section 3 — Move to Legacy: Inactive ≥365 Days (criterion 4.2.1)

These projects have not had a meaningful push in over 365 days. Per the spec, they are not disqualified but should receive an "inactive" annotation (or be moved to a legacy section). The recommendation here is to move them to a `"status": "legacy"` section rather than remove them, as they were historically valid agents.

| Agent | Repo | Days since push | Recommendation |
|---|---|---|---|
| Wolverine | biobootloader/wolverine | 807 days | **LEGACY** |
| Microagents | aymenfurter/microagents | 800 days | **LEGACY** |
| smol developer | smol-ai/developer | 777 days | **LEGACY** |
| AgentVerse | OpenBMB/AgentVerse | 622 days | **LEGACY** |
| DevOpsGPT | kuafuai/DevOpsGPT | 648 days | **LEGACY** |
| LaVague | lavague-ai/LaVague | 488 days | **LEGACY** |
| SuperAGI | TransformerOptimus/SuperAGI | 487 days | **LEGACY** |

**Notes:**
- DevOpsGPT also has `license: NOASSERTION` on GitHub API, suggesting the license may not be declared in a recognized format. If a manual check confirms no open-source license, this should be **REMOVE** instead of LEGACY.
- All seven were legitimate agents at time of inclusion.

---

## Section 4 — Keep: Borderline Entries

These entries have a defensible case for inclusion. Owner should review and decide.

### 4.1 License NOASSERTION concerns

| Agent | Repo | Issue | Recommendation |
|---|---|---|---|
| GitHub Copilot CLI | github/copilot-cli | NOASSERTION license; also potentially a thin client for hosted Copilot service | **KEEP** — owner review needed |
| Sweep | sweepai/sweep | NOASSERTION license; project pivoted from GitHub bot agent to JetBrains plugin | **KEEP** — owner review needed |

**Reasoning:**
- GitHub Copilot CLI: The CLI does include local agent logic (intent detection, command generation) beyond just proxying to Copilot's API. License NOASSERTION may be a GitHub detection artifact. Owner should verify the actual license file in the repo. If the project is purely a thin client, remove under 4.1.5.
- Sweep: Was a legitimate GitHub bot agent that opened PRs autonomously. Has since pivoted to JetBrains IDE. 248 days since last push. NOASSERTION license needs verification. Keep for now, remove in next sweep if license can't be verified.

### 4.2 Framework eligibility (4.3.1)

| Agent | Repo | Issue | Recommendation |
|---|---|---|---|
| Vercel AI SDK | vercel/ai | General AI toolkit; agent abstractions exist but not primary design goal | **KEEP** under 4.3.1 |
| Microsoft PromptFlow | microsoft/promptflow | LLM app development framework; limited agent-specific abstractions | **KEEP** — borderline |

**Reasoning:**
- Vercel AI SDK: v3+ includes `experimental_continueConversation`, multi-step tool use, and streaming agent patterns. The framework does enable agent construction. Qualifies under 4.3.1, borderline.
- Microsoft PromptFlow: Primarily a prompt engineering and flow orchestration tool. Agent abstractions are present but secondary to the LLM app development use case. Borderline under 4.3.1. Owner should decide if this is in scope.

### 4.3 Near-threshold inactivity

| Agent | Repo | Days since push | Recommendation |
|---|---|---|---|
| Devon | entropy-research/Devon | 363 days (as of 2026-05-25) | **KEEP** — 2 days under threshold |

**Reasoning:** Devon is 2 days under the 365-day threshold. Keep for now; will cross into legacy territory within days unless there's new activity.

---

## Section 5 — AgentOps HN Count False Positive

**Current count:** 1,077 mentions (from `hn_search_term: "agentops"`)  
**Root cause:** The Algolia full-text search for `agentops` tokenizes it as `agent` + `ops`, matching any story containing both words in any context — e.g., "AI coding agent ops", "AgentOS", general discussion of "agent operations."

**Evidence:** A sample of results shows hits for "Aperion Shield: local guardrail that blocks destructive AI coding agent ops" and "AgentOS: A portable open-source operating system for agents" — neither related to the AgentOps Python SDK.

**Fix:** Change `hn_search_term` to `"\"agentops\""` (with embedded quotes) for exact-phrase matching.  
Using the exact-phrase query `"agentops"`: **1 hit** in the last 30 days.

**Proposed change to agents.json:**
```json
// Before:
"hn_search_term": "agentops"

// After:
"hn_search_term": "\"agentops\""
```

Note: If AgentOps is removed from the index (see Section 2.5), this fix is moot.

---

## Section 6 — Agents That Passed All Checks

The remaining ~74 agents pass all automated checks (not archived, not deleted, license declared or plausible, activity within 365 days) and appear to meet the spirit of criteria 4.1.4 and 4.1.5 based on their descriptions and categories.

No issues found for: OpenHands, SWE-agent, Aider, Continue, Cline, Roo Code, MetaGPT, AutoGen, CrewAI, LangGraph, AutoGPT, BabyAGI, GPT Researcher, PydanticAI, ChatDev, E2B, Open Interpreter, Letta, CAMEL, Semantic Kernel, Browser Use, Composio, Dify, GPT Pilot, GPTMe, Khoj, Qwen Agent, Plandex, Open SWE, Microsoft Agent Framework, Google ADK Python, Google ADK Go, AgentScope, Eliza, VoltAgent, PraisonAI, Strands Agents, Spring AI Alibaba, Flowise, Coze Studio, Activepieces, Trigger.dev, Flyte, UI-TARS Desktop, Cua, Browser Use Web UI, Cognee, Graphiti, Leon, Firecrawl, DeerFlow, WrenAI, LiveKit Agents, TEN Framework, OmniParser, UFO, UI-TARS, RA.Aid, Maxun, Haystack, Devika, Mem0, PromptFlow (borderline), AdalFlow, Agno, Qwen Code, Gemini CLI, Codex CLI, gptme, Haystack, Devon (near-threshold).

---

## Appendix — Automated Check Results

The following agents were flagged by the automated inactivity check (days_ago > 365) or require manual review. This list was cross-referenced with the GitHub API to verify archived status.

| Agent | Days inactive | Archived | Manual action |
|---|---|---|---|
| GPT Engineer | 375 | **YES** | Remove (5.1) |
| Automata | 992 | **YES** | Remove (5.1) |
| OpenGPTs | ~335 (approx) | **YES** | Remove (5.1) |
| TaskWeaver | 62 | **YES** | Remove (5.1) |
| Wolverine | 807 | No | Legacy |
| Microagents | 800 | No | Legacy |
| smol developer | 777 | No | Legacy |
| AgentVerse | 622 | No | Legacy |
| DevOpsGPT | 648 | No | Legacy |
| LaVague | 488 | No | Legacy |
| SuperAGI | 487 | No | Legacy |
| Automata (also 4.2.1) | 992 | Yes | Remove (5.1 takes precedence) |
