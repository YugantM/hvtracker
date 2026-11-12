"""GA must count people, not automation.

456 of the 678 sessions that landed on /compare/ in 28 days came from one
"Chrome" in Singapore with zero engagement: automation with a spoofed user
agent, about a tenth of all GA sessions. Automation sets navigator.webdriver
even when it spoofs the UA, so every page that loads GA disables it for
webdriver, known bot UAs, local hosts and the hvt_notrack opt-out.

By November 2026, 82% of GA sessions came from headless browsers that hide
webdriver and send a plain Chrome UA (GA screen 1280x720 from Tencent Cloud,
1280x1200 from a residential proxy pool). A browser run with an emulated
viewport (Playwright, Puppeteer) reports a screen exactly the size of its
viewport; a real desktop window is shorter than its screen by the toolbar.
The second check disables GA on that, limited to what it can't misread:
no touch (phones), a Chrome UA (Firefox's resistFingerprinting and Tor
report screen = window), not Brave (farbles screen from the window size)
and not browser fullscreen (F11, which matches display-mode: fullscreen).

That caught 1280x1200 but not 1280x720: GA reports that crawler's browser
as "(not set)", so it likely fails the Chrome-UA condition. The third check
disables GA for a 1280x720 screen on its own, since screen size is the only
thing GA proves it reports. The owner accepted the cost: a 1920x1080 laptop
at 150% scaling also reports 1280x720 (31 named-browser sessions in 28 days,
against 10,234 from the crawler)."""
import os
import subprocess

import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GA = "googletagmanager.com/gtag/js?id=G-TZ8921LR0K"
VIEWPORT_CHECK = (
    'if(screen.width===innerWidth&&screen.height===innerHeight&&navigator.maxTouchPoints===0'
    '&&/Chrome\\//.test(ua)&&!navigator.brave&&!matchMedia("(display-mode: fullscreen)").matches)'
    '{window["ga-disable-G-TZ8921LR0K"]=true}')
SCREEN_CHECK = 'if(screen.width===1280&&screen.height===720){window["ga-disable-G-TZ8921LR0K"]=true}'


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
        if rel != "app.py":  # an f-string there; its rendered output is checked below
            assert VIEWPORT_CHECK in head, f"{rel}: guard lacks the emulated-viewport check"
            assert SCREEN_CHECK in head, f"{rel}: guard lacks the 1280x720 screen check"
    assert len(pages) >= 30


def test_app_pages_render_the_same_checks():
    html = app._marketing_page("Title", "Eyebrow", "Heading", "<p>Body</p>")
    head = html[:html.index(GA)]
    assert VIEWPORT_CHECK in head
    assert SCREEN_CHECK in head


def test_custom_events_skip_webdriver_too():
    js = open(os.path.join(ROOT, "analytics.js"), encoding="utf-8").read()
    assert js.index("if (navigator.webdriver) return;") < js.index("window.hvtTrack = function")
