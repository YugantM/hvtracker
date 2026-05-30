"""Tests for the db.py file-fallback path (no live Postgres needed)."""
import db


def test_not_enabled_without_database_url(monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "")
    assert db.enabled() is False


def test_load_agents_fallback_reads_agents_json():
    agents = db.load_agents()
    assert isinstance(agents, list)
    assert len(agents) == db.count_agents()
    assert len(agents) > 100


def test_loaded_agents_have_core_keys():
    for a in db.load_agents():
        assert "repo" in a and "/" in a["repo"]
        assert "name" in a
