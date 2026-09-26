"""The columnar history cache must be invisible to every history reader.

Renders used to json.load every daily snapshot in full (a 2.5 GB peak with
123 days). They now read a per-day column cache holding only
HISTORY_SERIES_FIELDS. These tests run each reader on the old full snapshots
and on the cache and require identical output, over synthetic days that hit
the edges the readers depend on: absent vs None keys, nested sub-keys, a
partial day, a degraded day, a methodology change and a repo rename.
"""
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone

import pytest

import fetch_and_build as fb

DAYS = 130
OLD_REPO, NEW_REPO = "old/renamed", "new/renamed"
NESTED_STATES = {
    "mcp_server_support": [{"status": "implemented"}, {"status": "declared"},
                           {"status": None}, {}, None, "ABSENT"],
    "external_service_dependencies": [{"providers": ["openai", "anthropic"]},
                                      {"providers": ["openai"]}, {"providers": []},
                                      {"other": 1}, "ABSENT"],
    "tool_plugin_surface": [{"plugin_system": "mcp"}, {"plugin_system": None},
                            {}, "ABSENT"],
    "package_provenance_drift": [{"status": "warning"}, {"status": "ok"},
                                 {"status": "not_applicable"}, "ABSENT"],
}


def _date(i: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=DAYS - 1 - i)).strftime("%Y-%m-%d")


def _row(rng: random.Random, i: int, day: int, n: int) -> dict:
    repo = f"o/a{i}"
    if i == 0:
        repo = OLD_REPO if day < DAYS // 2 else NEW_REPO
    row = {
        "repo": repo, "slug": repo.split("/")[1], "name": f"Agent {i}",
        "category": rng.choice(["Coding Agents", "MCP Servers"]),
        "rank": rng.randint(1, n), "score": round(rng.uniform(0, 100), 1),
        "trust_score": rng.choice([None, round(rng.uniform(20, 95), 1)]),
        "evidence_grade": rng.choice("ABCD"),
        "listing_status": rng.choice(["listed", "watch", "legacy"]),
        "scorecard_score": rng.choice([None, 0, 5.5, 7.8]),
        "stars": rng.randint(0, 50000), "license_spdx": rng.choice([None, "MIT", "Apache-2.0"]),
        "license_type": rng.choice([None, "permissive", "copyleft"]),
        "coverage_grade": rng.choice("ABCD"), "trust_confidence": rng.choice([0.67, 1.0]),
        "signed_commits_ratio": rng.choice([None, 0.0, 0.5, 1.0]),
        "weekly_downloads": rng.choice([None, 0, 1234]), "dl_source": rng.choice(["npm", "pypi", ""]),
        "weekly_commits": rng.choice([None, 0, 42]),
        "description": "not a history field", "trust_breakdown": {"safety": rng.choice([1.0, 12.5]), "identity": 10.8},
    }
    # Early days predate these signals entirely (absent, not None).
    if day > 20:
        row["has_provenance"] = rng.choice([True, False])
        row["days_ago"] = rng.choice([0, 3, 120, 400])
    if i == 5 and day % 2:  # one provisional row in 12+: a normal board
        row["pending_signals"] = True
    for field, states in NESTED_STATES.items():
        state = rng.choice(states)
        if state != "ABSENT":
            row[field] = state
    return row


@pytest.fixture
def history_dir(tmp_path, monkeypatch):
    rng = random.Random(7)
    hist = tmp_path / "history"
    hist.mkdir()
    partial, degraded = _date(DAYS - 30), _date(DAYS - 20)
    monkeypatch.setattr(fb, "PARTIAL_SNAPSHOT_DATES", frozenset({partial}))
    monkeypatch.setattr(fb, "REPO_RENAMES", {OLD_REPO: NEW_REPO})
    for day in range(DAYS):
        n = 12 + day // 20  # the roster grows over time
        agents = [_row(rng, i, day, n) for i in range(n)]
        if _date(day) == degraded:
            for a in agents:
                a["pending_signals"] = True
        snap = {"agents": agents, "methodology_version": "v4.2" if day < DAYS - 45 else "v4.3"}
        if day % 3 == 0:
            snap["graph_summary"] = {"providers": {"openai": day, "anthropic": 2}}
        (hist / f"{_date(day)}.json").write_text(json.dumps(snap))
    return hist


def _old_all(history_dir) -> list[dict]:
    """The pre-cache loaders: full snapshots, renames applied."""
    out = []
    for f in sorted(os.listdir(history_dir)):
        if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f):
            snap = fb._load_snapshot(os.path.join(history_dir, f))
            snap["_date"] = f[:-5]
            out.append(snap)
    return out


def _old_usable(history_dir) -> list[dict]:
    return [s for s in _old_all(history_dir)
            if s["_date"] not in fb.PARTIAL_SNAPSHOT_DATES and not fb.snapshot_is_degraded(s)]


def _current_rows(history_dir):
    latest = fb._load_snapshot(os.path.join(history_dir, sorted(os.listdir(history_dir))[-1]))
    return [{**a, "display_listing_status": a["listing_status"], "language": "Python"}
            for a in latest["agents"]]


