"""Watchlist alert emails: changes on tracked projects, sent as per-user digests.

Runs at the end of every render (fetch_and_build.main, inside the refresh
subprocess) and does nothing unless enabled(): ALERTS_ENABLED=1, a database,
and a mail provider (mailer.py). The web side (auth.py) uses the same switch
to show or hide the opt-in on /account.

The changes come from derive_agent_events: the same events as the profile
timeline and the header bell, so an email never says something the page
doesn't. Only finished days count. Every render until midnight UTC rewrites
today's snapshot, so a change seen at 08:00 can be gone by 12:00; a day's
changes go out after the first render of the next day.

Idempotent: alert_events is unique per (user, change_sig), so a re-run queues
nothing new, and rows are marked emailed only after the provider accepts the
digest (with an idempotency key, so a crash between the two can't double-send).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from html import escape

import db
import mailer

# derive_agent_events types worth an email. Rank and activity-score moves,
# license and Scorecard churn stay in the bell and on the timeline.
ALERT_KINDS = frozenset({
    "grade_changed", "trust_score_changed", "provenance_removed",
    "drift_warning_raised", "warning_issued", "delisted",
})
# Finished days still eligible, so a missed render (deploy, outage) catches up.
LOOKBACK_DAYS = 3
# A digest lists at most this many changes; the rest are on the account page.
DIGEST_MAX_LINES = 40
VERIFY_TTL = 48 * 3600
BASE_URL = os.environ.get("HVT_BASE_URL", "").rstrip("/") or "https://hvtracker.net"
UTM = "utm_source=hvtracker&utm_medium=email&utm_campaign=watchlist-digest"
# The session secret (auth.py), so links verify in the web process. Not
# imported from auth: that would load FastAPI into the render subprocess.
_SECRET = (os.environ.get("HVT_SESSION_SECRET") or os.environ.get("SECRET_KEY")
           or "dev-insecure-secret-change-me")


def enabled() -> bool:
    return os.environ.get("ALERTS_ENABLED") == "1" and db.enabled() and mailer.configured()


# ------------------------------------------------------------------ tokens ---

def _mac(raw: str) -> str:
    return hmac.new(_SECRET.encode(), b"alerts:" + raw.encode(), hashlib.sha256).hexdigest()[:32]


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def make_token(user_id: int, purpose: str, email: str | None = None) -> str:
    """Signed link token. A verify token is bound to the address it was sent
    to and expires; an unsubscribe token never expires."""
    payload: dict = {"u": int(user_id), "p": purpose}
    if email is not None:
        payload["e"] = _email_hash(email)
        payload["x"] = int(time.time()) + VERIFY_TTL
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{_mac(raw)}"


def read_token(token: str, purpose: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None
    if not hmac.compare_digest(sig, _mac(raw)):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("p") != purpose:
        return None
    if "x" in payload and int(payload["x"]) < time.time():
        return None
    return payload


def email_matches(payload: dict, email: str | None) -> bool:
    return bool(email) and hmac.compare_digest(payload.get("e", ""), _email_hash(email))


# ---------------------------------------------------------------- pipeline ---

def change_sig(change: dict) -> str:
    key = "|".join((change["slug"], change["kind"], change["date"], change["detail"]))
    return hashlib.sha1(key.encode()).hexdigest()


def finalized_changes(events_by_repo: dict[str, list[dict]], rows: list[dict],
                      today: str) -> dict[str, list[dict]]:
    """Alert-worthy events from finished days in the lookback window, by slug.

    `rows` maps repos to slugs and names: current rows first, then retired and
    recent-history rows, so a delisted project still resolves.
    """
    slug_of: dict[str, str] = {}
    name_of: dict[str, str] = {}
    for r in rows:
        repo, slug = (r.get("repo") or "").lower(), r.get("slug")
        if repo and slug and repo not in slug_of:
            slug_of[repo] = slug
            name_of.setdefault(slug, r.get("name") or slug)
    oldest = (date.fromisoformat(today) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    out: dict[str, list[dict]] = {}
    for repo, events in events_by_repo.items():
        slug = slug_of.get(repo)
        if not slug:
            continue
        for ev in events:
            day = ev.get("date") or ""
            if ev.get("type") in ALERT_KINDS and oldest <= day < today:
                out.setdefault(slug, []).append({
                    "slug": slug, "name": name_of[slug], "kind": ev["type"], "date": day,
                    "detail": ev.get("detail") or ev.get("label") or ev["type"],
                })
    return out


def queue_alerts(changes: dict[str, list[dict]]) -> int:
    """Queue each change for its opted-in watchers. Returns rows newly queued."""
    rows = []
    for sub in db.alert_subscribers_for(sorted(changes)):
        since = sub["since"].isoformat() if sub.get("since") else ""
        for ch in changes.get(sub["slug"], []):
            if ch["date"] >= since:  # never a change from before they watched/opted in
                rows.append({**ch, "user_id": sub["user_id"], "change_sig": change_sig(ch)})
    return db.add_alert_events(rows)


def is_due(digest: dict, now: datetime) -> bool:
    """Daily: at most one digest per ~day. Weekly: a week after the last one
    (or after opting in). The slack absorbs the 4-hourly render schedule."""
    last = digest.get("last_sent_at")
    if digest.get("cadence") == "weekly":
        last = last or digest.get("verified_at")
        return last is None or now - last >= timedelta(days=7, hours=-4)
    return last is None or now - last >= timedelta(hours=20)


def _link(slug: str, kind: str) -> str:
    # A delisted profile is gone (410); the account page still lists it.
    path = "/account/" if kind == "delisted" else f"/agents/{slug}/"
    return f"{BASE_URL}{path}?{UTM}"


def render_digest(events: list[dict], unsub_url: str) -> tuple[str, str, str]:
    """(subject, text, html) for one user's unsent changes, grouped by project."""
    by_slug: dict[str, list[dict]] = {}
    for ev in events:
        by_slug.setdefault(ev["slug"], []).append(ev)
    if len(by_slug) == 1:
        evs = next(iter(by_slug.values()))
        name = evs[0].get("name") or evs[0]["slug"]
        subject = f"{name}: {evs[0]['detail']}" if len(evs) == 1 else f"{name}: {len(evs)} changes"
    else:
        subject = f"{len(by_slug)} projects you track changed"
    subject = subject if len(subject) <= 120 else subject[:117] + "..."

    text = ["Changes on projects you track on HVTracker:", ""]
    html = ['<div style="font:14px/1.55 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f1b17;max-width:560px">',
            "<p>Changes on projects you track on HVTracker:</p>"]
    shown = 0
    for slug, evs in by_slug.items():
        if shown >= DIGEST_MAX_LINES:
            break
        name = evs[0].get("name") or slug
        url = _link(slug, evs[0]["kind"])
        text.append(name)
        html.append(f'<p style="margin:16px 0 4px"><a href="{escape(url)}" style="color:#26405e;font-weight:600">{escape(name)}</a></p><ul style="margin:0;padding-left:18px">')
        for ev in evs:
            if shown >= DIGEST_MAX_LINES:
                break
            text.append(f"  {ev['date']}  {ev['detail']}")
            html.append(f'<li><span style="color:#6f665d">{escape(ev["date"])}</span> {escape(ev["detail"])}</li>')
            shown += 1
        text += [f"  {url}", ""]
        html.append("</ul>")
    if shown < len(events):
        more = f"{len(events) - shown} more change(s) are on your account page: {BASE_URL}/account/"
        text += [more, ""]
        html.append(f"<p>{escape(more)}</p>")
    account = f"{BASE_URL}/account/#alerts"
    text += ["You get this because you track these projects and turned on alert emails.",
             f"Change how often: {account}", f"Unsubscribe: {unsub_url}"]
    html.append('<p style="margin-top:24px;color:#6f665d;font-size:12px">You get this because you track these '
                f'projects and turned on alert emails. <a href="{escape(account)}" style="color:#6f665d">Change how often</a> '
                f'&middot; <a href="{escape(unsub_url)}" style="color:#6f665d">Unsubscribe</a></p></div>')
    return subject, "\n".join(text) + "\n", "".join(html)


