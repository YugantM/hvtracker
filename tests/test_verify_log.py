"""Public 'recently checked' feed log (verify_log.py)."""
import verify_log


def _reset(tmp):
    verify_log._log = None
    verify_log.init(str(tmp))


def test_record_and_recent_newest_first(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "A", "C", True, False, 1000)
    verify_log.record("acme/b", "B", "B", True, True, 2000)
    r = verify_log.recent()
    assert [x["repo"] for x in r] == ["acme/b", "acme/a"]
    assert r[0]["provisional"] is True and r[1]["grade"] == "C"


def test_dedup_by_repo(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "A", "C", True, False, 1000)
    verify_log.record("acme/a", "A", "B", True, False, 1100)  # re-check moves it to newest
    r = verify_log.recent()
    assert len(r) == 1 and r[0]["grade"] == "B"


def test_persists_across_restart(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "A", "C", True, False, 1000)
    verify_log._log = None  # simulate a process restart
    verify_log.init(str(tmp_path))
    assert verify_log.recent()[0]["repo"] == "acme/a"


def test_trims_to_max(tmp_path):
    _reset(tmp_path)
    for i in range(120):
        verify_log.record("o/r%d" % i, None, "C", True, True, 1000)
    assert len(verify_log.recent(500)) == verify_log.MAX_ENTRIES
