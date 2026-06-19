"""Open-lookup gating + provisional verdict (open_lookup.py, P2)."""
import open_lookup

AI_REPO = {
    "full_name": "acme/agent", "name": "agent",
    "description": "An autonomous AI agent framework",
    "topics": ["ai-agent"], "stargazers_count": 5000,
    "license": {"spdx_id": "MIT"}, "pushed_at": "2026-06-10T00:00:00Z",
    "archived": False,
}


def test_looks_like_ai_by_topic():
    assert open_lookup.looks_like_ai({"topics": ["ai-agent"], "description": ""})


def test_looks_like_ai_by_description():
    assert open_lookup.looks_like_ai({"topics": [], "description": "A coding agent for your repo"})


def test_not_ai():
    assert not open_lookup.looks_like_ai({"topics": ["css"], "name": "grid", "description": "A CSS layout library"})


def test_build_provisional_trusted():
    v = open_lookup.build_provisional("acme/agent", AI_REPO)
    assert v["tracked"] is False and v["provisional"] is True and v["eligibility"] == "ok"
    assert v["trusted"] is True and v["grade"] == "C"
    assert v["stars"] == 5000 and v["trust_score"] is None and v["confidence"] < 0.5


def test_build_provisional_caution_when_no_license():
    repo = dict(AI_REPO, license=None)
    v = open_lookup.build_provisional("acme/agent", repo)
    assert v["trusted"] is False and v["grade"] == "D"


def test_evaluate_open_gates(monkeypatch):
    holder = {}
    monkeypatch.setattr(open_lookup, "fetch_repo", lambda rp, token="": holder["repo"])

    holder["repo"] = None
    assert open_lookup.evaluate_open("acme/agent", "acme/agent")["eligibility"] == "not_found"

    holder["repo"] = dict(AI_REPO, archived=True)
    assert open_lookup.evaluate_open("acme/agent", "acme/agent")["eligibility"] == "archived"

    holder["repo"] = {"topics": ["css"], "description": "layout", "stargazers_count": 9999, "archived": False}
    assert open_lookup.evaluate_open("acme/agent", "acme/agent")["eligibility"] == "not_ai"

    holder["repo"] = dict(AI_REPO, stargazers_count=500)
    assert open_lookup.evaluate_open("acme/agent", "acme/agent")["eligibility"] == "below_stars"

    holder["repo"] = AI_REPO
    assert open_lookup.evaluate_open("acme/agent", "acme/agent")["eligibility"] == "ok"