def test_rows_match_the_full_snapshot_field_by_field(history_dir):
    old, new = _old_all(history_dir), fb.load_history_series(str(history_dir))
    assert [d["_date"] for d in old] == [d["_date"] for d in new]
    for o, n in zip(old, new):
        assert o.get("methodology_version") == n.get("methodology_version")
        assert len(o["agents"]) == len(n["agents"])
        for oa, na in zip(o["agents"], n["agents"]):
            for f in fb.HISTORY_SERIES_FIELDS:
                assert (f in oa) == (f in na), f
                assert oa.get(f) == na.get(f), f
            for f, k in fb.HISTORY_SERIES_NESTED.items():
                ov, nv = (oa.get(f) or {}).get(k, "dflt"), (na.get(f) or {}).get(k, "dflt")
                assert (list(ov) if isinstance(ov, list) else ov) == \
                       (list(nv) if isinstance(nv, tuple) else nv), f
            assert "description" not in na


def test_usable_days_skip_partial_and_degraded(history_dir):
    old = [d["_date"] for d in _old_usable(history_dir)]
    assert [d["_date"] for d in fb.load_history(str(history_dir))] == old
    assert len(old) == DAYS - 2


def test_every_history_reader_gives_identical_output(history_dir):
    old, new = _old_usable(history_dir), fb.load_history(str(history_dir))
    rows = _current_rows(history_dir)
    slug_map = {r["repo"].lower(): r["slug"] for r in rows}
    for fn in (fb.compute_sparklines, fb.compute_weekly_changes, fb.compute_snapshot_posts,
               fb.compute_ecosystem_trends, fb.compute_quarterly_reports):
        assert fn(old) == fn(new), fn.__name__
    assert fb.compute_movers(old, slug_map, rows=rows, limit=12) == \
           fb.compute_movers(new, slug_map, rows=rows, limit=12)
    assert fb.compute_movers_page_data(rows, old) == fb.compute_movers_page_data(rows, new)
    assert fb.compute_newly_added(rows, old) == fb.compute_newly_added(rows, new)
    assert fb.compute_quarterly_reports(new), "fixture must span a completed quarter"


def test_reputation_events_are_identical(history_dir):
    def by_date(days):
        return ({d["_date"]: {a["repo"].lower(): a for a in d["agents"]} for d in days},
                {d["_date"]: d.get("methodology_version") for d in days})
    today = {r["repo"].lower(): r for r in _current_rows(history_dir)}
    old_h, old_m = by_date(_old_all(history_dir))
    new_h, new_m = by_date(fb.load_history_series(str(history_dir)))
    events = fb.derive_agent_events(new_h, today, new_m)
    assert fb.derive_agent_events(old_h, today, old_m) == events
    assert any(e["type"] == "drift_warning_raised" for evs in events.values() for e in evs)


@pytest.mark.parametrize("yesterday_partial", [False, True])
def test_prior_day_readers_match_the_file_readers(history_dir, tmp_path, monkeypatch, yesterday_partial):
    if yesterday_partial:
        monkeypatch.setattr(fb, "PARTIAL_SNAPSHOT_DATES", fb.PARTIAL_SNAPSHOT_DATES | {_date(DAYS - 2)})
    h, days = str(history_dir), fb.load_history_series(str(history_dir))
    def ranks(snap):
        return [(a["repo"], a.get("rank"), a.get("trust_score")) for a in snap["agents"]]
    assert ranks(fb._load_prior_snapshot(h, days)) == ranks(fb._load_prior_snapshot(h))
    assert fb.load_previous_ranks(h, days) == fb.load_previous_ranks(h)
    assert fb.load_previous_pending(h, days) == fb.load_previous_pending(h)
    for lookback in (3, 14, 200):
        assert fb.load_previous_downloads(h, lookback, days=days) == fb.load_previous_downloads(h, lookback)
    data_path = str(tmp_path / "data.json")
    (tmp_path / "data.json").write_text(json.dumps({"agents": [{"repo": "o/a3", "weekly_commits": 7}]}))
    assert fb.load_cached_commit_counts(data_path, h, days) == fb.load_cached_commit_counts(data_path, h)
    rows = _current_rows(history_dir)
    today = {r["repo"].lower(): r for r in rows}
    assert fb.compute_trust_trends(h, today, days) == fb.compute_trust_trends(h, today)
    assert fb.check_board_invariants(rows, fb._load_prior_snapshot(h, days)) == \
        fb.check_board_invariants(rows, fb._load_prior_snapshot(h))


