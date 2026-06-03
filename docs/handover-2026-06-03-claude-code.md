# Handover — 2026-06-03

This document is for continuing the current HVTracker trust/product cleanup in Claude Code without redoing discovery.

## Current objective

Keep the scope strict to **open-source AI agent projects / agent frameworks**, continue improving trust clarity, and keep all changes local-first.

The recent work focused on:

- registry consistency
- trust-change event modeling
- warning-state surfacing
- first-pass UI/UX cleanup on high-traffic pages

## What was completed

### 1. Registry consistency and strict scope

Already completed before the latest UI pass:

- strict inclusion rubric added at:
  - `/Users/harsiddhipari/hv_tracker/docs/strict-inclusion-rubric.md`
- legacy audit added at:
  - `/Users/harsiddhipari/hv_tracker/docs/cleanup/legacy-audit-2026-06-03.md`
- prior local fixes restored some wrongly-legacy active repos and cleaned legacy/public artifact mismatches

### 2. Trust-change event model

Implemented in:

- `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`

Key additions:

- `EVENT_REASON_META`
- `make_agent_event(...)`
- `summarize_recent_events(...)`
- richer `derive_agent_events(...)`

Event types now include:

- `listed`
- `delisted`
- `listing_state_changed`
- `score_changed`
- `trust_score_changed`
- `rank_changed`
- `stale_warning`
- `freshness_restored`
- `scorecard_added`
- `scorecard_removed`
- `provenance_added`
- `provenance_removed`
- `license_changed`

These are wired into:

- per-agent JSON in `data/agents/<slug>.json`
- `data/latest.json`
- homepage row summaries
- agent pages
- movers page

### 3. License-change bug fix

Bug:

- events were comparing `license_type` and `license_spdx` interchangeably
- this created fake events like `MIT -> open`

Fix:

- only compare SPDX to SPDX
- only compare license class to license class

Location:

- `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`

Verified locally:

- after rebuild, misleading `license_changed` recent events went to `COUNT 0`

### 4. Warning-state surfacing

Implemented in:

- `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`

New helper:

- `decorate_registry_states(rows, legacy_rows, violations)`

What it does:

- attaches `warning_reasons`
- sets `has_warning`
- derives `display_listing_status`
- derives `display_status_tone`

Current behavior:

- canonical `listing_status` is still whatever exists in config/state
- `display_listing_status` becomes `warning` for active rows with eligibility violations

This is a display-layer bridge, not a full canonical lifecycle migration yet.

### 5. Homepage redesign pass

Updated:

- `/Users/harsiddhipari/hv_tracker/template.html`

Changes:

- intro/hero is calmer and more registry-like
- replaced the earlier growth-oriented strip with a registry-state strip
- added registry summary cards
- state chips now appear on leaderboard rows
- recent-change summaries appear on rows
- “Projects needing review” panel exists and is now placed **below the leaderboard**

### 6. Agent page redesign pass

Updated:

- `/Users/harsiddhipari/hv_tracker/templates/agent.html.j2`

Changes:

- hero now shows structured trust/state summary instead of SEO-style paragraph
- recent changes block
- maintainer checklist
- warning banner for active listings needing review
- review flags block
- state badge styling

### 7. Category and compare consistency pass

Updated:

- `/Users/harsiddhipari/hv_tracker/templates/category.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/compare.html.j2`

Changes:

- category pages now show state chips beside grades
- compare pages now show:
  - registry state
  - review flags

### 8. Movers consistency pass

Updated:

- `/Users/harsiddhipari/hv_tracker/templates/movers.html.j2`
- `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`

Changes:

- mover rows now carry `display_listing_status`
- mover rows can show recent change context from current row data

Important clarification:

- a user correctly flagged confusion around Vercel AI SDK showing a historical `Rank rose 46 spots (#47 → #1)` event
- this was a real historical event on `2026-05-28`, but the UI made it easy to misread as current movement

Fix applied:

- `summarize_recent_events(...)` now prefixes the detail with the event date
- example:
  - `2026-05-28: Rank rose 46 spots (#47 → #1)`

This makes the time window explicit.

## Files changed in the latest phase

- `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`
- `/Users/harsiddhipari/hv_tracker/template.html`
- `/Users/harsiddhipari/hv_tracker/templates/agent.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/category.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/compare.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/movers.html.j2`

There are also many generated-file changes from repeated `--render-only` rebuilds.

## Additional UI pass completed after this handoff was first written

After the first handoff, a broader local UI cleanup was completed across the remaining shared templates that were still rendering an older dark/glass theme.

### Templates updated in this pass

- `/Users/harsiddhipari/hv_tracker/templates/use_case.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/methodology.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/badges.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/roadmap.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/blog_index.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/blog_category_comparison.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/spec_index.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/spec.html.j2`
- `/Users/harsiddhipari/hv_tracker/templates/movers.html.j2`

