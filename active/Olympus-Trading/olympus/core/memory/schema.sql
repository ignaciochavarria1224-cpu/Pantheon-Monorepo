-- Olympus Phase 4 — Canonical Database Schema
-- Single source of truth. database.py reads and executes this file.
-- All CREATE statements use IF NOT EXISTS — safe to run on every startup.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- ingestion_runs — records every ingest job for audit and idempotency checks
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id          TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT NOT NULL
                    CHECK (status IN ('running', 'completed', 'failed')),
    files_seen      INTEGER DEFAULT 0,
    rows_written    INTEGER DEFAULT 0,
    error_text      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- ranking_cycles — one row per completed RankingEngine cycle
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ranking_cycles (
    cycle_id            TEXT PRIMARY KEY,
    cycle_timestamp     TEXT NOT NULL,
    universe_size       INTEGER NOT NULL,
    scored_count        INTEGER NOT NULL,
    error_count         INTEGER NOT NULL,
    duration_seconds    REAL NOT NULL,
    top_longs_json      TEXT,
    top_shorts_json     TEXT,
    ingested_at         TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- cycle_rankings — individual symbol ranks within each cycle
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cycle_rankings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id        TEXT NOT NULL
                    REFERENCES ranking_cycles(cycle_id) ON DELETE CASCADE,
    cycle_timestamp TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL
                    CHECK (direction IN ('long', 'short')),
    rank            INTEGER NOT NULL,
    score           REAL NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (cycle_id, symbol, direction)
);

-- ---------------------------------------------------------------------------
-- trades — every completed paper trade
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trades (
    trade_id                TEXT PRIMARY KEY,
    position_id             TEXT NOT NULL,
    symbol                  TEXT NOT NULL,
    direction               TEXT NOT NULL
                            CHECK (direction IN ('long', 'short')),
    entry_price             REAL NOT NULL,
    exit_price              REAL NOT NULL,
    stop_price              REAL NOT NULL,
    target_price            REAL NOT NULL,
    size                    INTEGER NOT NULL,
    entry_time              TEXT NOT NULL,
    exit_time               TEXT NOT NULL,
    hold_duration_minutes   REAL NOT NULL,
    realized_pnl            REAL NOT NULL,
    r_multiple              REAL NOT NULL,
    exit_reason             TEXT NOT NULL
                            CHECK (exit_reason IN
                                ('stop', 'target', 'rotation', 'manual', 'eod_close')),
    status                  TEXT NOT NULL DEFAULT 'closed'
                            CHECK (status IN ('closed')),
    regime                  TEXT
                            CHECK (regime IN ('trend_up', 'trend_down', 'mixed', 'degraded')),
    rank_at_entry           INTEGER,
    score_at_entry          REAL,
    rank_at_exit            INTEGER,
    score_at_exit           REAL,
    entry_cycle_id          TEXT
                            REFERENCES ranking_cycles(cycle_id),
    exit_cycle_id           TEXT
                            REFERENCES ranking_cycles(cycle_id),
    ingested_at             TEXT NOT NULL,
    source_file             TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (position_id, entry_time)
);

