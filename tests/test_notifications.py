"""Regression tests for watchlist notifications (v3.2 T2.1).

Locks the product-plan acceptance criteria: a *watched* agent whose trust/rank
moved past a threshold yields exactly one in-app notification, while an equally
moved *unwatched* agent yields none. Move detection itself lives in
derive_agent_events (fetch_and_build.py); here we assert /api/notifications
surfaces those moves to the right user and honours read state.

Runs without Postgres: the db accessors and the rendered agents index are
stubbed, and the endpoint is driven through a minimal app mounting only
auth.router (no scheduler / static site build).
"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth

# One event per agent so "moved -> exactly one notification" is unambiguous.
_INDEX = {
    "watched-mover": {
        "slug": "watched-mover", "name": "Watched Mover",
        "recent_events": [{
            "date": "2026-06-30", "type": "trust_score_changed",
            "label": "HVTrust up", "detail": "HVTrust up 4.0pts (70.0 -> 74.0)",
            "tone": "positive",
        }],
    },
    "watched-stable": {
        "slug": "watched-stable", "name": "Watched Stable",
        "recent_events": [],
    },
    "unwatched-mover": {
        "slug": "unwatched-mover", "name": "Unwatched Mover",
        "recent_events": [{
            "date": "2026-06-30", "type": "rank_changed",
            "label": "Rank rose", "detail": "Rank rose 12 spots (#40 -> #28)",
            "tone": "positive",
        }],
    },
}


@pytest.fixture
def client(monkeypatch):
    # Simulate a DB-backed account watching two of the three agents.
    monkeypatch.setattr(auth.db, "enabled", lambda: True)
    monkeypatch.setattr(auth.db, "get_user", lambda uid: {"id": uid})
    monkeypatch.setattr(auth.db, "list_watch",
                        lambda uid: ["watched-mover", "watched-stable"])
    monkeypatch.setattr(auth.db, "get_last_read", lambda uid: None)
    monkeypatch.setattr(auth, "_agents_index", lambda: _INDEX)

    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


def _auth_headers():
    token = auth._sign({"uid": 1, "exp": int(time.time()) + 3600})
    return {"Cookie": f"{auth.SESSION_COOKIE}={token}"}


def test_requires_auth(client):
    assert client.get("/api/notifications").status_code == 401


def test_watched_move_yields_one_notification(client):
    data = client.get("/api/notifications", headers=_auth_headers()).json()
    # Exactly one notification, for the watched agent that moved.
    assert [i["slug"] for i in data["items"]] == ["watched-mover"]
    assert data["watching"] == 2


def test_unwatched_move_yields_none(client):
    data = client.get("/api/notifications", headers=_auth_headers()).json()
    assert "unwatched-mover" not in [i["slug"] for i in data["items"]]


def test_move_is_unread_until_read(client, monkeypatch):
    # Fresh account (no last_read) -> the move is unread.
    first = client.get("/api/notifications", headers=_auth_headers()).json()
    assert first["unread"] == 1
    assert first["items"][0]["unread"] is True

    # After marking read (last_read now past the event date) -> shown, not unread.
    monkeypatch.setattr(auth.db, "get_last_read", lambda uid: "2026-07-01T00:00:00Z")
    after = client.get("/api/notifications", headers=_auth_headers()).json()
    assert after["unread"] == 0
    assert after["items"][0]["unread"] is False
