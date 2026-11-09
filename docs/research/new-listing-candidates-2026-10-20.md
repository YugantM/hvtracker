# New listing candidates: batch 5 review of weekly report #371 (21 Oct 2026)

Source: issue #371, "New listing candidates — week of 2026-10-19" (50 of 925 candidates that pass the automated rubric, created in the last 120 days). Owner, 21 Oct: "do a proper review, keep the eligible ones and remove the rejected and record". So this batch adds what passes the review, records the rejections, and holds the rest with one question each.

> **Listing pause.** The resume criterion is still not met: last full sweep 19 Oct, 0 of 23 batch 1–2 profiles indexed then, 8.7% of sitemap URLs never crawled. Manual indexing requests have since indexed 10 of the 23 (by 20 Oct). As with batches 3 and 4, the owner chose to add before the criterion was met. Skill pages are noindex, so only agent rows lengthen Google's crawl queue.

## How this review was made

1. **Cross-check** against the roster, `REVIEWED_REJECTED` and last week's holds. Six of the 50 are repos held on 15 Oct (moli, OpenChatCut, pr-lens, memorax-code, and the two Jakeschincariol skills). They stay held. The other 44 are new.
2. **Checks on every new repo:**
   - the README and the file tree (`SKILL.md` files, plugin manifests, package files);
   - licence, with each `NOASSERTION` resolved by reading the LICENSE file;
   - forks-to-stars ratio, contributors, commits and stars per day;
   - watchers and distinct issue and PR authors, the activity that stars don't buy;
   - GitHub's current name, to catch renames.
3. **Category precedents** come from the live board: personal agents under Agent Frameworks (QwenPaw, CowAgent, nanobot), computer use under Browser & Computer Use, KiCad and IDA servers under MCP Servers, context tools as skills (context-mode, token-optimizer).

## A. Added (16)

**Agents, tools and MCP servers (11)**

| Repo | Stars | Category | Why it fits | Signals |
|---|---:|---|---|---|
| onehumanbeing/esp32-iphone-agent | 3,456 | Browser & Computer Use | An agent that operates a real iPhone through a $7 ESP32 (AirPlay screen, USB HID input) | 5 contributors, 52 commits, 20 issue authors |
| nano-muse/nanoMuse | 2,009 | Agent Frameworks | Personal agent with phone, desktop, web console and relay, all in the repo (GPL-3.0) | 20 contributors, 1,618 commits, 37 issue authors |
| aakarim/OpenLore | 1,539 | Memory & Knowledge | Shared Markdown knowledge for every agent on a team, over SSH and MCP | 5 contributors, 265 commits; forks only 0.7% |
| rociiu/talorys | 1,362 | Agent Frameworks | Personal agent that runs entirely in your own Cloudflare account | 12 contributors, 114 commits, 18 issue authors |
| 2akouwu/reverify | 1,310 | Observability & Evaluation | Deterministic tools check every claim the model makes before it counts | 4 contributors, 83 commits; OpenSSF Scorecard 6.7 |
| mixelpixx/Konnect | 1,349 | MCP Servers | KiCad 10 plugin: 228 MCP tools for schematic and PCB design (AGPL-3.0; precedent kicad-mcp-pro) | 38 contributors, 1,168 commits |
| HexRaysSA/ida-mcp | 1,328 | MCP Servers | The official IDA MCP server from Hex-Rays (precedent ida-pro-mcp) | 5 contributors, 98 commits |
| Leonxlnx/earshot | 2,026 | Protocols & Tool Integration | Audio analysis and synthesis for coding agents | 1 contributor, 33 commits, 6 days old: thin, as batch 3 accepted |
| vshulcz/deja-vu | 1,269 | Memory & Knowledge | Indexes past coding-agent sessions so agents stop re-debugging | 60 contributors, 2,384 commits; OpenSSF Scorecard 8.6 |
| awlevin/typesafe-computer-use | 1,251 | Browser & Computer Use | Drives a Mac toward a goal with a classifier and deterministic screen reading | 8 contributors, 116 commits |
| ant-research/AntOmniEvo | 1,221 | Agent Frameworks | Ant Research's auto-evolution framework for agent skills, workflows and algorithms (precedent EvoAgentX) | 6 contributors, 64 commits, 35 watchers |