-- ---------------------------------------------------------------------------
-- trade_features — feature snapshot at entry for each trade
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS trade_features (
    trade_id            TEXT PRIMARY KEY
                        REFERENCES trades(trade_id) ON DELETE CASCADE,
    symbol              TEXT NOT NULL,
    roc_5               REAL,
    roc_10              REAL,
    roc_20              REAL,
    acceleration        REAL,
    rvol_at_entry       REAL,
    vwap_deviation_at_entry REAL,
    range_position_at_entry REAL,
    raw_score           REAL,
    score_at_entry      REAL,
    close_at_entry      REAL,
    volume_at_entry     REAL,
    vwap_at_entry       REAL,
    atr_at_entry        REAL,
    high_20             REAL,
    low_20              REAL,
    bar_count_used      INTEGER,
    captured_at         TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- system_events — operational log for significant events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS system_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    symbol          TEXT,
    description     TEXT NOT NULL,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- apex_reports — structured reports generated by Apex (Phase 5)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS apex_reports (
    report_id               TEXT PRIMARY KEY,
    report_type             TEXT NOT NULL,
    generated_at            TEXT NOT NULL,
    period_start            TEXT,
    period_end              TEXT,
    content_json            TEXT NOT NULL,
    summary_text            TEXT,
    consumed_by_pantheon    INTEGER DEFAULT 0
                            CHECK (consumed_by_pantheon IN (0, 1)),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- pantheon_conclusions — debate outputs and judge conclusions (Phase 6)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pantheon_conclusions (
    conclusion_id           TEXT PRIMARY KEY,
    generated_at            TEXT NOT NULL,
    source_report_id        TEXT
                            REFERENCES apex_reports(report_id),
    researcher_output       TEXT,
    critic_output           TEXT,
    risk_manager_output     TEXT,
    optimizer_output        TEXT,
    judge_conclusion        TEXT NOT NULL,
    next_action             TEXT NOT NULL,
    tier                    TEXT NOT NULL
                            CHECK (tier IN
                                ('observation', 'candidate', 'promotion')),
    human_approved          INTEGER DEFAULT 0
                            CHECK (human_approved IN (0, 1)),
    approved_at             TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time);
CREATE INDEX IF NOT EXISTS idx_trades_direction ON trades(direction);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason);
CREATE INDEX IF NOT EXISTS idx_trades_entry_cycle_id ON trades(entry_cycle_id);
CREATE INDEX IF NOT EXISTS idx_trades_regime ON trades(regime);
CREATE INDEX IF NOT EXISTS idx_trades_r_multiple ON trades(r_multiple);
CREATE INDEX IF NOT EXISTS idx_trade_features_symbol ON trade_features(symbol);
CREATE INDEX IF NOT EXISTS idx_cycle_rankings_symbol_time
    ON cycle_rankings(symbol, cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_cycle_rankings_cycle_id
    ON cycle_rankings(cycle_id);
CREATE INDEX IF NOT EXISTS idx_cycle_rankings_symbol
    ON cycle_rankings(symbol);
CREATE INDEX IF NOT EXISTS idx_ranking_cycles_timestamp
    ON ranking_cycles(cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_system_events_event_time
    ON system_events(event_time);
CREATE INDEX IF NOT EXISTS idx_system_events_event_type
    ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_apex_reports_generated_at
    ON apex_reports(generated_at);
CREATE INDEX IF NOT EXISTS idx_apex_reports_type
    ON apex_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_pantheon_conclusions_tier
    ON pantheon_conclusions(tier);
CREATE INDEX IF NOT EXISTS idx_pantheon_conclusions_generated_at
    ON pantheon_conclusions(generated_at);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

CREATE VIEW IF NOT EXISTS v_trades_full AS
SELECT
    t.*,
    tf.roc_5, tf.roc_10, tf.roc_20, tf.acceleration,
    tf.rvol_at_entry, tf.vwap_deviation_at_entry, tf.range_position_at_entry,
    tf.raw_score, tf.score_at_entry AS feature_score_at_entry,
    tf.close_at_entry, tf.volume_at_entry, tf.vwap_at_entry,
    tf.atr_at_entry, tf.high_20, tf.low_20, tf.bar_count_used
FROM trades t
LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id;

CREATE VIEW IF NOT EXISTS v_trades_enriched AS
SELECT
    t.*,
    tf.symbol AS feature_symbol,
    tf.roc_5,
    tf.roc_10,
    tf.roc_20,
    tf.acceleration,
    tf.rvol_at_entry,
    tf.score_at_entry AS feature_score_at_entry,
    tf.range_position_at_entry,
    tf.vwap_deviation_at_entry,
    tf.raw_score,
    tf.close_at_entry,
    tf.volume_at_entry,
    tf.vwap_at_entry,
    tf.atr_at_entry,
    tf.high_20,
    tf.low_20,
    tf.bar_count_used,
    tf.captured_at AS feature_captured_at,
    cr.rank AS entry_rank_from_cycle_rankings,
    cr.score AS entry_score_from_cycle_rankings
FROM trades t
LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id
LEFT JOIN cycle_rankings cr
    ON cr.cycle_id = t.entry_cycle_id
   AND cr.symbol = t.symbol
   AND cr.direction = t.direction;

CREATE VIEW IF NOT EXISTS v_symbol_performance AS
SELECT
    symbol, direction,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners,
    SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) AS losers,
    ROUND(100.0 * SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)
          / COUNT(*), 1) AS win_rate_pct,
    ROUND(AVG(r_multiple), 2) AS avg_r_multiple,
    ROUND(SUM(realized_pnl), 2) AS total_pnl,
    ROUND(AVG(hold_duration_minutes), 0) AS avg_hold_minutes
FROM trades
GROUP BY symbol, direction;

CREATE VIEW IF NOT EXISTS v_exit_reason_stats AS
SELECT
    exit_reason, direction,
    COUNT(*) AS count,
    ROUND(AVG(r_multiple), 2) AS avg_r,
    ROUND(AVG(hold_duration_minutes), 0) AS avg_hold_minutes,
    ROUND(SUM(realized_pnl), 2) AS total_pnl,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners
FROM trades
GROUP BY exit_reason, direction;

CREATE VIEW IF NOT EXISTS v_rolling_7day AS
SELECT
    DATE(exit_time) AS trade_date,
    COUNT(*) AS trades,
    ROUND(AVG(r_multiple), 2) AS avg_r,
    ROUND(SUM(realized_pnl), 2) AS daily_pnl,
    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners
FROM trades
WHERE exit_time >= datetime('now', '-7 days')
GROUP BY DATE(exit_time)
ORDER BY trade_date DESC;

CREATE VIEW IF NOT EXISTS v_feature_buckets AS
SELECT
    CASE
        WHEN tf.roc_20 > 5  THEN 'strong_momentum'
        WHEN tf.roc_20 > 0  THEN 'mild_momentum'
        WHEN tf.roc_20 > -5 THEN 'mild_weakness'
        ELSE                     'strong_weakness'
    END AS momentum_bucket,
    t.direction,
    COUNT(*) AS trades,
    ROUND(AVG(t.r_multiple), 2) AS avg_r,
    ROUND(AVG(t.realized_pnl), 2) AS avg_pnl,
    SUM(CASE WHEN t.realized_pnl > 0 THEN 1 ELSE 0 END) AS winners
FROM trades t
JOIN trade_features tf ON t.trade_id = tf.trade_id
WHERE tf.roc_20 IS NOT NULL
GROUP BY momentum_bucket, t.direction;
