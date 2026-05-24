# HVTracker Eligibility Specification v1.0

**Status:** Draft — awaiting owner review before publication  
**Version:** v1.0  
**Date:** 2026-05-24  
**Authors:** HVTracker  
**Track:** Standards Track  

---

## 1. Abstract

This document defines the criteria by which a software project qualifies for inclusion in the HVTracker leaderboard. It specifies necessary and sufficient conditions using normative language (MUST, SHOULD, MAY) such that two independent reviewers applying this specification to any candidate project will reach the same inclusion or exclusion decision. This specification supersedes all prior informal or implicit eligibility rules.

---

## 2. Motivation

HVTracker tracks 65 AI agent projects and generates daily health scores. As the index has grown, the question of what belongs in it has become harder to answer by intuition alone. Several failure modes have emerged:

- Projects that were once active agents are now archived or unmaintained.
- Some entries are hosted services that expose no inspectable source code.
- Some entries are thin API wrappers with no agent logic of their own.
- Some entries are forks with no independent development activity.

Without a formal eligibility specification, the index is subject to arbitrary inclusion, motivated by novelty rather than fit. A formal spec makes the boundary visible, consistent, and disputable. It also enables automated checking during the build process, so violations surface as warnings rather than silent drift.

---

## 3. Terminology

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as described in RFC 2119.

**AI agent:** A software system that autonomously performs multi-step tasks by combining a language model with external capabilities such as tool use, memory, code execution, browser control, or file system access. An AI agent takes an underspecified goal as input and determines the sequence of actions required to accomplish it, without requiring a human to specify each step.

**Autonomous task execution:** The capacity of a system to complete a task end-to-end without human confirmation at each step. A system that requires a human to approve every action before proceeding is a tool, not an agent. A system that requires only an initial prompt and produces a final output is exhibiting autonomous task execution.

**Tool use:** The capacity of a software system to invoke external functions, APIs, code interpreters, or system interfaces as part of completing a task. Tool use is a necessary but not sufficient condition for agent classification.

**Hosted service:** A software system that is delivered exclusively via a networked API or web interface and for which no source code is publicly available for inspection, modification, or self-hosting. Hosted services are not eligible for HVTracker regardless of their capabilities.

**Thin client:** A software package whose primary function is to make API calls to a remote service, containing no agent logic of its own. A thin client that wraps a hosted agent service is not independently eligible; it may be considered only if the underlying service is also open-source and separately eligible.

**Framework:** A software library or toolkit that enables developers to construct AI agents, providing abstractions for tool use, memory, planning, or multi-agent coordination. A framework is eligible if it demonstrably enables agent construction and is not merely a general-purpose utility library with no agent-specific design.

**Open-source license:** A license that meets the Open Source Definition as maintained by the Open Source Initiative (OSI), or a license that is widely accepted in the open-source community and provides equivalent rights (source availability, modification, redistribution). This includes all OSI-approved licenses and the RAIL family of licenses when the source code is publicly available.

**Version control repository:** A hosted repository using a distributed version control system (e.g., Git) that is publicly accessible without authentication. GitHub, GitLab, Sourcehut, and Codeberg repositories satisfy this definition. A ZIP archive on a project website does not.

**Meaningful activity:** At least one of the following within a trailing 12-month window: a merged pull request, a commit to the primary branch, a published release, or a closed issue with a maintainer response. Activity by automated bots (dependency bumps, CI runs) does not count toward this threshold unless accompanied by human commits.

**Archived project:** A project whose version control repository has been placed in a read-only archived state by its maintainers, or a project whose maintainers have publicly stated it is no longer maintained.

**Abandoned fork:** A repository that is a fork of another project and has received zero independent commits (commits not present in the upstream project) since the fork was created, or since the upstream project itself became inactive.

---

## 4. Eligibility Criteria

### 4.1 Required Criteria (MUST)

A candidate project MUST satisfy all of the following to be eligible for inclusion.

**4.1.1 Open-source license**  
The project MUST be distributed under an open-source license as defined in Section 3. The license MUST be declared in the primary repository (e.g., LICENSE file, SPDX identifier in package manifest). A project with no declared license is not eligible.

**4.1.2 Public version control repository**  
The project MUST have a publicly accessible version control repository as defined in Section 3. The repository MUST be the primary location for source code and development activity — a mirror is not sufficient if the primary repository is private.

