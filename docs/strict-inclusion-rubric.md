# Strict Inclusion Rubric

This is the plain-language operating rule for what belongs in HVTracker.

HVTracker tracks **open-source AI agent projects** and **agent frameworks**. It does **not** track every AI-related repository.

## Include

A project is in scope only if all of the following are true:

- It has a public, non-archived primary source repository.
- It is distributed under an open-source license.
- It is primarily a software project that a third party can inspect, clone, and run.
- It is either:
  - an AI agent that can perform multi-step work from a natural-language goal, or
  - an agent framework whose primary purpose is building or coordinating AI agents.
- It contains non-trivial agent logic in its own codebase.
- It is active enough to justify active tracking.

## Agent test

An AI agent should clearly demonstrate at least two of these three behaviors:

- autonomous multi-step task execution
- tool use or external action taking
- goal-directed planning or adaptation

If a project only wraps an LLM, exposes an API client, or adds tool calls without autonomy or planning, it is out of scope.

## Framework test

A framework is in scope only if its primary design goal is agent construction and it provides agent-specific abstractions such as:

- tool registration or dispatch
- memory interfaces
- agent lifecycle management
- multi-agent coordination
- planning or execution loops

General-purpose SDKs, model clients, utility libraries, and generic app frameworks are out of scope even if agent projects can be built on top of them.

## Explicitly exclude

Do not include:

- model repositories
- general LLM SDKs or API clients
- prompt collections or cookbooks
- generic ML libraries
- general UI app builders
- document conversion tools
- workflow tools whose agent support is incidental rather than primary
- thin wrappers around a hosted remote agent API

## Canonical source of truth

The canonical inclusion state is the registry configuration and active generated registry data:

- `agents.json`
- `data/render_state.json`
- `output/history/<date>.json`

Generated profile artifacts on disk do not establish eligibility by themselves.

## Legacy handling

`listing_status: "legacy"` means the project remains in historical/internal state but is not part of the active public registry. Legacy entries should not publish active per-agent artifacts.

## When unsure

If a project needs a long explanation to justify why it is an agent, do not include it until the evidence is explicit in the repository and documentation.
