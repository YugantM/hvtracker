"""Dark mode (plan 2.7) is opt-in per audited page and never moves the
grade colours, which are a design invariant (grade B = #2c5282)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDITED = ["template.html", "templates/adopters.html.j2", "templates/agent.html.j2", "templates/compare_pair.html.j2",
           "templates/category.html.j2", "templates/methodology.html.j2"]


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_grade_colours_are_literal_hex_in_site_css():
    css = _read("static/site.css")
    for grade, hex_ in (("A", "#2f6846"), ("B", "#2c5282"), ("C", "#8b6914"), ("D", "#57524c")):
        assert re.search(r"\.grade-%s \{ color: #fff; background: %s; \}" % (grade, hex_), css), grade


def test_dark_tokens_only_apply_to_opted_in_pages():
    css = _read("static/site.css")
    block = css[css.index("@media (prefers-color-scheme: dark)"):]
    assert block.split("{", 2)[1].strip().startswith("html.theme-auto")
    for rel in AUDITED:
        assert '<html lang="en" class="theme-auto">' in _read(rel), rel
    # Pages not yet audited stay light, e.g. /trends/.
    assert "theme-auto" not in _read("templates/trends.html.j2")
