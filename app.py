"""HVTracker web service.

Serves the pre-generated static site from the volume, exposes a dynamic JSON
API and live SVG badges sourced from data.json, accepts agent submissions /
corrections into Postgres, and runs the 2-hourly refresh in-process.
"""
from __future__ import annotations

import json
import os
import re
import threading
import hashlib
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

import db
import mcp_server
import verify_log


# ---- anti-spam helpers -----------------------------------------------------

_RATE_WINDOW = 600  # 10 minutes
_RATE_LIMIT = 5
_rate_log: dict[str, deque] = {}
_rate_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


def _is_rate_limited(request: Request) -> bool:
    ip = _client_ip(request)
    now = time.monotonic()
    with _rate_lock:
        q = _rate_log.setdefault(ip, deque())
        while q and q[0] < now - _RATE_WINDOW:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            return True
        q.append(now)
    return False


# Open-lookup (P2): a more generous, read-only limit than the form limiter,
# plus a short cache so repeat checks of the same repo don't re-hit GitHub.
_OLOOKUP_WINDOW = 600
_OLOOKUP_LIMIT = 20
_olookup_log: dict[str, deque] = {}
_olookup_cache: dict[str, tuple] = {}
_OLOOKUP_TTL = 86400  # cache a repo's verdict for the day; a daily job can refresh it


def _is_open_lookup_limited(request: Request) -> bool:
    ip = _client_ip(request)
    now = time.monotonic()
    with _rate_lock:
        q = _olookup_log.setdefault(ip, deque())
        while q and q[0] < now - _OLOOKUP_WINDOW:
            q.popleft()
        if len(q) >= _OLOOKUP_LIMIT:
            return True
        q.append(now)
    return False


def _olookup_cache_get(repo: str):
    hit = _olookup_cache.get(repo)
    if hit and time.monotonic() - hit[0] < _OLOOKUP_TTL:
        return hit[1]
    return None


def _olookup_cache_put(repo: str, verdict: dict) -> None:
    _olookup_cache[repo] = (time.monotonic(), verdict)


# MCP endpoint limiter: the trust tools are read-only in-memory lookups with no
# external calls, so this is deliberately generous — it only exists to stop a
# flood that bypasses the CDN and hits the origin directly. A real multi-check
# agent session stays well under it.
_MCP_WINDOW = 60
_MCP_LIMIT = 60
_mcp_log: dict[str, deque] = {}


def _is_mcp_rate_limited(request: Request) -> bool:
    ip = _client_ip(request)
    now = time.monotonic()
    with _rate_lock:
        q = _mcp_log.setdefault(ip, deque())
        while q and q[0] < now - _MCP_WINDOW:
            q.popleft()
        if len(q) >= _MCP_LIMIT:
            return True
        q.append(now)
    return False


def _mcp_enabled() -> bool:
    """Budget kill switch for the MCP endpoint.

    Set MCP_ENABLED=0 (Railway variable) to pause only the /mcp server — the
    website, badges, and the /api/v1/mcp/verify HTTP API keep serving. Use this
    if MCP traffic ever pushes usage toward the workspace spend cap.
    """
    return os.environ.get("MCP_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"}


_EMAIL_RE = re.compile(r".+@.+\..+")

_FIELD_LIMITS = {
    "repo": 200,
    "name": 120,
    "email": 254,
    "contact": 254,
    "message": 4000,
    "notes": 4000,
}
_DEFAULT_LIMIT = 500


def _check_field_lengths(**fields: str) -> str | None:
    for name, value in fields.items():
        limit = _FIELD_LIMITS.get(name, _DEFAULT_LIMIT)
        if len(value) > limit:
            return f"{name} exceeds the {limit}-character limit."
    return None


HONEYPOT_HTML = '<div style="position:absolute;left:-9999px;top:-9999px" aria-hidden="true"><label>Leave blank<input name="website" autocomplete="off" tabindex="-1"></label></div>'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", BASE_DIR)
PREBUILT_DIR = os.path.join(BASE_DIR, "prebuilt")
os.makedirs(OUTPUT_DIR, exist_ok=True)  # volume subdir may not exist on first boot
DATA_PATH = os.path.join(OUTPUT_DIR, "data.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
COMPARE_TOOL_PATH = os.path.join(BASE_DIR, "compare", "index.html")
VERIFY_TOOL_PATH = os.path.join(BASE_DIR, "verify", "index.html")
SCAN_TOOL_PATH = os.path.join(BASE_DIR, "scan", "index.html")
RENDER_FINGERPRINT_PATH = os.path.join(OUTPUT_DIR, ".render_fingerprint")
verify_log.init(OUTPUT_DIR)  # public "recently checked" feed (transparency)
REFRESH_STATUS_PATH = os.path.join(OUTPUT_DIR, ".refresh_status.json")
MAX_DATA_AGE = timedelta(hours=int(os.environ.get("MAX_DATA_AGE_HOURS", "6")))
# OSSF scores are baked into the image from the `data` branch at build time
# (see Dockerfile). Re-pull that file at runtime so live refreshes apply the
# latest daily scan instead of the deploy-time snapshot, which otherwise ages
# out to the unreliable deps.dev fallback after 48h.
SCORECARD_CACHE_URL = os.environ.get(
    "SCORECARD_CACHE_URL",
    "https://raw.githubusercontent.com/YugantM/hvtracker/data/scorecard-cache.json",
)
SCORECARD_CACHE_PATH = os.path.join(BASE_DIR, "scorecard-cache.json")

@asynccontextmanager
async def _lifespan(_app):
    # Run the MCP Streamable-HTTP session manager (required by the SDK even in
    # stateless mode) for the lifetime of the app, then the existing startup work.
    _install_mcp_route()
    async with mcp_server.mcp.session_manager.run():
        startup()
        try:
            yield
        finally:
            shutdown()


app = FastAPI(title="HVTracker", docs_url="/api/docs", openapi_url="/api/openapi.json",
              lifespan=_lifespan)

# Accounts: GitHub/Google OAuth + watchlist/claim/notifications. Registered
# before the catch-all StaticFiles mount so its /auth/* and /api/* routes win.
import auth as _auth  # noqa: E402
app.include_router(_auth.router)

_scheduler = None
_refresh_lock = threading.Lock()
SITE_NAV_ITEMS = (
    ("Leaderboard", "/"),
    ("Movers", "/movers/"),
    ("Changes", "/changes/"),
    ("Use cases", "/use-cases/"),
    ("Methodology", "/methodology"),
    ("Score lab", "/score-lab/"),
    ("Compare", "/compare/"),
    ("Alerts", "/alerts/"),
    ("Data API", "/data/"),
    ("Sponsor", "/sponsor/"),
)


# ---- cache headers -------------------------------------------------------
#
# StaticFiles ships responses with no Cache-Control, so Cloudflare returns
# `cf-cache-status: DYNAMIC` and every visit hits Railway directly.  Add
# sensible defaults: HTML pages get 5 min browser / 15 min CDN cache (with
# stale-while-revalidate so re-fetches feel instant), JSON data endpoints
# get longer s-maxage since they're consumed by API users.  Routes that
# already set Cache-Control (e.g. badge SVGs at app.py:172) win — we only
# fill in the gaps.
_HTML_CACHE = "public, max-age=300, s-maxage=900, stale-while-revalidate=86400"
_JSON_CACHE = "public, max-age=600, s-maxage=1800, stale-while-revalidate=86400"


_CSP = (
    "default-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:"
)
_CANONICAL_HOST = "hvtracker.net"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_DYNAMIC_SLASH_PATHS = {
    "/alerts",
    "/badges",
    "/blog",
    "/changes",
    "/changelog",
    "/compare",
    "/verify",
    "/correct",
    "/data",
    "/data-api",
    "/ecosystem",
    "/movers",
    "/methodology",
    "/org",
    "/roadmap",
    "/score-lab",
    "/spec",
    "/sponsor",
    "/submit",
    "/use-cases",
}
_HEALTHCHECK_PATHS = {"/healthz", "/healthz/"}


def _external_scheme(request: Request) -> str:
    cf_visitor = request.headers.get("cf-visitor")
    if cf_visitor:
        try:
            scheme = json.loads(cf_visitor).get("scheme")
            if scheme in {"http", "https"}:
                return scheme
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    forwarded = request.headers.get("x-forwarded-proto", "")
    if forwarded:
        scheme = forwarded.split(",", 1)[0].strip().lower()
        if scheme in {"http", "https"}:
            return scheme
    return request.url.scheme


def _external_host(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    raw_host = forwarded_host.split(",", 1)[0].strip() if forwarded_host else request.headers.get("host", "")
    return raw_host.split(":", 1)[0].lower()


def _path_needs_trailing_slash(path: str) -> bool:
    if path in ("", "/") or path.endswith("/"):
        return False
    if path.startswith("/spec/"):
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3:
            return True
    if "." in path.rsplit("/", 1)[-1]:
        return False
    if path in _DYNAMIC_SLASH_PATHS or path.startswith("/track/"):
        return True
    candidate = os.path.join(OUTPUT_DIR, path.lstrip("/"))
    return os.path.isdir(candidate) and os.path.isfile(os.path.join(candidate, "index.html"))


def _canonical_redirect_target(request: Request) -> str | None:
    scheme = _external_scheme(request)
    host = _external_host(request)
    path = request.url.path or "/"
    target_path = f"{path}/" if _path_needs_trailing_slash(path) else path
    if host in _LOCAL_HOSTS:
        if target_path == path:
            return None
        query = request.url.query
        suffix = f"?{query}" if query else ""
        return f"{request.url.scheme}://{request.headers.get('host', host)}{target_path}{suffix}"
    if scheme == "https" and host == _CANONICAL_HOST and target_path == path:
        return None
    query = request.url.query
    suffix = f"?{query}" if query else ""
    return f"https://{_CANONICAL_HOST}{target_path}{suffix}"


@app.middleware("http")
async def _cache_headers(request, call_next):
    path = request.url.path
    if path not in _HEALTHCHECK_PATHS:
        redirect_target = _canonical_redirect_target(request)
        if redirect_target is not None:
            status_code = 301 if request.method in {"GET", "HEAD"} else 308
            return RedirectResponse(redirect_target, status_code=status_code)

    if path == "/mcp" and request.method == "POST":
        if not _mcp_enabled():
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32000,
                 "message": "HVTracker MCP is temporarily paused to stay within budget. "
                            "The website and the HTTP API at /api/v1/mcp/verify remain available."}},
                status_code=503,
                headers={"Retry-After": "3600"},
            )
        if _is_mcp_rate_limited(request):
            return JSONResponse(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32029,
                 "message": "Rate limit exceeded — too many MCP requests from your IP. Retry in a minute."}},
                status_code=429,
                headers={"Retry-After": "60"},
            )

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy-Report-Only"] = _CSP
    if _external_scheme(request) == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    if not path.startswith("/badge/"):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

    if response.status_code != 200 or "cache-control" in {k.lower() for k in response.headers}:
        return response
    if path.startswith("/data/") and path.endswith(".json"):
        response.headers["Cache-Control"] = _JSON_CACHE
    elif path.endswith("/") or path.endswith(".html"):
        response.headers["Cache-Control"] = _HTML_CACHE
    elif path in ("",) or path == "/":
        response.headers["Cache-Control"] = _HTML_CACHE
    return response

