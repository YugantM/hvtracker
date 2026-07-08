"""Watchlist alerts that matter (master plan 2.4).

derive_agent_events gains grade flips (methodology-suppressed, like
trust/rank) and provenance-drift warning raised/cleared. The bell path
(auth /api/notifications) must surface the new event types to watchers.
"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth
import fetch_and_build as fab


def _agent(grade="B", drift="match", **over):
    a = {
        "score": 80.0, "trust_score": 75.0, "rank": 20,
        "evidence_grade": grade, "listing_status": "listed", "days_ago": 3,
        "scorecard_score": 6.0, "has_provenance": True, "license_spdx": "MIT",
        "package_provenance_drift": {"status": drift},
    }
    a.update(over)
    return a


def _events(prev, curr, prev_m="v4.2", curr_m="v4.2"):
    history = {"2026-07-06": {"org/x": prev}, "2026-07-07": {"org/x": curr}}
    methodology = {"2026-07-06": prev_m, "2026-07-07": curr_m}
    out = fab.derive_agent_events(history, {"org/x": curr}, methodology)
    return out.get("org/x", [])


def _types(events):
    return [e["type"] for e in events]


def test_grade_flip_up_and_down():
    up = _events(_agent(grade="B"), _agent(grade="A"))
    assert "grade_changed" in _types(up)
    ev = next(e for e in up if e["type"] == "grade_changed")
    assert "B → A" in ev["detail"]
    down = _events(_agent(grade="A"), _agent(grade="C"))
    ev = next(e for e in down if e["type"] == "grade_changed")
    assert "A → C" in ev["detail"]


def test_grade_flip_suppressed_across_methodology_change():
    evs = _events(_agent(grade="A"), _agent(grade="C"),
                  prev_m="v4.1", curr_m="v4.2")
    assert "grade_changed" not in _types(evs)


def test_drift_warning_raised_and_cleared():
    raised = _events(_agent(drift="match"), _agent(drift="warning"))
    assert "drift_warning_raised" in _types(raised)
    cleared = _events(_agent(drift="warning"), _agent(drift="match"))
    ev = next(e for e in cleared if e["type"] == "drift_warning_cleared")
    assert "now: match" in ev["detail"]


def test_benign_drift_transitions_are_silent():
    assert "drift_warning_raised" not in _types(
        _events(_agent(drift="unknown"), _agent(drift="partial")))
    assert "drift_warning_cleared" not in _types(
        _events(_agent(drift="match"), _agent(drift="unknown")))


# ---- bell path: a watched grade flip yields exactly one notification ------

_INDEX = {
    "graded": {
        "slug": "graded", "name": "Graded",
        "recent_events": [{
            "date": "2026-07-07", "type": "grade_changed",
            "label": "Grade", "detail": "Trust grade B → A", "tone": "positive",
        }],
    },
}


@pytest.fixture
def bell_client(monkeypatch):
    monkeypatch.setattr(auth.db, "enabled", lambda: True)
    monkeypatch.setattr(auth.db, "get_user", lambda uid: {"id": uid})
    monkeypatch.setattr(auth.db, "list_watch", lambda uid: ["graded"])
    monkeypatch.setattr(auth.db, "get_last_read", lambda uid: None)
    monkeypatch.setattr(auth, "_agents_index", lambda: _INDEX)
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


def test_watched_grade_flip_rings_the_bell_once(bell_client):
    token = auth._sign({"uid": 1, "exp": int(time.time()) + 3600})
    data = bell_client.get(
        "/api/notifications",
        headers={"Cookie": f"{auth.SESSION_COOKIE}={token}"},
    ).json()
    assert [i["slug"] for i in data["items"]] == ["graded"]
    assert "B → A" in data["items"][0]["detail"]
