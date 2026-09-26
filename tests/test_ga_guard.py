"""GA must count people, not automation.

456 of the 678 sessions that landed on /compare/ in 28 days came from one
"Chrome" in Singapore with zero engagement: automation with a spoofed user
agent, about a tenth of all GA sessions. Automation sets navigator.webdriver
even when it spoofs the UA, so every page that loads GA disables it for
webdriver, known bot UAs, local hosts and the hvt_notrack opt-out."""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GA = "googletagmanager.com/gtag/js?id=G-TZ8921LR0K"


def _tracked_sources():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.endswith((".j2", ".html", ".py")) and not p.startswith("tests/")]


def test_every_page_that_loads_ga_guards_it_first():
    pages = []
    for rel in _tracked_sources():
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        if GA not in text:
            continue
        pages.append(rel)
        guard_at = text.find('window["ga-disable-G-TZ8921LR0K"]')
        assert 0 <= guard_at < text.index(GA), f"{rel}: GA loads without the guard before it"
        head = text[:text.index(GA)]
        for check in ("navigator.webdriver", "HeadlessChrome", "hvt_notrack"):
            assert check in head, f"{rel}: guard lacks {check}"
    assert len(pages) >= 30


def test_custom_events_skip_webdriver_too():
    js = open(os.path.join(ROOT, "analytics.js"), encoding="utf-8").read()
    assert js.index("if (navigator.webdriver) return;") < js.index("window.hvtTrack = function")