# ---- data.json access (mtime-cached) -------------------------------------

_cache: dict = {"mtime": None, "data": None}


def load_data() -> dict:
    """Return the current leaderboard from the volume's data.json (cached by mtime)."""
    try:
        mtime = os.path.getmtime(DATA_PATH)
    except OSError:
        return {"agents": [], "total": 0, "updated": None}
    if _cache["mtime"] != mtime:
        for _ in range(3):
            try:
                with open(DATA_PATH, encoding="utf-8") as f:
                    _cache["data"] = json.load(f)
                _cache["mtime"] = mtime
                break
            except json.JSONDecodeError:
                if _cache["data"] is not None:
                    return _cache["data"]
                time.sleep(0.05)
        else:
            return {"agents": [], "total": 0, "updated": None}
    return _cache["data"]


def _catalog_agent_count() -> int:
    try:
        with open(os.path.join(BASE_DIR, "agents.json"), encoding="utf-8") as f:
            return len(json.load(f))
    except (OSError, json.JSONDecodeError, TypeError):
        return 0


def _source_render_count() -> int:
    catalog_count = 0
    try:
        with open(os.path.join(BASE_DIR, "agents.json"), encoding="utf-8") as f:
            agents = json.load(f)
        catalog_count = sum(
            1 for agent in agents
            if agent.get("status") != "legacy" and agent.get("listing_status") != "legacy"
        )
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    path = os.path.join(BASE_DIR, "data", "render_state.json")
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        return max(catalog_count, len(payload.get("rows") or []))
    except (OSError, json.JSONDecodeError, TypeError):
        return catalog_count


def _normalize_github_repo(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    text = text.replace("git@github.com:", "https://github.com/")
    text = text.replace("ssh://git@github.com/", "https://github.com/")
    text = text.replace("git+https://github.com/", "https://github.com/")
    text = text.replace("git://github.com/", "https://github.com/")
    if "github.com/" in text.lower():
        m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s?#]+)", text, re.IGNORECASE)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2)
    else:
        parts = [part for part in text.strip("/").split("/") if part]
        if len(parts) != 2:
            return None
        owner, repo = parts
    repo = repo.removesuffix(".git")
    return f"{owner.lower()}/{repo.lower()}" if owner and repo else None


def _tracked_repo_lookup() -> dict[str, dict]:
    return {
        (agent.get("repo") or "").lower(): agent
        for agent in db.load_agents()
        if agent.get("repo")
    }


def load_manual_candidates() -> list[dict]:
    path = os.path.join(BASE_DIR, "docs", "import-candidates.json")
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, list):
        return []

    tracked = _tracked_repo_lookup()
    items = []
    for entry in payload:
        if isinstance(entry, str):
            source_repo = entry
            item = {"repo": entry}
        elif isinstance(entry, dict):
            source_repo = entry.get("repo") or entry.get("url") or entry.get("github")
            item = dict(entry)
        else:
            continue
        normalized_repo = _normalize_github_repo(source_repo)
        if not normalized_repo:
            continue
        tracked_agent = tracked.get(normalized_repo)
        item["repo"] = normalized_repo
        item["url"] = f"https://github.com/{normalized_repo}"
        item["tracked"] = tracked_agent is not None
        item["tracked_name"] = tracked_agent.get("name") if tracked_agent else None
        items.append(item)
    return items


def _site_header_html(updated: str) -> str:
    nav_links = "".join(
        f'<a href="{href}">{escape(label)}</a>'
        for label, href in SITE_NAV_ITEMS
    )
    return f"""<header class="site-header">
    <div class="site-header-inner">
      <a href="/" class="logo">HV<span>Tracker</span></a>
      <nav class="site-nav" aria-label="Site">
        {nav_links}
      </nav>
      <div class="site-status" data-updated="{updated}">
        <span class="live-dot"></span>updated <span class="site-status-value">{updated}</span>
      </div>
    </div>
  </header>"""


