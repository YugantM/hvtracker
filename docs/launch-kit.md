# HVTracker Launch Kit

**You post these — I can't publish on your behalf.** All copy is ready to paste.
Core hook (data-backed, defensible): *popularity ≠ trustworthiness.*

Key stats (live, 2026-05-31):
- hundreds of AI agents scored.
- **24 of the 30 most-starred agents have no build provenance.**
- Claude Code: #82 (128k stars). Codex: #2 (87k stars). Stars don't predict trust.
- Grade distribution: A=23, B=51, C=38, D=80.
- License reality: 180 open, 7 source-available, 2 proprietary, 3 unlicensed.

---

## 1. Show HN

**Title:** `Show HN: I scored hundreds of AI agents by supply-chain trust (most popular ≠ safest)`

**URL:** `https://hvtracker.net`

**First comment (post immediately after submitting):**

> I kept seeing "best AI agent" lists ranked purely by GitHub stars, so I built a registry that scores hundreds of agents on verifiable supply-chain signals instead: OSSF Scorecard, build provenance, signed commits, license type, maintenance, and adoption — each weighted by how hard it is to fake, then scaled by an evidence-confidence factor so tools with little verifiable evidence can't reach the top tier.
>
> The uncomfortable finding: 24 of the 30 most-starred agents publish no build provenance at all. Claude Code (128k stars) lands at #82 — not because it's bad software, but because it's proprietary with no public Scorecard or provenance, so there's little to verify. Codex (87k stars) sits at #2 because nearly everything is verifiable.
>
> Everything's open: the full dataset is CC BY 4.0 at /data, the methodology is public at /methodology, and there's a compare tool. I'd genuinely like pushback on the weighting — what signal am I over- or under-counting?

---

## 2. LinkedIn

**Post:**

> I kept seeing AI agent rankings that collapse everything into GitHub stars.
>
> That felt incomplete for tools that can read your code, run commands, and land inside CI.
>
> So I built HVTracker v2: a public trust registry that scores hundreds of AI agents on signals you can actually verify, including OSSF Scorecard, build provenance, signed commits, license type, maintenance, and adoption.
>
> The headline surprised even me: **24 of the 30 most-starred AI agents publish no build provenance at all.**
>
> A couple of examples:
> - Claude Code has 128k GitHub stars and ranks #82 on HVTracker.
> - Codex has 87k stars and ranks #2.
>
> That's not a product-quality verdict. It's a visibility verdict. Stars measure attention; trust depends on what the public can verify.
>
> I made the full dataset public under CC BY 4.0, published the methodology, and added a compare tool so people can inspect or challenge the weighting in the open.
>
> If you use AI agents in development, security, or platform engineering, I'd love your pushback:
> **Which trust signal would you weight differently?**

**First comment:**

> Link: https://hvtracker.net
>
> Methodology and raw data are public too. If a project is missing provenance or package metadata, tell me and I'll correct it.

## 3. X / Twitter thread

**1/**
I scored hundreds of AI agents by supply-chain trust, not GitHub stars.

The result is uncomfortable: the most popular tools are often the least verifiable.

🧵

**2/**
24 of the 30 most-starred AI agents publish zero build provenance.

No attestation that the package you install matches the source you're reading. For tools running in your terminal and CI, that's the signal that should matter most.

**3/**
Claude Code: 128k stars → ranked #82.
Codex: 87k stars → ranked #2.

Not a quality judgment. Claude Code is proprietary with no public OSSF Scorecard or provenance, so there's little to verify. Stars measure popularity; they don't measure trust.

**4/**
Each agent is scored on signals weighted by how hard they are to fake:
• OSSF Scorecard
• build provenance
• signed commits
• license type
• maintenance
• adoption

…then scaled by an evidence-confidence factor.

**5/**
It's fully open. Dataset is CC BY 4.0, methodology is public, and there's a compare tool.

Leaderboard → hvtracker.net

Tell me which signal I'm weighting wrong. 👇

---

## 4. Reddit

### r/LocalLLaMA  /  r/MachineLearning
**Title:** `I ranked hundreds of AI agents by supply-chain trust instead of GitHub stars — 24 of the 30 most popular have no build provenance`

**Body:**
> Most "best AI agent" lists rank by stars. I wanted to know which ones are actually *verifiable*, so I built a registry that scores hundreds of agents on OSSF Scorecard, build provenance, signed commits, license type, maintenance, and adoption — weighted by how hard each signal is to fake.
>
> Findings that surprised me:
> - 24 of the 30 most-starred agents publish no build provenance.
> - Claude Code (128k stars) ranks #82; Codex (87k) ranks #2 — driven by what's publicly verifiable, not quality.
> - the majority are Grade D, mostly for missing verifiable signals.
>
> Full dataset is CC BY 4.0 and the methodology is public. Happy to be told my weighting is wrong — that's half the reason I'm posting. Link in comments to avoid the spam filter.

*(Post the hvtracker.net link as your first comment — Reddit suppresses link-posts from low-karma accounts.)*

### r/devops  /  r/programming
**Title:** `A trust registry for AI agents — OSSF Scorecard, provenance, and signed commits instead of stars`

**Body:** Same as above, but lead with the supply-chain angle: *"If you're putting AI agents in your CI or dev environment, stars tell you nothing about whether the artifact matches the source. I scored hundreds of them on provenance, Scorecard, and signing."*

---

## 5. Posting playbook

- **Timing:** Show HN Tue–Thu, 8–10am ET (catches the US morning). One channel at a time — don't blast all at once; if HN hits the front page, ride it before posting elsewhere.
- **Engage fast:** First 60–90 min of comments decide HN ranking. Reply to every critique with data, not defensiveness. The "tell me what I'm weighting wrong" framing turns critics into contributors.
- **Don't oversell:** lead with the finding, not the product. The data is the story.
- **Reddit:** link as a comment, not the post body, on low-karma accounts.
- **Track it:** watch GA4 real-time + (once verified) Search Console for the query spike.

## 6. Newsletter pitch (P2 — send after launch lands)

**Subject:** `Data: 24 of 30 most-popular AI agents have no build provenance`

> Hi [name] — I run HVTracker, an open trust registry for AI agents. I just scored hundreds of them on supply-chain signals (Scorecard, provenance, signing) rather than stars. The headline: 24 of the 30 most-starred agents publish no provenance, and Claude Code ranks #82 despite 128k stars. Full dataset is CC BY 4.0 and free to cite/chart. Thought it might fit [newsletter] — happy to send the raw numbers or a chart. — [you]
