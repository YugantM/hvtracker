# Agent Fingerprint Research
**Date:** 2026-05-25  
**Status:** Complete — approved for implementation  
**Scope:** 10 agents from initial tracking list

---

## Summary Table

| Agent | Fingerprint type | Pattern | API endpoint | Est. volume (total) | Confidence |
|---|---|---|---|---|---|
| Aider | commit_trailer | `Co-authored-by: aider` | `search/commits` | ~96,538 commits | **High** |
| Devin | pr_body | `Created by Devin` | `search/issues` (type:pr) | ~6,185 PRs | **High** |
| Claude Code | pr_body | `Co-Authored-By: Claude` | `search/issues` (type:pr) | ~125,929 PRs | **Medium-High** |
| OpenHands | bot_account | `author:openhands-agent` | `search/issues` (type:pr) | ~190 PRs | **High** |
| Gemini CLI | pr_body | `Generated with Gemini CLI` | `search/issues` (type:pr) | ~594 PRs | **High** |
| Qwen Code | pr_body | `Generated with Qwen Code` | `search/issues` (type:pr) | ~541 PRs | **Medium** |
| Cline | — | No reliable fingerprint | — | — | **None** |
| CodeRabbit | — | Review-only tool | — | — | **None** |
| Sweep | pr_body | `Created by Sweep` | `search/issues` (type:pr) | ~38 PRs | **Low** (deprecated) |
| Codex CLI | — | Pattern too generic | — | — | **Excluded** |

---

## Per-Agent Details

### 1. Aider (paul-gauthier/aider)

