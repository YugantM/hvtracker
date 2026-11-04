"""The bucket copy of the daily snapshot is a backup, not part of the render:
a bucket error is reported in build_report.json and the render goes on (#380)."""
import fetch_and_build as fb


def test_bucket_error_is_reported_not_raised(tmp_path, monkeypatch):
    snap = tmp_path / "2026-10-22.json"
    snap.write_text("{}")

    def refuse(*_a, **_k):
        raise RuntimeError("AccessDenied")

    monkeypatch.setattr(fb.storage, "put_file", refuse)
    assert fb.archive_history_snapshot("2026-10-22", str(snap)) == "failed: RuntimeError: AccessDenied"


def test_archive_reports_ok_and_disabled(tmp_path, monkeypatch):
    snap = tmp_path / "2026-10-22.json"
    snap.write_text("{}")
    calls = []
    monkeypatch.setattr(fb.storage, "put_file", lambda key, *_a: calls.append(key) or True)
    assert fb.archive_history_snapshot("2026-10-22", str(snap)) == "ok"
    assert calls == ["history/2026-10-22.json"]
    monkeypatch.setattr(fb.storage, "put_file", lambda *_a: False)
    assert fb.archive_history_snapshot("2026-10-22", str(snap)) == "disabled"


def test_backfill_uploads_missing_snapshots_newest_first(tmp_path, monkeypatch):
    for name in ("2026-10-20.json", "2026-10-21.json", "2026-10-22.json",
                 "2026-10-23.json", "notes.json"):
        (tmp_path / name).write_text("{}")
    calls = []
    monkeypatch.setattr(fb.storage, "put_file", lambda key, *_a: calls.append(key) or True)
    # The bucket has today's copy and 20 Oct; 21 and 22 Oct were missed.
    monkeypatch.setattr(fb.storage, "list_keys",
                        lambda _p: {"history/2026-10-23.json", "history/2026-10-20.json"})
    result = fb.archive_history_snapshot("2026-10-23", str(tmp_path / "2026-10-23.json"))
    assert result == "ok, backfilled 2"
    assert calls == ["history/2026-10-23.json", "history/2026-10-22.json", "history/2026-10-21.json"]

    calls.clear()
    monkeypatch.setattr(fb, "HISTORY_BACKFILL_MAX", 1)
    assert fb.archive_history_snapshot("2026-10-23", str(tmp_path / "2026-10-23.json")) == "ok, backfilled 1"
    assert calls == ["history/2026-10-23.json", "history/2026-10-22.json"]


def test_backfill_error_is_reported(tmp_path, monkeypatch):
    (tmp_path / "2026-10-23.json").write_text("{}")
    monkeypatch.setattr(fb.storage, "put_file", lambda *_a: True)

    def refuse(_p):
        raise RuntimeError("AccessDenied")

    monkeypatch.setattr(fb.storage, "list_keys", refuse)
    assert fb.archive_history_snapshot("2026-10-23", str(tmp_path / "2026-10-23.json")) == "failed: RuntimeError: AccessDenied"
