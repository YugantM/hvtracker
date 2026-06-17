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
    for h in glob.glob(os.path.join(ROOT, "output", "history", "*.json")):
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
        assert r.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
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

        def add_job(self, func, trigger, hour, id, **kwargs):
            self.jobs.append({
                "func": func,
                "trigger": trigger,
                "hour": hour,
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
    monkeypatch.setattr(app.os.path, "isfile", lambda path: True)

    app._scheduler = None
    app.startup()

    assert app._scheduler is not None
    assert app._scheduler.started is True
    assert len(app._scheduler.jobs) == 1
    job = app._scheduler.jobs[0]
    assert callable(job["func"])
    assert job["trigger"] == "cron"
    assert job["hour"] == "*/2"
    assert job["id"] == "refresh"

    app.shutdown()
    assert app._scheduler is None