**Fingerprint type:** `commit_trailer`  
**Pattern:** `Co-authored-by: aider` (case-insensitive; also `Co-Authored-By: aider`)  
**Search query:** `"Co-authored-by: aider"` via `GET /search/commits`  
**Estimated total volume:** ~96,538 commits  
**Sample repos confirmed:**
- `paul-gauthier/paul-gauthier.github.io` (maintainer's own blog)
- Community repos with Aider-generated commits

**How Aider adds this:** Aider automatically appends `Co-authored-by: aider <noreply@aider.chat>` to every commit it makes. This is the canonical Aider fingerprint and is well-established in the community.

**Limitations:**
- Some projects may disable the trailer (`--no-git-co-author` flag).
- The broad `aider` string could theoretically match non-Aider commits, but in practice this is rare — the full trailer format is distinctive.

**Recommendation: Include. High-quality fingerprint.**

---

### 2. Devin (cognition-ai/devin — hosted service)

**Fingerprint type:** `pr_body`  
**Pattern:** `Created by Devin` (appears in PR description footer added by Devin)  
**Search query:** `"Created by Devin" type:pr` via `GET /search/issues`  
**Estimated total volume:** ~6,185 PRs  
**Sample results:**
- `fix(explore): preserve filter state when switching visualization types` — real product PR
- Some test/dummy PRs in the sample

**How Devin adds this:** Devin adds a footer to every PR description it creates. The marker is `Created by Devin` followed by a session link.

**Limitations:**
- A small number of PRs titled "Dummy PR for testing" indicate the marker is also used in test/sandbox environments. These will inflate counts slightly.
- Devin is a hosted service — `devin-ai-integration[bot]` is the GitHub App bot account. The `author:devin-ai-integration` commit search returned 243,351 (much higher) — this includes commits pushed by the bot, not just the Devin-created ones. The PR body marker is more precise.

**Recommendation: Include, use PR body marker (`"Created by Devin"`). High confidence.**

---

### 3. Claude Code (Anthropic)

**Fingerprint type:** `pr_body`  
**Pattern:** `Co-Authored-By: Claude` (commit trailer and PR body)  
**Also consider:** `🤖 Generated with [Claude Code]` in PR bodies  
**Search query:** `"Co-Authored-By: Claude" type:pr` via `GET /search/issues`  
**Estimated total volume:** ~125,929 PRs  
**Sample results:**
- Real Claude Code-generated PRs (e.g., translation tasks, feature PRs)
- One false positive: "Remove Co-Authored-By Claude from commit history" (a cleanup PR)

**How Claude Code adds this:** Claude Code appends `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` (or equivalent model name) to commit messages, and adds `🤖 Generated with [Claude Code](https://claude.com/claude-code)` to PR descriptions.

**Limitations:**
- "Co-Authored-By: Claude" could theoretically match a human named Claude, though this is rare in practice.
- The exact model version in the trailer varies (Sonnet, Opus, Haiku). Searching `"Co-Authored-By: Claude"` catches all variants.
- 125k is a large number — this signal will dominate the leaderboard. That's fine; it reflects Claude Code's actual adoption.

**Recommendation: Include. Use `"Co-Authored-By: Claude" type:pr merged:true` for merge rate. High-medium confidence.**

---

### 4. OpenHands (All-Hands-AI/OpenHands)

**Fingerprint type:** `pr_body`  
**Pattern:** `Authored by OpenHands` (footer added to PR descriptions)  
**Search query:** `"Authored by OpenHands" type:pr is:merged` via `GET /search/issues`  
**Estimated total volume:** ~72 merged PRs in 30 days  
**Sample PRs (May 2026):**
- `fix: Add teacher detail page at /teachers/[id]`
- `feat: add Loxa routing layer (v0)`
- `feat: security and UI upgrades`

**How OpenHands adds this:** OpenHands adds "Authored by OpenHands" to the body of every PR it creates.

**History note:** The original fingerprint was `author:openhands-agent` (GitHub App bot account). That bot has been inactive since ~July 2025 (most recent PR: 2025-07-11). OpenHands switched to the PR body marker for external deployments. The bot account fingerprint returned 0 for 30-day queries. Updated 2026-05-25.

**Limitations:**
- Some false positives possible if users manually write "Authored by OpenHands" in PR bodies.
- The phrase is specific enough to be low-noise in practice.

**Recommendation: Include with updated fingerprint. High confidence.**

---

### 5. Cline (cline/cline)

**Fingerprint type:** None confirmed  
**Pattern investigated:** "created with cline", general "cline" search  
**Results:**
- `"created with cline" type:pr` → 14 PRs (extremely low, likely not a standard marker)
- `"cline" type:pr` → 25,439 PRs (extremely noisy — "cline" is a common English word)
- No standard commit trailer or PR footer was found in Cline's documentation or codebase

**Why no fingerprint:** Cline operates as a VS Code extension that calls LLMs but does not automatically append any attribution marker to commits or PRs. Unlike Aider or Claude Code, Cline has no built-in "add my signature" step.

**Recommendation: Exclude from tracking pipeline. No reliable fingerprint.**

---

### 6. CodeRabbit (review-only tool)

**Fingerprint type:** None suitable  
**Pattern investigated:** `commenter:coderabbitai[bot]`, `coderabbitai` in PR reviews  
**Results:**
- `commenter:coderabbitai type:pr` → 0 (GitHub Search API does not index review comments via `commenter:` for bot accounts in this way)
- CodeRabbit reviews PRs; it does not create commits or PRs

**Why no fingerprint for our purposes:** CodeRabbit is a code review agent, not a code-writing agent. It leaves review comments and summary comments on PRs, but does not create commits or author PRs. The GitHub Search API's commit and issue endpoints do not capture review comments.

A proxy signal would be to count PRs where `coderabbitai[bot]` has commented, but this requires per-PR comment scanning — not feasible at scale with the search API.

**Recommendation: Exclude from tracking pipeline. Not suitable for commit/PR-based fingerprinting.**

---

### 7. Sweep (sweepai/sweep — deprecated)

**Fingerprint type:** `pr_body`  
**Pattern:** `Created by Sweep` (footer in PR description)  
**Search query:** `"Created by Sweep" type:pr` via `GET /search/issues`  
**Estimated total volume:** ~38 PRs (very low — deprecated)  
**Notes:** The sample hits were low quality (some looked like AI-generated test content unrelated to Sweep). Sweep is deprecated (pivoted to JetBrains plugin). The `sweep-ai[bot]` account still exists but has very little activity.

**Recommendation: Exclude from tracking pipeline — deprecated, insufficient signal volume.**

---

### 8. Codex CLI (openai/codex)

**Fingerprint type:** None confirmed  
**Pattern investigated:** `"Generated with Codex"`, `"Generated by Codex"`, `co-authored-by: codex`  
**Results:**
- `"Generated with Codex" type:pr` → 14,018 (but samples are contaminated: "feat(cli): prompt for node mismatch reinstall" is clearly not AI-generated; many hits reference "OpenAI Codex" the model, not the CLI)
- `"Generated by Codex"` → 16,933 (same problem — "codex" is too generic)
- Codex CLI's README and source code do not document a standard attribution marker

**Why excluded:** "Codex" appears in too many unrelated contexts (OpenAI Codex the model, the Codex documentation platform, other tools named Codex). The signal cannot be reliably filtered to the `openai/codex` CLI specifically. No standard commit trailer found.

**Recommendation: Exclude from tracking pipeline — signal too noisy, no confirmed standard marker.**

---

### 9. Gemini CLI (google-gemini/gemini-cli)

**Fingerprint type:** `pr_body`  
**Pattern:** `Generated with Gemini CLI` (footer in PR description)  
**Search query:** `"Generated with Gemini CLI" type:pr` via `GET /search/issues`  
**Estimated total volume:** ~594 PRs  
**Sample results:**
- `feat: migrate to moonrepo polyglot structure and add Stitch MCP e2e test`
- `ci: modernize GitHub workflows`
- Real-looking feature/infra PRs

**How Gemini CLI adds this:** The CLI adds a footer line `Generated with Gemini CLI` to PR descriptions.

**Limitations:**
- Relatively new tool — volume will grow. Current count of 594 is credible for a tool released in mid-2025.
- Sample shows legitimate PRs across multiple repos.

**Recommendation: Include. High confidence fingerprint.**

---

### 10. Qwen Code (QwenLM/qwen-code)

**Fingerprint type:** `pr_body`  
**Pattern:** `Generated with Qwen Code` (PR footer)  
**Search query:** `"Generated with Qwen Code" type:pr` via `GET /search/issues`  
**Estimated total volume:** ~541 PRs  
**Sample results:**
- `docs: add Qwen Code integration guide` (docs PR about the tool itself)
- `fix(core): emit enable_thinking on DashScope when reasoning is disabled` (from QwenLM/qwen-code repo)

**Caveats:**
- Some hits appear to be internal QwenLM development PRs, not external usage. The fingerprint may capture self-referential activity.
- The tool is relatively new; external adoption volume is unclear from the sample.

**Recommendation: Include but note medium confidence. Monitor for pattern quality over time.**

---

## Implementation Notes

### Agents to include in fingerprint tracking (6 of 10)

| Agent | `fingerprints.type` | `fingerprints.pattern` | `fingerprints.search_endpoint` |
|---|---|---|---|
| Aider | `commit_trailer` | `Co-authored-by: aider` | `commits` |
| Devin | `pr_body` | `Created by Devin` | `pulls` |
| Claude Code | `pr_body` | `Co-Authored-By: Claude` | `pulls` |
| OpenHands | `bot_account` | `openhands-agent` | `pulls` |
| Gemini CLI | `pr_body` | `Generated with Gemini CLI` | `pulls` |
| Qwen Code | `pr_body` | `Generated with Qwen Code` | `pulls` |

### Agents excluded (4 of 10)

| Agent | Reason |
|---|---|
| Cline | No standard attribution marker in commits or PRs |
| CodeRabbit | Review-only; doesn't author commits/PRs |
| Sweep | Deprecated; only ~38 PRs, signal too small |
| Codex CLI | "Codex" term too generic; no confirmed standard marker |

### API endpoint selection rationale

For `commit_trailer` type (Aider): use `GET /search/commits?q={pattern}` — commit messages are the native data.

For all others (PR-based): use `GET /search/issues?q={pattern}+type:pr+is:merged` — merged PRs are the meaningful unit (a PR that was rejected doesn't represent an agent action that landed).

### Rate limit budget

GitHub Search API: 30 requests/minute authenticated. Running 6 agents × 1 query each = 6 requests/run. Add a 2-second sleep between calls = ~12 seconds total. Well within budget even if we double the agent count.

### 30-day filter

To get `actions_30d`, append `created:>YYYY-MM-DD` to each search query where the date is 30 days ago. This scopes results to the trailing month, consistent with other `_30d` signals in the dataset.
