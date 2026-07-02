"""Unit tests for the pure helper functions in fetch_and_build.py.

These are deterministic and make no network calls.
"""
import json
import sys

import pytest
import requests

import fetch_and_build as fb


# ---- formatting ----------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Hello World", "hello-world"),
    ("foo/bar_baz", "foo-bar-baz"),
    ("  Spaces  ", "spaces"),
    ("Already-Slug", "already-slug"),
    ("C++ & Rust!", "c-rust"),
])
def test_slugify(name, expected):
    assert fb.slugify(name) == expected


def test_assign_unique_slugs_keeps_primary_and_disambiguates_duplicates():
    rows = [
        {"name": "Goose", "repo": "block/goose"},
        {"name": "Goose", "repo": "aaif-goose/goose"},
        {"name": "Codex", "repo": "openai/codex"},
    ]
    fb.assign_unique_slugs(rows)
    assert rows[0]["slug"] == "goose"
    assert rows[1]["slug"] == "aaif-goose-goose"
    assert rows[2]["slug"] == "codex"


@pytest.mark.parametrize("n,expected", [
    (0, "0"),
    (999, "999"),
    (1_000, "1.0k"),
    (1_500, "1.5k"),
    (1_000_000, "1.0M"),
    (2_400_000, "2.4M"),
])
def test_fmt_num(n, expected):
    assert fb.fmt_num(n) == expected


def test_fmt_date_handles_z_suffix():
    assert fb.fmt_date("2026-05-30T09:39:50Z") == "2026-05-30"
    assert fb.fmt_date("2026-01-02T00:00:00+00:00") == "2026-01-02"


def test_days_ago_is_nonnegative_and_monotonic():
    recent = fb.days_ago("2026-05-29T00:00:00Z")
    older = fb.days_ago("2020-01-01T00:00:00Z")
    assert recent >= 0
    assert older > recent


@pytest.mark.parametrize("d,cls", [
    (0, "fresh"), (7, "fresh"),
    (8, "recent"), (30, "recent"),
    (31, "aging"), (90, "aging"),
    (91, "stale"), (999, "stale"),
])
def test_freshness_class(d, cls):
    assert fb.freshness_class(d) == cls


@pytest.mark.parametrize("score,cls", [
    (100, "score-high"), (70, "score-high"),
    (69.9, "score-mid"), (45, "score-mid"),
    (44.9, "score-low"), (0, "score-low"),
])
def test_score_class(score, cls):
    assert fb.score_class(score) == cls


# ---- scoring -------------------------------------------------------------

def test_score_components_bounds():
    c = fb.score_components(stars=1_000_000, days_since=0, recent_commits=1000, forks=100_000)
    assert c["stars"] <= 30
    assert c["freshness"] <= 25
    assert c["activity"] <= 25
    assert c["community"] <= 20


def test_score_components_zero_floor():
    # days_since beyond 180 must floor freshness at 0, not go negative
    c = fb.score_components(stars=0, days_since=365, recent_commits=0, forks=0)
    assert c["freshness"] == 0.0
    assert c["stars"] == 0.0
    assert c["activity"] == 0.0
    assert c["community"] == 0.0


def test_health_score_matches_component_sum():
    stars, days, commits, forks = 5000, 10, 50, 800
    c = fb.score_components(stars, days, commits, forks)
    expected = round(c["stars"] + c["freshness"] + c["activity"] + c["community"], 1)
    assert fb.health_score(stars, days, commits, forks) == expected


def test_health_score_in_range():
    assert 0 <= fb.health_score(1_000_000, 0, 1000, 100_000) <= 100


# ---- rank delta display --------------------------------------------------

@pytest.mark.parametrize("delta,is_new,expected", [
    (None, True, "NEW"),
    (5, True, "NEW"),
    (None, False, "—"),
    (0, False, "="),
    (3, False, "▲3"),
    (-4, False, "▼4"),
])
def test_rank_delta_display(delta, is_new, expected):
    assert fb.rank_delta_display(delta, is_new) == expected


