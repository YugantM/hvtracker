"""Fetch Google Analytics 4 data for hvtracker.net via OAuth2."""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")
CLIENT_SECRET_PATH = os.environ.get(
    "GA4_CLIENT_SECRET",
    "client_secret_329878639361-bp4vju04vc9ug5bor9puhjav6ta945j7.apps.googleusercontent.com.json",
)
TOKEN_PATH = "ga_token.json"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def get_client():
    creds = None
    if Path(TOKEN_PATH).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return BetaAnalyticsDataClient(credentials=creds, transport="rest")


def run_report(client, dimensions, metrics, date_range="30daysAgo", limit=20, retries=3):
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=date_range, end_date="today")],
        limit=limit,
    )
    for attempt in range(retries):
        try:
            return client.run_report(request, timeout=120)
        except Exception as e:
            if attempt < retries - 1 and ("502" in str(e) or "503" in str(e) or "DEADLINE" in str(e)):
                wait = 10 * (attempt + 1)
                print(f"  Retrying in {wait}s ({e.__class__.__name__})...")
                time.sleep(wait)
            else:
                raise


def overview(client):
    resp = run_report(
        client,
        dimensions=["date"],
        metrics=["activeUsers", "sessions", "screenPageViews", "averageSessionDuration"],
    )
    rows = []
    for row in resp.rows:
        rows.append({
            "date": row.dimension_values[0].value,
            "users": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
            "pageviews": int(row.metric_values[2].value),
            "avg_session_sec": round(float(row.metric_values[3].value), 1),
        })
    rows.sort(key=lambda r: r["date"])
    return rows


def top_pages(client, limit=25):
    resp = run_report(
        client,
        dimensions=["pagePath"],
        metrics=["screenPageViews", "activeUsers"],
        limit=limit,
    )
    return [
        {
            "page": row.dimension_values[0].value,
            "pageviews": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        }
        for row in resp.rows
    ]


def traffic_sources(client, limit=15):
    resp = run_report(
        client,
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "activeUsers"],
        limit=limit,
    )
    return [
        {
            "source": row.dimension_values[0].value,
            "medium": row.dimension_values[1].value,
            "sessions": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        }
        for row in resp.rows
    ]


def top_landing_pages(client, limit=15):
    resp = run_report(
        client,
        dimensions=["landingPage"],
        metrics=["sessions", "activeUsers"],
        limit=limit,
    )
    return [
        {
            "landing_page": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "users": int(row.metric_values[1].value),
        }
        for row in resp.rows
    ]


def countries(client, limit=15):
    resp = run_report(
        client,
        dimensions=["country"],
        metrics=["activeUsers", "sessions"],
        limit=limit,
    )
    return [
        {
            "country": row.dimension_values[0].value,
            "users": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
        }
        for row in resp.rows
    ]


def devices(client):
    resp = run_report(
        client,
        dimensions=["deviceCategory"],
        metrics=["activeUsers", "sessions"],
    )
    return [
        {
            "device": row.dimension_values[0].value,
            "users": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
        }
        for row in resp.rows
    ]


def fetch_all():
    client = get_client()
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "overview": overview(client),
        "top_pages": top_pages(client),
        "traffic_sources": traffic_sources(client),
        "top_landing_pages": top_landing_pages(client),
        "countries": countries(client),
        "devices": devices(client),
    }


if __name__ == "__main__":
    if not PROPERTY_ID:
        print("Set GA4_PROPERTY_ID in .env")
        sys.exit(1)
    data = fetch_all()
    out_path = "ga_data.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out_path}")
    print(f"  {len(data['overview'])} days of overview data")
    print(f"  {len(data['top_pages'])} top pages")
    print(f"  {len(data['traffic_sources'])} traffic sources")
