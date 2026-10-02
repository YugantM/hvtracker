"""Agent page chain of custody (Phase 8): repo -> review/release -> package ->
installed release, plus what changed, what backs the score, how to verify it
and what it doesn't check."""
import json
import os

from jinja2 import Environment, FileSystemLoader

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _render(events=(), **overrides):
    env = Environment(
        loader=FileSystemLoader([os.path.join(ROOT, "templates"), ROOT]),
        autoescape=True,
    )
    with open(os.path.join(ROOT, "data", "render_state.json"), encoding="utf-8") as f:
        row = json.load(f)["rows"][0]
    row.update({"pending_signals": False, "evidence_grade": "B", "trust_score": 70.0,
                "coverage_grade": "B", "signal_types": 3})
    row.update(overrides)
    row["category_slug"] = ""
    row["org_slug_or_none"] = None
    row["review_insights"] = fab.agent_review_insights(row)
    row["remediation_steps"] = fab.agent_remediation_steps(row)
    row["safety_qa"] = fab.agent_safety_qa(row)
    row["correction_url"] = fab.agent_correction_url(row)
    row["custody_packages"] = fab.custody_packages(row)
    row["evidence_types"] = fab.evidence_types(row)
    row["sparkline_svg"] = ""
    row["rank_history"] = []
    row["event_chart_svg"] = ""
    return env.get_template("agent.html.j2").render(
        row=row, total=1, updated="", events=list(events), drift_events=[],
        methodology_version="v4.4", comparisons=[], provider_slugs={}, related=[],
    )


def _custody(html):
    start = html.index('<section class="custody"')
    return html[start:html.index("</section>", start)]


def _drift(**pkgs):
    return fab.detect_package_provenance_drift("acme/tool", **pkgs)


def test_packages_read_back_every_drift_verdict():
    drift = _drift(
        npm_package="tool", npm_metadata={"repository": {"url": "git+https://github.com/acme/tool.git"}},
        pypi_package="tool-py", pypi_metadata={"info": {"project_urls": {}}},
        crate_package="tool-rs", crate_metadata={"crate": {"repository": "https://github.com/someone/else"}},
    )
    row = {"repo": "acme/tool", "npm_package": "tool", "npm_provenance": True,
           "pypi_package": "tool-py", "crate_package": "tool-rs", "package_provenance_drift": drift}
    pkgs = {p["registry"]: p for p in fab.custody_packages(row)}
    assert pkgs["npm"]["source"] == "match" and pkgs["npm"]["attested"] is True
    assert pkgs["PyPI"]["source"] == "missing" and pkgs["PyPI"]["attested"] is False
    assert pkgs["crates.io"]["source"] == "mismatch"
    assert pkgs["crates.io"]["points_to"] == "someone/else"
    assert pkgs["crates.io"]["attested"] is None
    assert pkgs["PyPI"]["url"] == "https://pypi.org/project/tool-py/"


def test_same_owner_and_rename_are_not_mismatches():
    same = _drift(npm_package="t", npm_metadata={"repository": "https://github.com/acme/tool-js"})
    renamed = fab.detect_package_provenance_drift(
        "old/tool", npm_package="t", npm_metadata={"repository": "https://github.com/new/tool"},
        tracked_repo_canonical="new/tool")
    for drift, want in ((same, "same_owner"), (renamed, "renamed")):
        (p,) = fab.custody_packages({"npm_package": "t", "package_provenance_drift": drift})
        assert p["source"] == want and p["points_to"]


def test_package_without_a_drift_check_is_unchecked():
    (p,) = fab.custody_packages({"npm_package": "@scope/pkg", "package_provenance_drift": None})
    assert p["source"] == "unchecked"
    assert p["url"] == "https://www.npmjs.com/package/@scope/pkg"


def test_evidence_types_count_is_signal_types():
    row = {"weekly_downloads": 10, "scorecard_score": None, "has_provenance": True,
           "public_actions": None, "hn_mentions_30d": 0}
    types = fab.evidence_types(row)
    assert [present for _, present in types] == [True, True, True, False, True]


def test_chain_shows_source_review_packages_and_install():
    drift = _drift(npm_package="tool", npm_metadata={"repository": "https://github.com/someone/else"})
    html = _custody(_render(
        repo="acme/tool", npm_package="tool", pypi_package="", crate_package="", npm_provenance=False,
        package_provenance_drift=drift, signed_commits_pct=0, scorecard_score=6.1,
        scorecard_checks={"Code-Review": 3, "Signed-Releases": -1, "Maintained": 10},
        advisories={"checked": [{"ecosystem": "npm", "name": "tool", "version": "1.2.3"}],
                    "found": [], "worst": None, "checked_at": "2026-09-30T04:00:00Z"},
    ))
    assert "Chain of custody" in html
    assert "Unsigned" in html and "Mixed" in html
    assert "Code Review" in html and "n/a" in html
    assert "Source link points to someone/else, not this repo" in html
    assert "Source mismatch" in html and "Suggest a correction" in html
    assert "tool 1.2.3" in html and "No known advisories" in html


def test_no_package_project_says_so():
    html = _custody(_render(npm_package="", pypi_package="", crate_package="",
                            docker_image="", vscode_extension=""))
    assert "No registry package." in html
    assert "pin a release tag or commit" in html


def test_custody_changes_and_empty_state():
    ev = [{"date": "2026-09-01", "type": "provenance_added", "detail": "Package provenance attestation detected"},
          {"date": "2026-09-02", "type": "rank_changed", "detail": "Rank moved"}]
    html = _custody(_render(events=ev))
    assert "Package provenance attestation detected" in html
    assert "Rank moved" not in html
    assert "No change to package provenance" in _custody(_render())


def test_verify_and_limits_boxes():
    html = _custody(_render(slug="acme-tool"))
    assert 'href="/data/agents/acme-tool.json"' in html
    assert 'href="/methodology/#verify-yourself"' in html
    assert "cisco-ai-defense/mcp-scanner" in html
    skill = _custody(_render(listing_class="skill"))
    assert "cisco-ai-defense/skill-scanner" in skill and "mcp-scanner" not in skill


def test_provisional_rows_have_no_custody_section():
    html = _render(pending_signals=True, last_push="pending", days_ago=999)
    assert 'class="custody"' not in html
    assert "Supply Chain Trust" not in html


def test_owasp_line_is_on_every_profile_without_redating_it():
    html = _render()
    custody = _custody(html)
    assert "ASI04 Agentic Supply Chain Vulnerabilities" in custody and "/methodology/#owasp" in custody
    assert "AST02" not in custody
    assert "AST02 Supply Chain Compromise" in _custody(_render(listing_class="skill"))
    # Sitewide boilerplate, not this page's evidence: it sits in a lastmod:skip
    # region, so adding or editing it never re-dates the URL in the sitemap.
    edited = html.replace("These are the checks for OWASP", "Reworded boilerplate")
    assert edited != html
    assert fab.lastmod_fingerprint(html.encode(), "") == fab.lastmod_fingerprint(edited.encode(), "")
