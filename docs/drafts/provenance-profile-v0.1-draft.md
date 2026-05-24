# HVTracker Provenance Profile Specification v0.1

**Status:** Draft — awaiting owner review before publication  
**Version:** v0.1  
**Date:** 2026-05-24  
**Authors:** HVTracker  
**Track:** Standards Track  

---

## 1. Abstract

This document specifies the trust signal model used by HVTracker to assess the supply chain integrity of open-source AI agent projects. It formally defines the schema, data source, collection method, freshness expectations, and failure modes for each of the four currently tracked signals: npm provenance attestations, PyPI PEP 740 attestations, OSSF Scorecard, and signed commit ratio. It also defines an extension model by which new trust signals may be incorporated in future versions of this specification.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY in this document are to be interpreted as described in RFC 2119.

This is a v0.x specification. Signals are collected and displayed but do not affect the health score defined in the Methodology Specification v2.0. Promotion to v1.0 will occur when the trust model is considered stable enough to inform scoring.

---

## 2. Motivation

Open-source AI agent projects are becoming critical infrastructure. Unlike traditional software libraries, AI agents often operate with broad system permissions — reading files, browsing the web, executing code, and calling external APIs on behalf of users. The integrity of the supply chain from which these agents are installed therefore carries higher stakes than for passive libraries.

HVTracker tracks health signals derived from project activity (stars, commits, forks). These signals measure adoption and development momentum but say nothing about whether the artifacts users install are trustworthy. A project with 50,000 stars and daily commits can still ship a compromised release if its publishing pipeline lacks attestations or its commits go unsigned.

The Provenance Profile addresses this gap. It defines a set of unilaterally observable, publicly verifiable signals that characterize the supply chain trustworthiness of a project's release artifacts. No maintainer participation, registration, or opt-in is required or assumed — all signals are derived from public cryptographic infrastructure.

The four signals defined here were chosen because they are:
- Observable without contacting maintainers
- Derived from public infrastructure that exists independently of HVTracker
- Binary or scalar (not subjective assessments)
- Already collected by the reference implementation

---

## 3. Terminology

**Trust signal:** A binary or scalar value derived from publicly observable cryptographic infrastructure that characterizes one dimension of the supply chain integrity of a software project. Trust signals are not scores and are not aggregated into a composite value in this version.

**Attestation:** A cryptographically signed statement, produced by a known identity (typically a CI/CD system), asserting facts about a software artifact — most commonly that the artifact was built from a specific source commit in a specific pipeline environment. Attestations are logged to a transparency log so they cannot be silently revoked.

**Provenance:** The verifiable record of how a software artifact was produced: which source repository, which commit, which build environment, and which pipeline. Provenance is a specific category of attestation that answers "where did this artifact come from?"

**Artifact:** A published binary or source distribution of a software package — a `.whl` file on PyPI, a tarball on npm, a Docker image layer, etc.

**Transparency log:** An append-only, cryptographically verifiable log of signed records. The primary transparency log used by npm and PyPI provenance is Sigstore's Rekor. Once a record is appended, it cannot be deleted without detection.

**Freshness:** The degree to which a trust signal reflects the current state of a project rather than a historical state. A signal is fresh if it was collected within one Daily Run of the current build. A signal is stale if the data source was unavailable and the last known value is being carried forward.

**Verified signature:** A commit signature whose cryptographic validity has been confirmed by GitHub's signature verification API. A verified signature does not imply key quality or trust level — it means the signature is mathematically valid and the signing key is recognized by GitHub.

**Trusted Publisher:** A mechanism (npm: Provenance, PyPI: OIDC Trusted Publishing) that allows a CI/CD system to publish packages using a short-lived identity token rather than a long-lived API key. Artifacts published via a Trusted Publisher are eligible for provenance attestations.

**OSSF Scorecard:** An automated tool maintained by the Open Source Security Foundation that evaluates a project's security posture across a fixed set of checks and produces a score from 0 to 10.

---

## 4. Trust Signals

### 4.1 npm Provenance