def _runtime_git_sha() -> str | None:
    for key in (
        "RAILWAY_GIT_COMMIT_SHA",
        "GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "SOURCE_COMMIT",
        "COMMIT_SHA",
    ):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_updated_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M UTC", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _read_refresh_status() -> dict:
    try:
        with open(REFRESH_STATUS_PATH, encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _write_refresh_status(status: dict) -> None:
    with open(REFRESH_STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, sort_keys=True)


def _mark_refresh_status(**updates) -> dict:
    status = _read_refresh_status()
    status.update(updates)
    _write_refresh_status(status)
    return status


def find_agent(repo: str) -> dict | None:
    repo = repo.lower()
    for a in load_data().get("agents", []):
        if a["repo"].lower() == repo:
            return a
    return None


def find_agent_by_slug(slug: str) -> dict | None:
    slug = slug.lower()
    for a in load_data().get("agents", []):
        if (a.get("slug") or "").lower() == slug:
            return a
    return None


def _resolve_registry_agent(identifier: str) -> dict | None:
    """Resolve an identifier to a tracked agent: GitHub repo/URL first, then by
    npm/pypi package, slug, or display name. Mirrors the resolution used by
    /api/v1/mcp/verify and the MCP server so all three agree on what a string maps to."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    repo = _normalize_github_repo(identifier)
    agent = find_agent(repo) if repo else None
    if agent is None:
        key = identifier.lower()
        for a in load_data().get("agents", []):
            if (a.get("npm_package") or "").lower() == key or \
               (a.get("pypi_package") or "").lower() == key or \
               (a.get("slug") or "").lower() == key or \
               (a.get("name") or "").strip().lower() == key:
                agent = a
                break
    return agent


_SCAN_MAX_ITEMS = 60


def _parse_scan_input(text: str) -> list[str]:
    """Extract candidate identifiers from pasted requirements.txt, package.json,
    an MCP client config, or a plain (newline/comma) list. Best-effort and
    tolerant — unknown shapes fall back to line parsing."""
    text = (text or "").strip()
    if not text:
        return []
    ids: list[str] = []
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        obj = None
    if isinstance(obj, dict):
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            dep = obj.get(key)
            if isinstance(dep, dict):
                ids.extend(dep.keys())
        servers = obj.get("mcpServers")
        if isinstance(servers, dict):
            for name, cfg in servers.items():
                ids.append(name)
                if isinstance(cfg, dict) and isinstance(cfg.get("url"), str):
                    ids.append(cfg["url"])
    if not ids:
        # requirements.txt / plain list: strip version specifiers, extras, markers, comments.
        for raw in re.split(r"[\n,]", text):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            token = re.split(r"[<>=!~;\[ @]", line, maxsplit=1)[0].strip()
            if token:
                ids.append(token)
    seen, out = set(), []
    for i in ids:
        i = i.strip()
        k = i.lower()
        if i and k not in seen:
            seen.add(k)
            out.append(i)
    return out[:_SCAN_MAX_ITEMS]


# ---- JSON API ------------------------------------------------------------

@app.api_route(
    "/.well-known/mcp/server-card.json",
    methods=["GET", "HEAD"],
    include_in_schema=False,
)
def smithery_mcp_server_card():
    return JSONResponse(mcp_server.server_card(), headers={"Cache-Control": _JSON_CACHE})


@app.api_route("/healthz", methods=["GET", "HEAD"])
@app.api_route("/healthz/", methods=["GET", "HEAD"])
def healthz():
    d = load_data()
    source_fingerprint = _compute_render_fingerprint()
    stored_fingerprint = _read_render_fingerprint()
    refresh_status = _read_refresh_status()
    updated_at = _parse_updated_timestamp(d.get("updated"))
    data_age_seconds = None
    data_fresh = None
    if updated_at is not None:
        data_age_seconds = max(0, int((datetime.now(timezone.utc) - updated_at).total_seconds()))
        data_fresh = data_age_seconds <= int(MAX_DATA_AGE.total_seconds())
    return {
        "status": "ok",
        "agents": d.get("total", 0),
        "catalog_agents": _catalog_agent_count(),
        "source_render_agents": _source_render_count(),
        "updated": d.get("updated"),
        "max_data_age_seconds": int(MAX_DATA_AGE.total_seconds()),
        "data_age_seconds": data_age_seconds,
        "data_fresh": data_fresh,
        "git_sha": _runtime_git_sha(),
        "source_render_fingerprint": source_fingerprint,
        "stored_render_fingerprint": stored_fingerprint,
        "render_in_sync": bool(stored_fingerprint and stored_fingerprint == source_fingerprint),
        "refresh_in_progress": bool(refresh_status.get("in_progress")),
        "last_refresh_started_at": refresh_status.get("last_started_at"),
        "last_refresh_completed_at": refresh_status.get("last_completed_at"),
        "last_refresh_succeeded": refresh_status.get("last_succeeded"),
        "last_refresh_mode": refresh_status.get("last_mode"),
        "last_refresh_error": refresh_status.get("last_error"),
    }


@app.api_route("/api/agents", methods=["GET", "HEAD"])
def api_agents(q: str = "", category: str = "", sort: str = "rank",
               order: str = "asc", limit: int = 50, offset: int = 0):
    """Search/filter/sort/paginate the leaderboard."""
    agents = load_data().get("agents", [])
    if q:
        ql = q.lower()
        agents = [a for a in agents
                  if ql in a["name"].lower() or ql in a["repo"].lower()
                  or ql in (a.get("description") or "").lower()]
    if category:
        cl = category.lower()
        agents = [a for a in agents if (a.get("category") or "").lower() == cl]
    reverse = order == "desc"
    agents = sorted(agents, key=lambda a: (a.get(sort) is None, a.get(sort)), reverse=reverse)
    total = len(agents)
    page = agents[offset:offset + max(0, min(limit, 200))]
    return {"total": total, "count": len(page), "offset": offset, "agents": page}


@app.api_route("/api/agents/{owner}/{repo}", methods=["GET", "HEAD"])
def api_agent(owner: str, repo: str):
    agent = find_agent(f"{owner}/{repo}")
    if not agent:
        return JSONResponse({"error": "not found"}, status_code=404)
    return agent


@app.api_route("/api/feed", methods=["GET", "HEAD"])
def api_feed():
    path = os.path.join(OUTPUT_DIR, "feed.json")
    if not os.path.isfile(path):
        return JSONResponse({"error": "feed not built yet"}, status_code=503)
    with open(path, encoding="utf-8") as f:
        return JSONResponse(json.load(f))


@app.api_route("/api/import-candidates", methods=["GET", "HEAD"])
def api_import_candidates(status: str = "", category: str = "", tracked: str = "",
                          limit: int = 100, offset: int = 0):
    candidates = load_manual_candidates()
    if status:
        status_l = status.lower()
        candidates = [c for c in candidates if (c.get("status") or "").lower() == status_l]
    if category:
        category_l = category.lower()
        candidates = [c for c in candidates if (c.get("category") or "").lower() == category_l]
    if tracked:
        tracked_flag = tracked.lower()
        want_tracked = tracked_flag in ("1", "true", "yes")
        if tracked_flag in ("1", "true", "yes", "0", "false", "no"):
            candidates = [c for c in candidates if bool(c.get("tracked")) is want_tracked]
    total = len(candidates)
    page = candidates[offset:offset + max(0, min(limit, 500))]
    return {"total": total, "count": len(page), "offset": offset, "candidates": page}


_API_V1_CACHE = "public, max-age=900"
_API_V1_CORS = "*"


@app.get("/api/v1/graph")
def api_v1_graph():
    path = os.path.join(OUTPUT_DIR, "data", "graph.json")
    if not os.path.isfile(path):
        return JSONResponse({"error": "graph not built yet"}, status_code=503)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data, headers={
        "Cache-Control": _API_V1_CACHE,
        "Access-Control-Allow-Origin": _API_V1_CORS,
    })


@app.get("/api/v1/agents")
def api_v1_agents():
    if not os.path.isfile(DATA_PATH):
        return JSONResponse({"error": "data not built yet"}, status_code=503)
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data, headers={
        "Cache-Control": _API_V1_CACHE,
        "Access-Control-Allow-Origin": _API_V1_CORS,
    })


@app.get("/api/v1/mcp/verify")
def api_v1_mcp_verify(request: Request, server: str = ""):
    """Pre-connect trust verdict for an agent or MCP server.

    `server` may be a GitHub repo (owner/name or URL) or an npm/pypi package.
    Curated agents return a full signed verdict. An unlisted GitHub repo falls
    through to open lookup (P2): a free PROVISIONAL verdict if it is an AI
    project with >= 1,000 stars, else it is routed to /submit. The attestation
    is signed so the verdict is verifiable; verification is always free.
    """
    import mcp_trust
    server = (server or "").strip()
    cors = {"Access-Control-Allow-Origin": _API_V1_CORS}
    if not server:
        return JSONResponse({"error": "missing required query param: server"},
                            status_code=400, headers=cors)

    # 1) Curated registry (the gold "Verified" tier).
    agent = None
    repo = _normalize_github_repo(server)
    if repo:
        agent = find_agent(repo)
    if agent is None:
        # Resolve by package id, or by the agent's slug / display name — users
        # naturally type the name they see on the leaderboard ("headroom")
        # rather than the owner/repo or package id. Names and slugs are unique.
        key = server.lower()
        for a in load_data().get("agents", []):
            if (a.get("npm_package") or "").lower() == key or \
               (a.get("pypi_package") or "").lower() == key or \
               (a.get("slug") or "").lower() == key or \
               (a.get("name") or "").strip().lower() == key:
                agent = a
                break
    if agent is not None:
        verdict = mcp_trust.evaluate(agent, server)
        verdict["attestation"] = mcp_trust.build_attestation(verdict)
        verify_log.record(verdict.get("resolved") or repo or server, agent.get("name"),
                          verdict.get("grade"), verdict.get("trusted"), False, agent.get("stars"))
        return JSONResponse(verdict, headers={**cors, "Cache-Control": _API_V1_CACHE})

    # 2) Unlisted and not a GitHub repo -> submit funnel (no scoring).
    if not repo:
        verdict = mcp_trust.evaluate(None, server)
        verdict["attestation"] = mcp_trust.build_attestation(verdict)
        return JSONResponse(verdict, headers=cors)

    # 3) Unlisted GitHub repo -> open lookup (cached, rate-limited).
    cached = _olookup_cache_get(repo)
    if cached is not None:
        return JSONResponse(cached, headers=cors)
    if _is_open_lookup_limited(request):
        return JSONResponse(
            {"server": server, "tracked": False, "trusted": False,
             "eligibility": "rate_limited", "submit_url": "https://hvtracker.net/submit",
             "reasons": ["Too many instant checks from your IP — try again in a few minutes."]},
            status_code=429, headers=cors)
    import open_lookup
    verdict = open_lookup.evaluate_open(server, repo, os.environ.get("GITHUB_TOKEN", ""))
    if verdict.get("eligibility") == "ok":
        verdict["attestation"] = mcp_trust.build_attestation(verdict)
        verify_log.record(verdict.get("resolved") or repo, None, verdict.get("grade"),
                          verdict.get("trusted"), True, verdict.get("stars"))
    _olookup_cache_put(repo, verdict)
    return JSONResponse(verdict, headers=cors)


@app.get("/api/v1/verify/recent")
def api_v1_verify_recent():
    """Public feed: the last successfully checked projects (transparency).

    Every free check is public by default and appears here. Private checks will
    require the paid tier or a public submission.
    """
    return JSONResponse({"checks": verify_log.recent()}, headers={
        "Cache-Control": "public, max-age=30, s-maxage=60",
        "Access-Control-Allow-Origin": _API_V1_CORS,
    })


@app.post("/api/v1/scan")
async def api_v1_scan(request: Request):
    """Bulk pre-connect trust check for a whole dependency set.

    POST JSON {"input": "<requirements.txt | package.json | MCP config | list>"}.
    Each identifier is resolved against the curated registry and returned with a
    per-item verdict plus a summary. Registry-only (no GitHub open lookup) so it
    stays cheap and fast — the same engine that backs /api/v1/mcp/verify."""
    import mcp_trust
    cors = {"Access-Control-Allow-Origin": _API_V1_CORS}
    if _is_mcp_rate_limited(request):
        return JSONResponse({"error": "rate limited — slow down and retry shortly"},
                            status_code=429, headers=cors)
    try:
        payload = await request.json()
    except Exception:
        payload = None
    text = payload.get("input") if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        return JSONResponse(
            {"error": 'POST JSON {"input": "<requirements.txt / package.json / mcp config / list>"}'},
            status_code=400, headers=cors)
    if len(text) > 20000:
        return JSONResponse({"error": "input too large (max 20000 chars)"},
                            status_code=400, headers=cors)
    identifiers = _parse_scan_input(text)
    results = []
    summary = {"total": 0, "tracked": 0, "untracked": 0, "trusted": 0, "avg_trust": None}
    scores = []
    for ident in identifiers:
        v = mcp_trust.evaluate(_resolve_registry_agent(ident), ident)
        results.append({
            "input": ident,
            "tracked": v["tracked"],
            "trusted": v["trusted"],
            "grade": v["grade"],
            "trust_score": v["trust_score"],
            "resolved": v.get("resolved"),
            "slug": v.get("slug"),
        })
        summary["total"] += 1
        summary["tracked" if v["tracked"] else "untracked"] += 1
        if v["trusted"]:
            summary["trusted"] += 1
        if v["trust_score"] is not None:
            scores.append(v["trust_score"])
    # Average HVTrust across the tracked (scored) items in the stack.
    if scores:
        summary["avg_trust"] = round(sum(scores) / len(scores), 1)
    return JSONResponse({"summary": summary, "results": results}, headers=cors)


@app.api_route("/scan", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/scan/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def scan_tool():
    if not os.path.isfile(SCAN_TOOL_PATH):
        return HTMLResponse("<p>Scan tool is not available yet.</p>", status_code=503)
    with open(SCAN_TOOL_PATH, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.api_route("/compare", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/compare/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def compare_tool():
    if not os.path.isfile(COMPARE_TOOL_PATH):
        return HTMLResponse("<p>Compare tool is not available yet.</p>", status_code=503)
    with open(COMPARE_TOOL_PATH, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.api_route("/compare/{pair}", methods=["GET", "HEAD"], include_in_schema=False)
def compare_pair_noslash(pair: str):
    return RedirectResponse(f"/compare/{pair}/", status_code=301)


@app.api_route("/compare/{pair}/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def compare_pair(pair: str):
    # /compare/<a>-vs-<b>/ serves the interactive compare tool with both agents
    # preselected (the tool reads the slugs from the path). Validate the pair and
    # keep one canonical URL per pair — alphabetical by slug — so it never 404s or
    # splits for two tracked agents.
    parts = pair.split("-vs-")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    slug_a, slug_b = parts

    slugs = {r["slug"] for r in load_data().get("agents", [])}
    if slug_a not in slugs or slug_b not in slugs:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    if slug_a > slug_b:
        return RedirectResponse(f"/compare/{slug_b}-vs-{slug_a}/", status_code=301)

    return compare_tool()


@app.api_route("/verify", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/verify/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def verify_tool():
    if not os.path.isfile(VERIFY_TOOL_PATH):
        return HTMLResponse("<p>Verify tool is not available yet.</p>", status_code=503)
    with open(VERIFY_TOOL_PATH, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/og-v2.png")
def og_v2():
    return FileResponse(os.path.join(BASE_DIR, "og-v2.png"), media_type="image/png")


@app.get("/og-verify.png")
def og_verify():
    return FileResponse(os.path.join(BASE_DIR, "og-verify.png"), media_type="image/png")


@app.get("/og-mcp.png")
def og_mcp():
    return FileResponse(os.path.join(BASE_DIR, "og-mcp.png"), media_type="image/png")


@app.get("/og-scan.png")
def og_scan():
    return FileResponse(os.path.join(BASE_DIR, "og-scan.png"), media_type="image/png")


@app.get("/favicon.svg")
def favicon_svg():
    return FileResponse(os.path.join(BASE_DIR, "favicon.svg"), media_type="image/svg+xml")


# Browsers auto-request these regardless of <link> tags; point them at the SVG
# so they stop 404ing.
@app.get("/favicon.ico")
@app.get("/apple-touch-icon.png")
@app.get("/apple-touch-icon-precomposed.png")
def favicon_compat():
    return RedirectResponse("/favicon.svg", status_code=301)


@app.get("/haystack-logo.png")
def haystack_logo():
    return FileResponse(os.path.join(BASE_DIR, "haystack-logo.png"), media_type="image/png")


@app.get("/aipass-logo.png")
def aipass_logo():
    return FileResponse(os.path.join(BASE_DIR, "aipass-logo.png"), media_type="image/png")


@app.get("/composio-logo.svg")
def composio_logo():
    return FileResponse(os.path.join(BASE_DIR, "composio-logo.svg"), media_type="image/svg+xml")


@app.get("/lightrag-logo.png")
def lightrag_logo():
    return FileResponse(os.path.join(BASE_DIR, "lightrag-logo.png"), media_type="image/png")


@app.get("/hex-bg.svg")
def hex_bg():
    return FileResponse(os.path.join(BASE_DIR, "hex-bg.svg"), media_type="image/svg+xml")


# ---- Dynamic SVG badges --------------------------------------------------

def _badge_svg(label: str, value: str, color: str) -> str:
    char_w = 6.1
    label_w = len(label) * char_w + 12
    value_w = len(value) * char_w + 12
    total_w = label_w + value_w
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_w:.0f}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
  <clipPath id="r"><rect width="{total_w:.0f}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w:.0f}" height="20" fill="#555"/>
    <rect x="{label_w:.0f}" width="{value_w:.0f}" height="20" fill="#{color}"/>
    <rect width="{total_w:.0f}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="{label_w / 2:.0f}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_w / 2:.0f}" y="14">{label}</text>
    <text x="{label_w + value_w / 2:.0f}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_w + value_w / 2:.0f}" y="14">{value}</text>
  </g>
</svg>'''


@app.get("/badge/{owner}/{repo}/{kind}.svg")
def badge(owner: str, repo: str, kind: str):
    agent = find_agent(f"{owner}/{repo}")
    if kind == "trust":
        score = (agent or {}).get("trust_score", 0) or 0
        color = "34d399" if score >= 55 else "60a5fa" if score >= 30 else "f87171"
        svg = _badge_svg("HVTrust", str(score), color)
    elif kind == "grade":
        grade = (agent or {}).get("evidence_grade", "D")
        color = {"A": "34d399", "B": "60a5fa", "C": "fbbf24", "D": "f87171"}.get(grade, "9ca3af")
        svg = _badge_svg("Grade", grade, color)
    else:
        return JSONResponse({"error": "unknown badge kind"}, status_code=404)
    headers = {"Cache-Control": "public, max-age=3600"}
    if not agent:
        headers["Cache-Control"] = "public, max-age=60"
    return Response(svg, media_type="image/svg+xml", headers=headers)


@app.get("/badge/{slug}.svg")
def badge_by_slug(slug: str):
    kind = "trust"
    if slug.endswith("-grade"):
        slug = slug[:-6]
        kind = "grade"
    agent = find_agent_by_slug(slug)
    if not agent:
        return JSONResponse({"error": "not found"}, status_code=404)
    owner, repo = agent["repo"].split("/", 1)
    return badge(owner, repo, kind)


# ---- Submission / correction intake --------------------------------------

def _page(name: str) -> str:
    with open(os.path.join(TEMPLATES_DIR, name), encoding="utf-8") as f:
        return f.read()


def _marketing_page(
    title: str,
    eyebrow: str,
    heading: str,
    body_html: str,
    *,
    description: str = "HVTracker validates demand for alerts, data access, sponsorship, submissions, and corrections before building heavier workflows.",
    path: str = "/",
) -> str:
    canonical = f"https://hvtracker.net{path}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <link rel="canonical" href="{escape(canonical)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(canonical)}">
  <meta property="og:image" content="https://hvtracker.net/og-v2.png">
  <meta property="og:image:secure_url" content="https://hvtracker.net/og-v2.png">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="HVTracker AI trust registry preview">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="https://hvtracker.net/og-v2.png">
  <meta name="twitter:image:alt" content="HVTracker AI trust registry preview">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/static/site.css">
  <style>
    :root {{
      --paper:#f4f1eb; --paper-2:#ece4d6; --ink:#1f1b17; --muted:#6f665d;
      --line:#d5cbbc; --line-strong:#b9aa96; --lobster:#c67c6d;
      --lobster-soft:rgba(198,124,109,.14); --blue-strong:#7f9cbd; --green:#2f6846;
      --font-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
      --font-sans:"Hanken Grotesk",system-ui,-apple-system,sans-serif;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{
      min-height:100vh; color:var(--ink); font:15px/1.65 var(--font-sans);
      background:var(--paper);
      background-image:url("/hex-bg.svg");
      background-size:2000px 2000px;
    }}
    a {{ color:inherit; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .logo span {{ color:var(--lobster); }}
    .page {{ max-width:1120px; margin:0 auto; padding:24px 24px 48px; background:var(--paper); min-height:100vh; }}
    .shell {{
      max-width:780px; margin:0 auto;
    }}
    .hero {{ padding:28px 0 20px; border-bottom:1px solid var(--line); }}
    .eyebrow {{
      display:inline-block; margin-bottom:12px; color:var(--lobster); font:11px var(--font-mono);
      text-transform:uppercase; letter-spacing:0.08em;
    }}
    h1 {{ margin:0 0 10px; font-size:34px; line-height:1.1; letter-spacing:-0.03em; }}
    .lede {{ margin:0; max-width:680px; color:var(--muted); }}
    .content {{ padding:24px 0 30px; display:grid; gap:22px; }}
    .card {{
      border-top:2px solid var(--line-strong); padding:18px;
      background:var(--paper-2);
    }}
    .card h2 {{ margin:0 0 10px; font-size:15px; }}
    .card p {{ margin:0 0 10px; color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:14px; }}
    .pill {{
      display:inline-block; padding:4px 9px; border-radius:999px; font:11px var(--font-mono);
      background:var(--lobster-soft); color:var(--lobster);
    }}
    ul {{ margin:10px 0 0 18px; padding:0; color:var(--muted); }}
    li + li {{ margin-top:6px; }}
    form {{ display:grid; gap:14px; }}
    label {{ display:grid; gap:6px; font-weight:600; }}
    input, textarea {{
      width:100%; border:1px solid var(--line); border-radius:10px; padding:12px 13px;
      background:var(--paper); color:var(--ink); font:14px var(--font-sans);
    }}
    textarea {{ min-height:120px; resize:vertical; }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
    .button {{
      display:inline-flex; align-items:center; justify-content:center; padding:11px 16px; border-radius:10px;
      background:var(--paper); color:var(--ink); border:1px solid var(--line);
      font:700 12px var(--font-mono); text-decoration:none;
    }}
    .button.secondary {{
      background:var(--paper-2); color:var(--muted); border-color:var(--line);
    }}
    .button:hover {{ text-decoration:none; border-color:var(--lobster); color:var(--lobster); }}
    .button.secondary:hover {{ color:var(--ink); border-color:var(--lobster); }}
    .ok {{ color:var(--green); font-weight:700; }}
    footer {{
      margin-top:28px; padding-top:16px; border-top:1px solid var(--line);
      font:11px var(--font-mono); color:var(--muted); text-align:center;
    }}
    .footer-sep {{ color:var(--line-strong); }}
    footer a {{ color:var(--blue-strong); }}
    @media (max-width:760px) {{
      .page {{ padding:24px 20px 40px; }}
      h1 {{ font-size:28px; }}
    }}
  </style>
  <!-- opt out: localStorage.setItem('hvt_notrack','1') -->
  <script>
    (function(){{try{{if(localStorage.getItem("hvt_notrack")==="1"){{window["ga-disable-G-TZ8921LR0K"]=true;return}}}}catch(_){{}}
    var ua=navigator.userAgent||"";if(/HeadlessChrome|Puppeteer|Playwright|Claude\/[\d.]+.*Electron\/|bot|crawl|spider|curl|wget|python-requests/i.test(ua)){{window["ga-disable-G-TZ8921LR0K"]=true}}}})();
  </script>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-TZ8921LR0K"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-TZ8921LR0K');
  </script>
  <script defer src="/analytics.js"></script>
</head>
<body>
  {_site_header_html(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}
  <div class="page">
    <div class="shell">
      <section class="hero">
        <div class="eyebrow">{escape(eyebrow)}</div>
        <h1>{escape(heading)}</h1>
        <p class="lede">HVTracker is still early, so these pages are intentionally lightweight. The goal is to validate who wants alerts, data access, and sponsorship before building heavier workflows.</p>
      </section>
      <section class="content">
        {body_html}
      </section>
      <footer>
        <a href="/methodology">Methodology</a>
        <span class="footer-sep">&middot;</span>
        <a href="/spec/">Specifications</a>
        <span class="footer-sep">&middot;</span>
        <a href="/data/">Data API</a>
        <span class="footer-sep">&middot;</span>
        <a href="/compare/">Compare</a>
        <span class="footer-sep">&middot;</span>
        <a href="/badges/">Badges</a>
        <span class="footer-sep">&middot;</span>
        <a href="/changelog/">Changelog</a>
        <span class="footer-sep">&middot;</span>
        <a href="/blog/">Blog</a>
        <span class="footer-sep">&middot;</span>
        <a href="https://github.com/YugantM/hvtracker/issues/new?template=agent-listing.yml" target="_blank" rel="noopener">Submit Agent</a>
        <span class="footer-sep">&middot;</span>
        <a href="https://github.com/YugantM/hvtracker" target="_blank" rel="noopener">GitHub</a>
      </footer>
    </div>
  </div>
</body>
</html>"""


def _interest_unavailable() -> HTMLResponse:
    return HTMLResponse(
        _marketing_page(
            "Interest capture unavailable — HVTracker",
            "Temporarily unavailable",
            "Interest capture is offline right now.",
            "<div class='card'><p>The site can still be browsed, but the lead queue is unavailable on this environment. Try again later or reach out through GitHub issues.</p></div>",
            description="HVTracker interest capture is temporarily unavailable.",
        ),
        status_code=503,
    )


def _interest_thanks(title: str, message: str, repo: str | None = None) -> HTMLResponse:
    next_action = "<a class='button secondary' href='/alerts'>View alerts waitlist</a>"
    if repo:
        agent = find_agent(repo)
        if agent:
            next_action = f"<a class='button secondary' href='/agents/{agent['slug']}'>Back to {escape(agent['name'])}</a>"
    return HTMLResponse(
        _marketing_page(
            title,
            "Request saved",
            "You are on the list.",
            f"<div class='card'><p class='ok'>{escape(message)}</p><p>For now this is a human-reviewed queue, not an automated onboarding flow. That is intentional: it helps validate which alerts, exports, and sponsor offers are worth building first.</p></div><div class='actions'><a class='button' href='/'>Open leaderboard</a>{next_action}</div>",
            description=message,
        )
    )


def _queue_table_html(title: str, rows: list[dict], empty_copy: str) -> str:
    if not rows:
        return (
            "<div class='card'>"
            f"<h2>{escape(title)}</h2>"
            f"<p>{escape(empty_copy)}</p>"
            "</div>"
        )
    items: list[str] = []
    for row in rows:
        payload = row.get("payload") or {}
        payload_html = escape(json.dumps(payload, indent=2, sort_keys=True))
        created = row.get("created_at")
        created_text = created.isoformat() if hasattr(created, "isoformat") else escape(str(created))
        contact = escape(row.get("contact") or "—")
        items.append(
            "<div class='card'>"
            f"<h2>{escape(title[:-1] if title.endswith('s') else title)} #{row.get('id', '—')}</h2>"
            f"<p><strong>Repo:</strong> {escape(row.get('repo') or '—')}</p>"
            f"<p><strong>Contact:</strong> {contact}</p>"
            f"<p><strong>Status:</strong> {escape(row.get('status') or '—')}</p>"
            f"<p><strong>Created:</strong> {created_text}</p>"
            f"<pre style='white-space:pre-wrap;word-break:break-word;background:#f6f2e9;border:1px solid #d7d0c3;padding:12px;font-size:12px;line-height:1.5;overflow:auto'>{payload_html}</pre>"
            "</div>"
        )
    return f"<h2>{escape(title)}</h2>" + "".join(items)


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse, include_in_schema=False)
def admin_panel():
    submissions = db.list_queue("submissions", status="pending")
    corrections = db.list_queue("corrections", status="pending")
    queue_note = (
        "<div class='card'><p>This is a lightweight local review screen for the moderation queue. "
        "It is read-only for now: useful for opening the pending submissions and corrections that "
        "are already stored through the public forms.</p></div>"
    )
    if not db.enabled():
        queue_note = (
            "<div class='card'><p>The moderation queue needs <code>DATABASE_URL</code> to show real data. "
            "The route is now live, but this environment is running without the Postgres-backed queue.</p></div>"
        )
    body = (
        queue_note
        + _queue_table_html("Pending submissions", submissions, "No pending submissions.")
        + _queue_table_html("Pending corrections", corrections, "No pending corrections.")
    )
    return _marketing_page(
        "Admin queue — HVTracker",
        "Admin queue",
        "Review pending submissions and corrections.",
        body,
        description="HVTracker moderation queue for pending submissions and corrections.",
        path="/admin/",
    )


