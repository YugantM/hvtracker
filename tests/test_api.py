"""End-to-end API tests against a freshly rendered site in a temp OUTPUT_DIR.

Builds the static site with --render-only (no network) from the committed
render cache, then drives the FastAPI app with TestClient. No Postgres/Redis.
"""
import glob
import importlib
import json
import os
import shutil
import tempfile
import types
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def client():
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
    fetch_and_build.run_refresh("render")

    import app
    importlib.reload(app)  # re-bind OUTPUT_DIR + static mount
    from fastapi.testclient import TestClient
    with TestClient(app.app) as c:
        yield c

    shutil.rmtree(tmp, ignore_errors=True)


def test_healthz(client):
    j = client.get("/healthz").json()
    assert j["status"] == "ok"
    assert j["agents"] > 100
    assert j["catalog_agents"] >= j["agents"]
    assert j["source_render_agents"] == j["agents"]
    assert isinstance(j["max_data_age_seconds"], int)
    assert j["max_data_age_seconds"] > 0
    assert isinstance(j["data_fresh"], bool)
    assert isinstance(j["refresh_in_progress"], bool)
    assert isinstance(j["source_render_fingerprint"], str)
    assert len(j["source_render_fingerprint"]) == 64
    if j["stored_render_fingerprint"] is not None:
        assert j["render_in_sync"] == (j["stored_render_fingerprint"] == j["source_render_fingerprint"])
    if j["data_age_seconds"] is not None:
        assert isinstance(j["data_age_seconds"], int)
        assert j["data_age_seconds"] >= 0
    assert client.head("/healthz").status_code == 200


def test_search(client):
    j = client.get("/api/agents", params={"q": "agent", "limit": 5}).json()
    assert j["total"] >= 1
    assert len(j["agents"]) <= 5
    assert client.head("/api/agents").status_code == 200


def test_category_filter(client):
    j = client.get("/api/agents", params={"category": "Coding Agents"}).json()
    assert j["total"] >= 1
    assert all(a["category"] == "Coding Agents" for a in j["agents"])


def test_agent_detail_and_404(client):
    repo = client.get("/api/agents", params={"limit": 1}).json()["agents"][0]["repo"]
    owner, name = repo.split("/")
    assert client.get(f"/api/agents/{owner}/{name}").json()["repo"] == repo
    assert client.head(f"/api/agents/{owner}/{name}").status_code == 200
    assert client.get("/api/agents/no/such-repo").status_code == 404


def test_dynamic_badges(client):
    repo = client.get("/api/agents", params={"limit": 1}).json()["agents"][0]["repo"]
    owner, name = repo.split("/")
    for kind in ("trust", "grade"):
        r = client.get(f"/badge/{owner}/{name}/{kind}.svg")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg+xml")
        assert r.text.lstrip().startswith("<svg")
    assert client.get(f"/badge/{owner}/{name}/bogus.svg").status_code == 404


def test_static_site_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/feed").status_code == 200
    assert client.head("/api/feed").status_code == 200


def test_growth_pages_render(client):
    assert client.get("/alerts").status_code == 200
    assert client.get("/alerts/").status_code == 200
    assert client.get("/sponsor").status_code == 200
    assert client.get("/sponsor/").status_code == 200
    assert client.get("/data-api").status_code == 200
    assert client.get("/data-api/").status_code == 200
    assert client.get("/track/codex").status_code == 200
    assert client.get("/track/codex/").status_code == 200
    assert client.get("/track/not-a-real-agent").status_code == 404


def test_submit_validation_rejects_bad_repo(client):
    # No DB configured, so a valid repo would raise; we only assert the
    # owner/name validation guard fires before any DB call.
    r = client.post("/submit", data={"repo": "not-a-repo", "name": "X"})
    assert r.status_code == 400


