#!/usr/bin/env python3
"""Fetch GitHub data for tracked agents and render index.html."""

import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

METHODOLOGY_VERSION = "v2.0"
DATA_SCHEMA_VERSION = "v0.1"


def get_repo(owner_repo: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner_repo}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def get_commit_activity(owner_repo: str) -> list:
    """Return list of weekly commit-count dicts for the last 52 weeks."""
    url = f"{GITHUB_API}/repos/{owner_repo}/stats/commit_activity"
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json() or []
        if r.status_code == 202:
            # GitHub is computing stats asynchronously; wait and retry
            time.sleep(5 * (attempt + 1))
            continue
        # Any other failure: skip gracefully
        return []
    return []


def _parse_link_last_page(link_header: str) -> tuple[int | None, str | None]:
    """Parse rel=\"last\" page number and URL from a GitHub Link header."""
    for part in link_header.split(","):
        if 'rel="last"' not in part:
            continue
        url_match = re.search(r"<([^>]+)>", part)
        page_match = re.search(r"[?&]page=(\d+)", part)
        page = int(page_match.group(1)) if page_match else None
        url = url_match.group(1) if url_match else None
        return page, url
    return None, None


def fetch_recent_commits(owner_repo: str, days: int = 30) -> int | None:
    """Count commits on the default branch in the last `days` days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{GITHUB_API}/repos/{owner_repo}/commits"
    params = {"since": since_iso, "per_page": 100}

    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        commits = r.json()
        if not isinstance(commits, list):
            return None

        link = r.headers.get("Link", "")
        if not link:
            count = len(commits)
        else:
            last_page, last_url = _parse_link_last_page(link)
            if last_page is None or last_page <= 1:
                count = len(commits)
            elif last_url:
                r_last = requests.get(last_url, headers=HEADERS, timeout=30)
                r_last.raise_for_status()
                last_commits = r_last.json()
                if not isinstance(last_commits, list):
                    return None
                count = (last_page - 1) * 100 + len(last_commits)
            else:
                count = last_page * 100

        print(f"Recent commits for {owner_repo}: {count}", file=sys.stderr)
        return count
    except Exception:
        return None


def fetch_npm_downloads(package_name: str) -> int | None:
    """Fetch last-week download count from npm. Returns None on any error."""
    encoded = quote(package_name, safe='')
    url = f"https://api.npmjs.org/downloads/point/last-week/{encoded}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("downloads")
        return None
    except Exception:
        return None


def fetch_hn_mentions(search_term: str, days: int = 30) -> int:
    """Count HN stories matching search_term in the last `days` days."""
    # Algolia HN Search API allows 10,000 requests/hour (~65 calls per build).
    since = int(time.time()) - days * 86400
    params = {
        "query": search_term,
        "tags": "story",
        "numericFilters": f"created_at_i>{since}",
    }
    url = f"https://hn.algolia.com/api/v1/search?{urlencode(params)}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return int(r.json().get("nbHits", 0))
        return 0
    except Exception:
        return 0


def fetch_pypi_downloads(package_name: str) -> int | None:
    """Fetch last-week download count from PyPI via pypistats. Returns None on any error."""
    url = f"https://pypistats.org/api/packages/{package_name}/recent"
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", {})
                time.sleep(1.2)  # ~1 req/1.2s — safe for pypistats rate limit
                return data.get("last_week")
            if r.status_code == 429:
                time.sleep(10.0)  # back off and retry once
                continue
            return None
        except Exception:
            return None
    return None


def fetch_npm_provenance(package_name: str) -> bool | None:
    """Check if the latest version of an npm package has provenance attestations."""
    encoded = quote(package_name, safe='@/')
    url = f"https://registry.npmjs.org/{encoded}/latest"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json().get("dist", {}).get("attestations") is not None
        return None
    except Exception:
        return None


def fetch_pypi_provenance(package_name: str) -> bool | None:
    """Check if a PyPI package's latest release has PEP 740 provenance attestations."""
    url = f"https://pypi.org/simple/{package_name}/"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        files = r.json().get("files", [])
        if not files:
            return None
        last_file = files[-1]
        return last_file.get("provenance") is not None
    except Exception:
        return None