**Field name:** `npm_provenance`  
**Type:** `boolean | null`  
**Applicability:** Agents with a non-null `npm_package` field in `agents.json`.

#### 4.1.1 Schema

| Value | Meaning |
|---|---|
| `true` | The latest published version includes at least one provenance attestation in `dist.attestations`. |
| `false` | The latest published version has no provenance attestations (`dist.attestations` is absent or null). |
| `null` | No `npm_package` configured for this agent, or the API request failed. |

#### 4.1.2 Data Source

```
GET https://registry.npmjs.org/{encoded_package}/latest
```

Where `{encoded_package}` is the npm package name with `@` and `/` characters preserved (percent-encoding applied to all other special characters).

The response is a JSON object. The signal is `true` if and only if the `dist.attestations` field is present and non-null in the response body.

#### 4.1.3 Collection Method

The reference implementation calls this endpoint once per agent per Daily Run. npm does not publish a strict rate limit for anonymous reads; requests MAY be made in parallel with other npm requests.

#### 4.1.4 What a Positive Signal Means

`npm_provenance = true` means the package publisher used npm's Provenance feature, which requires publishing via a Trusted Publisher (currently: GitHub Actions, GitLab CI, or CircleCI). The resulting attestation is an in-toto SLSA provenance statement, signed via Sigstore's keyless signing protocol and logged to the Rekor transparency log.

A user installing the package can verify this attestation using `npm audit signatures` to confirm the artifact was built from the claimed source commit.

#### 4.1.5 Freshness

The signal reflects the state of the `latest` distribution tag at collection time. If a new version is published without attestations, the signal will change from `true` to `false` on the next Daily Run. Conversely, if a package migrates to Trusted Publishing, the signal will change from `false` to `true` on the next run after the new version is published.

#### 4.1.6 Failure Modes

| Condition | Observed value |
|---|---|
| npm registry returns non-200 | `null` (request failure; prior value not carried forward) |
| Package does not exist on npm | `null` |
| Network timeout (>10 seconds) | `null` |
| Package exists but has no `latest` tag | `null` |

#### 4.1.7 Limitations

- Only the `latest` distribution tag is checked. A package that publishes attestations on some versions but not others will show `true` if and only if the `latest` tag points to an attested version.
- The presence of an attestation is checked, not its content. The attestation is not cryptographically verified by the reference implementation — that step is left to end users via `npm audit signatures`.

---

### 4.2 PyPI Provenance (PEP 740)

**Field name:** `pypi_provenance`  
**Type:** `boolean | null`  
**Applicability:** Agents with a non-null `pypi_package` field in `agents.json`.

#### 4.2.1 Schema

| Value | Meaning |
|---|---|
| `true` | The last file entry in the package's Simple API response has a non-null `provenance` field. |
| `false` | The last file entry has no `provenance` field. |
| `null` | No `pypi_package` configured, or the API request returned non-200. |

#### 4.2.2 Data Source

```
GET https://pypi.org/simple/{package}/
Accept: application/vnd.pypi.simple.v1+json
```

The response is a JSON object per PEP 691. The reference implementation reads the `files` array and checks the last element's `provenance` field.

#### 4.2.3 Collection Method

Requests MUST be made serially with a minimum 1.2-second delay between PyPI requests per the Methodology Specification v2.0 (§4.3). On HTTP 429, the implementation MUST treat the signal as `null` for the current run; prior values are not carried forward.

#### 4.2.4 What a Positive Signal Means

`pypi_provenance = true` means the most recently uploaded distribution file carries a PEP 740 digital attestation. PEP 740 attestations are generated by PyPI's Trusted Publishing mechanism (GitHub Actions, GitLab CI, Google Cloud Build) and are cryptographically bound to the source repository and CI run that produced the artifact.

#### 4.2.5 Freshness

The signal reflects the last file in the Simple API response at collection time, which corresponds to the most recently uploaded distribution. If the maintainer uploads a new version without Trusted Publishing, the signal changes to `false` on the next Daily Run.

#### 4.2.6 Failure Modes

