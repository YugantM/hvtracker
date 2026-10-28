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


# The render checks. NOW is the 28 Oct 2026 12:23 UTC monitor reading;
# REPORT and SITEMAP are production's values at that moment.
NOW = cf.datetime(2026, 10, 28, 12, 23, tzinfo=cf.timezone.utc)
SIGNATURE_ERROR = (
    "failed: ClientError: An error occurred (SignatureDoesNotMatch) when calling the "
    "PutObject operation: The request signature we calculated does not match the "
    "signature you provided. Check your key and signing method.")
REPORT = {"generated_at": "2026-10-28T12:14:16Z", "history_archive": "ok"}
SITEMAP = "Wed, 28 Oct 2026 12:16:30 GMT"


def test_fresh_render_has_no_problems():
    assert cf.evaluate_report(REPORT, NOW, max_age_hours=9) == []
    assert cf.evaluate_sitemap(SITEMAP, NOW, max_age_hours=9) == []


def test_the_22_oct_failure_mode_alerts():
    # data.json kept updating, so /healthz was healthy apart from the failed
    # refresh; the pages, sitemap and build report stayed at 21 Oct 20:07 UTC,
    # from before #385 added history_archive.
    report = {"generated_at": "2026-10-21T20:07:12Z"}
    assert cf.evaluate_report(report, NOW, max_age_hours=9) == [
        "site render is 160.3 h old (build_report generated_at 2026-10-21T20:07:12Z, limit 9 h)"]
    assert cf.evaluate_sitemap("Wed, 21 Oct 2026 20:07:40 GMT", NOW, max_age_hours=9) == [
        "sitemap.xml, the render's last write, is 160.3 h old "
        "(Last-Modified Wed, 21 Oct 2026 20:07:40 GMT, limit 9 h)"]


def test_a_render_that_dies_after_the_build_report_alerts_on_the_sitemap():
    assert cf.evaluate_report(REPORT, NOW, max_age_hours=9) == []
    assert cf.evaluate_sitemap("Tue, 27 Oct 2026 23:10:00 GMT", NOW, max_age_hours=9) == [
        "sitemap.xml, the render's last write, is 13.2 h old "
        "(Last-Modified Tue, 27 Oct 2026 23:10:00 GMT, limit 9 h)"]


def test_one_missed_refresh_stays_quiet_two_alert():
    # Last good render 16:05 and the 20:00 one fails. At the 00:23 reading the
    # 00:00 render may still be running: quiet. If it fails too, 03:23 alerts.
    report = {"generated_at": "2026-10-28T16:05:00Z"}
    day = cf.datetime(2026, 10, 29, minute=23, tzinfo=cf.timezone.utc)
    assert cf.evaluate_report(report, day.replace(hour=0), max_age_hours=9) == []
    assert cf.evaluate_report(report, day.replace(hour=3), max_age_hours=9) == [
        "site render is 11.3 h old (build_report generated_at 2026-10-28T16:05:00Z, limit 9 h)"]


def test_failing_history_backup_alerts():
    # Production today: the bucket keys are stale, the render itself is fine.
    problems = cf.evaluate_report({**REPORT, "history_archive": SIGNATURE_ERROR}, NOW, max_age_hours=9)
    assert problems == [
        f"offsite history backup is failing (build_report history_archive: {SIGNATURE_ERROR})"]


def test_ok_disabled_or_missing_history_archive_does_not_alert():
    for value in ("ok", "disabled", None):
        assert cf.evaluate_report({**REPORT, "history_archive": value}, NOW, max_age_hours=9) == []
    assert cf.evaluate_report({"generated_at": REPORT["generated_at"]}, NOW, max_age_hours=9) == []


def test_unknown_render_age_alerts():
    for value in (None, "", "yesterday", "2026-10-28T12:14:16"):  # last: no timezone
        assert cf.evaluate_report({"generated_at": value}, NOW, max_age_hours=9) == [
            f"site render age is unknown (build_report generated_at: {value})"]
    for value in (None, "not a date"):
        assert cf.evaluate_sitemap(value, NOW, max_age_hours=9) == [
            f"sitemap.xml age is unknown (Last-Modified: {value})"]