@app.get("/submit", response_class=HTMLResponse)
@app.get("/submit/", response_class=HTMLResponse, include_in_schema=False)
def submit_form():
    body = """
    <div class='card'>
      <h2>Submit an agent for listing</h2>
      <p>Submissions enter a moderation queue and appear after review. Keep it simple: repo, display name, optional category, and a contact email if you want follow-up.</p>
      <form method='post' action='/submit'>
        <label>GitHub repo (owner/name)
          <input name='repo' placeholder='owner/name' required>
        </label>
        <label>Display name
          <input name='name' placeholder='My Agent' required>
        </label>
        <label>Category (optional)
          <input name='category' placeholder='Coding Agents'>
        </label>
        <label>Contact email (optional)
          <input name='contact' type='email' placeholder='you@example.com'>
        </label>
        """ + HONEYPOT_HTML + """
        <div class='actions'>
          <button class='button' type='submit'>Submit for review</button>
        </div>
      </form>
    </div>
    """
    return _marketing_page(
        "Submit an agent — HVTracker",
        "Submission",
        "Suggest a project for the trust registry.",
        body,
        description="Submit an AI agent project for review and possible inclusion in the HVTracker trust registry.",
        path="/submit/",
    )


@app.post("/submit", response_class=HTMLResponse)
@app.post("/submit/", response_class=HTMLResponse, include_in_schema=False)
def submit_post(request: Request, repo: str = Form(...), name: str = Form(...),
                category: str = Form(""), contact: str = Form(""),
                website: str = Form("")):
    if website:
        return HTMLResponse(
            _marketing_page("Submission received — HVTracker", "Submission saved", "Your project is queued for review.",
                "<div class='card'><p class='ok'>Thanks. The submission is in the review queue.</p></div>",
                path="/submit/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path="/submit/"), status_code=429)
    over = _check_field_lengths(repo=repo, name=name, category=category, contact=contact)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Submission", over,
                f"<div class='card'><p>{escape(over)}</p></div><div class='actions'><a class='button' href='/submit/'>Back to form</a></div>",
                path="/submit/"), status_code=400)
    if contact.strip() and not _EMAIL_RE.match(contact.strip()):
        return HTMLResponse(
            _marketing_page("Invalid email — HVTracker", "Submission", "Please provide a valid email address.",
                "<div class='card'><p>The contact email does not look valid.</p></div><div class='actions'><a class='button' href='/submit/'>Back to form</a></div>",
                path="/submit/"), status_code=400)
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    if repo.count("/") != 1:
        return HTMLResponse(
            _marketing_page(
                "Invalid repo — HVTracker",
                "Submission",
                "Use the GitHub owner/name format.",
                "<div class='card'><p>Please submit the repository as <code>owner/name</code>, for example <code>openai/codex</code>.</p></div><div class='actions'><a class='button' href='/submit/'>Back to form</a></div>",
                description="Submit an AI agent project for review and possible inclusion in the HVTracker trust registry.",
                path="/submit/",
            ),
            status_code=400,
        )
    if not db.enabled():
        return _interest_unavailable()
    db.add_submission(repo, {"name": name.strip(), "category": category.strip()}, contact.strip() or None)
    return HTMLResponse(
        _marketing_page(
            "Submission received — HVTracker",
            "Submission saved",
            "Your project is queued for review.",
            "<div class='card'><p class='ok'>Thanks. The submission is in the review queue.</p><p>HVTracker reviews repos manually before adding them so the registry stays evidence-backed and comparable.</p></div><div class='actions'><a class='button' href='/'>Open leaderboard</a><a class='button secondary' href='/submit/'>Submit another</a></div>",
            description="Your AI agent project submission has been received by HVTracker.",
            path="/submit/",
        )
    )


