"""MCP registry feed (Phase 9): official registry entries for scored repos,
re-served as v0.1 subregistries with HVTrust in server._meta, and grade-filtered
allowlists that never lend a repo's grade to an entry someone else published."""
import json
import os

import pytest
from fastapi.testclient import TestClient

import fetch_and_build as fab

OFFICIAL = {"io.modelcontextprotocol.registry/official": {
    "status": "active", "updatedAt": "2026-09-20T10:00:00.123456Z", "isLatest": True}}


def _entry(name, repo, version="1.0.0"):
    return {"server": {"name": name, "description": "d", "version": version,
                       "repository": {"url": f"https://github.com/{repo}", "source": "github"},
                       "_meta": {"io.modelcontextprotocol.registry/publisher-provided": {"x": 1}}},
            "_meta": OFFICIAL}


def _row(repo, grade="A", score=85.0, **kw):
    return {"repo": repo, "slug": repo.split("/")[1], "trust_score": score, "evidence_grade": grade,
            "coverage_grade": "B", "rank": 3, "listing_status": "listed", **kw}


@pytest.mark.parametrize("name,repo,row,site,want", [
    ("io.github.acme/tool", "acme/tool", {"repo": "acme/tool"}, "", "github-namespace-owner"),
    ("io.github.mallory/tool", "acme/tool", {"repo": "acme/tool"}, "", None),
    ("com.acme/tool", "acme/tool", {"repo": "acme/tool", "homepage": "https://docs.acme.com/x"}, "",
     "domain-homepage"),
    ("io.aiven/mcp", "aiven-open/mcp", {"repo": "Aiven-Open/mcp"}, "aiven.io/open-source", "domain-owner-website"),
    ("ai.smithery/brave", "brave/search", {"repo": "brave/search"}, "https://brave.com", None),
    ("com.evilacme/tool", "acme/tool", {"repo": "acme/tool"}, "https://acme.com", None),
])
def test_publisher_check(name, repo, row, site, want):
    assert fab.registry_publisher_check(name, repo, row, site) == want


@pytest.fixture
def feed(tmp_path, monkeypatch):
    snap = {"pulled_at": "2026-10-01T03:30:00Z", "owner_sites": {"bigco": "https://bigco.io"}, "servers": [
        _entry("io.github.acme/tool", "acme/tool"),
        _entry("io.github.mallory/tool", "acme/tool"),           # someone else's entry for acme's repo
        _entry("io.bigco/server", "bigco/mcp"),                  # tied through the owner's website
        _entry("io.github.newco/thing", "oldco/thing"),          # repo renamed on the roster
        _entry("io.github.pend/x", "pend/x"),                    # provisional row
        _entry("io.github.flag/y", "flag/y"),                    # open review flag
        _entry("io.github.cee/z", "cee/z"),                      # Grade C
        _entry("io.github.nobody/unscored", "nobody/unscored"),  # not on the board
    ]}
    (tmp_path / fab.REGISTRY_SNAPSHOT).write_text(json.dumps(snap))
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(fab, "REPO_RENAMES", {"oldco/thing": "newco/thing"})
    rows = [_row("acme/tool"), _row("bigco/mcp", "B", 70.0), _row("newco/thing"),
            _row("pend/x", pending_signals=True), _row("flag/y", listing_status="warning"),
            _row("cee/z", "C", 55.0, advisories={"found": [{}], "worst": "HIGH"})]
    assert fab.build_registry_feed(str(tmp_path), str(tmp_path), rows) == 7
    doc = json.loads((tmp_path / "data" / "registry.json").read_text())
    return tmp_path, {e["name"]: e for e in doc["entries"]}