def fetch_scorecard(owner_repo: str) -> dict | None:
    """Fetch OSSF Scorecard — tries deps.dev first, falls back to securityscorecards.dev."""
    # Primary: deps.dev
    try:
        encoded = quote(f"github.com/{owner_repo}", safe='')
        r = requests.get(f"https://api.deps.dev/v3/projects/{encoded}", timeout=15)
        if r.status_code == 200:
            sc = r.json().get("scorecard")
            if sc:
                overall = sc.get("overallScore", sc.get("score"))
                checks = {c["name"]: c.get("score", -1) for c in sc.get("checks", [])}
                return {"score": overall, "checks": checks}
    except Exception:
        pass
    # Fallback: securityscorecards.dev
    try:
        r = requests.get(
            f"https://api.securityscorecards.dev/projects/github.com/{owner_repo}",
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            overall = data.get("score")
            checks = {c["name"]: c.get("score", -1) for c in data.get("checks", [])}
            return {"score": overall, "checks": checks}
    except Exception:
        pass
    return None


def fetch_signed_commit_ratio(owner_repo: str, sample: int = 100) -> float | None:
    """Sample recent commits and return fraction with verified signatures (0.0–1.0)."""
    url = f"{GITHUB_API}/repos/{owner_repo}/commits"
    params = {"per_page": min(sample, 100)}
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if r.status_code != 200:
            return None
        commits = r.json()
        if not isinstance(commits, list) or not commits:
            return None
        verified = sum(
            1 for c in commits
            if c.get("commit", {}).get("verification", {}).get("verified")
        )
        return round(verified / len(commits), 3)
    except Exception:
        return None


def score_components(stars: int, days_since: int, recent_commits: int, forks: int) -> dict:
    """Compute the four score components. Reused by the leaderboard and profile pages."""
    stars_score = min(30, math.log1p(stars) / math.log1p(100_000) * 30)
    freshness_score = max(0.0, 25 * (1 - days_since / 180))
    activity_score = min(25, math.log1p(recent_commits) / math.log1p(100) * 25)
    community_score = min(20, math.log1p(forks) / math.log1p(20_000) * 20)
    return {
        "stars": round(stars_score, 1),
        "freshness": round(freshness_score, 1),
        "activity": round(activity_score, 1),
        "community": round(community_score, 1),
        "stars_pct": round(stars_score / 30 * 100, 1),
        "freshness_pct": round(freshness_score / 25 * 100, 1),
        "activity_pct": round(activity_score / 25 * 100, 1),
        "community_pct": round(community_score / 20 * 100, 1),
    }


def compute_score(repo: dict, weeks: list) -> float:
    pushed_at = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since = (datetime.now(timezone.utc) - pushed_at).days
    recent_commits = sum(w["total"] for w in weeks[-4:]) if weeks else 0
    c = score_components(repo["stargazers_count"], days_since, recent_commits, repo["forks_count"])
    return round(c["stars"] + c["freshness"] + c["activity"] + c["community"], 1)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_date(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")


def days_ago(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).days


def freshness_class(d: int) -> str:
    if d <= 7:
        return "fresh"
    if d <= 30:
        return "recent"
    if d <= 90:
        return "aging"
    return "stale"


def score_class(s: float) -> str:
    if s >= 70:
        return "score-high"
    if s >= 45:
        return "score-mid"
    return "score-low"


def _load_prior_snapshot(history_dir: str) -> dict | None:
    """Return the most recent history snapshot older than today, or None."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        candidates = sorted(
            [f for f in os.listdir(history_dir)
             if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f) and f[:-5] < today],
            reverse=True,
        )
        if not candidates:
            return None
        with open(os.path.join(history_dir, candidates[0]), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_previous_ranks(history_dir: str) -> dict[str, int]:
    """Load previous rankings from the most recent prior history snapshot."""
    prev = _load_prior_snapshot(history_dir)
    if not prev:
        return {}
    try:
        return {a["repo"].lower(): a["rank"] for a in prev.get("agents", [])}
    except (KeyError, TypeError):
        return {}


def load_previous_downloads(history_dir: str) -> dict[str, tuple[int, str]]:
    """Load previous download counts for use as fallback on PyPI 429."""
    prev = _load_prior_snapshot(history_dir)
    if not prev:
        return {}
    try:
        result = {}
        for a in prev.get("agents", []):
            dl = a.get("weekly_downloads")
            src = a.get("dl_source", "")
            if dl is not None:
                result[a["repo"].lower()] = (dl, src)
        return result
    except (KeyError, TypeError):
        return {}


def load_history(history_dir: str) -> list[dict]:
    """Load all history snapshots sorted chronologically. Returns list of dicts."""
    snapshots = []
    try:
        for f in sorted(os.listdir(history_dir)):
            if re.match(r"\d{4}-\d{2}-\d{2}\.json$", f):
                with open(os.path.join(history_dir, f), encoding="utf-8") as fh:
                    snap = json.load(fh)
                    snap["_date"] = f[:-5]
                    snapshots.append(snap)
    except Exception:
        pass
    return snapshots


def compute_movers(history: list[dict], window: int = 7) -> dict:
    """Compare latest snapshot vs `window` days ago. Returns {up: [...], down: [...]}."""
    if len(history) < 2:
        return {"up": [], "down": []}
    latest = history[-1]
    # Find snapshot closest to `window` days back
    baseline = history[0] if len(history) <= window else history[-min(window, len(history))]
    old_ranks = {a["repo"].lower(): a["rank"] for a in baseline.get("agents", [])}
    movers = []
    for a in latest.get("agents", []):
        repo = a["repo"].lower()
        old = old_ranks.get(repo)
        if old is None:
            continue
        delta = old - a["rank"]  # positive = improved
        if delta != 0:
            movers.append({"name": a["name"], "slug": re.sub(r"[^a-z0-9]+", "-", a["name"].lower()).strip("-"),
                           "rank": a["rank"], "delta": delta, "score": a["score"]})
    movers.sort(key=lambda m: m["delta"], reverse=True)
    up = [m for m in movers if m["delta"] > 0][:3]
    down = [m for m in movers if m["delta"] < 0][-3:]
    down.sort(key=lambda m: m["delta"])  # most negative first
    return {"up": up, "down": down}


def compute_sparklines(history: list[dict]) -> dict[str, list[dict]]:
    """Build per-agent rank history for sparkline rendering.
    Returns {repo_lower: [{date, rank, score}, ...]}."""
    sparklines: dict[str, list[dict]] = {}
    for snap in history:
        date = snap.get("_date", "")
        for a in snap.get("agents", []):
            key = a["repo"].lower()
            sparklines.setdefault(key, []).append({
                "date": date,
                "rank": a["rank"],
                "score": a["score"],
            })
    return sparklines


def render_sparkline_svg(points: list[dict], width: int = 200, height: int = 40) -> str:
    """Render a mini SVG sparkline for rank over time. Lower rank = higher on chart."""
    if len(points) < 2:
        return ""
    ranks = [p["rank"] for p in points]
    min_r, max_r = min(ranks), max(ranks)
    span = max(max_r - min_r, 1)
    n = len(ranks)
    coords = []
    for i, r in enumerate(ranks):
        x = round(i / (n - 1) * width, 1)
        y = round((r - min_r) / span * (height - 8) + 4, 1)  # 4px padding top/bottom
        coords.append(f"{x},{y}")
    path = "M" + "L".join(coords)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="display:block">'
        f'<path d="{path}" fill="none" stroke="#7c6af6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )


def rank_delta_display(delta: int | None, is_new: bool) -> str:
    """Return display string for rank delta."""
    if is_new:
        return "NEW"
    if delta is None or delta == 0:
        return "—"
    if delta > 0:
        return f"▲{delta}"
    return f"▼{abs(delta)}"


def rank_delta_class(delta: int | None, is_new: bool) -> str:
    """Return CSS class for rank delta."""
    if is_new:
        return "delta-new"
    if delta is None or delta == 0:
        return "delta-same"
    if delta > 0:
        return "delta-up"
    return "delta-down"


def run_eligibility_checks(rows: list[dict]) -> list[dict]:
    """Check automated eligibility criteria from the Eligibility Spec v1.0.

    Checks performed (all non-blocking warnings):
      §4.1.1 — no declared license
      §4.2.1 — no meaningful activity in trailing 12 months (days_ago >= 365)
      §5.1   — repository is archived
    §5.4 (repo 404/private) is already handled in fetch_one (returns None).

    Returns a list of violation dicts for the build report.
    """
    violations = []
    for r in rows:
        repo = r["repo"]
        if r.get("archived"):
            violations.append({"repo": repo, "criterion": "5.1", "detail": "repository is archived"})
        if r.get("license_spdx") is None:
            violations.append({"repo": repo, "criterion": "4.1.1", "detail": "no declared license (GitHub license field is null)"})
        if r.get("days_ago", 0) >= 365:
            violations.append({"repo": repo, "criterion": "4.2.1",
                                "detail": f"no meaningful activity in 12 months (last push {r.get('last_push', 'unknown')})"})

    if violations:
        print("\n── Eligibility Warnings (Eligibility Spec v1.0) ──────────────────────")
        for v in violations:
            print(f"  WARN [{v['criterion']}] {v['repo']}: {v['detail']}")
        print(f"  {len(violations)} warning(s). No agents removed automatically — owner review required.")
        print("────────────────────────────────────────────────────────────────────────\n")
    else:
        print("Eligibility check: all agents pass automated criteria.")

    return violations


def load_scorecard_cache(script_dir: str) -> dict:
    """Load scorecard-cache.json if present. Returns dict keyed by owner/repo."""
    path = os.path.join(script_dir, "scorecard-cache.json")
    if not os.path.isfile(path):
        print("scorecard-cache.json not found — scorecard data will be empty this run.")
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        agents = data.get("agents", {})
        print(f"Loaded scorecard cache: {len(agents)} repos (scanned {data.get('scanned_at', 'unknown')})")
        return agents
    except Exception as e:
        print(f"WARN: failed to load scorecard cache: {e}")
        return {}


def generate_data_endpoints(script_dir: str, data_output: dict, rows: list[dict], history_dir: str, now_str: str) -> None:
    """Generate stable /data/ endpoint files."""
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(os.path.join(data_dir, "agents"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "signals"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "history"), exist_ok=True)

    meta = {
        "schema_version": DATA_SCHEMA_VERSION,
        "generated_at": now_str,
        "methodology_version": METHODOLOGY_VERSION,
        "license": "CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/",
    }

    # /data/latest.json — full snapshot
    latest = {**meta, **data_output}
    with open(os.path.join(data_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, separators=(",", ":"), ensure_ascii=False)

    # /data/history/<YYYY-MM-DD>.json — copy of today's snapshot
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(data_dir, "history", f"{today_utc}.json"), "w", encoding="utf-8") as f:
        json.dump({**meta, **data_output}, f, separators=(",", ":"), ensure_ascii=False)

    # Load last 90 days of history for per-agent files
    history_by_date: dict[str, dict] = {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    for fname in sorted(os.listdir(history_dir)):
        if not fname.endswith(".json"):
            continue
        date_str = fname[:-5]
        if date_str < cutoff:
            continue
        try:
            with open(os.path.join(history_dir, fname), encoding="utf-8") as f:
                snap = json.load(f)
            history_by_date[date_str] = {a["repo"].lower(): a for a in snap.get("agents", [])}
        except Exception:
            pass

    # /data/agents/<slug>.json — per-agent with 90d history
    slug_map = {r["repo"].lower(): r["slug"] for r in rows}
    for agent in data_output["agents"]:
        repo_key = agent["repo"].lower()
        slug = slug_map.get(repo_key, repo_key.replace("/", "-"))
        history_points = []
        for date_str in sorted(history_by_date.keys()):
            snap_agent = history_by_date[date_str].get(repo_key)
            if snap_agent:
                history_points.append({
                    "date": date_str,
                    "rank": snap_agent.get("rank"),
                    "score": snap_agent.get("score"),
                    "stars": snap_agent.get("stars"),
                })
        agent_doc = {**meta, **agent, "history": history_points}
        with open(os.path.join(data_dir, "agents", f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(agent_doc, f, separators=(",", ":"), ensure_ascii=False)

    # /data/signals/scorecard.json
    scorecard_list = [
        {
            "repo": a["repo"],
            "name": a["name"],
            "scorecard_score": a.get("scorecard_score"),
            "scorecard_checks": a.get("scorecard_checks", {}),
            "signed_commits_ratio": a.get("signed_commits_ratio"),
        }
        for a in data_output["agents"]
    ]
    with open(os.path.join(data_dir, "signals", "scorecard.json"), "w", encoding="utf-8") as f:
        json.dump({**meta, "agents": scorecard_list}, f, separators=(",", ":"), ensure_ascii=False)

    # /data/signals/provenance.json
    provenance_list = [
        {
            "repo": a["repo"],
            "name": a["name"],
            "has_provenance": a.get("has_provenance"),
            "npm_provenance": a.get("npm_provenance"),
            "pypi_provenance": a.get("pypi_provenance"),
        }
        for a in data_output["agents"]
    ]
    with open(os.path.join(data_dir, "signals", "provenance.json"), "w", encoding="utf-8") as f:
        json.dump({**meta, "agents": provenance_list}, f, separators=(",", ":"), ensure_ascii=False)

    # /data/index.html
    agent_links = "\n".join(
        f'    <li><a href="/data/agents/{slug_map.get(a["repo"].lower(), a["repo"].replace("/","-"))}.json">'
        f'/data/agents/{slug_map.get(a["repo"].lower(), a["repo"].replace("/","-"))}.json</a> — {a["name"]}</li>'
        for a in data_output["agents"]
    )
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>HVTracker — Data Endpoints</title>
  <link rel="stylesheet" href="/spec/spec.css">
  <style>body{{max-width:800px;margin:2rem auto;padding:0 1rem;font-family:system-ui,sans-serif}}</style>
</head>
<body>
  <h1>HVTracker Data Endpoints</h1>
  <p>All endpoints are static JSON files updated daily at 06:00 UTC. CORS is open (<code>Access-Control-Allow-Origin: *</code>). License: <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</p>
  <p>Schema version: <strong>{DATA_SCHEMA_VERSION}</strong> · Methodology: <strong>{METHODOLOGY_VERSION}</strong> · Last generated: {now_str}</p>

  <h2>Core</h2>
  <ul>
    <li><a href="/data/latest.json">/data/latest.json</a> — Full current snapshot (all agents, all fields)</li>
    <li><a href="/data/history/{today_utc}.json">/data/history/YYYY-MM-DD.json</a> — Daily snapshots (e.g. <a href="/data/history/{today_utc}.json">{today_utc}</a>)</li>
  </ul>

  <h2>Signal Subsets</h2>
  <ul>
    <li><a href="/data/signals/scorecard.json">/data/signals/scorecard.json</a> — OSSF Scorecard + signed commits for all agents</li>
    <li><a href="/data/signals/provenance.json">/data/signals/provenance.json</a> — Supply-chain provenance signals for all agents</li>
  </ul>

  <h2>Per-Agent (with 90-day history)</h2>
  <ul>
{agent_links}
  </ul>
</body>
</html>"""
    with open(os.path.join(data_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"Generated data endpoints under data/ ({len(data_output['agents'])} agent files).")


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_path = os.path.join(script_dir, "agents.json")
    data_path = os.path.join(script_dir, "data.json")

    scorecard_cache = load_scorecard_cache(script_dir)

    with open(agents_path) as f:
        agents = json.load(f)

    # De-duplicate by repo path (agents.json may have accidental dupes)
    seen: set[str] = set()
    deduped = []
    for a in agents:
        key = a["repo"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    agents = deduped

    # Split active vs legacy agents — legacy entries are fetched but rendered separately
    legacy_agents = [a for a in agents if a.get("status") == "legacy"]
    agents = [a for a in agents if a.get("status") != "legacy"]

    # Load previous rankings and downloads from the most recent daily history snapshot.
    # Using history/ (not data.json) means deltas always compare against the prior
    # calendar day's run — unaffected by manual commits or code pushes during the day.
    history_dir = os.path.join(script_dir, "output", "history")
    os.makedirs(history_dir, exist_ok=True)
    prev_ranks = load_previous_ranks(history_dir)
    prev_downloads = load_previous_downloads(history_dir)
    history = load_history(history_dir)
    sparkline_data = compute_sparklines(history)

    def fetch_one(agent: dict) -> dict | None:
        repo_id = agent["repo"]
        name = agent.get("name", repo_id.split("/")[1])
        category = agent.get("category", "")
        npm_pkg = agent.get("npm_package", "")
        try:
            repo = get_repo(repo_id)
        except requests.HTTPError as e:
            print(f"SKIP {repo_id}: {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"ERROR {repo_id}: {e}", file=sys.stderr)
            return None

        weeks = get_commit_activity(repo_id)
        score = compute_score(repo, weeks)
        d = days_ago(repo["pushed_at"])
        # Use Stats API 4-week sum for the display column.
        # Fall back to Commits API when Stats returned nothing, or when the repo
        # pushed recently but the 4-week sum is zero (Stats API serves stale cache).
        commits_4wk = sum(w["total"] for w in weeks[-4:]) if weeks else None
        if commits_4wk is None or (commits_4wk == 0 and (not weeks or d <= 7)):
            commits_4wk = fetch_recent_commits(repo_id)
        recent_commits = commits_4wk
        # Flag cells where Stats API may still be stale (recent push, very low count).
        commits_low_confidence = bool(d <= 7 and (recent_commits or 0) < 10)

        # Fetch npm downloads + provenance in parallel (npm API has no strict rate limit)
        pypi_pkg = agent.get("pypi_package", "")
        npm_dl = fetch_npm_downloads(npm_pkg) if npm_pkg else None
        npm_prov = fetch_npm_provenance(npm_pkg) if npm_pkg else None
        signed_ratio = fetch_signed_commit_ratio(repo_id)
        print(f"OK  {repo_id:<45} score={score:5.1f}")

        return {
            "name": name,
            "category": category,
            "repo": repo_id,
            "url": repo["html_url"],
            "stars": repo["stargazers_count"],
            "stars_fmt": fmt_num(repo["stargazers_count"]),
            "forks": repo["forks_count"],
            "forks_fmt": fmt_num(repo["forks_count"]),
            "last_push": fmt_date(repo["pushed_at"]),
            "days_ago": d,
            "freshness_class": freshness_class(d),
            "weekly_commits": recent_commits,
            "commits_low_confidence": commits_low_confidence,
            "score": score,
            "score_class": score_class(score),
            "description": (repo.get("description") or "")[:120],
            "language": repo.get("language") or "",
            "open_issues": repo.get("open_issues_count", 0),
            "archived": repo.get("archived", False),
            "license_spdx": (repo.get("license") or {}).get("spdx_id") or None,
            "npm_package": npm_pkg if npm_pkg else "",
            "pypi_package": pypi_pkg if pypi_pkg else "",
            "npm_dl": npm_dl,
            "npm_provenance": npm_prov,
            "signed_commits_ratio": signed_ratio,
            "weekly_downloads": None,  # filled in serial pass below
            "dl_source": "",
        }

    rows = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_one, a): a for a in agents}
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.append(result)

    legacy_rows = []
    if legacy_agents:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(fetch_one, a): a for a in legacy_agents}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    result["status"] = "legacy"
                    legacy_rows.append(result)

    hn_terms = {
        a["repo"].lower(): a["hn_search_term"]
        for a in agents
        if a.get("hn_search_term")
    }
    for row in rows:
        term = hn_terms.get(row["repo"].lower())
        if term:
            row["hn_mentions_30d"] = fetch_hn_mentions(term)
            time.sleep(0.3)
        else:
            row["hn_mentions_30d"] = None

    # Fetch PyPI downloads serially to respect pypistats ~1 req/s rate limit.
    # (npm was already fetched in parallel above; combine here.)
    # On 429, fall back to the previous run's cached value so the table never goes blank.
    print("\nFetching PyPI downloads (serial, with cached fallback on 429)...")
    for row in rows:
        pypi_pkg = row.get("pypi_package", "")
        repo_key = row["repo"].lower()
        dl_parts = []
        if row.get("npm_dl") is not None:
            dl_parts.append(("npm", row["npm_dl"]))
        if pypi_pkg:
            pypi_dl = fetch_pypi_downloads(pypi_pkg)
            if pypi_dl is not None:
                dl_parts.append(("pypi", pypi_dl))
            else:
                # 429 or error — use last known good value from previous run
                cached = prev_downloads.get(repo_key)
                if cached:
                    cached_count, cached_src = cached
                    row["weekly_downloads"] = cached_count
                    row["dl_source"] = cached_src
                    print(f"  dl {row['repo']:<45} {cached_count:,} ({cached_src}) [cached fallback]")
                    continue
        if dl_parts:
            row["weekly_downloads"] = sum(dl for _, dl in dl_parts)
            row["dl_source"] = "+".join(src for src, _ in dl_parts)
            print(f"  dl {row['repo']:<45} {row['weekly_downloads']:,} ({row['dl_source']})")

    # Fetch PyPI provenance serially (pypi.org Simple API, ~1 req/s to be safe)
    print("\nFetching PyPI provenance (serial)...")
    for row in rows:
        pypi_pkg = row.get("pypi_package", "")
        if pypi_pkg:
            row["pypi_provenance"] = fetch_pypi_provenance(pypi_pkg)
            time.sleep(0.5)
        else:
            row["pypi_provenance"] = None

    # Load OSSF Scorecard from weekly CLI cache (scorecard-cache.json).
    # Falls back to API if cache misses, then to None.
    print("\nLoading OSSF Scorecard from cache...")
    cache_hits = 0
    api_hits = 0
    for row in rows:
        repo_key = row["repo"]
        cached = scorecard_cache.get(repo_key)
        if cached:
            row["scorecard_score"] = cached["score"]
            row["scorecard_checks"] = cached["checks"]
            cache_hits += 1
        else:
            # Cache miss — try live API as fallback
            sc = fetch_scorecard(repo_key)
            if sc:
                row["scorecard_score"] = sc["score"]
                row["scorecard_checks"] = sc["checks"]
                api_hits += 1
            else:
                row["scorecard_score"] = None
                row["scorecard_checks"] = {}
    print(f"  Scorecard: {cache_hits} from cache, {api_hits} from API, "
          f"{len(rows)-cache_hits-api_hits} unavailable.")

    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

    run_eligibility_checks(rows)

    # Add formatted download counts and slug/breakdown for template rendering
    for row in rows:
        dl = row.get("weekly_downloads")
        row["downloads_fmt"] = f"{dl:,}" if dl is not None else "—"
        row["slug"] = slugify(row["name"])
        row["score_breakdown"] = score_components(
            row["stars"],
            row["days_ago"],
            row.get("weekly_commits") or 0,
            row["forks"],
        )
        # Provenance summary for template rendering
        prov_signals = []
        if row.get("npm_provenance"):
            prov_signals.append("npm")
        if row.get("pypi_provenance"):
            prov_signals.append("pypi")
        row["provenance_sources"] = prov_signals
        row["has_provenance"] = len(prov_signals) > 0
        sc = row.get("scorecard_score")
        row["scorecard_fmt"] = f"{sc:.1f}" if sc is not None else None
        sr = row.get("signed_commits_ratio")
        row["signed_commits_pct"] = round(sr * 100) if sr is not None else None

    # Compute category ranks (within each category, sorted by score)
    cat_groups: dict[str, list[dict]] = {}
    for row in rows:
        cat = row.get("category", "")
        if cat:
            cat_groups.setdefault(cat, []).append(row)
    for cat_agents in cat_groups.values():
        cat_agents.sort(key=lambda x: x["score"], reverse=True)
        for j, row in enumerate(cat_agents, 1):
            row["category_rank"] = j

    # Compute rank deltas
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for row in rows:
        repo_key = row["repo"].lower()
        old_rank = prev_ranks.get(repo_key)
        if old_rank is None:
            row["previous_rank"] = None
            row["rank_delta"] = None
            row["rank_delta_display"] = rank_delta_display(None, True)
            row["rank_delta_class"] = rank_delta_class(None, True)
            row["rank_delta_sort"] = 9999  # sentinel for client-side sort (NEW agents)
        else:
            delta = old_rank - row["rank"]  # positive = improved (moved up)
            row["previous_rank"] = old_rank
            row["rank_delta"] = delta
            row["rank_delta_display"] = rank_delta_display(delta, False)
            row["rank_delta_class"] = rank_delta_class(delta, False)
            row["rank_delta_sort"] = delta

    # Collect category metadata for the template
    category_order = [
        "Coding Agents",
        "Agent Frameworks",
        "Workflow Platforms",
        "Browser & Computer Use",
        "LLM Gateways & Infra",
        "Memory & Knowledge",
        "Research & Data",
        "Multi-Agent Systems",
    ]
    categories = []
    for cat in category_order:
        if cat in cat_groups:
            categories.append({"name": cat, "count": len(cat_groups[cat])})

    # Write data.json (machine-readable leaderboard)
    data_output = {
        "updated": now_str,
        "methodology_version": METHODOLOGY_VERSION,
        "total": len(rows),
        "agents": [
            {
                "name": r["name"],
                "repo": r["repo"],
                "url": r["url"],
                "rank": r["rank"],
                "previous_rank": r["previous_rank"],
                "rank_delta": r["rank_delta"],
                "stars": r["stars"],
                "stars_fmt": r.get("stars_fmt", ""),
                "forks": r["forks"],
                "forks_fmt": r.get("forks_fmt", ""),
                "last_push": r["last_push"],
                "days_ago": r["days_ago"],
                "weekly_commits": r["weekly_commits"],
                "commits_low_confidence": r.get("commits_low_confidence", False),
                "score": r["score"],
                "description": r["description"],
                "language": r["language"],
                "open_issues": r["open_issues"],
                "category": r.get("category", ""),
                "category_rank": r.get("category_rank"),
                "npm_package": r.get("npm_package", ""),
                "pypi_package": r.get("pypi_package", ""),
                "weekly_downloads": r.get("weekly_downloads"),
                "dl_source": r.get("dl_source", ""),
                "hn_mentions_30d": r.get("hn_mentions_30d"),
                "has_provenance": r.get("has_provenance"),
                "npm_provenance": r.get("npm_provenance"),
                "pypi_provenance": r.get("pypi_provenance"),
                "signed_commits_ratio": r.get("signed_commits_ratio"),
                "scorecard_score": r.get("scorecard_score"),
                "scorecard_checks": r.get("scorecard_checks", {}),
            }
            for r in rows
        ],
    }
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data_output, f, indent=2, ensure_ascii=False)
    print(f"\nWrote data.json with {len(rows)} agents.")

    # Historical snapshots enable trend analysis and are core IP — never delete these files.
    history_dir = os.path.join(script_dir, "output", "history")
    os.makedirs(history_dir, exist_ok=True)
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history_path = os.path.join(history_dir, f"{today_utc}.json")
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(data_output, f, indent=2, ensure_ascii=False)
    print(f"Wrote history snapshot {history_path}.")

    generate_data_endpoints(script_dir, data_output, rows, history_dir, now_str)

    templates_dir = os.path.join(script_dir, "templates")
    env = Environment(
        loader=FileSystemLoader([templates_dir, script_dir]),
        autoescape=True,
    )

    movers = compute_movers(history)

    # Sort legacy rows by stars descending for display
    for lr in legacy_rows:
        lr["slug"] = slugify(lr["name"])
    legacy_rows.sort(key=lambda x: x.get("stars", 0), reverse=True)

    tmpl = env.get_template("template.html")
    html = tmpl.render(
        rows=rows,
        legacy_rows=legacy_rows,
        updated=now_str,
        total=len(rows),
        categories=categories,
        movers=movers,
        history_days=len(history),
    )
    out_path = os.path.join(script_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Built index.html with {len(rows)} agents.")

    # Compute sibling links per agent (top-5 in same category, excluding self)
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        cat = r.get("category", "")
        if cat:
            by_cat.setdefault(cat, []).append(r)
    for cat_rows in by_cat.values():
        cat_rows.sort(key=lambda x: x["score"], reverse=True)
    for row in rows:
        cat = row.get("category", "")
        siblings = [s for s in by_cat.get(cat, []) if s["slug"] != row["slug"]][:5]
        row["siblings"] = [
            {"name": s["name"], "slug": s["slug"], "score": s["score"], "rank": s["rank"]}
            for s in siblings
        ]

    # Per-agent profile pages — /agents/<slug>/index.html
    agent_tmpl = env.get_template("agent.html.j2")
    agents_dir = os.path.join(script_dir, "agents")
    os.makedirs(agents_dir, exist_ok=True)
    for row in rows:
        repo_key = row["repo"].lower()
        points = sparkline_data.get(repo_key, [])
        row["sparkline_svg"] = render_sparkline_svg(points)
        row["rank_history"] = points
        slug_dir = os.path.join(agents_dir, row["slug"])
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(agent_tmpl.render(row=row, total=len(rows), updated=now_str))

    for row in legacy_rows:
        repo_key = row["repo"].lower()
        points = sparkline_data.get(repo_key, [])
        row["sparkline_svg"] = render_sparkline_svg(points)
        row["rank_history"] = points
        row["siblings"] = []
        slug_dir = os.path.join(agents_dir, row["slug"])
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(agent_tmpl.render(row=row, total=len(rows), updated=now_str))
    print(f"Built {len(rows)} active + {len(legacy_rows)} legacy agent profile pages under agents/.")

    # sitemap.xml — /, /methodology, all /agents/<slug>
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from specs import ALL_SPECS as _ALL_SPECS
    sitemap_urls = [
        ("https://hvtracker.net/", "1.0", "daily"),
        ("https://hvtracker.net/methodology", "0.5", "monthly"),
        ("https://hvtracker.net/spec/", "0.4", "monthly"),
    ]
    for spec in _ALL_SPECS:
        sitemap_urls.append((
            f"https://hvtracker.net/spec/{spec['slug']}/{spec['version']}",
            "0.4", "monthly"
        ))
    for row in rows:
        sitemap_urls.append((f"https://hvtracker.net/agents/{row['slug']}", "0.8", "daily"))
    for row in legacy_rows:
        sitemap_urls.append((f"https://hvtracker.net/agents/{row['slug']}", "0.4", "monthly"))
    sitemap_urls += [
        ("https://hvtracker.net/data/", "0.6", "daily"),
        ("https://hvtracker.net/data/latest.json", "0.7", "daily"),
        ("https://hvtracker.net/data/signals/scorecard.json", "0.5", "daily"),
        ("https://hvtracker.net/data/signals/provenance.json", "0.5", "daily"),
    ]
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, prio, freq in sitemap_urls:
        sitemap_lines.append(
            f"  <url><loc>{loc}</loc><lastmod>{today_iso}</lastmod>"
            f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        )
    sitemap_lines.append("</urlset>")
    with open(os.path.join(script_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(sitemap_lines) + "\n")
    print(f"Wrote sitemap.xml with {len(sitemap_urls)} URLs.")

    # feed.json — JSON Feed 1.1 spec (jsonfeed.org). One item per agent.
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "HVTracker — Open-Source AI Agent Leaderboard",
        "description": "Daily health scores and rankings for open-source AI agents.",
        "home_page_url": "https://hvtracker.net/",
        "feed_url": "https://hvtracker.net/feed.json",
        "language": "en",
        "items": [
            {
                "id": f"https://hvtracker.net/agents/{r['slug']}",
                "url": f"https://hvtracker.net/agents/{r['slug']}",
                "external_url": r["url"],
                "title": f"#{r['rank']} {r['name']} — score {r['score']}",
                "content_text": (
                    f"{r.get('description','')}\n\n"
                    f"Score {r['score']}/100 · {r['stars']:,} stars · "
                    f"last push {r['last_push']} · "
                    f"{r.get('weekly_commits') or 0} commits in last 4 weeks"
                    f"{' · pkg provenance: ' + ','.join(r.get('provenance_sources',[])) if r.get('has_provenance') else ''}"
                    f"{' · OSSF ' + r['scorecard_fmt'] + '/10' if r.get('scorecard_fmt') else ''}"
                    f"{' · ' + str(r.get('signed_commits_pct','')) + '% signed commits' if r.get('signed_commits_pct') is not None else ''}"
                ).strip(),
                "date_modified": now_iso,
                "tags": [r["category"]] if r.get("category") else [],
            }
            for r in rows
        ],
    }
    with open(os.path.join(script_dir, "feed.json"), "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
    print(f"Wrote feed.json with {len(rows)} items.")

    methodology_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    methodology_html = env.get_template("methodology.html.j2").render(
        methodology_version=METHODOLOGY_VERSION,
        updated=methodology_date,
    )
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    methodology_paths = [
        os.path.join(output_dir, "methodology.html"),
        os.path.join(script_dir, "methodology.html"),
    ]
    for path in methodology_paths:
        with open(path, "w", encoding="utf-8") as f:
            f.write(methodology_html)
    print(f"Built methodology.html ({METHODOLOGY_VERSION}, updated {methodology_date}).")

    # Build /spec/ pages
    from specs import ALL_SPECS
    spec_tmpl = env.get_template("spec.html.j2")
    spec_index_tmpl = env.get_template("spec_index.html.j2")

    spec_base = os.path.join(script_dir, "spec")
    os.makedirs(spec_base, exist_ok=True)

    for spec in ALL_SPECS:
        spec_dir = os.path.join(spec_base, spec["slug"], spec["version"])
        os.makedirs(spec_dir, exist_ok=True)
        html = spec_tmpl.render(spec=spec)
        with open(os.path.join(spec_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Built spec: /spec/{spec['slug']}/{spec['version']}")

    # /spec/ index
    index_html = spec_index_tmpl.render(specs=ALL_SPECS)
    with open(os.path.join(spec_base, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"Built spec index with {len(ALL_SPECS)} spec(s).")


if __name__ == "__main__":
    main()
