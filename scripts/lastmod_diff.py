#!/usr/bin/env python3
"""How many pages would get a new sitemap <lastmod> if this tree deployed.

Since #314 a page's lastmod moves only when its fingerprint changes
(lastmod_fingerprint: numbers masked, <!--lastmod:skip--> regions dropped). A
template edit that touches every page of a type re-dates all of them. On
3 Oct, #322 re-dated 1,445 profiles that way, and in Phase 10 a Jinja comment
on its own line nearly did the same (no trim_blocks, so it renders a blank line).

Both renders run in this checkout, because the render also reads untracked
inputs (output/history, data.json, caches) that a fresh worktree lacks. The
files that differ from the base ref are swapped to their base version (written
with `git show`, so the index is untouched), rendered, then restored, always.
Run it before merging a template change. If it reports a sitewide re-date you
didn't intend, bump LASTMOD_FP_VERSION instead (its migration keeps dates).

Usage: python scripts/lastmod_diff.py [--base origin/main]
"""
import argparse
import collections
import glob
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from fetch_and_build import lastmod_fingerprint  # noqa: E402

CHURN = ["data/render_state.json", "og-v2.png", "scorecard-cache.json"]
SKIP_DIRS = {"output", ".venv", "node_modules", "dist", ".git"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def render_fingerprints() -> dict[str, str]:
    subprocess.run([sys.executable, "fetch_and_build.py", "--render-only"], cwd=ROOT,
                   check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "--", *CHURN], cwd=ROOT)
    out = {}
    for path in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
        rel = os.path.relpath(path, ROOT)
        if rel.split(os.sep)[0] not in SKIP_DIRS:
            with open(path, "rb") as f:
                out[rel] = lastmod_fingerprint(f.read(), "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()
    changed_files = [p for p in git("diff", "--name-only", args.base).splitlines()
                     if p not in CHURN and p != "scripts/lastmod_diff.py"]
    in_base = set(git("ls-tree", "-r", "--name-only", args.base).splitlines())
    with tempfile.TemporaryDirectory() as keep:
        for p in changed_files:  # keep the working versions
            if os.path.exists(os.path.join(ROOT, p)):
                os.makedirs(os.path.join(keep, os.path.dirname(p)), exist_ok=True)
                shutil.copy2(os.path.join(ROOT, p), os.path.join(keep, p))
        try:
            for p in changed_files:  # base versions in place
                target = os.path.join(ROOT, p)
                if p in in_base:
                    with open(target, "wb") as f:
                        f.write(subprocess.run(["git", "show", f"{args.base}:{p}"], cwd=ROOT,
                                               check=True, capture_output=True).stdout)
                elif os.path.exists(target):
                    os.remove(target)
            base = render_fingerprints()
        finally:
            for p in changed_files:  # always restore the working versions
                kept = os.path.join(keep, p)
                target = os.path.join(ROOT, p)
                if os.path.exists(kept):
                    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                    shutil.copy2(kept, target)
                elif os.path.exists(target):
                    os.remove(target)
    new = render_fingerprints()
    changed, total, examples = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for rel in sorted(set(base) & set(new)):
        kind = rel.split(os.sep)[0] if os.sep in rel else "home"
        total[kind] += 1
        if base[rel] != new[rel]:
            changed[kind] += 1
            examples[kind].append(rel)
    print(f"Pages whose sitemap date would move ({args.base} -> working tree; "
          f"{len(changed_files)} changed file(s)):")
    for kind in sorted(changed, key=lambda k: -changed[k]):
        print(f"  {kind:14} {changed[kind]:5} of {total[kind]:5}   e.g. {', '.join(examples[kind][:2])}")
    print(f"Total: {sum(changed.values())} of {sum(total.values())} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
