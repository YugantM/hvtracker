"""Locks /spec/runtime-trust (T3.2) to the code it documents.

The spec's §4 adjustment table must mirror compute_trust_score_v2 exactly —
"the verdict stays open" only holds if the published numbers are the real ones.
If the constants in fetch_and_build.py change, this fails until the spec (and
its version) are updated to match.
"""
import json
import os

import fetch_and_build as fb
import specs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPEC = next(s for s in specs.ALL_SPECS if s["slug"] == "runtime-trust")


def test_spec_registered_and_shaped():
    for key in ("title", "version", "date", "status", "abstract", "sections", "body"):
        assert SPEC.get(key), f"runtime-trust spec missing {key}"
    assert SPEC["status"] == "Draft"  # bump deliberately when promoted


def test_spec_documents_all_four_dimensions():
    body = SPEC["body"]
    for field in ("mcp_server_support", "external_service_dependencies",
                  "tool_plugin_surface", "package_provenance_drift"):
        assert field in body, f"spec body missing runtime field {field}"


def test_adjustment_table_matches_code():
    """Recompute known cases through compute_trust_score_v2 and assert the
    spec's published constants appear in the body."""
    # mcp: implemented +2.0, declared +1.0
    up = fb.compute_trust_score_v2({"trust_score": 50,
                                    "mcp_server_support": {"status": "implemented"}})
    assert up["trust_v2_breakdown"]["mcp"] == 2.0
    # drift: match +4.0, warning -5.0
    match = fb.compute_trust_score_v2({"trust_score": 50,
                                       "package_provenance_drift": {"status": "match"}})
    warn = fb.compute_trust_score_v2({"trust_score": 50,
                                      "package_provenance_drift": {"status": "warning"}})
    assert match["trust_v2_breakdown"]["package_provenance_drift"] == 4.0
    assert warn["trust_v2_breakdown"]["package_provenance_drift"] == -5.0
    # ext deps: cap -3.0 plus -1.0 for api keys
    deps = fb.compute_trust_score_v2({"trust_score": 50,
                                      "external_service_dependencies":
                                      {"providers": list("abcdefghij"), "requires_api_keys": True}})
    assert deps["trust_v2_breakdown"]["external_dependencies"] == -4.0

    body = SPEC["body"]
    for constant in ("+2.0", "+1.0", "+4.0", "&minus;5.0", "&minus;3.0",
                     "&minus;1.5", "&minus;0.3"):
        assert constant in body, f"spec body missing documented constant {constant}"


def test_advertised_in_well_known():
    with open(os.path.join(ROOT, ".well-known", "hvtracker.json")) as f:
        wk = json.load(f)
    assert wk["specs"]["runtime_trust"] == "https://hvtracker.net/spec/runtime-trust/v0.1"
