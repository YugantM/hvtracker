# Trust credential v0.3: an HVTrust record bound to the identities agents present

**Date:** 2026-10-06
**Status:** Proposed. Needs an owner decision before any code (Q4 plan G2/G3, "public commitment").
**Plan:** https://claude.ai/artifact/89TFKpJfa8ce92uKowefQk

## Summary

- **v0.2 can't be extended in place.** The published spec says versions "MUST NOT be modified after publication", and its subject is a GitHub repo and slug, which is not an identity an A2A or MCP client ever sees. So G2's identifiers belong in a v0.3.
- **The standards leave one role open for us, and it's the credit-bureau one.** The AI Catalog's only interoperable signed Trust Manifest is signed by the artifact's *own publisher*. A third party appears as an entry in `attestations[]` ("verify per its type"). A2A Agent Cards are signed by their own domain, and an `AgentExtension` lets a publisher point at anything. Neither standard lets us sign someone else's artifact, and we shouldn't try.
- **Proposal:** issue each HVTrust record as a W3C Verifiable Credential 2.0 signed as a JWT by `did:web:hvtracker.net`. The subject is named by evidenced identifiers (repo, package URLs, MCP registry names, domain, Agent Card URL), with a 7-day validity and a Bitstring Status List for revocation. Publish an identifier index so a client can find a record from what it already holds. Define two small profiles: an A2A extension and an AI Catalog attestation type. Everything is a static file: no runtime service, one new key.

## Where we are (v0.2)

| | v0.2 today |
|---|---|
| Location | `/data/agents/<slug>.json` → `trust_credential` |
| Subject | `{repo, slug, agent_url}` |
| Canonical form | our own: sorted keys, `(",",":")`, `ensure_ascii=false` |
| Signature | detached Ed25519, base64, key in `/.well-known/hvtracker.json` |
| Validity | `issued_at`, `expires_at` (+7 days) |
| Revocation | `listing_status: delisted` inside the credential |
| Verifier | `scripts/verify_credential.py` (bespoke) |
| Use | not measured until #343 (`agent_records` channel, deployed with the next release) |

A consumer has to implement our bespoke verifier, and even then the record only names a repo. An A2A client holding a signed Agent Card from `agents.example.com` has no way to connect the two.

## What the standards allow (October 2026)

**A2A 1.0.** Agent Cards are signed with JWS over the RFC 8785 canonical card, with the key named by `kid`/`jku` (spec section 8.4). That authenticates the *domain*. `AgentCapabilities.extensions[]` takes `{uri, description, required, params}`, which is the hook for a publisher to declare an external record.

**AI Catalog** (`/.well-known/ai-catalog.json`, Agent-Card/ai-catalog). Entries can carry a Trust Manifest with `identity`, `attestations[{type, uri, digest}]`, `provenance` and a detached-JWS `signature` bound to a `subject` digest. The only interoperable signing profile is the **did:web Publisher Profile**: the issuer must be the root `did:web` of the `urn:air` publisher domain, signing with ES256. "Delegated issuers… require separate profiles." Third-party evidence goes in `attestations`, verified "per its type (e.g., verify a JWT signature)". The spec warns that attestations have no built-in expiry ("Stale Attestations").

**MCP server cards** (SEP-2127, merged). Hosted at `<streamable-http-url>/server-card` and listable from an AI Catalog.

**W3C.** Verifiable Credentials Data Model 2.0 and Bitstring Status List v1.0 became Recommendations on 15 May 2025. The JOSE/COSE securing spec belongs to the same family; check its final status before implementing.

