"""Dark mode (plan 2.7) follows the system on every page, and never moves the
grade colours, which are a design invariant (grade B = #2c5282)."""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_grade_colours_are_literal_hex_in_site_css():
    css = _read("static/site.css")
    for grade, hex_ in (("A", "#2f6846"), ("B", "#2c5282"), ("C", "#8b6914"), ("D", "#57524c")):
        assert re.search(r"\.grade-%s \{ color: #fff; background: %s; \}" % (grade, hex_), css), grade


def test_site_css_dark_palette_applies_to_every_page():
    css = _read("static/site.css")
    block = css[css.index("@media (prefers-color-scheme: dark)"):]
    # html:root outranks the page-level :root overrides some templates carry.
    assert block.split("{", 2)[1].strip().startswith("html:root")


def _page_sources():
    pages = [p for p in glob.glob(os.path.join(ROOT, "templates", "*.j2"))
             if "<html" in open(p, encoding="utf-8").read()
             and os.path.basename(p) not in ("submit.html", "correct.html")]
    pages += [os.path.join(ROOT, p) for p in ("template.html", "scan/index.html", "verify/index.html",
                                               "live/index.html", "compare/index.html", "changelog/index.html")]
    pages += glob.glob(os.path.join(ROOT, "blog_static", "*", "index.html"))
    return pages


def test_every_page_gets_a_dark_palette():
    """Either it links site.css, or it carries its own dark block (the
    hand-written blog posts and /changelog/ define their palette inline)."""
    missing = []
    for p in _page_sources():
        html = open(p, encoding="utf-8").read()
        if "site.css" not in html and "prefers-color-scheme: dark" not in html:
            missing.append(os.path.relpath(p, ROOT))
    assert not missing, missing
    # The inline pages built in Python link site.css too.
    assert "/static/site.css" in _read("app.py")
    assert 'href="/static/site.css?v={css_hash}"' in _read("fetch_and_build.py")


def test_hand_written_pages_have_no_light_only_page_background():
    for p in glob.glob(os.path.join(ROOT, "blog_static", "*", "index.html")) + [os.path.join(ROOT, "changelog", "index.html")]:
        html = open(p, encoding="utf-8").read()
        assert not re.search(r"\.page\s*\{[^}]*background:\s*#f4f1eb", html), os.path.relpath(p, ROOT)


def test_auth_widget_styles_have_a_dark_override():
    """auth.js injects the header sign-in / account / notification styles with
    literal light values; dark mode must override them (live 'Sign in' button
    was light text on white before this)."""
    js = _read("auth.js")
    dark = js[js.index("@media (prefers-color-scheme:dark){"):]
    assert ".hvt-auth-btn,.hvt-bell,.hvt-auth-pop{background:var(--card)}" in dark


def test_marketing_pages_take_their_palette_from_site_css():
    """app.py's _marketing_page used to redefine --lobster/--muted/... with
    older, paler values (the orange labels read at 2.5-2.9:1 in light mode)."""
    import inspect
    import app
    src = inspect.getsource(app._marketing_page)
    head = src[src.index("<style>"):src.index("</style>")]
    for token in ("--lobster:", "--muted:", "--blue-strong:", "--paper:", "--ink:"):
        assert token not in head, token
