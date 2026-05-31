# DRAFT — for review before publishing
# Target URL: /blog/github-stars-dont-predict-ai-agent-trust
# Status: prose draft. Once you approve the words, I'll convert to the
# blog_static HTML format (matching existing articles) and it ships with the build.

---

## GitHub stars don't predict AI agent trust. I scored 192 of them to prove it.

**Subhead:** 24 of the 30 most-starred AI agents ship with no build provenance. Here's the full list — and the six that get it right.

---

Every "best AI agent" list ranks the same way: by GitHub stars. Stars are easy to count and easy to game. They measure attention, not trustworthiness — and for software you're about to give access to your terminal, your CI, and your codebase, attention is the wrong metric.

So I built HVTracker to score AI agents on signals you can actually verify: OSSF Scorecard, build provenance, signed commits, license type, maintenance, and adoption — each weighted by how hard it is to fake. 192 of the most notable agents, refreshed every two hours. (It's a curated registry of the agents people actually use — not an index of every repo on GitHub.)

Then I checked the 30 most-starred agents for the one signal that should be table stakes: **build provenance** — cryptographic proof that the package you install was built from the source you can read.

**24 of the 30 don't publish it.**

### The list

Of the 30 most-starred AI agents, these 24 ship without build provenance:

OpenClaw (376k ★), AutoGPT (185k), opencode (168k), Langflow (149k), Dify (143k), LangChain (138k), Claude Code (128k), Firecrawl (126k), Gemini CLI (105k), Browser Use (96k), MCP (87k), RAGFlow (82k), OpenHands (75k), Daytona (73k), DeerFlow (70k), MetaGPT (68k), Crawl4AI (67k), Open Interpreter (64k), AnythingLLM (61k), PrivateGPT (57k), OpenManus (56k), Flowise (53k), CrewAI (52k), LlamaIndex (50k).

That's not an accusation against any one of them. It's a snapshot of an ecosystem that has collectively decided provenance is optional.

### Why provenance matters

When you `pip install` or `npm install` an agent, you're trusting that the published artifact matches the public source. Provenance attestation (via SLSA / Sigstore) is the cryptographic receipt that proves it. Without it, a compromised build pipeline or a hijacked publish token can ship malicious code under a trusted name — and you'd have no way to tell. For tools that read your files and run commands, that gap isn't academic.

### The six that get it right

Credit where it's due. Among the 30 most-starred, these publish provenance:

**Codex, n8n, Open WebUI, Cline, AutoGen, Mem0.**

It's not a coincidence that they also score near the top on HVTracker. Verifiable practices and trust scores move together.

### Stars vs. trust, head to head

The clearest illustration:

- **Claude Code** — 128k stars, trust score **61.9 (#82)**.
- **Codex** — 87k stars, trust score **92.8 (#2)**.

Fewer stars, far higher trust. This isn't a quality judgment on Claude Code — it's an excellent tool. It's proprietary, with no public OSSF Scorecard and no published provenance, so there's simply less that's externally verifiable. That's the point: **popularity and verifiability are different axes, and stars only measure the first one.**

### How we score (and how to argue with it)

Every score is built from public signals, weighted by how hard they are to fake, then scaled by an evidence-confidence factor so a tool with little verifiable evidence can't bluff its way to the top. The full methodology is public, and the entire dataset is free to use under CC BY 4.0.

If you think a weight is wrong, tell us — the methodology is meant to be argued with, in the open.

**See where your stack ranks → [hvtracker.net](https://hvtracker.net)**
