"""HVTracker trust-layer MCP server (Streamable HTTP).

Exposes the existing trust engine as MCP tools so coding agents and services can
check supply-chain trust at decision time. This is a thin adapter over the same
resolution helpers and ``mcp_trust.evaluate`` that back ``/api/v1/mcp/verify`` —
there is no scoring logic here. Mounted at ``/mcp`` by app.py.

The verdict and the data stay OPEN (CC BY 4.0); only operations/scale are gated.

app.py imports this module at load time and this module needs app.py's data
helpers, so those imports are done lazily inside each tool to avoid a circular
import at module load.
"""
from typing import NotRequired, TypedDict

from mcp.types import ToolAnnotations
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_trust

SERVER_DISPLAY_NAME = "HVTracker MCP"
SERVER_VERSION = "0.2.0"
SERVER_DESCRIPTION = (
    "Pre-connect trust checks for AI agents, frameworks, packages, and MCP "
    "servers using HVTracker's public trust registry."
)
SERVER_HOMEPAGE = "https://hvtracker.net"
SERVER_REPOSITORY = "https://github.com/YugantM/hvtracker-mcp"
SERVER_URL = "https://hvtracker.net/mcp"

TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

AGENT_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"]},
        "repo": {"type": ["string", "null"]},
        "trust_score": {"type": ["number", "null"]},
        "evidence_grade": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "profile_url": {"type": "string"},
    },
    "required": ["name", "repo", "trust_score", "evidence_grade", "category", "profile_url"],
}

CAPABILITIES_SCHEMA = {
    "type": "object",
    "properties": {
        "mcp_status": {"type": "string"},
        "provider_count": {"type": "integer"},
        "requires_api_keys": {"type": "boolean"},
        "plugin_system": {"type": "string"},
        "drift_status": {"type": "string"},
    },
    "required": ["mcp_status", "provider_count", "requires_api_keys",
                 "plugin_system", "drift_status"],
}

CHECK_AGENT_TRUST_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "tracked": {"type": "boolean"},
        "name": {"type": ["string", "null"]},
        "repo": {"type": ["string", "null"]},
        "trust_score": {"type": ["number", "null"]},
        "evidence_grade": {"type": ["string", "null"]},
        "rank": {"type": ["integer", "null"]},
        "category": {"type": ["string", "null"]},
        "has_provenance": {"type": ["boolean", "null"]},
        "scorecard_score": {"type": ["number", "null"]},
        "coverage_grade": {"type": ["string", "null"]},
        "capabilities": {**CAPABILITIES_SCHEMA, "type": ["object", "null"]},
        "credential_url": {"type": ["string", "null"]},
        "profile_url": {"type": ["string", "null"]},
        "message": {"type": ["string", "null"]},
        "submit_url": {"type": ["string", "null"]},
    },
    "required": ["query", "tracked"],
}

COMPARE_AGENTS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "a": CHECK_AGENT_TRUST_OUTPUT_SCHEMA,
        "b": CHECK_AGENT_TRUST_OUTPUT_SCHEMA,
        "verdict": {"type": "string"},
        "compare_url": {"type": ["string", "null"]},
    },
    "required": ["a", "b", "verdict", "compare_url"],
}

VERIFY_MCP_SERVER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "server": {"type": "string"},
        "resolved": {"type": ["string", "null"]},
        "slug": {"type": ["string", "null"]},
        "tracked": {"type": "boolean"},
        "trusted": {"type": "boolean"},
        "grade": {"type": ["string", "null"]},
        "trust_score": {"type": ["number", "null"]},
        "confidence": {"type": ["number", "null"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "submit_url": {"type": ["string", "null"]},
        "mcp_server_support": {"type": ["string", "null"]},
        "tool_permissions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "server",
        "resolved",
        "tracked",
        "trusted",
        "grade",
        "trust_score",
        "confidence",
        "reasons",
        "mcp_server_support",
        "tool_permissions",
    ],
}

SEARCH_AGENTS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "results": {"type": "array", "items": AGENT_PROFILE_SCHEMA},
    },
    "required": ["count", "results"],
}


class Capabilities(TypedDict):
    mcp_status: str
    provider_count: int
    requires_api_keys: bool
    plugin_system: str
    drift_status: str


class AgentProfile(TypedDict):
    tracked: bool
    name: str | None
    repo: str | None
    trust_score: float | None
    evidence_grade: str | None
    rank: int | None
    category: str | None
    has_provenance: bool | None
    scorecard_score: float | None
    coverage_grade: str | None
    capabilities: Capabilities
    credential_url: str
    profile_url: str


