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
    """Record a CLIENT-initiated verify check (one row per repo, count++).

    Only real requests reach here, so this is the only writer allowed to move
    `checked_at` or bump `checks`. `name` is coalesced because the open-lookup
    path has no display name and must not blank one a curated check supplied.
    """
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO verify_checks (repo, name, grade, trusted, provisional, stars, refreshed_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (repo) DO UPDATE SET "
            "name = COALESCE(EXCLUDED.name, verify_checks.name), "
            "grade = EXCLUDED.grade, trusted = EXCLUDED.trusted, "
            "provisional = EXCLUDED.provisional, stars = EXCLUDED.stars, "
            "checks = verify_checks.checks + 1, checked_at = now(), refreshed_at = now()",
            (repo, name, grade, trusted, provisional, stars),
        )
        conn.commit()


def refresh_verify_check(repo: str, name: str | None, grade: str | None,
                         trusted: bool, stars: int | None) -> None:
    """Re-evaluate our own data for a repo already in the feed (nightly job).

    Deliberately does NOT touch `checked_at` or `checks` — nobody asked about
    this repo, we just revalidated it — and never inserts, so the job can only
    update repos a real client already put in the feed. `provisional` is left
    alone so a row that has since become curated is not pushed back.
    """
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE verify_checks SET "
            "name = COALESCE(%s, name), grade = %s, trusted = %s, stars = %s, "
            "refreshed_at = now() WHERE repo = %s",
            (name, grade, trusted, stars, repo),
        )
        conn.commit()


def recent_verify_checks(limit: int = 100) -> list[dict] | None:
    """Public feed rows, newest first. Returns None when the DB is disabled."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT repo, name, grade, trusted, provisional, stars, checks, "
            "to_char(checked_at, 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), "
            "to_char(refreshed_at, 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
            "FROM verify_checks ORDER BY checked_at DESC LIMIT %s",
            (limit,),
        )
        cols = ["repo", "name", "grade", "trusted", "provisional", "stars", "checks",
                "checked_at", "refreshed_at"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def verify_check_targets(limit: int = 200) -> list[str]:
    """Repos in the public feed, for the daily refresh job (stalest data first).

    Ordered by when we last REFRESHED (not when a client last asked), so the
    job walks its own backlog; rows never refreshed sort first via COALESCE.
    """
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT repo FROM verify_checks WHERE provisional = true "
                    "ORDER BY COALESCE(refreshed_at, checked_at) ASC LIMIT %s", (limit,))
        return [row[0] for row in cur.fetchall()]


# ---- machine-usage rollup (usage.py, /live/) -------------------------------

def add_usage_counts(rows: list[tuple[str, str, int]]) -> None:
    """Add (hour-bucket, channel, count) deltas to the rollup.

    Additive upsert, so a flush that is retried after a partial failure can
    only over-count by what it actually re-sends, and concurrent web replicas
    accumulate into the same bucket instead of clobbering each other.
    """
    if not enabled() or not rows:
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO usage_hourly (bucket, channel, count) VALUES (%s, %s, %s) "
            "ON CONFLICT (bucket, channel) DO UPDATE SET "
            "count = usage_hourly.count + EXCLUDED.count",
            rows,
        )
        conn.commit()


def usage_totals() -> dict[str, int] | None:
    """All-time counts per channel. None when the DB is disabled."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT channel, SUM(count) FROM usage_hourly GROUP BY channel")
        return {row[0]: int(row[1] or 0) for row in cur.fetchall()}


def usage_series(hours: int = 24) -> list[dict] | None:
    """Per-hour counts for the last `hours`, oldest first. None when disabled."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT to_char(bucket, 'YYYY-MM-DD\"T\"HH24:00:00\"Z\"'), channel, count "
            "FROM usage_hourly WHERE bucket >= date_trunc('hour', now()) "
            "- make_interval(hours => %s) ORDER BY bucket ASC",
            (max(0, int(hours) - 1),),
        )
        out: dict[str, dict[str, int]] = {}
        for bucket, channel, count in cur.fetchall():
            out.setdefault(bucket, {})[channel] = int(count or 0)
        return [{"bucket": b, "counts": c} for b, c in sorted(out.items())]


# ---- accounts / watchlist (auth.py) ---------------------------------------

_USER_COLS = ["id", "provider", "provider_id", "login", "name", "email", "avatar_url"]


def upsert_user(provider: str, provider_id: str, login: str | None,
                name: str | None, email: str | None, avatar_url: str | None) -> dict | None:
    """Insert or update a user by (provider, provider_id); return the row."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (provider, provider_id, login, name, email, avatar_url) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (provider, provider_id) DO UPDATE SET "
            "login = EXCLUDED.login, name = EXCLUDED.name, email = EXCLUDED.email, "
            "avatar_url = EXCLUDED.avatar_url, last_login = now() "
            f"RETURNING {', '.join(_USER_COLS)}",
            (provider, str(provider_id), login, name, email, avatar_url),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(zip(_USER_COLS, row)) if row else None


def get_user(user_id: int) -> dict | None:
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_USER_COLS)} FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return dict(zip(_USER_COLS, row)) if row else None


def get_password_user(email: str) -> dict | None:
    """Look up an email/password account (includes password_hash for verify)."""
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_USER_COLS)}, password_hash FROM users "
                    "WHERE provider = 'password' AND provider_id = %s", (email,))
        row = cur.fetchone()
        if not row:
            return None
        rec = dict(zip(_USER_COLS, row[:len(_USER_COLS)]))
        rec["password_hash"] = row[-1]
        return rec


def create_password_user(email: str, password_hash: str) -> dict | None:
    """Create an email/password account. Returns None if the email already exists."""
    if not enabled():
        return None
    handle = email.split("@")[0] or email
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (provider, provider_id, login, name, email, password_hash) "
            "VALUES ('password', %s, %s, %s, %s, %s) "
            "ON CONFLICT (provider, provider_id) DO NOTHING "
            f"RETURNING {', '.join(_USER_COLS)}",
            (email, handle, handle, email, password_hash),
        )
        row = cur.fetchone()
        conn.commit()
        return dict(zip(_USER_COLS, row)) if row else None


def list_watch(user_id: int) -> list[str]:
    if not enabled():
        return []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT agent_slug FROM watchlist WHERE user_id = %s ORDER BY created_at", (user_id,))
        return [r[0] for r in cur.fetchall()]


def add_watch(user_id: int, slug: str) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO watchlist (user_id, agent_slug) VALUES (%s, %s) "
                    "ON CONFLICT DO NOTHING", (user_id, slug))
        conn.commit()


def remove_watch(user_id: int, slug: str) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM watchlist WHERE user_id = %s AND agent_slug = %s", (user_id, slug))
        conn.commit()


def get_last_read(user_id: int) -> str | None:
    if not enabled():
        return None
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_char(last_read_at, 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
                    "FROM notification_reads WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None


def set_last_read(user_id: int) -> None:
    if not enabled():
        return
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO notification_reads (user_id, last_read_at) VALUES (%s, now()) "
                    "ON CONFLICT (user_id) DO UPDATE SET last_read_at = now()", (user_id,))
        conn.commit()
