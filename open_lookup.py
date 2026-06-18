"""On-demand 'open lookup' for repos not in the curated registry (P2).

Free instant verdict for an unlisted repo IF it is an AI project AND has at
least MIN_STARS_FREE stars. Otherwise the caller is routed to the moderated
/submit flow. Verdicts here are PROVISIONAL (public GitHub signals only — no
downloads, provenance, or history) and EPHEMERAL (never added to the public
registry). Reputation only; this does not issue identity.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

MIN_STARS_FREE = 1000

# AI-project eligibility — the only inclusion criterion for open lookup.
# Reuses the topic vocabulary from discover_agents.py plus common synonyms.
AI_TOPICS = {
    "ai", "ai-agent", "ai-agents", "agent", "agents", "agentic", "llm", "llms",
    "coding-agent", "llm-agent", "autonomous-agent", "agent-framework",
    "multi-agent", "mcp", "model-context-protocol", "generative-ai", "genai",
    "rag", "llmops", "ai-tools", "chatbot", "openai", "anthropic", "gpt",
}
_AI_DESC_RE = re.compile(
    r"\b(ai agent|ai agents|agentic|autonomous agent|llm|large language model|"
    r"mcp|model context protocol|ai[- ]powered|generative ai|coding agent|"
    r"multi[- ]agent|retrieval[- ]augmented|\brag\b|chatbot|gpt-?\d|copilot)\b",
    re.IGNORECASE,
)


def looks_like_ai(repo: dict) -> bool:
    """Basic check: is this an AI project? (topics or description signal)."""
    topics = {t.lower() for t in (repo.get("topics") or [])}
    if topics & AI_TOPICS:
        return True
    text = " ".join(filter(None, [repo.get("description"), repo.get("name"), repo.get("full_name")]))
    return bool(_AI_DESC_RE.search(text or ""))


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def build_provisional(server_id: str, repo: dict) -> dict:
    """Provisional verdict from public GitHub signals (pure; no network)."""
    full = repo.get("full_name") or server_id
    stars = int(repo.get("stargazers_count") or 0)
    lic = (repo.get("license") or {}).get("spdx_id")
    open_license = bool(lic) and lic not in ("NOASSERTION", "NONE")
    days = _days_since(repo.get("pushed_at"))
    active = days is not None and days <= 180

    reasons = [f"AI project · {stars:,} stars (provisional, public GitHub signals only — "
               "no package downloads, provenance, or history yet)."]
    reasons.append(f"Open license: {lic}." if open_license else
                   "No clear open-source license detected.")
    if days is not None:
        reasons.append(f"Active — last push {repo.get('pushed_at', '')[:10]}." if active else
                       f"Low recent activity — last push {repo.get('pushed_at', '')[:10]}.")
    reasons.append("Submit it for a continuously-tracked, fully-scored Verified listing.")

    trusted = open_license and active
    grade = "C" if trusted else "D"
    return {
        "server": server_id,
        "resolved": full,
        "tracked": False,
        "provisional": True,
        "eligibility": "ok",
        "trusted": trusted,
        "grade": grade,
        "trust_score": None,
        "confidence": 0.35,
        "stars": stars,
        "reasons": reasons,
        "tool_permissions": [],
        "submit_url": "https://hvtracker.net/submit",
    }


def _gate(server_id: str, eligibility: str, message: str, stars: int | None = None) -> dict:
    return {
        "server": server_id, "resolved": None, "tracked": False, "provisional": False,
        "eligibility": eligibility, "trusted": False, "grade": None, "trust_score": None,
        "confidence": 0.0, "stars": stars, "reasons": [message],
        "tool_permissions": [], "submit_url": "https://hvtracker.net/submit",
    }


def fetch_repo(owner_repo: str, token: str = "") -> dict | None:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"https://api.github.com/repos/{owner_repo}", headers=headers, timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def evaluate_open(server_id: str, repo_path: str, token: str = "") -> dict:
    """Full open-lookup decision for an unlisted GitHub repo."""
    repo = fetch_repo(repo_path, token)
    if not repo:
        return _gate(server_id, "not_found",
                     "Could not find that public GitHub repo. Open lookup needs a public "
                     "repository (owner/name). Submit it for review if it's private or renamed.")
    if repo.get("archived"):
        return _gate(server_id, "archived",
                     "This repository is archived (no longer maintained) — not eligible.")
    if not looks_like_ai(repo):
        return _gate(server_id, "not_ai",
                     "This doesn't look like an AI agent/project — HVTracker only covers AI agents.")
    stars = int(repo.get("stargazers_count") or 0)
    if stars < MIN_STARS_FREE:
        return _gate(server_id, "below_stars",
                     f"AI project with {stars:,} stars — below the {MIN_STARS_FREE:,}-star bar for a "
                     "free instant check. Submit it for moderated review instead.", stars=stars)
    return build_provisional(server_id, repo)