**4.1.3 Software deliverable**  
The project MUST be primarily delivered as software that can be inspected, cloned, and run by a third party. Projects delivered exclusively as hosted services are not eligible. A project that offers both a hosted service and a self-hostable open-source component is eligible on the basis of the open-source component only.

**4.1.4 Agent characteristics**  
The project MUST demonstrate at least two of the following three agent characteristics:

- **(a) Autonomous task execution:** The system can complete a multi-step task given only an initial natural-language goal, without requiring human confirmation at each step.
- **(b) Tool use:** The system can invoke external functions, APIs, code interpreters, file systems, or browser interfaces as part of task completion.
- **(c) Goal-directed planning:** The system decomposes a goal into sub-tasks, selects actions based on intermediate results, and adapts its plan when an action fails.

A system that satisfies only (b) — tool use — without (a) or (c) is a tool-augmented chatbot, not an agent, and is not eligible.

**4.1.5 Non-trivial implementation**  
The project MUST contain non-trivial agent logic in its own codebase. A package whose sole function is to forward requests to a remote agent API (thin client as defined in Section 3) is not eligible on its own. The project MUST contain at least one of: a planning or reasoning loop, a memory system, a tool dispatch mechanism, or a multi-step execution engine implemented in the package itself.

### 4.2 Recommended Criteria (SHOULD)

A candidate project SHOULD satisfy the following. Projects that do not satisfy these criteria are not disqualified but are flagged for manual review.

**4.2.1 Meaningful recent activity**  
The project SHOULD demonstrate meaningful activity as defined in Section 3 within the trailing 12 months. Projects with no meaningful activity in 12 months are flagged as inactive. They remain on the leaderboard but receive an "inactive" annotation visible to users.

**4.2.2 Installable package**  
The project SHOULD be installable via a mainstream package manager (npm, PyPI, Homebrew, Cargo, etc.). Projects distributed only as source tarballs or ZIP archives are technically eligible but harder to track and are deprioritized for inclusion.

**4.2.3 Documentation of agent capabilities**  
The project SHOULD document its agent characteristics in its README or official documentation. A project that makes no claims about agent behavior in its own documentation cannot be verified against criterion 4.1.4.

### 4.3 Optional Criteria (MAY)

**4.3.1 Framework eligibility**  
A project MAY be a framework or library that enables agent construction rather than an agent itself, provided it meets all MUST criteria and additionally:

- Its primary design goal is enabling agent construction (not general-purpose programming).
- It provides abstractions specific to agent behavior: tool registration, memory interfaces, agent lifecycle management, or multi-agent coordination.
- At least one publicly available project built on the framework qualifies as an agent under 4.1.4.

General-purpose utility libraries (HTTP clients, JSON parsers, LLM SDK wrappers with no agent abstractions) are not eligible under this clause.

---

## 5. Disqualification Criteria

A project is disqualified and MUST be removed from the leaderboard if any of the following conditions are met. Disqualification criteria take precedence over eligibility criteria.

**5.1 Archived repository**  
The project's primary version control repository has been archived (read-only) by its maintainers. Archiving signals intentional end-of-life.

**5.2 License revocation or change**  
The project has changed its license to one that no longer meets the open-source definition in Section 3 (e.g., relicensed to a commercial or source-available-only license). The change is evaluated as of the most recent release, not the historical record.

**5.3 Abandoned fork with no independent activity**  
The project is a fork of another tracked project and has made zero independent commits in the trailing 24 months. Forks that have diverged meaningfully and demonstrate independent development are not subject to this criterion.

**5.4 Private or deleted repository**  
The project's repository has been made private or deleted.

**5.5 Explicit maintainer withdrawal**  
The project's maintainers have formally requested removal from the index.

---

## 6. Review Process

### 6.1 Adding a new project

To add a candidate project to the index, a reviewer applies the criteria in Section 4 in order:

1. Verify 4.1.1 (license): Check the LICENSE file and SPDX identifier.
2. Verify 4.1.2 (repository): Confirm the repository is public and not a mirror.
3. Verify 4.1.3 (software deliverable): Confirm the project can be cloned and run.
4. Verify 4.1.4 (agent characteristics): Verify at least two of (a), (b), (c).
5. Verify 4.1.5 (non-trivial implementation): Confirm agent logic exists in the codebase.
6. Check 4.2.1 (recent activity): Note if inactive; flag for annotation, not exclusion.
7. Check Section 5 (disqualification): If any apply, the project is excluded regardless of 4.1.

