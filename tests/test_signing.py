"""Trust Credential v0.2 signing/verification (signing.py)."""
import base64

import pytest

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import signing


def _sample_cred():
    return {
        "spec": "https://hvtracker.net/spec/trust-credential/v0.2",
        "version": "0.2",
        "issuer": "hvtracker.net",
        "subject": {"repo": "owner/name", "slug": "name",
                    "agent_url": "https://hvtracker.net/agents/name"},
        "methodology_version": "v3.2",
        "issued_at": "2026-06-18T00:00:00Z",
        "expires_at": "2026-06-25T00:00:00Z",
        "trust_score": 84.2,
        "confidence": 0.8,
        "evidence_grade": "B",
        "dimensions": {"safety": 18.0, "adoption": 16.0},
        "listing_status": "listed",
    }


@pytest.fixture
def pubkey(monkeypatch):
    """Provision an ephemeral signing key via the env var the module reads."""
    pk = Ed25519PrivateKey.generate()
    monkeypatch.setenv("HVT_SIGNING_KEY",
                       base64.b64encode(pk.private_bytes_raw()).decode())
    return base64.b64encode(pk.public_key().public_bytes_raw()).decode()


def _signed(cred):
    cred["evidence_hash"] = signing.evidence_hash(cred)
    cred["signature"] = signing.sign_credential(cred)
    return cred


def test_sign_verify_roundtrip(pubkey):
    cred = _signed(_sample_cred())
    assert cred["signature"]
    assert signing.verify_credential(cred, public_key_b64=pubkey) is True


def test_tampered_credential_fails(pubkey):
    cred = _signed(_sample_cred())
    cred["trust_score"] = 99.9  # forge a higher score
    assert signing.verify_credential(cred, public_key_b64=pubkey) is False


def test_tampered_dimension_fails(pubkey):
    cred = _signed(_sample_cred())
    cred["dimensions"]["safety"] = 25.0
    assert signing.verify_credential(cred, public_key_b64=pubkey) is False


def test_unsigned_without_key(monkeypatch):
    monkeypatch.delenv("HVT_SIGNING_KEY", raising=False)
    assert signing.sign_credential(_sample_cred()) is None


def test_evidence_hash_is_stable_and_sensitive():
    a, b = _sample_cred(), _sample_cred()
    assert signing.evidence_hash(a) == signing.evidence_hash(b)
    b["trust_score"] = 1.0
    assert signing.evidence_hash(a) != signing.evidence_hash(b)


def test_published_pubkey_wellformed():
    assert len(base64.b64decode(signing.ISSUER_PUBLIC_KEY_B64)) == 32
