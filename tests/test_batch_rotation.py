"""The 2h batch must actually rotate through the whole board.

Regression for the freeze found via issue #212: `select_stale_batch` ranks
agents by a `full_fetched_at` stamp read out of data.json, but the stamp was
never published in data.json's field whitelist. Every agent therefore tied on
"" and the stable secondary sort handed the *same alphabetically-first sixth*
to every batch, forever — 83% of the board (1,372 of 1,647 rows) went weeks
with no download, provenance, or runtime-trust refresh while the site kept
serving their frozen values.

Two properties are locked here: consecutive cycles must not select the same
agents (rotation), and the stamp must survive a data.json round-trip (the
whitelist, which is what actually broke).
"""
import json

import fetch_and_build as fab


def _agents(n):
    return [{"repo": f"org/agent{i:03d}", "name": f"Agent {i}"} for i in range(n)]


def _write_data(path, agents, stamps):
    """Write a data.json holding only what the whitelist publishes."""
    path.write_text(
        json.dumps(
            {
                "agents": [
                    {"repo": a["repo"], "full_fetched_at": stamps.get(a["repo"], None)}
                    for a in agents
                ]
            }
        ),
        encoding="utf-8",
    )


def test_batches_rotate_across_cycles(tmp_path):
    """Six cycles must cover the whole board, never repeating an agent."""
    agents = _agents(60)
    data_path = tmp_path / "data.json"
    stamps = {}
    _write_data(data_path, agents, stamps)

    seen = []
    for cycle in range(6):
        batch = fab.select_stale_batch(agents, str(data_path), 6)
        assert batch, "batch selection returned nothing"
        seen.append({a["repo"] for a in batch})
        # Simulate the run stamping the agents it fetched, then republishing
        # data.json exactly the way main() does.
        for a in batch:
            stamps[a["repo"]] = f"2026-08-31T{cycle:02d}:00:00Z"
        _write_data(data_path, agents, stamps)

    for i in range(1, 6):
        assert not seen[i] & seen[i - 1], (
            f"cycle {i} re-selected agents from cycle {i - 1} — rotation is stuck"
        )
    covered = set().union(*seen)
    assert covered == {a["repo"] for a in agents}, (
        f"six cycles covered {len(covered)}/{len(agents)} agents"
    )


def test_unstamped_agents_sort_ahead_of_stamped_ones(tmp_path):
    """A never-fetched agent outranks every stamped one, whatever its name."""
    agents = _agents(12)
    data_path = tmp_path / "data.json"
    # Everything fetched recently except the alphabetically LAST agent, which
    # the old (name-ordered) behaviour would never have reached.
    stamps = {a["repo"]: "2026-08-31T00:00:00Z" for a in agents[:-1]}
    _write_data(data_path, agents, stamps)

    batch = fab.select_stale_batch(agents, str(data_path), 6)
    assert agents[-1]["repo"] in {a["repo"] for a in batch}


def test_full_fetched_at_survives_the_data_json_whitelist():
    """The stamp is only useful if data.json publishes it.

    Batch mode carries non-batch rows forward from data.json (not from
    render_state), so a stamp the whitelist drops is gone by the next cycle —
    which is precisely how the rotation froze.
    """
    source = open(fab.__file__, encoding="utf-8").read()
    _, _, after_writer = source.partition('# Write data.json (machine-readable leaderboard)')
    whitelist, _, _ = after_writer.partition("Wrote data.json")
    assert '"full_fetched_at": r.get("full_fetched_at")' in whitelist, (
        "full_fetched_at must be published in the data.json agent whitelist"
    )


def test_light_signals_refresh_does_not_restamp_the_rotation():
    """`refresh_github_signals` runs every 30 min over the WHOLE board.

    If it wrote `full_fetched_at`, every row would look freshly fetched and the
    ordering would flatten back to a permanent tie.
    """
    source = open(fab.__file__, encoding="utf-8").read()
    _, _, body = source.partition("def refresh_github_signals(")
    body, _, _ = body.partition("\ndef ")
    assert 'row["signals_fetched_at"]' in body, "expected the light refresh to keep its own stamp"
    assert "full_fetched_at" not in body, (
        "the 30-min signals refresh must not write full_fetched_at — "
        "it would flatten the batch rotation"
    )


def test_rotation_summary_counts_never_fetched_and_stalest():
    rows = [
        {"repo": "org/a", "full_fetched_at": "2026-08-31T00:00:00Z"},
        {"repo": "org/b", "full_fetched_at": None},
        {"repo": "org/c"},
        {"repo": "org/d", "full_fetched_at": "not-a-date"},
    ]
    summary = fab.summarize_fetch_rotation(rows)
    assert summary["total_rows"] == 4
    assert summary["never_fetched"] == 3
    assert summary["stalest_age_hours"] is not None


def test_rotation_summary_handles_a_board_with_no_stamps():
    summary = fab.summarize_fetch_rotation([{"repo": "org/a"}])
    assert summary["never_fetched"] == 1
    assert summary["stalest_age_hours"] is None
    assert summary["fetched_last_24h"] == 0
