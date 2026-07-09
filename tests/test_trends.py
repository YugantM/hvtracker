"""Ecosystem trends + quarterly State of Agent Trust reports (plan 3.2).

Locks the era rule (score-derived series never drawn across a methodology
change), the deterministic quarterly-report contract (completed quarters
only, minimum snapshot coverage, every figure traceable to the snapshots),
and the chart renderer's gap/era behaviour.
"""
from datetime import date, timedelta

import fetch_and_build as fab


def _agent(repo="org/a", grade="B", days_ago=3, mcp="none", prov=False,
           providers=None):
    return {
        "repo": repo, "rank": 1, "score": 80.0, "trust_score": 75.0,
        "evidence_grade": grade, "days_ago": days_ago,
        "mcp_server_support": {"status": mcp},
        "has_provenance": prov,
        "external_service_dependencies": {"providers": providers or []},
    }


def _snap(d, agents, version="v4.2", graph_providers=None):
    s = {"_date": d, "methodology_version": version, "agents": agents}
    if graph_providers is not None:
        s["graph_summary"] = {"providers": graph_providers}
    return s


def test_compute_ecosystem_trends_series_and_eras():
    history = [
        _snap("2026-07-01", [_agent(grade="A", mcp="implemented", days_ago=100),
                             _agent(repo="org/b", grade="D")],
              version="v4.1", graph_providers={"openai": 2}),
        _snap("2026-07-02", [_agent(grade="B"), _agent(repo="org/b", grade="D")],
              version="v4.2"),
        _snap("2026-07-03", [_agent(grade="B"), _agent(repo="org/b", grade="C")],
              version="v4.2", graph_providers={"openai": 1, "anthropic": 1}),
    ]
    t = fab.compute_ecosystem_trends(history)
    assert [d["date"] for d in t["days"]] == ["2026-07-01", "2026-07-02", "2026-07-03"]
    d0 = t["days"][0]
    assert d0["grades"] == {"A": 1, "B": 0, "C": 0, "D": 1}
    assert d0["mcp_implemented"] == 1
    assert d0["stale_90d"] == 1
    assert d0["providers"] == {"openai": 2}
    assert t["days"][1]["providers"] is None  # no graph_summary that day
    assert t["eras"] == [{"date": "2026-07-02", "version": "v4.2"}]


def test_chart_breaks_series_at_era_when_flagged():
    days = [
        {"date": "2026-07-01", "methodology_version": "v4.1"},
        {"date": "2026-07-02", "methodology_version": "v4.1"},
        {"date": "2026-07-03", "methodology_version": "v4.2"},
        {"date": "2026-07-04", "methodology_version": "v4.2"},
    ]
    series = [{"label": "x", "color": "#000", "values": [1, 2, 3, 4]}]
    broken = fab.render_trend_chart_svg(days, series, break_at_eras=True)
    joined = fab.render_trend_chart_svg(days, series, break_at_eras=False)
    assert broken.count("<polyline") == 2   # line restarts at the cutover
    assert joined.count("<polyline") == 1
    # the era marker (dashed line) is drawn either way
    assert 'stroke-dasharray="4,3"' in broken and 'stroke-dasharray="4,3"' in joined


def test_chart_handles_none_gaps_and_degenerate_input():
    days = [{"date": f"2026-07-0{i}", "methodology_version": "v4.2"} for i in range(1, 6)]
    series = [{"label": "x", "color": "#000", "values": [1, 2, None, 4, 5]}]
    svg = fab.render_trend_chart_svg(days, series)
    assert svg.count("<polyline") == 2  # gap splits the line
    assert fab.render_trend_chart_svg(days[:1], series) == ""  # <2 days
    assert fab.render_trend_chart_svg(
        days, [{"label": "x", "color": "#000", "values": [None] * 5}]) == ""


def _quarter_history(year=2026, month=1, n_days=25):
    start = date(year, month, 1)
    history = []
    for i in range(n_days):
        d = (start + timedelta(days=i)).isoformat()
        agents = [
            _agent(repo="org/a", grade="A", mcp="implemented", prov=True,
                   providers=["OpenAI"]),
            _agent(repo="org/b", grade="D", days_ago=120,
                   providers=["OpenAI", "Anthropic"]),
        ]
        if i >= 10:  # org/c joins mid-quarter with an MCP server
            agents.append(_agent(repo="org/c", grade="B", mcp="implemented",
                                 providers=["Anthropic"]))
        history.append(_snap(d, agents))
    return history


def test_quarterly_report_stats_trace_to_snapshots():
    posts = fab.compute_quarterly_reports(_quarter_history())
    assert len(posts) == 1
    p = posts[0]
    assert p["slug"] == "state-of-agent-trust-2026-q1"
    s = p["stats"]
    assert (s["agents_start"], s["agents_end"]) == (2, 3)
    assert s["newly_listed"] == 1 and s["delisted"] == 0
    assert (s["mcp_start"], s["mcp_end"]) == (1, 2)
    assert (s["provenance_start"], s["provenance_end"]) == (1, 1)
    assert (s["stale_start"], s["stale_end"]) == (1, 1)
    assert s["grades_end"] == {"A": 1, "B": 1, "C": 0, "D": 1}
    assert s["top_providers"][0] == {"name": "OpenAI", "count": 2}
    assert {"name": "Anthropic", "delta": 1} in s["provider_gainers"]
    # fact-check contract (T2.3 pattern): every excerpt figure is a stat
    for figure in (s["agents_end"], s["newly_listed"], s["mcp_start"],
                   s["mcp_end"], s["provenance_start"], s["provenance_end"],
                   s["snapshot_days"]):
        assert str(figure) in p["excerpt"]


def test_quarterly_report_needs_minimum_coverage():
    assert fab.compute_quarterly_reports(_quarter_history(n_days=20)) == []


def test_metric_baselines_skip_days_before_field_capture():
    """Early snapshots lack some fields entirely; reading absence as zero
    would publish tracking artifacts as ecosystem change ("MCP 0 → 102")."""
    history = _quarter_history()
    # first 5 days predate MCP-field capture
    for snap in history[:5]:
        for a in snap["agents"]:
            a.pop("mcp_server_support", None)
    posts = fab.compute_quarterly_reports(history)
    s = posts[0]["stats"]
    assert s["mcp_start"] == 1  # baselined at day 6, not 0 at day 1
    assert s["field_baselines"] == {"MCP": "2026-01-06"}
    assert s["tracking_began"] == "2026-01-01"  # quarter holds the first-ever snapshot


def test_tracking_began_flag_absent_for_later_quarters():
    q1 = _quarter_history(year=2026, month=1)
    q2_snap = _snap("2025-12-01", [_agent()])  # older history exists
    posts = fab.compute_quarterly_reports([q2_snap] + q1)
    assert posts[-1]["stats"]["tracking_began"] is None


def test_current_quarter_is_never_reported():
    today = date.today()
    history = _quarter_history(year=today.year, month=(today.month - 1) // 3 * 3 + 1)
    assert fab.compute_quarterly_reports(history) == []
