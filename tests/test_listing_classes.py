"""Per-class rank spaces.

The registry lists more than one kind of artifact. Agents are the original
board; skills are scored on the same evidence but ranked among themselves. The
property that makes this safe — and the reason the class exists at all — is
that adding or growing one class must move ZERO ranks in another. A shared rank
space would have churned 27.5 mean |Δrank| across 1,283 live agents when the
first 148 skills landed, tripping check_board_invariants' mass-churn guard.
"""
import fetch_and_build as fab


def _agents(n=50):
    return [
        {"repo": f"org/agent{i}", "slug": f"agent{i}", "trust_score": 90.0 - i * 0.7}
        for i in range(n)
    ]


def _skills(n=20):
    # Skills legitimately score low pre-scan (13-24 band), so they interleave
    # through the agent board's crowded tail rather than sitting below it.
    return [
        {"repo": f"org/skill{i}", "slug": f"skill{i}", "class": "skill",
         "trust_score": 24.0 - i * 0.5}
        for i in range(n)
    ]


def test_rows_without_class_default_to_agent():
    assert fab.listing_class({"repo": "org/x"}) == "agent"
    assert fab.listing_class({"repo": "org/x", "class": None}) == "agent"


def test_unknown_class_falls_back_to_agent():
    """A typo in the roster must not silently create a private rank space."""
    assert fab.listing_class({"repo": "org/x", "class": "sklil"}) == "agent"


def test_each_class_ranks_from_one():
    rows = fab.assign_ranks(_agents() + _skills())
    by_class = fab.group_by_class(rows)
    assert sorted(by_class) == ["agent", "skill"]
    for class_rows in by_class.values():
        ranks = sorted(r["rank"] for r in class_rows)
        assert ranks == list(range(1, len(class_rows) + 1))


def test_adding_a_class_moves_no_rank_in_another():
    """The core guarantee. Without it this whole class is a rank-churn event."""
    before = {r["repo"]: r["rank"] for r in fab.assign_ranks(_agents())}
    after = {
        r["repo"]: r["rank"]
        for r in fab.assign_ranks(_agents() + _skills())
        if r["listing_class"] == "agent"
    }
    assert before == after


def test_growing_a_class_moves_no_rank_in_another():
    """Not just introducing the class — every later roster batch too."""
    before = {
        r["repo"]: r["rank"]
        for r in fab.assign_ranks(_agents() + _skills(5))
        if r["listing_class"] == "agent"
    }
    after = {
        r["repo"]: r["rank"]
        for r in fab.assign_ranks(_agents() + _skills(60))
        if r["listing_class"] == "agent"
    }
    assert before == after


def test_ties_are_scoped_to_the_class():
    """A skill tying an agent's score must not mark that agent as tied."""
    agent = {"repo": "org/a", "slug": "a", "trust_score": 20.0}
    skill = {"repo": "org/s", "slug": "s", "class": "skill", "trust_score": 20.0}
    rows = fab.assign_ranks([agent, skill])
    assert not any(r["is_tied"] for r in rows)
    assert {r["display_rank"] for r in rows} == {1}


def test_class_is_reapplied_over_a_cached_row():
    """Regression: skills silently rejoined the agent board.

    Rows are constructed field-by-field, so a row loaded from the render_state
    cache carries no `class` key. The first render after the skill class landed
    put all 148 on the agent board ("Built index.html with 1431 agents" instead
    of 1283) because the class was never re-applied from the roster.
    """
    cached = [{"repo": "org/skill-a", "slug": "skill-a"},   # cache drops `class`
              {"repo": "org/agent-a", "slug": "agent-a"}]
    roster = [{"repo": "org/skill-a", "class": "skill"},
              {"repo": "org/agent-a"}]
    fab.apply_listing_classes(cached, roster)
    assert [fab.listing_class(r) for r in cached] == ["skill", "agent"]


def test_class_is_cleared_when_the_roster_drops_it():
    """Reclassifying in agents.json must win over whatever the cache holds."""
    cached = [{"repo": "org/x", "class": "skill"}]
    fab.apply_listing_classes(cached, [{"repo": "org/x"}])
    assert fab.listing_class(cached[0]) == "agent"


def test_published_payload_carries_listing_class():
    """Regression: /api/v1/agents served all 148 skills in production.

    data_output["agents"] is a field whitelist built as an explicit dict per
    row. `listing_class` was set on the internal row but not named in that
    whitelist, so it was dropped on the way out; the API filter treats a
    missing class as "agent" (deliberately, so pre-existing renders keep
    working) and therefore passed every skill through.
    """
    import inspect
    src = inspect.getsource(fab.main)
    start = src.index("data_output = {")
    payload = src[start:start + 3000]
    assert '"listing_class"' in payload, (
        "listing_class missing from the published agents payload — "
        "consumers cannot distinguish classes and /api/v1/agents leaks skills"
    )


def test_roster_class_values_are_all_known():
    """A typo in agents.json would silently demote a row to the agent board."""
    import json
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "agents.json"), encoding="utf-8") as f:
        agents = json.load(f)
    bad = [a["repo"] for a in agents
           if a.get("class") and a["class"] not in fab.LISTING_CLASSES]
    assert bad == [], f"unknown listing class: {bad}"


def test_listing_class_is_published_on_every_row():
    """Downstream consumers (templates, API, sitemap) filter on this field."""
    rows = fab.assign_ranks(_agents(3) + _skills(3))
    assert all("listing_class" in r for r in rows)
    assert sum(1 for r in rows if r["listing_class"] == "skill") == 3
