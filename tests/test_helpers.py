"""Unit tests for the pure helper functions in fetch_and_build.py.

These are deterministic and make no network calls.
"""
import sys

import pytest

import fetch_and_build as fb


# ---- formatting ----------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Hello World", "hello-world"),
    ("foo/bar_baz", "foo-bar-baz"),
    ("  Spaces  ", "spaces"),
    ("Already-Slug", "already-slug"),
    ("C++ & Rust!", "c-rust"),
])
def test_slugify(name, expected):
    assert fb.slugify(name) == expected


@pytest.mark.parametrize("n,expected", [
    (0, "0"),
    (999, "999"),
    (1_000, "1.0k"),
    (1_500, "1.5k"),
    (1_000_000, "1.0M"),
    (2_400_000, "2.4M"),
])
def test_fmt_num(n, expected):
    assert fb.fmt_num(n) == expected


def test_fmt_date_handles_z_suffix():
    assert fb.fmt_date("2026-05-30T09:39:50Z") == "2026-05-30"
    assert fb.fmt_date("2026-01-02T00:00:00+00:00") == "2026-01-02"


def test_days_ago_is_nonnegative_and_monotonic():
    recent = fb.days_ago("2026-05-29T00:00:00Z")
    older = fb.days_ago("2020-01-01T00:00:00Z")
    assert recent >= 0
    assert older > recent


@pytest.mark.parametrize("d,cls", [
    (0, "fresh"), (7, "fresh"),
    (8, "recent"), (30, "recent"),
    (31, "aging"), (90, "aging"),
    (91, "stale"), (999, "stale"),
])
def test_freshness_class(d, cls):
    assert fb.freshness_class(d) == cls


@pytest.mark.parametrize("score,cls", [
    (100, "score-high"), (70, "score-high"),
    (69.9, "score-mid"), (45, "score-mid"),
    (44.9, "score-low"), (0, "score-low"),
])
def test_score_class(score, cls):
    assert fb.score_class(score) == cls


# ---- scoring -------------------------------------------------------------

def test_score_components_bounds():
    c = fb.score_components(stars=1_000_000, days_since=0, recent_commits=1000, forks=100_000)
    assert c["stars"] <= 30
    assert c["freshness"] <= 25
    assert c["activity"] <= 25
    assert c["community"] <= 20


def test_score_components_zero_floor():
    # days_since beyond 180 must floor freshness at 0, not go negative
    c = fb.score_components(stars=0, days_since=365, recent_commits=0, forks=0)
    assert c["freshness"] == 0.0
    assert c["stars"] == 0.0
    assert c["activity"] == 0.0
    assert c["community"] == 0.0


def test_health_score_matches_component_sum():
    stars, days, commits, forks = 5000, 10, 50, 800
    c = fb.score_components(stars, days, commits, forks)
    expected = round(c["stars"] + c["freshness"] + c["activity"] + c["community"], 1)
    assert fb.health_score(stars, days, commits, forks) == expected


def test_health_score_in_range():
    assert 0 <= fb.health_score(1_000_000, 0, 1000, 100_000) <= 100


# ---- rank delta display --------------------------------------------------

@pytest.mark.parametrize("delta,is_new,expected", [
    (None, True, "NEW"),
    (5, True, "NEW"),
    (None, False, "—"),
    (0, False, "="),
    (3, False, "▲3"),
    (-4, False, "▼4"),
])
def test_rank_delta_display(delta, is_new, expected):
    assert fb.rank_delta_display(delta, is_new) == expected


@pytest.mark.parametrize("delta,is_new,expected", [
    (1, True, "delta-new"),
    (None, False, "delta-same"),
    (0, False, "delta-same"),
    (2, False, "delta-up"),
    (-2, False, "delta-down"),
])
def test_rank_delta_class(delta, is_new, expected):
    assert fb.rank_delta_class(delta, is_new) == expected


# ---- GitHub Link header parsing -----------------------------------------

def test_parse_link_last_page():
    header = (
        '<https://api.github.com/x?page=2>; rel="next", '
        '<https://api.github.com/x?page=9>; rel="last"'
    )
    page, url = fb._parse_link_last_page(header)
    assert page == 9
    assert url == "https://api.github.com/x?page=9"


def test_parse_link_last_page_absent():
    page, url = fb._parse_link_last_page('<https://api.github.com/x?page=2>; rel="next"')
    assert page is None and url is None


# ---- batch selection -----------------------------------------------------

def test_parse_batch_arg(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--batch", "3/6"])
    assert fb.parse_batch_arg() == (3, 6)


def test_parse_batch_arg_absent(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["prog", "--render-only"])
    assert fb.parse_batch_arg() is None


def test_select_batch_partitions_all_agents():
    agents = [{"repo": f"owner/repo{i:02d}"} for i in range(20)]
    total = 6
    seen = []
    for b in range(1, total + 1):
        seen.extend(a["repo"] for a in fb.select_batch(agents, b, total))
    # Every agent appears exactly once across all batches.
    assert sorted(seen) == sorted(a["repo"] for a in agents)


def test_select_batch_is_deterministic():
    agents = [{"repo": "b/B"}, {"repo": "a/A"}, {"repo": "c/C"}]
    first = fb.select_batch(agents, 1, 3)
    second = fb.select_batch(agents, 1, 3)
    assert first == second
