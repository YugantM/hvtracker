# New listing candidates: batch 3 pre-screen (8 Oct 2026)

Discovery proposes; **the owner decides**. Nothing here is in `agents.json` yet.

> **Listing batches are paused (#316).** The resume criterion was not met at the last sweep (4 Oct): 0 of the 23 batch 1–2 profiles were indexed, and 7.3% of sitemap URLs were never crawled (the bar is under 2%). The next sweep runs Sunday 11 Oct. Adding any of these means lifting the pause or waiting for it to clear.

The owner's example, `morluto/rea`, is **already listed**: REA, 86.5, grade A, #66 overall, in Security & Guardrails, with its npm package tracked. It has been on the roster since before #225, which is why discovery skips it. The list below looks for projects like it that aren't listed yet.

## How this list was made

1. **Fresh discovery runs** on 8 Oct:
   - `discover_agents.py` found 1,018 repos that pass the automated rubric (licence, not a fork, not archived, pushed this year, 500+ stars) and are neither listed nor rejected.
   - `discover_skills.py` found 582 skill repos, 280 of them with structural skill evidence (`single_skill` or `skill_collection`).
2. **Two pools**, because the weekly report (`scripts/discovery_report.py`) shows only repos created in the last 120 days, on the assumption that older ones were already reviewed:
   - *Recent* (created on or after 10 Jun): 320 repos, 261 never surfaced in any earlier screening doc or shortlist.
   - *Older but never surfaced*: 178 repos, 77 of them with 2,000+ stars. A project like `rea` would sit in this gap if it weren't already listed.
3. **Pre-screen** against `docs/strict-inclusion-rubric.md` and the rulings recorded in `REVIEWED_REJECTED`:
   - the supervisory-harness class (#180);
   - DeepSeek Harness wrappers and presets;
   - provider proxies and the thin-wrapper boundary;
   - non-agents;
   - lists and courses;
   - inorganic stars.
4. **Checks run for everything in A and B:**
   - licence (each `NOASSERTION` resolved by reading the LICENSE file);
   - forks-to-stars ratio, contributors, commit count and stars per day (the batch 1 inorganic test);
   - a README read wherever the description left scope unclear.

   As in batch 1, every approved repo also gets a full README read and its Scorecard scan pre-seeded before it is added.

## A. Propose (40)

**Agents, harnesses and frameworks (23)**

| Repo | Stars | Category | Why it fits | Signals |
|---|---:|---|---|---|
| Companion-Inc/feynman | 9,914 | Research & Data | "The open source AI research agent" | 14 contributors, 730 commits, forks 11% |
| apache/maka | 5,696 | Coding Agents (confirm) | Apache Incubating agent harness with its own loop, benchmarked per task | 135 contributors, 4,951 commits |
| agentscope-ai/agentscope-java | 5,889 | Agent Frameworks | Java port of the listed AgentScope (precedent: huggingface/tau) | 194 contributors |
| MiniMax-AI/minimax-code | 1,999 | Coding Agents | MiniMax's terminal coding agent | 14 contributors, forks 13% |
| unreallabsai/unreal-agent | 2,177 | Agent Frameworks | Async-first harness library plus runner and TUI | 6 contributors; 136 stars/day, forks 6% |
| bubbuild/bub | 1,680 | Agent Frameworks | Small agent runtime with plugins | 38 contributors |
| rivet-dev/agents | 1,600 | Sandboxes & Runtimes | Durable process per agent, memory across restarts | 19 contributors |
| NVIDIA-NeMo/labs-OO-Agents | 2,271 | Agent Frameworks | Python agent framework (LICENSE is Apache-2.0; GitHub shows NOASSERTION) | 32 contributors |
| ANative-Lab/EvoAgentX | 3,366 | Agent Frameworks | Self-evolving agent framework (LICENSE is MIT; renamed from EvoAgentX/EvoAgentX) | 33 contributors |
| ZJU-REAL/Easel | 3,277 | Research & Data (confirm) | Social-media agent: finds trends, writes and publishes | 18 contributors |
| agentrhq/webcmd | 2,669 | Browser & Computer Use | Self-learning agent browser | 26 contributors, forks 58% |
| milind-soni/OpenMausBot | 4,209 | Browser & Computer Use | Agent with its own virtual machine | 115 contributors |
| lycorp-jp/sim-use | 1,396 | Browser & Computer Use | Gives agents control of iOS Simulator and Android devices | 15 contributors |
| Pinvou/pinvou-agent | 2,391 | UI & App Builders | Desktop agent for tools, files and workflows | 9 contributors |
| MemTensor/memmy-agent | 2,077 | Memory & Knowledge | Personal agent plus shared local memory hub | 42 contributors |
| tigerless-labs/agent-memory | 2,646 | Memory & Knowledge | Long-term memory runtime for agents | 8 contributors |
| pipeshub-ai/pipeshub-ai | 3,820 | Memory & Knowledge | Context layer: company knowledge for agents | 70 contributors |
| latitude-dev/latitude-llm | 4,715 | Observability & Evaluation | Observability for agents | 44 contributors, 5,884 commits |
| deer-flow/llm-space | 1,993 | Observability & Evaluation | Desktop app to prototype, inspect and evaluate harness runs (sister to the listed DeerFlow) | 26 contributors |
| samugit83/redamon | 2,975 | Security & Guardrails | Self-hosted AI penetration-testing framework | 22 contributors, forks 21% |
| beenuar/AiSOC | 2,389 | Security & Guardrails | AI SOC with LLM-agent triage | 23 contributors |
| Mouseww/anything-analyzer | 3,743 | Security & Guardrails | Protocol analysis with an MCP server for agents (built agent-first, unlike the rejected pre-agent tools) | 10 contributors |
| google/mantis | 2,381 | Coding Agents (confirm) | Toolkit for coding agents to find, reproduce and fix bugs | 3 contributors |

**MCP servers (3)**

| Repo | Stars | Signals |
|---|---:|---|
| doobidoo/mcp-memory-service | 2,000 | 114 contributors, 3,567 commits |
| hi-godot/godot-ai | 2,867 | 33 contributors (MCP server for the Godot engine) |
| redhat-et/ripwire | 2,424 | 29 contributors (Red Hat's context search CLI plus MCP server) |

**Skills (14)**

| Repo | Stars | Signals |
|---|---:|---|
| cathrynlavery/diagram-design | 46,143 | 49 contributors; 264 stars/day, forks 6.4% |
| virgiliojr94/book-to-skill | 34,202 | 46 contributors; 214 stars/day, forks 10.5% |
| titanwings/distilly | 25,411 | 4 contributors; 132 stars/day, forks 8.6% |
| latent-spaces/brag | 14,326 | 10 contributors (`/brag` launch-video skill) |
| rehan-remade/universal-modder | 5,579 | 45 contributors; **697 stars/day** (8 days old), forks 9.3% |
| iflytek/skillhub | 5,159 | 47 contributors (self-hosted skill registry; could be a listing rather than a skill, see B) |
| PenglongHuang/chinese-novelist-skill | 3,331 | 2 contributors, forks 14% |
| QingYunA/answer-me-with-html | 2,319 | 13 contributors; 386 stars/day (6 days old) |
| amElnagdy/delegate-skills | 2,334 | 32 contributors |
| majidmanzarpour/threejs-game-skills | 2,449 | 1 contributor, 11 commits |
| kaankiziltug/logo-design-skill | 2,364 | 2 contributors; 197 stars/day |
| tourmind-com/Tourmind-Booking-Skills | 1,680 | 5 contributors (vendor skill for its own booking service) |
| ai-evals-course/evals-skills | 1,470 | 4 contributors |
| Oldcircle/geo-sleuth | 1,440 | 1 contributor |

The last five rows are thin (one or two contributors, few commits). Batch 1 held `internet-court-skill` for exactly that shape. Approve them only if thin skills are acceptable.

## B. Closer look (12): one question each

| Repo | Stars | Question |
|---|---:|---|
| lexmount/moli | 13,781 | Inorganic flags: 234 stars/day with forks at 2.5%. It's also browser infrastructure rather than an agent. Hold for a star-history check? |
| danielmiessler/LifeOS | 19,362 | "General purpose AI harness": its own agent loop, or a configuration layer on top of Claude Code (the supervisory class)? |
| Twigpine/zero | 1,697 | MIT terminal coding agent, but its sibling `Twigpine/openclaude` is "derived from Anthropic's Claude Code CLI… proprietary". Need proof zero isn't. |
| onecli/onecli | 3,565 | "Agent harness for teams": does it run its own agent or host external CLIs? |
| Prism-Shadow/penguin-harness | 2,458 | Multi-agent app platform ("agents build agents"): framework, or a general app builder? |
| superplanehq/superplane | 7,714 | Apache-2.0 core with an `/ee` enterprise directory. Open-core is acceptable by roster precedent (n8n, Dify)? |
| phronesis-io/eigenflux | 1,918 | Agent communication network (A2A-adjacent). Licence is Apache-2.0 plus a trademark clause; forks only 1.7%. |
| mnfst/llm-gateway | 7,566 | Provider gateway "for agents and harnesses": LLM Gateways & Infra (LiteLLM precedent), or the thin-wrapper boundary? |
| anus-dev/ANUS | 6,551 | Terminal coding agent with 6 contributors and 21 commits for 6.5k stars. Original code or a repackaged fork? |
| jordan-gibbs/hyperresearch | 3,806 | Turns Claude Code or Codex into a research agent: skill collection, or the supervisory class? |
| agentconnect-md/agentconnect | 1,456 | "Multi-agent alternative to Claude Tag": its own agents, or a router over external CLIs? |
| OpenSparX/MasterAgent | 1,646 | On-device agent framework with forks at 1.8%, 4 contributors and 27 commits: inorganic? |

## C. Reject (recommended), with the precedent

**Already ruled on, resurfacing under a new name**
- `OrchestratorInc/agent-orchestrator` **is `agentwrapper/agent-orchestrator`, renamed** (GitHub redirects). Rejected by the owner on 2026-07-07 as a supervisory harness. Discovery re-proposed it because `REVIEWED_REJECTED` matches by the old name.

**Adoption not earned by the current project**
- `feder-cr/invisible_dots` (31,867 stars): this is the renamed `feder-cr/Auto_Jobs_Applier_AIHawk` (2024 job-application bot). The new `feder-cr/dots` project (2,612 stars in the 5 Oct discovery issue) now redirects into it, so it inherits the old project's stars. It also advertises being "undetectable by anti-bot".
- `cinderline/northcinder` (forks 0.8%, 2 contributors, 6 commits) and `filtalgo/Filtmall-Shopping-Skill` (forks 1.1%, 21 commits): the inorganic pattern.

**Licence**
- `Twigpine/openclaude`: its LICENSE says it "contains code derived from Anthropic's Claude Code CLI. The original Claude Code source is proprietary."
- `EKKOLearnAI/ekko-studio`: Business Source License 1.1.
- `sugarforever/chat-ollama`: Apache-2.0 modified to restrict commercial use. Dify's modified licence was accepted, so this is the owner's call, but the rubric says open source.
- `Alishahryar1/free-claude-code`: NOASSERTION, and a provider proxy (below).

**Deprecated**
- `21st-dev/magic-mcp`: README: "Magic MCP is now the 21st MCP… This package remains published as a thin compatibility proxy."

**Supervisory harness class (#180): the agent work is delegated to external CLIs**
- `loopx-project/loopx`, `zeronsh/zeron`, `HarnessMD/munder-difflin`, `mvschwarz/openrig`, `spacering-net/codeg`, `happier-dev/happier`, `BytePioneer-AI/codex-host`, `hardbeat920/monocode`, `codeaholicguy/ai-devkit`, `Gaurav-Gosain/tuios`, `Gentleman-Programming/gentle-ai`, `iAmCorey/Wake`, `AltanS/collie`, `LodyAI/Lody`, `Louis-CFM/coucou`.
- Wrappers of a listed agent: `vastsa/PI-Desktop` (pi), `abundantbeing/hermes-browser-extension` (Hermes Agent).

**DeepSeek Harness add-ons (precedent: 2026-09-29 rulings on DSH wrappers and presets)**
- `Ebony-Vinyl/dsh-our-free-model`, `YuJunZhiXue/dsh-purge` (a jailbreak), `Small-tailqwq/dsh-deep-whale` (a skin), `bowenliang123/dsh-context`, `DSH-EAC/EAC-Desktop`, `xmanrui/dsh-im`, `shaobeichen/dsh-pocket`, `AdamPlatin123/dsh-plugin-radar`, `Clearailhc/clearai-dsh`, `Devin-AXIS/deepseek-design`, `Minglink/dsh-infinite-gen-4` (also asks for stars).

**Provider proxies and free-model access (thin-wrapper boundary)**
- `yetone/magpie`, `omnirush-ai/omnirush-gui`, `rebel0789/codexpro`, `sums001/Windows-Copilot-API` (reverse-engineered Copilot API), `HarnessRouter/harnessrouter`, `monid-ai/monid`.

**Not an agent, or agent support is incidental**
- Apps and tools: `onlook-dev/onlook` (design tool, waitlist), `DuarteSantos8/openGym`, `KKKKhazix/AIHOT`, `Kuddev/pebrel`, `shader-effects-inc/shaders`, `dream-num/univer`, `dream-num/univer-workspace`, `tianma-if/edgeever`, `px0-ai/px0`, `feigeCode/navop`, `Augani/dory`, `incoai/splash`, `unstablebuild/rune`, `drawdb-io/drawdb`, `docmost/docmost`, `Molunerfinn/PicGo`, `asciimoo/hister`, `devlikeapro/waha`, `xpf0000/FlyEnv`, `bostrot/wslmanager`, `CrossPaste/crosspaste-desktop`, `VoidenHQ/voiden`, `zhouxiaoka/autoclip`, `HBAI-Ltd/Toonflow-app`, `EthanYoQ/AI-Novel-Writer`, `every-app/open-seo`, `Javis603/token-monitor`, `freestylefly/WeChatBridge`, `fancydirty/mediary-scout`, `Observal/Observal` (registry for agent extensions).
- Infra where agents are one use among many: `wasmerio/wasmer`, `TykTechnologies/tyk`, `budtmo/docker-android` (2016), `infobyte/faraday` (2013), `cortex-docs/cortex`, `sopaco/deepwiki-rs`, `raullenchai/Rapid-MLX`, `SemiAnalysisAI/InferenceX`, `chrisryugj/kordoc` (document conversion), `Evil0ctal/Douyin_TikTok_Download_API`.
- Scrapers and account tools: `eatmoreduck/boss-zhipin-scraper` (bypasses anti-scraping), `Mahanaicoach/google-maps-scraper-kit`, `yacuo/check-cc`.
- Licence NOASSERTION, unresolved: `jundizhou/easy-stock`, `aoci-spec/aoci-code`, `pgrundev/pgbot`, `brayonpi/hexstellar`, `fy-agent/fyagent`, `lemomo-ai/lemo-opuscar`, `Vincentwei1021/video-talkcraft`, `Vincentwei1021/anything2explainer`.

**Lists, courses and collections**
- `thedaviddias/Front-End-Checklist`, `harvard-edge/cs249r_book`, `dipakkr/awesome-ai-engineering`, `liyupi/ai-guide`, `tradecatlabs/vibe-coding-cn`, `walkinglabs/learn-harness-engineering`, `lopopolo/harness-engineering`, `aliyun/ai-agent-handbook`, `ANative-Lab/Awesome-Self-Evolving-Agents`, `andyrewlee/awesome-agent-orchestrators`, `flypythoncom/python`, `ChenLiu-1996/figures4papers`, `ciembor/agent-rules-books` (a prompt collection), `crafter-station/petdex` (a gallery).

## Findings for the pipeline (separate from the batch decision)

1. **Rejections don't follow renames.** `REVIEWED_REJECTED` and the roster check match `owner/name` as typed, so a renamed reject comes back (agent-orchestrator). Discovery should resolve GitHub's redirect before matching, or the rejection list should store the new name too. Phase 8 noted the same gap for duplicates.
2. **Star inheritance isn't caught.** The inorganic test looks at forks and velocity. A new project moved into an old popular repo passes both. A cheap flag: `created_at` far older than the first commit on the current default branch, or a recent repository rename.
3. **The weekly report hides never-reviewed older repos.** It assumes anything older than 120 days "had its chance". 178 older candidates (77 with 2,000+ stars) were never surfaced in any screening. The report could add a short "older, never surfaced" section.
