""""How X could raise its score" (plan 5.2).

Every suggestion is the live scoring function re-run with one signal changed,
so the page can never promise a gain the real score wouldn't give. These tests
pin that: the no-change what-if reproduces each row's live score, and a row
whose score the function can't reproduce gets no suggestions at all."""
import json
import os

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_what_if_reproduces_every_score_a_render_assigns(tmp_path, monkeypatch):
    """Oracle = a real (offline) render: every row it scores must be reproduced
    by the what-if, and carry suggestions computed against that score."""
    import glob
    import shutil
    os.makedirs(tmp_path / "data")
    os.makedirs(tmp_path / "output" / "history")
    shutil.copy(os.path.join(ROOT, "data", "render_state.json"), tmp_path / "data" / "render_state.json")
    for h in glob.glob(os.path.join(ROOT, "seed", "history", "*.json")):
        shutil.copy(h, tmp_path / "output" / "history")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    fab.run_refresh("render")
    with open(tmp_path / "data" / "render_state.json", encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    scored = [r for r in rows if not r.get("pending_signals") and r.get("trust_score") is not None]
    assert len(scored) > 100
    for r in scored:
        assert abs(fab.what_if_score(r) - r["trust_score"]) <= 0.05, r["repo"]
        assert fab.grade_for_score(r["trust_score"]) == r["evidence_grade"], r["repo"]
    assert sum(1 for r in scored if r.get("improvements")) > len(scored) // 2


def _row(**over):
    row = {"repo": "o/r", "listing_status": "listed", "days_ago": 3, "weekly_commits": 40,
           "stars": 20000, "weekly_downloads": 40000, "npm_package": "r", "license_spdx": "MIT",
           "scorecard_score": 6.0, "scorecard_checks": {"Code-Review": 2, "Fuzzing": 0, "SAST": 8},
           "signed_commits_ratio": 0.5, "has_provenance": False}
    row.update(over)
    row["trust_score"] = fab.what_if_score(row)
    return row


def test_suggestions_are_real_gains_ranked_and_placed_in_the_category():
    row = _row()
    imp = fab.score_improvements(row, [row["trust_score"], 99.0, 10.0])
    assert [i["key"] for i in imp] == sorted([i["key"] for i in imp], key=lambda k: -next(
        x["gain"] for x in imp if x["key"] == k))
    for i in imp:
        assert i["gain"] >= 0.5 and i["score"] == round(row["trust_score"] + i["gain"], 1)
        assert i["grade"] == fab.grade_for_score(i["score"])
        assert i["category_rank"] == 1 + (i["score"] < 99.0) and i["category_size"] == 3
    keys = {i["key"] for i in imp}
    assert keys == {"provenance", "scorecard", "signing"}
    sc = next(i for i in imp if i["key"] == "scorecard")
    assert sc["detail"] == "lowest checks: Fuzzing 0, Code-Review 2"
    assert "--provenance" in next(i for i in imp if i["key"] == "provenance")["detail"]


def test_only_actionable_signals_are_suggested():
    row = _row(npm_package="", has_provenance=False, scorecard_score=9.5, signed_commits_ratio=1.0)
    keys = {i["key"] for i in fab.score_improvements(row)}
    assert "provenance" not in keys  # no npm/PyPI package: nothing to attest
    assert not keys & {"scorecard", "signing"}
    assert {i["key"] for i in fab.score_improvements(_row(license_spdx=None))} >= {"license"}


def test_no_suggestions_for_provisional_or_unexplained_scores():
    assert fab.score_improvements(_row(pending_signals=True)) == []
    drifted = _row()
    drifted["trust_score"] += 3.0  # a score the function doesn't reproduce
    assert fab.score_improvements(drifted) == []


def test_main_attaches_them_per_category():
    import inspect
    assert "score_improvements(row, peer_scores)" in inspect.getsource(fab.main)


def test_agent_page_card():
    from test_agent_verdict_card import _render
    imp = [{"key": "provenance", "action": "Publish build provenance for its packages",
            "detail": "npm publish --provenance from CI", "gain": 13.6, "score": 90.4, "grade": "A",
            "link": "https://docs.npmjs.com/generating-provenance-statements",
            "category_rank": 1, "category_size": 61}]
    html = _render(pending_signals=False, evidence_grade="B", trust_score=76.8, improvements=imp)
    assert 'id="imp-title"' in html and "+13.6" in html and "#1 of 61" in html
    assert 'id="imp-title"' not in _render(pending_signals=False, evidence_grade="A",
                                           trust_score=96.3, improvements=[])
