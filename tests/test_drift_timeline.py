"""Runtime-drift monitoring (T3.5 / master plan 3.1).

Capability-surface changes between daily snapshots become timeline events:
MCP status transitions, provider dependencies appearing/disappearing, and
tool/plugin-surface changes — joining the provenance/drift/staleness events
that already existed. filter_drift_events() selects the drift-class subset
for the agent-page timeline; the bell path must surface them to watchers.
"""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth
import fetch_and_build as fab


def _agent(mcp="none", providers=None, plugin="none", **over):
    a = {
        "score": 80.0, "trust_score": 75.0, "rank": 20,
        "evidence_grade": "B", "listing_status": "listed", "days_ago": 3,
        "scorecard_score": 6.0, "has_provenance": True, "license_spdx": "MIT",
        "package_provenance_drift": {"status": "match"},
        "mcp_server_support": {"status": mcp},
        "external_service_dependencies": {"providers": providers or [],
                                          "requires_api_keys": False},
        "tool_plugin_surface": {"plugin_system": plugin, "tool_tags": []},
    }
    a.update(over)
    return a


def _events(prev, curr):
    history = {"2026-07-06": {"org/x": prev}, "2026-07-07": {"org/x": curr}}
    methodology = {"2026-07-06": "v4.2", "2026-07-07": "v4.2"}
    return fab.derive_agent_events(history, {"org/x": curr}, methodology).get("org/x", [])


def _types(events):
    return [e["type"] for e in events]


def test_mcp_status_change_emits_event():
    evs = _events(_agent(mcp="declared"), _agent(mcp="implemented"))
    ev = next(e for e in evs if e["type"] == "mcp_status_changed")
    assert "declared → implemented" in ev["detail"]


def test_provider_added_and_removed():
    evs = _events(_agent(providers=["OpenAI", "Redis"]),
                  _agent(providers=["OpenAI", "Anthropic", "Postgres"]))
    added = next(e for e in evs if e["type"] == "provider_added")
    removed = next(e for e in evs if e["type"] == "provider_removed")
    assert "Anthropic, Postgres" in added["detail"]
    assert "grew" in added["detail"]
    assert "Redis" in removed["detail"]
    assert "shrank" in removed["detail"]


def test_tool_surface_change_emits_event():
    evs = _events(_agent(plugin="declared"), _agent(plugin="marketplace"))
    ev = next(e for e in evs if e["type"] == "tool_surface_changed")
    assert "declared → marketplace" in ev["detail"]


def test_stable_surface_is_silent():
    same = _agent(mcp="implemented", providers=["OpenAI"], plugin="declared")
    evs = _events(same, dict(same))
    drift_types = set(_types(evs)) & {"mcp_status_changed", "provider_added",
                                      "provider_removed", "tool_surface_changed"}
    assert drift_types == set()


def test_filter_drift_events_selects_surface_changes_only():
    events = [
        {"type": "mcp_status_changed", "date": "2026-07-07"},
        {"type": "provider_added", "date": "2026-07-07"},
        {"type": "trust_score_changed", "date": "2026-07-07"},
        {"type": "rank_changed", "date": "2026-07-07"},
        {"type": "drift_warning_raised", "date": "2026-07-07"},
        {"type": "stale_warning", "date": "2026-07-07"},
        {"type": "listed", "date": "2026-07-07"},
    ]
    kept = {e["type"] for e in fab.filter_drift_events(events)}
    assert kept == {"mcp_status_changed", "provider_added",
                    "drift_warning_raised", "stale_warning"}


# ---- acceptance: a watched synthetic drift rings the bell exactly once ----

_INDEX = {
    "drifty": {
        "slug": "drifty", "name": "Drifty",
        "recent_events": [{
            "date": "2026-07-07", "type": "provider_added",
            "label": "Surface",
            "detail": "Runtime surface grew — new detected provider dependency: Anthropic",
            "tone": "neutral",
        }],
    },
}


@pytest.fixture
def bell_client(monkeypatch):
    monkeypatch.setattr(auth.db, "enabled", lambda: True)
    monkeypatch.setattr(auth.db, "get_user", lambda uid: {"id": uid})
    monkeypatch.setattr(auth.db, "list_watch", lambda uid: ["drifty"])
    monkeypatch.setattr(auth.db, "get_last_read", lambda uid: None)
    monkeypatch.setattr(auth, "_agents_index", lambda: _INDEX)
    app = FastAPI()
    app.include_router(auth.router)
    return TestClient(app)


def test_watched_surface_drift_rings_the_bell_once(bell_client):
    token = auth._sign({"uid": 1, "exp": int(time.time()) + 3600})
    data = bell_client.get(
        "/api/notifications",
        headers={"Cookie": f"{auth.SESSION_COOKIE}={token}"},
    ).json()
    assert [i["slug"] for i in data["items"]] == ["drifty"]
    assert "Anthropic" in data["items"][0]["detail"]
