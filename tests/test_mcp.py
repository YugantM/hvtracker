"""Tests for the trust-layer MCP server (mcp_server.py).

Fast and offline: monkeypatches app.load_data with a small fixture so the tools
are exercised without a built data.json, a database, or network.
"""
import asyncio
import json

import pytest

import app
import mcp_server

FIXTURE = {"agents": [
    {"name": "LangGraph", "repo": "langchain-ai/langgraph", "slug": "langgraph",
     "trust_score": 92.2, "evidence_grade": "A", "rank": 2,
     "category": "Agent Frameworks", "has_provenance": True, "scorecard_score": 6.8,
     "pypi_package": "langgraph", "npm_package": "@langchain/langgraph",
     "description": "Build resilient agents.", "stars": 34000,
     "listing_status": "listed"},
    {"name": "AIPass", "repo": "AIOSAI/AIPass", "slug": "aipass",
     "trust_score": 70.0, "evidence_grade": "C", "rank": 50,
     "category": "Multi-Agent Systems", "has_provenance": False,
     "scorecard_score": None, "pypi_package": "aipass", "description": "",
     "listing_status": "listed"},
]}


@pytest.fixture(autouse=True)
def _fixture_data(monkeypatch):
    monkeypatch.setattr(app, "load_data", lambda: FIXTURE)


def test_check_agent_trust_resolves_by_name_slug_repo_url_package():
    for q in ("LangGraph", "langgraph", "langchain-ai/langgraph",
              "https://github.com/langchain-ai/langgraph", "@langchain/langgraph"):
        r = mcp_server.check_agent_trust(q)
        assert r["tracked"] is True, q
        assert r["name"] == "LangGraph"
        assert r["trust_score"] == 92.2
        assert r["evidence_grade"] == "A"
        assert r["profile_url"] == "https://hvtracker.net/agents/langgraph/"


def test_check_agent_trust_unknown_is_graceful():
    r = mcp_server.check_agent_trust("definitely-not-tracked-xyz")
    assert r["tracked"] is False
    assert "submit_url" in r


def test_verify_mcp_server_verdict():
    r = mcp_server.verify_mcp_server("langchain-ai/langgraph")
    assert r["tracked"] is True
    assert r["trusted"] is True
    assert r["grade"] == "A"
    # Unknown server: not trusted, but graceful (no evidence != guaranteed harm).
    r2 = mcp_server.verify_mcp_server("evil/unknown-server")
    assert r2["tracked"] is False
    assert r2["trusted"] is False


def test_search_agents_ranks_by_trust_and_filters_category():
    r = mcp_server.search_agents("")
    assert r["count"] == 2
    assert r["results"][0]["name"] == "LangGraph"  # higher trust first
    r2 = mcp_server.search_agents(category="Multi-Agent Systems")
    assert [a["name"] for a in r2["results"]] == ["AIPass"]


def test_check_agent_trust_includes_capabilities_and_credential():
    r = mcp_server.check_agent_trust("langgraph")
    assert r["coverage_grade"] is None  # fixture has no coverage_grade
    caps = r["capabilities"]
    assert caps["mcp_status"] == "none"
    assert caps["provider_count"] == 0
    assert caps["requires_api_keys"] is False
    assert r["credential_url"] == "https://hvtracker.net/data/agents/langgraph.json"


def test_compare_agents_verdict_and_profiles():
    r = mcp_server.compare_agents("LangGraph", "aipass")
    assert r["a"]["tracked"] and r["b"]["tracked"]
    assert "LangGraph scores higher" in r["verdict"]
    assert "92.2" in r["verdict"] and "70" in r["verdict"]
    # no published compare page in the test env
    assert r["compare_url"] is None


def test_compare_agents_untracked_side_is_graceful():
    r = mcp_server.compare_agents("LangGraph", "not-a-real-agent-xyz")
    assert r["b"]["tracked"] is False
    assert r["verdict"].startswith("No verdict")
    assert r["compare_url"] is None


def test_scan_stack_verdicts_and_summary_math():
    r = mcp_server.scan_stack("langgraph\naipass\ntotally-unknown-pkg")
    s = r["summary"]
    assert s["total"] == 3
    assert s["tracked"] == 2
    assert s["untracked"] == 1
    assert s["trusted"] >= 1
    # avg_trust averages only the tracked/scored items (92.2 and 70.0 → 81.1).
    assert s["avg_trust"] == 81.1
    by_input = {row["input"]: row for row in r["results"]}
    assert by_input["langgraph"]["tracked"] is True
    assert by_input["totally-unknown-pkg"]["tracked"] is False


def test_scan_stack_caps_oversized_input():
    # 20k-char cap keeps work bounded; an overlong blob must not error.
    r = mcp_server.scan_stack("langgraph\n" + ("x" * 30000))
    assert r["summary"]["total"] >= 1


