# MCP tiering & x402 monetization seam (design)

Status: **design only — no billing/paid-tier code exists or ships** until the
owner is eligible to monetize (visa + legal). This doc records the intended
free/premium split and the x402 hook so the paid layer can be added cleanly
later without redesigning the free tools shipped now.

## Why

MCP is HVTracker's dominant machine channel (per `machine_usage` in `/healthz`:
MCP ≫ api_v1). Cloudflare fronts the origin and supports the **x402** payment
protocol (HTTP `402 Payment Required` with machine-payable receipts), which makes
per-call metering of MCP tools a natural future revenue stream. The verdict data
stays open (CC BY 4.0); only *operations/scale* are ever gated.

## Tool tiers

| Tool | Tier | Notes |
|---|---|---|
| `verify_mcp_server` | free | single-item pre-connect verdict |
| `check_agent_trust` | free | single-item profile + capabilities + credential URL |
| `compare_agents` | free | two-item comparison |
| `search_agents` | free | registry search |
| `scan_stack` | free | bulk verdict, **capped at 20k chars / 60 items** |
| `list_categories` | free | taxonomy + counts |
| `get_leaderboard` | free | top-N by trust, optional category |
| `get_agent_history` | free | **90-day** public window (mtime-cached) |
| `watch_server` / rug-pull drift alerts | **metered (later)** | live `tools/list` capture + longitudinal diff; compute-heavy, connects outward — the moat |
| extended history (>90d) | **metered (later)** | code already reserves this (`app.py` history endpoint) |
| uncapped / commercial bulk scan | **metered (later)** | the `scan_stack` free cap is the free/paid line |
| on-demand full dataset export | **metered (later)** | beyond the free quarterly CC BY export |

The free line is chosen to maximise adoption of the machine channel now while
leaving genuinely higher-cost / higher-value operations for the paid tier.

## x402 hook (how the paid layer slots in later)

The MCP endpoint is a single `POST /mcp` (stateless, JSON responses). The
2026-07-28 MCP spec adds an **`Mcp-Method`** request header naming the operation
(and tool) without body inspection — see the MCP load-review memo. That header is
the metering key:

1. A thin shim in front of the tool dispatch reads `Mcp-Method` (and, for
   `tools/call`, the tool name) and looks up its tier.
2. `free` tools bypass untouched (today: every registered tool).
3. `metered` tools without a valid x402 receipt return **HTTP 402** with the
   x402 payment-requirements body; with a receipt, they execute.
4. Cloudflare sits in front, so 402 challenges / receipt verification can move to
   the edge, keeping origin cost flat.

Nothing above is implemented. When monetization is legally/visa-cleared:
- register the first `metered` tool(s),
- add the tier map + the 402 shim,
- wire x402 receipt verification (origin, then optionally Cloudflare edge),
- keep the free tools exactly as they are.

## Cost-safety invariant (applies now and to any future tool)

Every free tool is a pure read over already-loaded/cached data — no new always-on
process, no new external API call, no GitHub open-lookup. They share the existing
MCP safety nets: the 60/min/IP limiter on `POST /mcp`, the `MCP_ENABLED` kill
switch, and the $6 Railway soft-spend alert. `get_agent_history` is served from an
mtime-cached index (rebuilt only when a new daily snapshot lands) so exposing
history over the high-traffic MCP channel does not add per-call disk I/O.