def test_growth_post_routes_fail_gracefully_without_db(client):
    import app as _app
    _app._rate_log.clear()
    for path, payload in (
        ("/alerts", {"email": "test@example.com"}),
        ("/alerts/", {"email": "test@example.com"}),
        ("/sponsor", {"name": "Y", "company": "HV", "email": "test@example.com", "message": "Hi"}),
        ("/sponsor/", {"name": "Y", "company": "HV", "email": "test@example.com", "message": "Hi"}),
        ("/data-api", {"email": "test@example.com", "message": "Need access"}),
        ("/data-api/", {"email": "test@example.com", "message": "Need access"}),
        ("/track/codex", {"email": "test@example.com"}),
        ("/track/codex/", {"email": "test@example.com"}),
    ):
        _app._rate_log.clear()
        r = client.post(path, data=payload)
        assert r.status_code == 503


def test_honeypot_blocks_spam(client):
    """POST with honeypot filled returns 200 but writes nothing."""
    import app as _app
    _app._rate_log.clear()
    r = client.post("/alerts", data={"email": "bot@spam.com", "website": "http://spam.com"})
    assert r.status_code == 200
    assert "Thanks" in r.text


def test_rate_limit_returns_429(client):
    """6th rapid POST from same IP returns 429."""
    import app as _app
    _app._rate_log.clear()
    for i in range(5):
        r = client.post("/alerts", data={"email": f"user{i}@example.com"})
        assert r.status_code in (200, 503)
    r = client.post("/alerts", data={"email": "extra@example.com"})
    assert r.status_code == 429


def test_oversized_input_returns_400(client):
    """Oversized message field returns 400."""
    import app as _app
    _app._rate_log.clear()
    r = client.post("/correct", data={
        "repo": "owner/name",
        "message": "x" * 4001,
    })
    assert r.status_code == 400
    assert "limit" in r.text.lower()


def test_invalid_email_returns_400(client):
    """Invalid email format returns 400."""
    import app as _app
    _app._rate_log.clear()
    r = client.post("/alerts", data={"email": "not-an-email"})
    assert r.status_code == 400
    assert "email" in r.text.lower()


def test_forms_contain_honeypot(client):
    """All form pages include the honeypot field."""
    for path in ("/submit", "/correct", "/alerts", "/sponsor", "/data-api", "/track/codex"):
        r = client.get(path)
        assert r.status_code == 200
        assert 'name="website"' in r.text


def test_security_headers_on_homepage(client):
    """Homepage has all security headers."""
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "camera=()" in r.headers["permissions-policy"]
    assert "content-security-policy-report-only" in r.headers


def test_badge_has_no_x_frame_options(client):
    """Badge SVG routes omit X-Frame-Options so they can be embedded."""
    repo = client.get("/api/agents", params={"limit": 1}).json()["agents"][0]["repo"]
    owner, name = repo.split("/")
    r = client.get(f"/badge/{owner}/{name}/trust.svg")
    assert r.status_code == 200
    assert "x-frame-options" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_api_v1_agents(client):
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    assert r.headers["access-control-allow-origin"] == "*"
    assert "max-age=900" in r.headers["cache-control"]
    data = r.json()
    assert "agents" in data


def test_history_snapshot_keeps_runtime_drift_fields(client):
    """History snapshots are the only source for runtime-drift trends (T3.5);
    they can't be backfilled, so losing these fields is silent data loss."""
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(os.environ["OUTPUT_DIR"], "output", "history", f"{today}.json")
    with open(path) as f:
        snap = json.load(f)
    agent = snap["agents"][0]
    for key in ("mcp_server_support", "external_service_dependencies",
                "tool_plugin_surface", "package_provenance_drift",
                "has_provenance", "trust_score", "rank"):
        assert key in agent, f"runtime-drift field {key!r} missing from history snapshot"
    assert "graph_summary" in snap


