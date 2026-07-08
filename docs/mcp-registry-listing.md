# MCP registry listing — pointer (plan 1.3)

**The canonical distribution repo is `YugantM/hvtracker-mcp`** (corrected
2026-07-08 — an earlier draft of this doc wrongly pointed submissions at the
main repo). Everything listing-related lives THERE, not here:

- `server.json` — the official-registry payload
  (`io.github.YugantM/hvtracker-mcp`; remote `https://hvtracker.net/mcp`
  plus npm/PyPI/OCI stdio packages).
- `REGISTRY_SUBMISSIONS.md` — per-directory submission playbook (official
  registry, Smithery, Glama, PulseMCP, mcp.so, mcpservers.org,
  awesome-mcp-servers, Claude Desktop Extensions).
- `manifest.json` — MCPB bundle manifest for Claude Desktop.
- Tag-triggered CI publishes npm, PyPI, GHCR, Docker Hub, and the MCPB
  bundle on every `v*` tag; `publish-mcp-registry.yml`
  (workflow_dispatch, GitHub-OIDC auth — no tokens) pushes `server.json`
  to the official MCP registry.

State as of 2026-07-08: **v0.2.0** tagged and published (adds
`compare_agents` + capability/credential enrichment, matching the hosted
server at `hvtracker.net/mcp`). On any future `SERVER_VERSION` bump in this
repo's `mcp_server.py`, mirror the change in hvtracker-mcp (both stdio
implementations + metadata), tag, and re-dispatch the registry publish.

**Submission status (owner-confirmed 2026-07-08): DONE** on Smithery,
awesome-mcp-servers, and the official MCP registry (the registry also
re-verified live at 0.2.0 via the OIDC publish). No open submission work;
if more directories become worth listing on later, the field values are in
`REGISTRY_SUBMISSIONS.md`.
