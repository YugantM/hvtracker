"""SEO cleanup (GSC coverage report 2026-07-06).

Locks three behaviours:
- previously published /compare/<a>-vs-<b>/ pages survive rank shuffles
  (persisted in data/seo_state.json) instead of 404ing;
- sitemap <lastmod> only advances when a page's content actually changed;
- retired URLs 301 (score-lab, spec v0.1, deleted org/use-case) or 410
  (retired agents) instead of 404ing.

Renders the site three times into a temp OUTPUT_DIR: twice to reach steady
state (the first render writes today's history snapshot, which genuinely
changes agent pages), then once more after doctoring seo_state.json with
sentinel dates and a fabricated below-top-3 pair.
"""
import glob
import importlib
import json
import os
import shutil
import tempfile
from collections import defaultdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SENTINEL_LASTMOD = "2020-01-01"
SENTINEL_PUBLISHED = "2020-02-02"
# Pages that may legitimately change between two same-data renders once a new
# history snapshot exists (weekly-changes comparisons, live data feeds).
VOLATILE_LOCS = {
    "https://hvtracker.net/",
    "https://hvtracker.net/changes/",
    "https://hvtracker.net/data/",
    "https://hvtracker.net/data/latest.json",
    "https://hvtracker.net/data/signals/scorecard.json",
    "https://hvtracker.net/data/signals/provenance.json",
}


