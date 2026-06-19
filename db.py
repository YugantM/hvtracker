"""Postgres data layer for HVTracker.

Source of truth for the curated agent list and the submission/correction
moderation queue. Falls back to reading agents.json directly when DATABASE_URL
is unset (local development and CI), so the generator and tests run without a
live database.
"""
from __future__ import annotations

import json
import os
from typing import Any

DATABASE_URL = os.environ.get("DATABASE_URL", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Columns that map 1:1 to agents.json keys. Anything else goes into `extra`.
_AGENT_COLS = [
    "repo", "name", "category", "listing_status", "tracking_mode", "status",
    "npm_package", "pypi_package", "crate_package", "hn_search_term", "fingerprints",
]


def enabled() -> bool:
    """True when a real Postgres backend is configured."""
    return bool(DATABASE_URL)


def _connect():
    import psycopg  # imported lazily so file-fallback mode needs no driver
    return psycopg.connect(DATABASE_URL)


def init_schema() -> None:
    """Apply schema.sql (idempotent). No-op without DATABASE_URL."""
    if not enabled():
        return
    with open(os.path.join(BASE_DIR, "schema.sql")) as f:
        ddl = f.read()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(ddl)
        conn.commit()


# ---- agents --------------------------------------------------------------

def _row_to_agent(cols: list[str], values: tuple) -> dict[str, Any]:
    rec = dict(zip(cols, values))
    extra = rec.pop("extra", None) or {}
    agent = {k: v for k, v in rec.items() if v is not None}
    agent.update(extra)
    return agent


def load_agents() -> list[dict]:
    """Return the curated agent list shaped like agents.json entries.

    Reads from Postgres when configured, else falls back to agents.json.
    """
    if not enabled():
        with open(os.path.join(BASE_DIR, "agents.json")) as f:
            return json.load(f)
    cols = _AGENT_COLS + ["extra"]
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(cols)} FROM agents ORDER BY repo")
        return [_row_to_agent(cols, row) for row in cur.fetchall()]


def count_agents() -> int:
    if not enabled():
        with open(os.path.join(BASE_DIR, "agents.json")) as f:
            return len(json.load(f))
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM agents")
        return cur.fetchone()[0]


def upsert_agent(agent: dict) -> None:
    """Insert or update one agent from an agents.json-shaped dict."""
    if not enabled():
        raise RuntimeError("upsert_agent requires DATABASE_URL")
    known = {k: agent.get(k) for k in _AGENT_COLS}
    known["fingerprints"] = json.dumps(agent["fingerprints"]) if agent.get("fingerprints") else None
    extra = {k: v for k, v in agent.items() if k not in _AGENT_COLS}
    cols = _AGENT_COLS + ["extra"]
    vals = [known[k] for k in _AGENT_COLS] + [json.dumps(extra) if extra else None]
    placeholders = ", ".join(["%s"] * len(cols))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "repo")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO agents ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT (repo) DO UPDATE SET {updates}",
            vals,
        )
        conn.commit()


def delete_agents_not_in(repos: list[str]) -> int:
    """Remove agents from DB whose repo is not in the given list."""
    if not enabled():
        raise RuntimeError("delete_agents_not_in requires DATABASE_URL")
    if not repos:
        return 0
    with _connect() as conn, conn.cursor() as cur:
        placeholders = ", ".join(["%s"] * len(repos))
        cur.execute(f"DELETE FROM agents WHERE repo NOT IN ({placeholders})", repos)
        deleted = cur.rowcount
        conn.commit()
    return deleted


# ---- submissions / corrections -------------------------------------------

def add_submission(repo: str, payload: dict, contact: str | None) -> int:
    if not enabled():
        raise RuntimeError("add_submission requires DATABASE_URL")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO submissions (repo, payload, contact) VALUES (%s, %s, %s) RETURNING id",
            (repo, json.dumps(payload), contact),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


def add_correction(repo: str, payload: dict, contact: str | None) -> int:
    if not enabled():
        raise RuntimeError("add_correction requires DATABASE_URL")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO corrections (repo, payload, contact) VALUES (%s, %s, %s) RETURNING id",
            (repo, json.dumps(payload), contact),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


def add_interest_signup(kind: str, email: str, repo: str | None, payload: dict) -> int:
    if not enabled():
        raise RuntimeError("add_interest_signup requires DATABASE_URL")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO interest_signups (kind, email, repo, payload) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (kind, email, repo, json.dumps(payload)),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


def list_queue(table: str, status: str = "pending") -> list[dict]:
    if table not in ("submissions", "corrections"):
        raise ValueError(table)
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT id, repo, payload, contact, status, created_at "
            f"FROM {table} WHERE status = %s ORDER BY created_at",
            (status,),
        )
        cols = ["id", "repo", "payload", "contact", "status", "created_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def record_verify_check(repo: str, name: str | None, grade: str | None,
                        trusted: bool, provisional: bool, stars: int | None) -> None:
    """Upsert a public verify check (one row per repo, newest wins, count++)."""
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO verify_checks (repo, name, grade, trusted, provisional, stars) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (repo) DO UPDATE SET "
            "name = EXCLUDED.name, grade = EXCLUDED.grade, trusted = EXCLUDED.trusted, "
            "provisional = EXCLUDED.provisional, stars = EXCLUDED.stars, "
            "checks = verify_checks.checks + 1, checked_at = now()",
            (repo, name, grade, trusted, provisional, stars),
        )
        conn.commit()


def recent_verify_checks(limit: int = 100) -> list[dict] | None:
    """Public feed rows, newest first. Returns None when the DB is disabled."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT repo, name, grade, trusted, provisional, stars, checks, "
            "to_char(checked_at, 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
            "FROM verify_checks ORDER BY checked_at DESC LIMIT %s",
            (limit,),
        )
        cols = ["repo", "name", "grade", "trusted", "provisional", "stars", "checks", "checked_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def verify_check_targets(limit: int = 200) -> list[str]:
    """Repos in the public feed, for the daily refresh job (oldest-checked first)."""
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT repo FROM verify_checks WHERE provisional = true "
                    "ORDER BY checked_at ASC LIMIT %s", (limit,))
        return [row[0] for row in cur.fetchall()]
