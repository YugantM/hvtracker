"""Unit tests for the agent-discovery helpers (no network)."""
from datetime import datetime, timezone

import auto_add_agents as aa
import discover_agents as da


def _base_repo(**over):
    repo = {
        "archived": False,
        "fork": False,
        "stargazers_count": da.MIN_STARS + 10,
        "license": {"key": "mit"},
        "pushed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    repo.update(over)
    return repo


def test_passes_eligibility_happy_path():
    assert da.passes_eligibility(_base_repo()) is True


def test_rejects_archived():
    assert da.passes_eligibility(_base_repo(archived=True)) is False


def test_rejects_fork():
    assert da.passes_eligibility(_base_repo(fork=True)) is False


def test_rejects_low_stars():
    assert da.passes_eligibility(_base_repo(stargazers_count=0)) is False


def test_rejects_missing_license():
    assert da.passes_eligibility(_base_repo(license=None)) is False


def test_rejects_stale_push():
    assert da.passes_eligibility(_base_repo(pushed_at="2020-01-01T00:00:00Z")) is False


def test_bad_pushed_at_does_not_crash():
    # Unparseable date should be tolerated (not raise) and not disqualify on date alone.
    assert da.passes_eligibility(_base_repo(pushed_at="not-a-date")) is True


def test_infer_category_first_match_wins():
    assert aa.infer_category(["browser", "ai-agent"]) == "Browser & Computer Use"


def test_infer_category_fallback():
    assert aa.infer_category(["totally-unrelated"]) == "Agent Frameworks"


def test_infer_category_is_case_insensitive():
    assert aa.infer_category(["CODING-AGENT"]) == "Coding Agents"


def test_reviewed_rejected_repos_are_never_reproposed():
    """Owner-rejected candidates (2026-07-07: LobsterAI, Agent Orchestrator,
    Sandcastle) must stay in the denylist so discovery can't re-propose them."""
    for repo in ("netease-youdao/lobsterai",
                 "agentwrapper/agent-orchestrator",
                 "mattpocock/sandcastle"):
        assert repo in da.REVIEWED_REJECTED, repo
        assert "rejected" in da.REVIEWED_REJECTED[repo]
    # keys must be lowercase — main() filters with lowercase full_name keys
    assert all(k == k.lower() for k in da.REVIEWED_REJECTED)
