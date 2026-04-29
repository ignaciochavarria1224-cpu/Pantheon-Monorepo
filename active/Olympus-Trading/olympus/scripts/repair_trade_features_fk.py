"""
One-time repair script: rebuild trade_features with the correct foreign key.

Problem: trade_features in olympus.db was created with
    REFERENCES "trades_old"(trade_id) ON DELETE CASCADE
which points to a table that does not exist.

Fix: recreate trade_features with the canonical FK:
    REFERENCES trades(trade_id) ON DELETE CASCADE

Everything is done inside a single transaction. Any error triggers a full
rollback, leaving the database exactly as it was found.

Usage:
    python scripts/repair_trade_features_fk.py [path/to/olympus.db]

Default db path: data/olympus.db  (relative to the olympus/ working directory)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def step(msg: str) -> None:
    print(f"  {msg}")


def abort(msg: str) -> None:
    print(f"\nABORTED: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# SQL definitions — sourced from schema.sql and verified against live DB
# ---------------------------------------------------------------------------

CREATE_TRADE_FEATURES_NEW = """
CREATE TABLE trade_features_new (
    trade_id            TEXT PRIMARY KEY
                        REFERENCES trades(trade_id) ON DELETE CASCADE,
    symbol              TEXT NOT NULL,
    roc_5               REAL,
    roc_10              REAL,
    roc_20              REAL,
    acceleration        REAL,
    rvol                REAL,
    vwap_deviation      REAL,
    range_position      REAL,
    raw_score           REAL,
    normalized_score    REAL,
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
)
"""

COPY_ROWS = """
INSERT INTO trade_features_new SELECT * FROM trade_features
"""

DROP_OLD = "DROP TABLE trade_features"

RENAME_NEW = "ALTER TABLE trade_features_new RENAME TO trade_features"

RECREATE_INDEX = (
    "CREATE INDEX idx_trade_features_symbol ON trade_features(symbol)"
)

# Views that JOIN trade_features and must be dropped before the rename and
# recreated after. Definitions taken verbatim from schema.sql.
VIEWS_REFERENCING_TRADE_FEATURES = [
    (
        "v_trades_full",
        """CREATE VIEW v_trades_full AS
SELECT
    t.*,
    tf.roc_5, tf.roc_10, tf.roc_20, tf.acceleration,
    tf.rvol, tf.vwap_deviation, tf.range_position,
    tf.raw_score, tf.normalized_score,
    tf.close_at_entry, tf.volume_at_entry, tf.vwap_at_entry,
    tf.atr_at_entry, tf.high_20, tf.low_20, tf.bar_count_used
FROM trades t
LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id""",
    ),
    (
        "v_feature_buckets",
        """CREATE VIEW v_feature_buckets AS
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
GROUP BY momentum_bucket, t.direction""",
    ),
]


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def check_current_fk(conn: sqlite3.Connection) -> str:
    """Return the current CREATE TABLE sql for trade_features."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='trade_features'"
    ).fetchone()
    if row is None:
        abort("trade_features table does not exist — nothing to repair.")
    return row[0]


def fk_points_to_trades_old(create_sql: str) -> bool:
    return "trades_old" in create_sql


def fk_points_to_trades(create_sql: str) -> bool:
    # Must reference trades without the _old suffix
    import re
    return bool(re.search(r'REFERENCES\s+"?trades"?\s*\(', create_sql))


# ---------------------------------------------------------------------------
# Main repair
# ---------------------------------------------------------------------------

def repair(db_path: Path) -> None:
    print(f"\nOlympus trade_features FK repair")
    print(f"Database : {db_path.resolve()}")
    print()

    if not db_path.exists():
        abort(f"Database file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))

    try:
        # --- Pre-flight ---
        step("Checking current trade_features definition...")
        current_sql = check_current_fk(conn)

        if not fk_points_to_trades_old(current_sql):
            if fk_points_to_trades(current_sql):
                print("\nNothing to do: trade_features already references 'trades'. Exiting.")
                conn.close()
                return
            else:
                print(f"\nCurrent CREATE SQL:\n{current_sql}\n")
                abort(
                    "trade_features does not reference 'trades_old' or 'trades' — "
                    "unexpected schema. Inspect manually before running this script."
                )

        print(f"    FK currently points to 'trades_old' — repair required.")

        row_count = conn.execute("SELECT COUNT(*) FROM trade_features").fetchone()[0]
        step(f"Rows to migrate: {row_count}")

        # --- Begin single transaction ---
        step("Disabling foreign key enforcement for migration...")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        step("Creating trade_features_new with correct FK (REFERENCES trades)...")
        conn.execute(CREATE_TRADE_FEATURES_NEW)

        step(f"Copying {row_count} row(s) into trade_features_new...")
        conn.execute(COPY_ROWS)

        copied = conn.execute("SELECT COUNT(*) FROM trade_features_new").fetchone()[0]
        if copied != row_count:
            raise RuntimeError(
                f"Row count mismatch after copy: expected {row_count}, got {copied}"
            )

        for view_name, _ in VIEWS_REFERENCING_TRADE_FEATURES:
            step(f"Dropping view {view_name} (references trade_features)...")
            conn.execute(f"DROP VIEW IF EXISTS {view_name}")

        step("Dropping old trade_features table...")
        conn.execute(DROP_OLD)

        step("Renaming trade_features_new -> trade_features...")
        conn.execute(RENAME_NEW)

        step("Recreating idx_trade_features_symbol index...")
        conn.execute(RECREATE_INDEX)

        for view_name, view_sql in VIEWS_REFERENCING_TRADE_FEATURES:
            step(f"Recreating view {view_name}...")
            conn.execute(view_sql)

        step("Committing transaction...")
        conn.execute("COMMIT")

        step("Re-enabling foreign key enforcement...")
        conn.execute("PRAGMA foreign_keys = ON")

        # --- Verification ---
        print()
        print("Verifying repair...")
        new_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='trade_features'"
        ).fetchone()

        if new_sql is None:
            abort("trade_features is missing after repair — something went wrong.")

        new_create = new_sql[0]

        if "trades_old" in new_create:
            abort("trade_features still references 'trades_old' — repair failed.")

        if not fk_points_to_trades(new_create):
            abort("trade_features does not reference 'trades' — repair incomplete.")

        index_row = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_trade_features_symbol'"
        ).fetchone()
        if index_row is None:
            abort("idx_trade_features_symbol index is missing after repair.")

        for view_name, _ in VIEWS_REFERENCING_TRADE_FEATURES:
            view_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' AND name=?",
                (view_name,),
            ).fetchone()
            if view_row is None:
                abort(f"View {view_name} is missing after repair.")

        final_count = conn.execute("SELECT COUNT(*) FROM trade_features").fetchone()[0]

        print(f"  trade_features FK now references: trades  (correct)")
        print(f"  idx_trade_features_symbol         present (correct)")
        print(f"  Row count preserved:              {final_count} / {row_count}")
        for view_name, _ in VIEWS_REFERENCING_TRADE_FEATURES:
            print(f"  {view_name:<35} present (correct)")
        print()
        print("Repair complete. trade_features is healthy.")

    except Exception as exc:
        print(f"\nERROR: {exc}")
        print("Rolling back — database is unchanged.")
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()
        sys.exit(1)

    conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        # Default: relative to the olympus/ working directory
        path = Path(__file__).parent.parent / "data" / "olympus.db"

    repair(path)