@pytest.fixture(scope="module")
def site():
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "output", "history"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "data", "render_state.json"),
                os.path.join(tmp, "data", "render_state.json"))
    graph_src = os.path.join(ROOT, "data", "graph.json")
    if os.path.isfile(graph_src):
        shutil.copy(graph_src, os.path.join(tmp, "data", "graph.json"))
    for h in glob.glob(os.path.join(ROOT, "seed", "history", "*.json")):
        shutil.copy(h, os.path.join(tmp, "output", "history", os.path.basename(h)))

    os.environ["OUTPUT_DIR"] = tmp
    os.environ["DISABLE_SCHEDULER"] = "1"

    import fetch_and_build
    fetch_and_build.run_refresh("render")  # writes today's history snapshot
    fetch_and_build.run_refresh("render")  # steady state

    seo_path = os.path.join(tmp, "data", "seo_state.json")
    with open(seo_path, encoding="utf-8") as f:
        state1 = json.load(f)

    with open(os.path.join(tmp, "data", "render_state.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]

    # Fabricate a persisted pair no current top-3 combination produces:
    # category leader vs the category's #4.
    published = {tuple(p) for p in state1.get("published_compare_pairs", [])}
    by_cat = defaultdict(list)
    for r in rows:
        if r.get("category") and r.get("slug"):
            by_cat[r["category"]].append(r)
    fabricated = None
    for rs in by_cat.values():
        rs.sort(key=lambda x: x.get("category_rank") or 9999)
        if len(rs) >= 4:
            pair = tuple(sorted((rs[0]["slug"], rs[3]["slug"])))
            if pair not in published:
                fabricated = pair
                break
    assert fabricated, "need a category with >=4 agents to fabricate a pair"

    doctored = json.loads(json.dumps(state1))
    doctored["published_compare_pairs"].append(list(fabricated))
    for entry in doctored.get("sitemap_lastmod", {}).values():
        entry["date"] = SENTINEL_LASTMOD
    article_slug = sorted(doctored.get("article_meta", {}))[0]
    doctored["article_meta"][article_slug]["published"] = SENTINEL_PUBLISHED
    with open(seo_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f)

    fetch_and_build.run_refresh("render")
    with open(seo_path, encoding="utf-8") as f:
        state2 = json.load(f)

    # The committed render_state has no legacy rows, so exercise the 410 path
    # with a manufactured retired.json (renderer writes real ones from
    # legacy_rows; app.py reloads on mtime change).
    with open(os.path.join(tmp, "data", "retired.json"), "w", encoding="utf-8") as f:
        json.dump({"agents": ["retired-test-agent"]}, f)

    yield {
        "tmp": tmp,
        "state1": state1,
        "state2": state2,
        "fabricated": fabricated,
        "article_slug": article_slug,
    }
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def client(site):
    import app
    importlib.reload(app)  # re-bind OUTPUT_DIR + static mount
    from fastapi.testclient import TestClient
    # Canonical base_url so the scheme/host middleware doesn't 301 first.
    with TestClient(app.app, base_url="https://hvtracker.net") as c:
        yield c


def test_persisted_pair_survives_rank_shuffle(site):
    a, b = site["fabricated"]
    page = os.path.join(site["tmp"], "compare", f"{a}-vs-{b}", "index.html")
    assert os.path.isfile(page), "persisted pair was not re-rendered"
    with open(os.path.join(site["tmp"], "sitemap.xml"), encoding="utf-8") as f:
        sitemap = f.read()
    assert f"https://hvtracker.net/compare/{a}-vs-{b}/" in sitemap


def test_published_pairs_grow_monotonically(site):
    pairs1 = {tuple(p) for p in site["state1"]["published_compare_pairs"]}
    pairs2 = {tuple(p) for p in site["state2"]["published_compare_pairs"]}
    assert pairs1 <= pairs2


def test_sitemap_lastmod_stable_when_content_unchanged(site):
    with open(os.path.join(site["tmp"], "sitemap.xml"), encoding="utf-8") as f:
        sitemap = f.read()
    # Same data, same day: identical content hashes must reuse the stored
    # (sentinel) date rather than re-stamping today.
    assert (
        f"<loc>https://hvtracker.net/methodology/</loc><lastmod>{SENTINEL_LASTMOD}</lastmod>"
        in sitemap
    )
    # Pages the doctoring intentionally changed restamp correctly: the article
    # whose datePublished moved, the blog index carding it, the new pair.
    a, b = site["fabricated"]
    doctored_locs = {
        "https://hvtracker.net/blog/",
        f"https://hvtracker.net/blog/{site['article_slug']}/",
        f"https://hvtracker.net/compare/{a}-vs-{b}/",
    }
    restamped = [
        loc for loc in site["state2"]["sitemap_lastmod"]
        if f"<loc>{loc}</loc><lastmod>{SENTINEL_LASTMOD}</lastmod>" not in sitemap
        and loc not in VOLATILE_LOCS | doctored_locs
    ]
    assert not restamped, f"{len(restamped)} URLs re-stamped without content change: {restamped[:10]}"


def test_article_publish_date_is_stable(site):
    page = os.path.join(site["tmp"], "blog", site["article_slug"], "index.html")
    with open(page, encoding="utf-8") as f:
        html = f.read()
    assert SENTINEL_PUBLISHED in html, "datePublished re-stamped on re-render"


def test_retired_section_redirects(client):
    r = client.get("/score-lab/", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/methodology/#runtime-calibration"
    r = client.get("/spec/runtime-trust/v0.1/", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/spec/runtime-trust/v0.2/"
    r = client.get("/org/i-am-bee/", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/org/"


def test_retired_agent_pages_are_410(client):
    r = client.get("/agents/retired-test-agent/", follow_redirects=False)
    assert r.status_code == 410
    r = client.get("/compare/retired-test-agent-vs-zzz-not-real/", follow_redirects=False)
    assert r.status_code == 410
    # Hard-deleted agent (never in retired.json) is covered by the constant.
    r = client.get("/agents/bee-agent-framework/", follow_redirects=False)
    assert r.status_code == 410


def test_listed_agent_page_still_serves(site, client):
    with open(os.path.join(site["tmp"], "data", "render_state.json"), encoding="utf-8") as f:
        slug = json.load(f)["rows"][0]["slug"]
    r = client.get(f"/agents/{slug}/", follow_redirects=False)
    assert r.status_code == 200
