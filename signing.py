"""Ed25519 signing for HVTracker trust credentials (Trust Credential v0.2).

The build signs each per-agent credential with a private key supplied via the
HVT_SIGNING_KEY env var (base64-encoded 32-byte Ed25519 seed). The matching
public key is published below and in .well-known/hvtracker.json, so any third
party can verify a credential OFFLINE without re-fetching signals.

Verification and this format are intentionally OPEN — the trust verdict is
never gated. Signing is graceful: with no key (local/dev) or no `cryptography`
installed, credentials are emitted unsigned and the build still works.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    _CRYPTO = True
except Exception:  # pragma: no cover - only when dependency is absent
    _CRYPTO = False

# Published issuer public key (base64 raw 32 bytes). Rotate via
# scripts/gen_signing_key.py (updates this constant + the Railway secret).
ISSUER_PUBLIC_KEY_B64 = "mEfivVkAEfx09O2Dm0oG8+Zbh3dEZ2UB8a6P/Fd9Tgo="

_SIG_EXCLUDED = {"signature"}
_EVIDENCE_FIELDS = (
    "subject", "methodology_version", "trust_score",
    "confidence", "evidence_grade", "dimensions", "listing_status",
)


def _canonical_bytes(cred: dict) -> bytes:
    """Deterministic serialization of a credential, excluding `signature`.

    Verifiers reconstruct the exact same bytes: JSON with sorted keys, compact
    separators, and non-ASCII preserved.
    """
    payload = {k: v for k, v in cred.items() if k not in _SIG_EXCLUDED}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def evidence_hash(cred: dict) -> str:
    """SHA-256 (hex) over the score-bearing claim fields — binds the score to
    the evidence snapshot it was computed from."""
    subset = {k: cred[k] for k in _EVIDENCE_FIELDS if k in cred}
    blob = json.dumps(subset, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_private_key():
    seed = os.environ.get("HVT_SIGNING_KEY", "").strip()
    if not seed or not _CRYPTO:
        return None
    try:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed))
    except Exception:
        return None


def public_key_b64(private_key=None) -> str | None:
    """Public key derived from the active private key (for self-check)."""
    pk = private_key or _load_private_key()
    if pk is None:
        return None
    return base64.b64encode(pk.public_key().public_bytes_raw()).decode("ascii")


def signing_enabled() -> bool:
    return _load_private_key() is not None


def sign_credential(cred: dict) -> str | None:
    """Return a base64 detached Ed25519 signature over the canonical credential,
    or None when signing is unavailable (graceful for local/dev)."""
    pk = _load_private_key()
    if pk is None:
        return None
    return base64.b64encode(pk.sign(_canonical_bytes(cred))).decode("ascii")


def verify_credential(cred: dict, signature_b64: str | None = None,
                      public_key_b64: str | None = None) -> bool:
    """Verify a credential's detached signature OFFLINE. Defaults to the
    credential's own `signature` and the published issuer key."""
    if not _CRYPTO:
        raise RuntimeError("cryptography not installed; cannot verify")
    sig = signature_b64 or cred.get("signature")
    pub = public_key_b64 or ISSUER_PUBLIC_KEY_B64
    if not sig or not pub:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(pub)).verify(
            base64.b64decode(sig), _canonical_bytes(cred)
        )
        return True
    except Exception:
        return False