class CheckAgentTrustResult(TypedDict):
    query: str
    tracked: bool
    name: NotRequired[str | None]
    repo: NotRequired[str | None]
    trust_score: NotRequired[float | None]
    evidence_grade: NotRequired[str | None]
    rank: NotRequired[int | None]
    category: NotRequired[str | None]
    has_provenance: NotRequired[bool | None]
    scorecard_score: NotRequired[float | None]
    coverage_grade: NotRequired[str | None]
    capabilities: NotRequired[Capabilities | None]
    credential_url: NotRequired[str | None]
    profile_url: NotRequired[str | None]
    message: NotRequired[str | None]
    submit_url: NotRequired[str | None]


class CompareAgentsResult(TypedDict):
    a: CheckAgentTrustResult
    b: CheckAgentTrustResult
    verdict: str
    compare_url: str | None


class VerifyMcpServerResult(TypedDict):
    server: str
    resolved: str | None
    slug: NotRequired[str | None]
    tracked: bool
    trusted: bool
    grade: str | None
    trust_score: float | None
    confidence: float | None
    reasons: list[str]
    submit_url: NotRequired[str | None]
    mcp_server_support: str | None
    tool_permissions: list[str]


class AgentSearchResult(TypedDict):
    name: str | None
    repo: str | None
    trust_score: float | None
    evidence_grade: str | None
    category: str | None
    profile_url: str


class SearchAgentsResult(TypedDict):
    count: int
    results: list[AgentSearchResult]


def _tool_annotations(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, **TOOL_ANNOTATIONS)


def _tool_card(
    name: str,
    title: str,
    description: str,
    input_schema: dict,
    output_schema: dict,
) -> dict:
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": input_schema,
        "outputSchema": output_schema,
        "annotations": {"title": title, **TOOL_ANNOTATIONS},
    }


VERIFY_MCP_SERVER_DESCRIPTION = (
    "Pre-connect trust verdict for an MCP server, package, GitHub repo, or "
    "agent name before connecting an AI agent to it."
)
CHECK_AGENT_TRUST_DESCRIPTION = (
    "Get the HVTracker supply-chain trust profile for a tracked AI agent or "
    "framework."
)
SEARCH_AGENTS_DESCRIPTION = (
    "Search tracked AI agents and frameworks by name, repo, description, or "
    "category, ranked by trust score."
)
COMPARE_AGENTS_DESCRIPTION = (
    "Compare two tracked AI agents side by side: trust scores, grades, "
    "runtime capabilities, and an evidence-based verdict."
)


def server_card() -> dict:
    """Static metadata for directories that cannot scan the MCP endpoint."""
    return {
        "$schema": "https://modelcontextprotocol.io/schemas/server-card/v1.0",
        "version": "1.0",
        "protocolVersion": "2025-06-18",
        "serverInfo": {
            "name": SERVER_DISPLAY_NAME,
            "title": SERVER_DISPLAY_NAME,
            "version": SERVER_VERSION,
            "description": SERVER_DESCRIPTION,
            "homepage": SERVER_HOMEPAGE,
        },
        "description": SERVER_DESCRIPTION,
        "homepage": SERVER_HOMEPAGE,
        "repository": SERVER_REPOSITORY,
        "transport": {
            "type": "streamable-http",
            "url": SERVER_URL,
        },
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False,
        },
        "authentication": {
            "required": False,
        },
        "tools": [
            _tool_card(
                "verify_mcp_server",
                "Verify MCP Server",
                VERIFY_MCP_SERVER_DESCRIPTION,
                {
                    "type": "object",
                    "properties": {
                        "server": {
                            "type": "string",
                            "description": "MCP server URL, package name, or GitHub owner/repo.",
                        },
                    },
                    "required": ["server"],
                },
                VERIFY_MCP_SERVER_OUTPUT_SCHEMA,
            ),
            _tool_card(
                "check_agent_trust",
                "Check Agent Trust",
                CHECK_AGENT_TRUST_DESCRIPTION,
                {
                    "type": "object",
                    "properties": {
                        "name_or_repo": {
                            "type": "string",
                            "description": (
                                "Agent name, slug, GitHub repo/URL, npm package, "
                                "or PyPI package."
                            ),
                        },
                    },
                    "required": ["name_or_repo"],
                },
                CHECK_AGENT_TRUST_OUTPUT_SCHEMA,
            ),
            _tool_card(
                "search_agents",
                "Search Agents",
                SEARCH_AGENTS_DESCRIPTION,
                {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "default": "",
                            "description": "Optional name, repo, or description search text.",
                        },
                        "category": {
                            "type": "string",
                            "default": "",
                            "description": "Optional exact category filter.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50,
                            "description": "Maximum number of results to return.",
                        },
                    },
                },
                SEARCH_AGENTS_OUTPUT_SCHEMA,
            ),
            _tool_card(
                "compare_agents",
                "Compare Agents",
                COMPARE_AGENTS_DESCRIPTION,
                {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "string",
                            "description": "First agent — name, slug, GitHub repo/URL, or package.",
                        },
                        "b": {
                            "type": "string",
                            "description": "Second agent — name, slug, GitHub repo/URL, or package.",
                        },
                    },
                    "required": ["a", "b"],
                },
                COMPARE_AGENTS_OUTPUT_SCHEMA,
            ),
        ],
        "resources": [],
        "prompts": [],
    }