def test_sitemap_and_feeds_get_cache_headers(client):
    for path in ("/sitemap.xml", "/feed.json", "/changes/feed.xml"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "s-maxage=1800" in r.headers.get("cache-control", ""), path


def test_handwritten_feed_items_have_stable_dates(client):
    """Hand-written blog posts must not re-stamp date_modified every render
    (master plan 0.6) — a fresh render's feed must carry their real publish
    dates, byte-identical across renders."""
    expected = {
        "calibration-fix-and-coverage-grade": "2026-07-06T00:00:00Z",
        "scan-your-stack": "2026-06-23T00:00:00Z",
        "mcp-server-launch": "2026-06-21T00:00:00Z",
        "state-of-ai-agent-supply-chain-trust-2026": "2026-06-21T00:00:00Z",
        "ai-agents-mcp-servers-trust": "2026-06-21T00:00:00Z",
        "trapdoor-supply-chain-provenance": "2026-06-21T00:00:00Z",
        "how-to-evaluate-ai-agent-safety": "2026-05-27T00:00:00Z",
        "most-starred-ai-agents-no-provenance": "2026-05-30T00:00:00Z",
        "coding-agents-trust-rankings": "2026-05-30T00:00:00Z",
        "ai-agent-frameworks-ranked-by-trust": "2026-05-30T00:00:00Z",
        "github-stars-dont-predict-ai-agent-trust": "2026-05-31T00:00:00Z",
        "codex-vs-claude-code": "2026-06-01T00:00:00Z",
        "runtime-trust-is-live": "2026-06-05T00:00:00Z",
    }
    feed = client.get("/feed.json").json()
    by_slug = {
        item["id"].rsplit("/", 1)[-1]: item
        for item in feed["items"]
        if "/blog/" in item["id"]
    }
    for slug, date in expected.items():
        assert slug in by_slug, f"hand-written post {slug!r} missing from feed"
        assert by_slug[slug]["date_modified"] == date, (
            f"{slug}: date_modified {by_slug[slug]['date_modified']!r} != {date!r} "
            "— hand-written posts must keep their real publish date"
        )


def test_capabilities_page_serves(client):
    r = client.get("/capabilities/")
    assert r.status_code == 200
    assert "Capability Matrix" in r.text
    assert "/ecosystem/" in r.text  # provider links resolve to ecosystem pages


def test_machine_usage_counters(client):
    """Plan 1.2: /api/v1, /mcp, /data json, and export requests are counted
    and exposed via healthz so machine-surface usage becomes a visible KPI."""
    before = client.get("/healthz").json()["machine_usage"]
    client.get("/api/v1/agents")
    client.get("/data/latest.json")
    after = client.get("/healthz").json()["machine_usage"]
    # raw request counting: a canonical 301 + its follow-up may both count
    assert after["api_v1"] > before["api_v1"]
    assert after["data_json"] > before["data_json"]
    assert "since" in after


def test_badge_fetch_counters(client):
    """Badge SVG fetches are counted per slug and exposed via healthz —
    READMEs embed badges through GitHub's camo proxy (no referrer, no JS),
    so this server-side counter is the only visibility into that reach."""
    slug = client.get("/api/v1/agents").json()["agents"][0]["slug"]
    before = client.get("/healthz").json()["badge_fetches"]
    assert client.get(f"/badge/{slug}.svg").status_code == 200
    assert client.get(f"/badge/{slug}-grade.svg").status_code == 200
    after = client.get("/healthz").json()["badge_fetches"]
    assert after["total"] >= before["total"] + 2
    assert after["top"].get(slug, 0) >= 2
    # unknown slugs must not pollute the counters
    total_after_404 = after["total"]
    assert client.get("/badge/not-a-real-agent-xyz.svg").status_code == 404
    assert client.get("/healthz").json()["badge_fetches"]["total"] == total_after_404


def test_data_api_page_documents_machine_surface(client):
    r = client.get("/data-api/")
    assert "/api/v1/mcp/verify" in r.text
    assert ".well-known/hvtracker.json" in r.text
    assert "add-only" in r.text  # stability promise
    assert "CC BY 4.0" in r.text


def test_corrections_policy_page(client):
    """Plan 2.5: /correct/ carries the public dispute policy (evidence
    standard, turnaround, appeal path), is linked from methodology and the
    shared nav, and appears in the sitemap."""
    r = client.get("/correct/")
    assert r.status_code == 200
    for phrase in ("What counts as evidence", "within a week",
                   "Public appeal", "never changed by request"):
        assert phrase in r.text, phrase
    meth = client.get("/methodology/").text
    assert 'href="/correct/"' in meth
    assert 'href="/correct/"' in client.get("/").text  # nav
    assert "https://hvtracker.net/correct/" in client.get("/sitemap.xml").text


def test_dataset_export_serves(client):
    import fetch_and_build as fab
    label = fab.quarter_label()
    r = client.get(f"/data/exports/hvtrust-{label}.json.gz")
    assert r.status_code == 200
    r = client.get(f"/data/exports/hvtrust-{label}.csv")
    assert r.status_code == 200
    assert r.text.startswith("rank,")
    # docs page advertises the current quarter's stable URL
    r = client.get("/data-api/")
    assert f"hvtrust-{label}" in r.text
    assert "QUARTER_LABEL" not in r.text


def test_readme_adopter_logos_serve(client):
    """Every logo referenced by the homepage's 'Featured in READMEs' strip
    needs an explicit BASE_DIR route — the StaticFiles mount serves
    OUTPUT_DIR (the volume), so a logo shipped only in the image 404s."""
    for path, ctype in (
        ("/haystack-logo.png", "image/png"),
        ("/aipass-logo.png", "image/png"),
        ("/composio-logo.svg", "image/svg"),
        ("/lightrag-logo.png", "image/png"),
        ("/threadplane-logo.png", "image/png"),
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers["content-type"].startswith(ctype), path


def test_trend_badge_serves(client):
    """Plan 2.3 regression: /badge/<slug>-trend.svg is pre-rendered and must
    be served by the dynamic badge route (which previously only knew -grade
    and 404'd the advertised trend URL)."""
    r = client.get("/badge/haystack-trend.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg")
    assert "HVTrust" in r.text
    # Must serve the file the RENDER wrote (OUTPUT_DIR / the prod volume) —
    # not a stale copy under the code dir. This is exactly the prod bug the
    # first version of this test missed: BASE_DIR happened to contain
    # locally-rendered badges, masking the wrong path.
    rendered = os.path.join(os.environ["OUTPUT_DIR"], "badge", "haystack-trend.svg")
    with open(rendered, encoding="utf-8") as f:
        assert r.text == f.read()
    assert client.get("/badge/not-an-agent-trend.svg").status_code == 404


def test_agent_page_has_related_agents_strip(client):
    """Plan 2.1: every agent page cross-links its ranked category
    neighbours — >=3 internal agent links for a mid-category agent."""
    import re as _re
    html = client.get("/agents/haystack/").text
    assert "Ranked neighbours in" in html
    strip = html.split("Ranked neighbours in", 1)[1]
    links = _re.findall(r'href="/agents/([a-z0-9-]+)/"', strip)
    neighbours = [s for s in links if s != "haystack"]
    assert len(set(neighbours)) >= 3


def test_agent_page_links_capability_surface(client):
    """T3.3 acceptance: agent pages link each detected provider to its
    ecosystem page, and the runtime section links the capability matrix."""
    r = client.get("/agents/vercel-ai-sdk/")
    assert r.status_code == 200
    assert 'href="/capabilities/"' in r.text
    assert 'href="/ecosystem/anthropic/"' in r.text


def test_api_v1_agent_history(client):
    """Plan 3.3: per-agent 90-day public history — one entry per snapshot
    day, public fields only, CORS + cache headers, window capped."""
    r = client.get("/api/v1/agents/haystack/history")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "*"
    assert "max-age=900" in r.headers["cache-control"]
    body = r.json()
    assert body["slug"] == "haystack"
    assert body["window_days"] == 90
    assert body["count"] == len(body["history"])
    assert "CC BY 4.0" in body["license"]
    if body["history"]:
        pt = body["history"][0]
        assert "date" in pt
        # only whitelisted public fields leak through — no evidence blobs,
        # no trust_breakdown, no internal v2 aliases
        allowed = {"date", "rank", "trust_score", "evidence_grade",
                   "coverage_grade", "trust_confidence", "has_provenance",
                   "scorecard_score", "signed_commits_ratio", "stars",
                   "weekly_downloads", "days_ago", "listing_status",
                   "methodology_version"}
        assert set(pt) <= allowed
        # entries are date-ordered and inside the 90-day window
        import datetime as _dt
        dates = [p["date"] for p in body["history"]]
        assert dates == sorted(dates)
        cutoff = (_dt.date.today() - _dt.timedelta(days=90)).isoformat()
        assert all(d >= cutoff for d in dates)


def test_api_v1_agent_history_unknown_404(client):
    r = client.get("/api/v1/agents/not-a-real-agent/history")
    assert r.status_code == 404
    assert r.headers["access-control-allow-origin"] == "*"


def test_api_v1_graph(client):
    r = client.get("/api/v1/graph")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    assert r.headers["access-control-allow-origin"] == "*"
    assert "max-age=900" in r.headers["cache-control"]
    assert isinstance(r.json(), (dict, list))


def test_api_import_candidates_supports_manual_links(client, monkeypatch):
    import app as _app

    tmp = tempfile.mkdtemp()
    docs_dir = os.path.join(tmp, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    with open(os.path.join(docs_dir, "import-candidates.json"), "w", encoding="utf-8") as f:
        json.dump([
            "https://github.com/OpenAI/Codex",
            {
                "name": "Manual Candidate",
                "url": "git@github.com:Example/Agent.git",
                "status": "new",
                "category": "Coding Agents",
            },
            {"repo": "not-a-repo"},
        ], f)

    monkeypatch.setattr(_app, "BASE_DIR", tmp)
    monkeypatch.setattr(_app.db, "load_agents", lambda: [{"repo": "openai/codex", "name": "Codex"}])

    r = client.get("/api/import-candidates")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["count"] == 2
    assert body["candidates"][0]["repo"] == "openai/codex"
    assert body["candidates"][0]["tracked"] is True
    assert body["candidates"][0]["tracked_name"] == "Codex"
    assert body["candidates"][1]["repo"] == "example/agent"
    assert body["candidates"][1]["tracked"] is False

    filtered = client.get("/api/import-candidates", params={"status": "new", "tracked": "false"}).json()
    assert filtered["total"] == 1
    assert filtered["candidates"][0]["repo"] == "example/agent"

    shutil.rmtree(tmp, ignore_errors=True)


def test_startup_keeps_scheduler_alive(monkeypatch):
    import app
    importlib.reload(app)

    class FakeScheduler:
        def __init__(self, timezone):
            self.timezone = timezone
            self.jobs = []
            self.started = False
            self.shutdown_called = False

        def add_job(self, func, trigger, id, hour=None, minute=None, **kwargs):
            self.jobs.append({
                "func": func,
                "trigger": trigger,
                "hour": hour,
                "minute": minute,
                "id": id,
                **kwargs,
            })

        def start(self):
            self.started = True

        def shutdown(self, wait=False):
            self.shutdown_called = True

    fake_bg = types.ModuleType("apscheduler.schedulers.background")
    fake_bg.BackgroundScheduler = FakeScheduler
    fake_sched = types.ModuleType("apscheduler.schedulers")
    fake_sched.background = fake_bg
    fake_ap = types.ModuleType("apscheduler")
    fake_ap.schedulers = fake_sched
    monkeypatch.setitem(sys.modules, "apscheduler", fake_ap)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", fake_sched)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers.background", fake_bg)
    monkeypatch.delenv("DISABLE_SCHEDULER", raising=False)

    monkeypatch.setattr(app, "_seed_history_into_volume", lambda: 0)
    monkeypatch.setattr(app, "_compute_render_fingerprint", lambda: "fp")
    monkeypatch.setattr(app, "_read_render_fingerprint", lambda: "fp")
    monkeypatch.setattr(app.db, "init_schema", lambda: None)
    monkeypatch.setattr(app.db, "enabled", lambda: False)
    monkeypatch.setattr(app, "_has_missing_commit_rows", lambda: False)
    # Stub the sibling predicate too. This test asserts which scheduler jobs
    # get registered; it deletes DISABLE_SCHEDULER and does NOT fake the
    # thread, so leaving this reading the real data.json meant any roster with
    # provisional rows kicked a real fetch subprocess that outlived the suite.
    monkeypatch.setattr(app, "_has_pending_signal_rows", lambda: False)
    monkeypatch.setattr(app.os.path, "isfile", lambda path: True)

    app._scheduler = None
    app.startup()

    assert app._scheduler is not None
    assert app._scheduler.started is True
    jobs = {j["id"]: j for j in app._scheduler.jobs}
    # The 2h full batch and the frequent GitHub-signal refresh.
    assert "refresh" in jobs and "signals-refresh" in jobs
    assert all(callable(j["func"]) and j["trigger"] == "cron" for j in jobs.values())
    assert jobs["refresh"]["hour"] == "*/2"
    assert jobs["signals-refresh"]["minute"] is not None

    app.shutdown()
    assert app._scheduler is None


def test_startup_prefers_pending_over_commit_repair(monkeypatch):
    """A single restart must give freshly added agents their first signal
    refresh. ~10 rows legitimately sit at 0 commits with a recent push
    (default-branch-quiet repos), keeping _has_missing_commit_rows() true on
    nearly every boot — so if repair-commits outranked pending, new agents
    could never be scored by restarting (observed 2026-07-13, 20-agent add)."""
    import app
    importlib.reload(app)

    class FakeScheduler:
        def __init__(self, timezone):
            self.jobs = []

        def add_job(self, func, trigger, id, hour=None, minute=None, **kwargs):
            pass

        def start(self):
            pass

        def shutdown(self, wait=False):
            pass

    fake_bg = types.ModuleType("apscheduler.schedulers.background")
    fake_bg.BackgroundScheduler = FakeScheduler
    fake_sched = types.ModuleType("apscheduler.schedulers")
    fake_sched.background = fake_bg
    fake_ap = types.ModuleType("apscheduler")
    fake_ap.schedulers = fake_sched
    monkeypatch.setitem(sys.modules, "apscheduler", fake_ap)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", fake_sched)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers.background", fake_bg)
    monkeypatch.delenv("DISABLE_SCHEDULER", raising=False)

    monkeypatch.setattr(app, "_seed_history_into_volume", lambda: 0)
    monkeypatch.setattr(app, "_compute_render_fingerprint", lambda: "fp")
    monkeypatch.setattr(app, "_read_render_fingerprint", lambda: "fp")
    monkeypatch.setattr(app.db, "init_schema", lambda: None)
    monkeypatch.setattr(app.db, "enabled", lambda: False)
    monkeypatch.setattr(app.os.path, "isfile", lambda path: True)
    # Both startup-refresh conditions hold at once — pending must win.
    monkeypatch.setattr(app, "_has_missing_commit_rows", lambda: True)
    monkeypatch.setattr(app, "_has_pending_signal_rows", lambda: True)

    kicked = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._args = args

        def start(self):
            if self._args:
                kicked.append(self._args[0])

    monkeypatch.setattr(app.threading, "Thread", FakeThread)

    app._scheduler = None
    app.startup()
    app.shutdown()

    assert "pending" in kicked
    assert "repair-commits" not in kicked


# ---- GSC crawl-waste hygiene (2026-07-18 coverage drilldown fixes) ----

def test_login_page_is_noindex(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert '<meta name="robots" content="noindex">' in r.text
    assert 'rel="canonical" href="https://hvtracker.net/login/"' in r.text


def test_robots_txt_blocks_crawl_waste(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    star_group = r.text.split("User-agent: GPTBot")[0]
    for rule in ("Disallow: /auth/", "Disallow: /track/",
                 "Disallow: /login", "Disallow: /data/agents/"):
        assert rule in star_group
    # AI-crawler groups keep their own Allow: / and inherit no * rules.
    assert "User-agent: GPTBot\nAllow: /" in r.text


def test_compare_fallback_is_noindex_but_static_pairs_index(client):
    out = os.environ["OUTPUT_DIR"]
    static_pairs = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(out, "compare", "*-vs-*"))
        if os.path.isfile(os.path.join(p, "index.html")))
    assert static_pairs, "fixture render produced no static compare pairs"
    r = client.get(f"/compare/{static_pairs[0]}/")
    assert r.status_code == 200
    assert "x-robots-tag" not in r.headers

    slugs = sorted(a["slug"] for a in
                   client.get("/api/agents", params={"limit": 60}).json()["agents"])
    existing = set(static_pairs)
    a, b = next((a, b) for i, a in enumerate(slugs) for b in slugs[i + 1:]
                if f"{a}-vs-{b}" not in existing)
    r = client.get(f"/compare/{a}-vs-{b}/")
    assert r.status_code == 200
    assert r.headers.get("x-robots-tag") == "noindex"


def test_agent_page_track_link_has_trailing_slash(client):
    slug = client.get("/api/agents", params={"limit": 1}).json()["agents"][0]["slug"]
    r = client.get(f"/agents/{slug}/")
    assert r.status_code == 200
    assert f'href="/track/{slug}/"' in r.text
    assert f'href="/track/{slug}"/' not in r.text


def test_blog_urls_carry_trailing_slash(client):
    # Hand-written posts: canonical/og:url/mainEntityOfPage must match the
    # served URL (every page URL ends in /) — no-slash values 301 and landed
    # 25 posts in GSC's redirect bucket.
    import re
    offenders = []
    for path in glob.glob(os.path.join(ROOT, "blog_static", "*", "index.html")):
        with open(path, encoding="utf-8") as f:
            for m in re.finditer(r'https://hvtracker\.net/blog/[a-z0-9-]+["\)]', f.read()):
                offenders.append(f"{path}: {m.group(0)}")
    assert not offenders, offenders
    # feed.json: item urls resolve without a redirect hop (ids stay stable).
    feed = client.get("/feed.json").json()
    blog_urls = [i["url"] for i in feed["items"] if "/blog/" in i["url"]]
    assert blog_urls and all(u.endswith("/") for u in blog_urls)


# ---- /api/v1/usage + /live/ (machine-channel transparency) -----------------

def test_api_v1_usage_shape_and_self_exclusion(client):
    """The usage endpoint reports the machine channels without counting itself.

    The /live/ page polls this endpoint; if it were counted as api_v1 traffic
    the page would inflate the very number it reports.
    """
    import usage
    usage._snapshot_cache = None
    before = usage.snapshot()["totals"]["by_channel"]["api_v1"]

    for _ in range(3):
        r = client.get("/api/v1/usage")
        assert r.status_code == 200

    body = r.json()
    assert set(body) >= {"totals", "window", "recent_calls", "generated_at", "note"}
    assert set(body["totals"]) >= {"tool_calls", "requests", "by_channel", "by_tool"}
    assert set(body["window"]) >= {"tool_calls", "requests", "by_tool", "hourly"}
    assert isinstance(body["window"]["hourly"], list)

    usage._snapshot_cache = None
    after = usage.snapshot()["totals"]["by_channel"]["api_v1"]
    assert after == before, "/api/v1/usage must not count itself as machine usage"


def test_api_v1_usage_counts_other_api_traffic(client):
    """Sanity check the exclusion is path-scoped, not a disabled counter."""
    import usage
    usage._snapshot_cache = None
    before = usage.snapshot()["totals"]["by_channel"]["api_v1"]
    client.get("/api/v1/agents")
    usage._snapshot_cache = None
    assert usage.snapshot()["totals"]["by_channel"]["api_v1"] > before


def test_live_page_is_served(client):
    r = client.get("/live/")
    assert r.status_code == 200
    assert "trust questions answered" in r.text
    assert "/api/v1/usage" in r.text


def test_usage_endpoint_carries_site_freshness_for_the_header(client):
    """The header widget reads freshness + activity from this one response.

    It used to fetch /data/latest.json (multi-megabyte) for the timestamp.
    """
    body = client.get("/api/v1/usage").json()
    assert "data_updated" in body
    import usage
    usage._snapshot_cache = None
    assert "data_updated" not in usage.snapshot(), "must not leak into the cached snapshot"
