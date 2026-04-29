-- db/schema.sql
-- Run once to create Meridian tables in Black Book's Neon database

CREATE TABLE IF NOT EXISTS meridian_questions (
    id             SERIAL PRIMARY KEY,
    generated_date TEXT NOT NULL,
    questions      JSONB NOT NULL,
    pushed_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meridian_outputs (
    id               SERIAL PRIMARY KEY,
    framework_title  TEXT NOT NULL,
    framework_body   TEXT NOT NULL,
    source_entry_ids TEXT,
    entry_date_range TEXT,
    fitness          REAL,
    domains          TEXT,
    pushed_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meridian_insights (
    id             SERIAL PRIMARY KEY,
    insight_type   TEXT NOT NULL,
    insight_body   TEXT NOT NULL,
    generated_date TEXT NOT NULL,
    pushed_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meridian_notes (
    id          SERIAL PRIMARY KEY,
    note_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    stage       TEXT NOT NULL,
    fitness     REAL,
    maturity    INTEGER,
    domains     TEXT,
    body        TEXT,
    cycle       INTEGER,
    synced_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meridian_jobs (
    id             SERIAL PRIMARY KEY,
    status         TEXT NOT NULL DEFAULT 'pending',
    requested_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at     TEXT,
    completed_at   TEXT,
    result         TEXT
);

-- Brain theme hub documents (one row per theme + one INDEX row)
-- theme = domain slug (e.g. "friendship") or "INDEX"
-- body  = full markdown of the theme document
CREATE TABLE IF NOT EXISTS meridian_brain (
    id          SERIAL PRIMARY KEY,
    theme       TEXT NOT NULL,
    body        TEXT NOT NULL,
    cycle       INTEGER,
    synced_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
