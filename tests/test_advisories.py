"""Known advisories: OSV records against the release a listing ships today.

Shown, not scored. The identity guard decides whether a configured package
really is the listing's release: a stale second distribution (Open WebUI's
2024 npm id) or a package pointing at another owner must never put someone
else's advisories on a project's page.
"""
import pytest

import fetch_and_build as fb

GHSA = {"id": "GHSA-aaaa", "aliases": ["CVE-2026-1", "PYSEC-2026-1"], "summary": "Injection",
        "published": "2026-06-01T00:00:00Z", "database_specific": {"severity": "MODERATE"}}
PYSEC_TWIN = {"id": "PYSEC-2026-1", "aliases": ["CVE-2026-1", "GHSA-aaaa"],
              "details": "hermes has an injection issue\nmore", "published": "2026-08-04T00:00:00Z"}
CRIT = {"id": "GHSA-crit", "aliases": ["CVE-2026-9"], "summary": "Remote code execution",
        "published": "2026-09-10T00:00:00Z", "database_specific": {"severity": "CRITICAL"}}
LOW = {"id": "GHSA-low", "summary": "Minor", "published": "2026-07-01T00:00:00Z",
       "database_specific": {"severity": "LOW"}}
WITHDRAWN = {"id": "GHSA-gone", "withdrawn": "2026-09-01T00:00:00Z", "summary": "Retracted",
             "database_specific": {"severity": "HIGH"}}


@pytest.fixture
def registries(monkeypatch):
    meta = {}
    osv = {}
    monkeypatch.setattr(fb, "fetch_npm_package_metadata", lambda n: meta.get(("npm", n)))
    monkeypatch.setattr(fb, "fetch_pypi_package_metadata", lambda n: meta.get(("pypi", n)))
    monkeypatch.setattr(fb, "fetch_crate_package_metadata", lambda n: meta.get(("crates.io", n)))
    monkeypatch.setattr(fb, "fetch_osv_vulns", lambda eco, n, v: osv.get((eco, n, v), []))
    return meta, osv


@pytest.mark.parametrize("url,canonical,only,name,expected", [
    ("git+https://github.com/Owner/Repo.git", None, False, "x", True),      # this repo
    ("https://github.com/owner/other-repo", None, False, "x", True),        # same owner
    ("https://github.com/newowner/repo", "NewOwner/repo", False, "x", True),  # renamed
    ("https://github.com/someone-else/repo", None, True, "repo", False),    # another owner
    (None, None, True, "repo", True),                                        # sole package, same name
    ("https://repo.dev", None, True, "Repo", True),                          # non-GitHub homepage
    (None, None, False, "repo", False),                                      # a second, unverifiable one
    (None, None, True, "something-else", False),
])
def test_package_identity_guard(url, canonical, only, name, expected):
    assert fb.package_is_the_listing("owner/repo", canonical, url, name, only) is expected


def test_critical_advisory_on_the_current_release(registries):
    meta, osv = registries
    meta[("npm", "omniroute")] = {"version": "3.8.50",
                                  "repository": {"url": "git+https://github.com/diegosouzapw/OmniRoute.git"}}
    osv[("npm", "omniroute", "3.8.50")] = [CRIT, WITHDRAWN]
    res = fb.fetch_known_advisories("diegosouzapw/OmniRoute", npm_package="omniroute")
    assert res["checked"] == [{"ecosystem": "npm", "name": "omniroute", "version": "3.8.50"}]
    assert [f["id"] for f in res["found"]] == ["GHSA-crit"]  # withdrawn record dropped
    assert res["worst"] == "CRITICAL"


def test_alias_twins_count_once_and_keep_the_ghsa_severity(registries):
    meta, osv = registries
    meta[("pypi", "hermes-agent")] = {"info": {"version": "0.19.0", "project_urls": {}}}
    osv[("PyPI", "hermes-agent", "0.19.0")] = [PYSEC_TWIN, GHSA, LOW]
    res = fb.fetch_known_advisories("NousResearch/hermes-agent", pypi_package="hermes-agent")
    assert [f["id"] for f in res["found"]] == ["GHSA-aaaa", "GHSA-low"]  # worst first
    assert res["found"][0]["aliases"] == ["CVE-2026-1", "PYSEC-2026-1"]
    assert res["found"][0]["severity"] == "MODERATE" and res["worst"] == "MODERATE"


def test_stale_second_distribution_is_not_the_listing(registries):
    meta, osv = registries
    meta[("npm", "open-webui")] = {"version": "0.1.125"}  # no repository, published 2024
    meta[("pypi", "open-webui")] = {"info": {"version": "0.11.4",
                                             "home_page": "https://github.com/open-webui/open-webui"}}
    osv[("npm", "open-webui", "0.1.125")] = [CRIT]
    res = fb.fetch_known_advisories("open-webui/open-webui", npm_package="open-webui",
                                    pypi_package="open-webui")
    assert res["checked"] == [{"ecosystem": "PyPI", "name": "open-webui", "version": "0.11.4"}]
    assert res["found"] == [] and res["worst"] is None


