"""Account page watchlist rendering.

These cover the pure render helpers rather than the route, because the route
needs a signed-in session and DATABASE_URL; the helpers hold all the logic that
can actually be wrong (trend direction, averaging, delisted/pending states).
"""
import auth


def _index():
    return {
        "haystack": {
            "slug": "haystack", "name": "Haystack", "category": "Agent Frameworks",
            "trust_score": 90.8, "evidence_grade": "A", "coverage_grade": "B",
            "rank": 2, "rank_delta": 0, "days_ago": 59,
        },
        "climber": {
            "slug": "climber", "name": "Climber", "category": "Coding Agents",
            "trust_score": 70.5, "evidence_grade": "B", "coverage_grade": "A",
            "rank": 54, "rank_delta": 7, "days_ago": 3,
        },
        "faller": {
            "slug": "faller", "name": "Faller", "category": "Coding Agents",
            "trust_score": 40.0, "evidence_grade": "D", "coverage_grade": "D",
            "rank": 300, "rank_delta": -13, "days_ago": 200, "has_warning": True,
        },
        "fresh": {
            "slug": "fresh", "name": "Fresh", "category": "Coding Agents",
            "trust_score": 0.0, "evidence_grade": "D", "rank": 438,
            "rank_delta": -13, "days_ago": 999, "pending_signals": True,
        },
    }


def test_trend_direction_follows_rank_delta():
    """rank_delta is previous_rank - rank, so positive must render as UP."""
    html = auth.watchlist_html(["climber", "faller"], _index())
    climber = html.split('data-watch-slug="climber"')[1].split("</li>")[0]
    faller = html.split('data-watch-slug="faller"')[1].split("</li>")[0]
    assert "wl-up" in climber and "&#9650;7" in climber
    assert "wl-down" in faller and "&#9660;13" in faller


def test_rows_sort_by_rank_and_flag_review():
    html = auth.watchlist_html(["faller", "haystack", "climber"], _index())
    order = [s.split('"')[0] for s in html.split('data-watch-slug="')[1:]]
    assert order == ["haystack", "climber", "faller"]
    assert "needs review" in html          # only faller has has_warning


def test_pending_row_hides_placeholder_score():
    """A row awaiting its first scan must not read as a dead 0.0 project."""
    html = auth.watchlist_html(["fresh"], _index())
    assert "is-pending" in html
    assert "Awaiting first signal scan" in html
    assert "999" not in html and "0.0" not in html


def test_delisted_slug_survives_with_a_marker():
    html = auth.watchlist_html(["haystack", "ghost"], _index())
    assert "is-gone" in html
    assert "No longer listed" in html
    assert 'data-remove-slug="ghost"' in html   # still removable


def test_summary_excludes_pending_from_average():
    """Pending rows carry 0.0 until scanned; averaging them understates it."""
    summary = auth.watchlist_summary_html(["haystack", "climber", "fresh"], _index())
    assert "80.7" in summary                    # (90.8 + 70.5) / 2, not /3
    assert ">3<" in summary                     # but all three are "tracked"


def test_summary_counts_movement_both_ways():
    summary = auth.watchlist_summary_html(["climber", "faller", "haystack"], _index())
    assert "&#9650;1" in summary and "&#9660;1" in summary


def test_empty_watchlist_explains_how_to_start():
    assert auth.watchlist_summary_html([], _index()) == ""
    empty = auth.watchlist_html([], _index())
    assert "Track" in empty and "<ul" not in empty
