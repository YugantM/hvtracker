"""HVTracker web service.

Serves the pre-generated static site from the volume, exposes a dynamic JSON
API and live SVG badges sourced from data.json, accepts agent submissions /
corrections into Postgres, and runs the 2-hourly refresh in-process.
"""
from __future__ import annotations

import json
import os
import threading
import hashlib
import time
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", BASE_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)  # volume subdir may not exist on first boot
DATA_PATH = os.path.join(OUTPUT_DIR, "data.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
COMPARE_TOOL_PATH = os.path.join(BASE_DIR, "compare", "index.html")
RENDER_FINGERPRINT_PATH = os.path.join(OUTPUT_DIR, ".render_fingerprint")

app = FastAPI(title="HVTracker", docs_url="/api/docs", openapi_url="/api/openapi.json")

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

@app.get("/healthz")
def healthz():
    d = load_data()
    return {"status": "ok", "agents": d.get("total", 0), "updated": d.get("updated")}


@app.get("/api/agents")
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


@app.get("/api/agents/{owner}/{repo}")
def api_agent(owner: str, repo: str):
    agent = find_agent(f"{owner}/{repo}")
    if not agent:
        return JSONResponse({"error": "not found"}, status_code=404)
    return agent


@app.get("/api/feed")
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


def _marketing_page(title: str, eyebrow: str, heading: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg:#0b0d10; --surface:rgba(18,22,29,0.84); --border:rgba(142,154,176,0.24);
      --text:#eef2f6; --muted:#a8b3c2; --accent:#8fb3ff; --accent-soft:rgba(143,179,255,0.14);
      --mocha:#d8a657; --fresh:#2dd4bf; --font-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
      --font-sans:"Hanken Grotesk",system-ui,-apple-system,sans-serif;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; min-height:100vh; color:var(--text); font:15px/1.6 var(--font-sans);
      background:
        radial-gradient(circle at 14% -8%, rgba(45,212,191,0.16), transparent 28%),
        radial-gradient(circle at 85% 4%, rgba(216,166,87,0.13), transparent 24%),
        linear-gradient(180deg, #10141a 0%, #0b0d10 56%, #07090c 100%);
      padding:32px 20px;
    }}
    .page {{ max-width:860px; margin:0 auto; }}
    .shell {{
      border:1px solid var(--border); border-radius:18px; overflow:hidden;
      background:linear-gradient(135deg, rgba(255,255,255,0.055), rgba(255,255,255,0.014)), var(--surface);
      box-shadow:0 28px 90px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.05);
    }}
    .hero {{ padding:28px 28px 20px; border-bottom:1px solid rgba(255,255,255,0.08); }}
    .eyebrow {{
      display:inline-block; margin-bottom:12px; color:var(--mocha); font:11px var(--font-mono);
      text-transform:uppercase; letter-spacing:0.08em;
    }}
    h1 {{ margin:0 0 10px; font-size:34px; line-height:1.1; letter-spacing:-0.03em; }}
    .lede {{ margin:0; max-width:640px; color:var(--muted); }}
    .content {{ padding:24px 28px 30px; display:grid; gap:22px; }}
    .card {{
      border:1px solid var(--border); border-radius:14px; padding:18px;
      background:rgba(255,255,255,0.03);
    }}
    .card h2 {{ margin:0 0 10px; font-size:15px; }}
    .card p {{ margin:0 0 10px; color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:14px; }}
    .pill {{
      display:inline-block; padding:4px 9px; border-radius:999px; font:11px var(--font-mono);
      background:var(--accent-soft); color:var(--accent);
    }}
    ul {{ margin:10px 0 0 18px; padding:0; color:var(--muted); }}
    li + li {{ margin-top:6px; }}
    form {{ display:grid; gap:14px; }}
    label {{ display:grid; gap:6px; font-weight:600; }}
    input, textarea {{
      width:100%; border:1px solid rgba(142,154,176,0.32); border-radius:10px; padding:12px 13px;
      background:rgba(7,9,12,0.42); color:var(--text); font:14px var(--font-sans);
    }}
    textarea {{ min-height:120px; resize:vertical; }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
    .button {{
      display:inline-flex; align-items:center; justify-content:center; padding:11px 16px; border-radius:10px;
      background:var(--accent-soft); color:var(--text); border:1px solid var(--accent);
      font:700 12px var(--font-mono); text-decoration:none;
    }}
    .button.secondary {{
      background:rgba(255,255,255,0.035); color:var(--muted); border-color:var(--border);
    }}
    .button:hover {{ text-decoration:none; background:rgba(143,179,255,0.24); }}
    .button.secondary:hover {{ color:var(--text); border-color:var(--accent); }}
    .back {{ color:var(--muted); font:11px var(--font-mono); text-decoration:none; }}
    .back:hover {{ color:var(--accent); }}
    .ok {{ color:var(--fresh); font-weight:700; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="shell">
      <section class="hero">
        <div class="eyebrow">{escape(eyebrow)}</div>
        <h1>{escape(heading)}</h1>
        <p class="lede">HVTracker is still early, so these pages are intentionally lightweight. The goal is to validate who wants alerts, data access, and sponsorship before building heavier workflows.</p>
      </section>
      <section class="content">
        {body_html}
        <div class="actions">
          <a class="back" href="/">← Back to HVTracker</a>
        </div>
      </section>
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
        )
    )


@app.get("/submit", response_class=HTMLResponse)
def submit_form():
    return _page("submit.html")


@app.post("/submit", response_class=HTMLResponse)
def submit_post(repo: str = Form(...), name: str = Form(...),
                category: str = Form(""), contact: str = Form("")):
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    if repo.count("/") != 1:
        return HTMLResponse("<p>Invalid repo. Use <code>owner/name</code>.</p>", status_code=400)
    db.add_submission(repo, {"name": name.strip(), "category": category.strip()}, contact.strip() or None)
    return HTMLResponse("<p>Thanks — your submission is queued for review. "
                        "<a href='/'>Back to the leaderboard</a></p>")


@app.get("/correct", response_class=HTMLResponse)
def correct_form():
    return _page("correct.html")


@app.post("/correct", response_class=HTMLResponse)
def correct_post(repo: str = Form(...), message: str = Form(...), contact: str = Form("")):
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    db.add_correction(repo, {"message": message.strip()}, contact.strip() or None)
    return HTMLResponse("<p>Thanks — your correction is queued for review. "
                        "<a href='/'>Back to the leaderboard</a></p>")


@app.get("/alerts", response_class=HTMLResponse)
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
      <p>Tell me what you want tracked. A strong signal here is better than guessing what to ship next.</p>
      <form method='post' action='/alerts'>
        <label>Work email
          <input type='email' name='email' placeholder='you@company.com' required>
        </label>
        <label>Your role
          <input type='text' name='role' placeholder='Security engineer, founder, platform lead'>
        </label>
        <label>Agents or categories you care about
          <input type='text' name='agents' placeholder='Codex, Claude Code, browser agents, agent frameworks'>
        </label>
        <label>What alert would be useful first?
          <textarea name='notes' placeholder='Example: email me when a tracked agent loses provenance, drops below 70 HVTrust, or changes rank materially.'></textarea>
        </label>
        <div class='actions'>
          <button class='button' type='submit'>Join waitlist</button>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Alerts waitlist — HVTracker", "Growth", "Get trust alerts when agent risk changes.", body))


@app.post("/alerts", response_class=HTMLResponse)
def alerts_post(email: str = Form(...), role: str = Form(""), agents: str = Form(""), notes: str = Form("")):
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
        <div class='actions'>
          <button class='button' type='submit'>Track {escape(agent['name'])}</button>
          <a class='button secondary' href='/agents/{escape(agent["slug"])}'>Back to profile</a>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page(f"Track {agent['name']} — HVTracker", "Watchlist", f"Track {agent['name']} changes before they surprise you.", body))


