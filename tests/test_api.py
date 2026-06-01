"""End-to-end API tests against a freshly rendered site in a temp OUTPUT_DIR.

Builds the static site with --render-only (no network) from the committed
render cache, then drives the FastAPI app with TestClient. No Postgres/Redis.
"""
import glob
import importlib
import os
import shutil
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def client():
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "output", "history"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "data", "render_state.json"),
                os.path.join(tmp, "data", "render_state.json"))
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


def test_search(client):
    j = client.get("/api/agents", params={"q": "agent", "limit": 5}).json()
    assert j["total"] >= 1
    assert len(j["agents"]) <= 5


def test_category_filter(client):
    j = client.get("/api/agents", params={"category": "Coding Agents"}).json()
    assert j["total"] >= 1
    assert all(a["category"] == "Coding Agents" for a in j["agents"])


def test_agent_detail_and_404(client):
    repo = client.get("/api/agents", params={"limit": 1}).json()["agents"][0]["repo"]
    owner, name = repo.split("/")
    assert client.get(f"/api/agents/{owner}/{name}").json()["repo"] == repo
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


def test_growth_pages_render(client):
    assert client.get("/alerts").status_code == 200
    assert client.get("/sponsor").status_code == 200
    assert client.get("/data-api").status_code == 200
    assert client.get("/track/codex").status_code == 200
    assert client.get("/track/not-a-real-agent").status_code == 404


def test_submit_validation_rejects_bad_repo(client):
    # No DB configured, so a valid repo would raise; we only assert the
    # owner/name validation guard fires before any DB call.
    r = client.post("/submit", data={"repo": "not-a-repo", "name": "X"})
    assert r.status_code == 400


def test_growth_post_routes_fail_gracefully_without_db(client):
    for path, payload in (
        ("/alerts", {"email": "test@example.com"}),
        ("/sponsor", {"name": "Y", "company": "HV", "email": "test@example.com", "message": "Hi"}),
        ("/data-api", {"email": "test@example.com", "message": "Need access"}),
        ("/track/codex", {"email": "test@example.com"}),
    ):
        r = client.post(path, data=payload)
        assert r.status_code == 503
