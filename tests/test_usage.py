"""Machine-channel usage counters behind /live/ (usage.py)."""
import usage


def _reset(tmp):
    usage._pending.clear()
    usage._recent_calls.clear()
    usage._fallback = None
    usage._snapshot_cache = None
    usage.init(str(tmp))


def _fresh_snapshot(hours=24):
    usage._snapshot_cache = None  # snapshot() caches for a few seconds
    return usage.snapshot(hours)


def test_requests_and_tool_calls_are_counted_separately(tmp_path):
    _reset(tmp_path)
    usage.bump("mcp", 9)
    usage.bump("api_v1")
    usage.record_tool_call("check_agent_trust")
    usage.record_tool_call("check_agent_trust")
    usage.record_tool_call("search_agents")

    s = _fresh_snapshot()
    assert s["totals"]["requests"] == 10
    assert s["totals"]["by_channel"]["mcp"] == 9
    assert s["totals"]["tool_calls"] == 3
    assert s["totals"]["by_tool"] == {"check_agent_trust": 2, "search_agents": 1}


def test_recent_calls_are_newest_first_and_carry_no_arguments(tmp_path):
    _reset(tmp_path)
    usage.record_tool_call("search_agents")
    usage.record_tool_call("get_leaderboard")

    calls = _fresh_snapshot()["recent_calls"]
    assert [c["tool"] for c in calls] == ["get_leaderboard", "search_agents"]
    # Only the tool name and a timestamp are ever retained.
    assert set(calls[0]) == {"tool", "at"}


def test_recent_calls_are_bounded(tmp_path):
    _reset(tmp_path)
    for _ in range(usage.RECENT_CALLS + 25):
        usage.record_tool_call("search_agents")
    assert len(_fresh_snapshot()["recent_calls"]) == usage.RECENT_CALLS


def test_flush_persists_without_double_counting(tmp_path):
    _reset(tmp_path)
    usage.bump("mcp", 4)
    usage.record_tool_call("scan_stack")
    before = _fresh_snapshot()["totals"]

    assert usage.flush() > 0
    after = _fresh_snapshot()["totals"]
    assert after["requests"] == before["requests"] == 4
    assert after["tool_calls"] == before["tool_calls"] == 1

    # A second flush has nothing pending and must not re-add anything.
    assert usage.flush() == 0
    assert _fresh_snapshot()["totals"]["requests"] == 4


def test_totals_survive_a_restart(tmp_path):
    _reset(tmp_path)
    usage.bump("mcp", 3)
    usage.record_tool_call("compare_agents")
    usage.flush()

    _reset(tmp_path)  # reload the rollup from the volume
    s = _fresh_snapshot()
    assert s["totals"]["requests"] == 3
    assert s["totals"]["by_tool"] == {"compare_agents": 1}


def test_failed_flush_keeps_counts_pending(tmp_path, monkeypatch):
    _reset(tmp_path)
    usage.bump("mcp", 5)

    def boom(_rows):
        raise RuntimeError("db down")

    monkeypatch.setattr(usage, "_flush_to_file", boom)
    assert usage.flush() == 0, "a failed flush must report zero rows written"
    monkeypatch.undo()

    # Nothing was lost: the counts are still pending and flush cleanly later.
    assert usage.flush() > 0
    assert _fresh_snapshot()["totals"]["requests"] == 5


def test_hourly_series_totals_match_the_window(tmp_path):
    _reset(tmp_path)
    usage.bump("mcp", 6)
    usage.record_tool_call("search_agents")
    usage.record_tool_call("list_categories")

    w = _fresh_snapshot()["window"]
    assert sum(h["tool_calls"] for h in w["hourly"]) == w["tool_calls"] == 2
    assert sum(h["requests"] for h in w["hourly"]) == w["requests"] == 6


def test_snapshot_includes_unflushed_counts(tmp_path):
    _reset(tmp_path)
    usage.record_tool_call("search_agents")
    # Never flushed — the live page must still see it.
    assert _fresh_snapshot()["totals"]["tool_calls"] == 1


def test_snapshot_cache_is_keyed_by_window(tmp_path):
    """A short-window request must not be served to a long-window caller."""
    _reset(tmp_path)
    usage.record_tool_call("search_agents")
    assert usage.snapshot(1)["window_hours"] == 1
    assert usage.snapshot(24)["window_hours"] == 24, "cache must key on hours, not just time"


def test_hourly_series_is_zero_filled_across_the_window(tmp_path):
    """One point per hour, quiet hours included, newest last.

    A sparse series made a single busy hour render as one full-width block.
    """
    _reset(tmp_path)
    usage.record_tool_call("search_agents")
    hourly = usage.snapshot(24)["window"]["hourly"]
    assert len(hourly) == 24
    assert [h["bucket"] for h in hourly] == sorted(h["bucket"] for h in hourly)
    assert hourly[-1]["tool_calls"] == 1, "current hour is last"
    assert all(h["tool_calls"] == 0 for h in hourly[:-1])


def test_counting_since_reports_oldest_bucket(tmp_path):
    """The page says when counting began, so totals aren't read as all history."""
    _reset(tmp_path)
    assert _fresh_snapshot()["counting_since"] is None  # nothing recorded yet
    usage.bump("mcp", 2)
    usage.flush()
    since = _fresh_snapshot()["counting_since"]
    assert since is not None and len(since) == 10 and since.count("-") == 2


def test_hourly_series_carries_both_series(tmp_path):
    """The chart plots requests and tool calls, so both must be per-hour."""
    _reset(tmp_path)
    usage.bump("mcp", 5)
    usage.record_tool_call("search_agents")
    last = _fresh_snapshot()["window"]["hourly"][-1]
    assert last["requests"] == 5 and last["tool_calls"] == 1
