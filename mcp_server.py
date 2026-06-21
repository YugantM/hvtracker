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
SERVER_VERSION = "0.1.2"
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
        "profile_url": {"type": "string"},
        "message": {"type": "string"},
        "submit_url": {"type": "string"},
    },
    "required": ["query", "tracked"],
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
        "submit_url": {"type": "string"},
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
    profile_url: NotRequired[str | None]
    message: NotRequired[str | None]
    submit_url: NotRequired[str | None]


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
