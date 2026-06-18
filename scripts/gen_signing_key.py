"""Generate (or rotate) the HVTracker Ed25519 issuer signing key.

Usage:
    python scripts/gen_signing_key.py

Prints the PUBLIC key (safe to publish) and writes the PRIVATE seed to a
0600 temp file. Never commit the private seed. To provision:

    1. Paste the public key into signing.py (ISSUER_PUBLIC_KEY_B64) and
       .well-known/hvtracker.json ("public_key").
    2. Set the private seed as the Railway secret HVT_SIGNING_KEY:
         railway variables --set HVT_SIGNING_KEY="$(cat <tmpfile>)" \
           --service web --environment production
    3. Delete the temp file. Rotating the key invalidates older signatures
       (consumers re-fetch and re-verify against the new public key).
"""
import base64
import os
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

pk = Ed25519PrivateKey.generate()
seed = base64.b64encode(pk.private_bytes_raw()).decode()
pub = base64.b64encode(pk.public_key().public_bytes_raw()).decode()

fd, path = tempfile.mkstemp(prefix="hvt_signing_key_", suffix=".txt")
with os.fdopen(fd, "w") as f:
    f.write(seed)
os.chmod(path, 0o600)

print("PUBLIC KEY (publish in signing.py + .well-known/hvtracker.json):")
print(f"  {pub}")
print(f"\nPRIVATE seed written to: {path}")
print("Set it as the Railway secret HVT_SIGNING_KEY, then delete the file.")
