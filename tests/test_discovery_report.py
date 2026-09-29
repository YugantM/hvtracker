"""scripts/discovery_report.py: the weekly shortlist of new listing candidates."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import discovery_report as dr  # noqa: E402

TODAY = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _c(repo, stars, created, desc="An AI agent", name=None):
    return {"repo": repo, "name": name or repo.split("/")[1], "stars": stars, "created": created,
            "license": "MIT", "description": desc, "url": f"https://github.com/{repo}"}


def test_shortlist_keeps_recent_agents_ranked_by_stars():
    rows = dr.shortlist([
        _c("a/old", 90000, "2024-01-01"),                      # had its chance already
        _c("b/new", 5000, "2026-08-01"),
        _c("c/newer", 9000, "2026-09-10"),
        _c("d/awesome-agents", 20000, "2026-08-01"),           # an index
        _c("e/guide", 8000, "2026-08-01", desc="A curated list of agent tools"),
        _c("f/course", 7000, "2026-08-01", desc="Agent engineering course and tutorial"),
    ], days=120, top=50, today=TODAY)
    assert [r["repo"] for r in rows] == ["c/newer", "b/new"]


def test_shortlist_respects_top():
    rows = dr.shortlist([_c(f"o/r{i}", i, "2026-09-01") for i in range(10)], top=3, today=TODAY)
    assert [r["stars"] for r in rows] == [9, 8, 7]


def test_render_escapes_table_breaking_text():
    md = dr.render([_c("x/y", 1234, "2026-09-01", desc="pipes | in | text\nand a newline")], total=5, days=120)
    assert "| 1 | [x/y](https://github.com/x/y) | 1,234 | 2026-09-01 | MIT | pipes \\| in \\| text and a newline |" in md
    assert "Discovery proposes; the owner decides" in md