@app.get("/correct", response_class=HTMLResponse)
@app.get("/correct/", response_class=HTMLResponse, include_in_schema=False)
def correct_form():
    body = """
    <div class='card'>
      <h2>Request a correction</h2>
      <p>Spotted wrong data on a listing? Send the repo, explain what is wrong, and optionally leave a contact email for follow-up.</p>
      <form method='post' action='/correct'>
        <label>GitHub repo (owner/name)
          <input name='repo' placeholder='owner/name' required>
        </label>
        <label>What's wrong?
          <textarea name='message' rows='5' placeholder='Describe the issue...' required></textarea>
        </label>
        <label>Contact email (optional)
          <input name='contact' type='email' placeholder='you@example.com'>
        </label>
        """ + HONEYPOT_HTML + """
        <div class='actions'>
          <button class='button' type='submit'>Send correction</button>
        </div>
      </form>
    </div>
    """
    return _marketing_page(
        "Request a correction — HVTracker",
        "Corrections",
        "Flag data that needs review.",
        body,
        description="Request a correction to an HVTracker project listing.",
        path="/correct/",
    )


@app.post("/correct", response_class=HTMLResponse)
@app.post("/correct/", response_class=HTMLResponse, include_in_schema=False)
def correct_post(request: Request, repo: str = Form(...), message: str = Form(...),
                 contact: str = Form(""), website: str = Form("")):
    if website:
        return HTMLResponse(
            _marketing_page("Correction received — HVTracker", "Correction saved", "The correction request is queued for review.",
                "<div class='card'><p class='ok'>Thanks.</p></div>", path="/correct/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path="/correct/"), status_code=429)
    over = _check_field_lengths(repo=repo, message=message, contact=contact)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Correction", over,
                f"<div class='card'><p>{escape(over)}</p></div>", path="/correct/"), status_code=400)
    if not db.enabled():
        return _interest_unavailable()
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    db.add_correction(repo, {"message": message.strip()}, contact.strip() or None)
    return HTMLResponse(
        _marketing_page(
            "Correction received — HVTracker",
            "Correction saved",
            "The correction request is queued for review.",
            "<div class='card'><p class='ok'>Thanks. The correction request is now in the review queue.</p><p>HVTracker reviews correction requests manually so trust signals stay accurate and auditable.</p></div><div class='actions'><a class='button' href='/'>Open leaderboard</a><a class='button secondary' href='/correct/'>Send another correction</a></div>",
            description="Your HVTracker correction request has been received.",
            path="/correct/",
        )
    )


