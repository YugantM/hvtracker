# New listing candidates: batch 6 review of weekly report #398 (10 Nov 2026)

Source: issue #398, "New listing candidates — week of 2026-11-09" (50 of 1,073 candidates that pass the automated rubric, created in the last 120 days). Owner, 10 Nov: "add new entries to the leaderboard". As with batch 5, this batch adds what passes the review, records the rejections, and holds the rest with one question each. Nothing here is live until the PR is merged and deployed.

> **Listing pause.** The resume criterion (batch 1–5 pages indexed, under ~2% of sitemap URLs uncrawled) has not been re-measured here. As with batches 3–5, the owner chose to add before it was met. Skill pages are noindex, so only the 3 agent rows lengthen Google's crawl queue.

> **Depends on batch 5.** Batch 5 (PR #399, which replaces #374) was approved on 21 Oct but never merged, so the weekly reports since (#382, #390, #398) kept proposing its repos. Of this week's 50, six are batch 5 rows and ten are batch 5 or earlier rejections; they are settled by #399, not here.

## How this review was made

1. **Cross-check** of the 50 against the roster, `REVIEWED_REJECTED` (with batch 5's entries), and the open holds: 6 are batch 5 rows, 10 are already rejected, 5 are held from earlier weeks (moli, solidcraft, OpenChatCut, replica-skill, linkedin-agent-skill). **29 are new.**
2. **Checks on every new repo**, as in batch 5:
   - the README and the root file tree (`SKILL.md`, plugin manifests, package files);
   - licence, reading LICENSE wherever GitHub says `NOASSERTION` or the text is modified;
   - forks-to-stars ratio, contributors, commits, watchers and distinct issue and PR authors;
   - packages: only identifiers whose registry metadata names the repo (`scripts/verify_package_identifiers.py`).
3. **Category precedents** from the live board: phone agents under Browser & Computer Use (ESP32 iPhone Agent), personal agents under Agent Frameworks, context and cost tools as skills (Token Optimizer, Context Mode), vendor skill sets as skills (Google Skills), video skills (OpenFilm, ffmpeg-skill).

## A. Added (10)

**Agents (3)**

| Repo | Stars | Category | Why it fits | Signals |
|---|---:|---|---|---|
| wangzan101/Mika | 8,018 | Browser & Computer Use | On-device Android agent that works your apps and the web on a hidden background screen | 50 contributors, 664 commits, 39 issue authors; Apache-2.0 |
| amosblomqvist/learnharness | 8,083 | Agent Frameworks | Agent harness that measures what you know, plans, teaches and sets practice against a persistent learner model | 28 contributors, 1,015 commits, 65 issue authors; AGPL-3.0 |
| Ephemeral-AI-Lab/layerfs | 2,727 | Sandboxes & Runtimes | Ephemeral writable workspaces for agents over shared committed history | 24 contributors, 4,235 commits, 12 issue authors; MIT. Only 2 watchers, the one odd signal |

**Skills (7)**

| Repo | Stars | Why it fits | Signals |
|---|---:|---|---|
| google/elephant-goldfish-model | 16,964 | Plugin for drafting a spec with project context and reviewing it with fresh-context reviewers; manifests for Claude, Codex, Gemini, Cursor and Copilot | 35 contributors, 178 commits, 28 issue authors; Apache-2.0 |
| haydenschmitty/floorplan | 3,410 | Claude and Codex plugin that maps a codebase into an interactive plain-English diagram | 9 contributors, 140 commits, 51 issue authors; MIT |
| JuneYaooo/rea-video | 6,089 | CLI plus skills that an agent installs to break a video down shot by shot (the OpenFilm and ffmpeg-skill precedent) | 7 contributors, 73 commits, 13 issue authors; Apache-2.0 |
| microsoft/TokenEconomizer | 5,600 | Microsoft Research plugin that cuts coding-agent cost by learning from past sessions (the Token Optimizer precedent) | 29 contributors, 172 commits, 57 issue authors; Apache-2.0 |
| scenario-labs/skills | 3,649 | Skills for the Scenario MCP (images, video, 3D) plus skills that drive Blender, Unreal and other tools; listed as "Scenario Skills" because the repo name alone is generic | 14 contributors, 349 commits, release automation; MIT |
| alchaincyf/huashu-art-motion | 6,674 | A single `SKILL.md` skill that animates artwork in 35 styles | 1 contributor, 23 commits, 9 issue authors, forks 9.9%: thin, as earshot was in batch 5 |
| alchaincyf/huashu-motion | 2,597 | Skill, CLI and studio for product launch films made by a coding agent; npm `huashu-motion` (verified) | 1 contributor, 17 commits, forks 10%: thin |

## B. Held (5 new): one question each

| Repo | Question |
|---|---|
| modelflare-ai/AnyModelBot | A personal bot team with its own agent loop (files, shell, desktop) and real code (6 contributors, 286 commits). But 2,942 stars in two weeks with forks at 1.6% and 5 distinct issue authors, and it leads users to Modelflare's paid gateway. The moli question: add anyway? |
| Jakeschincariol/founder-skill | One commit by one author, like replica-skill and linkedin-agent-skill (held 15 Oct). Revisit all three once there is some history? |
| N4darae/shrt | A gRPC regression tester that installs a Claude Code skill. Developer tool or skill (the pr-lens question)? Also 135 watchers against 3 contributors and 5 issue authors. |
| qybaihe/bla | An MCP server and CLI that obfuscates software so AI reverse-engineering agents fail. Security & Guardrails, or out of scope because it works against agents rather than for them? |
| vAPI-Network/vapi-network | An x402 payment client for agents (USDC on Base) with an MCP server. In scope, and are 3,868 stars earned by 2 contributors and 64 commits (forks 3.4%)? |

Still held from earlier weeks and back in this report: lexmount/moli (now 23,156 stars), tangency-labs/solidcraft, 0xsline/OpenChatCut, Jakeschincariol/replica-skill and linkedin-agent-skill. Their questions are in the 13 Oct and 20 Oct reviews.

## C. Rejected (14), with the precedent

- **DeepSeek Harness add-ons (2026-09-29 DSH rulings):** `ccch1mneyyy/dsh-Go` (a third-party Android client for DSH, like the rejected DSHA), `Fei2411/DS-Bot`, `liguobao/ds-harness-remote`, and two copies of the rejected `YuJunZhiXue/dsh-purge`: `kingcharleslzy-ai/dsh-purge` (a "community" version) and `mmparko/dsh-purge` (a mirror).
- **`deepseek-ai/dsh-superagent-prototype`**, the one first-party case: it is a bundle for DSH, published as a single commit and labelled "research prototype for reference only, not an official DeepSeek product". Both the DSH ruling and the single-commit precedent say no for now. It will top the report every week at 22k stars; if the owner would rather revisit it once it has history, move it to held instead.
- **Supervisory class (#180):** `nightly-labs/openbot` (Codex, Claude Code, Grok and others do the work through ACP), `KKKKhazix/agent-autoloop` (schedules Claude Code or Codex in the background).
- **Licence (the chat-ollama precedent, 9 Oct):** `sandbox-quantum/switch` (Apache-2.0 limited by the Commons Clause; otherwise it would fit next to Cumora), `kuafuai/andee` (Apache-2.0 with added conditions: no multi-tenant hosting, no white-labelling).
- **Not an agent:** `horizon-rust/horizon` (a Minecraft rewrite in Rust), `rddmwmddr/android-ad-cleaner` (Android ad scripts) and `simbasjungles/free-my-tv` (a TV home screen), both after `cleanyourtv`; `shaongitbd/doory` (a Canva alternative).

## Findings for the pipeline

1. **Copies of rejected repos keep coming back.** Two copies of `dsh-purge` arrived under new owners this week: the fourth recurrence after agent-orchestrator, EAC-Desktop and ARTEX. Matching candidates against `REVIEWED_REJECTED` by fork parent or README "mirror of" lines would catch most of them.
2. **An unmerged batch keeps resurfacing.** #374 sat for three weeks, so 16 of its decisions came back in three reports. Merging a batch soon after approval keeps the weekly report short.

## Outcome and rank-churn gate (10 Nov)

**Recorded:** 10 rows in `agents.json` (one package id, npm `huashu-motion`, verified against its repo; the other nine have none, rather than a guess: `mika`, `layerfs`, `floorplan` and `skills` on npm belong to other projects), and 14 entries in `REVIEWED_REJECTED`. No new name or slug collides with a listed or retired (410) profile.

**Gate.** The 10 rows were scored in a local `--pending-only` run against the live 10 Nov board (12:08 UTC render, 1,758 rows), inserted and re-ranked. The comparator reproduces live ranks exactly (0 of 1,758 mismatches). Each row is also re-scored with `what_if_score` at Scorecard 3.0, 5.0 and 7.0, since our scan reaches new rows only after the deploy.

- **Agents:** no top-100 row moves. Mika (#1,361), LayerFS (#1,363) and LearnHarness (#1,365) enter at D (24.0–24.3): no packages, no Scorecard yet. 14 existing agents move, at most 3 places. **Range:** at Scorecard 7.0 they would reach about #585–601 (C).
- **Skills:** Scenario Skills enters at **#39 (68.2, B)**, from its OpenSSF Scorecard 6.6 and fully signed commits, and Huashu Motion at **#48 (67.2, B)**, from npm build provenance and about 1,070 weekly downloads, the way OpenFilm earned its rank. 62 skills from #39 to #100 move down 1–2 places. The other five enter at D (#384–#389). **Range:** Huashu Motion about #23 at Scorecard 5.0 (#19 at 7.0); Elephant Goldfish Model about #72 at 5.0 and #39 at 7.0; TokenEconomizer #69 at 7.0.
- **With batch 5 (#399) on the same board:** still no top-100 agent moves (at most 13 places, none above #214); on the skill board 75 of the top 100 move down 2–4 places (lower rows at most 12).
- No new eligibility warnings; package failures are only `AynOps/AynOps`, already on the live board; board invariants `[]`.
