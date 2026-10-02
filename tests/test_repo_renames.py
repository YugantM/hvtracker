"""Repo renames keep a listing's score and history (roster previous_repos).

Rows are keyed by repo everywhere, so a GitHub rename used to read as a new
provisional agent ("Grade pending", history reset) until data re-accumulated.
"""
import json
from datetime import datetime, timezone

import pytest

import fetch_and_build as fab

OLD, NEW = "cacheplane/angular-agent-framework", "cacheplane/threadplane"
ROSTER = [{"repo": NEW, "name": "Threadplane", "previous_repos": [OLD]},
          {"repo": "o/other", "name": "Other"}]


@pytest.fixture
def renames(monkeypatch):
    monkeypatch.setattr(fab, "REPO_RENAMES", fab.repo_renames(ROSTER))
    return fab.REPO_RENAMES


def test_map_comes_from_previous_repos():
    assert fab.repo_renames(ROSTER) == {OLD: NEW}


def test_rows_move_to_the_current_repo(renames):
    rows = [{"repo": "CachePlane/Angular-Agent-Framework", "url": "https://github.com/CachePlane/Angular-Agent-Framework",
             "trust_score": 82.5},
            {"repo": "o/other", "url": "https://github.com/o/other"}]
    assert fab.apply_repo_renames(rows) == 1
    assert rows[0]["repo"] == NEW and rows[0]["url"] == f"https://github.com/{NEW}"
    assert rows[0]["trust_score"] == 82.5  # the score carries over, no provisional reset
    assert rows[1]["repo"] == "o/other"


def test_history_stays_continuous_across_the_rename(renames, tmp_path):
    for day, repo, rank in (("2026-09-10", OLD, 108), ("2026-09-11", NEW, 107)):
        (tmp_path / f"{day}.json").write_text(json.dumps(
            {"agents": [{"repo": repo, "rank": rank, "trust_score": 82.0}] +
                       [{"repo": f"o/r{i}", "rank": i} for i in range(9)]}))
    history = fab.load_history(str(tmp_path))
    assert [a["repo"] for snap in history for a in snap["agents"] if a["rank"] > 100] == [NEW, NEW]


def test_previous_build_rows_are_matched_under_the_new_name(renames, tmp_path):
    data = tmp_path / "latest.json"
    data.write_text(json.dumps({"agents": [{"repo": OLD, "trust_score": 82.5, "weekly_commits": 12}]}))
    assert NEW.lower() in fab.load_existing_agents_map(str(data))
    assert fab.load_cached_commit_counts(str(data), str(tmp_path))[NEW.lower()] == 12
    kept = fab.merge_batch_into_data(str(data), [])
    assert kept[0]["repo"] == NEW


# A duplicate listing: the repo was listed again under its current name before
# the roster merged the two (Headroom as chopratejas/headroom and, as a skill,
# headroomlabs-ai/headroom). Pre-merge data carries both rows.
def _dup_rows():
    return [{"repo": OLD, "url": f"https://github.com/{OLD}", "rank": 247, "listing_class": "agent"},
            {"repo": NEW, "url": f"https://github.com/{NEW}", "rank": 26, "listing_class": "skill"},
            {"repo": "o/other", "rank": 3}]


def test_a_duplicate_listing_under_the_current_name_is_dropped(renames):
    rows = _dup_rows()
    assert fab.apply_repo_renames(rows) == 1
    assert [(r["repo"], r["rank"]) for r in rows] == [(NEW, 247), ("o/other", 3)]


def test_a_row_already_under_the_current_name_is_kept(renames):
    rows = [{"repo": NEW, "rank": 247}, {"repo": "o/other", "rank": 3}]
    assert fab.apply_repo_renames(rows) == 0
    assert len(rows) == 2


def test_history_keeps_only_the_carried_over_row(renames, tmp_path):
    filler = [{"repo": f"o/r{i}", "rank": i} for i in range(9)]
    (tmp_path / "2020-01-01.json").write_text(json.dumps({"agents": _dup_rows() + filler}))
    (tmp_path / "2020-01-02.json").write_text(json.dumps({"agents": _dup_rows() + filler}))
    for day in fab.load_history(str(tmp_path)):
        assert [a["rank"] for a in day["agents"] if a["repo"] == NEW] == [247]
    prior = fab._load_prior_snapshot(str(tmp_path))
    assert [a["rank"] for a in prior["agents"] if a["repo"] == NEW] == [247]


def test_mcp_history_skips_the_duplicate_listing(tmp_path, monkeypatch):
    import app
    import mcp_server
    hist = tmp_path / "output" / "history"
    hist.mkdir(parents=True)
    filler = [{"repo": f"o/r{i}", "rank": i} for i in range(9)]
    (hist / f"{datetime.now(timezone.utc):%Y-%m-%d}.json").write_text(
        json.dumps({"agents": _dup_rows() + filler}))
    (tmp_path / "agents.json").write_text(json.dumps(ROSTER))
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "BASE_DIR", str(tmp_path))
    mcp_server._history_index.update({"mtime": None, "data": None})
    index = mcp_server._get_history_index()
    assert [p["rank"] for p in index[NEW.lower()]] == [247]


def test_the_listings_own_scan_replaces_the_duplicates_older_one(renames):
    older = {"score": 5.0, "scanned_at": "2026-09-20T14:41:04Z"}
    newer = {"score": 6.5, "scanned_at": "2026-10-01T21:04:57Z"}
    cache = {OLD: newer, NEW: older}  # the duplicate's stale scan sits under NEW
    assert fab.carry_scorecards_over_renames(cache) == 1
    assert cache[NEW] is newer
    cache = {OLD: older, NEW: newer}
    assert fab.carry_scorecards_over_renames(cache) == 0
    assert cache[NEW] is newer


def test_a_plain_rename_gets_no_scan_from_its_previous_name(renames):
    # Threadplane's row holds a fresher API score (8.2) than the scan under
    # its old name (7.8); a cache hit would overwrite it, so none is made.
    cache = {"CachePlane/Angular-Agent-Framework": {"score": 7.8, "scanned_at": "2026-09-22T15:24:31Z"}}
    assert fab.carry_scorecards_over_renames(cache) == 0
    assert NEW not in cache
