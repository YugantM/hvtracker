-- HVTracker Postgres schema.
-- Postgres is the source of truth for the curated agent list and the
-- submission/correction moderation queue. Generated signals/history live on
-- the web service's volume (data.json, output/history/), not here.

CREATE TABLE IF NOT EXISTS agents (
    repo            TEXT PRIMARY KEY,          -- "owner/name"
    name            TEXT NOT NULL,
    category        TEXT,
    listing_status  TEXT DEFAULT 'listed',
    tracking_mode   TEXT,
    status          TEXT,                       -- e.g. 'legacy'; NULL = active
    npm_package     TEXT,
    pypi_package    TEXT,
    crate_package   TEXT,
    hn_search_term  TEXT,
    fingerprints    JSONB,
    extra           JSONB,                      -- catch-all for future agents.json fields
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS submissions (
    id          BIGSERIAL PRIMARY KEY,
    repo        TEXT NOT NULL,
    payload     JSONB NOT NULL,                 -- proposed agent fields
    contact     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',-- pending | approved | rejected
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corrections (
    id          BIGSERIAL PRIMARY KEY,
    repo        TEXT NOT NULL,
    payload     JSONB NOT NULL,                 -- {message, field, ...}
    contact     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interest_signups (
    id          BIGSERIAL PRIMARY KEY,
    kind        TEXT NOT NULL,                  -- alerts | track-agent | sponsor | api-access
    email       TEXT NOT NULL,
    repo        TEXT,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Public "recently checked" feed for /verify. One row per repo (newest check
-- wins); `checks` counts how many times it's been verified. Public by default.
CREATE TABLE IF NOT EXISTS verify_checks (
    repo           TEXT PRIMARY KEY,
    name           TEXT,
    grade          TEXT,
    trusted        BOOLEAN,
    provisional    BOOLEAN,
    stars          INTEGER,
    checks         INTEGER NOT NULL DEFAULT 1,
    first_checked  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS verify_checks_checked_at_idx ON verify_checks (checked_at DESC);
CREATE INDEX IF NOT EXISTS submissions_status_idx ON submissions (status);
CREATE INDEX IF NOT EXISTS corrections_status_idx ON corrections (status);
CREATE INDEX IF NOT EXISTS interest_signups_kind_idx ON interest_signups (kind);
CREATE INDEX IF NOT EXISTS interest_signups_repo_idx ON interest_signups (repo);

-- ---- Accounts (GitHub/Google OAuth) + per-user features -------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    provider      TEXT NOT NULL,                 -- github | google | password | dev
    provider_id   TEXT NOT NULL,                 -- stable provider id (email for password)
    login         TEXT,                          -- handle (e.g. github login)
    name          TEXT,
    email         TEXT,
    avatar_url    TEXT,
    password_hash TEXT,                          -- only for provider='password'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_id)
);
-- For DBs created before password auth existed:
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

CREATE TABLE IF NOT EXISTS watchlist (
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_slug   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, agent_slug)
);

CREATE TABLE IF NOT EXISTS notification_reads (
    user_id      BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS watchlist_user_idx ON watchlist (user_id);
-- The "claim your project" feature was removed; its table is no longer created.
DROP TABLE IF EXISTS claims;
