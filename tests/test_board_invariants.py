"""Board-integrity invariants (master plan task 0.3).

check_board_invariants() must trip on each defect class the v4.0–v4.2 era
produced (score pinning/inflation, out-of-range values, silent mass churn,
mass delisting) and stay quiet on a healthy board, a declared methodology
change, and normal roster growth.
"""
import fetch_and_build as fab


def _rows(n=100, score_fn=lambda i: 90.0 - i * 0.5):
    return [
        {"repo": f"org/agent{i}", "rank": i + 1, "trust_score": score_fn(i)}
        for i in range(n)
    ]


def _snapshot(rows, methodology=fab.METHODOLOGY_VERSION):
    return {
        "methodology_version": methodology,
        "agents": [
            {"repo": r["repo"], "rank": r["rank"], "trust_score": r["trust_score"]}
            for r in rows
        ],
    }


def test_healthy_board_no_violations():
    rows = _rows()
    assert fab.check_board_invariants(rows, _snapshot(rows)) == []


def test_healthy_board_without_prior_snapshot():
    assert fab.check_board_invariants(_rows(), None) == []


def test_score_pinned_near_100_trips():
    rows = _rows(score_fn=lambda i: 99.6 - i * 0.1)
    violations = fab.check_board_invariants(rows, None)
    assert any(">= 99.5" in v for v in violations)


def test_score_out_of_range_trips():
    rows = _rows()
    rows[0]["trust_score"] = 104.2
    rows[1]["trust_score"] = -3.0
    violations = fab.check_board_invariants(rows, None)
    assert any("outside [0,100]" in v for v in violations)


def test_mass_rank_churn_same_methodology_trips():
    rows = _rows()
    prior = _snapshot(rows)
    # Reverse the board: mean |Δrank| for 100 agents is 50 (> 15).
    for i, r in enumerate(rows):
        r["rank"] = len(rows) - i
    violations = fab.check_board_invariants(rows, prior)
    assert any("mass churn" in v for v in violations)


def test_mass_rank_churn_with_methodology_change_is_allowed():
    rows = _rows()
    prior = _snapshot(rows, methodology="v0.0-test-prior")
    for i, r in enumerate(rows):
        r["rank"] = len(rows) - i
    assert fab.check_board_invariants(rows, prior) == []


def test_listed_count_drop_over_5_percent_trips():
    rows = _rows(n=100)
    prior = _snapshot(rows)
    survivors = rows[:94]  # 6% drop
    violations = fab.check_board_invariants(survivors, prior)
    assert any("count dropped" in v for v in violations)


def test_roster_growth_is_allowed():
    prior = _snapshot(_rows(n=90))
    rows = _rows(n=100)
    assert fab.check_board_invariants(rows, prior) == []