def test_no_package_tied_to_the_listing_means_not_checked(registries):
    meta, _ = registries
    meta[("pypi", "metagpt")] = {"info": {"version": "0.8.2",
                                          "project_urls": {"Source": "https://github.com/geekan/MetaGPT"}}}
    assert fb.fetch_known_advisories("FoundationAgents/MetaGPT", pypi_package="metagpt") is None
    assert fb.fetch_known_advisories("o/r") is None


def test_lookup_failure_is_an_error_not_none_known(registries, monkeypatch):
    meta, _ = registries
    meta[("npm", "x")] = {"version": "1.0.0", "repository": "github:o/x"}
    monkeypatch.setattr(fb, "fetch_osv_vulns", lambda *a: None)
    assert "error" in fb.fetch_known_advisories("o/x", npm_package="x")


def test_advisories_survive_the_data_json_round_trip():
    """Batch mode carries 5/6 of the board forward from data.json's whitelist."""
    import inspect
    assert '"advisories": r.get("advisories")' in inspect.getsource(fb.main)


def test_drift_detector_unchanged_by_the_shared_url_helper():
    res = fb.detect_package_provenance_drift(
        "o/r", npm_package="p", npm_metadata={"repository": "https://github.com/evil/r"},
        pypi_package="q", pypi_metadata={"info": {"project_urls": {"Source": "https://github.com/o/r"}}})
    assert res["status"] == "warning"
    assert "npm package 'p' points to evil/r, not o/r" in res["evidence"]


# ---- surfaces: agent page, MCP ------------------------------------------------

ADV_CRIT = {
    "checked": [{"ecosystem": "npm", "name": "omniroute", "version": "3.8.50"}],
    "found": [{"id": "GHSA-hf57-cqmx-p4gr", "aliases": ["CVE-2026-88062"],
               "summary": "OmniRoute ACP Custom-Agent Remote Code Execution (RCE)",
               "severity": "CRITICAL", "published": "2026-09-10",
               "package": "omniroute", "version": "3.8.50"}],
    "worst": "CRITICAL", "checked_at": "2026-09-26T10:00:00Z",
}
ADV_NONE = {**ADV_CRIT, "found": [], "worst": None}


def _page(**row):
    from test_agent_verdict_card import _render
    return _render(pending_signals=False, evidence_grade="A", trust_score=93.3, **row)


def test_page_shows_banner_fact_list_and_unchanged_score():
    html = _page(advisories=ADV_CRIT)
    assert 'class="vadv"' in html and "in the release you'd install" in html
    assert "It affects omniroute 3.8.50, the latest published release." in html
    assert "One published advisory affects its latest release." in html
    assert 'class="vfacts is-5"' in html and "1 critical" in html
    assert 'id="advisories"' in html and "CVE-2026-88062" in html
    assert "The score doesn't include advisories yet." in html
    assert ">93.3<" in html and "Grade A" in html


def test_page_says_none_known_without_a_banner():
    html = _page(advisories=ADV_NONE)
    assert "None known" in html and 'class="vadv"' not in html and 'id="advisories"' not in html
    assert "no published advisory affects its latest release (omniroute)" in html


def test_page_without_a_checked_package_keeps_four_facts():
    html = _page(advisories=None)
    assert 'class="vfacts is-5"' not in html and ">Advisories<" not in html


def test_verify_mcp_server_reports_advisories_without_changing_trusted():
    import mcp_trust
    agent = {"repo": "diegosouzapw/OmniRoute", "slug": "omniroute", "evidence_grade": "A",
             "trust_score": 93.3, "listing_status": "listed", "npm_provenance": True}
    clean = mcp_trust.evaluate(agent, "omniroute")
    flagged = mcp_trust.evaluate({**agent, "advisories": ADV_CRIT}, "omniroute")
    assert flagged["trusted"] == clean["trusted"] is True
    assert flagged["advisories"]["count"] == 1 and flagged["advisories"]["scored"] is False
    assert any("GHSA-hf57-cqmx-p4gr" in r and "critical" in r for r in flagged["reasons"])
    assert clean["advisories"] is None


def test_check_agent_trust_profile_carries_the_summary():
    import mcp_server
    prof = mcp_server._profile({"slug": "x", "advisories": ADV_NONE})
    assert prof["advisories"] == {"checked": ["npm:omniroute@3.8.50"], "count": 0, "worst": None,
                                  "advisories": [], "scored": False}
    assert mcp_server._profile({"slug": "x"})["advisories"] is None