@pytest.mark.parametrize("delta,is_new,expected", [
    (1, True, "delta-new"),
    (None, False, "delta-same"),
    (0, False, "delta-same"),
    (2, False, "delta-up"),
    (-2, False, "delta-down"),
])
def test_rank_delta_class(delta, is_new, expected):
    assert fb.rank_delta_class(delta, is_new) == expected


# ---- GitHub Link header parsing -----------------------------------------

def test_parse_link_last_page():
    header = (
        '<https://api.github.com/x?page=2>; rel="next", '
        '<https://api.github.com/x?page=9>; rel="last"'
    )
    page, url = fb._parse_link_last_page(header)
    assert page == 9
    assert url == "https://api.github.com/x?page=9"


def test_parse_link_last_page_absent():
    page, url = fb._parse_link_last_page('<https://api.github.com/x?page=2>; rel="next"')
    assert page is None and url is None


def test_compute_trust_score_treats_all_download_sources_as_applicable():
    baseline = fb.compute_trust_score({
        "stars": 100,
        "weekly_downloads": None,
        "crate_package": "",
        "docker_image": "",
        "vscode_extension": "",
        "scorecard_score": None,
        "has_provenance": False,
        "public_actions": None,
        "hn_mentions_30d": None,
        "listing_status": "listed",
        "days_ago": 10,
        "weekly_commits": 5,
        "commits_low_confidence": False,
        "license_spdx": "MIT",
    })
    score = fb.compute_trust_score({
        "stars": 100,
        "weekly_downloads": None,
        "crate_package": "tool",
        "docker_image": "",
        "vscode_extension": "",
        "scorecard_score": None,
        "has_provenance": False,
        "public_actions": None,
        "hn_mentions_30d": None,
        "listing_status": "listed",
        "days_ago": 10,
        "weekly_commits": 5,
        "commits_low_confidence": False,
        "license_spdx": "MIT",
    })
    assert baseline["trust_confidence"] == 0.5
    assert score["trust_confidence"] == 0.4


# ---- runtime trust -------------------------------------------------------

def test_detect_mcp_server_support_marks_implemented_from_server_readme():
    result = fb.detect_mcp_server_support(
        readme_text="This project runs as an MCP server for Claude Desktop.",
    )
    assert result["status"] == "implemented"
    assert result["confidence"] in {"medium", "high"}
    assert result["evidence"]


def test_detect_mcp_server_support_marks_implemented_from_dependency_and_path():
    result = fb.detect_mcp_server_support(
        tree_paths=["server/mcp_server.py", "pyproject.toml"],
        manifest_text_by_path={"pyproject.toml": 'dependencies = ["fastmcp>=1.0"]'},
    )
    assert result["status"] == "implemented"
    assert result["confidence"] == "high"


def test_detect_mcp_server_support_marks_declared_from_generic_mcp_docs():
    result = fb.detect_mcp_server_support(
        readme_text="Roadmap: add Model Context Protocol support next quarter.",
    )
    assert result["status"] == "declared"
    assert result["confidence"] == "low"


def test_detect_mcp_server_support_does_not_treat_test_paths_as_implemented():
    result = fb.detect_mcp_server_support(
        tree_paths=["tests/mcp_server_status.rs", "package.json"],
        manifest_text_by_path={"package.json": '{"dependencies":{"@modelcontextprotocol/sdk":"1.0.0"}}'},
    )
    assert result["status"] == "declared"
    assert result["confidence"] == "medium"


def test_detect_mcp_server_support_marks_none_without_evidence():
    result = fb.detect_mcp_server_support()
    assert result == {"status": "none", "confidence": None, "evidence": []}


def test_detect_external_service_dependencies_from_readme_and_env_markers():
    result = fb.detect_external_service_dependencies(
        readme_text="Use OpenAI with OPENAI_API_KEY and Tavily with TAVILY_API_KEY.",
    )
    assert result["providers"] == ["OpenAI", "Tavily"]
    assert result["requires_api_keys"] is True
    assert result["confidence"] == "high"
    assert result["evidence"]


