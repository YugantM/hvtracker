"""MCP-server trust verdicts (P3) — mcp_trust.py."""
import base64

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import mcp_trust
import signing

GOOD = {
    "repo": "owner/good",
    "evidence_grade": "B",
    "listing_status": "listed",
    "trust_score": 72.0,
    "trust_confidence": 0.8,
    "npm_provenance": True,
    "scorecard_score": 7.5,
    "mcp_server_support": {"status": "verified"},
    "tool_plugin_surface": {"tool_tags": ["search", "code"]},
}


def test_untracked_server_not_trusted():
    v = mcp_trust.evaluate(None, "owner/unknown")
    assert v["tracked"] is False
    assert v["trusted"] is False
    assert any("registry" in r.lower() for r in v["reasons"])


def test_trusted_good_agent():
    v = mcp_trust.evaluate(GOOD, "owner/good")
    assert v["trusted"] is True
    assert v["grade"] == "B"
    assert v["resolved"] == "owner/good"
    assert "search" in v["tool_permissions"]
    assert any("provenance present" in r.lower() for r in v["reasons"])


def test_delisted_not_trusted():
    v = mcp_trust.evaluate(dict(GOOD, listing_status="delisted"), "owner/good")
    assert v["trusted"] is False
    assert any("do not connect" in r.lower() for r in v["reasons"])


def test_low_score_or_grade_not_trusted():
    assert mcp_trust.evaluate(dict(GOOD, trust_score=20.0, evidence_grade="D"),
                              "owner/good")["trusted"] is False


def test_missing_provenance_reason():
    a = dict(GOOD)
    a.pop("npm_provenance")
    a["pypi_provenance"] = False
    v = mcp_trust.evaluate(a, "owner/good")
    assert any("no build provenance" in r.lower() for r in v["reasons"])


@pytest.fixture
def pubkey(monkeypatch):
    pk = Ed25519PrivateKey.generate()
    monkeypatch.setenv("HVT_SIGNING_KEY",
                       base64.b64encode(pk.private_bytes_raw()).decode())
    return base64.b64encode(pk.public_key().public_bytes_raw()).decode()


def test_attestation_signs_and_tamper_fails(pubkey):
    att = mcp_trust.build_attestation(mcp_trust.evaluate(GOOD, "owner/good"))
    assert att["signature"]
    assert att["subject"]["mcp_server"] == "owner/good"
    assert signing.verify_credential(att, public_key_b64=pubkey) is True
    att["trusted"] = not att["trusted"]  # forge the verdict
    assert signing.verify_credential(att, public_key_b64=pubkey) is False
