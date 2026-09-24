"""--render-only must not touch the network.

normalize_license_type used to call classify_license (up to five
raw.githubusercontent.com fetches per repo on a cache miss) for every row
without a GitHub SPDX id, on every render. That made a "no API calls" render
take ~4.5 minutes and was most of the test suite's 27-minute runtime."""
import inspect

import pytest

import fetch_and_build as fab


def test_offline_keeps_the_stored_classification(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network classification in an offline render")
    monkeypatch.setattr(fab, "classify_license", boom)
    assert fab.normalize_license_type({"repo": "o/r", "license_type": "proprietary"}, offline=True) == "proprietary"
    assert fab.normalize_license_type({"repo": "o/r"}, offline=True) == "unlicensed"
    assert fab.normalize_license_type({"repo": "o/r", "license_spdx": "MIT"}, offline=True) == "open"
    assert fab.normalize_license_type({"repo": "o/r", "license_override": "open"}, offline=True) == "open"


def test_online_still_reclassifies(monkeypatch):
    monkeypatch.setattr(fab, "classify_license", lambda repo, spdx: "source-available")
    assert fab.normalize_license_type({"repo": "o/r", "license_type": "open"}) == "source-available"


def test_render_only_passes_offline_at_every_call_site():
    src = inspect.getsource(fab.main)
    calls = [line.strip() for line in src.splitlines() if "normalize_license_type(" in line]
    assert calls and all("offline=render_only" in c for c in calls), calls


def test_render_only_makes_no_http_requests(monkeypatch, tmp_path):
    """End to end: a full render-only pass with every HTTP entry point
    recorded (not raised: the generator swallows exceptions around its
    fetches, so a raising stub would pass silently). The committed fixture
    has ~1,450 provisional rows with no SPDX id, exactly the rows that used to
    trigger license fetches."""
    import glob
    import os
    import shutil
    import urllib.request
    import requests
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(tmp_path / "data")
    os.makedirs(tmp_path / "output" / "history")
    shutil.copy(os.path.join(root, "data", "render_state.json"), tmp_path / "data" / "render_state.json")
    for h in glob.glob(os.path.join(root, "seed", "history", "*.json")):
        shutil.copy(h, tmp_path / "output" / "history")

    calls = []

    def record(*a, **k):
        calls.append(a[:2])
        raise requests.ConnectionError("offline test")
    for name in ("get", "post", "head", "request"):
        monkeypatch.setattr(requests, name, record)
    monkeypatch.setattr(requests.Session, "request", record)
    monkeypatch.setattr(urllib.request, "urlopen", record)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    fab.run_refresh("render")
    assert (tmp_path / "index.html").is_file()
    assert calls == [], f"{len(calls)} HTTP call(s) during render-only, first: {calls[:3]}"
