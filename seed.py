#!/usr/bin/env python3
"""One-time seed: load agents.json into the Postgres `agents` table.

Idempotent — re-running upserts. Requires DATABASE_URL. The web service also
seeds automatically on first startup when the table is empty; this script is
for manual/initial seeding.
"""
import json
import os
import sys

import db


def main() -> None:
    if not db.enabled():
        sys.exit("DATABASE_URL is not set — nothing to seed.")
    db.init_schema()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents.json")
    with open(path) as f:
        agents = json.load(f)
    for a in agents:
        db.upsert_agent(a)
    print(f"Seeded {len(agents)} agents (table now has {db.count_agents()}).")


if __name__ == "__main__":
    main()
