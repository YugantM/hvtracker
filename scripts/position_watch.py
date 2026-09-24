"""Weekly Search Console position watch (plan 3.4).

Average position is the leading indicator: the 1 Sep 2026 re-rating moved the
site from ~15-16 to ~8-9, and clicks follow position. This compares the last
7 days of Search Console data with the 7 before and exits 2 when the latest
week's average position is worse (higher) than THRESHOLD, which would mean
the September gain is reverting.

Auth: a Google service account with read access to the Search Console
property, its JSON key in GSC_SERVICE_ACCOUNT_JSON. Without it the script
reports "not configured" and exits 0, so the workflow stays green until the
owner adds the secret.

Exit codes: 0 = fine (or not configured), 2 = past threshold, 1 = error.
"""
import json
import os
import sys
import urllib.parse
from datetime import date, timedelta

SITE = "https://hvtracker.net/"
THRESHOLD = 12.0
LAG_DAYS = 3  # Search Console data is final ~2-3 days late
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def windows(today: date):
    """(start, end) of the latest complete week and the week before it."""
    end = today - timedelta(days=LAG_DAYS)
    this = (end - timedelta(days=6), end)
    prev = (this[0] - timedelta(days=7), this[0] - timedelta(days=1))
    return this, prev


def summarize(query, window):
    """Aggregate (no dimensions) = the property's own impression-weighted
    average position for the window."""
    rows = query(window[0].isoformat(), window[1].isoformat()).get("rows") or []
    if not rows:
        return None
    r = rows[0]
    return {"clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
            "position": round(r.get("position", 0.0), 1)}


def evaluate(this, prev, threshold=THRESHOLD):
    if this is None:
        return 1, "No Search Console rows for the latest week."
    delta = None if prev is None else round(this["position"] - prev["position"], 1)
    trend = "" if delta is None else f" ({'+' if delta > 0 else ''}{delta} vs the week before)"
    line = (f"Average position {this['position']}{trend}; {this['clicks']} clicks, "
            f"{this['impressions']} impressions.")
    if this["position"] > threshold:
        return 2, f"{line} Worse than {threshold}: the September ranking gain may be reverting."
    return 0, line


def gsc_query_fn(key_json):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_info(json.loads(key_json), scopes=[SCOPE])
    session = AuthorizedSession(creds)
    url = ("https://www.googleapis.com/webmasters/v3/sites/"
           f"{urllib.parse.quote(SITE, safe='')}/searchAnalytics/query")

    def query(start, end):
        r = session.post(url, json={"startDate": start, "endDate": end, "type": "web"}, timeout=60)
        r.raise_for_status()
        return r.json()
    return query


def main():
    key = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "").strip()
    if not key:
        print("Position watch not configured: add the GSC_SERVICE_ACCOUNT_JSON repo secret.")
        return 0
    this_w, prev_w = windows(date.today())
    query = gsc_query_fn(key)
    this, prev = summarize(query, this_w), summarize(query, prev_w)
    code, msg = evaluate(this, prev)
    print(f"{this_w[0]} -> {this_w[1]}: {msg}")
    return code


if __name__ == "__main__":
    sys.exit(main())
