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

METHODOLOGY_VERSION = "v1.1"


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


def load_previous_ranks(data_path: str) -> dict[str, int]:
    """Load previous rankings from data.json. Returns {repo: rank} mapping."""
    if not os.path.exists(data_path):
        return {}
    try:
        with open(data_path, encoding="utf-8") as f:
            prev = json.load(f)
        return {a["repo"].lower(): a["rank"] for a in prev.get("agents", [])}
    except (json.JSONDecodeError, KeyError):
        return {}


def load_previous_downloads(data_path: str) -> dict[str, tuple[int, str]]:
    """Load previous download counts from data.json.
    Returns {pypi_or_npm_package: (count, dl_source)} for use as fallback on 429."""
    if not os.path.exists(data_path):
        return {}
    try:
        with open(data_path, encoding="utf-8") as f:
            prev = json.load(f)
        result = {}
        for a in prev.get("agents", []):
            dl = a.get("weekly_downloads")
            src = a.get("dl_source", "")
            if dl is not None:
                # key by repo so we can look up regardless of package name changes
                result[a["repo"].lower()] = (dl, src)
        return result
    except (json.JSONDecodeError, KeyError):
        return {}


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


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_path = os.path.join(script_dir, "agents.json")
    data_path = os.path.join(script_dir, "data.json")

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

    # Load previous rankings and downloads for delta computation and 429 fallback
    prev_ranks = load_previous_ranks(data_path)
    prev_downloads = load_previous_downloads(data_path)

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
        # Use Stats API 4-week sum (same source as score) for the display column.
        # Falls back to Commits API only if Stats API returned nothing.
        commits_4wk = sum(w["total"] for w in weeks[-4:]) if weeks else None
        if commits_4wk is None or (commits_4wk == 0 and not weeks):
            commits_4wk = fetch_recent_commits(repo_id)
        recent_commits = commits_4wk
        d = days_ago(repo["pushed_at"])

        # Fetch npm downloads in parallel (npm API has no strict rate limit)
        pypi_pkg = agent.get("pypi_package", "")
        npm_dl = fetch_npm_downloads(npm_pkg) if npm_pkg else None
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
            "score": score,
            "score_class": score_class(score),
            "description": (repo.get("description") or "")[:120],
            "language": repo.get("language") or "",
            "open_issues": repo.get("open_issues_count", 0),
            "npm_package": npm_pkg if npm_pkg else "",
            "pypi_package": pypi_pkg if pypi_pkg else "",
            "npm_dl": npm_dl,
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

    rows.sort(key=lambda x: x["score"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i

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
                "forks": r["forks"],
                "last_push": r["last_push"],
                "days_ago": r["days_ago"],
                "weekly_commits": r["weekly_commits"],
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

    templates_dir = os.path.join(script_dir, "templates")
    env = Environment(
        loader=FileSystemLoader([templates_dir, script_dir]),
        autoescape=True,
    )

    tmpl = env.get_template("template.html")
    html = tmpl.render(
        rows=rows,
        updated=now_str,
        total=len(rows),
        categories=categories,
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
        slug_dir = os.path.join(agents_dir, row["slug"])
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(agent_tmpl.render(row=row, total=len(rows), updated=now_str))
    print(f"Built {len(rows)} agent profile pages under agents/.")

    # sitemap.xml — /, /methodology, all /agents/<slug>
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap_urls = [
        ("https://hvtracker.net/", "1.0", "daily"),
        ("https://hvtracker.net/methodology", "0.5", "monthly"),
    ]
    for row in rows:
        sitemap_urls.append((f"https://hvtracker.net/agents/{row['slug']}", "0.8", "daily"))
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


if __name__ == "__main__":
    main()
