# HVTracker V1 Launch Plan

This is the zero-budget launch plan for the first public release of HVTracker.

## Launch Positioning

**One-line pitch:** HVTracker is an AI agent trust registry that ranks open-source agent projects by public evidence, not only stars.

**Short pitch:** HVTracker tracks 171 open-source AI agents across 14 categories and scores them using public signals for activity, adoption, transparency, safety, identity, provenance, and evidence quality.

**Audience:**

- Developers choosing an agent framework, coding agent, browser agent, memory layer, or workflow tool.
- Security and platform teams trying to understand agent supply-chain risk.
- Maintainers who want a public, neutral view of their project health.
- Researchers tracking the agent ecosystem.

**Launch hook:** The AI agent ecosystem is moving fast, but most lists optimize for popularity. HVTracker adds verifiable trust signals: commit freshness, package downloads, provenance, OSSF Scorecard, signed commits, rank movement, and public evidence grades.

## Launch Readiness Checklist

- [x] Homepage category filter supports one-category and zero-category states.
- [x] Selecting all categories restores global rank order.
- [x] Homepage agent links resolve to generated profile pages.
- [x] README describes v1 scope, signals, cadence, API, and limitations.
- [x] Open Graph image reflects v1 positioning and current counts.
- [x] Methodology copy says trust registry, not only health score.
- [x] Profile page metadata says trust profile.
- [ ] Decide source-code license before asking for external contributors.
- [ ] Add a short changelog or GitHub release notes for `v1.0.0`.
- [ ] Verify live Pages deploy after GitHub Actions/Pages incident clears.
- [ ] Check Twitter/X, LinkedIn, Slack, Discord, and Open Graph previews.

## Free Distribution Strategy

### Week 0: Prepare The Proof

Create 3-5 proof assets before posting:

- A screenshot of the top leaderboard with filters visible.
- A screenshot of a single agent profile.
- A screenshot or snippet showing the public JSON API.
- A simple "how we score" diagram from the methodology.
- A short list of surprising findings, for example top movers, projects with provenance, or high-trust smaller projects.

### Week 1: Founder-Led Launch

Post in this order so each post has somewhere useful to point:

1. GitHub release: `v1.0.0`.
2. Personal LinkedIn post.
3. X/Twitter thread.
4. Hacker News "Show HN".
5. Reddit communities where self-promotion rules allow it.
6. Relevant Discord/Slack communities, with a helpful angle rather than a drive-by link.
7. Direct maintainer outreach for projects that rank well or have corrections to suggest.

### Post Templates

**X/Twitter thread opener:**

```text
I built HVTracker: a trust registry for open-source AI agents.

It tracks 171 agent projects across 14 categories and ranks them by public evidence, not just stars:
- activity
- adoption
- transparency
- provenance
- OSSF Scorecard
- signed commits
- evidence grade

https://hvtracker.net
```

**LinkedIn opener:**

```text
The AI agent ecosystem is moving faster than ordinary "awesome lists" can explain.

I launched HVTracker v1 to make the landscape easier to evaluate: 171 open-source AI agent projects ranked by public evidence across activity, adoption, transparency, safety, identity, provenance, and rank movement.

The goal is not to declare winners. It is to make project health and trust signals easier to inspect.

https://hvtracker.net
```

**Show HN title:**

```text
Show HN: HVTracker - trust registry for open-source AI agents
```

**Show HN body:**

```text
I built HVTracker to track open-source AI agent projects using public, independently checkable signals.

It currently covers 171 projects across 14 categories. Instead of ranking only by stars, it surfaces activity, package downloads, OSSF Scorecard, package provenance, signed commits, rank movement, and evidence grades.

Each project gets a profile page and public JSON endpoint. Methodology is documented here:
https://hvtracker.net/methodology

Feedback on scoring, missing agents, and false positives would be very welcome.
```

### Community Targets

Start with communities that already discuss agent tooling and open-source infrastructure:

- Hacker News: Show HN.
- Reddit: `r/LocalLLaMA`, `r/MachineLearning`, `r/opensource`, `r/devops`, `r/cybersecurity`, only where rules permit.
- GitHub: tag a v1 release and pin the repository.
- LinkedIn: founder story plus methodology.
- X/Twitter: thread plus screenshots.
- Discord/Slack: LangChain, LlamaIndex, OpenAI builders, AI engineering, MLOps, platform engineering groups.
- Newsletters: Ben's Bites, TLDR AI, The Batch community submissions, Latent Space community, AI Engineer community.

### Outreach Angles

Do not ask people to "check out my product" first. Use useful prompts:

- "I ranked your project and may have missed package/provenance metadata. Want me to correct it?"
- "I found 12 agent projects with provenance signals. Would a public provenance table be useful?"
- "I am documenting agent supply-chain signals. What would you add to the methodology?"
- "Can I include your project in the v1 corrections pass?"

### Growth Loops

- **Maintainer correction loop:** every listed project can submit corrections, which creates GitHub activity and backlinks.
- **Badge loop:** offer optional badges such as `Tracked on HVTracker` or `Evidence grade A`.
- **Category pages:** publish category-specific pages and posts: coding agents, browser agents, agent frameworks, memory.
- **Monthly report:** publish "AI Agent Trust Report - Month YYYY" with movers, new listings, provenance adoption, and methodology changes.
- **API loop:** encourage others to build visualizations from the public API with attribution.

## Metrics To Watch

- GitHub stars and issue submissions.
- Number of correction PRs/issues from maintainers.
- Direct traffic to `hvtracker.net`.
- Referrers from HN, Reddit, LinkedIn, X, and GitHub.
- API hits to `/data/latest.json`.
- Pages for high-intent categories: coding agents, browser agents, security/guardrails.
- Mentions from maintainers.

## V1 Release Notes Draft

```markdown
## HVTracker v1.0.0

First public launch of the HVTracker AI Agent Trust Registry.

- Tracks 171 open-source AI agent projects across 14 categories
- Adds public leaderboard, per-agent pages, JSON API, feed, and sitemap
- Scores public signals for activity, adoption, transparency, safety, and identity
- Shows provenance, OSSF Scorecard, signed commit, package download, and HN signals where available
- Adds methodology and data schema specifications
- Adds staggered 4-hour refresh batches with a full 24-hour cycle

Feedback welcome: missing agents, category corrections, package metadata, and methodology critiques.
```
