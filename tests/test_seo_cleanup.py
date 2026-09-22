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
import re
import importlib
import itertools
import json
import os
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from unittest import mock

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The lastmod-stability assertion compares three renders of identical data.
# Renders take minutes each now (the site grew a lot), so wall-clock time
# advances between them, and any page carrying a relative-time value
# (days_ago, "N hours ago") re-hashes and re-stamps — a spurious failure.
# Freeze the clock fetch_and_build sees so all three renders are byte-stable.
_FROZEN_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return _FROZEN_NOW if tz is None else _FROZEN_NOW.astimezone(tz)

    @classmethod
    def utcnow(cls):
        return _FROZEN_NOW.replace(tzinfo=None)

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
    # Freeze fetch_and_build's clock across all renders in this fixture so
    # relative-time content is identical between them (see _FROZEN_NOW).
    with mock.patch.object(fetch_and_build, "datetime", _FrozenDatetime):
        fetch_and_build.run_refresh("render")  # writes today's history snapshot
        fetch_and_build.run_refresh("render")  # steady state

        seo_path = os.path.join(tmp, "data", "seo_state.json")
        with open(seo_path, encoding="utf-8") as f:
            state1 = json.load(f)

        with open(os.path.join(tmp, "data", "render_state.json"), encoding="utf-8") as f:
            rows = json.load(f)["rows"]

    # Fabricate a persisted pair the current generation rule does NOT produce,
    # so the re-render can only keep it via seo_state persistence.
    #
    # Derived from the published set rather than a fixed rank index: this used
    # to hardcode "leader vs #4", which silently stopped fabricating anything
    # the moment the rule widened past top-3 (every such pair became published,
    # so there was nothing left to test persistence with).
    published = {tuple(p) for p in state1.get("published_compare_pairs", [])}
    by_cat = defaultdict(list)
    for r in rows:
        if r.get("category") and r.get("slug"):
            by_cat[r["category"]].append(r)
    fabricated = None
    for rs in by_cat.values():
        rs.sort(key=lambda x: x.get("category_rank") or 9999)
        for a, b in itertools.combinations(rs, 2):
            pair = tuple(sorted((a["slug"], b["slug"])))
            if pair not in published:
                fabricated = pair
                break
        if fabricated:
            break
    assert fabricated, "need one same-category pair outside the current generation rule"

    doctored = json.loads(json.dumps(state1))
    doctored["published_compare_pairs"].append(list(fabricated))
    for entry in doctored.get("sitemap_lastmod", {}).values():
        entry["date"] = SENTINEL_LASTMOD
    article_slug = sorted(doctored.get("article_meta", {}))[0]
    doctored["article_meta"][article_slug]["published"] = SENTINEL_PUBLISHED
    with open(seo_path, "w", encoding="utf-8") as f:
        json.dump(doctored, f)

    with mock.patch.object(fetch_and_build, "datetime", _FrozenDatetime):
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


def test_persisted_pair_survives_rank_shuffle(site, client):
    a, b = site["fabricated"]
    page = os.path.join(site["tmp"], "compare", f"{a}-vs-{b}", "index.html")
    assert os.path.isfile(page), "persisted pair was not re-rendered"
    # The invariant is anti-404, not sitemap membership: a rank shuffle must
    # never make an already-indexed compare URL 404. The page stays rendered
    # and serves 200 even when the crawl-budget policy holds it OUT of the
    # sitemap (see test_compare_sitemap_prunes_unproven) — the fabricated pair
    # has no impressions, so it is reachable via internal links, not the
    # sitemap. Sitemap presence is asserted for proven/wave pairs, not here.
    r = client.get(f"/compare/{a}-vs-{b}/", follow_redirects=False)
    assert r.status_code == 200


def test_compare_sitemap_prunes_unproven(site):
    """Crawl-budget policy: the sitemap advertises far fewer compare pairs than
    are generated on disk — proven pairs (compare_sitemap_allow.txt) plus a
    bounded wave — while every generated pair stays on disk (reachable)."""
    compare_root = os.path.join(site["tmp"], "compare")
    on_disk = {d for d in os.listdir(compare_root)
               if "-vs-" in d and os.path.isdir(os.path.join(compare_root, d))}
    with open(os.path.join(site["tmp"], "sitemap.xml"), encoding="utf-8") as f:
        sitemap = f.read()
    in_sitemap = set(re.findall(r"/compare/([a-z0-9.-]+-vs-[a-z0-9.-]+)/", sitemap))
    # Something is generated and something is advertised...
    assert on_disk and in_sitemap
    # ...but the sitemap is a strict, meaningfully smaller subset of disk.
    assert in_sitemap <= on_disk
    assert len(in_sitemap) < len(on_disk)


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


def test_double_slash_collapses_to_canonical(site, client):
    # /agents/<slug>// used to serve 200 (a duplicate of the single-slash
    # canonical). It must 301 to the collapsed path so each page has one URL.
    slug = site["fabricated"][0]  # a real agent slug present in this render
    r = client.get(f"/agents/{slug}//", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == f"https://hvtracker.net/agents/{slug}/"
    # A single trailing slash is already canonical and must NOT redirect.
    assert client.get(f"/agents/{slug}/", follow_redirects=False).status_code == 200


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
