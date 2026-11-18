# CTR tests

Plan task 3.1. Titles and meta descriptions change **only** through a logged
batch like this one, never as a side effect (#114: title churn cost indexed
URLs). Each entry lists the exact change, its Search Console baseline and the
date to check it. Overrides live in `CTR_TEST_COMPARE` in `fetch_and_build.py`.

How to check: Search Console → Performance → filter the page, compare the 28
days after deploy against the baseline below, and compare against the
control group (all other `/compare/` pages) over the same windows. A test
"wins" if its CTR rises by more than the control's at a similar position.
Revert a loser by deleting its entry.

## Profile and category pages (Phase 10, from 2026-10-04)

`CTR_TEST_AGENT` (keyed by profile slug) and `CTR_TEST_CATEGORY` (keyed by
category slug) in `fetch_and_build.py` take the same kind of logged
title/description override as `CTR_TEST_COMPARE`. Fields: profiles `{name}`
`{score}` `{grade}` `{rank}` `{total}` `{category}`; categories `{category}`
`{count}` `{top3}`. With no entry a page renders byte for byte as before
(checked: 0 of 3,260 pages changed). A test fails if any key lacks a mention in
this file, so every entry needs a batch section below with its baseline,
control group and check dates. Before merging a batch, run
`python scripts/lastmod_diff.py`: only the tested pages may show a new date.

## Batch 1 — deployed 2026-09-24 08:48 UTC (deployment 93273d1c); check 2026-10-08, then 2026-10-22

Baseline window: 2026-08-24 → 2026-09-21 (28 days).

| Page | Impr. | Clicks | CTR | Pos. | Queries (impr. / clicks / pos.) |
|---|---|---|---|---|---|
| `/compare/litellm-vs-vllm/` | 481 | 2 | 0.42% | 8.0 | "litellm vs vllm" 197/1/7.8 · "vllm vs litellm" 148/0/8.2 |
| `/compare/hindsight-vs-mem0/` | 180 | 2 | 1.11% | 7.2 | "mem0 vs hindsight" 86/0/6.9 · "hindsight vs mem0" 55/2/8.1 |
| Control: 396 other compare pages | 3,170 | 102 | 3.22% | — | — |

**Why these two:** searchers ask what the tools *are* ("vllm vs litellm": a
gateway against an inference engine), and the templated title answered a
question they didn't ask ("AI agent trust comparison").

| Page | Old title | New title |
|---|---|---|
| litellm-vs-vllm | LiteLLM vs vLLM: AI agent trust comparison \| HVTracker | LiteLLM vs vLLM: AI Gateway vs Inference Engine \| HVTracker |
| hindsight-vs-mem0 | Hindsight vs Mem0: AI agent trust comparison \| HVTracker | Hindsight vs Mem0: Which Agent Memory Layer to Trust? \| HVTracker |

New descriptions lead with what each tool does, then the live scores. The
body change shipped alongside, a one-line "what it is" on every compare
card, applies to all pairs, so the control group has it too.

**Not in this batch, and why:**
- `/capabilities/` (2,293 impr., 1 click, pos. 8.8). Every named query behind
  it is someone else's repo name ("dexmcp.icu", 105 impr.); the page ranks
  because it lists every project. Its title already states its real intent
  ("Which AI Agents Support MCP?"). No title converts a navigational search
  for another site, so changing it would add noise, not signal.
- Homepage (2,798 impr., 5 clicks, pos. 7.1). Its named queries are brand
  misspellings; the rest are anonymised. Nothing to target yet.
- Agent / category titles are templated across hundreds of pages. Too large
  for a measured test.

### Batch 1 result — checked 2026-11-17

28 days after the deploy (2026-09-25 → 2026-10-22) against the baseline:

| Page | Baseline CTR (pos.) | After CTR (pos.) | Control after |
|---|---|---|---|
| `/compare/hindsight-vs-mem0/` | 1.11% (7.2) | 5.09% (5.7), 22 clicks / 432 impr. | 2.53% (428 pages, was 3.22%) |
| `/compare/litellm-vs-vllm/` | 0.42% (8.0) | 1.15% (5.9), 9 clicks / 782 impr. | same |

Both rose while the control fell, so both are kept. Position also improved by
about 1.5 places on each, so not all of the lift is the title. hindsight-vs-mem0
is a clear win and held it (4.83% on 2026-10-19 → 11-15). litellm-vs-vllm
still trails the control (0.77% in that later window): the next candidate for
a second wording if it stays there.

## Batch 2 — compare pages seen high but not clicked (opened 2026-11-17; deploy pending)

Baseline window: 2026-10-19 → 2026-11-15 (28 days). Control: all other
`/compare/` pages, 455 pages, 6,005 impr., 156 clicks, 2.60%.

| Page | Impr. | Clicks | CTR | Pos. | Queries (impr. / clicks / pos.) |
|---|---|---|---|---|---|
| `/compare/langfuse-vs-mlflow/` | 262 | 1 | 0.38% | 8.0 | "mlflow vs langfuse" 102/0/7.9 · "langfuse vs mlflow" 84/0/7.9 |
| `/compare/cline-vs-qwen-code/` | 131 | 2 | 1.53% | 6.4 | "qwen code vs cline" 22/0/2.6 · "cline vs qwen code" 14/0/2.5 |

**Why these two:** the batch 1 pattern. Both now describe themselves in
similar words ("open source AI engineering platform"; "coding agent"), so the
searcher is asking how they differ, and the templated title answers a trust
question first.

| Page | Old title | New title |
|---|---|---|
| langfuse-vs-mlflow | Langfuse vs MLflow: AI agent trust comparison \| HVTracker | Langfuse vs MLflow: LLM Observability vs the Full ML Platform \| HVTracker |
| cline-vs-qwen-code | Cline vs Qwen Code: AI agent trust comparison \| HVTracker | Cline vs Qwen Code: IDE Coding Agent vs Terminal Agent \| HVTracker |

Descriptions lead with what each tool is, then the live scores. Check 14 and
28 days after the deploy, against the control over the same window.

**Not in this batch, and why:**
- `/compare/hermes-agent-vs-oh-my-pi/` (672 impr., 2.53%): already at the control
  rate.
- `/compare/hermes-agent-vs-mistral-vibe/` (232 impr., 1.72%): its queries
  ("hermes agent mistral", "mistral vibe hermes") are ambiguous between the
  agent and Nous's Hermes models, so a title can't answer them.
- `/compare/browser-use-vs-stagehand/` (125 impr., 0 clicks): position 11.1,
  page two, where a title barely matters.
