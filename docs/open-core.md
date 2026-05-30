# Open-Core Plan

These notes describe how HVTracker can stay useful and trusted in public while preserving room for a future company.

This is product strategy, not legal advice. Before fundraising, selling paid plans, or accepting major external contributions, choose licenses deliberately with counsel.

## Principle

Keep the public project valuable enough to earn trust, citations, and community corrections. Keep expensive, operational, private, or workflow-specific capabilities in a hosted commercial layer.

## Current Repository Boundary

As of the Railway migration:

- **Repository code:** MIT-licensed in this repo.
- **Public registry data:** CC BY 4.0.
- **Hosted service:** can remain proprietary in its operations, enrichment, alerting, and private workflows even if the public registry stays open and inspectable.

That means you do not need to close the whole repository to build a company. The better move is to keep the trust-critical surface public and keep the operational/commercial layer private.

## Public Core

Keep these public:

- The curated list of tracked open-source agents.
- The scoring methodology and versioned specifications.
- Basic current leaderboard fields.
- Per-agent public profile pages.
- Public evidence grade and trust breakdown.
- Public data sources and collection caveats.
- Correction and listing process.
- Build transparency report.

This keeps HVTracker credible. If people cannot inspect how rankings are produced, the trust registry becomes just another black-box ranking.

## Commercial Layer

Reserve these for a future hosted product:

- Full historical time series beyond the public window.
- Alerting on rank drops, maintainer inactivity, provenance regressions, license changes, or security signal changes.
- Private watchlists and team notes.
- Vendor comparison exports.
- API keys, higher rate limits, webhooks, and SLAs.
- Enterprise risk scoring overlays.
- Closed-source/commercial agent tracking.
- Private customer annotations and internal approval workflows.
- Enriched signals that require paid APIs, manual analysis, or expensive processing.
- Custom categories for a company's internal agent stack.

## Public Data Boundary

The current v1 public API exposes enough data to be useful and verifiable. If you want a future company path, avoid publishing everything by default.

Recommended boundary:

| Layer | Public | Paid or private later |
|---|---|---|
| Current rank and category | Yes | No |
| Basic public signals | Yes | No |
| Methodology | Yes | No |
| Per-agent summary | Yes | No |
| 90-day public history | Yes, if affordable | Extended history |
| Raw third-party API responses | No | No, store internally if allowed |
| Watchlists and alerts | No | Yes |
| Bulk exports | Limited | Yes |
| Commercial/closed-source agents | Limited or none | Yes |
| Manual review notes | Summaries only | Full notes |

## Licensing Direction

Pick this before a serious v1 release:

- **Source code:** Apache-2.0 or AGPL-3.0 are the two obvious choices.
- **Public data:** CC BY 4.0 is good for attribution and broad reuse.
- **Brand:** keep the HVTracker name, logo, and domain as project/company marks, not as freely reusable data.

Tradeoff:

- Apache-2.0 maximizes adoption and contributions, but competitors can reuse the code.
- AGPL-3.0 protects the hosted-service layer better, but can reduce enterprise contribution comfort.
- A source-available license gives more control, but is no longer open source in the OSI sense.

My default recommendation for your situation: keep the public data under CC BY 4.0, use Apache-2.0 for non-sensitive code if community growth matters most, and keep hosted enrichment, private history, alerts, and workflows proprietary.

## What Not To Publish

Do not publish:

- API keys, raw credentials, or private tokens.
- Expensive raw crawl outputs.
- Private notes about vendors or maintainers.
- Customer watchlists or internal evaluations.
- Paid/enriched datasets you may want to sell later.
- Anything whose third-party terms prohibit redistribution.

## Company-Ready Product Ladder

1. **Free public site:** leaderboard, profiles, specs, current public API.
2. **Free developer API:** limited requests, attribution required.
3. **Pro account:** watchlists, alerts, CSV export, extended history.
4. **Team account:** shared watchlists, approval notes, webhook alerts.
5. **Enterprise:** private agent registry, custom scoring, procurement exports, SLA, compliance support.

## Messaging

Use this language:

> HVTracker is open where trust requires inspection: methodology, public rankings, public signals, and correction workflows. Hosted features may add private watchlists, alerting, extended history, and enterprise workflows.

Avoid promising:

- "All data will always be public."
- "Everything will be open source forever."
- "This is a security certification."
- "This ranking proves the best agent."

## Near-Term Actions

- Add a license decision before inviting broad contributions.
- Add a clear public data license note to every API endpoint or docs page.
- Keep methodology and schema versioned.
- Add a badge policy before maintainers start asking for badges.
- Keep raw collection caches out of the public API unless they are cheap, allowed, and strategically safe.
