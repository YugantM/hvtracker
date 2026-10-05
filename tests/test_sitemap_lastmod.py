"""Sitemap <lastmod> fingerprint (GSC URL Inspection sweep 2026-10-01).

The live sitemap stamped 2,093 of 2,140 URLs "today" on every refresh because
each data refresh moves the numbers on every data-driven page. These lock the
normalization: a refresh that only moves numbers or reorders rank-driven lists
must not change the fingerprint; a real content change must.
"""
import os
import re

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = "2026-10-01 12:00 UTC"

PAGE = """<html><head><title>Aider: HVTrust {score}/100</title>{robots}</head><body>
<p>Updated {now}</p>
<div class="stat-value">{stars}</div>
<span class="meta">Repo last pushed {days} days ago</span>
<span class="badge grade-{grade}">{grade}</span>
<!--lastmod:skip--><section class="neighbours"><ol>{neighbours}</ol></section><!--/lastmod:skip-->
<p>{text}</p>
</body></html>"""


def _fp(now=NOW, **kw):
    fields = dict(score="75.8", robots="", stars="12.3k", days="3", grade="B",
                  neighbours="<li>Cline</li><li>Codex</li>", text="AI pair programming.",
                  now=now)
    fields.update(kw)
    return fab.lastmod_fingerprint(PAGE.format(**fields).encode("utf-8"), now)


def test_daily_refresh_noise_keeps_fingerprint():
    base = _fp()
    assert _fp(score="76.1", stars="12.4k", days="4") == base
    assert _fp(neighbours="<li>Codex</li><li>Cline</li>") == base
    assert _fp(now="2026-10-02 08:00 UTC") == base


def test_real_content_changes_move_fingerprint():
    base = _fp()
    assert _fp(grade="A") != base
    assert _fp(robots='<meta name="robots" content="noindex">') != base
    assert _fp(text="AI pair programming in your terminal.") != base


def _profile_fp(*, rank_delta, targets, checks, events, days_ago=6, projected="C", grade="B", history_days=5):
    """Fingerprint of a real rendered profile, varying only what a refresh moves."""
    import json
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader([os.path.join(ROOT, "templates"), ROOT]), autoescape=True)
    with open(os.path.join(ROOT, "data", "render_state.json"), encoding="utf-8") as f:
        row = json.load(f)["rows"][0]
    row.update(
        evidence_grade=grade, scorecard_checks=checks, recent_events=events,
        rank_delta=rank_delta, rank_delta_class="delta-up" if rank_delta > 0 else "delta-down",
        rank_delta_display=("▲" if rank_delta > 0 else "▼") + str(abs(rank_delta)),
        category_slug=fab.slugify(row.get("category", "")), org_slug_or_none=None,
        event_chart_svg="",
        days_ago=days_ago, freshness_class="fresh" if days_ago <= 1 else "recent",
        improvements=[{"link": "/methodology/", "action": "Publish provenance", "detail": "",
                       "gain": 4.2, "score": 70.1, "grade": projected}],
    )
    row["review_insights"] = fab.agent_review_insights(row)
    row["remediation_steps"] = fab.agent_remediation_steps(row)
    row["safety_qa"] = fab.agent_safety_qa(row)
    row["correction_url"] = fab.agent_correction_url(row)
    row["rank_history"] = [{"date": f"2026-09-{29 + d:02d}" if d < 2 else f"2026-10-{d - 1:02d}",
                            "rank": 60 + (d * 7) % 11, "score": 70.0} for d in range(history_days)]
    row["sparkline_svg"] = fab.render_sparkline_svg(row["rank_history"])
    html = env.get_template("agent.html.j2").render(
        row=row, total=1705, updated=NOW, events=events, drift_events=[],
        methodology_version="v4.3", comparisons=[], provider_slugs={}, related=[],
        compare_targets=targets,
    )
    return fab.lastmod_fingerprint(html.encode("utf-8"), NOW)


def _target(name, delta):
    return {"name": name, "delta": delta, "url": f"/compare/x-vs-{name.lower()}/", "published": False}


def test_profile_refresh_noise_keeps_fingerprint():
    """The 4 Oct prod check: between two 4-hourly refreshes 23 of 60 profiles
    re-hashed on the compare tray, the rank arrow, Scorecard check order, new
    "Rank Moved" events, push recency wording and the projected grade; and at
    each day boundary every rank sparkline gains a point (5 Oct: all 1,445
    profiles re-dated). None of those may move lastmod."""
    score_event = fab.make_agent_event("2026-09-20", "trust_score_changed", "HVTrust rose 4 points")
    rank_a = fab.make_agent_event("2026-10-03", "rank_changed", "Rank rose 12 spots (#80 → #68)")
    rank_b = fab.make_agent_event("2026-10-04", "rank_changed", "Rank dropped 11 spots (#68 → #79)")
    base = _profile_fp(
        rank_delta=3, targets=[_target("Cline", 2.1), _target("Codex", 0)],
        checks={"Code-Review": 8, "CI-Tests": 10}, events=[score_event, rank_a])
    assert _profile_fp(
        rank_delta=-2, targets=[_target("Codex", 1.4), _target("Aider", -3)],
        checks={"CI-Tests": 10, "Code-Review": 7}, events=[score_event, rank_a, rank_b],
        days_ago=0, projected="B", history_days=6) == base
    # A real change still moves it.
    assert _profile_fp(
        rank_delta=3, targets=[_target("Cline", 2.1), _target("Codex", 0)],
        checks={"Code-Review": 8, "CI-Tests": 10}, events=[score_event, rank_a], grade="A") != base


def test_lastmod_entry_dates():
    v, old = fab.LASTMOD_FP_VERSION, fab.LASTMOD_FP_VERSION - 1
    today, then = "2026-10-05", "2026-09-28"
    # New page, unchanged page, changed page.
    assert fab.lastmod_entry(None, "h1", today)["date"] == today
    assert fab.lastmod_entry({"hash": "h1", "date": then, "fp": v}, "h1", today)["date"] == then
    assert fab.lastmod_entry({"hash": "h1", "date": then, "fp": v}, "h2", today)["date"] == today
    # A version bump re-keys without re-dating...
    migrated = fab.lastmod_entry({"hash": "h1", "date": then, "fp": old}, "h2", today)
    assert migrated == {"hash": "h2", "date": then, "fp": v}
    # ...for one render only: a page unchanged at the bump takes the current
    # version, so its next real change re-dates it instead of passing as a
    # migration.
    unchanged = fab.lastmod_entry({"hash": "h1", "date": then, "fp": old}, "h1", today)
    assert unchanged["fp"] == v
    assert fab.lastmod_entry(unchanged, "h3", today)["date"] == today


def test_template_skip_markers_are_balanced():
    for name in ("agent.html.j2", "compare_pair.html.j2"):
        with open(os.path.join(ROOT, "templates", name), encoding="utf-8") as f:
            src = f.read()
        opens = [m.start() for m in re.finditer(r"<!--lastmod:skip-->", src)]
        closes = [m.start() for m in re.finditer(r"<!--/lastmod:skip-->", src)]
        assert opens, f"{name}: rank-driven regions lost their lastmod:skip markers"
        assert len(opens) == len(closes), f"{name}: unbalanced lastmod:skip markers"
        assert all(o < c for o, c in zip(opens, closes)), f"{name}: marker out of order"