@app.get("/alerts", response_class=HTMLResponse)
@app.get("/alerts/", response_class=HTMLResponse, include_in_schema=False)
def alerts_page():
    body = """
    <div class='grid'>
      <div class='card'>
        <span class='pill'>Early access</span>
        <h2 style='margin-top:10px'>What you would get</h2>
        <ul>
          <li>Rank-change alerts for agents you care about</li>
          <li>Trust-score drops and provenance regressions</li>
          <li>New compare pages and methodology launches</li>
        </ul>
      </div>
      <div class='card'>
        <span class='pill'>Why this exists</span>
        <h2 style='margin-top:10px'>This is a fake-door by design</h2>
        <p>I am validating demand before building accounts, saved watchlists, and alert pipelines. If enough teams ask for the same thing, it gets prioritized.</p>
      </div>
    </div>
    <div class='card'>
      <h2>Join the alerts waitlist</h2>
      <p>Leave your email and I will reach out when the first trust alerts are ready.</p>
      <form method='post' action='/alerts'>
        <label>Work email
          <input type='email' name='email' placeholder='you@company.com' required>
        </label>
        """ + HONEYPOT_HTML + """
        <div class='actions'>
          <button class='button' type='submit'>Join waitlist</button>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Alerts waitlist — HVTracker", "Growth", "Get trust alerts when agent risk changes.", body, description="Join the HVTracker alerts waitlist for rank changes, trust drops, and provenance regressions.", path="/alerts/"))


@app.post("/alerts", response_class=HTMLResponse)
@app.post("/alerts/", response_class=HTMLResponse, include_in_schema=False)
def alerts_post(request: Request, email: str = Form(...), role: str = Form(""), agents: str = Form(""),
                notes: str = Form(""), website: str = Form("")):
    if website:
        return HTMLResponse(
            _marketing_page("Alerts waitlist — HVTracker", "Thanks", "Thanks. I saved your alert request.",
                "<div class='card'><p class='ok'>Thanks.</p></div>", path="/alerts/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path="/alerts/"), status_code=429)
    over = _check_field_lengths(email=email, notes=notes)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Alerts", over,
                f"<div class='card'><p>{escape(over)}</p></div>", path="/alerts/"), status_code=400)
    if not _EMAIL_RE.match(email.strip()):
        return HTMLResponse(
            _marketing_page("Invalid email — HVTracker", "Alerts", "Please provide a valid email address.",
                "<div class='card'><p>That email does not look valid.</p></div>", path="/alerts/"), status_code=400)
    if not db.enabled():
        return _interest_unavailable()
    db.add_interest_signup(
        "alerts",
        email.strip().lower(),
        None,
        {
            "role": role.strip(),
            "agents": agents.strip(),
            "notes": notes.strip(),
            "source": "alerts-page",
        },
    )
    return _interest_thanks("Alerts waitlist — HVTracker", "Thanks. I saved your alert request.")


@app.get("/track/{slug}", response_class=HTMLResponse)
@app.get("/track/{slug}/", response_class=HTMLResponse, include_in_schema=False)
def track_agent_page(slug: str):
    agent = find_agent_by_slug(slug)
    if not agent:
        return HTMLResponse("<p>Agent not found.</p>", status_code=404)
    body = f"""
    <div class='grid'>
      <div class='card'>
        <span class='pill'>{escape(agent['name'])}</span>
        <h2 style='margin-top:10px'>Track this agent</h2>
        <p>Use this if you would want a lightweight watchlist for <strong>{escape(agent['name'])}</strong>: trust-score changes, provenance drift, maintenance drops, or comparison updates.</p>
      </div>
      <div class='card'>
        <span class='pill'>Signal first</span>
        <h2 style='margin-top:10px'>Not a finished product yet</h2>
        <p>This is intentionally simple. I want to see which agents teams actually care enough about to monitor before building dashboards and login flows.</p>
      </div>
    </div>
    <div class='card'>
      <h2>Join the watchlist queue</h2>
      <p>When the first tracked-agent workflow is ready, these are the people I will contact first.</p>
      <form method='post' action='/track/{escape(slug)}'>
        <label>Work email
          <input type='email' name='email' placeholder='you@company.com' required>
        </label>
        <label>Team or role
          <input type='text' name='role' placeholder='Security, platform, engineering leadership'>
        </label>
        <label>What would make this useful?
          <textarea name='notes' placeholder='Example: alert me when build provenance disappears, signed-commit coverage drops, or {escape(agent['name'])} falls behind similar tools.'></textarea>
        </label>
        """ + HONEYPOT_HTML + f"""
        <div class='actions'>
          <button class='button' type='submit'>Track {escape(agent['name'])}</button>
          <a class='button secondary' href='/agents/{escape(agent["slug"])}'>Back to profile</a>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page(f"Track {agent['name']} — HVTracker", "Watchlist", f"Track {agent['name']} changes before they surprise you.", body, description=f"Track {agent['name']} on HVTracker and get notified when important trust signals move.", path=f"/track/{agent['slug']}/"))


@app.post("/track/{slug}", response_class=HTMLResponse)
@app.post("/track/{slug}/", response_class=HTMLResponse, include_in_schema=False)
def track_agent_post(request: Request, slug: str, email: str = Form(...), role: str = Form(""),
                     notes: str = Form(""), website: str = Form("")):
    agent = find_agent_by_slug(slug)
    if not agent:
        return HTMLResponse("<p>Agent not found.</p>", status_code=404)
    if website:
        return HTMLResponse(
            _marketing_page(f"Track {agent['name']} — HVTracker", "Thanks", f"Thanks. I saved your request to track {agent['name']}.",
                "<div class='card'><p class='ok'>Thanks.</p></div>", path=f"/track/{agent['slug']}/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path=f"/track/{agent['slug']}/"), status_code=429)
    over = _check_field_lengths(email=email, role=role, notes=notes)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Track", over,
                f"<div class='card'><p>{escape(over)}</p></div>", path=f"/track/{agent['slug']}/"), status_code=400)
    if not _EMAIL_RE.match(email.strip()):
        return HTMLResponse(
            _marketing_page("Invalid email — HVTracker", "Track", "Please provide a valid email address.",
                "<div class='card'><p>That email does not look valid.</p></div>", path=f"/track/{agent['slug']}/"), status_code=400)
    if not db.enabled():
        return _interest_unavailable()
    db.add_interest_signup(
        "track-agent",
        email.strip().lower(),
        agent["repo"],
        {
            "role": role.strip(),
            "notes": notes.strip(),
            "source": f"track:{slug}",
        },
    )
    return _interest_thanks(f"Track {agent['name']} — HVTracker", f"Thanks. I saved your request to track {agent['name']}.", repo=agent["repo"])


