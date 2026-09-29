# New listing candidates — first batch (29 Sep 2026)

Phase 7, task 7.1. Discovery proposes; **the owner decides**. Nothing here is
in `agents.json` yet.

## How this list was made

`discover_agents.py` (now also searching repos created in the last 120 days,
because each query only returns the top 100 by stars and big topics crowd new
projects out) → 1,046 repos pass the automated rubric (license, not a fork,
not archived, pushed this year, 500+ stars) → `scripts/discovery_report.py`
keeps the 60 created in the last 120 days that aren't lists or course
material. I pre-screened those 60 against the owner's past rulings in
`REVIEWED_REJECTED`. The screen is based on each repo's description; before
anything is added, each approved repo also gets a README check and the
inorganic-stars check (`sv-number/mcp-server` precedent: stars vs forks,
contributors, and commit history), and its Scorecard scan is pre-seeded.

## A. Propose for the first batch (30)

**Agents, harnesses and frameworks with their own agent logic (15)**

| Repo | Stars | What it is |
|---|---|---|
| XiaomiMiMo/MiMo-Code | 13,549 | Xiaomi's coding agent |
| google/artemis | 10,628 | Natural-language Android automation agent |
| zai-org/ZCode | 7,145 | Z.ai's coding agent harness |
| Human-Agent-Society/reef | 7,241 | Infrastructure for self-improving agents |
| truefoundry/trueforge | 6,012 | Open-source agent runtime |
| alphaXiv/OpenResearch | 5,928 | Research agents |
| CopilotKit/OpenBot | 5,707 | AI coworkers, each with its own computer |
| TencentCloud/Octop | 5,683 | Self-hosted multi-agent assistant |
| SenteLabsAI/OpenExecutive | 5,374 | Multi-agent "executive team" |
| ApodexAI/FrontierAgent | 4,688 | Agent framework |
| fuxicodex/Fuxi | 3,363 | Terminal coding agent |
| NVlabs/SoL-Pi | 3,198 | Auto-research loops for agent harnesses |
| huggingface/tau | 2,875 | Python port of Pi's coding agent |
| Player-YN/BrowserKitten | 2,882 | Selection-first web agent for Chrome |
| hypit-ai/hypit | 17,455 | Video-cloning agent workflow |

**Skills (10)**

| Repo | Stars | What it is |
|---|---|---|
| cloudflare/security-audit-skill | 23,016 | Multi-phase security-audit skill for coding agents |
| Tencent/BrowserSkill | 7,866 | Lets agents use a real logged-in browser |
| internet-court/internet-court-skill | 6,302 | Agent-to-agent commerce mandates |
| larashero3-dotcom/lieflat-charts | 5,791 | Data-visualisation skill |
| microsoft/skill-recorder | 4,162 | Records a work session into a Copilot skill |
| isjiamu/gzh-design-skill | 3,864 | Markdown → WeChat article layout skill |
| yanliudesign/mono-color-skill | 3,304 | Editorial print-image skill |
| Forward-Future/loopy | 3,157 | Library of agent loops + installable skill |
| rlaope/oh-my-hermes | 3,019 | Plugin bundle for Hermes Agent |
| ScrapeCreators/social-media-research-skills | 2,938 | Social-media research skills |

**MCP servers and agent tools (5)**

| Repo | Stars | What it is |
|---|---|---|
| Waishnav/devspace | 5,166 | Coding-agent harness exposed over MCP |
| totec448-spec/chat-on-steroids | 4,102 | Local MCP capabilities for ChatGPT |
| zvec-ai/zvec-grep | 3,827 | Local-first search built for agents |
| superdesigndev/treg | 3,800 | Gateway for agent tools ("OpenRouter for tools") |
| Ryze-AI-Adgent/open-seo-mcp-skills | 2,882 | SEO MCP server + skills |

## B. Needs a closer look (11)

The description alone doesn't settle which side of the boundary these are on.