| Condition | Observed value |
|---|---|
| HTTP 429 (rate limited) | `null` |
| HTTP 404 (package not found) | `null` |
| `files` array is empty | `null` |
| Network timeout (>10 seconds) | `null` |

#### 4.2.7 Limitations

- Only the last file in the Simple API response is checked. This is typically the most recently uploaded wheel or sdist, not necessarily the latest stable release. Packages with complex upload patterns (e.g., uploading old sdists alongside new wheels) may produce unexpected results.
- PEP 740 was accepted in 2024. Packages published before Trusted Publishing was widely available will show `false` regardless of their security posture. This is a real-world limitation, not a code deficiency.
- Packages published via `twine` with API tokens cannot carry PEP 740 attestations by design.

---

### 4.3 OSSF Scorecard

**Field names:** `scorecard_score` (float | null), `scorecard_checks` (object | {})  
**Type:** `float` in range [0.0, 10.0] | `null`; `object` mapping check name to score integer  
**Applicability:** All agents. Coverage depends on upstream indexing.

#### 4.3.1 Schema

`scorecard_score`: A float in [0.0, 10.0] representing the overall Scorecard score, or `null` if unavailable.

`scorecard_checks`: A JSON object where each key is a Scorecard check name and each value is the integer score for that check (-1 if the check could not be run, 0–10 otherwise). Empty object if `scorecard_score` is null.

Known check names (non-exhaustive, as the OSSF Scorecard check set evolves):
`Maintained`, `Code-Review`, `CII-Best-Practices`, `License`, `Signed-Releases`, `Branch-Protection`, `Dangerous-Workflow`, `Token-Permissions`, `Pinned-Dependencies`, `Vulnerabilities`, `Packaging`, `SAST`, `Fuzzing`, `Security-Policy`.

#### 4.3.2 Data Sources

The reference implementation tries two sources in order:

**Primary:** deps.dev Projects API
```
GET https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}
```
The `scorecard.overallScore` field (or `scorecard.score` as a fallback) is used for `scorecard_score`. The `scorecard.checks` array is iterated to build `scorecard_checks`.

**Fallback:** OpenSSF Security Scorecards API
```
GET https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}
```
The `score` field is used for `scorecard_score`. The `checks` array is iterated to build `scorecard_checks`.

The fallback is attempted if and only if the primary source returns a non-200 status or returns a 200 with no `scorecard` field.

#### 4.3.3 Collection Method

One request per agent per Daily Run to the primary source, with fallback to the secondary source on failure. Both requests have a 15-second timeout. No rate limiting is applied; both APIs are read-only and publicly accessible.

#### 4.3.4 What the Score Means

The OSSF Scorecard score is an aggregate of 10–18 individual checks (the exact set varies by Scorecard version). Each check produces a score of 0–10 or -1 (not applicable / could not run). The overall score is a weighted average of applicable checks. A score of 10 indicates full compliance across all applicable checks; 0 indicates critical failures.

The check set and weights are defined by the OpenSSF Scorecard project, not by HVTracker. HVTracker reports the score as-is; it does not reweight or reinterpret the individual checks.

#### 4.3.5 Freshness

The score reported by deps.dev and securityscorecards.dev reflects the most recent Scorecard analysis run for the repository. The OpenSSF Scorecard project runs analyses periodically (typically weekly), not in real time. HVTracker's Daily Run may collect the same score for multiple consecutive days if no new Scorecard analysis has been completed upstream.

#### 4.3.6 Failure Modes

| Condition | Observed value |
|---|---|
| Both primary and fallback return non-200 | `null` / `{}` |
| Primary returns 200 but no `scorecard` field, fallback returns non-200 | `null` / `{}` |
| Network timeout on both sources | `null` / `{}` |
| Repository not indexed by either upstream | `null` / `{}` |

#### 4.3.7 Limitations

