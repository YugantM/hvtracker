"""Confirm every project we list as a badge adopter still embeds the badge.

The homepage strip and /adopters/ say publicly that these projects carry the
HVTrust badge in their README. NVIDIA/SkillSpector removed it on 2026-09-17 and
we kept claiming it for a week. This reads BADGE_ADOPTERS straight out of
fetch_and_build.py (via ast, so no dependencies), fetches each README from the
GitHub API and looks for a hvtracker.net/badge/ link.

Exit codes: 0 = all present, 2 = at least one missing, 1 = could not check.
"""
import ast
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BADGE = re.compile(r"hvtracker\.net/badge/", re.I)


def load_adopters(path=os.path.join(ROOT, "fetch_and_build.py")):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "BADGE_ADOPTERS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("BADGE_ADOPTERS not found in fetch_and_build.py")


def fetch_readme(repo, token=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/readme",
        headers={"Accept": "application/vnd.github.raw", "User-Agent": "hvtracker-adopter-check",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check(adopters, fetch):
    """Return (missing, errors) as lists of repos."""
    missing, errors = [], []
    for _slug, repo, _desc in adopters:
        try:
            if not BADGE.search(fetch(repo)):
                missing.append(repo)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            errors.append(f"{repo}: {e}")
    return missing, errors


def main():
    adopters = load_adopters()
    token = os.environ.get("GITHUB_TOKEN")
    missing, errors = check(adopters, lambda repo: fetch_readme(repo, token))
    print(json.dumps({"checked": len(adopters), "missing": missing, "errors": errors}, indent=2))
    if missing:
        print("\nRemove these from BADGE_ADOPTERS in fetch_and_build.py (and their "
              "adopters/<slug>.png), or confirm the badge moved to another file.")
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
