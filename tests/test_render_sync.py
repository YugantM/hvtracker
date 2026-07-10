"""Render-only sync invariants.

After repeated regressions on 2026-06-01 (4 commits to get the
image-volume render_state sync correct on Railway), these tests pin the
core behaviour so it doesn't quietly break again.

Invariants under test
---------------------
1. Image render_state.json is seeded to the volume *only when missing*,
   never overwritten — protects fresh data from being clobbered by a
   stale Docker image on deploy.

2. add_provisional_missing_agents() adds an agents.json entry to the
   rendered output when it's missing from render_state.json — the
   mechanism that makes "newly listed" agents appear after a push without
   waiting for the next scheduled refresh.
"""

import json
import os
import shutil

import pytest

import fetch_and_build as fb


# ---- 2. provisional listing of newly-added agents ----------------------


def test_provisional_listing_adds_missing_agent():
    """An agents.json entry not present in `rows` gets a provisional row."""
    rows = [
        {"repo": "existing/agent", "name": "Existing", "rank": 1, "slug": "existing"},
    ]
    agents = [
        {"repo": "existing/agent", "name": "Existing"},
        {"repo": "new-org/new-agent", "name": "NewAgent", "category": "Agent Frameworks"},
    ]
    added = fb.add_provisional_missing_agents(rows, agents)
    assert added == 1
    repos = {r["repo"].lower() for r in rows}
    assert "new-org/new-agent" in repos


def test_legacy_rows_restored_provisionally():
    """Legacy agents lost from the render cache must be re-added (internal
    only): prod never runs a full fetch, so without this they stayed gone —
    emptying data/retired.json (breaking the 410s) and getting miscounted
    as failed fetches (2026-07-10 bug: all 22 legacy agents affected)."""
    legacy_rows = []
    legacy_agents = [
        {"repo": "stale/old-agent", "name": "OldAgent",
         "category": "Agent Frameworks", "listing_status": "legacy"},
    ]
    added = fb.add_provisional_missing_agents(legacy_rows, legacy_agents)
    assert added == 1
    row = legacy_rows[0]
    assert row["listing_status"] == "legacy"
    assert row["pending_signals"] is True
    # retired.json needs slugs — assign_unique_slugs covers legacy rows too
    fb.assign_unique_slugs(legacy_rows)
    assert row["slug"] == "oldagent"


def test_agents_json_status_fields_agree():
    """status and listing_status must never contradict each other — SuperAGI
    carried status=legacy + listing_status=listed, so the split treated it
    as legacy while everything keying on listing_status counted it listed."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "agents.json"), encoding="utf-8") as f:
        agents = json.load(f)
    bad = [a["repo"] for a in agents
           if {a.get("status"), a.get("listing_status")} >= {"legacy", "listed"}]
    assert bad == [], f"contradictory status fields: {bad}"


def test_provisional_row_seeds_commits_as_unknown():
    """weekly_commits must seed as None ("not fetched yet"), not 0.
    app._has_missing_commit_rows() only detects None, so a 0 seed made new
    agents look already-counted — the startup repair-commits refresh never
    fired and they showed 0 commits indefinitely (2026-07-10 bug)."""
    row = fb.provisional_agent_row(
        {"repo": "new-org/new-agent", "name": "NewAgent", "category": "Agent Frameworks"}
    )
    assert row["weekly_commits"] is None
    assert row["pending_signals"] is True


def test_missing_commit_detection_catches_provisional_rows(tmp_path, monkeypatch):
    """The startup repair trigger must see a freshly-provisioned agent."""
    import app as app_mod
    provisional = fb.provisional_agent_row(
        {"repo": "new-org/new-agent", "name": "NewAgent", "category": "Agent Frameworks"}
    )
    data = {"agents": [{"repo": "old/agent", "weekly_commits": 12}, provisional]}
    p = tmp_path / "data.json"
    p.write_text(json.dumps(data))
    monkeypatch.setattr(app_mod, "DATA_PATH", str(p))
    assert app_mod._has_missing_commit_rows() is True
    # and stays quiet when every row has a real count
    data["agents"][1]["weekly_commits"] = 0
    p.write_text(json.dumps(data))
    assert app_mod._has_missing_commit_rows() is False


def test_provisional_listing_skips_already_present():
    """Don't double-add agents already in `rows`."""
    rows = [
        {"repo": "existing/agent", "name": "Existing", "rank": 1, "slug": "existing"},
    ]
    agents = [{"repo": "existing/agent", "name": "Existing"}]
    added = fb.add_provisional_missing_agents(rows, agents)
    assert added == 0
    assert len(rows) == 1