- Not all repositories have been indexed by the OpenSSF Scorecard infrastructure. Absence of a score does not imply poor security posture — it may simply mean the project has not been analysed yet.
- The score reflects the state of the repository at the time of the upstream Scorecard run, not at collection time. There may be a lag of up to one week between a change in the repository and a change in the reported score.
- The Scorecard check set evolves over time. A score of 7.0 in 2025 may not be directly comparable to a score of 7.0 in 2026 if new checks were added.

---

### 4.4 Signed Commit Ratio

**Field name:** `signed_commits_ratio`  
**Type:** `float` in range [0.0, 1.0] | `null`  
**Applicability:** All agents.

#### 4.4.1 Schema

| Value | Meaning |
|---|---|
| `1.0` | All sampled commits carry a verified signature. |
| `0.0` | No sampled commits carry a verified signature. |
| `0.0 < x < 1.0` | A fraction `x` of sampled commits carry a verified signature. |
| `null` | The GitHub API request failed, or the commits list is empty. |

The value is rounded to 3 decimal places.

#### 4.4.2 Data Source

```
GET https://api.github.com/repos/{owner}/{repo}/commits?per_page=100
```

For each commit in the response, the `commit.verification.verified` boolean field is read. The signal is `verified_count / total_count`.

#### 4.4.3 Collection Method

One authenticated request per agent per Daily Run (uses the configured GitHub personal access token). The sample size is fixed at `min(100, per_page_max)`. Requests have a 30-second timeout.

This is the only trust signal that requires GitHub API authentication. The GitHub API returns up to 100 commits per page; requesting more would require pagination, which is not implemented in the current reference implementation.

#### 4.4.4 What the Signal Means

`signed_commits_ratio` measures what fraction of the most recent commits on the default branch carry a cryptographic signature that GitHub has verified as mathematically valid. Signatures may be GPG, SSH, or S/MIME.

A high ratio indicates that committers in the project have configured signing keys and use them consistently. A ratio of 1.0 does not guarantee that the signing keys themselves are trustworthy — it only means the signatures are present and cryptographically valid per GitHub's verification.

#### 4.4.5 Freshness

The signal is collected fresh on every Daily Run. It reflects the most recent 100 commits on the default branch at collection time. As new commits are pushed, the sample window slides forward and older commits leave the sample.

#### 4.4.6 Failure Modes

| Condition | Observed value |
|---|---|
| GitHub API returns non-200 | `null` |
| Response is not a list | `null` |
| Empty commits list | `null` |
| Network timeout (>30 seconds) | `null` |

#### 4.4.7 Limitations

- **Web-based commit inflation:** Commits made through GitHub's web UI (e.g., editing files in the browser, merging PRs via the merge button) are signed by GitHub's own key and reported as `verified`. Projects that conduct a large share of their work through the GitHub UI will show inflated ratios that do not reflect active GPG/SSH signing discipline by contributors.
- **Sample window only:** Only the most recent 100 commits are sampled. A project that historically signed all commits but stopped signing recently will show a lower ratio; a project that recently started signing will show a higher ratio than its full history warrants.
- **Key trust not evaluated:** The signal reports signature presence, not key quality. A commit signed with a weak key or a key with no web of trust is counted as verified.

---

## 5. Extension Model

New trust signals SHOULD be added to this specification rather than to the Methodology Specification. The following criteria govern when a new signal may be incorporated:

### 5.1 Inclusion Criteria

A proposed new trust signal MUST satisfy all of the following:

1. **Unilateral observability:** The signal MUST be derivable from public APIs or public cryptographic infrastructure without contacting project maintainers or requiring their opt-in.
2. **Binary or scalar output:** The signal MUST produce a `boolean`, `float`, or `integer` value (or `null` for unavailability). Categorical or free-text signals are not permitted.
3. **Determinism:** Given the same API response at the same point in time, two independent implementations MUST produce the same signal value.
4. **Distinct from existing signals:** The proposed signal MUST measure a dimension of supply chain trust not already covered by the four signals in Section 4.
5. **Stable upstream source:** The data source MUST be maintained by a known organization and have a documented API. Signals derived from ephemeral or undocumented endpoints are not eligible.

### 5.2 Addition Process

