"""Regression tests for resolve_row_downloads — a transient downloads-fetch
failure must not null a real number and crater an agent's score.

Bug (2026-09-03): the last-known-good fallback covered only pypi, so a failed
npm fetch nulled weekly_downloads for npm-only packages. vercel/ai went
15.3M dl -> None, which collapsed the adoption dimension + confidence and
crashed trust 96.4 -> 70.0 (rank 2 -> 223) for a healthy top-2 project.
"""

from fetch_and_build import resolve_row_downloads

PREV = {"vercel/ai": (15_316_812, "npm"), "psf/black": (9_000_000, "pypi")}


def _row(repo, **sources):
    r = {"repo": repo}
    r.update(sources)
    return r


def test_live_npm_value_used():
    r = _row("vercel/ai", npm_dl=23_560_904)
    assert resolve_row_downloads(r, PREV) == "live"
    assert r["weekly_downloads"] == 23_560_904
    assert r["dl_source"] == "npm"


def test_npm_failure_falls_back_to_cache():
    # The exact bug: npm-only package, npm fetch returned None this run.
    r = _row("vercel/ai", npm_dl=None)
    assert resolve_row_downloads(r, PREV) == "cached"
    assert r["weekly_downloads"] == 15_316_812
    assert r["dl_source"] == "npm"


def test_all_sources_empty_no_prior_stays_none():
    # GitHub-only agent (no package ever) must remain None, not fabricated.
    r = _row("some/github-only-agent")
    assert resolve_row_downloads(r, PREV) is None
    assert r.get("weekly_downloads") is None


def test_sources_are_summed():
    r = _row("acme/thing", npm_dl=100, pypi_dl=50, docker_pulls=25)
    assert resolve_row_downloads(r, PREV) == "live"
    assert r["weekly_downloads"] == 175
    assert set(r["dl_source"].split("+")) == {"npm", "pypi", "docker"}


def test_real_zero_is_not_treated_as_failure():
    # A genuine 0 (deprecated package) is a live value, not a fetch failure —
    # it must NOT trigger the cached fallback.
    r = _row("vercel/ai", npm_dl=0)
    assert resolve_row_downloads(r, PREV) == "live"
    assert r["weekly_downloads"] == 0
    assert r["dl_source"] == "npm"


def test_pypi_failure_still_falls_back():
    # The originally-covered case must keep working through the shared helper.
    r = _row("psf/black", pypi_dl=None)
    assert resolve_row_downloads(r, PREV) == "cached"
    assert r["weekly_downloads"] == 9_000_000
    assert r["dl_source"] == "pypi"