# Stateless + JSON responses: no per-session state to keep, simplest to mount
# behind the existing app's middleware. app.py registers the SDK route directly
# so POST /mcp is handled without a redirect to /mcp/.
# session_manager is run by app.py's lifespan.
#
# DNS-rebinding protection guards *localhost* MCP servers from malicious web
# pages; it would reject legitimate clients hitting the public hvtracker.net
# host, so it's disabled for this read-only public API.
mcp = FastMCP(
    "hvtracker",
    instructions=SERVER_DESCRIPTION,
    website_url=SERVER_HOMEPAGE,
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def fresh_streamable_http_app():
    """Build a Streamable HTTP app with a fresh SDK session manager."""
    # The MCP SDK's StreamableHTTPSessionManager is intentionally single-use.
    # FastAPI test clients and reload-style processes can start lifespan more
    # than once in the same interpreter, so app.py reinstalls this route on
    # startup with a fresh manager.
    mcp._session_manager = None
    return mcp.streamable_http_app()


def _resolve_agent(query: str) -> dict | None:
    """Resolve a name / slug / owner-repo / URL / package to a tracked agent.

    Mirrors the resolution in ``app.api_v1_mcp_verify`` so the MCP tools and the
    HTTP endpoint agree on what a string maps to.
    """
    from app import _normalize_github_repo, find_agent, load_data
    query = (query or "").strip()
    if not query:
        return None
    repo = _normalize_github_repo(query)
    agent = find_agent(repo) if repo else None
    if agent is None:
        key = query.lower()
        for a in load_data().get("agents", []):
            if (a.get("npm_package") or "").lower() == key or \
               (a.get("pypi_package") or "").lower() == key or \
               (a.get("slug") or "").lower() == key or \
               (a.get("name") or "").strip().lower() == key:
                agent = a
                break
    return agent


def _profile(a: dict) -> AgentProfile:
    mcp_support = a.get("mcp_server_support") or {}
    ext = a.get("external_service_dependencies") or {}
    tooling = a.get("tool_plugin_surface") or {}
    drift = a.get("package_provenance_drift") or {}
    return {
        "tracked": True,
        "name": a.get("name"),
        "repo": a.get("repo"),
        "trust_score": a.get("trust_score"),
        "evidence_grade": a.get("evidence_grade"),
        "rank": a.get("rank"),
        "category": a.get("category"),
        "has_provenance": a.get("has_provenance"),
        "scorecard_score": a.get("scorecard_score"),
        "coverage_grade": a.get("coverage_grade"),
        "capabilities": {
            "mcp_status": mcp_support.get("status") or "none",
            "provider_count": len(ext.get("providers") or []),
            "requires_api_keys": bool(ext.get("requires_api_keys")),
            "plugin_system": tooling.get("plugin_system") or "none",
            "drift_status": drift.get("status") or "not_applicable",
        },
        # Ed25519-signed trust_credential lives here; verifiable offline
        # against /.well-known/hvtracker.json (methodology#verify-yourself).
        "credential_url": f"https://hvtracker.net/data/agents/{a.get('slug')}.json",
        "profile_url": f"https://hvtracker.net/agents/{a.get('slug')}/",
    }


@mcp.tool(
    title="Check Agent Trust",
    description=CHECK_AGENT_TRUST_DESCRIPTION,
    annotations=_tool_annotations("Check Agent Trust"),
)
def check_agent_trust(name_or_repo: str) -> CheckAgentTrustResult:
    """Get the HVTracker supply-chain trust profile for a tracked AI agent or
    framework. Accepts a display name ("LangGraph"), slug, GitHub owner/repo or
    URL, or an npm/PyPI package name. Returns the trust score (0-100), evidence
    grade (A-F), rank, provenance and OpenSSF Scorecard signals, and the profile
    URL. Returns tracked=false when the project is not in the registry."""
    a = _resolve_agent(name_or_repo)
    if not a:
        return {
            "query": name_or_repo,
            "tracked": False,
            "message": "Not in the HVTracker registry — no independent trust "
                       "evidence. Treat as unverified.",
            "submit_url": "https://hvtracker.net/submit",
        }
    return {"query": name_or_repo, **_profile(a)}


@mcp.tool(
    title="Verify MCP Server",
    description=VERIFY_MCP_SERVER_DESCRIPTION,
    annotations=_tool_annotations("Verify MCP Server"),
)
def verify_mcp_server(server: str) -> VerifyMcpServerResult:
    """Pre-connect trust verdict for an MCP server — "Safe Browsing for MCP".
    Call this BEFORE connecting an agent to an untrusted MCP server. Pass the
    server's URL, npm/PyPI package, or GitHub owner/repo. Returns whether it
    resolves to a tracked, trusted project, with grade, score, and reasons. An
    unknown server returns trusted=false (no evidence) — not a guarantee of harm."""
    return mcp_trust.evaluate(_resolve_agent(server), server)


@mcp.tool(
    title="Compare Agents",
    description=COMPARE_AGENTS_DESCRIPTION,
    annotations=_tool_annotations("Compare Agents"),
)
def compare_agents(a: str, b: str) -> CompareAgentsResult:
    """Compare two tracked AI agents side by side. Accepts the same
    identifiers as check_agent_trust for each side. Returns both trust
    profiles, an evidence-based one-line verdict, and the HVTracker compare
    page URL when one is published."""
    ra = check_agent_trust(a)
    rb = check_agent_trust(b)
    if not ra["tracked"] or not rb["tracked"]:
        missing = [q for q, r in ((a, ra), (b, rb)) if not r["tracked"]]
        verdict = (f"No verdict: {', '.join(missing)} not in the registry — "
                   "no independent trust evidence to compare.")
        return {"a": ra, "b": rb, "verdict": verdict, "compare_url": None}

    sa, sb = ra.get("trust_score") or 0, rb.get("trust_score") or 0
    if sa == sb:
        verdict = (f"{ra['name']} and {rb['name']} tie at HVTrust {sa} "
                   f"(grades {ra['evidence_grade']}/{rb['evidence_grade']}).")
    else:
        hi, lo = (ra, rb) if sa > sb else (rb, ra)
        verdict = (f"{hi['name']} scores higher on verifiable trust: HVTrust "
                   f"{hi['trust_score']} (grade {hi['evidence_grade']}) vs "
                   f"{lo['name']} at {lo['trust_score']} (grade {lo['evidence_grade']}).")

    # Published compare pages use canonical alphabetical slug order; only
    # link one that actually exists on this deployment.
    import os as _os

    from app import BASE_DIR
    slug_a = (ra.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1]
    slug_b = (rb.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1]
    first, second = sorted([slug_a, slug_b])
    pair = f"{first}-vs-{second}"
    compare_url = (f"https://hvtracker.net/compare/{pair}/"
                   if _os.path.isdir(_os.path.join(BASE_DIR, "compare", pair))
                   else None)
    return {"a": ra, "b": rb, "verdict": verdict, "compare_url": compare_url}


@mcp.tool(
    title="Search Agents",
    description=SEARCH_AGENTS_DESCRIPTION,
    annotations=_tool_annotations("Search Agents"),
)
def search_agents(query: str = "", category: str = "", limit: int = 10) -> SearchAgentsResult:
    """Search tracked AI agents and frameworks by name, repo, or description, with
    an optional category filter. Returns matches ranked by trust score (name,
    repo, trust_score, grade, category, profile URL)."""
    from app import load_data
    ql, cl = (query or "").lower(), (category or "").lower()
    out = []
    for a in load_data().get("agents", []):
        hay = f"{a.get('name', '')} {a.get('repo', '')} {a.get('description', '') or ''}".lower()
        if ql and ql not in hay:
            continue
        if cl and (a.get("category") or "").lower() != cl:
            continue
        out.append({
            "name": a.get("name"),
            "repo": a.get("repo"),
            "trust_score": a.get("trust_score"),
            "evidence_grade": a.get("evidence_grade"),
            "category": a.get("category"),
            "profile_url": f"https://hvtracker.net/agents/{a.get('slug')}/",
        })
    out.sort(key=lambda r: (r["trust_score"] is None, -(r["trust_score"] or 0)))
    limit = max(1, min(int(limit or 10), 50))
    return {"count": len(out), "results": out[:limit]}