def test_policies_and_trust_meta(feed):
    _, by = feed
    assert by["io.github.acme/tool"]["policies"] == ["all", "grade-a", "grade-b", "grade-c"]
    assert by["io.github.mallory/tool"]["policies"] == ["all"]
    assert by["io.bigco/server"]["policies"] == ["all", "grade-b", "grade-c"]
    assert by["io.github.newco/thing"]["policies"] == ["all", "grade-a", "grade-b", "grade-c"]
    assert by["io.github.pend/x"]["policies"] == ["all"]
    assert by["io.github.flag/y"]["policies"] == ["all"]
    assert by["io.github.cee/z"]["policies"] == ["all", "grade-c"]
    assert "io.github.nobody/unscored" not in by
    server = by["io.github.acme/tool"]["entry"]["server"]
    trust = server["_meta"][fab.REGISTRY_META_KEY]
    assert trust["trust_score"] == 85.0 and trust["grade"] == "A" and trust["publisher_verified"] is True
    assert trust["profile"] == "https://hvtracker.net/agents/tool/"
    # The official entry is otherwise untouched: publisher meta and wrapper meta survive.
    assert server["_meta"]["io.modelcontextprotocol.registry/publisher-provided"] == {"x": 1}
    assert by["io.github.acme/tool"]["entry"]["_meta"] == OFFICIAL
    pend = by["io.github.pend/x"]["entry"]["server"]["_meta"][fab.REGISTRY_META_KEY]
    assert pend["provisional"] is True and pend["trust_score"] is None and pend["grade"] is None
    assert by["io.github.cee/z"]["entry"]["server"]["_meta"][fab.REGISTRY_META_KEY]["known_advisory"] == "HIGH"


@pytest.fixture
def client(feed, monkeypatch):
    import app
    monkeypatch.setattr(app, "OUTPUT_DIR", str(feed[0]))
    monkeypatch.setattr(app, "_registry_cache", {"mtime": None, "doc": None})
    return TestClient(app.app)


def test_list_paginates_with_cors(client):
    r = client.get("/registry/all/v0.1/servers?limit=3")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "*"
    assert "GET" in r.headers["access-control-allow-methods"]
    body = r.json()
    assert [s["server"]["name"] for s in body["servers"]] == [
        "io.bigco/server", "io.github.acme/tool", "io.github.cee/z"]
    assert body["metadata"] == {"count": 3, "nextCursor": "io.github.cee/z"}
    nxt = client.get(f"/registry/all/v0.1/servers?limit=100&cursor={body['metadata']['nextCursor']}").json()
    assert nxt["metadata"] == {"count": 4} and nxt["servers"][0]["server"]["name"] == "io.github.flag/y"


def test_graded_list_search_and_filters(client):
    names = [s["server"]["name"] for s in client.get("/registry/grade-b/v0.1/servers").json()["servers"]]
    assert names == ["io.bigco/server", "io.github.acme/tool", "io.github.newco/thing"]
    assert client.get("/registry/grade-a/v0.1/servers?search=ACME").json()["metadata"]["count"] == 1
    assert client.get("/registry/all/v0.1/servers?updated_since=2026-09-21T00:00:00Z").json()["metadata"]["count"] == 0
    assert client.get("/registry/all/v0.1/servers?updated_since=nope").status_code == 400
    assert client.get("/registry/grade-z/v0.1/servers").status_code == 404


def test_single_server_endpoints(client):
    r = client.get("/registry/grade-a/v0.1/servers/io.github.acme%2Ftool/versions/latest")
    assert r.status_code == 200 and r.json()["server"]["name"] == "io.github.acme/tool"
    assert client.get("/registry/grade-a/v0.1/servers/io.github.acme%2Ftool/versions/1.0.0").status_code == 200
    assert client.get("/registry/grade-a/v0.1/servers/io.github.acme%2Ftool/versions/0.9.0").status_code == 404
    # Someone else's entry for the same repo is in `all` but not in an allowlist.
    assert client.get("/registry/all/v0.1/servers/io.github.mallory%2Ftool/versions/latest").status_code == 200
    assert client.get("/registry/grade-a/v0.1/servers/io.github.mallory%2Ftool/versions/latest").status_code == 404
    versions = client.get("/registry/all/v0.1/servers/io.github.acme%2Ftool/versions").json()
    assert versions["metadata"]["count"] == 1


def test_preflight_and_guide(client):
    r = client.options("/registry/grade-b/v0.1/servers")
    assert r.status_code == 204 and r.headers["access-control-allow-headers"] == "Authorization, Content-Type"
    page = client.get("/registry/")
    assert page.status_code == 200 and "https://hvtracker.net/registry/grade-b" in page.text


def test_no_snapshot_writes_nothing(tmp_path):
    assert fab.build_registry_feed(str(tmp_path), str(tmp_path), []) == 0
    assert not os.path.exists(tmp_path / "data" / "registry.json")