@app.post("/track/{slug}", response_class=HTMLResponse)
def track_agent_post(slug: str, email: str = Form(...), role: str = Form(""), notes: str = Form("")):
    agent = find_agent_by_slug(slug)
    if not agent:
        return HTMLResponse("<p>Agent not found.</p>", status_code=404)
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
        <div class='actions'>
          <button class='button' type='submit'>Send sponsor interest</button>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Sponsor HVTracker", "Commercial", "Reach teams evaluating AI agents with context, not banner spam.", body))


@app.post("/sponsor", response_class=HTMLResponse)
def sponsor_post(name: str = Form(...), company: str = Form(...), email: str = Form(...), message: str = Form(...)):
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
        <div class='actions'>
          <button class='button' type='submit'>Request access</button>
          <a class='button secondary' href='/data.json'>Open public data</a>
        </div>
      </form>
    </div>
    """
    return HTMLResponse(_marketing_page("Data API and pricing — HVTracker", "Data", "Public data today. Commercial access next.", body))


@app.post("/data-api", response_class=HTMLResponse)
def data_api_post(email: str = Form(...), company: str = Form(""), message: str = Form(...)):
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

def _refresh(mode: str) -> None:
    import fetch_and_build
    try:
        fetch_and_build.run_refresh(mode)
    except Exception as e:  # never let a build error kill the scheduler thread
        print(f"[scheduler] refresh ({mode}) failed: {e}")


def _compute_render_fingerprint() -> str:
    digest = hashlib.sha256()
    tracked_paths = [
        os.path.join(BASE_DIR, "template.html"),
        os.path.join(BASE_DIR, "compare", "index.html"),
        os.path.join(BASE_DIR, "og-v2.png"),
        os.path.join(BASE_DIR, "agents.json"),
    ]
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
    _refresh(mode)
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
    seeded = _seed_history_into_volume()
    fingerprint = _compute_render_fingerprint()
    stored_fingerprint = _read_render_fingerprint()
    db.init_schema()
    # Seed the agents table from agents.json the first time the DB is empty.
    if db.enabled() and db.count_agents() == 0:
        with open(os.path.join(BASE_DIR, "agents.json")) as f:
            for a in json.load(f):
                db.upsert_agent(a)
        print(f"[startup] seeded agents table from agents.json")
    # If the volume has no site yet, build one in the background so the service
    # comes up immediately and the site appears shortly after.
    if not os.path.isfile(DATA_PATH):
        threading.Thread(target=_refresh_and_record, args=("full", fingerprint), daemon=True).start()
        print("[startup] no data.json on volume — kicked off initial full build")
    elif _has_missing_commit_rows():
        threading.Thread(target=_refresh_and_record, args=("repair-commits", fingerprint), daemon=True).start()
        print("[startup] detected rows with missing commit counts — kicked off targeted repair refresh")
    elif seeded > 0 or stored_fingerprint != fingerprint:
        # We just dropped prior-day snapshots into a volume that already had a
        # site rendered without them — or templates/assets changed in the image.
        # Re-render so rank deltas, sparklines, movers, and share metadata stay
        # in sync with the current deploy.
        threading.Thread(target=_refresh_and_record, args=("render", fingerprint), daemon=True).start()
        if seeded > 0:
            print("[startup] history seeded into existing volume — kicked off render-only rebuild")
        else:
            print("[startup] template/assets fingerprint changed — kicked off render-only rebuild")

    if os.environ.get("DISABLE_SCHEDULER") != "1":
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler(timezone="UTC")
        sched.add_job(lambda: _refresh("auto"), "cron", hour="*/2", id="refresh")
        sched.start()
        print("[startup] scheduler started (refresh every 2h)")


# Static site LAST so /api, /badge, /submit, /correct take precedence.
app.mount("/", StaticFiles(directory=OUTPUT_DIR, html=True), name="site")