@app.get("/sponsor", response_class=HTMLResponse)
@app.get("/sponsor/", response_class=HTMLResponse, include_in_schema=False)
def sponsor_page():
    body = """
    <div class='grid'>
      <div class='card'>
        <span class='pill'>Sponsor options</span>
        <h2 style='margin-top:10px'>Low-noise ways to partner</h2>
        <ul>
          <li>Category or report sponsorships</li>
          <li>Supported compare pages for relevant buyers</li>
          <li>Launch-week or research sponsorships</li>
        </ul>
      </div>
      <div class='card'>
        <span class='pill'>Good fit</span>
        <h2 style='margin-top:10px'>Who this is for</h2>
        <p>Agent infrastructure, observability, security, evaluation, and devtools companies that want to reach technical buyers without generic ad inventory.</p>
      </div>
    </div>
    <div class='card'>
      <h2>Start a sponsor conversation</h2>
      <p>Keep it short. I mostly need to know who you are, what audience you want, and whether you want sponsorship, research, or a custom data relationship.</p>
      <form method='post' action='/sponsor'>
        <label>Name
          <input type='text' name='name' placeholder='Your name' required>
        </label>
        <label>Company
          <input type='text' name='company' placeholder='Company name' required>
        </label>
        <label>Work email
          <input type='email' name='email' placeholder='you@company.com' required>
        </label>
        <label>What are you interested in?
          <textarea name='message' placeholder='Example: we sell agent observability and want to sponsor a category roundup or trust report aimed at platform and security teams.' required></textarea>
        </label>
        """ + HONEYPOT_HTML + """
        <div class='actions'>
          <button class='button' type='submit'>Send sponsor interest</button>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Sponsor HVTracker", "Commercial", "Reach teams evaluating AI agents with context, not banner spam.", body, description="Sponsor HVTracker to reach teams evaluating AI agents with trust and comparison context.", path="/sponsor/"))


@app.post("/sponsor", response_class=HTMLResponse)
@app.post("/sponsor/", response_class=HTMLResponse, include_in_schema=False)
def sponsor_post(request: Request, name: str = Form(...), company: str = Form(...),
                 email: str = Form(...), message: str = Form(...), website: str = Form("")):
    if website:
        return HTMLResponse(
            _marketing_page("Sponsor HVTracker", "Thanks", "Thanks. I saved your sponsorship inquiry.",
                "<div class='card'><p class='ok'>Thanks.</p></div>", path="/sponsor/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path="/sponsor/"), status_code=429)
    over = _check_field_lengths(name=name, email=email, message=message)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Sponsor", over,
                f"<div class='card'><p>{escape(over)}</p></div>", path="/sponsor/"), status_code=400)
    if not _EMAIL_RE.match(email.strip()):
        return HTMLResponse(
            _marketing_page("Invalid email — HVTracker", "Sponsor", "Please provide a valid email address.",
                "<div class='card'><p>That email does not look valid.</p></div>", path="/sponsor/"), status_code=400)
    if not db.enabled():
        return _interest_unavailable()
    db.add_interest_signup(
        "sponsor",
        email.strip().lower(),
        None,
        {
            "name": name.strip(),
            "company": company.strip(),
            "message": message.strip(),
            "source": "sponsor-page",
        },
    )
    return _interest_thanks("Sponsor HVTracker", "Thanks. I saved your sponsorship inquiry.")


@app.get("/data-api", response_class=HTMLResponse)
@app.get("/data-api/", response_class=HTMLResponse, include_in_schema=False)
def data_api_page():
    body = """
    <div class='grid'>
      <div class='card'>
        <span class='pill'>Available now</span>
        <h2 style='margin-top:10px'>Public layer</h2>
        <ul>
          <li>Free leaderboard browsing</li>
          <li>Public JSON snapshot</li>
          <li>Open methodology and specs</li>
          <li>Read-only REST API (v1)</li>
        </ul>
      </div>
      <div class='card'>
        <span class='pill'>Planned paid layer</span>
        <h2 style='margin-top:10px'>Commercial access</h2>
        <ul>
          <li>Higher-rate data access</li>
          <li>Historical exports and change feeds</li>
          <li>Watchlists, alerts, and shared team usage</li>
        </ul>
      </div>
    </div>
    <div class='card'>
      <h2>REST API v1</h2>
      <p>Two read-only endpoints are available now, no auth required. CORS-enabled for browser use.</p>
      <div class='card' style='margin-top:12px'>
        <h2 style='font-family:var(--font-mono);font-size:13px'><code>GET /api/v1/agents</code></h2>
        <p>Full agent leaderboard with trust scores, evidence grades, and metadata.</p>
        <pre style='background:var(--paper);border:1px solid var(--line);padding:12px;overflow-x:auto;font:13px var(--font-mono);border-radius:6px;margin-top:8px'><code>curl -s https://hvtracker.net/api/v1/agents | python -m json.tool | head</code></pre>
      </div>
      <div class='card' style='margin-top:12px'>
        <h2 style='font-family:var(--font-mono);font-size:13px'><code>GET /api/v1/graph</code></h2>
        <p>Dependency and ecosystem graph data for all tracked agents.</p>
        <pre style='background:var(--paper);border:1px solid var(--line);padding:12px;overflow-x:auto;font:13px var(--font-mono);border-radius:6px;margin-top:8px'><code>curl -s https://hvtracker.net/api/v1/graph | python -m json.tool | head</code></pre>
      </div>
      <div class='card' style='margin-top:12px'>
        <h2 style='font-family:var(--font-mono);font-size:13px'><code>POST /api/v1/scan</code></h2>
        <p>Bulk trust check for a whole dependency set — paste a requirements.txt, package.json, or MCP config and get a verdict per item. Powers the <a href='/scan/'>Scan your stack</a> tool.</p>
        <pre style='background:var(--paper);border:1px solid var(--line);padding:12px;overflow-x:auto;font:13px var(--font-mono);border-radius:6px;margin-top:8px'><code>curl -s https://hvtracker.net/api/v1/scan -H 'Content-Type: application/json' \
  -d '{"input": "langchain\ncrewai\nautogen"}' | python -m json.tool</code></pre>
      </div>
      <p style='margin-top:12px;color:var(--muted);font-size:13px'>Auth and rate quotas for a paid tier are intentionally out of scope for now.</p>
    </div>
    <div class='card'>
      <h2>MCP server — trust layer for agents</h2>
      <p>Add HVTracker as a <a href='https://modelcontextprotocol.io'>Model Context Protocol</a> server so a coding agent can check supply-chain trust <em>before</em> installing a dependency or connecting to an MCP server. Streamable HTTP, no auth, no install.</p>
      <pre style='background:var(--paper);border:1px solid var(--line);padding:12px;overflow-x:auto;font:13px var(--font-mono);border-radius:6px;margin-top:8px'><code>{
  "mcpServers": {
    "hvtracker": { "url": "https://hvtracker.net/mcp" }
  }
}</code></pre>
      <p style='margin-top:12px;color:var(--muted);font-size:13px'>Tools: <code>verify_mcp_server</code> (pre-connect "Safe Browsing for MCP" verdict), <code>check_agent_trust</code>, <code>search_agents</code>.</p>
    </div>
    <div class='card'>
      <h2>Early pricing stub</h2>
      <div class='grid'>
        <div class='card'>
          <span class='pill'>Free</span>
          <h2 style='margin-top:10px'>Public registry</h2>
          <p>Leaderboard, agent profiles, compare pages, methodology, and the public JSON layer.</p>
        </div>
        <div class='card'>
          <span class='pill'>Planned from $29/mo</span>
          <h2 style='margin-top:10px'>Builder</h2>
          <p>Email alerts, small watchlists, expanded exports, and early access to new comparison workflows.</p>
        </div>
        <div class='card'>
          <span class='pill'>Planned from $149/mo</span>
          <h2 style='margin-top:10px'>Team</h2>
          <p>Shared watchlists, deeper history, bulk exports, and commercial usage support.</p>
        </div>
      </div>
    </div>
    <div class='card'>
      <h2>Request API or data access</h2>
      <p>If you want to use HVTracker data commercially, tell me how. The point of this page is to validate which export shapes and usage rights are worth productizing first.</p>
      <form method='post' action='/data-api'>
        <label>Work email
          <input type='email' name='email' placeholder='you@company.com' required>
        </label>
        <label>Company or team
          <input type='text' name='company' placeholder='Company or project name'>
        </label>
        <label>What do you need?
          <textarea name='message' placeholder='Example: daily JSON export for internal evaluations, historical trust changes, compare data for content, or commercial redistribution rights.' required></textarea>
        </label>
        """ + HONEYPOT_HTML + """
        <div class='actions'>
          <button class='button' type='submit'>Request access</button>
          <a class='button secondary' href='/data.json'>Open public data</a>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Data API and pricing — HVTracker", "Data", "Public data today. Commercial access next.", body, description="Explore the HVTracker data API, exports, and future commercial access options.", path="/data-api/"))


@app.post("/data-api", response_class=HTMLResponse)
@app.post("/data-api/", response_class=HTMLResponse, include_in_schema=False)
def data_api_post(request: Request, email: str = Form(...), company: str = Form(""),
                  message: str = Form(...), website: str = Form("")):
    if website:
        return HTMLResponse(
            _marketing_page("Data API — HVTracker", "Thanks", "Thanks. I saved your request.",
                "<div class='card'><p class='ok'>Thanks.</p></div>", path="/data-api/"))
    if _is_rate_limited(request):
        return HTMLResponse(
            _marketing_page("Too many requests — HVTracker", "Slow down", "Please wait before submitting again.",
                "<div class='card'><p>Too many submissions from this address. Try again in a few minutes.</p></div>",
                path="/data-api/"), status_code=429)
    over = _check_field_lengths(email=email, message=message)
    if over:
        return HTMLResponse(
            _marketing_page("Input too long — HVTracker", "Data API", over,
                f"<div class='card'><p>{escape(over)}</p></div>", path="/data-api/"), status_code=400)
    if not _EMAIL_RE.match(email.strip()):
        return HTMLResponse(
            _marketing_page("Invalid email — HVTracker", "Data API", "Please provide a valid email address.",
                "<div class='card'><p>That email does not look valid.</p></div>", path="/data-api/"), status_code=400)
    if not db.enabled():
        return _interest_unavailable()
    db.add_interest_signup(
        "api-access",
        email.strip().lower(),
        None,
        {
            "company": company.strip(),
            "message": message.strip(),
            "source": "data-api-page",
        },
    )
    return _interest_thanks("Data API and pricing — HVTracker", "Thanks. I saved your API and data access request.")


# ---- Scheduler + startup --------------------------------------------------

def _pull_scorecard_cache() -> bool:
    """Refresh the baked scorecard cache from the `data` branch so live
    full/batch refreshes apply the latest OSSF scan rather than the image's
    deploy-time snapshot. Best-effort: on any failure the existing cache is
    left untouched. Returns True if the local cache was updated."""
    import urllib.request
    try:
        with urllib.request.urlopen(SCORECARD_CACHE_URL, timeout=20) as resp:
            raw = resp.read()
        data = json.loads(raw)
        agents = data.get("agents") if isinstance(data, dict) else None
        if not isinstance(agents, dict) or not agents:
            print("[scorecard] data-branch cache has no agents — keeping baked cache")
            return False
        tmp = SCORECARD_CACHE_PATH + ".tmp"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, SCORECARD_CACHE_PATH)
        print(f"[scorecard] pulled data-branch cache: {len(agents)} repos "
              f"(scanned {data.get('scanned_at', 'unknown')})")
        return True
    except Exception as e:
        print(f"[scorecard] data-branch cache pull failed ({e}) — keeping baked cache")
        return False


def _refresh(mode: str) -> bool:
    """Run a refresh cycle. Returns True on success, False on failure."""
    import fetch_and_build
    try:
        # Pull the latest OSSF scan from the data branch before every refresh —
        # including render-only, which now re-applies the cache to all agents so
        # fresh scores reach the live site on each deploy/restart, not just on a
        # GitHub-signal refresh cycle.
        _pull_scorecard_cache()
        fetch_and_build.run_refresh(mode)
        return True
    except Exception as e:  # never let a build error kill the scheduler thread
        import traceback
        print(f"[scheduler] refresh ({mode}) failed: {e}")
        traceback.print_exc()
        return False


def _compute_render_fingerprint() -> str:
    digest = hashlib.sha256()
    tracked_paths = [
        os.path.join(BASE_DIR, "fetch_and_build.py"),
        os.path.join(BASE_DIR, "template.html"),
        os.path.join(BASE_DIR, "compare", "index.html"),
        os.path.join(BASE_DIR, "og-v2.png"),
        os.path.join(BASE_DIR, "agents.json"),
    ]
    _css_path = os.path.join(BASE_DIR, "static", "site.css")
    if os.path.isfile(_css_path):
        tracked_paths.append(_css_path)
    # render_state.json lives on the volume in production (excluded from Docker
    # image by .dockerignore).  Include it when present so adding an agent
    # triggers a re-render; skip gracefully when the file doesn't exist yet.
    _rs_path = os.path.join(BASE_DIR, "data", "render_state.json")
    if os.path.isfile(_rs_path):
        tracked_paths.append(_rs_path)
    templates_dir = os.path.join(BASE_DIR, "templates")
    for name in sorted(os.listdir(templates_dir)):
        if name.endswith((".html", ".j2")):
            tracked_paths.append(os.path.join(templates_dir, name))
    blog_static_dir = os.path.join(BASE_DIR, "blog_static")
    if os.path.isdir(blog_static_dir):
        for name in sorted(os.listdir(blog_static_dir)):
            idx = os.path.join(blog_static_dir, name, "index.html")
            if os.path.isfile(idx):
                tracked_paths.append(idx)
    for path in tracked_paths:
        with open(path, "rb") as f:
            digest.update(path.removeprefix(BASE_DIR).encode("utf-8"))
            digest.update(b"\0")
            digest.update(f.read())
            digest.update(b"\0")
    return digest.hexdigest()


