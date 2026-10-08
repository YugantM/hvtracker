# Watchlist alert emails: runbook

Signed-in users track projects (profile Track button, `/track/<slug>/`, `/scan/`
"Watch all"). Changes on tracked projects always show in the header bell and
on `/account`. This doc covers the opt-in **email digest** on top of that
(`alerts.py`, `mailer.py`). It ships dark: nothing is sent and `/account`
shows no email option until it is switched on.

Status 2026-10-08: built, **off**. `docs/product-plan-2026-h2.md` puts hosted
alert delivery behind the visa/monetization gate, so switching it on is an
owner decision. The digests are free and carry no paid-tier code.

## How it works

1. Every render (`fetch_and_build.main`, inside the refresh subprocess) calls
   `alerts.run()` after `recent_events` are written. `derive_agent_events` is the
   source, so an email never says something the profile timeline doesn't.
2. Only **finished days** count (`oldest <= date < today`, `LOOKBACK_DAYS = 3`).
   Every render until midnight UTC rewrites today's snapshot, so a change seen at
   08:00 can be gone by 12:00. A day's changes therefore go out after the first
   render of the next day (~00:00–04:00 UTC).
3. Emailed kinds (`ALERT_KINDS`): `grade_changed`, `trust_score_changed`
   (≥3 points, as on the timeline), `provenance_removed`, `drift_warning_raised`,
   `warning_issued`, `delisted`. Methodology cutovers are already suppressed
   upstream. Rank, activity-score, license and Scorecard churn stay in the bell.
4. For each changed slug, opted-in watchers get one `alert_events` row per
   change (unique on `(user_id, change_sig)`), but only for changes on or after
   the later of when they started watching and when they confirmed the address.
5. `send_pending()` sends one digest per user when due: daily = at most every
   20 h; weekly = 7 days after the last digest (or after opting in). Rows are
   marked `emailed_at` only after Resend accepts the message. The request
   carries an `Idempotency-Key` (`hvt-digest-<user>-<max row id>`), so a crash
   between sending and marking can't double-send within 24 h.

Opt-in: `/account` → "Email me at <address>" sends a confirmation link
(throttled to one per 10 min per user). `GET /verify-email/<token>` shows a
button; the `POST` confirms. Scanners that fetch links in mail can't confirm or
unsubscribe. The token is bound to the address it was sent to and expires
after 48 h. Digests go to `users.alert_email`, the confirmed address, even if
the sign-in provider's email changes later.

Unsubscribe: every digest has `List-Unsubscribe` plus the RFC 8058 one-click
`List-Unsubscribe-Post` header, pointing at `POST /unsub/<token>`. The link in
the body opens a page with a button. Unsubscribing sets `alert_cadence = 'off'`
and deletes the unsent queue, so opting back in later doesn't send stale
changes. Tokens are HMAC-signed with `HVT_SESSION_SECRET`. Rotating the secret
breaks links in mails already sent; `/account` still works.

## Switching it on (owner)

1. Resend account (free tier: 3,000/month, 100/day). Add a sending domain,
   e.g. `alerts.hvtracker.net`, and publish the SPF, DKIM and DMARC records
   Resend shows in Cloudflare DNS. Wait until Resend says "verified".
2. Railway env on `web`: `RESEND_API_KEY`, `ALERTS_FROM` (default
   `HVTracker alerts <alerts@hvtracker.net>`; must be on the verified domain),
   `ALERTS_ENABLED=1`. `HVT_BASE_URL` defaults to `https://hvtracker.net`.
3. Applying env changes redeploys the service. Follow the deploy runbook in
   CLAUDE.md, including the `refresh_in_progress` check.
4. Test on yourself: `/account` → opt in → confirm → look for
   `[alerts] … queued; … digest(s) sent` lines in the boot or 4-hourly render logs.

**Kill switch:** unset `ALERTS_ENABLED`. Rendering, queuing and sending stop.
Links in mails already sent keep working.

## Numbers

`DATABASE_URL=… python scripts/account_stats.py [--days 7]`: users, signups,
share tracking ≥1 project, watch adds, opt-ins, changes queued and emailed.
Digest click-through shows in GA as `utm_campaign=watchlist-digest`. Opens are
not tracked; that needs a pixel, which the digests don't carry. Client events
in GA: `scan_watch_all`, `track_signin_nudge`, `watchlist_add`.

## The old waitlists

`/alerts` and `/track/<slug>` used to collect emails into `interest_signups`
(`kind` = `alerts` / `track-agent`). The rows are kept. Their consent copy:
"I will reach out when the first trust alerts are ready" and "When the first
tracked-agent workflow is ready, these are the people I will contact first".
That covers one personal "it's ready" note. Nothing has been sent to them;
whether and when to send it is the owner's call.