### Design direction applied

The shared direction is now:

- warm paper background
- darker ink text
- restrained borders instead of glass/shadow treatment
- pastel blue for control and button-like UI
- muted lobster as a secondary accent
- generally more Japanese editorial / registry restraint and less “AI dashboard template”

This pass was intentionally surgical:

- no product IA changes
- no data-model changes beyond what already existed
- only template/CSS cleanup plus one copy clarification on the movers page

### Movers page clarification

The movers hero copy previously implied that the latest trust event shown was the direct explanation for the net move.

That is not always true. A project can have:

- a net rise over the comparison window
- but a most recent event inside that same window that is a drop

The copy was updated to say:

- the page shows net rank delta
- plus the latest tracked trust event within that window

This is more accurate and less misleading.

## What now renders in the new style

Verified local outputs after `python3 fetch_and_build.py --render-only`:

- `/Users/harsiddhipari/hv_tracker/use-cases/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/coding-agents/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/high-evidence/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/provenance-ready/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/recently-active/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/self-hosted-open-source/index.html`
- `/Users/harsiddhipari/hv_tracker/methodology/index.html`
- `/Users/harsiddhipari/hv_tracker/badges/index.html`
- `/Users/harsiddhipari/hv_tracker/roadmap/index.html`
- `/Users/harsiddhipari/hv_tracker/blog/index.html`
- `/Users/harsiddhipari/hv_tracker/spec/index.html`
- `/Users/harsiddhipari/hv_tracker/movers/index.html`

The current generated `movers/index.html` also now includes:

- pastel-blue and lobster accents
- calmer paper styling
- updated mover-window copy

## Known UI issues still open

These are the most important follow-ups for the next pass.

### 1. Radar charts still look visually broken on lighter pages

This is the biggest unfinished UI issue.

Problem:

- several radar charts were originally styled for dark backgrounds
- after the template/palette migration, the chart internals still carry old hard-coded light-on-dark colors in SVG output
- this makes labels and chart elements look mismatched or washed out on paper pages

Symptoms seen in generated pages:

- axis/label text inside radar SVGs still use dark-theme values like `#eef2f6` and `#8fb3ff`
- chart backgrounds / strokes still assume a dark surface
- on lighter pages this reads as visually inconsistent or broken

Pages affected most visibly:

- `/Users/harsiddhipari/hv_tracker/movers/index.html`
- `/Users/harsiddhipari/hv_tracker/use-cases/index.html`
- likely any page using the generated radar SVG helpers

What to inspect:

- radar SVG generation inside `/Users/harsiddhipari/hv_tracker/fetch_and_build.py`
- look for hard-coded fill/stroke/text colors in SVG builders

Goal:

- make chart colors inherit or explicitly match the new paper palette
- ensure labels, gridlines, panel fills, and accent polygons are all readable on the lighter background

### 2. Hand-written blog articles are still old-theme islands

Important distinction:

- category-comparison blog pages are now styled via shared templates
- but the long-form static research articles under `blog_static/` are still authored as standalone HTML and keep the old dark theme

Affected source directory:

- `/Users/harsiddhipari/hv_tracker/blog_static/`

Because the build copies these directly, the generated `/blog/...` pages for those articles still look old.

Observed examples:

- `/Users/harsiddhipari/hv_tracker/blog/github-stars-dont-predict-ai-agent-trust/index.html`
- `/Users/harsiddhipari/hv_tracker/blog/codex-vs-claude-code/index.html`
- `/Users/harsiddhipari/hv_tracker/blog/how-to-evaluate-ai-agent-safety/index.html`
- `/Users/harsiddhipari/hv_tracker/blog/most-starred-ai-agents-no-provenance/index.html`
- `/Users/harsiddhipari/hv_tracker/blog/you-are-not-installing-what-you-think/index.html`

Recommendation:

- either migrate those seven static files to the new paper palette
- or extract them onto a shared article template later

For the next pass, a direct CSS-only migration is probably the lowest-risk choice.

### 3. `Needs review` may not appear on movers until a warning-listed mover is actually in the movers set

This is not currently a bug in the template.

What was verified:

- `display_status_label` exists in data generation
- movers template uses `item.display_status_label`
- current generated movers page simply does not contain a warning-row example in the visible mover set, so the string `Needs review` may not appear in the output snapshot

Do not treat that absence alone as a template failure.

## Suggested next steps for Claude Code

Priority order:

1. fix radar chart SVG colors in `fetch_and_build.py`
2. rebuild locally with `python3 fetch_and_build.py --render-only`
3. verify the chart-bearing pages visually and by spot-checking SVG color tokens
4. migrate `blog_static/*/index.html` off the old dark theme
5. rebuild again and verify copied `/blog/...` outputs

## Useful verification commands

