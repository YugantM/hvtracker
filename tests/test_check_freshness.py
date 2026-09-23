"""The freshness monitor must flag the 22 Sep 2026 failure mode (scheduler
never started, data a day old, /healthz still "ok") and stay quiet when the
site is healthy."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "check_freshness", os.path.join(ROOT, "scripts", "check_freshness.py"))
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)

HEALTHY = {
    "status": "ok",
    "data_age_seconds": 2 * 3600,
    "scheduler_running": True,
    "scheduler_error": None,
    "last_refresh_succeeded": True,
    "last_refresh_mode": "auto",
}


def test_healthy_site_has_no_problems():
    assert cf.evaluate(HEALTHY, max_age_hours=12) == []


def test_the_22_sep_failure_mode_alerts():
    h = {**HEALTHY, "scheduler_running": False, "data_age_seconds": 30 * 3600}
    problems = cf.evaluate(h, max_age_hours=12)
    assert any("scheduler is not running" in p for p in problems)
    assert any("30.0 h old" in p for p in problems)


def test_stale_data_alone_alerts():
    problems = cf.evaluate({**HEALTHY, "data_age_seconds": 13 * 3600}, max_age_hours=12)
    assert problems == ["data is 13.0 h old (limit 12 h)"]


def test_failed_refresh_alerts():
    h = {**HEALTHY, "last_refresh_succeeded": False, "last_refresh_error": "boom"}
    assert any("last refresh failed" in p for p in cf.evaluate(h, max_age_hours=12))


def test_unknown_age_alerts_but_missing_scheduler_key_does_not():
    h = {k: v for k, v in HEALTHY.items() if k != "scheduler_running"}
    assert cf.evaluate(h, max_age_hours=12) == []
    assert cf.evaluate({**HEALTHY, "data_age_seconds": None}, max_age_hours=12)
