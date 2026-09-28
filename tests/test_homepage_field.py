"""Roster `homepage` (a maintainer's official site, #216) and the
corrections monitor that would have surfaced #216 after five days."""
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from check_corrections import overdue  # noqa: E402


def _render(**row):
    from test_agent_verdict_card import _render as render
    return render(pending_signals=False, **row)


def test_roster_homepages_are_plain_https_urls():
    """Rendered into href attributes, so nothing but https:// may get in."""
    with open(os.path.join(ROOT, "agents.json"), encoding="utf-8") as f:
        roster = json.load(f)
    homepages = {a["repo"]: a["homepage"] for a in roster if "homepage" in a}
    assert homepages, "expected at least HOL Guard to carry a homepage"
    for repo, url in homepages.items():
        assert re.fullmatch(r"https://[A-Za-z0-9.-]+(/[^\s\"'<>]*)?", url), (repo, url)


def _hero_links(html):
    return re.search(r'<div class="source-links">(.*?)</div>', html, re.S).group(1)


def test_page_has_repository_and_website_buttons_and_json_ld():
    html = _render(homepage="https://hol.org/guard", homepage_source="roster", homepage_label="hol.org/guard",
                   homepage_icon_src="/site-icons/abc.png")
    links = _hero_links(html)
    assert re.search(r'class="src-btn" href="https://github.com/[^"]+"[^>]*>\s*<svg[^>]*>.*?</svg>\s*Repository', links, re.S)
    assert re.search(r'class="src-btn" href="https://hol.org/guard" target="_blank" rel="noopener noreferrer" '
                     r'title="hol.org/guard">\s*<img class="src-ico src-fav" src="/site-icons/abc.png"[^>]*>\s*Website', links)
    assert ">Website →</a>" in html
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["sameAs"] == ["https://hol.org/guard"]


def test_website_button_falls_back_to_a_globe_without_a_favicon():
    links = _hero_links(_render(homepage="https://example.org", homepage_source="github",
                                homepage_label="example.org", homepage_icon_src=""))
    assert "src-fav" not in links and "<circle" in links and "Website" in links


def test_page_without_a_homepage_has_only_the_repository_button():
    html = _render(homepage="")
    links = _hero_links(html)
    assert "Repository" in links and "Website" not in links
    assert "Website →" not in html and '"sameAs"' not in html


# ---- declared homepages (GitHub's "Website" field) ---------------------------

import fetch_and_build as fab  # noqa: E402


def test_usable_homepage_keeps_project_sites_and_drops_non_homepages():
    keep = {
        "https://www.langflow.org": "https://www.langflow.org",
        "http://openinterpreter.com/": "http://openinterpreter.com/",
        "waku.one": "https://waku.one",                       # bare domain
        "https://skyworkai.github.io/DeepResearchAgent/": "https://skyworkai.github.io/DeepResearchAgent/",
        "https://aka.ms/semantic-kernel": "https://aka.ms/semantic-kernel",
        "https://arxiv.org/abs/2307.07924": "https://arxiv.org/abs/2307.07924",
        "https://skills.sh": "https://skills.sh",             # a directory's own root
    }
    for value, expected in keep.items():
        assert fab.usable_homepage(value) == expected, value
    for value in ("", None, "https://github.com/antvis/mcp-server-chart",
                  "https://www.npmjs.com/package/x", "https://pypi.org/project/x/",
                  "https://discord.gg/abc", "https://x.com/someone",
                  "https://deepwiki.com/owner/repo", "https://skills.sh/blader/humanizer",
                  "https://glama.ai/mcp/servers/a/b", "javascript:alert(1)",
                  "http://localhost:3000", "http://127.0.0.1", "https://a b.com"):
        assert fab.usable_homepage(value) == "", value


class _Resp:
    def __init__(self, code):
        self.status_code = code

    def close(self):
        pass


def test_homepage_is_dead_only_on_a_definite_answer(monkeypatch):
    import requests

    def get_with(result):
        def get(url, **kw):
            if isinstance(result, Exception):
                raise result
            return _Resp(result)
        return get

    cases = [
        (requests.exceptions.ConnectionError("NameResolutionError: nodename nor servname provided"), True),
        (404, True), (410, True),
        (200, False), (403, False), (503, False),
        (requests.exceptions.ConnectionError("Connection refused"), None),
        (requests.exceptions.Timeout(), None),
        (requests.exceptions.SSLError("bad cert"), None),
    ]
    for result, expected in cases:
        monkeypatch.setattr(fab.requests, "get", get_with(result))
        assert fab.homepage_is_dead("https://example.com") is expected, result


def test_roster_homepage_wins_over_the_declared_one():
    row = {"github_homepage": "https://declared.example"}
    fab.apply_homepage(row, "https://hol.org/guard")
    assert (row["homepage"], row["homepage_source"]) == ("https://hol.org/guard", "roster")
    fab.apply_homepage(row, "")
    assert (row["homepage"], row["homepage_source"]) == ("https://declared.example", "github")
    empty = {}
    fab.apply_homepage(empty, "")
    assert (empty["homepage"], empty["homepage_source"]) == ("", "")


def test_homepage_label_is_short():
    assert fab.homepage_label("https://hol.org/guard") == "hol.org/guard"
    assert fab.homepage_label("http://www.langflow.org/") == "langflow.org"
    assert fab.homepage_label("https://docs.e2b.dev/?utm_source=github&utm_medium=referral") == "docs.e2b.dev"
    assert fab.homepage_label("https://medium.com/@someone/" + "a-very-long-article-slug" * 5) == "medium.com"


