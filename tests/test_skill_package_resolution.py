"""build_skill_rows only records packages the registry actually serves.

It used to record any non-private package.json / pyproject.toml name. 47
roster ids (2026-09-24) named packages that were never published or had been
unpublished, so those listings scored at 2/3 confidence for a downloads signal
that could never arrive.
"""
import json

import build_skill_rows as bsr


class Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body


REGISTRY = {
    "https://registry.npmjs.org/live-pkg": Resp(200, {"dist-tags": {"latest": "1.0.0"}}),
    "https://registry.npmjs.org/@scope%2Flive": Resp(200, {"dist-tags": {"latest": "2.0.0"}}),
    # npm's tombstone for an unpublished package: 200, no dist-tags.
    "https://registry.npmjs.org/gone-pkg": Resp(200, {"time": {"unpublished": {}}}),
    "https://pypi.org/pypi/live-py/json": Resp(200, {"info": {}}),
}


def fake_get(url, timeout=None, **_):
    return REGISTRY.get(url, Resp(404))


def test_is_published_reads_the_registry(monkeypatch):
    monkeypatch.setattr(bsr.requests, "get", fake_get)
    assert bsr.is_published("npm", "live-pkg")
    assert bsr.is_published("npm", "@scope/live")
    assert not bsr.is_published("npm", "gone-pkg"), "unpublished tombstone"
    assert not bsr.is_published("npm", "never-published")
    assert bsr.is_published("pypi", "live-py")
    assert not bsr.is_published("pypi", "never-published")


def test_resolve_packages_skips_unpublished_manifest_names(monkeypatch):
    monkeypatch.setattr(bsr.requests, "get", fake_get)
    files = {
        ("org/published", "package.json"): json.dumps({"name": "live-pkg"}),
        ("org/published", "pyproject.toml"): 'name = "live-py"\n',
        ("org/tooling-only", "package.json"): json.dumps({"name": "never-published"}),
        ("org/tooling-only", "pyproject.toml"): 'name = "never-published"\n',
    }
    monkeypatch.setattr(bsr, "get_file", lambda repo, path: files.get((repo, path)))
    assert bsr.resolve_packages("org/published") == {
        "npm_package": "live-pkg", "pypi_package": "live-py"}
    assert bsr.resolve_packages("org/tooling-only") == {}
