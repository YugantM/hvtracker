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

## Batch 1 — deployed with Phase 3 (check 14 days after deploy, then at 28)

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