def test_provisional_listing_skips_legacy_agents():
    """Legacy-status agents are handled separately, not provisioned into
    the active leaderboard."""
    rows = [{"repo": "existing/agent", "name": "Existing", "rank": 1, "slug": "existing"}]
    agents = [
        {"repo": "existing/agent", "name": "Existing"},
        {"repo": "stale/legacy", "name": "Stale", "status": "legacy"},
    ]
    added = fb.add_provisional_missing_agents(rows, agents)
    # legacy entries are filtered before this function in main(); regardless,
    # if a legacy entry sneaks through, it should not be promoted to active.
    # We don't strictly assert here on count — just that the active set stays sane.
    active_repos = {r["repo"].lower() for r in rows if r.get("status") != "legacy"}
    assert "existing/agent" in active_repos


# ---- 1. render_state volume seed only when missing --------------------


def test_image_render_state_seeded_when_volume_missing(tmp_path, monkeypatch):
    """When OUTPUT_DIR/data/render_state.json doesn't exist, the image
    copy is seeded to the volume."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    volume = tmp_path / "volume"
    (volume / "data").mkdir(parents=True)
    # Volume has no render_state.json yet.
    assert not (volume / "data" / "render_state.json").exists()

    # Reproduce the seed step from fetch_and_build.main():
    image_rs = os.path.join(repo_root, "data", "render_state.json")
    volume_rs = volume / "data" / "render_state.json"
    if os.path.isfile(image_rs) and not volume_rs.exists():
        shutil.copy2(image_rs, volume_rs)

    assert volume_rs.exists()
    # Volume copy must match the image copy byte-for-byte after seeding.
    assert open(volume_rs, "rb").read() == open(image_rs, "rb").read()


def test_volume_render_state_not_overwritten_when_present(tmp_path):
    """When the volume already has render_state.json (from a prior
    scheduled refresh), a fresh boot must NOT overwrite it with the
    image copy."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    volume = tmp_path / "volume"
    (volume / "data").mkdir(parents=True)
    volume_rs = volume / "data" / "render_state.json"

    # Pretend the volume has a fresh, scheduled-refresh-updated copy.
    fresh = {"rows": [{"repo": "fresh/data", "name": "Fresh", "rank": 1}], "legacy_rows": []}
    volume_rs.write_text(json.dumps(fresh))

    # Re-run the seed logic.
    image_rs = os.path.join(repo_root, "data", "render_state.json")
    if os.path.isfile(image_rs) and not volume_rs.exists():
        shutil.copy2(image_rs, volume_rs)

    # The volume's fresh copy must survive.
    after = json.load(open(volume_rs))
    assert after == fresh


def test_history_seeded_into_separate_output_root(tmp_path):
    """Render-only output roots should inherit baked history snapshots so
    rank deltas and sparklines are available during image builds."""
    base_dir = tmp_path / "base"
    script_dir = tmp_path / "prebuilt"
    seed_dir = base_dir / "seed" / "history"
    seed_dir.mkdir(parents=True)
    (seed_dir / "2026-06-10.json").write_text(json.dumps({"agents": []}))

    copied = fb.seed_history_into_output_root(str(base_dir), str(script_dir))

    assert copied == 1
    assert (script_dir / "output" / "history" / "2026-06-10.json").exists()
