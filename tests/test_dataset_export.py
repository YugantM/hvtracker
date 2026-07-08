"""Quarterly dataset export (master plan 1.6).

write_dataset_export() must produce a citable, CC BY 4.0 snapshot of the
public fields at a stable per-quarter path — refreshed within the quarter,
frozen when renders roll to the next quarter's filename.
"""
import csv
import gzip
import json
import os
from datetime import datetime, timezone

import fetch_and_build as fab


def _row(slug="a", rank=1):
    return {
        "slug": slug, "name": slug.title(), "repo": f"org/{slug}",
        "rank": rank, "display_rank": rank, "category": "Agent Frameworks",
        "trust_score": 80.0, "evidence_grade": "A", "coverage_grade": "B",
        "trust_confidence": 1.0, "stars": 100, "weekly_downloads": 50,
        "license_spdx": "MIT", "has_provenance": True, "scorecard_score": 7.5,
        "signed_commits_ratio": 0.4, "listing_status": "listed",
        "mcp_server_support": {"status": "implemented"},
        "external_service_dependencies": {"providers": ["OpenAI"], "requires_api_keys": True},
        "tool_plugin_surface": {"plugin_system": "declared", "tool_tags": ["code"]},
        "package_provenance_drift": {"status": "match"},
    }


def test_quarter_label():
    assert fab.quarter_label(datetime(2026, 7, 7, tzinfo=timezone.utc)) == "2026-Q3"
    assert fab.quarter_label(datetime(2026, 1, 1, tzinfo=timezone.utc)) == "2026-Q1"
    assert fab.quarter_label(datetime(2026, 12, 31, tzinfo=timezone.utc)) == "2026-Q4"


def test_export_writes_json_and_csv(tmp_path):
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)
    label = fab.write_dataset_export(str(tmp_path), [_row("b", 2), _row("a", 1)], now=now)
    assert label == "2026-Q3"

    json_path = tmp_path / "data" / "exports" / "hvtrust-2026-Q3.json.gz"
    with gzip.open(json_path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    assert "CC BY 4.0" in doc["license"]
    assert doc["methodology_version"] == fab.METHODOLOGY_VERSION
    assert "hvtrust-2026-Q3.json.gz" in doc["citation"]
    assert doc["count"] == 2
    # rank-ordered, reshaped runtime fields flattened
    assert [a["slug"] for a in doc["agents"]] == ["a", "b"]
    assert doc["agents"][0]["mcp_status"] == "implemented"
    assert doc["agents"][0]["provider_count"] == 1
    assert doc["agents"][0]["requires_api_keys"] is True

    csv_path = tmp_path / "data" / "exports" / "hvtrust-2026-Q3.csv"
    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["slug"] == "a"
    assert set(fab.EXPORT_CSV_FIELDS) == set(rows[0].keys())


def test_export_is_none_safe(tmp_path):
    bare = {"slug": "bare", "name": "Bare", "repo": "org/bare", "rank": None}
    fab.write_dataset_export(str(tmp_path), [bare],
                             now=datetime(2026, 7, 7, tzinfo=timezone.utc))
    json_path = tmp_path / "data" / "exports" / "hvtrust-2026-Q3.json.gz"
    with gzip.open(json_path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    agent = doc["agents"][0]
    assert agent["mcp_status"] == "none"
    assert agent["provider_count"] == 0
    assert agent["drift_status"] == "not_applicable"


def test_rerender_same_quarter_overwrites_not_duplicates(tmp_path):
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    fab.write_dataset_export(str(tmp_path), [_row()], now=now)
    fab.write_dataset_export(str(tmp_path), [_row(), _row("b", 2)], now=now)
    export_dir = tmp_path / "data" / "exports"
    files = sorted(os.listdir(export_dir))
    assert files == ["hvtrust-2026-Q3.csv", "hvtrust-2026-Q3.json.gz"]
    with gzip.open(export_dir / "hvtrust-2026-Q3.json.gz", "rt", encoding="utf-8") as f:
        assert json.load(f)["count"] == 2
