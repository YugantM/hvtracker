# MCP registry listing — submission kit (plan 1.3)

Prepared 2026-07-08. Goal: get `https://hvtracker.net/mcp` discoverable in
MCP registries so assistants find the trust tools organically (master plan
asset #2 — embedded distribution).

Server facts (from `mcp_server.py`, v0.2.0):

- Remote **Streamable HTTP** at `https://hvtracker.net/mcp` — no auth, no
  install, read-only tools, 60/min per-IP rate limit, `MCP_ENABLED` kill
  switch.
- Tools: `verify_mcp_server`, `check_agent_trust`, `compare_agents`,
  `search_agents`.
- Server card already served at
  `https://hvtracker.net/.well-known/mcp/server-card.json` (Smithery-style
  scan target).

## 1. Official MCP registry (registry.modelcontextprotocol.io) — OWNER ACTION

Namespace `io.github.yugantm/*` requires GitHub auth via the
`mcp-publisher` CLI (it proves org/user ownership). Steps:

```bash
brew install mcp-publisher          # or download from the registry repo
cd $(mktemp -d)
cat > server.json <<'EOF'
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-07-09/server.schema.json",
  "name": "io.github.yugantm/hvtracker",
  "description": "Pre-connect trust checks for AI agents, frameworks, packages, and MCP servers using HVTracker's public trust registry.",
  "status": "active",
  "repository": { "url": "https://github.com/YugantM/hvtracker", "source": "github" },
  "version": "0.2.0",
  "remotes": [
    { "type": "streamable-http", "url": "https://hvtracker.net/mcp" }
  ]
}
EOF
mcp-publisher login github
mcp-publisher publish
```

Notes:
- Verify the current schema URL/fields against the registry docs at publish
  time — the registry format was still stabilizing in mid-2026.
- Re-publish on every `SERVER_VERSION` bump.

## 2. Smithery (smithery.ai) — OWNER ACTION, low effort

Smithery scans `/.well-known/mcp/server-card.json`, which is already live.
Submit the site URL via their "add server" flow while signed in with the
GitHub account.

## 3. Other directories (best-effort, no accounts needed to prepare)

- PulseMCP, Glama, mcp.so and similar directories accept submissions with
  name + endpoint + description. Use:
  - Name: **HVTracker — AI Agent Trust Registry**
  - Endpoint: `https://hvtracker.net/mcp` (Streamable HTTP, no auth)
  - One-liner: "Check the supply-chain trust of any AI agent, package, or
    MCP server before you connect — evidence-based scores, signed
    credentials, free."

## Why this matters

Every registry listing is compounding distribution: an assistant that
discovers the server calls `verify_mcp_server` at decision time, which is
exactly the "trust primitive machines consult" position from the master
plan (§2). Track adoption via `machine_usage.mcp` in `/healthz` (shipped in
plan 1.2).