def test_declared_homepage_link_is_nofollow():
    html = _render(homepage="https://www.langflow.org", homepage_source="github", homepage_label="langflow.org")
    assert 'rel="noopener noreferrer nofollow">Website →</a>' in html
    assert 'rel="noopener noreferrer nofollow" title="langflow.org">' in _hero_links(html)


def test_declared_homepage_survives_the_data_json_whitelist():
    import inspect
    source = inspect.getsource(fab.main)
    _, _, after_writer = source.partition("# Write data.json (machine-readable leaderboard)")
    whitelist, _, _ = after_writer.partition("Wrote data.json")
    assert '"github_homepage": r.get("github_homepage", "")' in whitelist


NOW = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def _issue(n, title, created, comments=()):
    return {"number": n, "title": title, "createdAt": created, "url": f"u/{n}",
            "comments": [{"authorAssociation": a} for a in comments]}


def test_overdue_flags_only_old_unanswered_correction_requests():
    issues = [
        _issue(216, "[Correction] HOL Guard official website", "2026-09-04T10:00:00Z"),
        _issue(300, "[Correction] answered", "2026-09-01T10:00:00Z", comments=["NONE", "OWNER"]),
        _issue(301, "[Correction] only the requester replied", "2026-09-01T10:00:00Z", comments=["NONE"]),
        _issue(302, "[Correction] too new", "2026-09-26T10:00:00Z"),
        _issue(303, "Some other issue", "2026-08-01T10:00:00Z"),
    ]
    assert [i["number"] for i in overdue(issues, now=NOW)] == [216, 301]


# ---- website favicons ---------------------------------------------------------

def _png_bytes(size=(48, 48), color=(200, 30, 30, 255)):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_icon_candidates_prefer_sharp_icons_then_favicon_ico():
    html = ('<link rel="icon" href="/fav.ico"><link rel="apple-touch-icon" href="/apple.png">'
            '<link rel="icon" type="image/png" href="https://cdn.example/icon-32.png">'
            '<link rel="stylesheet" href="/x.css"><link rel="icon" href="data:image/png;base64,AAA">')
    assert fab._icon_candidates(html, "https://example.org/docs/") == [
        "https://example.org/apple.png", "https://cdn.example/icon-32.png",
        "https://example.org/fav.ico", "https://example.org/favicon.ico"]


def test_icon_png_accepts_raster_and_rejects_everything_else():
    from PIL import Image
    import io
    png = fab._icon_png(_png_bytes())
    assert Image.open(io.BytesIO(png)).size == (32, 32)
    assert fab._icon_png(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>") is None
    assert fab._icon_png(_png_bytes(color=(0, 0, 0, 0))) is None      # fully transparent
    assert fab._icon_png(_png_bytes(size=(4, 4))) is None             # too small
    assert fab._icon_png(b"not an image") is None


class _Raw:
    def __init__(self, data):
        self.data = data

    def read(self, n, decode_content=True):
        return self.data[:n]


class _Get:
    def __init__(self, status=200, text="", data=b"", url=""):
        self.status_code, self.text, self.raw, self.url = status, text, _Raw(data), url
        self.ok = status < 400

    def close(self):
        pass


def test_fetch_site_icon_follows_the_page_then_falls_back(monkeypatch):
    pages = {
        "https://example.org": _Get(text='<link rel="icon" href="/i.png">', url="https://example.org/"),
        "https://example.org/i.png": _Get(status=404),
        "https://example.org/favicon.ico": _Get(data=_png_bytes()),
    }
    monkeypatch.setattr(fab.requests, "get", lambda url, **kw: pages.get(url, _Get(status=404)))
    icon = fab.fetch_site_icon("https://example.org")
    assert icon and fab.fetch_site_icon("https://blocked.example") is None


def test_store_site_icon_writes_one_file_per_host(tmp_path, monkeypatch):
    import base64
    monkeypatch.setattr(fab, "fetch_site_icon", lambda url: base64.b64encode(fab._icon_png(_png_bytes())).decode())
    a = fab.store_site_icon("https://example.org/docs", str(tmp_path))
    b = fab.store_site_icon("https://example.org/other", str(tmp_path))
    assert a == b and a.startswith("/site-icons/") and a.endswith(".png")
    assert (tmp_path / a.lstrip("/")).is_file()
    monkeypatch.setattr(fab, "fetch_site_icon", lambda url: None)
    assert fab.store_site_icon("https://blocked.example", str(tmp_path)) == ""


def test_icon_is_used_only_for_the_homepage_it_was_fetched_for():
    row = {"github_homepage": "https://a.example", "homepage_icon": "/site-icons/a.png",
           "homepage_icon_for": "https://a.example"}
    fab.apply_homepage(row, "")
    assert row["homepage_icon_src"] == "/site-icons/a.png"
    fab.apply_homepage(row, "https://roster.example")    # homepage changed since the fetch
    assert row["homepage_icon_src"] == ""


def test_icon_fields_survive_the_data_json_whitelist():
    import inspect
    source = inspect.getsource(fab.main)
    _, _, after_writer = source.partition("# Write data.json (machine-readable leaderboard)")
    whitelist, _, _ = after_writer.partition("Wrote data.json")
    assert '"homepage_icon": r.get("homepage_icon", "")' in whitelist
    assert '"homepage_icon_for": r.get("homepage_icon_for", "")' in whitelist
