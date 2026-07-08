"""Trend badge (master plan 2.3): 30-day rank direction, era-aware.

The arrow reads the sparkline series that compute_sparklines() already
trims at the last METHODOLOGY_VERSION change, so a scoring cutover can
never render as a movement.
"""
from datetime import datetime, timedelta, timezone

import fetch_and_build as fab


def _pts(*ranks, days_apart=1):
    today = datetime.now(timezone.utc)
    n = len(ranks)
    return [
        {"date": (today - timedelta(days=(n - 1 - i) * days_apart)).strftime("%Y-%m-%d"),
         "rank": r, "score": 90.0}
        for i, r in enumerate(ranks)
    ]


def test_improving_rank_shows_up_arrow():
    assert fab.trend_arrow(_pts(20, 15, 10)) == "↗"


def test_declining_rank_shows_down_arrow():
    assert fab.trend_arrow(_pts(10, 15, 20)) == "↘"


def test_small_jitter_is_flat():
    # board is dense; +/-2 positions must not read as a trend
    assert fab.trend_arrow(_pts(10, 12, 9, 11)) == "→"


def test_short_or_missing_series_is_flat():
    assert fab.trend_arrow([]) == "→"
    assert fab.trend_arrow(_pts(10)) == "→"
    assert fab.trend_arrow([{"date": "2026-01-01", "rank": None},
                            {"date": "2026-01-02", "rank": 5}]) == "→"


def test_window_ignores_points_older_than_30_days():
    old = [{"date": "2020-01-01", "rank": 300, "score": 10.0}]
    recent = _pts(10, 11)  # flat within the window
    assert fab.trend_arrow(old + recent) == "→"


def test_generate_badges_writes_trend_svg(tmp_path):
    rows = [{"slug": "demo", "name": "Demo", "repo": "org/demo",
             "trust_score": 88.0, "evidence_grade": "A"}]
    spark = {"org/demo": _pts(20, 10)}
    fab.generate_badges(str(tmp_path), rows, spark)
    trend = (tmp_path / "badge" / "demo-trend.svg").read_text()
    assert "A ↗" in trend
    assert (tmp_path / "badge" / "demo.svg").exists()
    assert (tmp_path / "badge" / "demo-grade.svg").exists()
