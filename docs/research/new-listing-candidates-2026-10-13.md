# New listing candidates: batch 4 review of weekly report #364 (13 Oct 2026)

Discovery proposes; **the owner decides**. Source: issue #364, "New listing candidates — week of 2026-10-12" (50 of 905 candidates that pass the automated rubric, created in the last 120 days).

> **Listing pause.** The last full indexing sweep (4 Oct) did not meet the #316 resume criterion, and no full sweep has run since. Skill pages are noindex and outside the sitemap, so skills don't lengthen Google's crawl queue; agent rows do. The owner lifted the pause for this batch on 15 Oct, as for batch 3.

## How this review was made

1. **Cross-check** against the roster, `REVIEWED_REJECTED` and the batch 3 pre-screen (`new-listing-candidates-2026-10-08.md`). Five of the 50 were already open from batch 3: three closer-look repos (moli, penguin-harness, agentconnect) and two held back by the README read (Easel, delegate-skills). One is a rejected repo under a new owner (`DSH-EAC/EAC-Desktop` now redirects to `Ebony-Vinyl/EAC-Desktop`).
2. **Checks on every repo:**
   - a README read and the file tree (`SKILL.md` files, plugin manifests, package files);
   - licence, with each `NOASSERTION` resolved by reading the LICENSE file;
   - forks-to-stars ratio, contributors, commits and stars per day (the batch 1 inorganic test);
   - for the fast risers, activity that stars can't fake: watchers, distinct issue and PR authors, release downloads, package downloads.
3. **No star-history check was possible.** GitHub's stargazer list now returns 404 for repositories we don't own, so star timelines and stargazer accounts can't be sampled.

## A. Added (21)

**Agents and tools (7)**

| Repo | Stars | Category | Why it fits | Signals |
|---|---:|---|---|---|
| dzhng/jevgrep | 2,656 | Protocols & Tool Integration | Code-search CLI for coding agents | npm `@dzhng/jevgrep`, 1,992 downloads a week; 8 contributors, 213 commits |
| Prism-Shadow/penguin-harness | 2,502 | Agent Frameworks | Batch 3 closer look: runs its own harness and self-improvement framework | 19 contributors, 754 commits, 103k release downloads |
| ai4s-research/open-science | 1,790 | Research & Data | Research workbench with its own agent runtime; a separate project from the listed `aipoch/open-science` (different first commit and authors), named "Open Science Desktop" | LICENSE is MIT; 17 contributors, 578 commits, 42 issue authors |
| xzf-thu/VoiceMem | 2,488 | Memory & Knowledge | Memory service for voice agents (precedent: tigerless-labs/agent-memory) | Apache-2.0; 5 contributors, 78 commits, 113 watchers |
| Intuition-Lab/personal-model | 1,336 | Memory & Knowledge | Local long-term memory runtime with an MCP server | 9 contributors, 343 commits |
| BitMiracle-AI/Dormice | 1,516 | Sandboxes & Runtimes | Self-hosted, E2B-compatible agent sandboxes | 3 contributors, 323 commits; its README says it isn't production-ready |
| cosmtrek/mindwalk | 1,369 | Observability & Evaluation | Replays coding-agent sessions on a map of the codebase (precedent: deer-flow/llm-space) | 5 contributors, 62 commits |

**Skills (14)**, each shipping a `SKILL.md` or a plugin manifest under an open-source licence. Most are thin (one to four contributors), which batch 3 accepted.

- Design and writing: oil-oil/oil-motion, oil-oil/beautify-github-readme, oil-oil/oil-ui, larashero3-dotcom/writing-dna-skill, coji/natural-japanese, nanaism/yomiyasu
- Video: HUANGCHIHHUNGLeo/claude-real-video, edenfunf/reelmimic, Alisa0808/vox-director (needs an Atlas Cloud API key), veedstudio/open-edit
- Workflow and output style: kharmanskyi/open-steps, petergyang/human-review, alexgreensh/attention-span (AGPL-3.0), snflkd/fluent-korean

## B. Held (7): one question each

| Repo | Question |
|---|---|
| lexmount/moli | Scope is settled (obscura, camofox-browser and steel-browser are listed), and it is real software: 18 contributors, 1,879 commits, 15.8k binary downloads. But stars rose by 3,900 in five days with forks at 2.6%, and only 4 distinct authors appear in its last 100 issues and PRs. Add anyway? |
| memorax-ai/memorax-code | MIT client for the MemoraX memory service: a 90-day guest mode, then an account. In scope? |
| 0xsline/OpenChatCut | A video editor with a built-in agent and an MCP server. An app (the onlook precedent) or agent-first (the anything-analyzer precedent)? |
| androoAGI/starnet | Its own multi-agent harness, but 2 contributors made 12,921 commits and 47k files in 121 days. Healthy, or generated churn? |
| coldteadotai/pr-lens | Draws pull requests as diagrams, as a GitHub App plus a skill. Developer tool or skill? |
| Jakeschincariol/replica-skill, Jakeschincariol/linkedin-agent-skill | Each is a single commit by one author. Revisit once there is some history. |

