#!/usr/bin/env python3
"""Incident watch: a critical or high advisory now affects a listed project.

Clicks follow incidents: after Composio's May 2026 incident, "is composio safe"
became HVTracker's best query (position ~3, most of the site's clicks). The
profile page updates itself on the next full fetch; what needs a person is
posting about it while people are searching. This reads the live board and
prints one issue per critical/high advisory, published in the last 14 days,
that no `incident-watch` issue names yet; the workflow opens them. Read-only
against hvtracker.net.

stdin: existing incident-watch issue titles, one per line (open and closed).
stdout: JSON list of {"title", "body"} to open.
Exit 0 = ran (list may be empty), 1 = the board could not be read.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import date, timedelta

URL = os.environ.get("BOARD_URL", "https://hvtracker.net/data.json")
SITE = "https://hvtracker.net"
CAPS = {"CRITICAL": "64.9 (Grade C)", "HIGH": "79.9 (Grade B)"}
# Search interest peaks around disclosure; an advisory from months ago that a
# newly listed project carries is shown on its page but is not news to post.
MAX_AGE_DAYS = 14


def new_incidents(rows: list[dict], seen_titles: str, today: date | None = None) -> list[dict]:
    cutoff = ((today or date.today()) - timedelta(days=MAX_AGE_DAYS)).isoformat()
    out = []
    for r in rows:
        adv = r.get("advisories") or {}
        for it in adv.get("found") or []:
            sev = it.get("severity")
            if sev not in CAPS or it["id"] in seen_titles or (it.get("published") or "") < cutoff:
                continue
            cve = next((a for a in it.get("aliases") or [] if a.startswith("CVE-")), None)
            ref = f"{it['id']}" + (f" / {cve}" if cve else "")
            page = f"{SITE}/agents/{r['slug']}/"
            post = (f"{r['name']} has an unfixed {sev.lower()} advisory ({cve or it['id']}) in "
                    f"{it['package']} {it['version']}, the release you'd install today. HVTrust caps "
                    f"its score at {CAPS[sev].split()[0]} until a fixed release ships. {page}")
            out.append({
                "title": f"Incident watch: {r['name']} — {it['id']} ({sev})",
                "body": "\n".join([
                    f"A {sev.lower()} advisory now affects **{r['name']}** "
                    f"(rank #{r.get('rank')}, HVTrust {r.get('trust_score')}).",
                    "",
                    f"- Advisory: [{ref}](https://osv.dev/vulnerability/{it['id']}), published {it.get('published')}",
                    f"- Affects: {it['package']} {it['version']} (latest release)",
                    f"- Summary: {it.get('summary', '').strip()}",
                    f"- Profile: {page}#advisories",
                    "",
                    "Playbook (docs/incident-playbook.md):",
                    f"- [ ] The profile shows it and the score is capped at {CAPS[sev]} "
                    f"(check `{page}?cb=1`; the edge may serve a stale copy)",
                    "- [ ] Post on X within 2 days, while people search for it. Draft:",
                    "",
                    f"> {post}",
                    "",
                    "- [ ] Close this issue once a fixed release ships (the cap lifts on the next full fetch)",
                ]),
            })
    return out


def main() -> int:
    req = urllib.request.Request(f"{URL}?nocache={int(time.time())}",
                                 # Cloudflare blocks the default python-urllib user agent.
                                 headers={"User-Agent": "Mozilla/5.0 (hvtracker-incident-watch)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            rows = json.load(resp)["agents"]
    except Exception as e:
        print(f"ERROR: could not read {URL}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(new_incidents(rows, sys.stdin.read()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
