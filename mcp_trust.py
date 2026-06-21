"""MCP-server trust verdicts (P3) — "Safe Browsing for MCP".

An MCP client calls this *before connecting* to a server. We resolve the server
to its HVTracker trust record and return a pre-connect verdict, optionally signed
(reuses signing.py; same v0.2 attestation shape, subject = the MCP server).

Reputation only — this rides on whatever identity the MCP transport provides
(server URL + TLS, package name, repo); it does not issue identity. The trust
verdict and this format stay OPEN; only operations/scale are monetized.
"""
from datetime import datetime, timedelta, timezone

import signing

# Policy (documented in the MCP Server Trust spec). A consumer MAY override.
TRUSTED_GRADES = {"A", "B", "C"}
BLOCKED_STATUS = {"delisted", "warning", "legacy"}
MCP_SUPPORT_STATUS = {"declared", "implemented", "verified", "supported"}
MIN_SCORE = 40.0


def evaluate(agent: dict | None, server_id: str) -> dict:
    """Pure pre-connect verdict. `agent` is the resolved HVTracker record or None."""
    if not agent:
        return {
            "server": server_id,
            "resolved": None,
            "tracked": False,
            "trusted": False,
            "grade": None,
            "trust_score": None,
            "confidence": 0.0,
            "reasons": ["Not in the HVTracker registry — no independent evidence. "
                        "Submit it for review (eligibility applies); until then treat as "
                        "unverified and connect only if you trust the source directly."],
            "submit_url": "https://hvtracker.net/submit",
            "mcp_server_support": None,
            "tool_permissions": [],
        }

    grade = agent.get("evidence_grade")
    status = (agent.get("listing_status") or "").lower()
    score = agent.get("trust_score")
    mcp = agent.get("mcp_server_support") or {}
    tags = (agent.get("tool_plugin_surface") or {}).get("tool_tags") or []

    reasons: list[str] = []
    if status in BLOCKED_STATUS:
        reasons.append(f"Listing status '{status}' — do not connect.")
    if agent.get("npm_provenance") or agent.get("pypi_provenance"):
        reasons.append("Build provenance present (published package ties back to source).")
    else:
        reasons.append("No build provenance — the published package is not cryptographically "
                       "tied to its source.")
    sc = agent.get("scorecard_score")
    if sc is not None:
        reasons.append(f"OSSF Scorecard {sc}/10.")
    if mcp.get("status") in MCP_SUPPORT_STATUS:
        reasons.append(f"MCP server support: {mcp.get('status')}.")
    if tags:
        reasons.append(f"Declared tool surface: {', '.join(tags)} — review these permissions "
                       "before granting access.")

    trusted = (
        status not in BLOCKED_STATUS
        and grade in TRUSTED_GRADES
        and isinstance(score, (int, float))
        and score >= MIN_SCORE
    )
    return {
        "server": server_id,
        "resolved": agent.get("repo"),
        "slug": agent.get("slug"),
        "tracked": True,
        "trusted": trusted,
        "grade": grade,
        "trust_score": score,
        "confidence": agent.get("trust_confidence", agent.get("confidence")),
        "reasons": reasons,
        "mcp_server_support": mcp.get("status"),
        "tool_permissions": tags,
    }


def build_attestation(verdict: dict, issued_at: str | None = None) -> dict:
    """Wrap a verdict in a signed v0.2-style attestation (subject = MCP server).

    Signed with the issuer Ed25519 key when present (see signing.py); otherwise
    `signature` is null and the verdict is still usable, verified by reproduction.
    """
    now = datetime.now(timezone.utc)
    att = {
        "spec": "https://hvtracker.net/spec/mcp-server-trust/v0.1",
        "version": "0.1",
        "issuer": "hvtracker.net",
        "subject": {"mcp_server": verdict["server"], "repo": verdict.get("resolved")},
        "issued_at": issued_at or now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trusted": verdict["trusted"],
        "grade": verdict["grade"],
        "trust_score": verdict["trust_score"],
        "confidence": verdict["confidence"],
    }
    att["evidence_hash"] = signing.evidence_hash(att)
    att["signature"] = signing.sign_credential(att)
    return att
