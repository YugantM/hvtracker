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


def _render_pair(a, b, decision=None):
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
        trail_grade=None, gap=None, coverage_caveat=None, decision=decision)


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


def _dv_row(name, score, grade, bk, **kw):
    row = {"name": name, "slug": name.lower(), "trust_score": score, "evidence_grade": grade,
           "trust_breakdown": bk}
    row.update(kw)
    return row


_BK = {"safety": 15.0, "identity": 18.0, "transparency": 13.6, "maintenance": 19.9, "adoption": 20.0}


def test_decision_verdict_close_same_grade_vs_clear_gap():
    a = _dv_row("Codex", 90.0, "A", _BK)
    b = _dv_row("Qwen", 87.9, "A", dict(_BK, safety=18.2, adoption=17.0))
    assert fab.compare_decision(a, b)["verdict"].startswith(
        "Both are Grade A and 2.1 points apart, so choose on what you weigh most.")
    c = _dv_row("Low", 62.0, "C", dict(_BK, adoption=2.0))
    assert fab.compare_decision(a, c)["verdict"].startswith(
        "Codex leads on trust: 90.0/100 (Grade A) against 62.0/100 (Grade C), a 28.0-point gap.")


def test_decision_folds_identical_dimensions_and_skips_tiny_leads():
    a = _dv_row("A", 80.0, "A", _BK)
    b = _dv_row("B", 79.9, "B", dict(_BK, maintenance=19.8, adoption=18.0))
    d = fab.compare_decision(a, b)
    assert [x["label"] for x in d["same"]] == ["Safety", "Identity", "Transparency"]
    # Maintenance differs by 0.1: it gets a bar, but it is not a reason to choose.
    assert [x["label"] for x in d["diffs"]] == ["Maintenance", "Adoption"]
    assert d["sides"][0]["choose_if"] == "Choose A if adoption matters most."
    assert d["sides"][1]["choose_if"] is None


def test_decision_evidence_only_cites_signals_that_favour_the_leader():
    """Composio led adoption on stars while having FEWER downloads — the
    point must cite stars, never "41.9k downloads against 214.2k"."""
    a = _dv_row("Composio", 74.6, "B", dict(_BK, adoption=16.9),
                weekly_downloads=41_900, stars=30_300)
    b = _dv_row("mcp-proxy", 73.7, "B", dict(_BK, adoption=15.4),
                weekly_downloads=214_200, stars=2_800)
    point = fab.compare_decision(a, b)["sides"][0]["points"][0]
    assert point == {"delta": "+1.5", "text": "Adoption: 30.3k GitHub stars against 2.8k"}


def test_decision_needs_both_scores():
    assert fab.compare_decision(_dv_row("A", 80.0, "A", _BK), _dv_row("B", None, None, {})) is None


def test_decision_view_renders_above_the_evidence_table():
    a = _pair_row(name="Codex", slug="codex", trust_breakdown=_BK, repo="openai/codex")
    b = _pair_row(name="Qwen", slug="qwen", trust_score=87.9, repo="QwenLM/qwen-code",
                  trust_breakdown=dict(_BK, safety=18.2, adoption=17.0))
    html = _render_pair(a, b, decision=fab.compare_decision(a, b))
    assert html.index("Choose Codex if") < html.index('id="evidence"') < html.index('<table class="cmp">')
    assert "Where they differ" in html
    assert len(_ld_blocks(html)) == 2  # both JSON-LD blocks still parse


def test_ctr_test_overrides_only_touch_logged_pairs():
    """Plan 3.1: titles change only for entries in CTR_TEST_COMPARE (logged in
    docs/ctr-tests.md); every other pair keeps the templated title (#114)."""
    lite = _pair_row(name="LiteLLM", slug="litellm", trust_score=77.8, evidence_grade="B")
    vllm = _pair_row(name="vLLM", slug="vllm", trust_score=81.4, evidence_grade="A")
    for x, y in ((lite, vllm), (vllm, lite)):
        o = fab.ctr_test_override(x, y)
        assert o["title"] == "LiteLLM vs vLLM: AI Gateway vs Inference Engine | HVTracker"
        assert f"{x['name']} {x['trust_score']}/100 (Grade {x['evidence_grade']})" in o["description"]
    html = _render_pair(lite, vllm)
    assert "AI agent trust comparison" in html  # no override passed -> templated title
    import re as _re
    over = fab.ctr_test_override(lite, vllm)
    from jinja2 import Environment, FileSystemLoader
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = Environment(loader=FileSystemLoader([os.path.join(root, "templates"), root]), autoescape=True)
    page = env.get_template("compare_pair.html.j2").render(
        a=lite, b=vllm, category={"name": "LLM Gateways & Infra", "slug": "llm-gateways-infra"},
        metrics=[], dims=[], caps=[], total=1, updated="", methodology_version="4.3",
        css_hash="x", related=[], lead_name=None, coverage_caveat=None, decision=None,
        seo_override=over)
    assert _re.search(r"<title>LiteLLM vs vLLM: AI Gateway vs Inference Engine \| HVTracker</title>", page)
    other = _pair_row(name="Other", slug="other")
    assert fab.ctr_test_override(lite, other) is None
    assert all(tuple(sorted(k)) == k for k in fab.CTR_TEST_COMPARE)
