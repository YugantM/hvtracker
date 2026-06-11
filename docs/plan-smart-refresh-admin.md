# Smart Refresh + Admin Plan

Goal: make leaderboard refresh feel closer to real time while staying inside free API quotas, and add a small private admin surface to inspect and control refresh behavior.

This plan is intentionally scoped for a medium-effort GPT-5.4-mini pass. It avoids a big architecture rewrite.

## Assumptions

- Keep the current FastAPI app and in-process scheduler for now.
- Keep Railway as the runtime.
- Use the existing Postgres service for refresh state instead of adding a new queue system.
- Use existing per-agent activity signals already present in generated data where possible.
- Admin access should be private-by-default, but "attack proof" is not a realistic claim for any internet-exposed app. We aim for strong layered protection.

## Non-Goals

- No separate worker service in this phase.
- No full migration of historical site data into Postgres in this phase.
- No arbitrary command execution from the admin page.
- No replacement of the current scoring/ranking logic.

## Current Behavior

- Scheduler runs every 2 hours in `app.py`.
- `auto` refresh maps to fixed `--batch N/6` slices in `fetch_and_build.py`.
- Batch membership is deterministic by repo name, not by freshness or activity.
- External quota pressure mainly comes from PyPI, fingerprint/public action fetches, and stale scorecard/API refreshes.

## Target Behavior

- Refresh the most active / most important agents more often.
- Refresh low-activity agents less often.
- Stay within free API budgets by pacing providers separately.
- Keep a human-readable admin page showing what the scheduler is doing.
- Allow a few safe manual actions: dry-run, run one cycle, refresh one agent, pause/resume scheduler.

## Phase 1: Smart Refresh State

Add small persistent tables in Postgres:

- `agent_refresh_state`
  - `repo` text primary key
  - `priority_tier` text
  - `last_refreshed_at` timestamptz
  - `last_selected_at` timestamptz
  - `next_refresh_at` timestamptz
  - `refresh_interval_minutes` int
  - `last_error` text
  - `consecutive_failures` int default 0
  - `last_activity_score` numeric
  - `last_priority_reason` text

- `provider_budget_state`
  - `provider` text primary key
  - `window_started_at` timestamptz
  - `window_minutes` int
  - `budget_limit` int
  - `budget_used` int
  - `last_error` text

- `admin_audit_log`
  - `id` uuid or bigserial
  - `created_at` timestamptz
  - `actor` text
  - `action` text
  - `target` text
  - `result` text
  - `meta_json` jsonb

Verify:
- schema migration runs locally
- tables can be seeded from current `data.json` / `agents.json`

## Phase 2: Priority Calculation

Add a small deterministic planner module or helper functions. Keep it simple.

Inputs per agent:

- current rank
- trust score
- weekly commits
- `days_ago`
- recent rank movement
- whether signals are missing
- whether the repo is newly added

Suggested priority tiers:

- `hot`
  - top 25 agents, or newly added, or missing important signals, or large recent movement
  - target refresh every 4 hours

- `warm`
  - active maintained agents with moderate movement
  - target refresh every 12 hours

- `cold`
  - low-activity agents
  - target refresh every 48 hours

- `legacy`
  - legacy or rarely changing entries
  - target refresh every 7 days

Keep the first scoring rule dumb and explainable. Example:

- start at 0
- +3 if rank <= 25
- +2 if weekly commits >= 20
- +2 if days_ago <= 14
- +2 if rank moved by >= 3 recently
- +3 if pending/missing signals
- +4 if newly added

Map score to tier.

Verify:
- unit tests for tier assignment with fixed fixtures
- dry-run output shows tier and reason per selected repo

## Phase 3: Replace Fixed Batch Selection

Replace deterministic `1/6` batch selection in `auto` mode with:

1. load eligible agents from refresh state
2. filter agents where `next_refresh_at <= now`
3. sort by:
   - tier
   - overdue-ness
   - rank importance
   - missing signals
4. take as many agents as the provider budgets allow

Important: keep a hard cap per cycle so one run stays bounded.

Recommended starting limits:

- max 25 active agents per auto cycle
- max 5 legacy agents per auto cycle

Fallback:

- if refresh state is empty or broken, fall back once to current batch logic

