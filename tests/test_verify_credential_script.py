"""The public reference verifier (scripts/verify_credential.py) must stay
byte-compatible with the production signer (signing.py): same canonical
serialization, same evidence hash, and it must reject tampering, expiry,
and revocation (master plan 1.5)."""
import base64
import importlib.util
import os

import pytest

cryptography = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

import signing  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "verify_credential", os.path.join(ROOT, "scripts", "verify_credential.py"))
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


@pytest.fixture()
def signed_credential(monkeypatch):
    key = Ed25519PrivateKey.generate()
    seed_b64 = base64.b64encode(key.private_bytes_raw()).decode("ascii")
    monkeypatch.setenv("HVT_SIGNING_KEY", seed_b64)
    cred = {
        "spec": "https://hvtracker.net/spec/trust-credential/v0.2",
        "version": "0.2",
        "issuer": "hvtracker.net",
        "subject": {"repo": "acme/agent", "slug": "agent",
                    "agent_url": "https://hvtracker.net/agents/agent"},
        "methodology_version": "v4.2",
        "issued_at": "2026-07-07T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
        "trust_score": 87.5,
        "confidence": 0.9,
        "evidence_grade": "A",
        "dimensions": {"safety": 20, "identity": 18, "transparency": 17,
                       "maintenance": 16, "adoption": 16},
        "listing_status": "listed",
    }
    cred["evidence_hash"] = signing.evidence_hash(cred)
    cred["signature"] = signing.sign_credential(cred)
    assert cred["signature"], "signing must be active with the test key"
    return cred, signing.public_key_b64()


def test_script_canonicalization_matches_signer(signed_credential):
    cred, _ = signed_credential
    assert script.canonical_bytes(cred) == signing._canonical_bytes(cred)
    assert script.evidence_hash(cred) == signing.evidence_hash(cred)


def test_valid_credential_verifies(signed_credential):
    cred, pub = signed_credential
    assert script.verify(cred, pub) == []


def test_tampered_score_fails_both_checks(signed_credential):
    cred, pub = signed_credential
    cred["trust_score"] = 100.0
    failures = script.verify(cred, pub)
    assert any("signature" in f for f in failures)
    assert any("evidence_hash" in f for f in failures)


def test_expired_credential_fails(signed_credential, monkeypatch):
    cred, pub = signed_credential
    cred["expires_at"] = "2020-01-01T00:00:00Z"
    cred["signature"] = signing.sign_credential(cred)  # re-sign the past date
    failures = script.verify(cred, pub)
    assert any("expired" in f for f in failures)


def test_delisted_is_revocation(signed_credential):
    cred, pub = signed_credential
    cred["listing_status"] = "delisted"
    cred["evidence_hash"] = signing.evidence_hash(cred)
    cred["signature"] = signing.sign_credential(cred)
    failures = script.verify(cred, pub)
    assert any("revoked" in f for f in failures)


def test_null_signature_reported(signed_credential):
    cred, pub = signed_credential
    cred["signature"] = None
    failures = script.verify(cred, pub)
    assert any("null" in f for f in failures)


def test_wrong_key_fails(signed_credential):
    cred, _ = signed_credential
    other = Ed25519PrivateKey.generate()
    wrong_pub = base64.b64encode(other.public_key().public_bytes_raw()).decode()
    failures = script.verify(cred, wrong_pub)
    assert any("signature" in f for f in failures)