The reviewer records their findings in a structured note attached to the pull request that adds the agent to `agents.json`. The note MUST reference each criterion explicitly.

### 6.2 Reviewing existing projects

The automated build process checks criteria 5.1 (archived), 5.4 (private/deleted), and 4.2.1 (recent activity) on every run. Violations are emitted as warnings in the build log and do not block the build. The owner reviews warnings and decides on action.

Criteria that require human judgment (4.1.4, 4.1.5, 5.3) are reviewed manually on a quarterly basis or when flagged by the automated check.

### 6.3 Removal process

Before removing a project, the owner reviews the disqualification reason and, where practical, notifies the project maintainers. Removal is recorded in the git commit message with the criterion cited. No project is removed without owner approval.

---

## 7. Automated Enforcement

The build system implements automated checks for the following criteria during each daily cron run. All checks are non-blocking (warnings only).

| Check | Criterion | Data source |
|---|---|---|
| Repository archived | 5.1 | GitHub API: `archived` field |
| Repository not found | 5.4 | GitHub API: HTTP 404 on repo endpoint |
| No activity in 12 months | 4.2.1 | GitHub API: `pushed_at` field |
| No declared license | 4.1.1 | GitHub API: `license` field |

Criteria 4.1.4 and 4.1.5 require human review and are not automatically enforced.

---

## 8. Versioning and Changelog

This specification is versioned independently of the HVTracker methodology specification. Changes to eligibility criteria increment the minor version (v1.0 → v1.1) for clarifications and the major version (v1.0 → v2.0) for changes that would cause a currently included project to be excluded or a currently excluded project to become eligible.

### Changelog

| Version | Date | Summary |
|---|---|---|
| v1.0 | 2026-05-24 | Initial publication |

---

## Appendix A — Boundary Cases

The following cases are provided to illustrate how the criteria apply in ambiguous situations. These are non-normative.

**A.1 Hosted service with open-source server code**  
A product that offers a hosted SaaS interface and also publishes the server code under an open-source license. Eligible on the basis of the open-source component if it meets 4.1.4 and 4.1.5. The hosted interface is irrelevant to eligibility.

**A.2 Research prototype**  
A repository associated with a published academic paper, containing code that runs an agent experiment but has no releases, no package, and no commits after the paper's publication date. Eligible under 4.1 if agent characteristics are present, but flagged under 4.2.1 as inactive. Not disqualified.

**A.3 Model provider SDK**  
An SDK published by an LLM provider that includes convenience wrappers for function calling and tool use. Eligible under 4.3.1 (framework) only if it includes agent-specific abstractions (e.g., an agent loop, tool registry, multi-step execution engine). A bare function-calling wrapper is not eligible.

**A.4 Fork with substantial divergence**  
A fork of a tracked project that has added its own planning engine, tool integrations, and an independent release history. Not subject to 5.3. Evaluated independently against all criteria in Section 4.

**A.5 Project that relicenses partially**  
A project that relicenses its core under a commercial license but retains an open-source community edition. Eligible only if the community edition meets all criteria in Section 4 independently, without depending on proprietary components for core agent functionality.

---

## Appendix B — Criteria Quick Reference

| ID | Level | Criterion |
|---|---|---|
| 4.1.1 | MUST | Open-source license declared |
| 4.1.2 | MUST | Public version control repository |
| 4.1.3 | MUST | Software deliverable, not hosted-only |
| 4.1.4 | MUST | ≥2 of: autonomous execution, tool use, goal-directed planning |
| 4.1.5 | MUST | Non-trivial agent logic in own codebase |
| 4.2.1 | SHOULD | Meaningful activity in trailing 12 months |
| 4.2.2 | SHOULD | Installable via mainstream package manager |
| 4.2.3 | SHOULD | Agent capabilities documented in README |
| 4.3.1 | MAY | Framework eligible if agent-specific abstractions present |
| 5.1 | DISQUALIFY | Repository archived |
| 5.2 | DISQUALIFY | License no longer open-source |
| 5.3 | DISQUALIFY | Abandoned fork, zero independent commits in 24 months |
| 5.4 | DISQUALIFY | Repository private or deleted |
| 5.5 | DISQUALIFY | Maintainer withdrawal request |
