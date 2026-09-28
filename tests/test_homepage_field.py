"""Roster `homepage` (a maintainer's official site, #216) and the
corrections monitor that would have surfaced #216 after five days."""
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from check_corrections import overdue  # noqa: E402


def _render(**row):
    from test_agent_verdict_card import _render as render
    return render(pending_signals=False, **row)


def test_roster_homepages_are_plain_https_urls():
    """Rendered into href attributes, so nothing but https:// may get in."""
    with open(os.path.join(ROOT, "agents.json"), encoding="utf-8") as f:
        roster = json.load(f)
    homepages = {a["repo"]: a["homepage"] for a in roster if "homepage" in a}
    assert homepages, "expected at least HOL Guard to carry a homepage"
    for repo, url in homepages.items():
        assert re.fullmatch(r"https://[A-Za-z0-9.-]+(/[^\s\"'<>]*)?", url), (repo, url)


def test_page_links_the_homepage_and_names_it_in_json_ld():
    html = _render(homepage="https://hol.org/guard")
    assert '<a href="https://hol.org/guard" target="_blank" rel="noopener noreferrer">hol.org/guard</a>' in html
    assert ">Website →</a>" in html
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["sameAs"] == ["https://hol.org/guard"]


def test_page_without_a_homepage_is_unchanged():
    html = _render(homepage="")
    assert "Website →" not in html and '"sameAs"' not in html


NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def _issue(n, title, created, comments=()):
    return {"number": n, "title": title, "createdAt": created, "url": f"u/{n}",
            "comments": [{"authorAssociation": a} for a in comments]}


def test_overdue_flags_only_old_unanswered_correction_requests():
    issues = [
        _issue(216, "[Correction] HOL Guard official website", "2026-09-04T10:00:00Z"),
        _issue(300, "[Correction] answered", "2026-09-01T10:00:00Z", comments=["NONE", "OWNER"]),
        _issue(301, "[Correction] only the requester replied", "2026-09-01T10:00:00Z", comments=["NONE"]),
        _issue(302, "[Correction] too new", "2026-09-26T10:00:00Z"),
        _issue(303, "Some other issue", "2026-08-01T10:00:00Z"),
    ]
    assert [i["number"] for i in overdue(issues, now=NOW)] == [216, 301]