## C. Rejected (22), with the precedent

- **Already ruled on, back under a new owner:** `Ebony-Vinyl/EAC-Desktop` is the rejected `DSH-EAC/EAC-Desktop`.
- **Held in batch 3:** `ZJU-REAL/Easel` (OpenClaw does the agent work) and `amElnagdy/delegate-skills` (delegates to external implementer CLIs).
- **Supervisory harness class (#180):** `agentconnect-md/agentconnect` (brings Claude Code, Codex and other ACP agents into chat; answers its batch 3 question), `amplifthq/opentag`, `egoist/waku`, `eneskirca/nodeterm` (also Business Source License 1.1), `AMAP-ML/LongHorizon-Harness`.
- **DeepSeek Harness add-ons:** `Fei2411/DeepSeek-Bot`, `PC2005-cloud/dsh-pet`.
- **Licence not open source:** `feitangyuan/onetake` (PolyForm Noncommercial 1.0.0), `Pluviobyte/rnskill` (CC BY-NC 4.0).
- **Courses:** `hahhforest/pi-textbook`, `SaladDay/pi-from-scratch`.
- **Not an agent:** `TokenRhythm/NeoHorse` (model weights), `HanyuanWang/LiveStream-Agent-Studio` (vertical Windows app, 12 commits), `adtexterry-lgtm/unigit-ecosystem` (a brand page, 3 commits), `diudiu-tech/delivery-harness` (its README calls it an educational MVP with mock tools).
- **Superseded or a copy:** `icebird1998/drawio-scientific-illustrator` (development moved to the listed `icebird1998/scientific-illustrator`); `jiwoochris/artex-ko` (a 10-day-old translation of `Autumn-27/ARTEX`, forks exceed stars).
- **Stars without activity:** `Appllama/appllama-skills` (2,746 stars, 10 commits, no PRs, no watchers), `ray-r-ren/agent-apprenticeship` (6 commits).

## Findings for the pipeline

1. **Rejections still don't follow renames or owner moves.** `Ebony-Vinyl/EAC-Desktop` came back the same way `agent-orchestrator` did in batch 3. Both names are now in `REVIEWED_REJECTED`; resolving GitHub's redirect before matching would close the gap.
2. **The inorganic test has lost its best tool.** Without stargazer lists, star velocity can only be cross-checked against activity that stars don't buy: watchers, distinct issue authors, release and package downloads.

## Outcome (owner, 15 Oct)

Owner: "add the 21, reject the 22, hold the seven". That lifts the #316 pause for this batch, as batch 3 did.

**Added (21):** section A. Names follow each project's own spelling; `ai4s-research/open-science` is "Open Science Desktop" because the listed `aipoch/open-science` holds the `open-science` slug. No new slug collides with a listed or retired (410) profile.

**Packages:** `scripts/verify_package_identifiers.py` verified 5 against their repos (npm: `@dzhng/jevgrep`, `@prismshadow/penguin-core`, `human-review`; PyPI: `personal-model`, `claude-real-video`). The other 16 carry no identifier rather than a guess; most obvious names belong to unrelated projects.

**Rejected (22)** into `REVIEWED_REJECTED`, including the new name of the rejected EAC-Desktop. The seven in B stay open and will reappear in later weekly reports.

**Rank-churn gate:** the 21 rows were scored in a local `--pending-only` run against the live 15 Oct board (08:08 UTC), inserted into it, and re-ranked. The comparator reproduces live ranks exactly (0 of 1,742 mismatches).
- **Agents:** no top-100 row moves. PenguinHarness enters at **#224 (76.5, B)** and Jevgrep at **#334 (71.1, B)**, both with npm provenance. The other five enter at grade D (18–33, confidence 0.5–0.67: young repos, mostly without packages). Existing agents move 1.7 places on average, at most 7, and none above #224.
- **Skills:** Human Review enters at **#92 (61.2, C)**, earned by its npm package with provenance, so the nine skills at #92–#100 each drop one place. The other 13 enter at grade D, #355–#383.
- The new rows raise no eligibility warnings or package failures (the one package failure, `AynOps/AynOps`, is already on the live board). Scorecard was not pre-seeded, so OSSF data arrives from the hourly rotation within 24 hours of the deploy and may move some scores.
