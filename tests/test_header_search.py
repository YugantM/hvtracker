"""Search on every page (plan 5.1).

Search visitors land on agent and compare pages (94% of search clicks), and
the only search box used to be the homepage leaderboard's. The shared header
now carries one, backed by a compact /data/search-index.json that loads on
first use. The homepage keeps its own leaderboard search instead."""
import os

from jinja2 import Environment, FileSystemLoader

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _header(**ctx):
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")), autoescape=True)
    return env.get_template("_site_header.html.j2").render(updated="now", **ctx)


def test_every_page_header_has_the_search_box_and_script():
    html = _header()
    assert 'id="hdr-q"' in html and 'name="q"' in html and 'action="/"' in html  # no-JS: /?q=
    assert 'role="combobox"' in html and 'aria-controls="hdr-results"' in html
    assert '/static/search.js' in html and 'class="hdr-search-btn"' in html


def test_homepage_keeps_its_own_search_instead():
    assert 'id="hdr-q"' not in _header(header_search=False)
    src = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    assert '{% set header_search = false %}' in src.split('{% include "_site_header.html.j2" %}')[0]


def test_search_index_is_compact_and_hides_provisional_grades():
    rows = [
        {"name": "Composio", "slug": "composio", "repo": "composiohq/composio",
         "category": "Protocols & Tool Integration", "trust_score": 76.8, "evidence_grade": "B",
         "description": "not shipped"},
        {"name": "New MCP", "slug": "new-mcp", "repo": "o/new-mcp", "category": "MCP Servers",
         "trust_score": 12.0, "evidence_grade": "D", "pending_signals": True},
    ]
    idx = fab.build_search_index(rows)
    assert idx["fields"] == ["name", "slug", "repo", "category", "score", "grade"]
    assert idx["rows"] == [["Composio", "composio", "composiohq/composio",
                            "Protocols & Tool Integration", 76.8, "B"],
                           ["New MCP", "new-mcp", "o/new-mcp", "MCP Servers", 12.0, None]]


def test_the_index_is_written_with_the_board_and_not_counted_as_machine_use():
    import inspect

    import app
    assert "build_search_index(board_rows)" in inspect.getsource(fab.main)
    assert "/data/search-index.json" in app._USAGE_EXCLUDED_PATHS


def test_the_script_ships_in_the_image():
    assert os.path.isfile(os.path.join(ROOT, "static", "search.js"))
    assert "COPY static/ static/" in open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8").read()
