"""Compare surface v2 (master plan 2.2): capability diff rows and the
coverage caveat on the verdict."""
import fetch_and_build as fab


def _row(name="A", mcp="none", providers=None, keys=False, plugin="none",
         drift="not_applicable", coverage=None):
    return {
        "name": name,
        "coverage_grade": coverage,
        "mcp_server_support": {"status": mcp},
        "external_service_dependencies": {"providers": providers or [],
                                          "requires_api_keys": keys},
        "tool_plugin_surface": {"plugin_system": plugin},
        "package_provenance_drift": {"status": drift},
    }


def test_capability_rows_leads():
    a = _row("A", mcp="implemented", keys=True, drift="match",
             providers=["OpenAI", "Anthropic", "Redis", "Postgres"])
    b = _row("B", mcp="declared", keys=False, drift="warning", plugin="marketplace")
    rows = {r["label"]: r for r in fab.compare_capability_rows(a, b)}
    assert rows["MCP server"]["lead"] == "a"          # implemented > declared
    assert rows["Requires API keys"]["lead"] == "b"   # not needing keys wins
    assert rows["Provenance drift"]["lead"] == "a"    # match > warning
    assert rows["External providers"]["lead"] == "none"  # no winner by design
    assert rows["Plugin surface"]["lead"] == "none"
    # display shape
    assert rows["External providers"]["a"].startswith("4 — OpenAI, Anthropic, Redis")
    assert rows["External providers"]["a"].endswith("…")
    assert rows["External providers"]["b"] == "—"
    assert rows["Plugin surface"]["b"] == "marketplace"
    assert rows["MCP server"]["b"] == "Declared"


def test_capability_rows_none_safe():
    rows = fab.compare_capability_rows({"name": "X"}, {"name": "Y"})
    assert all(r["lead"] == "none" for r in rows)
    assert {r["label"] for r in rows} == {"MCP server", "External providers",
                                          "Requires API keys", "Plugin surface",
                                          "Provenance drift"}


def test_coverage_caveat_only_when_leader_is_thinner():
    lead = {"name": "Leader", "coverage_grade": "C"}
    trail = {"name": "Trailer", "coverage_grade": "A"}
    caveat = fab.compare_coverage_caveat(lead, trail)
    assert caveat is not None and "coverage C vs A" in caveat and "Leader" in caveat
    # leader with equal or better coverage: no caveat
    assert fab.compare_coverage_caveat({"name": "L", "coverage_grade": "A"},
                                       {"name": "T", "coverage_grade": "B"}) is None
    assert fab.compare_coverage_caveat({"name": "L", "coverage_grade": "B"},
                                       {"name": "T", "coverage_grade": "B"}) is None
    # missing grades: no caveat
    assert fab.compare_coverage_caveat({"name": "L"}, {"name": "T", "coverage_grade": "A"}) is None
