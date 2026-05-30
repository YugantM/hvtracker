"""Data-integrity checks: agents.json is well-formed and self-consistent.

Guards against the most common breakage — a hand-edited agents.json that
would crash the build at runtime in CI / the Railway cron.
"""
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRED_KEYS = {"name", "repo", "category", "listing_status", "tracking_mode"}


@pytest.fixture(scope="module")
def agents():
    with open(os.path.join(ROOT, "agents.json")) as f:
        return json.load(f)


def test_agents_json_is_a_nonempty_list(agents):
    assert isinstance(agents, list)
    assert len(agents) > 0


def test_every_agent_has_required_keys(agents):
    for a in agents:
        missing = REQUIRED_KEYS - a.keys()
        assert not missing, f"{a.get('repo', a)} missing keys: {missing}"


def test_repo_format_is_owner_slash_name(agents):
    for a in agents:
        repo = a["repo"]
        assert repo.count("/") == 1 and all(repo.split("/")), f"bad repo: {repo!r}"


def test_no_duplicate_repos(agents):
    repos = [a["repo"].lower() for a in agents]
    dupes = {r for r in repos if repos.count(r) > 1}
    assert not dupes, f"duplicate repos: {dupes}"
