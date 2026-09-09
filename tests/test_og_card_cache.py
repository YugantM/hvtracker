"""og_card_signature gates OG-card regeneration by content hash, so the 2h
batch stops re-rendering ~1,700 identical PIL cards every run. The signature
must change iff a rendered field changes — a miss serves a stale share card.
"""

from fetch_and_build import og_card_signature

BASE = {
    "name": "Haystack", "description": "LLM framework", "repo": "deepset-ai/haystack",
    "trust_score": 96.7, "evidence_grade": "A", "stars_fmt": "26.4k",
    "weekly_commits": 220, "category": "Agent Frameworks",
    "trust_breakdown": {"safety": 21.9, "identity": 18.0}, "rank": 1,
}
GEN = "abc123"


def sig(**overrides):
    row = {**BASE, **overrides}
    return og_card_signature(row, overrides.pop("_total", 148), GEN)


def test_identical_inputs_are_stable():
    assert sig() == sig()


def test_ignores_unrendered_fields():
    # Fields the card never draws must NOT bust the cache (that's the whole win).
    assert sig() == og_card_signature({**BASE, "scorecard_score": 9.9, "forks": 5000}, 148, GEN)


def test_every_rendered_field_busts_the_hash():
    baseline = sig()
    for field, newval in [
        ("name", "Haystack 2"), ("description", "changed"), ("repo", "x/y"),
        ("trust_score", 90.0), ("evidence_grade", "B"), ("stars_fmt", "27k"),
        ("weekly_commits", 999), ("category", "Coding Agents"),
        ("trust_breakdown", {"safety": 10.0}), ("rank", 2),
    ]:
        assert sig(**{field: newval}) != baseline, f"{field} did not change the signature"


def test_total_denominator_busts_the_hash():
    assert og_card_signature(BASE, 148, GEN) != og_card_signature(BASE, 149, GEN)


def test_generator_source_change_busts_all_cards():
    assert og_card_signature(BASE, 148, "abc123") != og_card_signature(BASE, 148, "def456")
