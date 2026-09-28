"""Flag correction requests that have waited too long for a reply.

/correct/ promises a reply within about a week. #216 (HOL Guard) waited 24
days because nothing surfaced it. Reads `gh issue list --json
number,title,createdAt,url,comments` output and exits 2 when any open
"[Correction]" issue is older than MAX_AGE_DAYS with no reply from the repo
side (owner, member or collaborator), 0 otherwise.

Usage: python scripts/check_corrections.py issues.json
"""
import json
import sys
from datetime import datetime, timedelta, timezone

MAX_AGE_DAYS = 5
MAINTAINER_ROLES = {"OWNER", "MEMBER", "COLLABORATOR"}


def overdue(issues: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    late = []
    for issue in issues:
        if not issue.get("title", "").lower().startswith("[correction]"):
            continue
        created = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
        answered = any(c.get("authorAssociation") in MAINTAINER_ROLES for c in issue.get("comments") or [])
        if created < cutoff and not answered:
            late.append(issue)
    return late


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as f:
        late = overdue(json.load(f))
    now = datetime.now(timezone.utc)
    for issue in late:
        created = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
        print(f"#{issue['number']} waiting {(now - created).days} days: {issue['title']} {issue['url']}")
    if not late:
        print(f"No correction request older than {MAX_AGE_DAYS} days without a reply.")
    return 2 if late else 0


if __name__ == "__main__":
    sys.exit(main())