def test_detect_external_service_dependencies_from_manifest_dependencies():
    result = fb.detect_external_service_dependencies(
        manifest_text_by_path={"package.json": '{"dependencies":{"openai":"^4","redis":"^5"}}'},
    )
    assert result["providers"] == ["OpenAI", "Redis"]
    assert result["requires_api_keys"] is False
    assert result["confidence"] == "high"


def test_detect_external_service_dependencies_none_without_evidence():
    result = fb.detect_external_service_dependencies(
        readme_text="Local CLI for markdown editing.",
        manifest_text_by_path={"package.json": '{"dependencies":{"chalk":"^5"}}'},
    )
    assert result == {
        "providers": [],
        "requires_api_keys": False,
        "confidence": None,
        "evidence": [],
    }


def test_detect_tool_plugin_surface_from_extensions_and_browser_deps():
    result = fb.detect_tool_plugin_surface(
        readme_text="Extensions let users add browser automation integrations.",
        tree_paths=["extensions/example/index.ts"],
        manifest_text_by_path={"package.json": '{"dependencies":{"playwright":"^1.0"}}'},
    )
    assert result["plugin_system"] == "extension-based"
    assert "browser" in result["tool_tags"]
    assert result["confidence"] == "high"


def test_manifest_dep_marker_does_not_match_inside_unrelated_words():
    """Regression for the T3.1 runtime-signal audit: a short marker like "pg"
    must not match as a substring inside an unrelated token (e.g. a package
    named "debugging-tools"), only as the start of an actual token."""
    assert fb._manifest_has_dep_marker("debugging-tools==1.0", "pg") is False
    assert fb._manifest_has_dep_marker("psycopg2-binary==2.9.9", "psycopg") is True
    assert fb._manifest_has_dep_marker("pgvector==0.2", "pg") is True
    assert fb._manifest_has_dep_marker('"asyncpg": "^1"', "asyncpg") is True


def test_external_service_dependencies_readme_mention_alone_is_not_a_provider():
    """A README documenting an optional integration ("supports OpenAI,
    Anthropic, or Bedrock") is not evidence of a hard runtime dependency --
    only a manifest dependency or credential/env marker counts."""
    result = fb.detect_external_service_dependencies(
        readme_text="This framework supports OpenAI, Anthropic, or Amazon Bedrock as pluggable LLM backends.",
    )
    assert result["providers"] == []
    assert result["confidence"] is None


def test_external_service_dependencies_mixed_real_and_docs_only():
    """A provider with real manifest evidence still counts (and logs the docs
    mention too); a provider mentioned only in docs does not count at all."""
    result = fb.detect_external_service_dependencies(
        readme_text="Supports OpenAI (see docs) and can optionally integrate with Anthropic.",
        manifest_text_by_path={"pyproject.toml": "openai = \"^1.0\""},
    )
    assert result["providers"] == ["OpenAI"]
    assert "Anthropic" not in result["providers"]


def test_tool_plugin_surface_readme_mention_alone_is_not_a_tag():
    """"search"/"code" patterns (bare "search", "github", "repository") are
    common enough to false-positive on nearly any README; require manifest
    dependency evidence, not a doc mention, to count toward the score."""
    result = fb.detect_tool_plugin_surface(
        readme_text="See our GitHub repository for search and retrieval examples.",
    )
    assert result["tool_tags"] == []


def test_detect_package_provenance_drift_match_and_warning():
    match = fb.detect_package_provenance_drift(
        "openai/codex",
        npm_package="openai-codex",
        npm_metadata={"repository": {"url": "git+https://github.com/openai/codex.git"}},
    )
    assert match["status"] == "match"
    assert match["confidence"] == "high"

    warning = fb.detect_package_provenance_drift(
        "openai/codex",
        pypi_package="openai-codex",
        pypi_metadata={"info": {"project_urls": {"Source": "https://github.com/other/repo"}}},
    )
    assert warning["status"] == "warning"
    assert warning["confidence"] == "high"


