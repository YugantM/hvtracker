"""
discover_agents.py — search GitHub for new AI agent candidates not yet in agents.json.

Output: candidates.json (if any found) — list of repos passing automated pre-checks.
Prints a summary to stdout.

NEVER auto-adds to agents.json. Discovery proposes; owner decides.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Repos the owner reviewed and rejected — never re-propose them. Keyed by
# lowercase "owner/name"; value records the decision for the audit trail.
# Add entries here whenever a manual-review candidate is declined.
REVIEWED_REJECTED = {
    "netease-youdao/lobsterai": (
        "2026-07-07 owner: rejected — OpenClaw is the execution runtime; "
        "thin-wrapper boundary (see docs/research/new-agent-candidates-2026-07-06.md)"
    ),
    "agentwrapper/agent-orchestrator": (
        "2026-07-07 owner: rejected — supervisory harness; external agents do "
        "the coding, lifecycle management not goal-directed orchestration"
    ),
    "mattpocock/sandcastle": (
        "2026-07-07 owner: rejected — sandbox automation delegating model "
        "interaction to coding-agent CLIs, not an agent framework"
    ),
    # 2026-07-14: the supervisory-harness class. Each of these is popular
    # (10k-30k stars) and resurfaces every sweep, but delegates the actual
    # agent work to an external coding-agent CLI — the same boundary that
    # disqualified agentwrapper/agent-orchestrator above.
    "iofficeai/aionui": (
        "2026-07-14 owner: rejected — desktop GUI wrapping OpenClaw/Claude "
        "Code/Codex; the wrapped CLI is the agent"
    ),
    "bloopai/vibe-kanban": (
        "2026-07-14 owner: rejected — kanban board that dispatches work to "
        "external coding agents; task management, not agent logic"
    ),
    "manaflow-ai/cmux": (
        "2026-07-14 owner: rejected — terminal emulator with tabs for coding "
        "agents; no agent logic of its own"
    ),
    "snarktank/ralph": (
        "2026-07-14 owner: rejected — loop that re-invokes Claude Code until a "
        "PRD is done; the loop is a harness, the CLI is the agent"
    ),
    "stablyai/orca": (
        "2026-07-14 owner: rejected — ADE for running a fleet of external "
        "coding agents in parallel; supervisory harness"
    ),
    "superset-sh/superset": (
        "2026-07-14 owner: rejected — editor for running many Claude Code/Codex "
        "instances; supervisory harness"
    ),
    # 2026-08-10 sweep. The 2026-08-06 batch (635557e5) reviewed 269 candidates
    # and recorded its ~228 declines only in the commit message, so this sweep
    # re-proposed all of them. Recording decisions here is the mechanism that
    # stops that; see docs/research/new-listing-candidates-2026-08-10.md.
    "generalaction/emdash": (
        "2026-08-10 rejected — desktop app running Claude Code/Codex/OpenCode "
        "in git worktrees; the #180 supervisory-harness class"
    ),
    "firerpa/lamda": (
        "2026-08-10 rejected — Android automation/reverse-engineering framework "
        "(frida, mitmproxy, ADB); agent support is incidental, predates agents"
    ),
    "bhouston/mycoder": (
        "2026-08-10 rejected — real coding agent with its own tool system, but "
        "214 days since last push; fails the activity requirement"
    ),
    "nikmcfly/mirofish-offline": (
        "2026-08-10 rejected — self-declared fork of 666ghj/MiroFish; the "
        "upstream is the canonical candidate and is now listed"
    ),
    "tastyeffectco/sandboxd": (
        "2026-08-10 rejected — self-hosted AI app builder whose coding agent "
        "does the work; the rubric excludes general UI app builders"
    ),
    # Adoption signals that do not survive inspection. Both would have entered
    # the leaderboard on stars they did not earn.
    "sv-number/mcp-server": (
        "2026-08-10 rejected — 492 stars on a 3-day-old repo with 0 forks, 0 "
        "watchers, 0 issues, 1 contributor and 71 KB of code; inorganic"
    ),
    "keon/browser-control": (
        "2026-08-10 rejected — repo created 2016-12-21 with zero commits before "
        "2025; the 3,127 stars belong to the repo's previous life, not this code"
    ),
    # 2026-08-26 discovery sweep — README-read verdicts (see agents-shortlist.json).
    "makecindy/cindy": (
        "2026-08-26 rejected — harness wrapper; README: 'the first supported "
        "harnesses are Claude Code and Codex', the wrapped CLI does the work. "
        "Same class as iofficeai/aionui (#180)"
    ),
    "simonlin1212/vibe-research": (
        "2026-08-26 rejected — serves agents, isn't one; README says it 'never "
        "recommends' and 'leaves an interface to plug in your own AI'. A trading "
        "data dashboard, not an agent"
    ),
    "tsingyuai/growth-lab": (
        "2026-08-26 not an agent — its own product model is 'Codex/Claude Code = "
        "Runtime, Skill = method'; a Skills+client bundle running ON an external "
        "runtime. Skill-class candidate, not the agent board"
    ),
    "pingdotgg/t3code": (
        "2026-08-27 owner ruling (hold the boundary) — README: 'an agent harness "
        "control surface', a mobile/web/desktop app to CONTROL Claude Code/Codex/"
        "Cursor/Grok Build/OpenCode on your machine. Control-surface class with no "
        "agent logic of its own; same boundary as aionui/cmux/cindy. Direct "
        "analogs getpaseo/paseo, nanmicoder/cc-haha, milisp/codexia are the same class"
    ),
    # 2026-09-29 first-batch pre-screen (docs/research/new-listing-candidates-2026-09-29.md).
    "anywhere-labs/dsh-desktop": (
        "2026-09-29 owner: rejected — desktop wrapper around DeepSeek Harness; "
        "the wrapped runtime is the agent (iofficeai/aionui)"
    ),
    "dataelement/dsh-desktop": (
        "2026-09-29 owner: rejected — desktop wrapper around DeepSeek Harness; "
        "the wrapped runtime is the agent (iofficeai/aionui)"
    ),
    "zhu1090093659/dsh-web": (
        "2026-09-29 owner: rejected — web wrapper around DeepSeek Harness; "
        "the wrapped runtime is the agent (iofficeai/aionui)"
    ),
    "dsh-tauri/deepseek-harness-desktop": (
        "2026-09-29 owner: rejected — desktop wrapper around DeepSeek Harness; "
        "the wrapped runtime is the agent (iofficeai/aionui)"
    ),
    "meteornox/deepseek-balance-whale-widget": (
        "2026-09-29 owner: rejected — balance widget for DeepSeek Harness, "
        "not an agent (iofficeai/aionui)"
    ),
    "yjh051108/dsh-routing-suite": (
        "2026-09-29 owner: rejected — routing presets for DeepSeek Harness, not an agent"
    ),
    "xiaobright/dsh-anchored-standard": (
        "2026-09-29 owner: rejected — prompt/config standard for DeepSeek Harness, not an agent"
    ),
    "chuspeeism/dashi-taskboard": (
        "2026-09-29 owner: rejected — task panel dispatching to Codex/DeepSeek "
        "Harness (bloopai/vibe-kanban)"
    ),
    "lidge-jun/opencodex": (
        "2026-09-29 owner: rejected — provider proxy for coding-agent CLIs; "
        "serves agents, isn't one (simonlin1212/vibe-research)"
    ),
    "miuuyy/codex-chatgpt-web": (
        "2026-09-29 owner: rejected — provider proxy for coding-agent CLIs; "
        "serves agents, isn't one (simonlin1212/vibe-research)"
    ),
    "xiaoduoya/codex-with-chatgpt": (
        "2026-09-29 owner: rejected — provider proxy for coding-agent CLIs; "
        "serves agents, isn't one (simonlin1212/vibe-research)"
    ),
    "wang2122/sprix-sage-router": (
        "2026-09-29 owner: rejected — model router for coding-agent CLIs; "
        "serves agents, isn't one (simonlin1212/vibe-research)"
    ),
    "shengjidaguai-china/goutoujunshi": (
        "2026-09-29 owner: rejected — a prompt persona for Codex, not an agent"
    ),
    "shy3130/tick-stock-panel": (
        "2026-09-29 owner: rejected — stock workbench, not an agent"
    ),
    "hithink-tech/financial-api": (
        "2026-09-29 owner: rejected — market-data API, not an agent"
    ),
    "jub0t/concat": (
        "2026-09-29 owner: rejected — video editor; MCP support is incidental "
        "(firerpa/lamda)"
    ),
    "jakubantalik/thinking-orbs": (
        "2026-09-29 owner: rejected — UI loading components, not an agent"
    ),
    "alephaitech/workbuddyguide": (
        "2026-09-29 owner: rejected — a usage guide, not an agent"
    ),
    "buchidonggua/dg-ai-notes": (
        "2026-09-29 owner: rejected — personal notes, not an agent"
    ),
    # Held from the approved batch pending the owner's call, then rejected.
    "fuxicodex/fuxi": (
        "2026-09-29 owner: rejected — LICENSE reads 'Proprietary. All rights "
        "reserved.'; fails the license rule"
    ),
    "player-yn/browserkitten": (
        "2026-09-29 owner: rejected — 2,882 stars vs 10 forks, 4 contributors, "
        "20 commits; inorganic (sv-number/mcp-server)"
    ),
    "scrapecreators/social-media-research-skills": (
        "2026-09-29 owner: rejected — 2,938 stars vs 37 forks, 2 contributors, "
        "7 commits; inorganic (sv-number/mcp-server)"
    ),
    "internet-court/internet-court-skill": (
        "2026-09-29 owner: rejected — 6,302 stars, 1 contributor, 4 commits; "
        "inorganic (sv-number/mcp-server); MIT covers only its own parts"
    ),
    # 29 Sep pre-screen, section B ("closer look"), decided 1 Oct.
    "spinabot/brigade": (
        "2026-10-01 owner: rejected — +2,550 stars (8,442 -> 10,994) in two days "
        "against 58 forks and 6 watchers; inorganic (player-yn/browserkitten)"
    ),
    "tutti-os/tutti": (
        "2026-10-01 owner: rejected — the open-source edition connects existing "
        "agents (Claude Code/Codex/Hermes); collaboration is in the closed VM "
        "edition. Supervisory harness (pingdotgg/t3code, generalaction/emdash)"
    ),
    "yc-software/qm": (
        "2026-10-01 owner: rejected — 'Pi, OpenCode, Codex, and Claude Code all "
        "drive the same core': the plugged-in harness is the agent (makecindy/cindy). "
        "Strongest case if the harness boundary is ever widened"
    ),
    "genspark-ai/genoffice": (
        "2026-10-01 owner: rejected — an office suite whose agent, skill and MCP "
        "server are features of the app (jub0t/concat)"
    ),
    # 2026-10-09 batch 3 decisions (docs/research/new-listing-candidates-2026-10-08.md):
    # the owner approved section A and rejected section C.
    "orchestratorinc/agent-orchestrator": (
        "2026-10-09 owner: rejected — Already rejected 2026-07-07 as "
        "agentwrapper/agent-orchestrator; this is the same repo renamed"
    ),
    "feder-cr/invisible_dots": (
        "2026-10-09 owner: rejected — adoption not earned: a new project moved "
        "into feder-cr/Auto_Jobs_Applier_AIHawk's repo (2024 job bot) and "
        "inherits its stars"
    ),
    "feder-cr/dots": (
        "2026-10-09 owner: rejected — adoption not earned: a new project moved "
        "into feder-cr/Auto_Jobs_Applier_AIHawk's repo (2024 job bot) and "
        "inherits its stars"
    ),
    "cinderline/northcinder": (
        "2026-10-09 owner: rejected — inorganic stars: forks under 2% of stars, "
        "2-3 contributors, a few dozen commits (sv-number/mcp-server precedent)"
    ),
    "filtalgo/filtmall-shopping-skill": (
        "2026-10-09 owner: rejected — inorganic stars: forks under 2% of stars, "
        "2-3 contributors, a few dozen commits (sv-number/mcp-server precedent)"
    ),
    "twigpine/openclaude": (
        "2026-10-09 owner: rejected — licence: LICENSE says it 'contains code "
        "derived from Anthropic's Claude Code CLI… proprietary'"
    ),
    "ekkolearnai/ekko-studio": (
        "2026-10-09 owner: rejected — licence: Business Source License 1.1, not "
        "open source"
    ),
    "sugarforever/chat-ollama": (
        "2026-10-09 owner: rejected — licence: Apache-2.0 modified to restrict "
        "commercial use"
    ),
    "alishahryar1/free-claude-code": (
        "2026-10-09 owner: rejected — provider proxy for free model access, "
        "licence NOASSERTION"
    ),
    "21st-dev/magic-mcp": (
        "2026-10-09 owner: rejected — deprecated: README says Magic MCP is now "
        "the 21st MCP and this package is a thin compatibility proxy"
    ),
    "loopx-project/loopx": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "zeronsh/zeron": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "harnessmd/munder-difflin": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "mvschwarz/openrig": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "spacering-net/codeg": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "happier-dev/happier": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "bytepioneer-ai/codex-host": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "hardbeat920/monocode": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "codeaholicguy/ai-devkit": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "gaurav-gosain/tuios": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "gentleman-programming/gentle-ai": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "iamcorey/wake": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "altans/collie": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "lodyai/lody": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "louis-cfm/coucou": (
        "2026-10-09 owner: rejected — supervisory harness (#180): external "
        "coding-agent CLIs do the agent work"
    ),
    "vastsa/pi-desktop": (
        "2026-10-09 owner: rejected — wrapper around an already-listed agent "
        "runtime (pi, Hermes Agent)"
    ),
    "abundantbeing/hermes-browser-extension": (
        "2026-10-09 owner: rejected — wrapper around an already-listed agent "
        "runtime (pi, Hermes Agent)"
    ),
    "ebony-vinyl/dsh-our-free-model": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "yujunzhixue/dsh-purge": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "small-tailqwq/dsh-deep-whale": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "bowenliang123/dsh-context": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "dsh-eac/eac-desktop": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "xmanrui/dsh-im": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "shaobeichen/dsh-pocket": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "adamplatin123/dsh-plugin-radar": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "clearailhc/clearai-dsh": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "devin-axis/deepseek-design": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "minglink/dsh-infinite-gen-4": (
        "2026-10-09 owner: rejected — DeepSeek Harness add-on (plugin, skin, "
        "preset, wrapper or jailbreak), not an agent (2026-09-29 DSH rulings)"
    ),
    "yetone/magpie": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "omnirush-ai/omnirush-gui": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "rebel0789/codexpro": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "sums001/windows-copilot-api": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "harnessrouter/harnessrouter": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "monid-ai/monid": (
        "2026-10-09 owner: rejected — provider proxy or free-model access "
        "layer: thin-wrapper boundary"
    ),
    "onlook-dev/onlook": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "duartesantos8/opengym": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "kkkkhazix/aihot": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "kuddev/pebrel": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "shader-effects-inc/shaders": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "dream-num/univer": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "dream-num/univer-workspace": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "tianma-if/edgeever": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "px0-ai/px0": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "feigecode/navop": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "augani/dory": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "incoai/splash": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "unstablebuild/rune": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "drawdb-io/drawdb": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "docmost/docmost": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "molunerfinn/picgo": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "asciimoo/hister": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "devlikeapro/waha": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "xpf0000/flyenv": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "bostrot/wslmanager": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "crosspaste/crosspaste-desktop": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "voidenhq/voiden": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "zhouxiaoka/autoclip": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "hbai-ltd/toonflow-app": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "ethanyoq/ai-novel-writer": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "every-app/open-seo": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "javis603/token-monitor": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "freestylefly/wechatbridge": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "fancydirty/mediary-scout": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "observal/observal": (
        "2026-10-09 owner: rejected — not an agent: an app or tool whose AI "
        "features are incidental"
    ),
    "wasmerio/wasmer": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "tyktechnologies/tyk": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "budtmo/docker-android": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "infobyte/faraday": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "cortex-docs/cortex": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "sopaco/deepwiki-rs": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "raullenchai/rapid-mlx": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "semianalysisai/inferencex": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "chrisryugj/kordoc": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "evil0ctal/douyin_tiktok_download_api": (
        "2026-10-09 owner: rejected — infrastructure where agents are one use "
        "among many, or agent support predates or is incidental to the product"
    ),
    "eatmoreduck/boss-zhipin-scraper": (
        "2026-10-09 owner: rejected — scraper or account tool, not an agent"
    ),
    "mahanaicoach/google-maps-scraper-kit": (
        "2026-10-09 owner: rejected — scraper or account tool, not an agent"
    ),
    "yacuo/check-cc": (
        "2026-10-09 owner: rejected — scraper or account tool, not an agent"
    ),
    "jundizhou/easy-stock": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "aoci-spec/aoci-code": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "pgrundev/pgbot": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "brayonpi/hexstellar": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "fy-agent/fyagent": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "lemomo-ai/lemo-opuscar": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "vincentwei1021/video-talkcraft": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "vincentwei1021/anything2explainer": (
        "2026-10-09 owner: rejected — licence NOASSERTION with no standard "
        "licence found; reconsider if one appears"
    ),
    "thedaviddias/front-end-checklist": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "harvard-edge/cs249r_book": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "dipakkr/awesome-ai-engineering": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "liyupi/ai-guide": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "tradecatlabs/vibe-coding-cn": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "walkinglabs/learn-harness-engineering": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "lopopolo/harness-engineering": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "aliyun/ai-agent-handbook": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "anative-lab/awesome-self-evolving-agents": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "andyrewlee/awesome-agent-orchestrators": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "flypythoncom/python": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "chenliu-1996/figures4papers": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "ciembor/agent-rules-books": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
    "crafter-station/petdex": (
        "2026-10-09 owner: rejected — list, course, guide or collection; ships "
        "no agent"
    ),
}

# Topics to query (one request each)
# GitHub topics are exact strings: `topic:ai-agent` does not match a repo
# tagged `ai-agents`. That single missing plural made
# deepseek-ai/deepseek-harness — 130k stars, MIT, first-party — unreachable by
# every sweep, because its topics are ai-agents/cordis/dsh/dsh-plugin and its
# description ("DeepSeek Harness: Everything is a Plugin.") matches no keyword
# either. Measured 2026-08-16: the additions below reach 536 novel repos the
# original list could not see. Add plurals whenever you add a singular.
TOPICS = [
    "ai-agent",
    "ai-agents",
    "coding-agent",
    "coding-agents",
    "llm-agent",
    "llm-agents",
    "autonomous-agent",
    "autonomous-agents",
    "ai-coding-assistant",
    "agent-framework",
    "ai-agent-framework",
    "agent-harness",
    "agent-orchestration",
    "multi-agent",
    "multi-agent-systems",
    "agentic",
    "agent-tools",
    "agent-memory",
    "mcp",
    "mcp-server",
    "mcp-servers",
    "mcp-client",
    "mcp-tools",
    "model-context-protocol",
    "claude-code",
    # Vendor-ecosystem topics. A first-party launch spawns its own tag before
    # it adopts the generic ones — dsh/dsh-plugin appeared with the DeepSeek
    # Harness release and held 46 repos within three days.
    "dsh",
    "dsh-plugin",
]

# Keyword searches (description field)
KEYWORDS = [
    '"AI agent" in:description',
    '"coding agent" in:description',
    '"autonomous agent" in:description',
    '"MCP server" in:description',
    '"agent harness" in:description',
    '"harness" in:description',
]

MIN_STARS = 500
# Every search returns only the top 100 by stars, so on a big topic that page
# is all long-established repos and a three-month-old project never surfaces.
# Each query therefore also runs restricted to repos created in this window.
RECENT_DAYS = 120
SLEEP_BETWEEN = 3  # seconds between API calls (Search API: 30 req/min)
OUTPUT_PATH = "candidates.json"


def search_repos(query: str) -> list[dict]:
    """Run one GitHub search query, returning up to 100 results."""
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
    full_query = f"{query} stars:>{MIN_STARS} pushed:>{one_year_ago}"
    params = {
        "q": full_query,
        "sort": "stars",
        "order": "desc",
        "per_page": 100,
    }
    try:
        r = requests.get(
            f"{GITHUB_API}/search/repositories",
            headers=HEADERS,
            params=params,
            timeout=20,
        )
        if r.status_code == 422:
            print(f"  WARN: invalid query [{query}] — skipped")
            return []
        r.raise_for_status()
        items = r.json().get("items", [])
        return items
    except Exception as e:
        print(f"  WARN: search failed [{query}]: {e}")
        return []


def passes_eligibility(repo: dict) -> bool:
    """
    Automated pre-checks (machine-verifiable MUST/SHOULD criteria from Eligibility Spec v1.0):
      §4.1.1 — has declared open-source license
      §4.1.2 — public repository (already guaranteed by Search API)
      §4.2.1 — pushed within last 365 days
      §5.1   — not archived
      §5.3   — not a fork (forks with zero independent commits are disqualifying)
    Plus floor of MIN_STARS stars.
    """
    if repo.get("archived"):
        return False
    if repo.get("fork"):
        return False
    if repo.get("stargazers_count", 0) < MIN_STARS:
        return False
    if repo.get("license") is None:
        return False
    pushed_at = repo.get("pushed_at", "")
    if pushed_at:
        try:
            pushed_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - pushed_dt).days >= 365:
                return False
        except ValueError:
            pass
    return True


LIVE_BOARD_URL = "https://hvtracker.net/data.json"


def load_existing_repos(live_board_url: str = LIVE_BOARD_URL) -> set[str]:
    """Lowercase repo paths already tracked, under every name they go by.

    Search returns a repo under its current GitHub name, so matching roster
    keys alone re-proposed renamed repos as new listings: NanoNets/Graft,
    chopratejas/headroom, imartinez/privateGPT and nowork-studio/NotFair were
    each listed twice. This also counts each roster row's previous_repos and
    the current name the live board resolved for it (its `url`), which covers
    a rename the roster hasn't recorded yet."""
    existing: set[str] = set()
    try:
        with open("agents.json") as f:
            agents = json.load(f)
        existing |= {name.lower() for a in agents for name in [a["repo"], *(a.get("previous_repos") or [])]}
    except Exception as e:
        print(f"WARN: could not load agents.json: {e}")
    try:
        resp = requests.get(live_board_url, headers={"User-Agent": "Mozilla/5.0 (hvtracker-discovery)"},
                            timeout=60)
        resp.raise_for_status()
        rows = resp.json()["agents"]
        existing |= {r["url"].lower().rstrip("/").removeprefix("https://github.com/")
                     for r in rows if (r.get("url") or "").lower().startswith("https://github.com/")}
    except Exception as e:
        print(f"WARN: could not read the live board ({e}); matching roster names only")
    return existing


