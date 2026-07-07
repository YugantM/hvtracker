"""Capability matrix (/capabilities/, T3.3 — master plan 1.1a).

build_capability_matrix() reshapes per-row runtime fields into the hub-page
context; these tests lock the counting rules, provider slugs (must match the
ecosystem-page slugs so links resolve), rank ordering, and None-safety.
"""
import fetch_and_build as fab


def _row(slug="a", rank=1, mcp="none", providers=None, keys=False,
         plugin="none", tags=None, drift="not_applicable", **over):
    row = {
        "slug": slug,
        "name": slug.title(),
        "repo": f"org/{slug}",
        "rank": rank,
        "display_rank": rank,
        "trust_score": 80.0,
        "evidence_grade": "A",
        "mcp_server_support": {"status": mcp},
        "external_service_dependencies": {
            "providers": providers or [], "requires_api_keys": keys},
        "tool_plugin_surface": {"plugin_system": plugin, "tool_tags": tags or []},
        "package_provenance_drift": {"status": drift},
    }
    row.update(over)
    return row


def test_stats_count_each_dimension():
    rows = [
        _row("a", 1, mcp="implemented", providers=["OpenAI"], keys=True,
             plugin="marketplace", drift="match"),
        _row("b", 2, mcp="declared", providers=["OpenAI", "Anthropic"],
             plugin="extension-based", drift="warning"),
        _row("c", 3),
    ]
    stats = fab.build_capability_matrix(rows)["stats"]
    assert stats["total"] == 3
    assert stats["mcp_implemented"] == 1
    assert stats["mcp_declared"] == 1
    assert stats["requires_keys"] == 1
    assert stats["keyless"] == 1  # b has providers but needs no keys
    assert stats["marketplace"] == 1
    assert stats["extension_based"] == 1
    assert stats["drift_match"] == 1
    assert stats["drift_warning"] == 1
    assert stats["provider_count"] == 2  # OpenAI + Anthropic, deduped


def test_provider_slugs_match_ecosystem_pages():
    rows = [_row("a", 1, providers=["Amazon Bedrock", "Google Gemini"])]
    matrix = fab.build_capability_matrix(rows)
    slugs = {p["slug"] for p in matrix["agents"][0]["providers"]}
    assert slugs == {"amazon-bedrock", "google-gemini"}
    eco = fab.build_ecosystem_pages(rows)
    assert slugs == {p["slug"] for p in eco}


def test_agents_ordered_by_rank_with_none_last():
    rows = [_row("worst", 300), _row("best", 1), _row("pending", rank=None)]
    matrix = fab.build_capability_matrix(rows)
    assert [a["slug"] for a in matrix["agents"]] == ["best", "worst", "pending"]


def test_missing_runtime_fields_are_safe():
    bare = {"slug": "bare", "name": "Bare", "repo": "org/bare", "rank": 1}
    agent = fab.build_capability_matrix([bare])["agents"][0]
    assert agent["mcp_status"] == "none"
    assert agent["providers"] == []
    assert agent["plugin_system"] == "none"
    assert agent["drift_status"] == "not_applicable"
    assert agent["tool_tag_count"] == 0
