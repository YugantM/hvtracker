"""Tests for the trust-layer MCP server (mcp_server.py).

Fast and offline: monkeypatches app.load_data with a small fixture so the tools
are exercised without a built data.json, a database, or network.
"""
import asyncio

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


def test_tools_registered_with_input_schemas():
    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert set(tools) == {"check_agent_trust", "verify_mcp_server", "search_agents"}
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
    for tool in body["tools"]:
        assert tool["outputSchema"]["type"] == "object"
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
    assert {tool["name"] for tool in body["tools"]} == {
        "check_agent_trust",
        "verify_mcp_server",
        "search_agents",
    }
