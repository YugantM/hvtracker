"""Unit tests for the runtime scorecard-cache re-pull.

The live app must re-pull scorecard-cache.json from the `data` branch so
full/batch refreshes apply the latest OSSF scan instead of the deploy-time
image snapshot (which ages out to the deps.dev fallback after 48h). The pull
is best-effort: a bad/unreachable response must never clobber the baked cache.
"""
import json

import app


def _fake_resp(payload: bytes):
    class FakeResp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return lambda *a, **k: FakeResp()


def test_pull_writes_fresh_cache(tmp_path, monkeypatch):
    dest = tmp_path / "scorecard-cache.json"
    monkeypatch.setattr(app, "SCORECARD_CACHE_PATH", str(dest))
    payload = json.dumps({
        "scanned_at": "2026-06-17T18:42:25Z",
        "agents": {"vercel/ai": {"score": 7.5, "checks": {}, "scanned_at": "2026-06-17T18:42:25Z"}},
    }).encode()
    monkeypatch.setattr("urllib.request.urlopen", _fake_resp(payload))

    assert app._pull_scorecard_cache() is True
    written = json.loads(dest.read_text())
    assert written["agents"]["vercel/ai"]["score"] == 7.5


def test_pull_failure_keeps_baked_cache(tmp_path, monkeypatch):
    dest = tmp_path / "scorecard-cache.json"
    dest.write_text('{"agents": {"vercel/ai": {"score": 6.4}}}')
    monkeypatch.setattr(app, "SCORECARD_CACHE_PATH", str(dest))

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", boom)

    assert app._pull_scorecard_cache() is False
    # Existing baked cache must be left intact.
    assert json.loads(dest.read_text())["agents"]["vercel/ai"]["score"] == 6.4


def test_pull_rejects_empty_agents(tmp_path, monkeypatch):
    dest = tmp_path / "scorecard-cache.json"
    dest.write_text('{"agents": {"vercel/ai": {"score": 6.4}}}')
    monkeypatch.setattr(app, "SCORECARD_CACHE_PATH", str(dest))
    monkeypatch.setattr("urllib.request.urlopen", _fake_resp(b'{"agents": {}}'))

    assert app._pull_scorecard_cache() is False
    assert json.loads(dest.read_text())["agents"]["vercel/ai"]["score"] == 6.4
