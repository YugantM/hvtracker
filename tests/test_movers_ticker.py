"""Regression tests for the homepage daily-movers ticker (compute_movers limit).

The homepage ticker widened from 3 to 12 movers per direction; lock that the
`limit` param caps each side and preserves the "biggest first" ordering.
"""
import fetch_and_build as fb

# repo -> (baseline_rank, latest_rank); positive delta = moved up (rank shrank).
_MOVES = {
    "o/up1": (10, 5),   # +5
    "o/up2": (8, 6),    # +2
    "o/up3": (20, 19),  # +1
    "o/dn1": (5, 12),   # -7
    "o/dn2": (3, 4),    # -1
    "o/dn3": (30, 33),  # -3
}


def _history():
    baseline = {"_date": "2020-01-01", "agents": [
        {"repo": r, "name": r, "rank": b, "score": 1} for r, (b, _) in _MOVES.items()]}
    latest = {"_date": "2020-01-02", "agents": [
        {"repo": r, "name": r, "rank": c, "score": 1} for r, (_, c) in _MOVES.items()]}
    return [baseline, latest]


def _rows():
    return [{"repo": r, "slug": r.split("/")[1], "rank": c,
             "category": "", "evidence_grade": "A", "language": "Python"}
            for r, (_, c) in _MOVES.items()]


def _movers(limit=None):
    rows = _rows()
    slug_map = {r["repo"].lower(): r["slug"] for r in rows}
    kwargs = {"rows": rows}
    if limit is not None:
        kwargs["limit"] = limit
    return fb.compute_movers(_history(), slug_map, **kwargs)


def test_limit_caps_each_side():
    m = _movers(limit=2)
    assert len(m["up"]) == 2
    assert len(m["down"]) == 2
    # Biggest gain first; biggest drop (most negative) first.
    assert m["up"][0]["delta"] >= m["up"][1]["delta"] > 0
    assert m["down"][0]["delta"] <= m["down"][1]["delta"] < 0


def test_limit_above_available_returns_all_movers():
    m = _movers(limit=50)
    assert len(m["up"]) == 3
    assert len(m["down"]) == 3


def test_default_limit_is_three():
    m = _movers()
    assert len(m["up"]) == 3
    assert len(m["down"]) == 3
