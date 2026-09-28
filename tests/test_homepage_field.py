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


def test_page_links_the_homepage_and_names_it_in_json_ld():
    html = _render(homepage="https://hol.org/guard", homepage_source="roster", homepage_label="hol.org/guard")
    assert '<a href="https://hol.org/guard" target="_blank" rel="noopener noreferrer">hol.org/guard</a>' in html
    assert ">Homepage →</a>" in html
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["sameAs"] == ["https://hol.org/guard"]


def test_page_without_a_homepage_is_unchanged():
    html = _render(homepage="")
    assert "Homepage →" not in html and '"sameAs"' not in html


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
    assert 'rel="noopener noreferrer nofollow">Homepage →</a>' in html
    assert 'rel="noopener noreferrer nofollow">langflow.org</a>' in html


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
