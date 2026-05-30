"""HVTracker web service.

Serves the pre-generated static site from the volume, exposes a dynamic JSON
API and live SVG badges sourced from data.json, accepts agent submissions /
corrections into Postgres, and runs the 2-hourly refresh in-process.
"""
from __future__ import annotations

import json
import os
import threading

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", BASE_DIR)
os.makedirs(OUTPUT_DIR, exist_ok=True)  # volume subdir may not exist on first boot
DATA_PATH = os.path.join(OUTPUT_DIR, "data.json")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

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
        with open(DATA_PATH, encoding="utf-8") as f:
            _cache["data"] = json.load(f)
        _cache["mtime"] = mtime
    return _cache["data"]


def find_agent(repo: str) -> dict | None:
    repo = repo.lower()
    for a in load_data().get("agents", []):
        if a["repo"].lower() == repo:
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


# ---- Submission / correction intake --------------------------------------

def _page(name: str) -> str:
    with open(os.path.join(TEMPLATES_DIR, name), encoding="utf-8") as f:
        return f.read()


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


# ---- Scheduler + startup --------------------------------------------------

def _refresh(mode: str) -> None:
    import fetch_and_build
    try:
        fetch_and_build.run_refresh(mode)
    except Exception as e:  # never let a build error kill the scheduler thread
        print(f"[scheduler] refresh ({mode}) failed: {e}")


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


@app.on_event("startup")
def startup():
    seeded = _seed_history_into_volume()
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
        threading.Thread(target=_refresh, args=("full",), daemon=True).start()
        print("[startup] no data.json on volume — kicked off initial full build")
    elif seeded > 0:
        # We just dropped prior-day snapshots into a volume that already had a
        # site rendered without them — re-render so rank deltas, sparklines,
        # and movers reflect the now-present history.
        threading.Thread(target=_refresh, args=("render",), daemon=True).start()
        print("[startup] history seeded into existing volume — kicked off render-only rebuild")

    if os.environ.get("DISABLE_SCHEDULER") != "1":
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler(timezone="UTC")
        sched.add_job(lambda: _refresh("auto"), "cron", hour="*/2", id="refresh")
        sched.start()
        print("[startup] scheduler started (refresh every 2h)")


# Static site LAST so /api, /badge, /submit, /correct take precedence.
app.mount("/", StaticFiles(directory=OUTPUT_DIR, html=True), name="site")
