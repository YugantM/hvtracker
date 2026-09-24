"""Docker images and trust confidence (the 2026-09-19 flap).

Nine MCP servers whose only package is a Docker image swung between trust
confidence 1.0 and 0.67 (~20 points, grade to D and back) from one render to
the next. Two defects compounded:

1. data.json's whitelist dropped docker_image/vscode_extension, so a row
   carried forward by batch mode lost its package and counted downloads as
   not applicable, while the render that fetched it counted them as missing.
2. fetch_docker_pulls sent refs like `docker.io/org/app:1.0` and
   `ghcr.io/org/app:v1` to the Docker Hub API verbatim, which 404s — only 5 of
   91 roster images ever returned a pull count.
"""
import inspect

import fetch_and_build as fab


def _row(**overrides):
    row = {
        "repo": "org/app",
        "listing_status": "listed",
        "days_ago": 10,
        "scorecard_score": 6.0,
        "license_spdx": "MIT",
        "npm_package": "",
        "pypi_package": "",
        "crate_package": "",
        "docker_image": "",
        "vscode_extension": "",
        "weekly_downloads": None,
    }
    row.update(overrides)
    return row


def test_docker_hub_repo_normalises_pull_references():
    cases = {
        "n8nio/n8n": "n8nio/n8n",
        "docker.io/armlimited/arm-mcp:2.4.0": "armlimited/arm-mcp",
        "index.docker.io/zenmldocker/mcp-zenml:1.5.1": "zenmldocker/mcp-zenml",
        "meloncafe/chromadb-remote-mcp:latest": "meloncafe/chromadb-remote-mcp",
        "nginx": "library/nginx",
        "docker.io/library/nginx:1.27@sha256:abc": "library/nginx",
        "Docker.io/Org/App": "org/app",
    }
    for image, expected in cases.items():
        assert fab.docker_hub_repo(image) == expected, image


def test_docker_hub_repo_rejects_other_registries_and_junk():
    for image in (
        "ghcr.io/buildkite/buildkite-mcp-server:0.7.0",
        "quay.io/org/app",
        "localhost:5000/app",
        "registry.example.com:443/org/app",
        "",
        None,
        "a/b/c",
    ):
        assert fab.docker_hub_repo(image) is None, image


def test_fetch_docker_pulls_asks_the_hub_for_the_bare_repo(monkeypatch):
    seen = []

    class Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"pull_count": 1234}

    def fake_get(url, timeout):
        seen.append(url)
        return Resp()

    monkeypatch.setattr(fab.requests, "get", fake_get)
    assert fab.fetch_docker_pulls("docker.io/armlimited/arm-mcp:2.4.0") == 1234
    assert seen == ["https://hub.docker.com/v2/repositories/armlimited/arm-mcp/"]

    seen.clear()
    assert fab.fetch_docker_pulls("ghcr.io/org/app:v1") is None
    assert seen == [], "a non-Hub image has no pull count to ask for"


def test_non_hub_image_is_not_applicable_so_confidence_holds():
    """A ghcr.io image has no public pull count: like shipping no package,
    that is 'not applicable', not 'unverified'."""
    ghcr = fab.compute_trust_score(_row(docker_image="ghcr.io/org/app:v1"))
    none = fab.compute_trust_score(_row())
    assert ghcr["trust_confidence"] == none["trust_confidence"] == 1.0
    assert ghcr["trust_score"] == none["trust_score"]


def test_hub_image_counts_and_its_pulls_are_the_evidence():
    missing = fab.compute_trust_score(_row(docker_image="docker.io/org/app:1.0"))
    present = fab.compute_trust_score(
        _row(docker_image="docker.io/org/app:1.0", weekly_downloads=50_000))
    assert missing["trust_confidence"] == 0.67
    assert present["trust_confidence"] == 1.0


def test_package_ids_survive_the_data_json_whitelist():
    """Batch mode carries un-fetched rows forward from data.json, so every
    field compute_trust_score reads to decide applicability must be published
    there — otherwise the row scores differently in the render that fetched it
    than in every render after."""
    source = inspect.getsource(fab.main)
    _, _, after_writer = source.partition("# Write data.json (machine-readable leaderboard)")
    whitelist, _, _ = after_writer.partition("Wrote data.json")
    for key in ("npm_package", "pypi_package", "crate_package", "docker_image", "vscode_extension"):
        assert f'"{key}": r.get("{key}", "")' in whitelist, key

