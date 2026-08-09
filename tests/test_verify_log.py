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


# ---- refresh must not masquerade as a client check -------------------------
# The nightly verify-feed job used to call record(), which restamped every
# provisional row with the same timestamp each night, pinned them to the top of
# the public feed, and inflated `checks`. These lock the split.

def test_refresh_does_not_move_position_or_count(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "A", "C", True, True, 1000)
    verify_log.record("acme/b", "B", "B", True, True, 2000)
    before = verify_log.recent()[0]["checked_at"]

    verify_log.refresh("acme/a", None, "B", True, 1500)

    r = verify_log.recent()
    assert [x["repo"] for x in r] == ["acme/b", "acme/a"], "refresh must not reorder the feed"
    a = next(x for x in r if x["repo"] == "acme/a")
    assert a["checks"] == 1, "refresh must not count as a check"
    assert a["checked_at"] == before or a["checked_at"] <= before
    assert a["grade"] == "B" and a["stars"] == 1500, "refresh must still update the verdict"
    assert a["refreshed_at"] >= a["checked_at"]


def test_refresh_never_creates_an_entry(tmp_path):
    _reset(tmp_path)
    verify_log.refresh("acme/ghost", None, "C", True, 10)
    assert verify_log.recent() == []


def test_refresh_preserves_name(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "Acme", "C", True, True, 1000)
    verify_log.refresh("acme/a", None, "C", True, 1000)  # open lookup has no name
    assert verify_log.recent()[0]["name"] == "Acme"


def test_record_increments_checks(tmp_path):
    _reset(tmp_path)
    verify_log.record("acme/a", "Acme", "C", True, True, 1000)
    verify_log.record("acme/a", None, "C", True, True, 1000)
    r = verify_log.recent()[0]
    assert r["checks"] == 2
    assert r["name"] == "Acme", "a nameless re-check must not blank an existing name"
