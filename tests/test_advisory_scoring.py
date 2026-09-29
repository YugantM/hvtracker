"""v4.4 advisory ceiling (rule R3, docs/advisory-scoring-review-2026-09-28.md).

An advisory that affects the latest release, with no fixed version shipped,
caps the score: critical at 64.9 (top of Grade C), high at 79.9 (top of B).
Moderate, low and unrated advisories are shown, never scored.
"""
import fetch_and_build as fb
import specs

RUNTIME = next(s for s in specs.ALL_SPECS if s["slug"] == "runtime-trust")


def _adv(*severities):
    found = [{"id": f"GHSA-{i}", "severity": sev, "aliases": [], "summary": "x",
              "published": "2026-09-01", "package": "p", "version": "1.0"}
             for i, sev in enumerate(severities)]
    rated = [f["severity"] for f in found if f["severity"]]
    worst = min(rated, key=fb.ADVISORY_SEVERITIES.index) if rated else None
    return {"checked": [{"ecosystem": "npm", "name": "p", "version": "1.0"}], "found": found,
            "worst": worst, "checked_at": "2026-09-29T00:00:00Z"}


def _score(base, advisories=None):
    return fb.compute_trust_score_v2({"trust_score": base, "advisories": advisories})


def test_critical_caps_at_the_top_of_grade_c():
    r = _score(93.3, _adv("CRITICAL", "MODERATE"))
    assert r["trust_score_v2"] == 64.9 and fb.grade_for_score(64.9) == "C"
    assert r["trust_v2_advisory_cap"] == {"worst": "CRITICAL", "ceiling": 64.9, "uncapped": 93.3}


def test_high_caps_at_the_top_of_grade_b():
    r = _score(85.0, _adv("HIGH"))
    assert r["trust_score_v2"] == 79.9 and fb.grade_for_score(79.9) == "B"


def test_moderate_low_and_unrated_never_change_the_score():
    for adv in (_adv("MODERATE"), _adv("LOW"), _adv(None)):
        r = _score(90.0, adv)
        assert r["trust_score_v2"] == 90.0 and r["trust_v2_advisory_cap"] is None


def test_scores_already_below_the_ceiling_are_untouched():
    r = _score(40.0, _adv("CRITICAL"))
    assert r["trust_score_v2"] == 40.0 and r["trust_v2_advisory_cap"] is None


def test_no_check_or_a_failed_check_never_caps():
    for adv in (None, {"error": "OSV unreachable"}, {"checked": [], "found": [], "worst": None}):
        assert _score(90.0, adv)["trust_score_v2"] == 90.0


def test_fixing_the_advisory_is_the_top_improvement():
    row = {"trust_score": 64.9, "advisories": _adv("CRITICAL"), "pending_signals": False,
           "has_provenance": True, "scorecard_score": 9.5, "signed_commits_ratio": 1.0,
           "license_spdx": "MIT", "listing_status": "listed", "days_ago": 1, "stars": 50000,
           "weekly_commits": 50}
    base = fb.compute_trust_score(row)["trust_score"]
    row["trust_score"] = fb.compute_trust_score_v2({**row, "trust_score": base})["trust_score_v2"]
    imp = fb.score_improvements(row)
    assert imp and imp[0]["key"] == "advisory" and imp[0]["score"] > 64.9
    assert imp[0]["link"] == "https://osv.dev/vulnerability/GHSA-0"


def test_spec_documents_the_ceilings_the_code_uses():
    assert RUNTIME["version"] == "v0.3"
    for sev, ceiling in fb.ADVISORY_CEILINGS.items():
        assert f"<code>{sev}</code> at {ceiling}" in RUNTIME["body"], sev
    assert fb.METHODOLOGY_VERSION == "v4.4"
