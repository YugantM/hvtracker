"""The refresh scheduler must start on every boot, at any cadence.

On 22 Sep 2026 the production scheduler never started: the site served
day-old data for over a day while /healthz still said "ok". These tests lock
the pieces that decide whether refreshes run at all.
"""
import os
import sys

import pytest
from apscheduler.triggers.cron import CronTrigger


@pytest.fixture()
def app_module(monkeypatch, tmp_path):
    # Only matters if this is the first import of app in the session: keep its
    # volume paths out of the repo. No reload — other test modules hold app.
    if "app" not in sys.modules:
        monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    import app
    yield app
    if app._scheduler is not None:
        app._scheduler.shutdown(wait=False)
    app._scheduler = None
    app._scheduler_error = None


def test_signals_cron_sub_hour_keeps_minute_step(app_module):
    fields = app_module._signals_cron(30)
    assert fields == {"minute": "*/30"}
    CronTrigger(timezone="UTC", **fields)


def test_signals_cron_hourly_and_slower_steps_the_hour(app_module):
    # minute="*/360" is rejected by APScheduler ("step value (360) is higher
    # than the total range"), and at startup that would crash the whole app.
    with pytest.raises(ValueError):
        CronTrigger(minute="*/360", timezone="UTC")
    assert app_module._signals_cron(360) == {"hour": "*/6", "minute": 30}
    assert app_module._signals_cron(60) == {"hour": "*/1", "minute": 30}
    for minutes in (60, 120, 360, 720):
        CronTrigger(timezone="UTC", **app_module._signals_cron(minutes))


def test_start_scheduler_registers_every_job(app_module, monkeypatch):
    monkeypatch.delenv("DISABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("SIGNALS_REFRESH_MIN", raising=False)
    app_module._start_scheduler()
    assert app_module._scheduler_error is None
    assert app_module._scheduler is not None and app_module._scheduler.running
    jobs = {job.id: job for job in app_module._scheduler.get_jobs()}
    assert {"refresh", "signals-refresh", "usage-flush"} <= set(jobs)
    # Default signals cadence is 6 hours, expressed on the hour field.
    assert "hour='*/6'" in str(jobs["signals-refresh"].trigger)
    assert set(app_module._scheduled_jobs()) == set(jobs)


def test_start_scheduler_failure_is_recorded_not_raised(app_module, monkeypatch):
    class Broken:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("scheduler exploded")

    monkeypatch.delenv("DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr(app_module, "BackgroundScheduler", Broken)
    app_module._start_scheduler()  # must not raise: the site stays up
    assert app_module._scheduler is None
    assert "scheduler exploded" in app_module._scheduler_error


def test_start_scheduler_respects_disable_flag(app_module):
    assert os.environ.get("DISABLE_SCHEDULER") == "1"
    app_module._start_scheduler()
    assert app_module._scheduler is None
    assert app_module._scheduler_error is None


def test_boot_refresh_switch(app_module, monkeypatch):
    started = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._args = args

        def start(self):
            started.append(self._args[0])

    monkeypatch.setattr(app_module.threading, "Thread", FakeThread)
    monkeypatch.setenv("HVT_BOOT_REFRESH", "0")
    app_module._kick_boot_refresh("render", "fp")
    assert started == []  # the suite's default: no real refreshes under pytest
    monkeypatch.setenv("HVT_BOOT_REFRESH", "1")
    app_module._kick_boot_refresh("render", "fp")
    assert started == ["render"]