def test_list_categories_counts_and_hints():
    r = mcp_server.list_categories()
    assert r["count"] == 2
    cats = {c["category"]: c for c in r["categories"]}
    assert cats["Agent Frameworks"]["count"] == 1
    assert 'get_leaderboard(category="Agent Frameworks")' == \
        cats["Agent Frameworks"]["leaderboard_hint"]


def test_get_leaderboard_overall_and_by_category():
    r = mcp_server.get_leaderboard()
    assert r["count"] == 2
    assert r["results"][0]["name"] == "LangGraph"  # higher trust first
    r2 = mcp_server.get_leaderboard(category="Multi-Agent Systems")
    assert r2["category"] == "Multi-Agent Systems"
    assert [a["name"] for a in r2["results"]] == ["AIPass"]


def test_get_agent_history_unknown_is_graceful():
    r = mcp_server.get_agent_history("not-a-real-agent-xyz")
    assert r["tracked"] is False
    assert "message" in r


def test_get_agent_history_reads_snapshots_and_caches(tmp_path, monkeypatch):
    from datetime import date, timedelta
    hist = tmp_path / "output" / "history"
    hist.mkdir(parents=True)
    today = date.today()
    for i, sc in enumerate((80.0, 92.2)):
        day = (today - timedelta(days=1 - i)).isoformat()
        (hist / f"{day}.json").write_text(json.dumps({
            "methodology_version": "v4.2",
            "agents": [{"repo": "langchain-ai/langgraph", "rank": 3 - i,
                        "trust_score": sc, "evidence_grade": "A"}],
        }))
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    mcp_server._history_index.update({"mtime": None, "data": None})

    r = mcp_server.get_agent_history("langgraph")
    assert r["tracked"] is True
    assert r["count"] == 2
    assert r["history"][0]["trust_score"] == 80.0  # oldest first
    assert r["window_days"] == 90

    # Second call must reuse the cached index (same dir mtime → one build).
    first = mcp_server._get_history_index()
    second = mcp_server._get_history_index()
    assert first is second


EXPECTED_TOOLS = {
    "check_agent_trust", "verify_mcp_server", "search_agents", "compare_agents",
    "scan_stack", "list_categories", "get_leaderboard", "get_agent_history",
}


def test_tools_registered_with_input_schemas():
    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert set(tools) == EXPECTED_TOOLS
    assert "name_or_repo" in tools["check_agent_trust"].inputSchema["properties"]
    assert "server" in tools["verify_mcp_server"].inputSchema["properties"]
    check_schema = tools["check_agent_trust"].outputSchema["properties"]
    assert {"type": "null"} in check_schema["profile_url"]["anyOf"]
    assert {"type": "null"} in check_schema["message"]["anyOf"]
    assert {"type": "null"} in check_schema["submit_url"]["anyOf"]
    verify_schema = tools["verify_mcp_server"].outputSchema["properties"]
    assert {"type": "null"} in verify_schema["submit_url"]["anyOf"]
    for tool in tools.values():
        assert tool.outputSchema
        assert tool.outputSchema["type"] == "object"
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True


def test_streamable_http_serves_mcp_exact_path_without_redirect(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(app, "startup", lambda: None)
    monkeypatch.setattr(app, "shutdown", lambda: None)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"},
        },
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    with TestClient(app.app, base_url="https://hvtracker.net",
                    follow_redirects=False) as client:
        response = client.post("/mcp", headers=headers, json=payload)

    assert response.status_code == 200
    assert response.headers.get("location") is None
    body = response.json()
    assert body["result"]["serverInfo"]["name"] == "hvtracker"


def test_smithery_server_card_endpoint(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(app, "startup", lambda: None)
    monkeypatch.setattr(app, "shutdown", lambda: None)
    with TestClient(app.app, base_url="https://hvtracker.net",
                    follow_redirects=False) as client:
        response = client.get("/.well-known/mcp/server-card.json")

    assert response.status_code == 200
    assert response.headers.get("location") is None
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["serverInfo"]["name"] == "HVTracker MCP"
    assert body["serverInfo"]["description"]
    assert body["serverInfo"]["homepage"] == "https://hvtracker.net"
    assert body["homepage"] == "https://hvtracker.net"
    assert body["authentication"]["required"] is False
    card_tools = {tool["name"]: tool for tool in body["tools"]}
    check_schema = card_tools["check_agent_trust"]["outputSchema"]["properties"]
    assert check_schema["profile_url"]["type"] == ["string", "null"]
    assert check_schema["message"]["type"] == ["string", "null"]
    assert check_schema["submit_url"]["type"] == ["string", "null"]
    verify_schema = card_tools["verify_mcp_server"]["outputSchema"]["properties"]
    assert verify_schema["submit_url"]["type"] == ["string", "null"]
    for tool in body["tools"]:
        assert tool["outputSchema"]["type"] == "object"
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
    assert {tool["name"] for tool in body["tools"]} == EXPECTED_TOOLS
    compare_card = card_tools["compare_agents"]
    assert set(compare_card["inputSchema"]["required"]) == {"a", "b"}
    assert compare_card["outputSchema"]["required"] == ["a", "b", "verdict", "compare_url"]
