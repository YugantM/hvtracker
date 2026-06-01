# HVTracker — Engineering Backlog

Source of truth for technical work. The product roadmap lives at `/roadmap`;
this file is for engineering/infra debt that doesn't show up there.

Update as you ship.  Move done items to "## Done" with a date + commit.

---

## 🔴 High priority

- **Cloudflare Cache Rule for HTML/JSON.**  Cache-Control headers are now
  set correctly on the origin (HTML: `s-maxage=900`, JSON: `s-maxage=1800`)
  but Cloudflare still returns `cf-cache-status: DYNAMIC` because by
  default it only caches static file extensions.  Add one Cache Rule in
  the Cloudflare dashboard:

  - **Match:** URL path starts with `/agents/`, `/categories/`, `/data/`,
    `/blog/`, `/compare/` OR exactly equals `/`
  - **Action:** Cache eligibility = Eligible for cache, Edge TTL =
    Respect origin headers

  Until this is configured, only the browser caches HTML; Railway still
  serves every visit.  5-minute dashboard task.

## 🟡 Medium priority

- **Multi-stage Dockerfile.** Pillow + DejaVu fonts are only needed at build
  time (for OG card generation); moving them to a `builder` stage would shrink
  the runtime image.  Estimated effort: 30 min.

- **Periodic eligibility-warnings review.** The build prints warnings but
  doesn't fail.  Re-triage on the first of each month: any agent that's
  drifted into "no meaningful activity 12+ months" should be flipped to
  `status: legacy` in `agents.json` (and `listing_status: legacy`).  Done
  once on 2026-06-01.

- **Accepted no-license warnings (review quarterly).** These four are
  intentional and won't be auto-flagged again:
  - `anthropics/claude-code` — proprietary (license_override applied)
  - `browserbase/open-operator` — no license declared upstream
  - `yoheinakajima/babyagi` — abandoned, no license
  - `trypear/pearai-master` — no license declared upstream

## 🟢 Low priority / nice-to-have

- **De-dup inline CSS** across `template.html` and the Jinja templates into a
  shared `static/site.css`.  Cosmetic — only useful if styles diverge.

- **Speed up PyPI downloads fetch.**  Currently serial (~1 req/s for ~50
  packages = ~1 min on full builds).  Could parallelise with a token-bucket
  limiter, but pypistats is sensitive to bursts.  Acceptable as-is.

- **Sparser OSSF Scorecard coverage.**  Many agents return `null` because OSSF
  hasn't crawled them.  `scorecard-scan.yml` already fills gaps weekly; no
  action unless coverage drops below ~75%.

- **GitHub release-asset downloads as a signal source.**  For self-hosted
  agents (no npm/pypi/Docker), GitHub release asset download counts are the
  only public proxy.  Today they're not tracked; would fill in download
  numbers for agents like Odysseus.  Effort: 2h.

## Done

- 2026-06-01 — **Cache headers for HTML and JSON responses.**  Added a
  FastAPI middleware setting `Cache-Control: public, max-age=300,
  s-maxage=900, stale-while-revalidate=86400` for HTML and `max-age=600,
  s-maxage=1800` for `/data/*.json`.  Cloudflare now caches at the edge;
  Railway origin traffic should drop substantially.

- 2026-06-01 — **HTML5 validation in CI.**  `tests/validate_html.py` parses
  9 sample pages (homepage + representative profile/category/blog/compare
  pages) with `html5lib` in strict mode; CI fails on any structural error.
  Caught two real bugs while adding it: unescaped `&` in Google Fonts
  links and the `/badges/` PR-request URL.

- 2026-06-01 — **Render-only legacy reclassification.**  Flipping an
  agent's status to `legacy` in agents.json now propagates on the next
  `--render-only` build, without waiting for a full refetch.

- 2026-06-01 — **15 stale agents moved to legacy.**  Repos with no
  meaningful activity for 12+ months (or archived) no longer compete with
  fresh agents on the main leaderboard.  Build warnings dropped 19 → 4.

- 2026-06-01 — **Render-sync regression tests** (`tests/test_render_sync.py`).
  Five unit tests pinning the two invariants that caused 4 commits worth
  of regressions on 2026-06-01 (image-volume seed-only-when-missing;
  provisional listing of newly-added agents).

- 2026-06-01 — **Removed dead `_headers` file** (Cloudflare Pages format,
  ignored by FastAPI).

- 2026-06-01 — **Per-agent OG cards** with custom trust-breakdown
  visualization (commit 921793b4).
- 2026-06-01 — **Render-state volume sync** so newly-added agents propagate
  to Railway on deploy (commit f82fbf62 et al.).
- 2026-06-01 — **Duplicate Goose dedup + name-based loader dedupe** so
  `aaif-goose/goose` can't shadow `block/goose` (commit d1a4a4b4).
