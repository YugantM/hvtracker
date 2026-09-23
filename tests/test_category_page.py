"""Category pages (plan 2.6): podium, grade mix, and the first 50 rows open.

Every row must stay in the HTML (search engines and no-JS readers see the
full list); only rows past 50 are collapsed, and provisional rows are shown
as pending rather than graded."""
import os
import re

from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _row(i, grade="B", pending=False):
    return {"name": f"Agent {i}", "slug": f"agent-{i}", "repo": f"o/agent-{i}",
            "category_rank": i, "trust_score": 90 - i * 0.1, "evidence_grade": grade,
            "stars": 1000 - i, "stars_fmt": "1k", "days_ago": i, "has_provenance": i % 2 == 0,
            "pending_signals": pending, "description": "", "display_listing_status": "listed",
            "display_status_label": "Listed"}


def _render(agents):
    env = Environment(loader=FileSystemLoader([os.path.join(ROOT, "templates"), ROOT]),
                      autoescape=True)
    return env.get_template("category.html.j2").render(
        category="MCP Servers", slug="mcp-servers", agents=agents, item_noun="agent",
        item_plural="agents", all_categories=[], updated="2026-09-23", avg_trust=70,
        total_stars="1k", grade_a_count=0, warning_count=0, top3_names="", comparisons=[])


def test_all_rows_stay_in_html_and_only_the_first_50_are_expanded():
    agents = [_row(i) for i in range(1, 121)]
    html = _render(agents)
    rows = re.findall(r"<tr[^>]*data-g=", html)
    assert len(rows) == 120
    assert html.count('class="is-more"') == 70
    assert "Show the next 50 of 120" in html
    assert "<noscript>" in html  # no-JS readers get every row


def test_provisional_rows_are_pending_not_graded_and_kept_off_the_podium():
    agents = [_row(1, pending=True, grade="D")] + [_row(i, "A") for i in range(2, 6)]
    html = _render(agents)
    podium = html[html.index('<div class="podium">'):html.index('<div class="gmix">')]
    assert "Agent 1<" not in podium and "Agent 2<" in podium
    assert "1 provisional, awaiting a first full check" in html
    assert re.search(r'data-g="P"[^>]*>.*?grade-pending"[^>]*>pending<', html, re.S)