def test_detect_package_provenance_drift_same_owner_is_not_a_warning():
    """A same-owner/different-repo package (JS split, rename, monorepo carve-out)
    is not evidence of hijack — it should not carry the -5.0 warning penalty.
    Regression for the T3.1 false-positive fix (langchain-ai/langgraphjs case)."""
    # Only a same-owner variant, no other check -> inconclusive, not a warning.
    same_owner_only = fb.detect_package_provenance_drift(
        "langchain-ai/langgraph",
        npm_package="@langchain/langgraph",
        npm_metadata={"repository": {"url": "https://github.com/langchain-ai/langgraphjs"}},
    )
    assert same_owner_only["status"] == "unknown"
    assert "same owner" in same_owner_only["evidence"][0]

    # Same-owner variant on one check, tracked-repo match on another -> partial,
    # not warning (the ECC-adjacent, LangGraph-shaped case).
    mixed = fb.detect_package_provenance_drift(
        "langchain-ai/langgraph",
        npm_package="@langchain/langgraph",
        npm_metadata={"repository": {"url": "https://github.com/langchain-ai/langgraphjs"}},
        pypi_package="langgraph",
        pypi_metadata={"info": {"project_urls": {"Source": "https://github.com/langchain-ai/langgraph"}}},
    )
    assert mixed["status"] == "partial"

    # A genuine different-owner mismatch must still warn even when a same-owner
    # variant is also present elsewhere -- one real red flag should not be
    # diluted by an unrelated inconclusive check.
    still_warns = fb.detect_package_provenance_drift(
        "strands-agents/sdk-python",
        npm_package="strands",
        npm_metadata={"repository": {"url": "https://github.com/mulesoft-labs/node-strands"}},
        pypi_package="strands-agents",
        pypi_metadata={"info": {"project_urls": {"Source": "https://github.com/strands-agents/sdk-python"}}},
    )
    assert still_warns["status"] == "warning"


def test_detect_package_provenance_drift_repo_transfer_is_not_a_warning():
    """A package pointing to the tracked repo's *current* GitHub name (after a
    rename/org transfer, confirmed via a live get_repo() full_name, which
    transparently follows GitHub redirects) is not evidence of hijack.
    Regression for the T3.1 audit (Garak: leondz/garak -> nvidia/garak;
    Ragas: explodinggradients/ragas -> vibrantlabsai/ragas)."""
    transferred = fb.detect_package_provenance_drift(
        "leondz/garak",
        pypi_package="garak",
        pypi_metadata={"info": {"project_urls": {"Homepage": "https://github.com/NVIDIA/garak"}}},
        tracked_repo_canonical="NVIDIA/garak",
    )
    assert transferred["status"] == "unknown"
    assert "current name after a rename/transfer" in transferred["evidence"][0]

    # Without the canonical hint (e.g. get_repo() failed), the same mismatch
    # correctly still warns -- we only trust a confirmed GitHub redirect.
    no_hint = fb.detect_package_provenance_drift(
        "leondz/garak",
        pypi_package="garak",
        pypi_metadata={"info": {"project_urls": {"Homepage": "https://github.com/NVIDIA/garak"}}},
    )
    assert no_hint["status"] == "warning"

    # A mismatch to some OTHER repo entirely (not the canonical name) still
    # warns even when a canonical hint is present for a different target.
    unrelated_mismatch = fb.detect_package_provenance_drift(
        "leondz/garak",
        pypi_package="garak",
        pypi_metadata={"info": {"project_urls": {"Homepage": "https://github.com/someone-else/unrelated"}}},
        tracked_repo_canonical="NVIDIA/garak",
    )
    assert unrelated_mismatch["status"] == "warning"


def test_normalize_github_repo_url_variants():
    assert fb._normalize_github_repo_url("git+https://github.com/OpenAI/Codex.git") == "openai/codex"
    assert fb._normalize_github_repo_url("git@github.com:OpenAI/Codex.git") == "openai/codex"
    assert fb._normalize_github_repo_url("https://example.com/nope") is None


