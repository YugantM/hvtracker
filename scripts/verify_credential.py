#!/usr/bin/env python3
"""Verify an HVTracker trust credential yourself — no trust in us required.

Standalone on purpose: copy this single file anywhere. Needs Python 3.10+
and `pip install cryptography`. Spec: https://hvtracker.net/spec/trust-credential/v0.2

Usage:
    python3 verify_credential.py <agent-slug>          # fetch + verify live
    python3 verify_credential.py --file cred.json      # verify a saved credential
                                                       # (offline; uses --key or the pinned fallback)
"""
import argparse
import base64
import hashlib
import json
import ssl
import sys
import urllib.request
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

try:  # some Python installs (notably python.org macOS) lack system CAs
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

WELL_KNOWN = "https://hvtracker.net/.well-known/hvtracker.json"
AGENT_URL = "https://hvtracker.net/data/agents/{slug}.json"
# Issuer key at time of writing — the current key is always published at
# WELL_KNOWN under trust_credential.public_key; prefer fetching it.
FALLBACK_KEY_B64 = "mEfivVkAEfx09O2Dm0oG8+Zbh3dEZ2UB8a6P/Fd9Tgo="
EVIDENCE_FIELDS = ("subject", "methodology_version", "trust_score",
                   "confidence", "evidence_grade", "dimensions", "listing_status")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "hvt-verify/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        return json.load(resp)


def canonical_bytes(cred: dict) -> bytes:
    """The exact bytes the issuer signed: credential minus `signature`,
    JSON with sorted keys, compact separators, non-ASCII preserved."""
    payload = {k: v for k, v in cred.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def evidence_hash(cred: dict) -> str:
    subset = {k: cred[k] for k in EVIDENCE_FIELDS if k in cred}
    blob = json.dumps(subset, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def verify(cred: dict, public_key_b64: str) -> list[str]:
    """Return a list of failures; empty list means the credential is good."""
    failures = []
    sig = cred.get("signature")
    if not sig:
        failures.append("signature is null — issuing build had no key; "
                        "verify by score reproduction instead (spec §5)")
        return failures
    try:
        Ed25519PublicKey.from_public_bytes(
            base64.b64decode(public_key_b64)
        ).verify(base64.b64decode(sig), canonical_bytes(cred))
    except Exception:
        failures.append("Ed25519 signature does NOT verify — credential altered or wrong key")
    if cred.get("evidence_hash") and evidence_hash(cred) != cred["evidence_hash"]:
        failures.append("evidence_hash mismatch — score-bearing fields were altered")
    expires = cred.get("expires_at")
    if expires:
        try:
            if datetime.fromisoformat(expires.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                failures.append(f"credential expired at {expires} — fetch a fresh one")
        except ValueError:
            failures.append(f"unparseable expires_at: {expires!r}")
    if cred.get("listing_status") == "delisted":
        failures.append("subject is delisted — treat as revoked regardless of score (spec §6)")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", help="agent slug, e.g. haystack")
    ap.add_argument("--file", help="path to a saved credential JSON (offline)")
    ap.add_argument("--key", help="issuer public key, base64 raw 32 bytes")
    args = ap.parse_args()
    if not args.slug and not args.file:
        ap.error("give an agent slug or --file")

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            doc = json.load(f)
        cred = doc.get("trust_credential", doc)
        key = args.key or FALLBACK_KEY_B64
    else:
        cred = fetch_json(AGENT_URL.format(slug=args.slug))["trust_credential"]
        key = args.key or fetch_json(WELL_KNOWN)["trust_credential"]["public_key"]

    failures = verify(cred, key)
    subject = (cred.get("subject") or {}).get("repo", "?")
    if failures:
        print(f"FAIL: {subject}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {subject} — trust_score {cred.get('trust_score')} "
          f"(grade {cred.get('evidence_grade')}, confidence {cred.get('confidence')}), "
          f"signed by hvtracker.net, valid until {cred.get('expires_at')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
