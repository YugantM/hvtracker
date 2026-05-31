#!/usr/bin/env bash
# Full local dev environment — Postgres, Redis, scheduler, hot-reload.
# Usage:
#   ./dev.sh              Start the full stack on http://localhost:8000
#   ./dev.sh --rebuild    Re-render templates before starting (no API calls)
#   ./dev.sh --stop       Stop local Postgres and Redis

set -euo pipefail
cd "$(dirname "$0")"

PG_BIN="/opt/homebrew/opt/postgresql@14/bin"
PG_DATA="/opt/homebrew/var/postgresql@14"
PG_PORT=5433
PG_LOG="/opt/homebrew/var/log/postgresql@14.log"
DB_NAME="hvtracker_dev"

# ── Stop mode ────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
  echo "→ Stopping local services…"
  "$PG_BIN/pg_ctl" -D "$PG_DATA" stop 2>/dev/null && echo "  Postgres stopped" || echo "  Postgres was not running"
  brew services stop redis 2>/dev/null && echo "  Redis stopped" || echo "  Redis was not running"
  exit 0
fi

# ── Start Postgres on port 5433 (avoids conflict with system PG on 5432) ───
if ! "$PG_BIN/pg_isready" -p "$PG_PORT" -q 2>/dev/null; then
  echo "→ Starting Postgres on port $PG_PORT…"
  "$PG_BIN/pg_ctl" -D "$PG_DATA" -o "-p $PG_PORT" -l "$PG_LOG" start
  sleep 1
fi
# Create the dev database if it doesn't exist
"$PG_BIN/psql" -p "$PG_PORT" -d postgres -tc \
  "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || "$PG_BIN/psql" -p "$PG_PORT" -d postgres -c "CREATE DATABASE $DB_NAME"

# ── Start Redis ──────────────────────────────────────────────────────────────
if ! redis-cli ping &>/dev/null; then
  echo "→ Starting Redis…"
  brew services start redis
  sleep 1
fi

# ── Environment ──────────────────────────────────────────────────────────────
export DATABASE_URL="postgresql://localhost:${PG_PORT}/${DB_NAME}"
export REDIS_URL="redis://localhost:6379"
export GITHUB_TOKEN="${GITHUB_TOKEN:-$(grep -s GITHUB_TOKEN .env 2>/dev/null | cut -d= -f2 || true)}"
export OUTPUT_DIR="$PWD"

# ── Optional template rebuild ────────────────────────────────────────────────
if [[ "${1:-}" == "--rebuild" ]]; then
  echo "→ Rebuilding templates from cached render_state (no API calls)…"
  python fetch_and_build.py --render-only
  echo ""
fi

echo "→ Full dev stack on http://localhost:8000"
echo "  Postgres: localhost:$PG_PORT/$DB_NAME"
echo "  Redis:    localhost:6379"
echo "  Scheduler: enabled (2h cron)"
echo "  GITHUB_TOKEN: ${GITHUB_TOKEN:+set}${GITHUB_TOKEN:-NOT SET (fetches will fail)}"
echo "  Press Ctrl-C to stop the server (services keep running; use ./dev.sh --stop)"
echo ""

uvicorn app:app --host 127.0.0.1 --port 8000 --reload
