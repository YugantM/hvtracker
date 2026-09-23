#!/usr/bin/env python3
"""Write compare_sitemap_allow.txt — the compare pairs that have earned at least
one Search Console impression, normalised to canonical alphabetical a-vs-b order.

fetch_and_build.py reads this file to decide which /compare/<a>-vs-<b>/ pages go
in the sitemap (§ crawl-budget: advertise proven pairs, hold the untested tail in
waves). Regenerate periodically as more pairs earn impressions:

    uv run --with google-analytics-data --with google-api-python-client \
           --with google-auth ~/hvtracker/build_compare_allowlist.py

Needs the GA4/GSC service-account key (same one app uses for analytics):
GOOGLE_APPLICATION_CREDENTIALS or ~/.config/hvtracker/google-sa.json.
"""
import os
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SITE = "https://hvtracker.net/"
KEY = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS",
                     str(Path.home() / ".config/hvtracker/google-sa.json"))
OUT = Path(__file__).with_name("compare_sitemap_allow.txt")
START, END = "2026-05-14", None  # full history → 3 days ago


def norm(pair: str) -> str:
    a, _, b = pair.partition("-vs-")
    return f"{a}-vs-{b}" if not b else "-vs-".join(sorted((a, b)))


def main() -> int:
    import datetime as dt
    end = END or str(dt.date.today() - dt.timedelta(days=3))
    creds = service_account.Credentials.from_service_account_file(
        KEY, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    sc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    rows, start_row = [], 0
    while True:
        resp = sc.searchanalytics().query(siteUrl=SITE, body={
            "startDate": START, "endDate": end, "dimensions": ["page"],
            "dimensionFilterGroups": [{"filters": [{
                "dimension": "page", "operator": "includingRegex",
                "expression": r"/compare/.+-vs-.+"}]}],
            "rowLimit": 25000, "startRow": start_row}).execute()
        got = resp.get("rows", [])
        rows += got
        if len(got) < 25000:
            break
        start_row += 25000

    pairs = set()
    for r in rows:
        page = r["keys"][0]
        seg = page.rstrip("/").rsplit("/compare/", 1)[-1]
        if "-vs-" in seg:
            pairs.add(norm(seg))
    OUT.write_text("\n".join(sorted(pairs)) + "\n")
    print(f"{len(pairs)} proven compare pairs -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
