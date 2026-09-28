# Advisory scoring: upset review (28 Sep 2026)

Phase 6 task 6.4. **Owner decision required. Nothing here changes a score.**

## Question

Advisories (OSV, #272) are shown on agent pages but don't touch HVTrust. The
top-ranked skill, OmniRoute (Grade A, 93.3), has an unfixed critical remote
code execution in the release people install. Should a known, unfixed,
serious advisory affect the score? If so, by which rule?

## Data

- Live `data.json`, 28 Sep 2026 (1,676 listings). Recomputing every row
  through `compute_trust_score` + `compute_trust_score_v2` reproduces the live
  `trust_score` on **all 1,676** (0 drift), so the old-vs-new comparison runs
  on identical inputs.
- #272's own `fetch_known_advisories` (identity guard included) run over all
  **877** listings that configure a package: **811** tie to their listing,
  0 errors.
- With the staleness guard from #284 (skip a package whose latest release is
  over a year old), **6** listings have advisories on their latest release:

| Listing | Class | Score | Grade | Rank | Package @ latest (released) | Worst | Advisories |
|---|---|---|---|---|---|---|---|
| OmniRoute | skill | 93.3 | A | #1 | npm omniroute 3.8.50 (2026-08-28) | CRITICAL | GHSA-hf57-cqmx-p4gr: ACP custom-agent RCE |
| Hermes Agent | agent | 84.1 | A | #94 | PyPI hermes-agent 0.19.0 (2026-07-20) | MODERATE | 2 |
| Chroma | agent | 73.6 | B | #249 | PyPI chromadb 1.5.9 (2026-05-05) | CRITICAL | 2 critical (code injection, incl. pre-auth), 2 high (tenant isolation) |
| LobeHub | skill | 66.7 | B | #50 | npm @lobehub/lobehub 2.1.26 (2026-02-10) | CRITICAL | unauthenticated SSRF; 2 moderate |
| MindsHub | agent | 65.5 | B | #453 | PyPI mindsdb 26.1.0 (2026-04-23) | unrated | 4 |
| Aider | agent | 51.9 | C | #877 | PyPI aider-chat 0.86.2 (2026-02-12) | LOW | 2 |

Without the staleness guard, AutoGPT would also have been capped, through
`agpt` 0.2.2 (last released April 2023). AutoGPT doesn't ship that way, so the
guard is a precondition for any rule below.

## Candidate rules and their effect

All are applied after runtime calibration, like a gate. "Bystanders" means
listings whose own score didn't change.

| Rule | Listings changed | Grade flips | Largest move | Bystanders (max \|Δrank\|) |
|---|---|---|---|---|
| **R1** cap at 64.9 (Grade C) for a critical or high | 3 | OmniRoute A→C, Chroma B→C, LobeHub B→C | OmniRoute #1→#62 (skills), Chroma #249→#482 | 2 |
| **R2** worst-advisory penalty −15 / −8 / −3 / −1 | 5 | OmniRoute A→B, Chroma B→C, LobeHub B→C | LobeHub #50→#211, Chroma #249→#668 | 1 |
| **R3** cap by severity: critical → C (64.9), high → B (79.9) | 3 (same as R1 today) | same as R1 | same as R1 | 2 |

R1 and R3 match today because every critical-or-high case has a critical.
They differ only for a high-only case: R1 caps it at C, R3 at B. R2 leaves
OmniRoute at Grade B with an unfixed critical RCE. It also docks moderates
(Hermes −3), whose real-world meaning varies too widely for a fixed penalty.

## Recommendation: R3, with the staleness guard

- **Legible.** "No Grade A or B while the release you'd install has an unfixed
  critical" is one sentence a maintainer can check.
- **Proportionate.** High caps at B, not C. Moderate, low and unrated don't
  change the score. They stay on the page, where the reader can weigh them.
- **Self-lifting.** Each listing's advisories are re-read on its daily full
  fetch (OSV cached 6 h). When a fixed version ships, the cap lifts on the
  next fetch, with no manual step.
- **Small, targeted blast radius.** 3 listings move; nobody else moves more
  than 2 places.

## Caveats the owner should weigh

1. **Coverage asymmetry.** Only listings with a registry package tied to
   their repo can be checked: 811 of 1,676 (48%). A project with no package
   can never be capped. The rule acts only on positive evidence of an unfixed
   flaw, never on missing evidence, so it doesn't penalise the unchecked.
   Still, two equally flawed projects can be treated differently.
2. **Severity comes from the advisory database** (GHSA `database_specific`).
   Unrated records never trigger a cap.
3. **The identity guard can miss.** Open WebUI's and MetaGPT's registry ids
   point elsewhere, so they are "not checked", never capped. A wrong cap needs
   both a tied, recently released package and an OSV record against that exact
   version.
4. **A big visible move.** OmniRoute drops from #1 to #62 on the skills board.
   Its page already shows the advisory, and the seal says the score doesn't
   include it yet. Scoring it removes that contradiction.

## If approved, it ships like every scoring change

`METHODOLOGY_VERSION` v4.3 → v4.4 (sparkline reset, cutover notification
suppression), spec `runtime-trust` v0.2 → v0.3 with the §4 table updated (the
spec-matches-code test locks it), and the methodology section and policy-log
entry. The rule lives in the gate step after `compute_trust_score_v2`, with
tests on the three live cases, and an evidence gate re-run on the day it
merges.

Reproduce (read-only, a few minutes): `python scripts/advisory_scoring_gate.py`.
It exits non-zero if any fetch errors or the recompute drifts from live.
