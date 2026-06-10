"""Tests for the knowledge-graph builder (Task 5.1 & 5.2)."""
import json
import os

import pytest

import fetch_and_build as fb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON = os.path.join(ROOT, "data.json")

_needs_data_json = pytest.mark.skipif(
    not os.path.isfile(DATA_JSON),
    reason="data.json not present (generated at runtime)",
)


def _load_rows():
    with open(DATA_JSON) as f:
        return json.load(f)["agents"]


@_needs_data_json
def test_build_graph_entity_and_edge_counts():
    rows = _load_rows()
    g = fb.build_graph(rows)
    projects = [e for e in g["entities"].values() if e["type"] == "project"]
    providers = [e for e in g["entities"].values() if e["type"] == "provider"]
    assert len(projects) > 200
    assert len(providers) > 10


@_needs_data_json
def test_build_graph_edge_src_exists_in_entities():
    rows = _load_rows()
    g = fb.build_graph(rows)
    entity_keys = set(g["entities"].keys())
    for edge in g["edges"]:
        assert edge["src"] in entity_keys, f"edge src {edge['src']} missing from entities"


@_needs_data_json
def test_anthropic_provider_edges():
    rows = _load_rows()
    g = fb.build_graph(rows)
    anthropic_edges = [e for e in g["edges"] if e["rel"] == "USES_PROVIDER" and e["dst"] == "provider/anthropic"]
    assert len(anthropic_edges) > 50


def test_history_snapshot_has_graph_summary(tmp_path):
    rows = [
        {
            "repo": "test-org/test-repo",
            "name": "TestRepo",
            "slug": "testrepo",
            "rank": 1,
            "trust_score": 80,
            "category": "Coding Agents",
            "external_service_dependencies": {"providers": ["Anthropic", "OpenAI"]},
            "mcp_server_support": {"status": "declared"},
            "has_provenance": True,
        },
    ]
    g = fb.build_graph(rows)
    provider_counts = {}
    for e in g["edges"]:
        if e["rel"] == "USES_PROVIDER":
            pslug = e["dst"].removeprefix("provider/")
            provider_counts[pslug] = provider_counts.get(pslug, 0) + 1
    summary = {
        "providers": provider_counts,
        "mcp_count": sum(1 for e in g["edges"] if e["rel"] == "SUPPORTS_MCP"),
        "provenance_count": sum(1 for e in g["edges"] if e["rel"] == "HAS_PROVENANCE"),
        "org_count": sum(1 for v in g["entities"].values() if v["type"] == "org"),
    }
    assert summary["providers"]["anthropic"] == 1
    assert summary["mcp_count"] == 1
    assert summary["provenance_count"] == 1
    assert summary["org_count"] == 1
