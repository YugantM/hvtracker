"""Compare surface v2 (master plan 2.2): capability diff rows and the
coverage caveat on the verdict."""
import fetch_and_build as fab


def _row(name="A", mcp="none", providers=None, keys=False, plugin="none",
         drift="not_applicable", coverage=None):
    return {
        "name": name,
        "coverage_grade": coverage,
        "mcp_server_support": {"status": mcp},
        "external_service_dependencies": {"providers": providers or [],
                                          "requires_api_keys": keys},
        "tool_plugin_surface": {"plugin_system": plugin},
        "package_provenance_drift": {"status": drift},
    }


def test_capability_rows_leads():
    a = _row("A", mcp="implemented", keys=True, drift="match",
             providers=["OpenAI", "Anthropic", "Redis", "Postgres"])
    b = _row("B", mcp="declared", keys=False, drift="warning", plugin="marketplace")
    rows = {r["label"]: r for r in fab.compare_capability_rows(a, b)}
    assert rows["MCP server"]["lead"] == "a"          # implemented > declared
    assert rows["Requires API keys"]["lead"] == "b"   # not needing keys wins
    assert rows["Provenance drift"]["lead"] == "a"    # match > warning
    assert rows["External providers"]["lead"] == "none"  # no winner by design
    assert rows["Plugin surface"]["lead"] == "none"
    # display shape
    assert rows["External providers"]["a"].startswith("4 — OpenAI, Anthropic, Redis")
    assert rows["External providers"]["a"].endswith("…")
    assert rows["External providers"]["b"] == "—"
    assert rows["Plugin surface"]["b"] == "marketplace"
    assert rows["MCP server"]["b"] == "Declared"


def test_capability_rows_none_safe():
    rows = fab.compare_capability_rows({"name": "X"}, {"name": "Y"})
    assert all(r["lead"] == "none" for r in rows)
    assert {r["label"] for r in rows} == {"MCP server", "External providers",
                                          "Requires API keys", "Plugin surface",
                                          "Provenance drift"}


def test_coverage_caveat_only_when_leader_is_thinner():
    lead = {"name": "Leader", "coverage_grade": "C"}
    trail = {"name": "Trailer", "coverage_grade": "A"}
    caveat = fab.compare_coverage_caveat(lead, trail)
    assert caveat is not None and "coverage C vs A" in caveat and "Leader" in caveat
    # leader with equal or better coverage: no caveat
    assert fab.compare_coverage_caveat({"name": "L", "coverage_grade": "A"},
                                       {"name": "T", "coverage_grade": "B"}) is None
    assert fab.compare_coverage_caveat({"name": "L", "coverage_grade": "B"},
                                       {"name": "T", "coverage_grade": "B"}) is None
    # missing grades: no caveat
    assert fab.compare_coverage_caveat({"name": "L"}, {"name": "T", "coverage_grade": "A"}) is None


def test_published_pillar_maxes_match_what_scoring_can_emit():
    """The denominators we print (agent page, compare pages, methodology) must
    equal the real ceiling of each pillar. A row saturated on every input has
    to land exactly on TRUST_DIMENSIONS — otherwise we publish a bar that can
    never fill, which is how the compare page came to show identity as / 20
    when the pillar maxes out at 18.
    """
    saturated = {
        "scorecard_score": 10,
        "has_provenance": True,
        "signed_commits_ratio": 1.0,
        "listing_status": "listed",
        "license_spdx": "MIT",
        "days_ago": 0,
        "weekly_commits": 100,
        "stars": 100_000,
        "weekly_downloads": 1_000_000,
    }
    breakdown = fab.compute_trust_score(saturated)["trust_breakdown"]
    for key, (_label, published_max) in fab.TRUST_DIMENSIONS.items():
        assert breakdown[key] == published_max, (
            f"{key}: scoring tops out at {breakdown[key]} but we publish / {published_max}")
    assert sum(mx for _lbl, mx in fab.TRUST_DIMENSIONS.values()) == 100


def _render_pair(a, b):
    """Render the real compare template so the shipped JSON-LD is what's tested."""
    import os
    from jinja2 import Environment, FileSystemLoader
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = Environment(loader=FileSystemLoader([os.path.join(root, "templates"), root]))
    return env.get_template("compare_pair.html.j2").render(
        a=a, b=b, category={"name": "Research & data", "slug": "research-data"},
        metrics=[], dims=[], caps=[], total=418, updated="2026-08-10",
        methodology_version="4.2", css_hash="abc", related=[],
        lead_name=None, lead_score=None, lead_grade=None, trail_score=None,
        trail_grade=None, gap=None, coverage_caveat=None)


def _pair_row(**kw):
    row = {"name": "Docling", "slug": "docling", "category": "Research & data",
           "url": "https://github.com/docling-project/docling",
           "description": "Document parsing toolkit", "trust_score": 88.6,
           "evidence_grade": "A", "rank": 12, "coverage_grade": "B",
           "stars_fmt": "1.2k", "trust_breakdown": {}, "license_spdx": "MIT"}
    row.update(kw)
    return row


def _ld_blocks(html):
    import json
    import re
    return [json.loads(m) for m in re.findall(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)]


def test_pair_structured_data_survives_hostile_strings():
    """Names really do carry ampersands ("Weights & Biases Weave", "MITRE
    ATT&CK") and a description could carry a quote; the JSON-LD must still
    parse rather than silently breaking the whole block."""
    a = _pair_row(name="Weights & Biases Weave", slug="weights-biases-weave",
                  description='Ships a "tracing" client & <hooks>')
    b = _pair_row(name="MITRE ATT&CK", slug="mitre-attack", trust_score=74.2,
                  evidence_grade="B", rank=99)
    types = {b_["@type"]: b_ for b_ in _ld_blocks(_render_pair(a, b))}

    assert "BreadcrumbList" in types, "breadcrumbs must survive the addition"
    items = [e["item"] for e in types["ItemList"]["itemListElement"]]
    assert [i["name"] for i in items] == ["Weights & Biases Weave", "MITRE ATT&CK"]
    assert items[0]["description"] == 'Ships a "tracing" client & <hooks>'
    assert [i["review"]["reviewRating"]["ratingValue"] for i in items] == [88.6, 74.2]
    assert items[1]["review"]["url"] == "https://hvtracker.net/agents/mitre-attack/"


def test_pair_structured_data_omits_review_for_unscored_rows():
    """Provisional rows have no trust_score yet — emitting a rating of null (or
    0) would be a false claim about the project."""
    html = _render_pair(_pair_row(), _pair_row(name="New Agent", slug="new-agent",
                                               trust_score=None, evidence_grade=None,
                                               rank=None, description=None))
    items = [e["item"] for e in
             {b["@type"]: b for b in _ld_blocks(html)}["ItemList"]["itemListElement"]]
    assert "review" in items[0]
    assert "review" not in items[1], "unscored row must not carry a rating"
    assert "description" not in items[1]