def send_pending(now: datetime | None = None) -> int:
    """Send every due digest; mark its rows only once the provider accepted it."""
    now = now or datetime.now(timezone.utc)
    sent = 0
    for digest in db.pending_alert_digests():
        if not is_due(digest, now):
            continue
        uid, events = digest["user_id"], digest["events"]
        unsub = f"{BASE_URL}/unsub/{make_token(uid, 'unsub')}"
        subject, text, html = render_digest(events, unsub)
        key = f"hvt-digest-{uid}-{max(e['id'] for e in events)}"
        if mailer.send(digest["email"], subject, text, html, unsub_url=unsub, idempotency_key=key):
            db.mark_alerts_emailed(uid, [e["id"] for e in events])
            sent += 1
    return sent


def send_verification(user_id: int, email: str) -> bool:
    url = f"{BASE_URL}/verify-email/{make_token(user_id, 'verify', email)}"
    text = (f"Confirm that HVTracker should email {email} when a project you track changes:\n\n"
            f"{url}\n\nThe link works for 48 hours. If you didn't ask for this, ignore this "
            "email and nothing more will be sent.\n")
    html = ('<div style="font:14px/1.55 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f1b17;max-width:560px">'
            f"<p>Confirm that HVTracker should email {escape(email)} when a project you track changes.</p>"
            f'<p><a href="{escape(url)}" style="color:#26405e;font-weight:600">Confirm alert emails</a></p>'
            '<p style="color:#6f665d;font-size:12px">The link works for 48 hours. If you didn\'t ask for this, '
            "ignore this email and nothing more will be sent.</p></div>")
    return mailer.send(email, "Confirm your HVTracker alert emails", text, html)


def run(events_by_repo: dict[str, list[dict]], rows: list[dict], today: str) -> dict | None:
    """The render hook: queue new changes, then send due digests. Never raises."""
    if not enabled():
        return None
    try:
        changes = finalized_changes(events_by_repo, rows, today)
        queued = queue_alerts(changes) if changes else 0
        sent = send_pending()
    except Exception as e:  # alerts must never fail a render
        print(f"[alerts] failed: {type(e).__name__}: {e}", flush=True)
        return None
    n = sum(len(v) for v in changes.values())
    print(f"[alerts] {n} change(s) on {len(changes)} project(s); {queued} queued; "
          f"{sent} digest(s) sent", flush=True)
    return {"changes": n, "projects": len(changes), "queued": queued, "sent": sent}
