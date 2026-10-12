"""Identifier index (trust credential v0.3 design, section 4): package URLs and
MCP registry names that evidence ties to a listing, written to
data/identifiers.json and used by the shared resolver. A package or registry
name nobody tied to the repo must not find the repo's record."""
import json

import pytest
from fastapi.testclient import TestClient

import app
import fetch_and_build as fab
import mcp_server
import mcp_trust


@pytest.mark.parametrize("text,want", [
    ("pkg:npm/left-pad", "pkg:npm/left-pad"),
    ("pkg:npm/%40Acme/Tool", "pkg:npm/%40acme/tool"),
    ("pkg:npm/@acme/tool@2.0.0", "pkg:npm/%40acme/tool"),        # unencoded scope, version dropped
    ("pkg:pypi/Acme_Tool@1.0?x=1#sub", "pkg:pypi/acme-tool"),    # qualifiers and subpath dropped
    ("PKG:PyPI/zope.interface", "pkg:pypi/zope.interface"),
    ("pkg:cargo/Shared", "pkg:cargo/Shared"),                    # cargo names keep their case
    ("pkg:npm/", None),
    ("pkg:npm/@acme/", None),
    ("acme/tool", None),
    ("npm/left-pad", None),
])
def test_parse_purl(text, want):
    assert mcp_trust.parse_purl(text) == want


def _entry(name, repo):
    return {"server": {"name": name, "description": "d", "version": "1.0.0",
                       "repository": {"url": f"https://github.com/{repo}", "source": "github"}},
            "_meta": {}}


def _row(repo, checked=(), **kw):
    row = {"repo": repo, "slug": repo.replace("/", "-"), "name": repo, "trust_score": 85.0,
           "evidence_grade": "A", "coverage_grade": "B", "rank": 3, "listing_status": "listed", **kw}
    if checked:
        row["advisories"] = {"checked": [{"ecosystem": e, "name": n, "version": "1.0.0"} for e, n in checked],
                             "found": [], "worst": None}
    return row


ROWS = [
    _row("acme/tool", [("npm", "@Acme/Tool"), ("PyPI", "acme_tool")], homepage="https://acme.example"),
    # A package id is configured, but the advisory check never tied it to the repo.
    _row("bigco/mcp", npm_package="bigco-mcp", advisories=None),
    _row("sib/one", [("crates.io", "shared")]),
    _row("sib/two", [("crates.io", "shared")]),
]


@pytest.fixture
def index(tmp_path, monkeypatch):
    snap = {"owner_sites": {"bigco": "https://bigco.io"}, "servers": [
        _entry("io.github.Acme/Tool", "acme/tool"),
        _entry("io.github.mallory/tool", "acme/tool"),   # someone else's entry for acme's repo
        _entry("io.bigco/server", "bigco/mcp"),          # tied through the owner's website
        _entry("io.github.nobody/unscored", "nobody/unscored"),
    ]}
    (tmp_path / fab.REGISTRY_SNAPSHOT).write_text(json.dumps(snap))
    (tmp_path / "data").mkdir()
    fab.build_registry_feed(str(tmp_path), str(tmp_path), ROWS)
    doc = fab.build_identifier_index(str(tmp_path), ROWS)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "_identifiers_cache", {"mtime": None, "purl": {}, "registry": {}})
    monkeypatch.setattr(app, "load_data", lambda: {"agents": ROWS})
    return tmp_path, doc


def test_index_lists_only_evidenced_identifiers(index):
    tmp_path, doc = index
    assert doc == json.loads((tmp_path / "data" / "identifiers.json").read_text())
    assert doc["identifiers"]["purl"] == {
        "pkg:cargo/shared": ["sib-one", "sib-two"],  # every listing, never a pick
        "pkg:npm/%40acme/tool": ["acme-tool"],
        "pkg:pypi/acme-tool": ["acme-tool"],
    }
    assert doc["identifiers"]["mcp-registry"] == {
        "io.bigco/server": ["bigco-mcp"],
        "io.github.Acme/Tool": ["acme-tool"],
    }
    assert doc["counts"] == {"purl": 3, "mcp-registry": 2}
    assert set(doc["evidence"]) == set(doc["identifiers"]) == {"purl", "mcp-registry"}
    # Homepage domains are a one-way claim, so they are not looked up here.
    assert "acme.example" not in json.dumps(doc)


def test_index_without_a_registry_feed_still_lists_packages(tmp_path):
    (tmp_path / "data").mkdir()
    doc = fab.build_identifier_index(str(tmp_path), ROWS)
    assert doc["counts"] == {"purl": 3, "mcp-registry": 0}


def test_resolver_finds_a_listing_by_package_url_or_registry_name(index):
    for q in ("pkg:npm/%40acme/tool", "pkg:npm/@acme/tool@2.0.0", "pkg:pypi/Acme_Tool",
              "io.github.Acme/Tool", "io.github.acme/tool"):
        assert app._resolve_registry_agent(q)["repo"] == "acme/tool", q
    assert app._resolve_registry_agent("io.bigco/server")["repo"] == "bigco/mcp"


def test_resolver_refuses_untied_and_ambiguous_identifiers(index):
    assert app._resolve_registry_agent("io.github.mallory/tool") is None
    assert app._resolve_registry_agent("pkg:npm/bigco-mcp") is None
    assert app._resolve_registry_agent("pkg:cargo/shared") is None  # two listings: no guess
    assert app._normalize_github_repo("pkg:npm/tool") is None


def test_resolver_works_without_an_index(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "_identifiers_cache", {"mtime": None, "purl": {}, "registry": {}})
    monkeypatch.setattr(app, "load_data", lambda: {"agents": ROWS})
    assert app._resolve_registry_agent("pkg:npm/%40acme/tool") is None
    assert app._resolve_registry_agent("acme/tool")["slug"] == "acme-tool"


def test_mcp_tools_and_verify_api_share_the_lookup(index, monkeypatch):
    assert mcp_server.verify_mcp_server("io.github.Acme/Tool")["resolved"] == "acme/tool"
    assert mcp_server.check_agent_trust("pkg:pypi/acme-tool")["repo"] == "acme/tool"
    assert mcp_server.check_agent_trust("io.github.mallory/tool")["tracked"] is False
    monkeypatch.setattr(app, "startup", lambda: None)
    monkeypatch.setattr(app, "shutdown", lambda: None)
    with TestClient(app.app, base_url="https://hvtracker.net") as c:
        hit = c.get("/api/v1/mcp/verify", params={"server": "pkg:npm/@acme/tool"}).json()
        miss = c.get("/api/v1/mcp/verify", params={"server": "pkg:npm/not-listed"}).json()
    assert hit["tracked"] is True and hit["resolved"] == "acme/tool"
    # An unlisted package URL is answered as "not tracked", never looked up as a GitHub repo.
    assert miss["tracked"] is False and miss["submit_url"]
