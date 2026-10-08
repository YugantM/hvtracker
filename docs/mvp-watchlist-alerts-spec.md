# MVP spec: Watchlist + Score-Change Alerts ("monitor your stack")

Status: ready to build · Drafted 2026-10-08 · Target repo: `~/hvtracker`
Owner build session: separate (this file is the handoff).

> Reconcile with `docs/growth-plan.md`, `docs/product-plan-2026-h2.md`, and
> `docs/open-core.md` before starting — this spec should slot into those, not
> contradict them.

---

## 1. Why / goal

HVTracker's human traffic is ~29 real visits/day and **89% of organic visitors are
new** — people Google "is X safe", read the verdict once, and never return. There is
**no returning audience, no email list, and branded search ≈ 0.** Engagement is
excellent (3.5-min sessions), so the content works; what's missing is a *reason to come
back*.

**Goal of this MVP:** convert one-time trust-checkers into returning, signed-in users by
letting them **monitor the tools in their own stack** and get **alerted when a tool's
trust changes** — which simultaneously (a) creates return visits, (b) builds an opt-in
email list, and (c) gives us the *only* honest, high-open-rate email to send.

**Principle:** login to get MORE (save, monitor, alert), never login to see what you came
for. The public trust pages stay fully open and citable — do **not** gate them (gating
would reverse the Sept page-1 breakout and kill the citation surface that is our #1 growth
lever).

**Success metrics (instrument from day one):**
- signups/week, watch-adds/week, % of signups with ≥1 watched tool
- alert emails sent, open rate, click-through back to site
- returning-user share of organic (today ~11%) — should rise

---

## 2. What ALREADY exists (do NOT rebuild — verify then reuse)

Confirmed by code read 2026-10-08:

