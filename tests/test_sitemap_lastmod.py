"""Sitemap <lastmod> fingerprint (GSC URL Inspection sweep 2026-10-01).

The live sitemap stamped 2,093 of 2,140 URLs "today" on every refresh because
each data refresh moves the numbers on every data-driven page. These lock the
normalization: a refresh that only moves numbers or reorders rank-driven lists
must not change the fingerprint; a real content change must.
"""
import os
import re

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = "2026-10-01 12:00 UTC"

PAGE = """<html><head><title>Aider: HVTrust {score}/100</title>{robots}</head><body>
<p>Updated {now}</p>
<div class="stat-value">{stars}</div>
<span class="meta">Repo last pushed {days} days ago</span>
<span class="badge grade-{grade}">{grade}</span>
<!--lastmod:skip--><section class="neighbours"><ol>{neighbours}</ol></section><!--/lastmod:skip-->
<p>{text}</p>
</body></html>"""


def _fp(now=NOW, **kw):
    fields = dict(score="75.8", robots="", stars="12.3k", days="3", grade="B",
                  neighbours="<li>Cline</li><li>Codex</li>", text="AI pair programming.",
                  now=now)
    fields.update(kw)
    return fab.lastmod_fingerprint(PAGE.format(**fields).encode("utf-8"), now)


def test_daily_refresh_noise_keeps_fingerprint():
    base = _fp()
    assert _fp(score="76.1", stars="12.4k", days="4") == base
    assert _fp(neighbours="<li>Codex</li><li>Cline</li>") == base
    assert _fp(now="2026-10-02 08:00 UTC") == base


def test_real_content_changes_move_fingerprint():
    base = _fp()
    assert _fp(grade="A") != base
    assert _fp(robots='<meta name="robots" content="noindex">') != base
    assert _fp(text="AI pair programming in your terminal.") != base


def test_template_skip_markers_are_balanced():
    for name in ("agent.html.j2", "compare_pair.html.j2"):
        with open(os.path.join(ROOT, "templates", name), encoding="utf-8") as f:
            src = f.read()
        opens = [m.start() for m in re.finditer(r"<!--lastmod:skip-->", src)]
        closes = [m.start() for m in re.finditer(r"<!--/lastmod:skip-->", src)]
        assert opens, f"{name}: rank-driven regions lost their lastmod:skip markers"
        assert len(opens) == len(closes), f"{name}: unbalanced lastmod:skip markers"
        assert all(o < c for o, c in zip(opens, closes)), f"{name}: marker out of order"