def main() -> None:
    existing = load_existing_repos()
    print(f"Loaded {len(existing)} existing agents.\n")

    seen: dict[str, dict] = {}  # full_name.lower() -> repo dict

    recent = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    queries = [f"topic:{t}" for t in TOPICS] + KEYWORDS
    for base in queries:
        for query in (base, f"{base} created:>{recent}"):
            print(f"Searching {query!r} ...", end=" ", flush=True)
            items = search_repos(query)
            new = sum(1 for it in items if it["full_name"].lower() not in seen)
            for it in items:
                seen.setdefault(it["full_name"].lower(), it)
            print(f"{len(items)} results, {new} new")
            time.sleep(SLEEP_BETWEEN)

    print(f"\nTotal unique repos found: {len(seen)}")

    # Filter out already-tracked repos and owner-rejected candidates
    novel = {k: v for k, v in seen.items() if k not in existing}
    print(f"New (not in agents.json): {len(novel)}")
    rejected_hits = sorted(k for k in novel if k in REVIEWED_REJECTED)
    if rejected_hits:
        novel = {k: v for k, v in novel.items() if k not in REVIEWED_REJECTED}
        print(f"Skipping {len(rejected_hits)} owner-rejected repo(s): {', '.join(rejected_hits)}")

    # Eligibility pre-checks
    candidates = []
    for repo_dict in novel.values():
        if passes_eligibility(repo_dict):
            lic = repo_dict.get("license") or {}
            candidates.append({
                "repo": repo_dict["full_name"],
                "name": repo_dict["name"],
                "description": (repo_dict.get("description") or "")[:140],
                "stars": repo_dict["stargazers_count"],
                "language": repo_dict.get("language") or "",
                "license": lic.get("spdx_id") or lic.get("name") or "Unknown",
                "last_push": (repo_dict.get("pushed_at") or "")[:10],
                "created": (repo_dict.get("created_at") or "")[:10],
                "topics": repo_dict.get("topics", []),
                "url": repo_dict.get("html_url", ""),
            })

    # Sort by stars descending
    candidates.sort(key=lambda x: x["stars"], reverse=True)

    if candidates:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(candidates, f, indent=2)
        print(f"\nWrote {len(candidates)} candidates to {OUTPUT_PATH}.")
    else:
        # Remove stale candidates file if nothing found
        if os.path.exists(OUTPUT_PATH):
            os.remove(OUTPUT_PATH)
        print("\nNo new candidates found.")

    print(f"\nSummary: {len(seen)} found → {len(novel)} novel → {len(candidates)} pass pre-checks.")
    if candidates:
        print("\nTop 5 by stars:")
        for c in candidates[:5]:
            print(f"  {c['repo']:<50} ⭐{c['stars']:,}  {c['language']}")


if __name__ == "__main__":
    main()