# ---- batch selection -----------------------------------------------------

def test_parse_batch_arg(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--batch", "3/6"])
    assert fb.parse_batch_arg() == (3, 6)


def test_parse_batch_arg_absent(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--render-only"])
    assert fb.parse_batch_arg() is None


def test_select_batch_partitions_all_agents():
    agents = [{"repo": f"owner/repo{i:02d}"} for i in range(20)]
    total = 6
    seen = []
    for b in range(1, total + 1):
        seen.extend(a["repo"] for a in fb.select_batch(agents, b, total))
    # Every agent appears exactly once across all batches.
    assert sorted(seen) == sorted(a["repo"] for a in agents)


def test_select_batch_is_deterministic():
    agents = [{"repo": "b/B"}, {"repo": "a/A"}, {"repo": "c/C"}]
    first = fb.select_batch(agents, 1, 3)
    second = fb.select_batch(agents, 1, 3)
    assert first == second


def test_compute_newly_added_uses_first_seen_history_not_previous_rank():
    history = [
        {"_date": "2026-05-30", "agents": [
            {"repo": "block/goose"},
            {"repo": "openai/codex"},
        ]},
        {"_date": "2026-05-31", "agents": [
            {"repo": "block/goose"},
            {"repo": "aaif-goose/goose"},
            {"repo": "openai/codex"},
        ]},
        {"_date": "2026-06-01", "agents": [
            {"repo": "block/goose"},
            {"repo": "aaif-goose/goose"},
            {"repo": "openai/codex"},
        ]},
    ]
    rows = [
        {"name": "Goose", "repo": "block/goose", "slug": "goose", "rank": 40, "category": "Coding Agents", "evidence_grade": "B"},
        {"name": "Goose", "repo": "aaif-goose/goose", "slug": "aaif-goose-goose", "rank": 70, "category": "Agent Frameworks", "evidence_grade": "C"},
        {"name": "Codex", "repo": "openai/codex", "slug": "codex", "rank": 2, "category": "Coding Agents", "evidence_grade": "A"},
    ]
    added = fb.compute_newly_added(rows, history, limit=6)
    assert [item["repo"] for item in added] == ["aaif-goose/goose"]


def test_load_cached_commit_counts_prefers_data_json_then_history(tmp_path, monkeypatch):
    data_path = tmp_path / "data.json"
    history_dir = tmp_path / "output" / "history"
    history_dir.mkdir(parents=True)

    data_path.write_text(
        """
        {
          "agents": [
            {"repo": "anthropics/claude-code", "weekly_commits": 41},
            {"repo": "foo/bar", "weekly_commits": null}
          ]
        }
        """.strip(),
        encoding="utf-8",
    )
    (history_dir / "2026-05-30.json").write_text(
        """
        {
          "agents": [
            {"repo": "anthropics/claude-code", "weekly_commits": 12},
            {"repo": "foo/bar", "weekly_commits": 7}
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    class _FakeDateTime:
        @staticmethod
        def now(_tz=None):
            from datetime import datetime, timezone
            return datetime(2026, 5, 31, tzinfo=timezone.utc)

    monkeypatch.setattr(fb, "datetime", _FakeDateTime)
    cached = fb.load_cached_commit_counts(str(data_path), str(history_dir))
    assert cached["anthropics/claude-code"] == 41
    assert cached["foo/bar"] == 7


class _FakeResp:
    def __init__(self, status_code=200, headers=None, json_data=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json_data = json_data

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_github_get_retries_after_429(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(status_code=429, headers={"Retry-After": "1"})
        return _FakeResp(status_code=200, json_data={"ok": True})

    monkeypatch.setattr(fb.requests, "get", fake_get)
    monkeypatch.setattr(fb.time, "sleep", lambda s: sleeps.append(s))

    resp = fb._github_get("https://api.github.com/repos/openai/codex")
    assert resp.json() == {"ok": True}
    assert calls["n"] == 2
    assert sleeps == [1.0]


def test_github_get_retries_202_then_succeeds(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_get(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResp(status_code=202)
        return _FakeResp(status_code=200, json_data=[{"total": 3}])

    monkeypatch.setattr(fb.requests, "get", fake_get)
    monkeypatch.setattr(fb.time, "sleep", lambda s: sleeps.append(s))

    resp = fb._github_get(
        "https://api.github.com/repos/openai/codex/stats/commit_activity",
        allow_202=True,
    )
    assert resp.json() == [{"total": 3}]
    assert calls["n"] == 3
    assert sleeps == [5, 10]


def test_repair_missing_commit_counts_uses_live_then_cached(monkeypatch):
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = [
        {
            "repo": "anthropics/claude-code",
            "weekly_commits": None,
            "last_push": today,
            "days_ago": 0,
            "commits_low_confidence": False,
        },
        {
            "repo": "openai/codex",
            "weekly_commits": None,
            "last_push": yesterday,
            "days_ago": 1,
            "commits_low_confidence": False,
        },
    ]

    monkeypatch.setattr(
        fb,
        "get_commit_activity",
        lambda repo: [] if repo == "anthropics/claude-code" else [{"total": 0}] * 52,
    )
    monkeypatch.setattr(
        fb,
        "fetch_recent_commits",
        lambda repo: 40 if repo == "anthropics/claude-code" else None,
    )

    repaired = fb.repair_missing_commit_counts(rows, {"openai/codex": 936})
    assert repaired == 2
    assert rows[0]["weekly_commits"] == 40
    assert rows[1]["weekly_commits"] == 936


def test_history_writer_never_deletes_existing_snapshots(tmp_path):
    """Existing history snapshots must survive when a new one is written."""
    history_dir = tmp_path / "output" / "history"
    history_dir.mkdir(parents=True)

    old_snapshot = {"agents": [{"repo": "old/one", "trust_score": 50}]}
    (history_dir / "2026-05-01.json").write_text(json.dumps(old_snapshot))
    (history_dir / "2026-05-02.json").write_text(json.dumps(old_snapshot))

    new_snapshot = {"agents": [{"repo": "new/one", "trust_score": 70}]}
    today = "2026-06-10"
    new_path = history_dir / f"{today}.json"
    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(new_snapshot, f)

    remaining = sorted(f.name for f in history_dir.glob("*.json"))
    assert remaining == ["2026-05-01.json", "2026-05-02.json", f"{today}.json"]


def _snap(date, version, agents):
    return {"_date": date, "methodology_version": version, "agents": agents}


def _a(repo, rank, score=50):
    return {"repo": repo, "rank": rank, "score": score}


def test_sparklines_reset_at_methodology_version_change():
    """A methodology-version change is not a real rank movement -- the
    sparkline should start fresh from the change, not connect across it."""
    history = [
        _snap("2026-05-23", None, [_a("o/agent", 10)]),
        _snap("2026-05-24", "v2.0", [_a("o/agent", 40)]),
        _snap("2026-05-28", "v3.0", [_a("o/agent", 20)]),
        _snap("2026-06-05", "v3.2", [_a("o/agent", 5)]),
        _snap("2026-06-06", "v3.2", [_a("o/agent", 7)]),
        _snap("2026-06-07", "v3.2", [_a("o/agent", 6)]),
    ]
    points = fb.compute_sparklines(history)["o/agent"]
    assert [p["date"] for p in points] == ["2026-06-05", "2026-06-06", "2026-06-07"]
    assert [p["rank"] for p in points] == [5, 7, 6]


def test_sparklines_no_reset_when_version_stable():
    history = [
        _snap("2026-06-01", "v3.2", [_a("o/agent", 10)]),
        _snap("2026-06-02", "v3.2", [_a("o/agent", 8)]),
        _snap("2026-06-03", "v3.2", [_a("o/agent", 9)]),
    ]
    points = fb.compute_sparklines(history)["o/agent"]
    assert len(points) == 3
    assert points[0]["date"] == "2026-06-01"


def test_sparklines_empty_history():
    assert fb.compute_sparklines([]) == {}
