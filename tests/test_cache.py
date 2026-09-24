"""cache.py: the on-volume API cache that replaced Redis (plan 3.5)."""
import os
import time

import cache


def _counting(monkeypatch, tmp_path, ttl=3600, skip_none=False, result="v"):
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path) if tmp_path else "")
    monkeypatch.setattr(cache, "_pruned", False)
    calls = []

    @cache.cached("t", ttl=ttl, skip_none=skip_none)
    def fetch(x):
        calls.append(x)
        return result
    return fetch, calls


def test_pass_through_when_unconfigured(monkeypatch):
    fetch, calls = _counting(monkeypatch, None)
    fetch("a"), fetch("a")
    assert calls == ["a", "a"]


def test_second_call_is_served_from_disk(monkeypatch, tmp_path):
    fetch, calls = _counting(monkeypatch, tmp_path, result={"stars": 5})
    assert fetch("o/r") == {"stars": 5} and fetch("o/r") == {"stars": 5}
    assert calls == ["o/r"]
    assert len(list(tmp_path.glob("*.json"))) == 1 and not list(tmp_path.glob("*.tmp"))


def test_expired_entries_are_refetched(monkeypatch, tmp_path):
    fetch, calls = _counting(monkeypatch, tmp_path, ttl=-1)
    fetch("a"), fetch("a")
    assert calls == ["a", "a"]


def test_none_is_not_cached_with_skip_none(monkeypatch, tmp_path):
    fetch, calls = _counting(monkeypatch, tmp_path, skip_none=True, result=None)
    fetch("a"), fetch("a")
    assert calls == ["a", "a"] and not list(tmp_path.glob("*.json"))


def test_stale_files_are_pruned_on_first_write(monkeypatch, tmp_path):
    old = tmp_path / "old.json"
    old.write_text("{}")
    past = time.time() - 3 * 86400
    os.utime(old, (past, past))
    fetch, _ = _counting(monkeypatch, tmp_path)
    fetch("a")
    assert not old.exists()
