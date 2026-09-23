#!/usr/bin/env python3
"""Refuse a deploy that would break production. Run from the worktree you are
about to `railway up`.

Every outage on record came from something the local gates can't see:

- 2026-09-17: `usage.py` was imported by the app but missing from the
  Dockerfile's COPY lines (they copy by filename) -> boot crash, 502.
- 2026-09-21: `main` carried a 464-row roster against production's 1,705 ->
  the live board shrank to 441 agents for a day.

Checks:
1. Every local module reachable from app.py's imports is COPY'd.
2. Every BASE_DIR file/dir the runtime code reads is COPY'd.
3. agents.json has at least as many rows as live /healthz `catalog_agents`
   (skip with --offline; the CI test runs checks 1-2 only).

Exit 0 = safe to deploy, 1 = do not deploy.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import urllib.request

RUNTIME_ENTRY = "app"
# Modules whose BASE_DIR reads ship in the image (fetch_and_build runs there
# as the render subprocess; its inputs are covered by check 1's module list).
BASE_DIR_READERS = ("app.py", "mcp_server.py", "auth.py")


def runtime_modules(root: str) -> set[str]:
    """Local top-level modules reachable by import from app.py."""
    local = {f[:-3] for f in os.listdir(root) if f.endswith(".py")}
    seen: set[str] = set()
    todo = [RUNTIME_ENTRY]
    while todo:
        mod = todo.pop()
        if mod in seen or mod not in local:
            continue
        seen.add(mod)
        with open(os.path.join(root, f"{mod}.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                todo += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                todo.append(node.module.split(".")[0])
    return seen


def _copy_sources(root: str) -> list[str]:
    """Source paths of every plain (non --from) COPY line in the Dockerfile."""
    sources: list[str] = []
    with open(os.path.join(root, "Dockerfile"), encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "COPY" and not parts[1].startswith("--"):
                sources += [p.rstrip("/") for p in parts[1:-1]]
    return sources


def _covered(path: str, sources: list[str]) -> bool:
    return any(path == s or path.startswith(s + "/") for s in sources)


def base_dir_paths(root: str) -> set[str]:
    """Paths read via os.path.join(BASE_DIR, "<literal>", ...) in runtime code.

    Only the leading string-literal arguments count; a dynamic tail (an
    f-string slug) makes the literal prefix a directory requirement.
    """
    paths: set[str] = set()
    for name in BASE_DIR_READERS:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "join" and node.args
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == "BASE_DIR"):
                continue
            parts = []
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    parts.append(arg.value)
                else:
                    break
            if parts:
                paths.add("/".join(parts))
    return paths


def image_gaps(root: str) -> list[str]:
    """Everything the runtime needs that the Dockerfile does not COPY."""
    sources = _copy_sources(root)
    gaps = [f"module {m}.py" for m in sorted(runtime_modules(root))
            if not _covered(f"{m}.py", sources)]
    gaps += [f"file {p}" for p in sorted(base_dir_paths(root))
             if not _covered(p, sources)]
    return gaps


def roster_gap(root: str) -> str | None:
    """Problem string if the ref's roster is smaller than live, else None."""
    with open(os.path.join(root, "agents.json"), encoding="utf-8") as f:
        rows = len(json.load(f))
    req = urllib.request.Request("https://hvtracker.net/healthz",
                                 headers={"User-Agent": "Mozilla/5.0 (hvtracker-predeploy)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        live = json.load(resp)["catalog_agents"]
    print(f"roster: this ref {rows} rows, live catalog_agents {live}")
    if rows < live:
        return f"agents.json has {rows} rows but production lists {live}: deploying would delist agents"
    return None


def main(argv: list[str]) -> int:
    root = os.path.abspath(next((a for a in argv if not a.startswith("--")), "."))
    problems = [f"Dockerfile does not COPY {g}" for g in image_gaps(root)]
    if "--offline" not in argv:
        gap = roster_gap(root)
        if gap:
            problems.append(gap)
    if problems:
        print("DO NOT DEPLOY:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK: {len(runtime_modules(root))} runtime modules and "
          f"{len(base_dir_paths(root))} BASE_DIR paths are in the image")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
