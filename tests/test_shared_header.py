"""One site header everywhere: templates/_site_header.html.j2.

Hand-written pages (blog posts, /changelog/, /scan/, /verify/, /live/,
/compare/) used to carry their own copies, which drifted: stale links, no
mobile Menu. They now hold a <!--#site-header--> slot that the generator
(blog, changelog) or the app (tools) fills from the partial."""
import glob
import os

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "<!--#site-header-->"
HAND_WRITTEN = (glob.glob(os.path.join(ROOT, "blog_static", "*", "index.html"))
                + [os.path.join(ROOT, p, "index.html") for p in ("changelog", "scan", "verify", "live", "compare")])


def test_hand_written_pages_use_the_slot_not_a_copy():
    for p in HAND_WRITTEN:
        html = open(p, encoding="utf-8").read()
        rel = os.path.relpath(p, ROOT)
        assert html.count(MARK) == 1, rel
        assert '<header class="site-header">' not in html, rel
        assert "fonts.googleapis.com" not in html, rel  # site.css ships the faces


def test_generator_fills_the_slot(tmp_path):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")), autoescape=True)
    page = tmp_path / "index.html"
    page.write_text(f"<body>\n  {MARK}\n  <main></main>\n</body>")
    assert fab.fill_site_header(str(page), env, "2026-09-24 12:00 UTC")
    html = page.read_text()
    assert MARK not in html and 'class="nav-toggle"' in html and "2026-09-24 12:00 UTC" in html
    assert not fab.fill_site_header(str(page), env, "x")  # idempotent: nothing left to fill


def test_app_header_is_the_partial():
    import app
    html = app._site_header_html("now")
    assert 'class="nav-toggle"' in html and 'href="/live/"' in html  # partial-only link
    filled = app._with_site_header(f"<p>{MARK}</p>")
    assert MARK not in filled and '<header class="site-header">' in filled
