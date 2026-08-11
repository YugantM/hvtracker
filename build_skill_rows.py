"""
build_skill_rows.py — turn skills-shortlist.json into roster-shaped rows.

Reads the ripe shortlist, resolves REAL package identifiers (so the downloads
signal can fire rather than being merely "applicable"), derives a display name,
and emits skills.json in agents.json row shape.

Writes a SEPARATE file. It never touches agents.json — placement on the board
is an owner decision (see the class-separation note in the session).
"""

import json
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

# Repo names too generic to stand alone on a leaderboard — qualify with the org.
GENERIC_NAMES = {
    "skills", "cli", "agents", "plugins", "plugin", "skill", "tools",
    "extensions", "commands", "hooks", "marketplace", "sdk", "core",
}

CATEGORY = "Agent Skills"  # provisional — see placement decision


def get_file(repo: str, path: str) -> str | None:
    try:
        r = requests.get(
            f"{GITHUB_API}/repos/{repo}/contents/{path}",
            headers={**HEADERS, "Accept": "application/vnd.github.raw"},
            timeout=20,
        )
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def resolve_packages(repo: str) -> dict:
    """Real npm / PyPI identifiers, only when actually publishable."""
    out = {}

    pkg = get_file(repo, "package.json")
    if pkg:
        try:
            data = json.loads(pkg)
            name = data.get("name")
            # A private or unnamed manifest publishes nothing — no downloads signal.
            if name and not data.get("private"):
                out["npm_package"] = name
        except Exception:
            pass

    pyproject = get_file(repo, "pyproject.toml")
    if pyproject:
        m = re.search(r'(?m)^\s*name\s*=\s*["\']([^"\']+)["\']', pyproject)
        if m:
            out["pypi_package"] = m.group(1)

    return out


def display_name(repo: str, fallback: str) -> str:
    owner, name = repo.split("/", 1)
    slug = name.lower()
    pretty = re.sub(r"[-_]+", " ", name).strip()
    if slug in GENERIC_NAMES:
        org = re.sub(r"[-_]+", " ", owner.replace("-labs", "").replace("-ai", "")).strip()
        return f"{org.title()} {pretty.title()}"
    if pretty.islower() or pretty.isupper():
        pretty = pretty.title()
    return pretty


def dedupe_names(rows: list[dict], taken: set[str]) -> int:
    """Org-qualify any display name that collides, in place. Returns the count.

    `display_name` only qualifies names that are generic in isolation ("skills",
    "cli"). It cannot see that four different orgs each ship an "agent-skills"
    repo, or that a name is already used by an agent. assign_unique_slugs would
    still produce unique URLs, but the category page would show four rows all
    labelled "Agent Skills" — one of them identical to the category itself.
    """
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["name"]] = counts.get(row["name"], 0) + 1

    fixed = 0
    for row in rows:
        name = row["name"]
        if counts[name] == 1 and name not in taken and name != CATEGORY:
            continue
        owner = row["repo"].split("/", 1)[0]
        org = re.sub(r"[-_]+", " ", owner.replace("-labs", "").replace("-ai", "")).strip()
        row["name"] = f"{org.title()} {name}"
        fixed += 1
    return fixed


def main() -> None:
    with open("skills-shortlist.json") as f:
        shortlist = json.load(f)

    rows, stats = [], {"npm": 0, "pypi": 0, "none": 0}
    for i, rec in enumerate(shortlist, 1):
        repo = rec["repo"]
        row = {
            "repo": repo,
            "name": display_name(repo, rec["name"]),
            "category": CATEGORY,
            "listing_status": "listed",
            "tracking_mode": "direct",
        }
        if rec.get("ships_package"):
            pkgs = resolve_packages(repo)
            row.update(pkgs)
            if "npm_package" in pkgs:
                stats["npm"] += 1
            if "pypi_package" in pkgs:
                stats["pypi"] += 1
            if not pkgs:
                stats["none"] += 1
        else:
            stats["none"] += 1

        rows.append(row)
        print(f"  [{i}/{len(shortlist)}] {repo:<44} {row['name'][:28]:<28} "
              f"npm={row.get('npm_package', '-')[:24]}")
        time.sleep(0.1)

    with open("agents.json") as f:
        taken = {a["name"] for a in json.load(f) if a.get("class") != "skill"}
    renamed = dedupe_names(rows, taken)
    print(f"\nOrg-qualified {renamed} colliding display name(s).")

    with open("skills.json", "w") as f:
        json.dump(rows, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"{len(rows)} rows -> skills.json")
    print(f"  npm identifier resolved : {stats['npm']}")
    print(f"  pypi identifier resolved: {stats['pypi']}")
    print(f"  no package (git-clone)  : {stats['none']}")


if __name__ == "__main__":
    main()
