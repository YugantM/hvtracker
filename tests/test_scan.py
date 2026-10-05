"""Tests for the bulk 'Scan your stack' helpers in app.py.

Fast and offline: monkeypatches app.load_data with a small fixture so resolution
runs without a built data.json, a database, or network. Mirrors test_mcp.py.
"""
import pytest

import app
import mcp_trust

FIXTURE = {"agents": [
    {"name": "LangGraph", "repo": "langchain-ai/langgraph", "slug": "langgraph",
     "trust_score": 92.2, "evidence_grade": "A", "listing_status": "listed",
     "pypi_package": "langgraph", "npm_package": "@langchain/langgraph"},
    {"name": "CrewAI", "repo": "crewAIInc/crewAI", "slug": "crewai",
     "trust_score": 70.0, "evidence_grade": "C", "listing_status": "listed",
     "pypi_package": "crewai"},
]}


@pytest.fixture(autouse=True)
def _fixture_data(monkeypatch):
    monkeypatch.setattr(app, "load_data", lambda: FIXTURE)


# ---- _parse_scan_input ---------------------------------------------------

def test_parse_requirements_txt():
    text = "langgraph==0.2.1\ncrewai>=0.5  # a comment\n-r other.txt\n\n# header\nllama-index"
    assert app._parse_scan_input(text) == ["langgraph", "crewai", "llama-index"]


def test_parse_package_json():
    text = '{"dependencies": {"@langchain/langgraph": "^0.2.0"}, "devDependencies": {"typescript": "5"}}'
    assert app._parse_scan_input(text) == ["@langchain/langgraph", "typescript"]


def test_parse_mcp_config_takes_names_and_urls():
    text = '{"mcpServers": {"cognee": {"url": "https://github.com/topoteretes/cognee"}}}'
    assert app._parse_scan_input(text) == ["cognee", "https://github.com/topoteretes/cognee"]


def test_parse_plain_list_and_dedup():
    assert app._parse_scan_input("crewai, CrewAI\ncrewai") == ["crewai"]


def test_parse_caps_item_count():
    text = "\n".join(f"pkg-{i}" for i in range(200))
    assert len(app._parse_scan_input(text)) == app._SCAN_MAX_ITEMS


def test_parse_empty():
    assert app._parse_scan_input("   ") == []


# ---- _resolve_registry_agent --------------------------------------------

def test_resolve_by_name_slug_repo_url_package():
    for q in ("LangGraph", "langgraph", "langchain-ai/langgraph",
              "https://github.com/langchain-ai/langgraph", "@langchain/langgraph"):
        assert (app._resolve_registry_agent(q) or {}).get("slug") == "langgraph", q


def test_resolve_unknown_is_none():
    assert app._resolve_registry_agent("not-a-real-agent") is None


# ---- end-to-end verdict composition (what the endpoint returns) ----------

def test_scan_verdicts_match_engine():
    ids = app._parse_scan_input("langgraph\ncrewai\nbogus-pkg")
    verdicts = {i: mcp_trust.evaluate(app._resolve_registry_agent(i), i) for i in ids}
    assert verdicts["langgraph"]["tracked"] and verdicts["langgraph"]["trusted"]
    assert verdicts["crewai"]["tracked"] and verdicts["crewai"]["trusted"]
    assert verdicts["bogus-pkg"]["tracked"] is False


# ---- package-id collisions (5 Oct: "fastmcp" resolved to the TypeScript port)

COLLIDING = {"agents": [
    # Board order: the TypeScript port ranks above the Python original.
    {"name": "FastMCP (TypeScript)", "repo": "punkpeye/fastmcp", "slug": "fastmcp-typescript",
     "npm_package": "fastmcp", "trust_score": 87.7, "evidence_grade": "A", "listing_status": "listed"},
    {"name": "FastMCP", "repo": "PrefectHQ/fastmcp", "slug": "fastmcp",
     "pypi_package": "fastmcp", "trust_score": 80.0, "evidence_grade": "A", "listing_status": "listed"},
    {"name": "Only Npm", "repo": "o/only-npm", "slug": "only-npm-agent",
     "npm_package": "only-npm", "trust_score": 60.0, "evidence_grade": "C", "listing_status": "listed"},
]}


def test_exact_slug_or_name_beats_a_colliding_package(monkeypatch):
    import mcp_server
    monkeypatch.setattr(app, "load_data", lambda: COLLIDING)
    for resolve in (app._resolve_registry_agent, mcp_server._resolve_agent):
        assert resolve("fastmcp")["repo"] == "PrefectHQ/fastmcp"
        assert resolve("FastMCP (TypeScript)")["repo"] == "punkpeye/fastmcp"
        assert resolve("fastmcp-typescript")["repo"] == "punkpeye/fastmcp"
        assert resolve("only-npm")["repo"] == "o/only-npm"  # package-only still resolves


def test_verify_endpoint_uses_the_same_resolution(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(app, "load_data", lambda: COLLIDING)
    monkeypatch.setattr(app, "startup", lambda: None)
    monkeypatch.setattr(app, "shutdown", lambda: None)
    with TestClient(app.app, base_url="https://hvtracker.net") as c:
        r = c.get("/api/v1/mcp/verify", params={"server": "fastmcp"})
    assert r.status_code == 200
    assert r.json().get("resolved") in ("PrefectHQ/fastmcp", "prefecthq/fastmcp")
