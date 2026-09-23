#!/usr/bin/env python3
"""Verify npm / PyPI / crates.io identifiers before they go on a roster row.

Why this is a correctness gate and not tidying: `detect_package_provenance_drift`
in fetch_and_build.py compares a row's package source against its tracked repo
and raises a drift warning when they disagree. A guessed identifier therefore
does not fail quietly — it publishes a false supply-chain accusation against
somebody else's project, the #96-#99 false-positive class.

The obvious name is frequently taken by an unrelated project. Measured on the
2026-08-10 batch: PyPI `excel-mcp-server` belongs to zavora-ai, `maverick-mcp`
to airlock-labs, `spec-workflow-mcp` to kingkongshot; npm `camofox-browser` to
redf0x1, `xiaohongshu-mcp` to "not", `fence` to bhickey. Four of that batch's
first-draft identifiers were guessed from repo names and three were wrong.

Method: collect the names a project itself advertises (README badge URLs and
install lines) plus repo-name variants, then accept one only when the registry
metadata DECLARES the same GitHub repo in repository/homepage/bugs/project_urls.
Scanning the whole metadata document instead would match the first github.com
URL anywhere in it — a dependency, a funding link — which is how a wrong
identifier gets wired in the first place.

A candidate that matches nothing is reported, never guessed. The row then
carries no identifier and scores GitHub-only: a lower coverage grade, which is
honest, where a guess would not be.

Usage:
    python3 scripts/verify_package_identifiers.py rows.json
    python3 scripts/verify_package_identifiers.py rows.json --apply
"""
import argparse
import concurrent.futures as cf
import json
import re
import sys
import urllib.parse
import urllib.request

FIELD = {"npm": "npm_package", "pypi": "pypi_package", "cargo": "crate_package"}
REGISTRY_URL = {
    "npm": "https://registry.npmjs.org/{}",
    "pypi": "https://pypi.org/pypi/{}/json",
    "cargo": "https://crates.io/api/v1/crates/{}",
}


def fetch(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hvtracker-pkg-verify"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception:
        return None


def _gh(url) -> str | None:
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git|/|$)", str(url or ""), re.I)
    return f"{m.group(1)}/{m.group(2)}".lower() if m else None


def declared_repos(blob: dict) -> set[str]:
    """Repos the package DECLARES — never a free-text scan of the document."""
    out = set()
    rep = blob.get("repository")
    bugs = blob.get("bugs")
    for v in (rep.get("url") if isinstance(rep, dict) else rep,
              blob.get("homepage"),
              bugs.get("url") if isinstance(bugs, dict) else bugs):
        if _gh(v):
            out.add(_gh(v))
    info = blob.get("info") or {}
    for v in list((info.get("project_urls") or {}).values()) + [info.get("home_page")]:
        if _gh(v):
            out.add(_gh(v))
    return out


def candidates(repo: str, readme: str) -> list[tuple[str, str]]:
    owner, name = repo.split("/")
    out, seen = [], set()

    def push(kind, value):
        v = (kind, value)
        if v not in seen and value:
            seen.add(v)
            out.append(v)

    for kind, pat in (("npm", r"npmjs\.com/package/([@\w./%-]+)"),
                      ("npm", r"badge\.fury\.io/js/([@\w.%-]+)"),
                      ("pypi", r"pypi\.org/project/([\w.-]+)"),
                      ("pypi", r"pepy\.tech/project/([\w.-]+)"),
                      ("cargo", r"crates\.io/crates/([\w-]+)")):
        for m in re.finditer(pat, readme or "", re.I):
            push(kind, urllib.parse.unquote(m.group(1)).rstrip("/"))
    # Install lines name the package, but also name dependencies — hence the
    # try-every-candidate loop in verify() rather than trusting the first hit.
    for m in re.finditer(r"(?:pipx install|uvx|pip install)\s+([\w.-]+)", readme or ""):
        if m.group(1) not in ("uv", "pip"):
            push("pypi", m.group(1))
    # `npx <pkg>` is the dominant install idiom for Node CLIs and MCP servers,
    # and omitting it is not a small miss: it hid @deepseek-ai/dsh, the official
    # package of a 130k-star first-party harness, while the unscoped
    # `deepseek-harness` name on npm belongs to an unrelated account.
    for m in re.finditer(r"(?:npm install|npm i|pnpm add|yarn add|npx|bunx)(?:\s+-g|\s+-y)*\s+(@?[\w./-]+)",
                         readme or ""):
        if m.group(1) not in ("-g", "-y", "install"):
            push("npm", m.group(1))
    for variant in (name, name.replace("_", "-"), name.lower(),
                    name.lower().replace("_", "-"), f"@{owner.lower()}/{name.lower()}"):
        for kind in ("npm", "pypi", "cargo"):
            push(kind, variant)
    return out[:20]


def verify(repo: str, readme: str) -> tuple[str | None, str | None, str]:
    misses = []
    for kind, pkg in candidates(repo, readme):
        data = fetch(REGISTRY_URL[kind].format(urllib.parse.quote(pkg, safe="@")))
        if not data:
            continue
        if kind == "cargo":
            data = data.get("crate") or {}
        found = declared_repos(data)
        if repo.lower() in found:
            return kind, pkg, "declared-repo match"
        if found:
            misses.append(f"{pkg}->{sorted(found)[0]}")
    return None, None, ("TAKEN: " + ", ".join(misses[:3])) if misses else "no verified package"


def readme_for(repo: str) -> str:
    for br in ("main", "master", "dev"):
        for fn in ("README.md", "readme.md", "README.MD"):
            try:
                url = f"https://raw.githubusercontent.com/{repo}/{br}/{fn}"
                with urllib.request.urlopen(url, timeout=25) as r:
                    return r.read().decode("utf-8", "replace")
            except Exception:
                continue
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rows", help="JSON file of roster-shaped rows")
    ap.add_argument("--apply", action="store_true",
                    help="write verified identifiers back into the rows file")
    ap.add_argument("--readmes", help="optional JSON cache: {repo: readme_text}")
    args = ap.parse_args()

    rows = json.load(open(args.rows))
    cache = json.load(open(args.readmes)) if args.readmes else {}

    missing = [r["repo"] for r in rows if r["repo"] not in cache]
    if missing:
        with cf.ThreadPoolExecutor(10) as ex:
            cache.update(dict(zip(missing, ex.map(readme_for, missing))))

    results = {}
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(verify, r["repo"], cache.get(r["repo"], "")): r for r in rows}
        for fut in cf.as_completed(futs):
            results[futs[fut]["repo"]] = fut.result()

    ok = 0
    for r in rows:
        kind, pkg, why = results[r["repo"]]
        if kind:
            ok += 1
            print(f"  OK   {r['repo']:<44}{kind}:{pkg}")
            if args.apply:
                for f in FIELD.values():
                    r.pop(f, None)
                r[FIELD[kind]] = pkg
        else:
            print(f"  --   {r['repo']:<44}{why}")
    print(f"\n{ok}/{len(rows)} rows get a verified identifier; "
          f"{len(rows) - ok} carry none rather than a guess.")

    if args.apply:
        json.dump(rows, open(args.rows, "w"), indent=1)
        print(f"wrote {args.rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
