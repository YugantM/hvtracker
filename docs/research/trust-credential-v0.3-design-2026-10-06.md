# Trust credential v0.3: an HVTrust record bound to the identities agents present

**Date:** 2026-10-06, revised 2026-10-12
**Status:** Approved by the owner on 2026-10-12 (all four decisions, with the five review changes listed below). No code yet (Q4 plan G2/G3, "public commitment").
**Plan:** https://claude.ai/artifact/89TFKpJfa8ce92uKowefQk

## Summary

- **v0.2 can't be extended in place.** The published spec says versions "MUST NOT be modified after publication", and its subject is a GitHub repo and slug, which is not an identity an A2A or MCP client ever sees. So G2's identifiers belong in a v0.3.
- **The standards leave one role open for us, and it's the credit-bureau one.** The AI Catalog's only interoperable signed Trust Manifest is signed by the artifact's *own publisher*. A third party appears as an entry in `attestations[]`. A2A Agent Cards are signed by their own domain, and an `AgentExtension` lets a publisher point at anything. Neither standard lets us sign someone else's artifact, and we shouldn't try.
- **Design:** issue each HVTrust record as a W3C Verifiable Credential 2.0 signed as a JWT by `did:web:hvtracker.net`. The subject is named by evidenced identifiers (repo, package URLs, MCP registry names, repo-declared domain), with a 7-day validity. Publish an identifier index so a client can find a record from a package or registry name it already holds. Define two small Draft profiles: an A2A extension and an AI Catalog attestation type. Everything is a static file: no runtime service, one new key.

## Review changes (2026-10-12)

The owner's review checked the proposal against the live code, the published standards, the F1 study's 7 Oct run and the live board. Five things changed:

1. **No Agent Card identifier in v0.3.** Most cards on our listings' homepages describe a documentation assistant, not the listed product (section 2).
2. **Domains stay out of the lookup index**, and the index maps each identifier to a list of listings (section 4).
3. **No status list in v0.3.** A record is checked by fetching it (section 3).
4. **A published vocabulary file** defines the credential's own terms (section 1).
5. **The A2A profile accepts an HTTPS-fetched card**, not only a signed one (section 5).

## Where we are (v0.2)

