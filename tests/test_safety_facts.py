"""Reviewed safety facts on profile pages (Q4 plan E2/E3).

Facts come from safety_facts.json, each with a source and an evidence class.
They render only on profiles that have them; every other profile must stay
byte-for-byte unchanged, or the sitemap re-dates ~1,700 URLs (#322)."""
import json
import os

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

import fetch_and_build as fab

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")


def test_shipped_file_is_valid_and_names_real_listings():
    with open(fab.SAFETY_FACTS_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    assert fab.safety_fact_problems(doc) == []
    with open(os.path.join(ROOT, "agents.json"), encoding="utf-8") as f:
        slugs = {fab.slugify(a["name"]) for a in json.load(f)}
    assert set(doc["profiles"]) <= slugs, set(doc["profiles"]) - slugs
    # The loader accepts it as a whole (a single bad fact would blank it).
    assert set(fab.load_safety_facts()) == set(doc["profiles"])


def test_loader_orders_topics_and_labels_classes(tmp_path):
    doc = {"profiles": {"x": {"checked": "2026-10-06", "facts": [
        {"topic": "security", "class": "observed", "text": "s", "source": "https://www.x.dev/security.txt"},
        {"topic": "operator", "class": "declared", "text": "o", "source": "https://x.dev/terms"},
        {"topic": "access", "class": "source", "text": "a", "source": "https://github.com/x/x"},
    ]}}}
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc))
    groups = fab.load_safety_facts(str(path))["x"]["groups"]
    assert [g["key"] for g in groups] == ["operator", "access", "security"]
    assert [g["facts"][0]["label"] for g in groups] == ["PUBLISHER", "IN CODE", "CHECKED"]
    assert groups[2]["facts"][0]["source_host"] == "x.dev"


def test_malformed_file_is_rejected_whole(tmp_path):
    bad = {"profiles": {"x": {"checked": "6 Oct", "facts": [
        {"topic": "rumour", "class": "hearsay", "text": "", "source": "http://x.dev"}]}}}
    problems = fab.safety_fact_problems(bad)
    assert len(problems) == 5  # date, topic, class, text, source
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(bad))
    assert fab.load_safety_facts(str(path)) == {}
    assert fab.load_safety_facts(str(tmp_path / "missing.json")) == {}


def _row(**overrides):
    with open(os.path.join(ROOT, "data", "render_state.json"), encoding="utf-8") as f:
        row = json.load(f)["rows"][0]
    row.update(pending_signals=False, **overrides)
    row["category_slug"] = fab.slugify(row.get("category", "")) if row.get("category") else ""
    row["org_slug_or_none"] = None
    row["review_insights"] = fab.agent_review_insights(row)
    row["remediation_steps"] = fab.agent_remediation_steps(row)
    row["safety_qa"] = fab.agent_safety_qa(row)
    row["correction_url"] = fab.agent_correction_url(row)
    row["sparkline_svg"] = ""
    row["rank_history"] = []
    row["event_chart_svg"] = ""
    return row


def _render(row, env=None):
    env = env or Environment(loader=FileSystemLoader([TEMPLATES, ROOT]), autoescape=True)
    return env.get_template("agent.html.j2").render(
        row=row, total=1, updated="", events=[], drift_events=[],
        methodology_version="v4.4", comparisons=[], provider_slugs={}, related=[],
    )


def test_profile_without_facts_is_byte_identical_to_the_old_template():
    with open(os.path.join(TEMPLATES, "agent.html.j2"), encoding="utf-8") as f:
        src = f.read()
    tag = src.index("{%- if row.safety_facts %}")
    start = src.rindex("\n", 0, tag)  # the whitespace `{%-` strips goes too
    end = src.index("{%- endif %}", tag) + len("{%- endif %}")
    old_env = Environment(loader=ChoiceLoader([DictLoader({"agent.html.j2": src[:start] + src[end:]}),
                                               FileSystemLoader([TEMPLATES, ROOT])]), autoescape=True)
    row = _row(safety_facts=None)
    assert _render(row) == _render(row, old_env)
    assert 'id="safety-facts"' not in _render(row)


def test_profile_with_facts_shows_each_fact_with_class_and_source(tmp_path):
    doc = {"profiles": {"demo": {"checked": "2026-10-06", "facts": [
        {"topic": "data", "class": "declared", "text": "Stores the OAuth tokens of apps you connect.",
         "source": "https://docs.example.com/token-custody"},
        {"topic": "security", "class": "observed", "text": "Publishes a security.txt.",
         "source": "https://example.com/.well-known/security.txt"}]}}}
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc))
    row = _row(safety_facts=fab.load_safety_facts(str(path))["demo"])
    html = _render(row)
    section = html[html.index('id="safety-facts"'):]
    section = section[:section.index("</section>")]
    assert "Where your data goes" in section and "Security practice" in section
    assert "Who runs it" not in section  # no operator facts, no empty heading
    assert "Stores the OAuth tokens of apps you connect." in section
    assert 'href="https://docs.example.com/token-custody"' in section and ">docs.example.com<" in section
    assert section.count('class="sev sev-none">PUBLISHER<') == 2  # legend + the fact
    assert "Checked 2026-10-06" in section
    assert "IN CODE" not in section  # the legend names it only on pages that use it
    # Shown, never scored: the facts don't touch the score shown on the page.
    assert f"{row['trust_score']}/100" in html


def test_legend_explains_in_code_when_a_fact_uses_it(tmp_path):
    doc = {"profiles": {"demo": {"checked": "2026-10-08", "facts": [
        {"topic": "access", "class": "source", "text": "Edits are auto-approved by default.",
         "source": "https://github.com/example/demo/blob/main/settings.ts"}]}}}
    path = tmp_path / "facts.json"
    path.write_text(json.dumps(doc))
    html = _render(_row(safety_facts=fab.load_safety_facts(str(path))["demo"]))
    section = html[html.index('id="safety-facts"'):]
    assert "is read from the project's source code" in section[:section.index("</section>")]
