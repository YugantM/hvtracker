"""Weekly "new listing candidates" report from discover_agents.py's output.

Discovery proposes; the owner decides (Eligibility Spec). This turns
candidates.json (everything that passes the automated rubric) into a short,
reviewable list: projects created recently (older ones have had their chance
to be listed or rejected), minus indexes and course material that ship no
agent, ranked by stars.

Usage: python scripts/discovery_report.py [candidates.json] [--days 120] [--top 50]
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

# Repos that index or teach rather than ship something an agent runs. Same
# spirit as discover_skills.py's "list" exclusion.
_LIST_DESC = ("curated list", "curated collection", "a list of", "collection of awesome",
              "interview guide", "interview questions", "tutorial", "course", "cheat sheet",
              "cheatsheet", "learning path", "roadmap for")


def is_list_or_course(c: dict) -> bool:
    name = (c.get("name") or c.get("repo", "").split("/")[-1]).lower()
    desc = (c.get("description") or "").lower()
    return name.startswith("awesome") or "awesome-" in name or any(p in desc for p in _LIST_DESC)


def shortlist(candidates: list[dict], days: int = 120, top: int = 50,
              today: datetime | None = None) -> list[dict]:
    cutoff = ((today or datetime.now(timezone.utc)) - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [c for c in candidates if (c.get("created") or "") >= cutoff and not is_list_or_course(c)]
    recent.sort(key=lambda c: -c.get("stars", 0))
    return recent[:top]


def _cell(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    text = text[:limit - 1] + "…" if len(text) > limit else text
    return text.replace("|", "\\|")


def render(rows: list[dict], total: int, days: int) -> str:
    lines = [
        f"{len(rows)} of {total} candidates that pass the automated eligibility rubric were "
        f"created in the last {days} days and aren't lists or course material. "
        "Discovery proposes; the owner decides: reply with the repos to add. Rejected ones go "
        "into `REVIEWED_REJECTED` in `discover_agents.py` so they aren't proposed again.",
        "",
        "| # | Repository | Stars | Created | License | Description |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(rows, 1):
        lines.append(f"| {i} | [{c['repo']}]({c.get('url') or 'https://github.com/' + c['repo']}) | "
                     f"{c.get('stars', 0):,} | {c.get('created', '')} | {_cell(c.get('license', ''), 16)} | "
                     f"{_cell(c.get('description', ''), 90)} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="candidates.json")
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()
    try:
        with open(args.path, encoding="utf-8") as f:
            candidates = json.load(f)
    except FileNotFoundError:
        candidates = []
    sys.stdout.write(render(shortlist(candidates, args.days, args.top), len(candidates), args.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