| | v0.2 today |
|---|---|
| Location | `/data/agents/<slug>.json` → `trust_credential` |
| Subject | `{repo, slug, agent_url}` |
| Canonical form | our own: sorted keys, `(",",":")`, `ensure_ascii=false` |
| Signature | detached Ed25519, base64, key in `/.well-known/hvtracker.json` |
| Validity | `issued_at`, `expires_at` (+7 days) |
| Revocation | `listing_status: delisted` inside the credential; a delisted listing's record returns 404 |
| Verifier | `scripts/verify_credential.py` (bespoke) |
| Use | measured since 7 Oct by the `agent_records` channel (#343): about 1,000 fetches in the first five days. Crawlers and verifiers can't be told apart. |

A consumer has to implement our bespoke verifier, and even then the record only names a repo. An A2A client holding an Agent Card from `agents.example.com` has no way to connect the two.

## What the standards allow (October 2026)

**A2A 1.0.** Agent Cards are signed with JWS over the RFC 8785 canonical card, with the key named by `kid`/`jku` (spec section 8.4). That authenticates the *domain*. `AgentCapabilities.extensions[]` takes `{uri, description, required, params}`, which is the hook for a publisher to declare an external record.

**AI Catalog** (`/.well-known/ai-catalog.json`, Agent-Card/ai-catalog). Entries can carry a Trust Manifest with `identity`, `attestations[{type, uri, digest}]`, `provenance` and a detached-JWS `signature`. The only interoperable signing profile is the **did:web Publisher Profile**: the issuer must be the root `did:web` of the publisher domain, signing with ES256. Delegated issuers "require separate profiles". Third-party evidence goes in `attestations`, where `digest` is optional and "verification semantics come from the attestation's format or an applicable attestation profile". The spec warns that attestations have no built-in expiry ("Stale Attestations"). It is still changing: 24 decision records so far, the latest commit on 8 Oct 2026.

**MCP server cards** (SEP-2127, merged). Hosted at `<streamable-http-url>/server-card` and listable from an AI Catalog.

**W3C.** Verifiable Credentials Data Model 2.0, Bitstring Status List v1.0 and Securing Verifiable Credentials using JOSE and COSE all became Recommendations on 15 May 2025. The JWT media type is `application/vc+jwt`.

## What the evidence shows

**F1 study, 7 Oct run** (`a2a-card-study.json` on the `data` branch):

- 18,155 hosts probed, 17,263 reachable. 1,850 serve an Agent Card (10.7%), 605 of them valid v1.0.
- 75 cards are signed and 48 verify. Algorithms: ES256 43, EdDSA 28, RS256 2, ES256K 1, one with none named.
- 696 hosts serve an AI Catalog. 122 carry Trust Manifests, 11 of them signed. 37 carry any attestation, and the types are free-form (`https-origin`, `publisher-identity`, `privacy-policy`, one third-party scanner).
- **Our listings:** 732 homepage hosts, 51 serve a card, none signed. At least 32 of those cards are documentation-site assistants (protocol 0.3, one skill, for example "Docs by LangChain" on docs.langchain.com), not the listed product. 17 serve an AI Catalog, 3 with Trust Manifests, none signed.

**Live board, 12 Oct:** 1,012 of 1,742 listings declare an external homepage, on 950 hosts. 155 are on shared platforms (github.io 127, vercel.app 9, arxiv.org 8). 36 hosts are shared by two or more listings (98 listings).

**Demand:** MCP tools answered 193 calls in the last seven days (13 `check_agent_trust`, no `verify_mcp_server`). Lookups by package and registry name have an audience today. The A2A profile has none among our listings yet.

## Design

### 1. Envelope: VC 2.0 as a JWT, issued by did:web:hvtracker.net

- `/.well-known/did.json` publishes the issuer DID document with an **ES256** verification key. The AI Catalog's did:web profile requires ES256 of publishers, so its consumers already verify ES256 over did:web, and it is the most common algorithm on signed Agent Cards (43 of 75). Reusing the Ed25519 key with EdDSA would also work (28 of 75 signed cards use it) and stays the fallback. The Ed25519 key keeps signing v0.2.
- Each record is an `application/vc+jwt` at `/data/agents/<slug>.jwt` (about 1.5 KB). Any VC library verifies the signature with no HVTracker code.
- The credential's `@context` is the W3C v2 context followed by our own, published once and never changed, at `/spec/trust-credential/v0.3/context.jsonld`. It defines `identifiers`, `trustScore` and the other terms below. The W3C base context has no default vocabulary, so a credential with undefined terms would not conform.
- v0.2 JSON keeps being issued unchanged alongside until 2027-03-31. Before stopping it, compare `.json` and `.jwt` fetches on the `agent_records` channel. The v0.2 page stays as published.

### 2. Subject: evidenced identifiers (G2)

Illustrative values:

```json
"credentialSubject": {
  "id": "https://hvtracker.net/agents/composio",
  "identifiers": [
    {"type": "repo",         "value": "https://github.com/composiohq/composio",  "evidence": "listing"},
    {"type": "purl",         "value": "pkg:pypi/composio-core",                 "evidence": "package links to repo"},
    {"type": "mcp-registry", "value": "io.github.composiohq/composio",           "evidence": "publisher-tie rule"},
    {"type": "domain",       "value": "composio.dev",                           "evidence": "repo-declared"}
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
| `domain` | the repo declares it as its homepage and the host isn't one that unrelated projects share. **One-way evidence**, labelled `repo-declared` | none (new label) |

**Domains.** The identifier is the full host. Hosts that many unrelated projects share are left out (arxiv.org, huggingface.co, medium.com, link shorteners such as aka.ms). An owner's own subdomain on a platform (`owner.github.io`, `project.vercel.app`) is kept as the full host. Several listings may carry the same domain.

A `domain` identifier is a claim the repo makes, and any repo can declare any homepage. It is safe to rely on only in the publisher-pointed flows of section 5, where the publisher's own card or catalog names our record and our record names the domain, so the link runs both ways.

**No Agent Card identifier in v0.3.** The proposal bound a record to any card found on the listing's homepage domain. At least 32 of the 51 such cards describe a documentation assistant, and none is signed, so that rule would bind most records to the wrong thing. The A2A profile matches on `domain` instead. Revisit when listings serve cards for the product itself; the monthly F1 run reports that.

A client must match an identifier it *already verified* (the card's domain, the registry name it installed) against this list. A record never "proves" an identity; it only says which identities our evidence covers.

### 3. Validity and revocation

- `validFrom` / `validUntil`: 7 days, as today. Short-lived records double as freshness.
- **No status list in v0.3.** Every flow here fetches the record from hvtracker.net by URL, so a record is checked by fetching it: a delisted listing's record returns 404, as the v0.2 JSON does today, and a corrected record replaces the old one in place. Clients should fetch the record when they use it and honour its cache headers, not keep copies.
- A Bitstring Status List needs a second signed credential, a permanent per-listing index and a 16 KB minimum list. It is deferred until someone holds copies we can't replace, for example if publishers inline the JWT as a `data:` URI. The AI Catalog spec prefers inline attestations, but a 7-day record makes that impractical.

### 4. Finding a record without the publisher's help

- `/data/identifiers.json`: maps every `purl` and `mcp-registry` identifier to a **list** of listing slugs, cached by Cloudflare. A client holding only a registry name or a purl needs one GET.
- **Domains are not in the index.** A lookup by domain would return whichever repos declared that domain, including repos that have nothing to do with the site. Domains are matched only inside a record the publisher pointed at.
- The MCP tools (`check_agent_trust`, `verify_mcp_server`) and `/api/v1/mcp/verify` gain the same lookups and return the JWT URL.

### 5. Two small profiles, so publishers can point at their record

Both are published as **Draft**.

- **A2A extension** `https://hvtracker.net/spec/a2a-hvtrust/v0.1`: `{"uri": "…/a2a-hvtrust/v0.1", "required": false, "params": {"credential": "https://hvtracker.net/data/agents/<slug>.jwt"}}`. Client steps:
  1. Establish the card's domain. Either the card was fetched over HTTPS from that domain's well-known path, or its signature verifies against a key from that domain (A2A 8.4). Only 75 of 1,850 public cards are signed, so a signature can't be required.
  2. Fetch the JWT and verify it against `did:web:hvtracker.net`.
  3. Require a `domain` identifier equal to the card's domain.
  4. Check `validUntil`.

  `required` must be false: our record informs a decision, and must never gate the protocol.
- **AI Catalog attestation type** `https://hvtracker.net/spec/trust-credential/v0.3`. A publisher adds `{"type": "<that URI>", "uri": "…/<slug>.jwt", "description": "HVTrust independent supply-chain record"}` to its own Trust Manifest. Omit `digest`, because the record rotates weekly. The JWT carries its own integrity and validity, which also answers the spec's stale-attestation warning. The consumer matches the catalog's host against a `domain` identifier. Fetching the record tells us that someone verified it; we count only the channel and the hour, as `/api/v1/usage` documents.

### 6. What it costs

Static files only: about 1,742 JWTs (≈2.6 MB), the index, `did.json` and the context file. A few seconds of render time; nothing always-on, no new Railway cost. **One owner action:** generate the ES256 key and set it as a Railway secret (like `HVT_SIGNING_KEY`).

## What this does not do

- **Authenticate agents.** The card's own domain, its JWS or the registry does that; we consume their result.
- **Sign anyone's artifact or Trust Manifest.** That's the publisher's role under both standards.
- **Gate a protocol.** The extension is optional, and a client that ignores it loses nothing.

## Decisions (owner, 2026-10-12)

1. **Envelope and key:** VC 2.0 JWT, issuer `did:web:hvtracker.net`, a new ES256 key. Approved.
2. **v0.2 overlap:** issue both until 2027-03-31, then stop issuing v0.2 after checking the fetch split. Its page stays. Approved.
3. **Domain identifiers from repo homepages:** in the credential, labelled `repo-declared`; not in the lookup index. Approved.
4. **Profiles:** publish both as Draft with the spec. Approved.

## Build order

1. G2a: `/data/identifiers.json` (package and registry names) and the lookups in the MCP tools and verify API. This is a new file, so no spec change, and it's useful for MCP clients today.
2. G3: `did.json`, the context file, the per-agent JWTs, spec v0.3, `verify_credential.py --jwt`, and tests (round-trip with a standard JOSE verifier). Needs the ES256 key first.
3. The two profiles, as Draft pages under `/spec/`.

Usage is measured by the `agent_records` channel (#343); extend it to count `.jwt` fetches.