def test_cache_parses_each_snapshot_once(history_dir, tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    before = sorted(os.listdir(history_dir))
    parses = []
    real = fb._series_entry
    monkeypatch.setattr(fb, "_series_entry", lambda snap, sig: parses.append(1) or real(snap, sig))

    first = fb.load_history_series(str(history_dir), str(cache_dir))
    assert len(parses) == DAYS
    parses.clear()
    second = fb.load_history_series(str(history_dir), str(cache_dir))
    assert parses == []
    assert [dict(a) for d in first for a in d["agents"]] == [dict(a) for d in second for a in d["agents"]]

    # Today's snapshot is rewritten on every render: only it is re-read.
    today = history_dir / before[-1]
    snap = json.loads(today.read_text())
    snap["agents"][1]["rank"] = 999
    today.write_text(json.dumps(snap))
    third = fb.load_history_series(str(history_dir), str(cache_dir))
    assert len(parses) == 1
    assert third[-1]["agents"][1]["rank"] == 999
    # The snapshots are never touched and the cache never lands beside them.
    assert sorted(os.listdir(history_dir)) == before


def test_rename_is_applied_on_load_not_baked_into_the_cache(history_dir, tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    fb.load_history_series(str(history_dir), str(cache_dir))
    monkeypatch.setattr(fb, "REPO_RENAMES", {})
    repos = {a["repo"] for d in fb.load_history_series(str(history_dir), str(cache_dir))
             for a in d["agents"]}
    assert OLD_REPO in repos


def test_stale_cache_version_is_rebuilt(history_dir, tmp_path):
    cache_dir = tmp_path / "cache"
    fb.load_history_series(str(history_dir), str(cache_dir))
    name = sorted(os.listdir(cache_dir))[0]
    entry = json.loads((cache_dir / name).read_text())
    entry["v"] = 0
    entry["cols"]["rank"] = [-1] * entry["n"]
    (cache_dir / name).write_text(json.dumps(entry))
    days = fb.load_history_series(str(history_dir), str(cache_dir))
    assert all(a["rank"] != -1 for a in days[0]["agents"])


def test_history_rows_are_read_only(history_dir):
    row = fb.load_history(str(history_dir))[-1]["agents"][0]
    with pytest.raises(TypeError):
        row["rank"] = 1


def test_unwritable_cache_never_fails_the_render(history_dir, tmp_path, monkeypatch):
    real_replace = os.replace

    def full_disk(src, dst):
        if str(dst).startswith(str(tmp_path / "cache")):
            raise OSError(28, "No space left on device")
        return real_replace(src, dst)
    monkeypatch.setattr(fb.os, "replace", full_disk)
    days = fb.load_history_series(str(history_dir), str(tmp_path / "cache"))
    assert len(days) == DAYS


def test_malformed_snapshot_is_skipped(history_dir):
    (history_dir / "2020-01-01.json").write_text(json.dumps({"agents": [1, 2]}))
    days = fb.load_history_series(str(history_dir))
    assert "2020-01-01" not in {d["_date"] for d in days} and len(days) == DAYS


def test_public_history_files_serve_exactly_what_the_old_index_did(history_dir, tmp_path, monkeypatch):
    import app
    import mcp_server
    root = tmp_path / "root"
    (root / "output").mkdir(parents=True)
    (root / "output" / "history").symlink_to(history_dir)
    base = tmp_path / "base"
    base.mkdir()
    (base / "agents.json").write_text(json.dumps([{"repo": NEW_REPO, "previous_repos": [OLD_REPO]}]))
    monkeypatch.setattr(app, "OUTPUT_DIR", str(root))
    monkeypatch.setattr(app, "BASE_DIR", str(base))
    monkeypatch.setattr(app, "_PARTIAL_SNAPSHOT_DATES", fb.PARTIAL_SNAPSHOT_DATES)
    mcp_server._history_index.update({"mtime": None, "data": None})
    old = mcp_server._get_history_index()
    assert old[NEW_REPO] and len(old) > 12

    fb.write_public_history(fb.load_history_series(str(history_dir)),
                            str(root / ".cache" / "history-api"))
    for repo_key, points in old.items():
        assert mcp_server._history_points(repo_key) == points, repo_key
    assert mcp_server._history_points("no/such-repo") == []
    assert mcp_server._history_index["data"] is None  # the fallback index is dropped


def test_public_history_fields_mirror_the_api():
    import app
    assert app._HISTORY_PUBLIC_FIELDS == fb.HISTORY_PUBLIC_FIELDS
    assert app._HISTORY_PUBLIC_DAYS == fb.HISTORY_PUBLIC_DAYS


def test_todays_snapshot_is_recorded_without_a_reparse(history_dir, tmp_path, monkeypatch):
    cache_dir = str(tmp_path / "cache")
    days = fb.load_history_series(str(history_dir), cache_dir)
    today = days[-1]["_date"]
    snap = json.loads((history_dir / f"{today}.json").read_text())
    snap["agents"][2]["trust_score"] = 12.3
    path = history_dir / f"{today}.json"
    path.write_text(json.dumps(snap, indent=2))
    fb.record_history_series_day(days, today, snap, str(path), cache_dir)
    assert len(days) == DAYS and days[-1]["agents"][2]["trust_score"] == 12.3

    parses = []
    real = fb._series_entry
    monkeypatch.setattr(fb, "_series_entry", lambda s, sig: parses.append(1) or real(s, sig))
    again = fb.load_history_series(str(history_dir), cache_dir)
    assert parses == []
    fresh = fb.load_history_series(str(history_dir))
    assert [dict(a) for a in again[-1]["agents"]] == [dict(a) for a in fresh[-1]["agents"]]
