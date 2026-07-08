"""Related-agents strip (master plan 2.1 internal mesh)."""
import fetch_and_build as fab


def _cat(n=6, category="Coding Agents"):
    rows = [{"slug": f"a{i}", "name": f"A{i}", "category": category,
             "category_rank": i + 1, "trust_score": 90 - i,
             "evidence_grade": "A"} for i in range(n)]
    return {category: rows}, rows


def test_middle_agent_gets_two_neighbours_each_side():
    cat_sorted, rows = _cat()
    related = fab.related_agents(rows[2], cat_sorted)  # rank 3
    assert [r["slug"] for r in related] == ["a0", "a1", "a3", "a4"]
    assert [r["category_rank"] for r in related] == [1, 2, 4, 5]


def test_top_agent_pads_from_below():
    cat_sorted, rows = _cat()
    related = fab.related_agents(rows[0], cat_sorted)
    assert [r["slug"] for r in related] == ["a1", "a2", "a3", "a4"]


def test_bottom_agent_pads_from_above():
    cat_sorted, rows = _cat()
    related = fab.related_agents(rows[-1], cat_sorted)
    assert [r["slug"] for r in related] == ["a1", "a2", "a3", "a4"]


def test_small_category_returns_what_exists():
    cat_sorted, rows = _cat(n=2)
    assert [r["slug"] for r in fab.related_agents(rows[0], cat_sorted)] == ["a1"]


def test_unknown_category_or_slug_is_empty():
    cat_sorted, _ = _cat()
    assert fab.related_agents({"slug": "ghost", "category": "Coding Agents"}, cat_sorted) == []
    assert fab.related_agents({"slug": "a0", "category": "Nope"}, cat_sorted) == []
