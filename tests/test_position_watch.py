"""scripts/position_watch.py alerts when average position regresses (plan 3.4)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import position_watch as pw  # noqa: E402


def test_windows_are_two_adjacent_complete_weeks():
    this, prev = pw.windows(date(2026, 9, 24))
    assert this == (date(2026, 9, 15), date(2026, 9, 21))
    assert prev == (date(2026, 9, 8), date(2026, 9, 14))


def test_summarize_reads_the_aggregate_row():
    q = lambda s, e: {"rows": [{"clicks": 80, "impressions": 5000, "position": 8.94}]}  # noqa: E731
    assert pw.summarize(q, (date(2026, 9, 15), date(2026, 9, 21))) == {
        "clicks": 80, "impressions": 5000, "position": 8.9}
    assert pw.summarize(lambda s, e: {}, (date(2026, 9, 15), date(2026, 9, 21))) is None


def test_alerts_only_past_the_threshold():
    ok = {"clicks": 80, "impressions": 5000, "position": 8.9}
    bad = {"clicks": 30, "impressions": 4000, "position": 13.2}
    code, msg = pw.evaluate(ok, dict(ok, position=8.1))
    assert code == 0 and "+0.8 vs the week before" in msg
    code, msg = pw.evaluate(bad, ok)
    assert code == 2 and "reverting" in msg
    assert pw.evaluate(None, ok)[0] == 1


def test_not_configured_is_green(monkeypatch, capsys):
    monkeypatch.delenv("GSC_SERVICE_ACCOUNT_JSON", raising=False)
    assert pw.main() == 0
    assert "not configured" in capsys.readouterr().out