| Repo | Stars | Question |
|---|---|---|
| yc-software/qm | 15,282 | "Multiplayer agent harness": its own agent, or a supervisory harness (#180 class)? |
| trailhq/Graft | 9,395 | Speeds up Claude Code/Cursor/Codex: a tool for agents, or does it serve them without being one? |
| genspark-ai/genoffice | 8,140 | AI office suite: are there agents in it, or AI features? |
| spinabot/brigade | 8,381 | "Personal intelligence": too vague to classify |
| deeplethe/utopia | 7,980 | "Enterprise world model": model, not an agent? |
| trycompai/crm | 10,960 | "CRM designed for AI agents": an app agents use |
| img2threejs/img2threejs | 17,175 | Skill, agent, or app? |
| yetone/cumora | 3,908 | Team chat with agents as members: platform or harness? |
| tutti-os/tutti | 3,787 | "Where people and agents build": too vague to classify |
| tigerless-labs/cost-xray | 3,010 | Inspects Claude Code/Codex API traffic: observability for agents |
| Tiger3807861189/J-Space-Cognition-Suite | 3,003 | Inference-time control suite: not an agent? |

## C. Recommend rejecting (19)

Each matches a past owner ruling. If you agree, these go into
`REVIEWED_REJECTED` so discovery stops proposing them.

| Repos | Reason (precedent) |
|---|---|
| anywhere-labs/dsh-desktop, dataelement/dsh-desktop, zhu1090093659/dsh-web, dsh-tauri/deepseek-harness-desktop, MeteorNOX/DeepSeek-Balance-Whale-Widget | Desktop/web wrappers around DeepSeek Harness, which is already listed. The wrapped runtime is the agent (`iofficeai/aionui`) |
| yjh051108/dsh-routing-suite, xiaobright/dsh-anchored-standard | Presets and routing config for DeepSeek Harness, not agents |
| chuspeeism/dashi-taskboard | Task panel that dispatches to Codex/DSH (`bloopai/vibe-kanban`) |
| lidge-jun/opencodex, miuuyy/codex-chatgpt-web, XiaoDuoYa/codex-with-chatgpt, wang2122/sprix-sage-router | Provider proxies and routers for coding-agent CLIs. They serve agents without being one (`simonlin1212/vibe-research`) |
| shengjidaguai-china/goutoujunshi | A prompt persona for Codex, not an agent |
| shy3130/tick-stock-panel, HiThink-Tech/Financial-API | Stock workbench and a market-data API, not agents |
| jub0t/Concat | Video editor with MCP support; agent support is incidental (`firerpa/lamda`) |
| Jakubantalik/thinking-orbs | UI loading components |
| AlephAITech/WorkBuddyGuide, buchidonggua/dg-ai-notes | A guide and personal notes |

## After approval

Approved repos are added with pre-seeded Scorecard scans (the add-agent
runbook), in one PR, with the rank-churn evidence gate. Rejected ones go into
`REVIEWED_REJECTED`. From now on a "New listing candidates" issue opens every
Monday (`.github/workflows/discovery-report.yml`).

## Outcome (owner, 29 Sep)

Owner: approve A, reject C. B (closer look) stays open.

- **Added (26)** after the README and inorganic-stars checks. Packages are
  recorded only when the registry entry points back at the repo, so
  `google/artemis` is listed without the `artemis` PyPI package (that name
  belongs to Artemis-xyz).
- **Held (4), then rejected by the owner** (also in `REVIEWED_REJECTED`):
  - `fuxicodex/Fuxi`: LICENSE reads "Proprietary. All rights reserved.", so
    the rubric's license check fails.
  - `Player-YN/BrowserKitten`: 2,882 stars vs 10 forks, 4 contributors,
    20 commits.
  - `ScrapeCreators/social-media-research-skills`: 2,938 stars vs 37 forks,
    2 contributors, 7 commits.
  - `internet-court/internet-court-skill`: 6,302 stars, 1 contributor,
    4 commits; MIT covers only its own parts.
- **Rejected (19)**: all of section C, now in `REVIEWED_REJECTED`.

Rank-churn gate: the 26 rows, scored in a pending-only run, were inserted into
the live board of 29 Sep and re-ranked (the comparator reproduces live ranks
exactly: 0 mismatches). No row in the top 100 of either class moves; the top 216
agents are unchanged. Two new rows land mid-board (`hypit-ai/hypit` 75.6 at
#217 and `Human-Agent-Society/reef` 73.7 at #253), so most agents below them
move 2 places. The other 24 enter at Grade D with 0.5–0.67 confidence (young
repos, no packages, no Scorecard yet), which moves the tail by up to 18 places.
Mean |Δrank| is about 2, well under the invariant's 15. Scorecard scans reach
the new rows within a day of deploy, because the scan uses the live roster and
takes the stalest repos first.