1. A candidate signal is described in a draft section following the format of Section 4 (schema, data source, collection method, what it means, freshness, failure modes, limitations).
2. The draft is reviewed by the owner and merged into a new minor version of this specification (e.g., v0.1 → v0.2).
3. The reference implementation is updated to collect the signal. The signal is added to `data.json` and displayed on agent profile pages.
4. The signal is collected for at least 30 days before any discussion of incorporating it into the health score.

### 5.3 Removal Process

A signal MAY be removed if:
- The upstream data source becomes unavailable or undocumented.
- The signal is found to be non-deterministic or gameable in a way that undermines its value.
- A superior signal that subsumes it is added.

Removal increments the minor version. Historical Snapshots retain all fields from their collection date and are not retroactively modified.

---

## 6. Verification Process

HVTracker does not independently verify the cryptographic claims in trust signals — that responsibility lies with the end user and the upstream infrastructure. HVTracker's role is to collect and report whether the relevant cryptographic infrastructure is in use.

The verification chain for each signal is:

| Signal | Who verifies the cryptography |
|---|---|
| `npm_provenance` | npm CLI (`npm audit signatures`); Rekor transparency log |
| `pypi_provenance` | PyPI (`pip install --verify` where supported); Rekor transparency log |
| `scorecard_score` | OpenSSF Scorecard infrastructure; publicly auditable |
| `signed_commits_ratio` | GitHub's signature verification API; end users via `git verify-commit` |

HVTracker reports the output of these verification systems, not the raw cryptographic proofs. A `true` or high-ratio value means the relevant verification system reported success — it does not constitute an independent endorsement by HVTracker.

---

## 7. Versioning and Changelog

This specification uses a `vMAJOR.MINOR` version scheme:

- **v0.x:** Signals are collected and displayed but do not affect the health score. The specification is considered experimental; signals may be added, removed, or redefined with minor version increments.
- **v1.x:** The signal set is considered stable. Changes that affect which signals are collected or how they are defined increment the major version.
- Promotion from v0.x to v1.0 requires that the signal set has been stable for at least 90 days and that the owner has reviewed the specification for completeness.

All published versions remain permanently accessible at their versioned URLs. A version MUST NOT be modified after it receives Published status.

### Changelog

| Version | Date | Summary |
|---|---|---|
| v0.1 | 2026-05-24 | Initial draft. Defines four signals: npm provenance, PyPI PEP 740, OSSF Scorecard (with deps.dev primary + securityscorecards.dev fallback), signed commit ratio. Extension model defined. |

---

## Appendix A — Field Reference

Complete list of trust signal fields as stored in `data.json` and available in agent profile templates:

| Field | Type | Signal | Since |
|---|---|---|---|
| `npm_provenance` | `boolean \| null` | npm SLSA provenance attestation | Methodology v2.0 |
| `pypi_provenance` | `boolean \| null` | PyPI PEP 740 attestation | Methodology v2.0 |
| `has_provenance` | `boolean \| null` | `npm_provenance OR pypi_provenance` (derived) | Methodology v2.0 |
| `scorecard_score` | `float \| null` | OSSF Scorecard overall score [0–10] | Methodology v2.0 |
| `scorecard_checks` | `object \| {}` | Per-check Scorecard scores | Methodology v2.0 |
| `signed_commits_ratio` | `float \| null` | Fraction of signed commits [0.0–1.0] | Methodology v2.0 |

---

## Appendix B — Coverage as of 2026-05-24

Reported for reference; these numbers will change with each Daily Run.

| Signal | Coverage | Notes |
|---|---|---|
| `signed_commits_ratio` | 65/65 (100%) | GitHub API always returns data |
| `npm_provenance` | 4/11 with npm packages | 4 of 11 npm-tracked agents use Trusted Publishing |
| `pypi_provenance` | 7/46 with PyPI packages | Most packages predate PEP 740 |
| `has_provenance` | 11/65 (17%) | npm OR PyPI signal present |
| `scorecard_score` | 3/65 (5%) | Low upstream index coverage; securityscorecards.dev fallback added 2026-05-24, untested |