| Capability | Where | State |
|---|---|---|
| OAuth login (GitHub + Google) + signed-cookie sessions, `current_user()`, dev-login | `auth.py` (`SESSION_COOKIE=hvt_session`, `current_user()`, `/auth/{provider}/login`, `/auth/dev-login`) | **Real** |
| `/account` page (shows signed-in user's data) + `/login` | `app.py` ~L561 (CDN varies on these paths) | Exists — verify contents |
| Postgres data layer (gated on `DATABASE_URL`, psycopg; falls back to agents.json read-only) | `db.py`, `schema.sql` | **Real** |
| `users` table + `upsert_user/get_user`, password users | `db.py` L308-366, `schema.sql` L90 | **Real** |
| `watchlist` table + `list_watch/add_watch/remove_watch` | `db.py` L370-391, `schema.sql` L106 | **Real (data layer only)** |
| `notification_reads` (per-user `last_read_at`) + `get/set_last_read` | `db.py` L395-410, `schema.sql` L113 | **Real** |
| "Scan your stack" — paste requirements.txt / package.json / MCP config → per-item verdict | `app.py` `/scan`, `POST /api/v1/scan`, `_parse_scan_input()` L854 | **Real, working** |
| `verify_checks` (latest grade/score snapshot per repo, upsert) | `db.py` L169-245, `schema.sql` L58 | **Real (latest only)** |
| **Change-detection engine** — `diff_snapshots(baseline, latest)` → per-agent `{new_score, delta, ...}`; `compute_weekly_changes(history)`; powers public `/changes` feed | `fetch_and_build.py` L4171-4219 | **Real — REUSE THIS for alerts** |
| Email *capture* (waitlist) → `interest_signups` | `db.py` `add_interest_signup` L140, `schema.sql` L40 | Real |
| Rate limiting, honeypot, field-length guards on forms | `app.py` `_is_rate_limited`, `HONEYPOT_HTML`, `_check_field_lengths` | Real — reuse |
| History snapshots (per-day, 90-day public window) | `output/history/`, `/api/v1/agents/{slug}/history` | Real — source for diffs |
| Scaffolded tests | `tests/test_account_watchlist.py`, `tests/test_watchlist_alerts.py`, `tests/test_notifications.py` | **Read these first — make them pass** |

**Fake-doors to REPLACE with the real thing:**
- `GET/POST /alerts` — currently a "fake-door by design" collecting waitlist emails into
  `interest_signups` (app.py L2056-2129). Explicitly says "validating demand before
  building accounts, saved watchlists, and alert pipelines."
- `GET/POST /track/{slug}` — same pattern (app.py L2131-2175).

**Does NOT exist (the real gaps this MVP fills):**
1. Logged-in watchlist **UX** wired to `add_watch/remove_watch` (a real "☆ Watch" control
   on agent/MCP/compare pages + a list on `/account`).
2. **Transactional email sending** — none. Only email-regex validators and `boto3` for S3
   (`storage.py`). No SMTP/provider.
3. The **alert pipeline**: changed tools (from `diff_snapshots`) → users watching them →
   notification + email, with de-dupe.
4. **Scan → watchlist bridge** (let a logged-in user watch everything in a scan).
5. Email **prefs / verification / unsubscribe**.

---

## 3. Scope

### In scope (MVP)
1. Real watchlist: watch/unwatch any agent / MCP server / skill while logged in.
2. `/account` watchlist view: each watched tool with current grade/score + last change.
3. Scan → "Watch all" bridge on `/scan` results for logged-in users.
4. Alert pipeline: per refresh, diff scores, find affected watchers, write alert events.
5. In-app notifications (unread badge) using `notification_reads` + alert events.
6. **Email alerts**: batched per-user email when a watched tool's grade/score crosses a
   threshold, with verification + one-click unsubscribe + frequency preference.
7. Replace `/alerts` and `/track/{slug}` fake-doors with real flows (keep the captured
   `interest_signups` emails — offer to migrate/notify them).
8. Conversion CTAs: soft "☆ Watch — sign in" prompts on trust pages (non-blocking).

### Explicitly NOT in scope
- Any gating/blurring of public content.
- Paid tiers / billing (watchlist is free; this is the acquisition layer). Note where the
  paid line will later sit (API tier, bulk, org seats) but don't build it.
- Webhooks/Slack alerts (phase 2 — leave a seam).
- Mobile app, teams/orgs, SSO beyond existing OAuth.

---

## 4. Architecture

```
fetch_and_build refresh (existing cron)
  └─ diff_snapshots(baseline, latest)         # already computes per-slug score/grade deltas
       └─ alerts.detect_changes(diff)         # NEW: filter to "alert-worthy" changes
            └─ for each changed slug:
                 watchers = db.watchers_for(slug)        # NEW: reverse index on watchlist
                 for user in watchers:
                    db.add_alert_event(user, slug, change)   # NEW: in-app feed + de-dupe
       └─ alerts.send_pending_emails()         # NEW: batch per-user, respect prefs/verified/unsub
```

- **Reuse `diff_snapshots`** — do not write new change detection. It already returns the
  per-agent score/grade deltas that power `/changes`. Add a thin `alerts` module that
  consumes its output.
- **Trigger point:** the refresh that writes the daily history snapshot (where
  `compute_weekly_changes`/`diff_snapshots` already run). Alerts piggyback there; no new
  cron. Guard with an env flag (`ALERTS_ENABLED`) and the existing `DISABLE_SCHEDULER`
  semantics.
- **Idempotency:** an `alert_events` row is unique per (user, slug, change-signature) so a
  re-run of the same refresh never double-sends. Email send is logged (`emailed_at`) so a
  crash mid-send resumes without duplicates.
- **Storage:** Postgres (already the backend). Email via provider HTTP API (§7).

---

## 5. Data model (additions to `schema.sql`)

```sql
-- What changed, for whom, and whether we've notified. Drives both the in-app
-- feed and the email batch. change_sig makes re-runs idempotent.
CREATE TABLE IF NOT EXISTS alert_events (
  id            bigserial PRIMARY KEY,
  user_id       bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_slug    text   NOT NULL,
  kind          text   NOT NULL,        -- 'grade_drop' | 'grade_rise' | 'score_move' | 'provenance_lost' | 'delisted'
  old_value     text,
  new_value     text,
  change_sig    text   NOT NULL,         -- e.g. sha1(slug|kind|old|new|snapshot_date)
  created_at    timestamptz NOT NULL DEFAULT now(),
  emailed_at    timestamptz,            -- NULL = not yet emailed
  UNIQUE (user_id, change_sig)
);
CREATE INDEX IF NOT EXISTS alert_events_user_unemailed
  ON alert_events (user_id) WHERE emailed_at IS NULL;

-- Reverse lookup watchers_for(slug) is just: SELECT user_id FROM watchlist WHERE agent_slug=%s
CREATE INDEX IF NOT EXISTS watchlist_by_slug ON watchlist (agent_slug);

-- Per-user email prefs. Default: alerts ON, weekly cadence, must verify first.
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_cadence text NOT NULL DEFAULT 'instant';   -- 'instant'|'daily'|'weekly'|'off'
ALTER TABLE users ADD COLUMN IF NOT EXISTS unsub_token text;   -- random, for one-click unsubscribe
```

New `db.py` functions: `watchers_for(slug)`, `add_alert_event(...)`, `unemailed_events(user_id)` /
`pending_email_batches()`, `mark_emailed(ids)`, `set_alert_cadence`, `set_email_verified`,
`get_user_by_unsub_token`, `set_cadence_off_by_token`.

**Change-worthiness rule (in `alerts.detect_changes`)** — avoid noise:
- `grade_drop` / `grade_rise`: letter grade changed (A↔B↔C↔D↔F).
- `score_move`: |delta| ≥ 5.0 points (tune; `diff_snapshots` already gives `delta`).
- `provenance_lost`: had build provenance, now doesn't.
- `delisted`: slug left the catalog (retired).
Only these generate events. Cosmetic rank shuffles do not.

---

## 6. Component specs

### 6.1 Real watchlist control (replace fake-door)
- Add a `POST /api/v1/watch` `{slug, on:bool}` (JSON, session-auth via `current_user`).
  Returns `{watching:bool, count}`. 401 → front-end shows the login CTA.
- On agent (`templates/agent.html.j2`), MCP, and compare pages, render a **☆ Watch**
  button. Logged-out: button links to `/auth/github/login?next=<page>` with copy
  "Watch this tool — sign in". Logged-in: toggles via the API, optimistic UI.
- Repurpose `GET /track/{slug}`: if logged-in, 302 to the tool page with watch applied (or
  to `/account`); keep the pretty URL. Remove the waitlist form.

### 6.2 `/account` watchlist view
- List `list_watch(user_id)` joined to current agent data: name, grade, score, last change
  (most recent `alert_events` for that slug), link. Unwatch inline.
- Unread alert feed (events since `get_last_read`); calling the page sets `set_last_read`.
- Email prefs: cadence selector (instant/daily/weekly/off), verified-state, resend-verify.

### 6.3 Scan → watchlist bridge
- `/scan` already parses a stack and scores each item. For logged-in users, add
  **"☆ Watch all N tools"** and per-row watch toggles on the results.
- Do **not** store raw pasted configs. Only persist the resolved slugs the user explicitly
  watches. (Privacy: the scan itself stays ephemeral unless they watch items.)

### 6.4 Alert pipeline (the core new logic — `alerts.py`)
- `detect_changes(diff) -> list[Change]` consuming `diff_snapshots` output.
- For each change: `watchers_for(slug)` → `add_alert_event(...)` (unique on change_sig).
- `send_pending_emails()`:
  - group `alert_events` with `emailed_at IS NULL` by user, respecting `alert_cadence`
    (instant = send now; daily/weekly = only when the cadence window elapsed; off = skip).
  - only send to `email_verified_at IS NOT NULL`.
  - render one digest email per user ("3 tools you watch changed"), send, `mark_emailed`.
- Runs inside the refresh, behind `ALERTS_ENABLED`. Fully idempotent.

### 6.5 In-app notifications
- Unread count = `alert_events` for user with `created_at > last_read`. Badge in header
  (the `hvt_signed_in` hint cookie already lets the front-end know a session exists without
  an API call — reuse it to decide whether to fetch the count).

### 6.6 Email delivery (§7 for provider)
- `email.py`: `send(to, subject, html, text, unsub_url)` — thin wrapper over the provider.
- Templates: (a) **verify your email** (sent on first alert opt-in), (b) **alert digest**.
  Plain, dev-audience, text + minimal HTML. Every email has List-Unsubscribe header + a
  one-click `GET /unsub/{token}` that sets cadence 'off'.
- Verification: on enabling alerts, send verify link `GET /verify-email/{token}`; set
  `email_verified_at`. No alert emails until verified (anti-abuse + deliverability).

### 6.7 CTAs / conversion
- Soft, non-blocking "☆ Watch — sign in" on trust pages and scan results. Never a wall.
- Convert existing `interest_signups` (alerts/track waitlist emails): one-time
  announcement email (if we can send to them under their original opt-in) inviting them to
  create an account and re-add watches. Check original consent copy before mailing.

---

## 7. Email provider (decision needed; recommendation below)

Constraints: <$10/mo budget, low volume (hundreds of users, low-frequency alerts),
dev-grade deliverability, minimal new infra. `boto3` is already a dep but S3 here uses a
**custom endpoint** (`S3_ENDPOINT` — likely R2/Backblaze, not AWS), so AWS SES is NOT
already wired.

**Recommended: Resend** — 3,000 emails/mo free, 100/day; simple HTTPS API (no new SDK, just
`requests`); good deliverability; easy DKIM/SPF setup. Fits the budget with headroom.

Alternatives: **AWS SES** (cheapest at scale, ~$0.10/1k, but needs an AWS account + domain
verification + out-of-sandbox request) ; **Postmark** (best deliverability, 100/mo free
then paid). Pick Resend for the MVP unless an AWS account is already handy.

**Setup task (ops):** a sending subdomain `alerts.hvtracker.net` (or `mail.`) with
SPF + DKIM + DMARC, sender `alerts@hvtracker.net`. Record in `docs/incident-playbook.md`.

Secrets: `RESEND_API_KEY` (Railway env), `ALERTS_FROM`, `ALERTS_ENABLED`.

---

## 8. Privacy / safety / anti-abuse
- Public content stays open; nothing gated. No cloaking.
- Raw scanned configs never stored — only explicitly-watched slugs.
- Email verification required before any alert send; one-click unsubscribe; List-Unsubscribe.
- Reuse existing `_is_rate_limited`, honeypot, field-length guards on new POST forms.
- Session auth only for write endpoints (`current_user`); CSRF: forms already use the
  signed state pattern — keep POSTs same-origin + session-bound.
- Idempotent sends (change_sig + emailed_at) so a refresh re-run or crash never spams.

---

## 9. Build order (shippable slices)
1. **Schema + db fns** (alert_events, prefs cols, watchers_for, event fns) + make
   `tests/test_account_watchlist.py` pass. Ship watch/unwatch API + ☆ button + `/account`
   list. *(Real watchlist, no emails yet — already useful, fully testable.)*
2. **Alert detection**: `alerts.detect_changes` on `diff_snapshots`, write `alert_events`,
   in-app unread feed. Make `tests/test_watchlist_alerts.py` + `test_notifications.py` pass.
3. **Email**: `email.py` + Resend + verify flow + unsubscribe + digest template +
   `send_pending_emails()` in refresh behind `ALERTS_ENABLED`.
4. **Scan → watch bridge** on `/scan` results.
5. **Convert fake-doors** (`/alerts`, `/track/{slug}`) to real flows; migrate waitlist.
6. **Instrument** signup/watch/alert metrics (extend `usage.py` / machine_usage pattern).

Each slice deploys independently (Railway `railway up` — see
`docs/plan-history-storage-railway.md` and the deploy memory: single-attach volume, manual
deploy, in-container render; run schema migration on boot via `db.init_schema()`).

## 10. Open decisions for the build session
- Email provider final pick (Resend vs SES) — depends on whether an AWS acct is handy.
- Default cadence: `instant` vs `daily`? (Spec defaults `instant`; daily is calmer — decide.)
- Watchable types: agents only first, or agents+MCP+skills from day one? (Watchlist stores
  `agent_slug`; MCP/skills are rows in the same catalog, so likely all three — confirm slug
  space is unified.)
- Does `verify_checks` or `output/history/` give a clean previous-snapshot for diffing at
  alert time? (`diff_snapshots` uses history baseline vs latest — confirm it's the right
  granularity for per-refresh alerts vs weekly.)
- What consent did `interest_signups` capture — can we email those addresses now?

## 11. Test plan
- Unit: `detect_changes` thresholds (grade cross, ±5 score, provenance loss, delist);
  change_sig idempotency; cadence windowing; unsub token flow.
- Integration (extend existing scaffolded tests): watch→change→event→email de-dupe; a
  refresh re-run sends nothing new; verified-gate blocks unverified sends.
- Manual: dev-login (`HVT_DEV_AUTH=1`) → watch a tool → simulate a grade drop in a test
  snapshot → assert in-app unread + one email with working unsubscribe.
