"""Incident watch opens one issue per new critical/high advisory and never
repeats one an existing issue already names."""
import importlib.util
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "check_incidents", os.path.join(ROOT, "scripts", "check_incidents.py"))
ci = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ci)


def _row(*found):
    return {"name": "Chroma", "slug": "chroma", "rank": 60, "trust_score": 64.9,
            "advisories": {"found": list(found)}}


def _adv(id_, sev, aliases=()):
    return {"id": id_, "severity": sev, "aliases": list(aliases), "summary": "RCE via x",
            "published": "2026-09-29", "package": "chromadb", "version": "1.5.9"}


def test_critical_and_high_open_issues_moderate_does_not():
    rows = [_row(_adv("GHSA-aaaa", "CRITICAL", ["CVE-2026-1"]), _adv("GHSA-bbbb", "HIGH"),
                 _adv("GHSA-cccc", "MODERATE"))]
    out = ci.new_incidents(rows, "", today=date(2026, 10, 1))
    assert [o["title"] for o in out] == ["Incident watch: Chroma — GHSA-aaaa (CRITICAL)",
                                         "Incident watch: Chroma — GHSA-bbbb (HIGH)"]
    body = out[0]["body"]
    assert "https://hvtracker.net/agents/chroma/#advisories" in body
    assert "64.9 (Grade C)" in body and "CVE-2026-1" in body
    assert "79.9 (Grade B)" in out[1]["body"]


def test_advisory_named_by_an_existing_issue_is_skipped():
    rows = [_row(_adv("GHSA-aaaa", "CRITICAL"), _adv("GHSA-bbbb", "HIGH"))]
    seen = "Incident watch: Chroma — GHSA-aaaa (CRITICAL)\n"
    assert [o["title"] for o in ci.new_incidents(rows, seen, today=date(2026, 10, 1))] == ["Incident watch: Chroma — GHSA-bbbb (HIGH)"]


def test_old_advisories_are_not_news():
    rows = [_row(_adv("GHSA-aaaa", "CRITICAL"))]
    assert ci.new_incidents(rows, "", today=date(2026, 10, 14)) == []


def test_rows_without_advisories_are_quiet():
    assert ci.new_incidents([{"name": "x", "slug": "x", "advisories": None}], "") == []
