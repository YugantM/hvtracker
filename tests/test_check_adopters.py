"""scripts/check_adopters.py keeps the public adopter claim true."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import check_adopters  # noqa: E402
import fetch_and_build as fab  # noqa: E402


def test_reads_the_same_list_the_site_renders():
    assert check_adopters.load_adopters() == fab.BADGE_ADOPTERS


def test_flags_a_readme_without_the_badge():
    readmes = {
        "a/kept": "[![HVTrust](https://hvtracker.net/badge/kept.svg)](https://hvtracker.net/agents/kept/)",
        "b/dropped": "# Dropped\nNo badge any more.",
    }
    adopters = [("kept", "a/kept", ""), ("dropped", "b/dropped", "")]
    missing, errors = check_adopters.check(adopters, readmes.__getitem__)
    assert missing == ["b/dropped"] and errors == []


def test_every_listed_adopter_is_a_tracked_project():
    """Matched by slug, which survives repo renames (GitHub redirects the old
    name, and the roster can lag a rename, as with Threadplane)."""
    import json
    with open(os.path.join(os.path.dirname(fab.__file__), "agents.json"), encoding="utf-8") as f:
        rows = [{"name": a["name"], "repo": a["repo"]} for a in json.load(f)]
    fab.assign_unique_slugs(rows)
    slugs = {r["slug"] for r in rows}
    for slug, repo, _desc in fab.BADGE_ADOPTERS:
        assert slug in slugs, (slug, repo)
