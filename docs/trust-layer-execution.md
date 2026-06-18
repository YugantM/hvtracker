# Trust-Layer Execution Tracker

Executing `~/.claude/plans/i-need-you-to-atomic-leaf.md`. Branch per phase off `main`; one PR each. Worked in an isolated git worktree so codex's branch is never touched.

**Guardrail:** verification + methodology + attestation format stay OPEN. Monetize operations/scale/privacy only — never the verdict.

## P1 — Signed verifiable attestation ✅ (this branch: `trust-layer-p1`)
- [x] Ed25519 issuer keypair generated. Public key published; private seed handed off (NOT committed).
- [x] `signing.py` — canonicalize / `sign_credential` / `verify_credential` / `evidence_hash`; reads `HVT_SIGNING_KEY`; graceful no-key + no-`cryptography` fallback.
- [x] `cryptography>=43,<45` added to `requirements.txt`.
- [x] Credential bumped to **v0.2** in `fetch_and_build.py` (adds `expires_at`, `evidence_hash`, real `signature`).
- [x] `.well-known/hvtracker.json` → `signed:true`, Ed25519, public key + canonicalization rule.
- [x] Spec `trust-credential` v0.1→**v0.2** in `specs.py` (Signing now active).
- [x] `scripts/gen_signing_key.py` (rotation). Tests `tests/test_signing.py` (6, green).
- [ ] **OWNER ACTION before deploy:** set Railway secret `HVT_SIGNING_KEY` to the seed in `/tmp/hvt_signing_key.txt`, then delete the file. Without it, credentials emit `signature:null` (still valid, verified by reproduction).
- [ ] Deploy via clean-worktree `railway up` (see `[[deploy-mechanism]]`); confirm a live `/data/agents/<slug>.json` `signature` verifies against the `.well-known` key.

## Next (not started)
- **P3** MCP-server trust (beachhead 1) · **P7 ∥** billing rail (accounts/keys/metering/Stripe; interim = manual enterprise pilots) · **P2** open lookup · **P4** A2A AgentCard field · **P5** verify+policy API · **P6** transparency log.

## Resume notes
- Repo is code-only; don't re-commit generated artifacts. Each phase = own branch + PR off latest `main`.
- Do NOT touch the `codex/*` branches or their working-tree WIP.