Verify:
- `auto` still completes successfully
- selected agents are no longer repo-name slices
- low-priority agents are skipped when budgets are tight

## Phase 4: Provider Budgets

Track quota use at the provider level, not just per run.

Providers to model first:

- `pypi_downloads`
- `pypi_provenance`
- `github_actions_search`
- `scorecard_api`
- `hn_search`

Behavior:

- each cycle resets a provider window if expired
- each API call increments `budget_used`
- if a provider budget is exhausted, skip that signal and continue the rest
- mark the agent with a reason like `skipped_pypi_budget`

Do not overcomplicate this with token buckets yet. Fixed windows are enough for phase 1.

Example starting budgets:

- PyPI downloads: 40 calls / 2 hours
- PyPI provenance: 80 calls / 2 hours
- GitHub public actions search: 30 calls / 2 hours
- Scorecard API: 20 calls / 2 hours, prefer cache first
- HN search: 60 calls / 2 hours

Verify:
- simulated budget exhaustion skips only affected signals
- cycle still succeeds and persists partial results cleanly

## Phase 5: Human-Testable Worker Controls

Add safe commands first, before the admin page:

- `python3 fetch_and_build.py --dry-run-auto`
- `python3 fetch_and_build.py --auto-once`
- `python3 fetch_and_build.py --refresh-agent owner/repo`
- `python3 fetch_and_build.py --recompute-refresh-state`

Dry-run output should show:

- selected agents
- skipped agents
- remaining provider budgets
- tier/reason per selected agent
- estimated call counts

Verify:
- one-cycle commands can be run locally in minutes
- dry-run is deterministic with fixed time input

## Phase 6: Private Admin Page

Use a separate subdomain: `admin.hvtracker.net`

Security layers:

- protect the subdomain with Cloudflare Access
- require allowed email identity
- add app-side admin secret/session check as defense in depth
- no public links from the main site
- aggressive rate limiting on `/admin/*`
- audit log every admin action

Admin page scope:

- current scheduler status
- last refresh time
- next due agents
- provider budgets remaining
- recent failures
- manual actions:
  - dry-run cycle
  - run one cycle
  - refresh one agent
  - pause scheduler
  - resume scheduler

No arbitrary command input box.

Verify:
- unauthorized request gets denied
- authorized access can see dashboard
- manual actions create audit log rows

## Phase 7: Scheduler Controls

Minimal additions:

- `REFRESH_AUTOMATION_ENABLED=1|0`
- in-memory pause toggle backed by Postgres or a small settings table

Behavior:

- scheduler can remain installed
- if paused, scheduled cycles log a skipped reason and exit cleanly

Verify:
- paused scheduler does not mutate data
- resume restores normal scheduling

## Tests

Add focused tests only:

- tier calculation
- next refresh scheduling
- provider budget exhaustion
- due-agent selection order
- admin auth gate
- admin audit logging

Do not try to integration-test the infinite loop.
Test one cycle at a time.

## Suggested File Scope

- `db.py`
  - schema helpers and small CRUD for refresh state / budgets / audit log

- `fetch_and_build.py`
  - planner helpers
  - one-cycle auto refresh path
  - dry-run / single-agent commands

- `app.py`
  - small admin routes
  - auth gate
  - scheduler pause/resume hooks

- `templates/`
  - one minimal admin template

## Success Criteria

1. Smart refresh replaces fixed repo-name batches for `auto` mode.
   Verify: a dry-run shows activity/freshness-based selection.

2. The system respects provider budgets instead of failing the whole cycle.
   Verify: forced budget exhaustion still completes a cycle with skip reasons.

3. A human can inspect and manually trigger one cycle safely.
   Verify: admin page shows status and one-cycle controls.

4. The implementation is small enough for a medium-effort model pass.
   Verify: no new service, no queue framework, no major rewrite.

## Recommended Delivery Order

1. DB state tables
2. tier planner + tests
3. due-agent auto selection
4. provider budgets
5. CLI dry-run / one-cycle tools
6. admin auth + admin page
7. scheduler pause/resume

## Nice-to-Have Later

- move refreshing to a dedicated worker service
- store full historical snapshots in Postgres/object storage
- show per-agent freshness on the public site
- add alerting when provider budgets are exhausted too often
