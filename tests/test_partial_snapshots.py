"""Snapshots and rows with no comparable rank must not produce rank movement.

The 2026-09-21 snapshot holds 441 rows (production briefly ran main's stale
roster), and the next render re-added 1,241 rows provisionally. Deltas against
either put "▲887" on the homepage movers strip and tripped the board-churn
invariant with a mean |Δrank| of 54.6.
"""
import json
import os

import fetch_and_build as fb


def _write(dirpath, date, agents):
    with open(os.path.join(dirpath, f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump({"agents": agents, "methodology_version": fb.METHODOLOGY_VERSION}, f)


def test_partial_snapshot_date_is_never_read_back(tmp_path):
    assert "2026-09-21" in fb.PARTIAL_SNAPSHOT_DATES
    _write(tmp_path, "2026-09-20", [{"repo": "o/a", "rank": 5}])
    _write(tmp_path, "2026-09-21", [{"repo": "o/a", "rank": 1}])
    assert [s["_date"] for s in fb.load_history(str(tmp_path))] == ["2026-09-20"]
    assert fb._load_prior_snapshot(str(tmp_path))["agents"][0]["rank"] == 5
    assert fb.load_previous_ranks(str(tmp_path)) == {"o/a": 5}
    # The file itself stays on disk: history is never deleted.
    assert os.path.isfile(os.path.join(tmp_path, "2026-09-21.json"))


def test_provisional_prior_rows_have_no_previous_rank(tmp_path):
    _write(tmp_path, "2026-09-20", [
        {"repo": "o/real", "rank": 3},
        {"repo": "O/Prov", "rank": 900, "pending_signals": True},
    ])
    assert fb.load_previous_ranks(str(tmp_path)) == {"o/real": 3}
    assert fb.load_previous_pending(str(tmp_path)) == {"o/prov"}


def test_movers_skip_provisional_rows_on_either_day():
    baseline = {"_date": "2020-01-01", "agents": [
        {"repo": "o/real", "name": "real", "rank": 10, "score": 1},
        {"repo": "o/was-prov", "name": "was-prov", "rank": 900, "score": 1,
         "pending_signals": True},
        {"repo": "o/now-prov", "name": "now-prov", "rank": 20, "score": 1},
    ]}
    latest = {"_date": "2020-01-02", "agents": [
        {"repo": "o/real", "name": "real", "rank": 8, "score": 1},
        {"repo": "o/was-prov", "name": "was-prov", "rank": 30, "score": 1},
        {"repo": "o/now-prov", "name": "now-prov", "rank": 950, "score": 1,
         "pending_signals": True},
    ]}
    rows = [{"repo": r, "slug": r.split("/")[1], "rank": 1, "category": "",
             "evidence_grade": "A", "language": ""}
            for r in ("o/real", "o/was-prov", "o/now-prov")]
    slug_map = {r["repo"]: r["slug"] for r in rows}
    movers = fb.compute_movers([baseline, latest], slug_map, rows=rows)
    assert [m["slug"] for m in movers["up"]] == ["real"]
    assert movers["down"] == []


def test_board_churn_ignores_rows_provisional_in_prior_snapshot():
    prior = {"methodology_version": fb.METHODOLOGY_VERSION, "agents": (
        [{"repo": f"o/r{i}", "rank": i} for i in range(1, 41)]
        + [{"repo": f"o/p{i}", "rank": 100 + i, "pending_signals": True} for i in range(40)]
    )}
    # Real rows hold their ranks; the provisional ones move wildly once their
    # full signal set arrives — a completeness event, not mass churn.
    rows = ([{"repo": f"o/r{i}", "rank": i, "trust_score": 50.0} for i in range(1, 41)]
            + [{"repo": f"o/p{i}", "rank": 900 + i, "trust_score": 10.0} for i in range(40)])
    violations = fb.check_board_invariants(rows, prior)
    assert not any("mass churn" in v for v in violations)


def test_board_churn_still_fires_for_real_rows():
    prior = {"methodology_version": fb.METHODOLOGY_VERSION,
             "agents": [{"repo": f"o/r{i}", "rank": i} for i in range(1, 41)]}
    rows = [{"repo": f"o/r{i}", "rank": 41 - i, "trust_score": 50.0} for i in range(1, 41)]
    assert any("mass churn" in v for v in fb.check_board_invariants(rows, prior))


def test_web_process_copy_of_partial_dates_matches_the_generator():
    # app.py inlines the list to keep fetch_and_build out of the web process;
    # the public history API must skip exactly the days the site skips.
    import app
    assert app._PARTIAL_SNAPSHOT_DATES == fb.PARTIAL_SNAPSHOT_DATES
