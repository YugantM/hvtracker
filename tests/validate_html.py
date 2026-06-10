#!/usr/bin/env python3
"""HTML5 structural validation for rendered pages.

Parses each sample page with html5lib in strict mode.  Any parse error
(unclosed tag, malformed attribute, doctype issue, etc.) fails CI.

Run from the repo root after a render-only build:

    python fetch_and_build.py --render-only
    python tests/validate_html.py
"""

import os
import sys

import html5lib


# Representative pages — covers every template used by the build.
SAMPLES = [
    "index.html",
    "agents/langgraph/index.html",
    "agents/odysseus/index.html",
    "categories/coding-agents/index.html",
    "compare/index.html",
    "methodology/index.html",
    "blog/index.html",
    "roadmap/index.html",
    "badges/index.html",
    "changes/index.html",
]


def main() -> int:
    failures: list[tuple[str, list[str]]] = []
    checked = 0
    for path in SAMPLES:
        if not os.path.isfile(path):
            print(f"  skip (missing): {path}")
            continue
        parser = html5lib.HTMLParser(strict=True)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            parser.parse(text)
            checked += 1
            print(f"  ok: {path}")
        except html5lib.html5parser.ParseError as e:
            failures.append((path, [str(e)] + [str(err) for err in parser.errors[:5]]))
            print(f"  FAIL: {path}")

    if failures:
        print("\nHTML validation errors:")
        for path, errors in failures:
            print(f"\n{path}")
            for err in errors:
                print(f"  {err}")
        return 1

    print(f"\nValidated {checked} HTML files — all clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