def _read_render_fingerprint() -> str | None:
    try:
        with open(RENDER_FINGERPRINT_PATH, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _write_render_fingerprint(fingerprint: str) -> None:
    with open(RENDER_FINGERPRINT_PATH, "w", encoding="utf-8") as f:
        f.write(fingerprint)


def _refresh_and_record(mode: str, fingerprint: str, trigger: str = "internal") -> bool:
    if not _refresh_lock.acquire(blocking=False):
        print(f"[scheduler] skipped refresh ({mode}) from {trigger}: another refresh is already running")
        _mark_refresh_status(
            in_progress=True,
            last_mode=mode,
            last_trigger=trigger,
            last_skipped_at=_utc_now_iso(),
            last_error="refresh skipped because another refresh is already running",
        )
        return False
    started_at = _utc_now_iso()
    _mark_refresh_status(
        in_progress=True,
        last_mode=mode,
        last_trigger=trigger,
        last_started_at=started_at,
        last_succeeded=None,
        last_error=None,
    )
    try:
        ok = _refresh(mode)
        completed_at = _utc_now_iso()
        if ok:
            _write_render_fingerprint(fingerprint)
        _mark_refresh_status(
            in_progress=False,
            last_mode=mode,
            last_trigger=trigger,
            last_completed_at=completed_at,
            last_succeeded=ok,
            last_error=None if ok else f"refresh failed in mode {mode}",
        )
        return ok
    finally:
        _refresh_lock.release()


def _seed_history_into_volume() -> int:
    """Copy daily history snapshots baked into the image into the volume if
    they're missing. Without prior days the leaderboard has no rank deltas,
    sparklines, or movers. Existing files on the volume are never overwritten,
    so today's freshly-written snapshot is preserved. Returns the number of
    files copied."""
    import shutil
    seed = os.path.join(BASE_DIR, "seed", "history")
    if not os.path.isdir(seed):
        return 0
    dest = os.path.join(OUTPUT_DIR, "output", "history")
    os.makedirs(dest, exist_ok=True)
    copied = 0
    for fn in sorted(os.listdir(seed)):
        if not fn.endswith(".json"):
            continue
        dst = os.path.join(dest, fn)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(seed, fn), dst)
            copied += 1
    if copied:
        print(f"[startup] seeded {copied} history snapshot(s) into volume")
    return copied


def _sync_prebuilt_to_volume() -> bool:
    """Copy the build-time rendered site into the volume so fresh HTML is
    served immediately on first boot. Once a volume has live data, do not
    copy prebuilt output over it; startup/render jobs will update generated
    files without downgrading fresher leaderboard data."""
    import shutil
    if not os.path.isdir(PREBUILT_DIR) or PREBUILT_DIR == OUTPUT_DIR:
        return False
    if os.path.isfile(DATA_PATH):
        print("[startup] existing volume data found — skipped prebuilt sync")
        return False
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copied = 0
    for root, dirs, files in os.walk(PREBUILT_DIR):
        rel = os.path.relpath(root, PREBUILT_DIR)
        dest = os.path.join(OUTPUT_DIR, rel)
        os.makedirs(dest, exist_ok=True)
        for f in files:
            if f == ".agents_hash":
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(dest, f))
            copied += 1
    print(f"[startup] synced {copied} pre-rendered files from image → volume")
    return copied > 0


def _has_missing_commit_rows() -> bool:
    """Detect broken generated rows where weekly_commits is missing."""
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return any(a.get("weekly_commits") is None for a in data.get("agents", []))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _has_pending_signal_rows() -> bool:
    """Detect provisional rows that still need their first signal refresh."""
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return any(a.get("pending_signals") for a in data.get("agents", []))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _refresh_verify_feed():
    """Daily: re-verify the provisional (open-lookup) repos in the public feed
    so their verdicts stay fresh. Curated repos are refreshed by the main cron;
    only the open-lookup ones need this. Gentle on the GitHub budget."""
    if not db.enabled():
        return
    import open_lookup
    token = os.environ.get("GITHUB_TOKEN", "")
    refreshed = 0
    for repo in db.verify_check_targets(limit=200):
        try:
            v = open_lookup.evaluate_open(repo, repo, token)
            if v.get("eligibility") == "ok":
                verify_log.record(v.get("resolved") or repo, None, v.get("grade"),
                                  v.get("trusted"), True, v.get("stars"))
                refreshed += 1
        except Exception:
            pass
        time.sleep(0.6)  # ~100/min, well within the authenticated GitHub budget
        if refreshed >= 150:
            break
    print(f"[scheduler] verify feed refresh complete: {refreshed} repo(s)")


def _startup():
    global _scheduler
    _sync_prebuilt_to_volume()
    seeded = _seed_history_into_volume()
    fingerprint = _compute_render_fingerprint()
    stored_fingerprint = _read_render_fingerprint()
    db.init_schema()
    # Sync agents table from agents.json on every startup.  agents.json is
    # the source of truth; the table is rebuilt from it.  upsert_agent is
    # idempotent and only `agents.json` writes to this table (submissions
    # and corrections go to separate tables), so this is safe to run
    # unconditionally — it keeps category/legacy/license-override edits
    # in sync without waiting for a manual reseed.
    #
    # We also track a hash of the agents.json content (stored on the volume)
    # to detect when the *content* actually changed across deploys. The
    # fingerprint above hashes templates + agents.json bytes together; the
    # render-only rebuild reads agents from the DB. If only agents.json
    # changed (e.g. an agent's category was edited), template fingerprints
    # match, but the render is still stale unless we explicitly trigger one.
    agents_changed = False
    if db.enabled():
        with open(os.path.join(BASE_DIR, "agents.json"), "rb") as f:
            agents_bytes = f.read()
        agents_hash = hashlib.sha256(agents_bytes).hexdigest()
        agents_seed = json.loads(agents_bytes)
        agents_hash_path = os.path.join(OUTPUT_DIR, ".agents_hash")
        try:
            prev_hash = open(agents_hash_path).read().strip()
        except OSError:
            prev_hash = ""
        seed_repos = {a["repo"] for a in agents_seed}
        db_repos = {a.get("repo") for a in db.load_agents()}
        if prev_hash != agents_hash or db_repos != seed_repos:
            for a in agents_seed:
                db.upsert_agent(a)
            # Remove agents from DB that were deleted from agents.json
            valid_repos = list(seed_repos)
            pruned = db.delete_agents_not_in(valid_repos)
            with open(agents_hash_path, "w") as f:
                f.write(agents_hash)
            agents_changed = True
            print(f"[startup] agents.json sync needed → synced {len(agents_seed)} entries into DB, pruned {pruned}")
        else:
            print(f"[startup] agents.json unchanged ({len(agents_seed)} entries) — DB sync skipped")
    # If the volume has no site yet, build one in the background so the service
    # comes up immediately and the site appears shortly after.
    if not os.path.isfile(DATA_PATH):
        threading.Thread(target=_refresh_and_record, args=("full", fingerprint, "startup"), daemon=True).start()
        print("[startup] no data.json on volume — kicked off initial full build")
    elif _has_missing_commit_rows():
        threading.Thread(target=_refresh_and_record, args=("repair-commits", fingerprint, "startup"), daemon=True).start()
        print("[startup] detected rows with missing commit counts — kicked off targeted repair refresh")
    elif os.environ.get("DISABLE_SCHEDULER") != "1" and _has_pending_signal_rows():
        threading.Thread(target=_refresh_and_record, args=("pending", fingerprint, "startup"), daemon=True).start()
        print("[startup] detected provisional rows — kicked off pending refresh")
    elif seeded > 0 or stored_fingerprint != fingerprint or agents_changed:
        # Re-render when:
        #   - we just dropped prior-day snapshots into a volume that already
        #     had a site rendered without them, or
        #   - templates/assets changed in the image, or
        #   - agents.json content changed since last deploy (DB resync above)
        threading.Thread(target=_refresh_and_record, args=("render", fingerprint, "startup"), daemon=True).start()
        if seeded > 0:
            print("[startup] history seeded into existing volume — kicked off render-only rebuild")
        elif stored_fingerprint != fingerprint:
            print("[startup] template/assets fingerprint changed — kicked off render-only rebuild")
        else:
            print("[startup] agents.json changed — kicked off render-only rebuild")

    if os.environ.get("DISABLE_SCHEDULER") != "1":
        from apscheduler.schedulers.background import BackgroundScheduler
        if _scheduler is None:
            _scheduler = BackgroundScheduler(timezone="UTC")
            _scheduler.add_job(
                lambda: _refresh_and_record("auto", _compute_render_fingerprint(), "scheduler"),
                "cron",
                hour="*/2",
                id="refresh",
                max_instances=1,
                coalesce=True,
            )
            # Fast, frequent GitHub-signal refresh (stars/forks/commits → HVTrust
            # /rank) for the whole registry. Cheap via GraphQL, so it can run
            # often without exhausting rate limits — this is what keeps the
            # leaderboard dynamic. The 2h "auto" batch still handles the heavier
            # PyPI/discovery/OSSF signals. Tunable via SIGNALS_REFRESH_MIN.
            signals_min = max(5, int(os.environ.get("SIGNALS_REFRESH_MIN", "30")))
            _scheduler.add_job(
                lambda: _refresh_and_record("signals", _compute_render_fingerprint(), "scheduler"),
                "cron",
                minute=f"*/{signals_min}",
                id="signals-refresh",
                max_instances=1,
                coalesce=True,
            )
            if db.enabled():
                _scheduler.add_job(
                    _refresh_verify_feed,
                    "cron",
                    hour=4,
                    id="verify-feed-refresh",
                    max_instances=1,
                    coalesce=True,
                )
            _scheduler.start()
        print(f"[startup] scheduler started (signals every {signals_min}m, full batch every 2h)")


def _shutdown():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def startup():
    _startup()


def shutdown():
    _shutdown()


def _install_mcp_route():
    route = mcp_server.fresh_streamable_http_app().routes[0]
    routes = app.router.routes
    routes[:] = [r for r in routes if getattr(r, "path", None) != "/mcp"]
    insert_at = next(
        (i for i, r in enumerate(routes) if getattr(r, "name", None) == "site"),
        len(routes),
    )
    routes.insert(insert_at, route)


# Trust-layer MCP server (Streamable HTTP) — register the SDK route directly
# before the static catch-all so POST /mcp is handled without a slash redirect.
# session_manager runs in _lifespan above.
_install_mcp_route()

# Static site LAST so /api, /badge, /submit, /correct take precedence.
app.mount("/", StaticFiles(directory=OUTPUT_DIR, html=True), name="site")