The F1 study (#346, first run 6 Oct) will show how many public cards and catalogs actually exist, signed or not.

## Proposal

### 1. Envelope: VC 2.0 as a JWT, issued by did:web:hvtracker.net

- `/.well-known/did.json` publishes the issuer DID document with an **ES256** verification key. ES256 is what the AI Catalog's did:web profile and A2A's examples use, and the most widely supported JOSE algorithm. The Ed25519 key stays for v0.2.
- Each record is a `application/vc+jwt` at `/data/agents/<slug>.jwt` (about 1.5 KB). Any VC library verifies it with no HVTracker code.
- v0.2 JSON keeps being issued unchanged alongside, until a date you choose (suggested 2027-03-31). The v0.2 page stays as published.

### 2. Subject: evidenced identifiers (G2)

Illustrative values:

```json
"credentialSubject": {
  "id": "https://hvtracker.net/agents/composio",
  "identifiers": [
    {"type": "repo",         "value": "https://github.com/composiohq/composio",  "evidence": "listing"},
    {"type": "purl",         "value": "pkg:pypi/composio-core",                 "evidence": "package links to repo"},
    {"type": "mcp-registry", "value": "io.github.composiohq/composio",           "evidence": "publisher-tie rule"},
    {"type": "domain",       "value": "composio.dev",                           "evidence": "repo-declared homepage"},
    {"type": "a2a-card",     "value": "https://…/.well-known/agent-card.json",   "evidence": "card links back to repo"}
  ],
  "trustScore": 74.9, "evidenceGrade": "B", "coverageGrade": "A", "confidence": 0.9,
  "methodologyVersion": "v4.4", "dimensions": { … }, "listingStatus": "listed",
  "evidenceHash": "…", "history": "https://hvtracker.net/api/v1/agents/composio/history"
}
```

An identifier goes in only when the link is evidenced, using rules we already run:

| Type | Included when | Existing rule |
|---|---|---|
| `purl` (npm, pypi, cargo) | the package's metadata links to the repo, or it is the listing's only package | `package_is_the_listing()` (advisory check) |
| `mcp-registry` | the registry name passes the publisher-tie rule | Phase 9 graded feed |
| `domain` | the repo declares it as its homepage. **Weaker evidence**, labelled as such | none (new label) |
| `a2a-card` | F1 finds a card on that domain whose `provider.url` or documentation links back to the repo or homepage | new, from F1 rows |

A client must match an identifier it *already verified* (the card's signing domain, the registry name it installed) against this list. A record never "proves" an identity; it only says which identities our evidence covers.

### 3. Validity and revocation

- `validFrom` / `validUntil`: 7 days, as today. Short-lived records double as freshness.
- **Bitstring Status List** at `/data/status/hvtrust.json` (a status-list credential, regenerated each render, edge-cached). A bit is set when a listing is delisted or a correction voids a record before it expires.

### 4. Finding a record without the publisher's help

- `/data/identifiers.json`: an `{identifier: slug}` index of every identifier above, about 200 KB, cached by Cloudflare. A client holding only a card URL, a registry name or a purl needs one GET.
- The MCP tools (`check_agent_trust`, `verify_mcp_server`) and `/api/v1/mcp/verify` gain the same lookups and return the JWT URL.

### 5. Two small profiles, so publishers can point at their record

- **A2A extension** `https://hvtracker.net/spec/a2a-hvtrust/v0.1`: `{"uri": "…/a2a-hvtrust/v0.1", "required": false, "params": {"credential": "https://hvtracker.net/data/agents/<slug>.jwt"}}`. Client steps: verify the card's own signature (A2A 8.4) → fetch and verify the JWT against `did:web:hvtracker.net` → require a `domain` or `a2a-card` identifier equal to the card's signing domain or URL → check `validUntil` and the status list. `required` must be false: our record informs a decision, and must never gate the protocol.
- **AI Catalog attestation type** `https://hvtracker.net/spec/trust-credential/v0.3`. A publisher adds `{"type": "<that URI>", "uri": "…/<slug>.jwt", "description": "HVTrust independent supply-chain record"}` to its own signed Trust Manifest. Omit `digest`, because the record rotates weekly. The JWT carries its own integrity and validity, which also answers the spec's stale-attestation warning.

### 6. What it costs

Static files only: about 1,705 JWTs (≈2.5 MB), the index, the status list, `did.json`. A few seconds of render time; nothing always-on, no new Railway cost. **One owner action:** generate the ES256 key and set it as a Railway secret (like `HVT_SIGNING_KEY`).

## What this does not do

- **Authenticate agents.** The card's own JWS or the registry does that; we consume their result.
- **Sign anyone's artifact or Trust Manifest.** That's the publisher's role under both standards.
- **Gate a protocol.** The extension is optional, and a client that ignores it loses nothing.

## Decisions needed

1. **Envelope and key:** VC 2.0 JWT, issuer `did:web:hvtracker.net`, a new ES256 key (recommended). The alternative is Ed25519-only: fewer libraries, no new key.
2. **v0.2 overlap:** issue both until 2027-03-31 (recommended), then stop issuing v0.2. Its page stays.
3. **Domain identifiers from repo homepages:** include, labelled `repo-declared` (recommended), or leave them out until a two-way link is found.
4. **Profiles:** publish both as Draft with the spec (recommended, nil cost), or wait for F1's numbers.

## Suggested order once approved

1. G2a: `/data/identifiers.json` and the lookups in the MCP tools and verify API. This is a new file, so no spec change, and it's useful for MCP clients today.
2. G3: `did.json`, the per-agent JWTs, the status list, spec v0.3, `verify_credential.py --jwt`, and tests (round-trip with a standard JOSE verifier).
3. The profiles, as Draft pages under `/spec/`.

Usage is measured by the `agent_records` channel (#343); extend it to count `.jwt` fetches.
