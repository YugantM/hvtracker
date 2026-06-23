"""Unit tests for the GraphQL batch-fetch normalization in fetch_and_build.py.

_gql_normalize is pure (no network): it maps a GitHub GraphQL Repository node
to the REST /repos shape the build pipeline consumes, plus the private
_commits_30d / _signed_ratio fields. These tests lock that contract.
"""
import fetch_and_build as fb


FULL_NODE = {
    "nameWithOwner": "owner/repo",
    "url": "https://github.com/owner/repo",
    "stargazerCount": 1234,
    "forkCount": 56,
    "isArchived": False,
    "pushedAt": "2026-06-20T00:00:00Z",
    "description": "A test repo",
    "primaryLanguage": {"name": "Python"},
    "licenseInfo": {"spdxId": "MIT"},
    "issues": {"totalCount": 7},
    "defaultBranchRef": {
        "name": "main",
        "target": {
            "c30": {"totalCount": 42},
            "recent": {"nodes": [
                {"signature": {"isValid": True}},
                {"signature": {"isValid": False}},
                {"signature": None},
            ]},
        },
    },
}


def test_gql_normalize_maps_rest_shape():
    r = fb._gql_normalize(FULL_NODE)
    assert r["html_url"] == "https://github.com/owner/repo"
    assert r["stargazers_count"] == 1234
    assert r["forks_count"] == 56
    assert r["pushed_at"] == "2026-06-20T00:00:00Z"
    assert r["description"] == "A test repo"
    assert r["language"] == "Python"
    assert r["open_issues_count"] == 7
    assert r["archived"] is False
    assert r["license"] == {"spdx_id": "MIT"}
    assert r["default_branch"] == "main"
    assert r["_source"] == "graphql"


def test_gql_normalize_commit_count_and_signed_ratio():
    r = fb._gql_normalize(FULL_NODE)
    assert r["_commits_30d"] == 42
    # 1 of 3 recent commits has a valid signature -> 0.333
    assert r["_signed_ratio"] == 0.333


def test_gql_normalize_handles_empty_repo():
    node = {
        "nameWithOwner": "o/r", "url": "u",
        "stargazerCount": 0, "forkCount": 0, "isArchived": True,
        "pushedAt": None, "description": None,
        "primaryLanguage": None, "licenseInfo": None,
        "issues": {"totalCount": 0},
        "defaultBranchRef": None,
    }
    r = fb._gql_normalize(node)
    assert r["default_branch"] == "HEAD"
    assert r["_commits_30d"] is None
    assert r["_signed_ratio"] is None
    assert r["license"] == {"spdx_id": None}
    assert r["archived"] is True


def test_gql_normalize_without_signatures_omits_ratio():
    # The light (metadata-only) query used by the runtime batch must not claim a
    # signed ratio, so fetch_signed_commit_ratio falls back to REST if ever called.
    r = fb._gql_normalize(FULL_NODE, with_signatures=False)
    assert "_signed_ratio" not in r
    assert r["_commits_30d"] == 42
    assert r["stargazers_count"] == 1234


def test_gql_fragment_signature_toggle():
    assert "signature" in fb._gql_fragment(True)
    assert "signature" not in fb._gql_fragment(False)


def test_gql_normalize_all_signed():
    node = dict(FULL_NODE)
    node["defaultBranchRef"] = {
        "name": "main",
        "target": {"c30": {"totalCount": 5},
                   "recent": {"nodes": [{"signature": {"isValid": True}}] * 4}},
    }
    assert fb._gql_normalize(node)["_signed_ratio"] == 1.0