Render-only rebuild:

- `python3 /Users/harsiddhipari/hv_tracker/fetch_and_build.py --render-only`

Check for old dark-theme tokens in shared templates/generated outputs:

- `rg -n -g '*.j2' -g '*.html' -- "--bg:#0b0d10|--bg:        #0b0d10|backdrop-filter|glass-hi|panel-shadow|linear-gradient\\(180deg,#10141a|linear-gradient\\(180deg, #10141a" /Users/harsiddhipari/hv_tracker/templates /Users/harsiddhipari/hv_tracker/use-cases /Users/harsiddhipari/hv_tracker/methodology /Users/harsiddhipari/hv_tracker/badges /Users/harsiddhipari/hv_tracker/roadmap /Users/harsiddhipari/hv_tracker/blog /Users/harsiddhipari/hv_tracker/spec`

Check the static blog island:

- `rg -n -- "--bg:#0b0d10|--surface:#151920" /Users/harsiddhipari/hv_tracker/blog_static /Users/harsiddhipari/hv_tracker/blog`

Spot-check regenerated pages for paper palette:

- look for `#f4f1eb`, `#7f9cbd`, and `#c67c6d` in the target HTML files

## Local verification already performed

Repeatedly run successfully:

- `python3 -m py_compile fetch_and_build.py`
- `python3 fetch_and_build.py --render-only`

Observed outputs during recent rebuilds:

- `data/latest.json` updated correctly
- active warning projection worked:
  - `warning_agents 6`
- generated pages updated:
  - homepage
  - agent pages
  - category pages
  - compare pages
  - movers page

Sanity checks performed:

- warning state exists in generated homepage and agent pages
- compare/category pages include state signaling
- misleading license-change events removed
- recent-change summaries now include event dates

## Important current behavior

### Warning state is derived, not canonical

This is important.

Right now:

- `listing_status` in canonical config is still mostly `listed` / `legacy`
- `warning` is **derived at render/build time** from eligibility violations

That means:

- the product now displays warning state correctly enough for users
- but the registry model is still not fully migrated to a first-class lifecycle workflow

## Known open issues / remaining work

### High priority

1. Canonical lifecycle model

Still pending:

- make `warning` a first-class canonical state where appropriate
- separate clearly:
  - `listed`
  - `warning`
  - `legacy`
  - `rejected`
  - `delisted`

Current code still treats warning mostly as a display overlay.

2. Correction/reviewer workflow

Still not built:

- structured correction intake
- review queue
- decision logging
- override reasons

3. Alerts/feed/webhooks

Still not built:

- trust drop alerts
- listing-state change alerts
- provenance/license/archive alerts

### Product/UI work still pending

4. Movers page can still be improved

It is more consistent now, but still not a full reason-first movers page.

Ideal next step:

- explicitly separate:
  - mover window delta
  - latest recent event
- maybe show both with labels instead of one inline sentence

5. Compare redesign

Still fairly table-centric.

Needs:

- clearer trust verdict framing
- explicit warning handling
- better “what changed recently” comparisons

6. Broader UI cleanup

Homepage/profile are improved, but the redesign is not finished.

Still worth revisiting:

- visual density and hierarchy across all secondary pages
- remove remaining template-like/glossy behaviors where they still show through

### Policy/state decisions still needed

7. Decide how to handle currently active-but-problematic rows

Examples already surfacing as warning:

- archived repos still displayed active with `warning`
- no-license repos still displayed active with `warning`

This is now visible, which is good.

But product policy still needs a decision:

- stay active with warning?
- move to delisted/rejected/legacy?

## Immediate next recommended steps

If continuing from here, the best order is:

1. Make lifecycle states canonical, not just derived
2. Redesign movers page around explicit windows and reason codes
3. Add correction/reviewer workflow
4. Add alerts/feed/webhook layer

## Notes about the worktree

- The repo is dirty.
- Many generated files changed because of local rebuilds.
- Do not assume a clean diff limited to source templates.
- Avoid reverting unrelated generated output unless explicitly asked.

## Useful local commands

Rebuild locally without API calls:

```bash
python3 fetch_and_build.py --render-only
```

Quick syntax check:

```bash
python3 -m py_compile fetch_and_build.py
```

Check warning-projected agents:

```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('data/latest.json').read_text())
warning_agents=[a for a in obj['agents'] if a.get('display_listing_status')=='warning']
print('warning_agents', len(warning_agents))
for a in warning_agents[:10]:
    print(a['repo'], a.get('warning_reasons'))
PY
```

Check recent-change summary for a specific repo:

```bash
python3 - <<'PY'
import json
from pathlib import Path
obj=json.loads(Path('data/latest.json').read_text())
for a in obj['agents']:
    if a['repo']=='vercel/ai':
        print(a.get('recent_change_summary'))
        break
PY
```
