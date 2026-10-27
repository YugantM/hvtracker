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
