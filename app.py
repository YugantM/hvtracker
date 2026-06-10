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
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import db


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
RENDER_FINGERPRINT_PATH = os.path.join(OUTPUT_DIR, ".render_fingerprint")

app = FastAPI(title="HVTracker", docs_url="/api/docs", openapi_url="/api/openapi.json")
_scheduler = None


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


@app.middleware("http")
async def _cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy-Report-Only"] = _CSP
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
    path = os.path.join(BASE_DIR, "data", "render_state.json")
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        return len(payload.get("rows") or [])
    except (OSError, json.JSONDecodeError, TypeError):
        return 0


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


# ---- JSON API ------------------------------------------------------------

@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz():
    d = load_data()
    source_fingerprint = _compute_render_fingerprint()
    stored_fingerprint = _read_render_fingerprint()
    return {
        "status": "ok",
        "agents": d.get("total", 0),
        "catalog_agents": _catalog_agent_count(),
        "source_render_agents": _source_render_count(),
        "updated": d.get("updated"),
        "git_sha": _runtime_git_sha(),
        "source_render_fingerprint": source_fingerprint,
        "stored_render_fingerprint": stored_fingerprint,
        "render_in_sync": bool(stored_fingerprint and stored_fingerprint == source_fingerprint),
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


@app.api_route("/compare", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/compare/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def compare_tool():
    if not os.path.isfile(COMPARE_TOOL_PATH):
        return HTMLResponse("<p>Compare tool is not available yet.</p>", status_code=503)
    with open(COMPARE_TOOL_PATH, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/og-v2.png")
def og_v2():
    return FileResponse(os.path.join(BASE_DIR, "og-v2.png"), media_type="image/png")


@app.get("/favicon.svg")
def favicon_svg():
    return FileResponse(os.path.join(BASE_DIR, "favicon.svg"), media_type="image/svg+xml")


@app.get("/haystack-logo.png")
def haystack_logo():
    return FileResponse(os.path.join(BASE_DIR, "haystack-logo.png"), media_type="image/png")


@app.get("/aipass-logo.png")
def aipass_logo():
    return FileResponse(os.path.join(BASE_DIR, "aipass-logo.png"), media_type="image/png")


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
    .site-header {{
      position:sticky; top:0; z-index:100;
      background:var(--paper);
      border-bottom:1px solid var(--line);
    }}
    .site-header-inner {{
      max-width:1200px; margin:0 auto; padding:14px 24px;
      display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;
    }}
    .logo {{ font-family:var(--font-mono); font-size:20px; font-weight:700; color:var(--ink); }}
    .logo span {{ color:var(--lobster); }}
    .site-nav {{
      margin-left:auto; font-family:var(--font-mono); font-size:11px;
      display:flex; gap:6px; flex-wrap:wrap;
    }}
    .site-nav a {{
      color:var(--muted); padding:5px 10px; border:1px solid transparent;
    }}
    .site-nav a:hover {{
      color:var(--ink); border-color:var(--line); background:var(--paper-2); text-decoration:none;
    }}
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
      .site-header-inner {{ gap:8px; }}
      .site-nav {{ margin-left:0; }}
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
  <header class="site-header">
    <div class="site-header-inner">
      <a href="/" class="logo">HV<span>Tracker</span></a>
      <nav class="site-nav" aria-label="Site">
        <a href="/">Leaderboard</a>
        <a href="/movers/">Movers</a>
        <a href="/use-cases/">Use cases</a>
        <a href="/methodology">Methodology</a>
        <a href="/compare/">Compare</a>
        <a href="/alerts/">Alerts</a>
        <a href="/data/">Data API</a>
        <a href="/sponsor/">Sponsor</a>
      </nav>
    </div>
  </header>
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

def _refresh(mode: str) -> bool:
    """Run a refresh cycle. Returns True on success, False on failure."""
    import fetch_and_build
    try:
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


def _refresh_and_record(mode: str, fingerprint: str) -> None:
    if _refresh(mode):
        _write_render_fingerprint(fingerprint)


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
    served immediately on deploy.  Preserves volume-only files (history
    snapshots, data.json from prior full builds) — only overwrites HTML,
    static assets, and render metadata that the build produced."""
    import shutil
    if not os.path.isdir(PREBUILT_DIR) or PREBUILT_DIR == OUTPUT_DIR:
        return False
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    copied = 0
    for root, dirs, files in os.walk(PREBUILT_DIR):
        rel = os.path.relpath(root, PREBUILT_DIR)
        dest = os.path.join(OUTPUT_DIR, rel)
        os.makedirs(dest, exist_ok=True)
        for f in files:
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


@app.on_event("startup")
def startup():
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
        if prev_hash != agents_hash:
            for a in agents_seed:
                db.upsert_agent(a)
            # Remove agents from DB that were deleted from agents.json
            valid_repos = [a["repo"] for a in agents_seed]
            pruned = db.delete_agents_not_in(valid_repos)
            with open(agents_hash_path, "w") as f:
                f.write(agents_hash)
            agents_changed = True
            print(f"[startup] agents.json changed → synced {len(agents_seed)} entries into DB, pruned {pruned}")
        else:
            print(f"[startup] agents.json unchanged ({len(agents_seed)} entries) — DB sync skipped")
    # If the volume has no site yet, build one in the background so the service
    # comes up immediately and the site appears shortly after.
    if not os.path.isfile(DATA_PATH):
        threading.Thread(target=_refresh_and_record, args=("full", fingerprint), daemon=True).start()
        print("[startup] no data.json on volume — kicked off initial full build")
    elif _has_missing_commit_rows():
        threading.Thread(target=_refresh_and_record, args=("repair-commits", fingerprint), daemon=True).start()
        print("[startup] detected rows with missing commit counts — kicked off targeted repair refresh")
    elif seeded > 0 or stored_fingerprint != fingerprint or agents_changed:
        # Re-render when:
        #   - we just dropped prior-day snapshots into a volume that already
        #     had a site rendered without them, or
        #   - templates/assets changed in the image, or
        #   - agents.json content changed since last deploy (DB resync above)
        threading.Thread(target=_refresh_and_record, args=("render", fingerprint), daemon=True).start()
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
            _scheduler.add_job(lambda: _refresh("auto"), "cron", hour="*/2", id="refresh")
            _scheduler.start()
        print("[startup] scheduler started (refresh every 2h)")


@app.on_event("shutdown")
def shutdown():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# Static site LAST so /api, /badge, /submit, /correct take precedence.
app.mount("/", StaticFiles(directory=OUTPUT_DIR, html=True), name="site")
