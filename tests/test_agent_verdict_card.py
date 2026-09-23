"""Agent page verdict card (plan 2.2) and its provisional state (plan 2.3).

A provisional row (pending_signals) has not had its first full signal fetch,
so its score is partial: the page must say so and must not publish a grade,
a rank-based verdict or a review rating for it."""
import json
import os
import re

from jinja2 import Environment, FileSystemLoader

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _render(**overrides):
    env = Environment(
        loader=FileSystemLoader([os.path.join(ROOT, "templates"), ROOT]),
        autoescape=True,
    )
    with open(os.path.join(ROOT, "data", "render_state.json"), encoding="utf-8") as f:
        row = json.load(f)["rows"][0]
    row.update(overrides)
    row["category_slug"] = fab.slugify(row.get("category", "")) if row.get("category") else ""
    row["org_slug_or_none"] = None
    row["review_insights"] = fab.agent_review_insights(row)
    row["remediation_steps"] = fab.agent_remediation_steps(row)
    row["safety_qa"] = fab.agent_safety_qa(row)
    row["correction_url"] = fab.agent_correction_url(row)
    row["sparkline_svg"] = ""
    row["rank_history"] = []
    row["event_chart_svg"] = ""
    return env.get_template("agent.html.j2").render(
        row=row, total=1, updated="", events=[], drift_events=[],
        methodology_version="v4.3", comparisons=[], provider_slugs={}, related=[],
    )


def _json_ld(html):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    return [json.loads(b) for b in blocks]


def _seal(html):
    return html[html.index('<aside class="vseal"'):html.index("</aside>")]


def test_scored_agent_shows_grade_seal_and_rating():
    html = _render(pending_signals=False, evidence_grade="B", trust_score=74.6)
    assert "Grade B" in _seal(html)
    assert 'id="is-it-safe"' in html
    app = _json_ld(html)[0]
    assert app["review"]["reviewRating"]["ratingValue"] == 74.6


def test_provisional_agent_withholds_grade_and_rating():
    html = _render(
        pending_signals=True, evidence_grade="D", trust_score=14.4,
        description="Pending first signal refresh", last_push="pending",
        days_ago=999, scorecard_score=3.4, weekly_downloads=None,
        signed_commits_pct=None, has_provenance=False,
    )
    seal = _seal(html)
    assert "Grade pending" in seal and "provisional" in seal
    assert "Grade D" not in seal
    assert "Evidence is still being collected." in html
    assert "1 of the 5 signals" in html
    # No grade/rank paragraph, no placeholder description, no rating markup.
    assert 'id="is-it-safe"' not in html
    assert "Pending first signal refresh" not in html
    app, faq = _json_ld(html)[:2]
    assert "review" not in app and "description" not in app
    assert "provisional" in faq["mainEntity"][0]["acceptedAnswer"]["text"]
