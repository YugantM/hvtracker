"""Transactional email for watchlist alerts, over Resend's HTTPS API.

Named mailer.py, not email.py: a top-level email.py would shadow the stdlib
`email` package that requests and http.client import.

Without RESEND_API_KEY nothing is sent and send() returns False, so callers
leave their rows unsent. For a local click-through (HVT_DEV_AUTH=1, never in
production) the message is printed instead and counts as sent.
"""
from __future__ import annotations

import os

import requests

RESEND_URL = "https://api.resend.com/emails"
API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM = os.environ.get("ALERTS_FROM", "HVTracker alerts <alerts@hvtracker.net>")

# Same double gate as auth.DEV_AUTH: explicit opt-in, and never production.
_IS_PROD = (os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production"
            or os.environ.get("HVT_ENV", "").lower() == "production")
DEV_OUTBOX = os.environ.get("HVT_DEV_AUTH") == "1" and not _IS_PROD


def configured() -> bool:
    return bool(API_KEY) or DEV_OUTBOX


def send(to: str, subject: str, text: str, html: str, *,
         unsub_url: str | None = None, idempotency_key: str | None = None) -> bool:
    """Send one message. True only when the provider accepted it. Never raises.

    `unsub_url` adds List-Unsubscribe plus the RFC 8058 one-click header
    (a POST to that URL unsubscribes). `idempotency_key` makes Resend drop a
    repeat of the same send within 24 h, e.g. after a crash between sending
    and marking the rows sent.
    """
    headers = {}
    if unsub_url:
        headers["List-Unsubscribe"] = f"<{unsub_url}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if not API_KEY:
        if DEV_OUTBOX:
            print(f"[mailer] dev outbox (not sent) to={to} subject={subject!r}\n{text}", flush=True)
            return True
        print("[mailer] RESEND_API_KEY not set; nothing sent", flush=True)
        return False
    req_headers = {"Authorization": f"Bearer {API_KEY}"}
    if idempotency_key:
        req_headers["Idempotency-Key"] = idempotency_key[:256]
    try:
        r = requests.post(RESEND_URL, headers=req_headers, timeout=15, json={
            "from": FROM, "to": [to], "subject": subject, "text": text, "html": html,
            "headers": headers,
        })
    except requests.RequestException as e:
        print(f"[mailer] send failed: {type(e).__name__}", flush=True)
        return False
    if r.status_code >= 300:
        # The body names the problem (unverified domain, bad key).
        print(f"[mailer] send rejected: HTTP {r.status_code} {r.text[:200]}", flush=True)
        return False
    return True
