"""Repo renames keep a listing's score and history (roster previous_repos).

Rows are keyed by repo everywhere, so a GitHub rename used to read as a new
provisional agent ("Grade pending", history reset) until data re-accumulated.
"""
import json

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