**Skills (5)**: kajisho5/ffmpeg-skill (14 skills plus an MCP server, 9 contributors), dzhng/skills (34 skills; listed as "Dzhng Skills" because the name alone is generic), mikehasa/golive-skill ("GoLive"), openfilm/openfilm (an agent-first video skill set, like batch 4's video skills), ranxianglei/billion-context (a context-compression plugin for Claude Code, Codex and OpenCode; LICENSE is MIT, 88 contributors).

## B. Held (9): one question each

| Repo | Question |
|---|---|
| tangency-labs/solidcraft, pireel/pireel, leemysw/yovoice | Apps that agents can drive through MCP: a CAD app, a video editor, an audio studio. The same question as OpenChatCut last week: an app (the onlook precedent) or agent-first (the anything-analyzer precedent)? One ruling settles all four. |
| lexmount/moli, 0xsline/OpenChatCut, coldteadotai/pr-lens, memorax-ai/memorax-code, Jakeschincariol/replica-skill, Jakeschincariol/linkedin-agent-skill | Held on 15 Oct; the questions are in new-listing-candidates-2026-10-13.md. moli is now at 19,983 stars. |

## C. Rejected (25), with the precedent

- **Already ruled on, under a new name:** `jiwoochris/artex-global` is the `artex-ko` rejected on 15 Oct, renamed.
- **A re-upload:** `trhhubsd/ARTEX`, posted by an unrelated account; the original `Autumn-27/ARTEX` is gone (404), so authorship can't be established.
- **DeepSeek Harness add-ons:** `T-Auto/dsh-ops`, `DSH-APP/DSHA` (an Android launcher), `elysia395/dsh-wallpaper-engine`, `corrinehu/dsh-workbuddy-connect` (also discontinued, going offline 22 Oct), `Derpyu520/qq-bridge`.
- **Provider proxies and relays:** `ardeyouxipianyi/workbuddy2api-hub` (multi-account reverse proxy), `Folkbench/folkbench` (a relay switcher with sponsored relays), `amontlabs/lcu` (exposes the Codex app's computer-use runtime without Codex authentication).
- **Supervisory class (#180):** `autonomous-ai/openharness`, `amplifthq/openmeld` (same org as the rejected opentag).
- **Wrappers of a listed runtime:** `penso/herdr-gpui` and `devswha/herdr-web-ui` (third-party clients for the listed herdrdev/herdr); `AhmadHassan-BTed/AutoSwarm-Shadow-Adapter` (an add-on for AutoSwarm, renamed from OpenOPC-Shadow-Adapter; both names recorded; one contributor, forks 0.1%).
- **Not an agent:** `Gathin23/cleanyourtv` (TV debloat scripts), `deeplethe/solid-glass` (a UI design system), `krishhgg/Insomnia` (a keep-awake app), `croffasia/itsaplan` (an issue tracker), `marclou/mailcheap` (a newsletter app), `l0ng-ai/tty7` (a terminal).
- **Courses and collections:** `youngyangyang04/llm-master`, `soumatheusgomes/vibe-coding-toolkit`.
- **Stars without matching activity:** `feder-cr/git-ai` (2,404 stars in the 19 Oct report, 909 on 21 Oct, which usually means GitHub removed fake stars; same owner as the 8 Oct star-inheritance case), `maxrave-dev/kotlin-footguns` (one contributor, 11 commits, forks 0.4%).

## Findings for the pipeline

1. **Renames keep defeating the rejection list.** `artex-ko` came back as `artex-global` within a week; `OpenOPC-Shadow-Adapter` arrived already renamed. Resolving GitHub's current name before matching `REVIEWED_REJECTED` would close this; it is the third recurrence (agent-orchestrator, EAC-Desktop, ARTEX).
2. **A falling star count is a strong inorganic signal.** git-ai lost 60% of its stars in two days. The weekly report could store each candidate's star count and flag drops on the next run.

## Outcome and rank-churn gate (21 Oct)

**Recorded:** 16 rows in `agents.json` (8 with package ids verified against their repos: npm `create-talorys`, `@vshulcz/deja-vu`, `ffmpeg-skill`, `golive`, `openfilm`, `billion-context`; PyPI `reverify`, `ida-mcp`), and 26 entries in `REVIEWED_REJECTED` (the 25 repos plus AutoSwarm-Shadow-Adapter's old name). No new slug collides with a listed or retired (410) profile.

**Gate.** The 16 rows were scored in a local `--pending-only` run against the live 21 Oct board (08:08 UTC), inserted and re-ranked. The comparator reproduces live ranks exactly (0 of 1,763 mismatches). New this time, after batch 4: each row is also re-scored with `what_if_score` at Scorecard 3.0, 5.0 and 7.0, because our scan reaches new rows only after the deploy. Checked first against batch 4: PenguinHarness re-scores to 76.0 without Scorecard and 85.2 with its 4.4, matching the live board.

- **Agents:** no top-100 row moves. deja-vu enters at **#203 (77.7, B**; its OpenSSF Scorecard 8.6 is already included), Hex-Rays IDA MCP at **#352 (70.6, B)**, Reverify at #652 (61.3, C), the other eight at D. Existing agents move 2.3 places on average, at most 11, none above #203. **Range:** IDA MCP is the only row that could reach the top 100, at about #91 if its Scorecard comes in near 7.0 (#147 at 5.0).
- **Skills:** openfilm enters at **#25 (75.1, B)** and ffmpeg-skill at **#26 (74.7, B)**, so 76 skills from #25 to #100 move down 1–2 places. Both earn it the way their neighbours do: npm provenance, signed commits (openfilm 100%), maintenance at the maximum, 1,500–3,000 weekly downloads. billion-context, golive and Dzhng Skills enter at D. **Range:** with Scorecard 5.0, openfilm and ffmpeg-skill would reach about #11; billion-context about #29 and golive about #55.
- No new eligibility warnings or package failures (the one failure, `AynOps/AynOps`, is already on the live board).
