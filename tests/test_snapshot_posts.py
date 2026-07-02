"""Regression tests for automated weekly trust-snapshot posts (v3.2 T2.3).

Locks the plan's acceptance criteria: posts are deterministic (byte-identical
re-render), only completed ISO weeks publish, empty weeks are skipped, and —
the fact-check guarantee — every figure in the rendered prose traces to a
snapshot value (no invented numbers).
"""
import os
import re
from datetime import datetime, timedelta, timezone

from jinja2 import Environment, FileSystemLoader

import fetch_and_build as fb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mondays_back(n: int) -> str:
    """ISO date of the Monday n weeks before the current (incomplete) week."""
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    return (monday - timedelta(weeks=n)).strftime("%Y-%m-%d")


def _snap(date: str, agents: list[dict]) -> dict:
    return {"_date": date, "agents": agents}


def _agent(repo, name, trust, rank, prov=False, mcp="none", cat="Coding Agents"):
    return {"repo": repo, "name": name, "slug": repo.split("/")[1],
            "trust_score": trust, "rank": rank, "category": cat,
            "has_provenance": prov, "mcp_server_support": {"status": mcp}}


def _history():
    # Two completed weeks (baseline + week under report) plus a snapshot in the
    # current week that must NOT publish.
    base = [
        _agent("o/alpha", "Alpha", 70.0, 1),
        _agent("o/beta", "Beta", 60.0, 2),
    ]
    week1 = [
        _agent("o/alpha", "Alpha", 74.5, 1),                      # +4.5 trust
        _agent("o/beta", "Beta", 55.0, 2),                        # -5.0 trust
        _agent("o/gamma", "Gamma", 48.0, 3, prov=True, mcp="implemented"),  # new
    ]
    return [
        _snap(_mondays_back(2), base),
        _snap(_mondays_back(1), week1),
        _snap(datetime.now(timezone.utc).strftime("%Y-%m-%d"), week1),
    ]


def test_only_completed_weeks_publish_and_shape():
    posts = fb.compute_snapshot_posts(_history())
    assert len(posts) == 1  # current week excluded; only one completed pair
    p = posts[0]
    assert p["slug"].startswith("trust-snapshot-")
    assert p["counts"] == {"newly_listed": 1, "trust_up": 1, "trust_down": 1,
                           "provenance_gained": 0, "mcp_gained": 0}
    assert p["total_agents"] == 3
    assert p["trust_up"][0]["delta"] == 4.5
    assert p["trust_down"][0]["delta"] == -5.0


def test_empty_week_skipped():
    same = [_agent("o/alpha", "Alpha", 70.0, 1)]
    history = [_snap(_mondays_back(2), same), _snap(_mondays_back(1), same)]
    assert fb.compute_snapshot_posts(history) == []


def _render(post: dict) -> str:
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")),
                      autoescape=True)
    env.globals["css_hash"] = "test"
    return env.get_template("blog_snapshot.html.j2").render(post=post)


def test_render_is_deterministic():
    post = fb.compute_snapshot_posts(_history())[0]
    assert _render(post) == _render(post)


def test_every_figure_traces_to_snapshot_values():
    """The fact-check gate: no number appears in the visible prose unless it is
    a snapshot value (score, delta, count, rank, date part) — nothing invented."""
    history = _history()
    post = fb.compute_snapshot_posts(history)[0]
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ",
                  _render(post), flags=re.S)

    allowed: set[str] = set()
    for snap in history[:2]:
        for d in (snap["_date"], ):
            allowed.update(d.split("-"))                    # date parts
            allowed.add(str(int(d[:4])))
        for a in snap["agents"]:
            for v in (a["trust_score"], a["rank"]):
                allowed.update({f"{v}", f"{v:.1f}".rstrip("0").rstrip("."), f"{v:.1f}"})
    for k, v in post["counts"].items():
        allowed.add(str(v))
    allowed.add(str(post["total_agents"]))
    allowed.update({str(post["week"]), f"{post['week']:02d}", str(post["year"])})
    for sec in ("trust_up", "trust_down"):
        for i in post[sec]:
            d = abs(i["delta"])
            allowed.update({f"{d}", f"{d:.1f}"})
    # date_display like "June 29, 2026" contributes day-of-month without zero pad
    allowed.update({str(int(x)) for x in list(allowed) if x.isdigit()})

    for num in re.findall(r"\d+(?:\.\d+)?", text):
        assert num in allowed, f"figure {num!r} in prose does not trace to a snapshot value"
