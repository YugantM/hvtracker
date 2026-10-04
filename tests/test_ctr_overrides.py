"""Phase 10 (A2): logged title/description tests for profile and category pages.

With no entry a page must render exactly as before (a title change outside a
logged batch, or a sitewide byte change, is what #114 and #322 taught us to
avoid); with an entry, the override is filled with live values. Every entry
must be logged in docs/ctr-tests.md."""
import os
import re

from jinja2 import Environment, FileSystemLoader

import fetch_and_build as fab
from tests.test_category_page import _row as cat_row
from tests.test_custody_chain import _render as render_profile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _title(html):
    return re.search(r"<title>(.*?)</title>", html).group(1)


def _description(html):
    return re.search(r'<meta name="description" content="(.*?)">', html).group(1)


def test_override_is_filled_with_live_values():
    tests = {"blender-mcp": {"title": "{name} MCP: is it safe? {score}/100 | HVTracker",
                             "description": "{name} is Grade {grade}, #{rank} of {total} in {category}."}}
    got = fab.ctr_test_page_override(tests, "blender-mcp", name="Blender MCP", score=71.2, grade="B",
                                     rank=140, total=1347, category="MCP Servers")
    assert got == {"title": "Blender MCP MCP: is it safe? 71.2/100 | HVTracker",
                   "description": "Blender MCP is Grade B, #140 of 1347 in MCP Servers."}
    assert fab.ctr_test_page_override(tests, "other") is None


def test_profile_keeps_its_title_without_an_entry_and_takes_one_with_it():
    default = render_profile()
    assert re.fullmatch(r"Is .+ Safe\? Trust Score &amp; Safety Signals \| HVTracker", _title(default))
    html = render_profile(seo_override={"title": "Custom title", "description": "Custom description"})
    assert _title(html) == "Custom title" and _description(html) == "Custom description"


def _render_category(**extra):
    env = Environment(loader=FileSystemLoader([os.path.join(ROOT, "templates"), ROOT]), autoescape=True)
    return env.get_template("category.html.j2").render(**{
        "category": "Coding Agents", "slug": "coding-agents", "agents": [cat_row(1)], "item_noun": "agent",
        "item_plural": "agents", "all_categories": [], "updated": "", "avg_trust": 70, "total_stars": "1k",
        "grade_a_count": 0, "warning_count": 0, "top3_names": "Agent 1", "comparisons": [], **extra})


def test_category_keeps_its_title_without_an_entry_and_takes_one_with_it():
    assert _title(_render_category()) == "Best AI Coding Agents — Ranked by Trust Score | HVTracker"
    html = _render_category(seo_override={"title": "T", "description": "D"})
    assert _title(html) == "T" and _description(html) == "D"


def test_every_override_is_logged():
    with open(os.path.join(ROOT, "docs", "ctr-tests.md"), encoding="utf-8") as f:
        log = f.read()
    for key in list(fab.CTR_TEST_AGENT) + list(fab.CTR_TEST_CATEGORY):
        assert key in log, f"{key} has a CTR override but no entry in docs/ctr-tests.md"
