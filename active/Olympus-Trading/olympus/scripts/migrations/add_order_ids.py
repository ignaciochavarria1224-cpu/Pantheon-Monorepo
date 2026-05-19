"""
add_order_ids.py — Part A schema migration.

Adds two nullable columns to the `trades` table:
    entry_order_id TEXT
    exit_order_id  TEXT

These carry the Alpaca order IDs of the confirmed entry/exit fills, so new
trades have the order-to-trade linkage that future reconciliation (Part B)
needs. Historical rows keep NULL — this migration never modifies row data.

Idempotency
-----------
Idempotent by INSPECTION, not by exception-swallowing: it reads
PRAGMA table_info(trades) and only issues ALTER TABLE for a column that is
genuinely absent. Safe to run any number of times. (Silent try/except around
the ALTER is deliberately NOT used — masked failures are the class of bug
this whole audit exists to remove.)

Path discipline
---------------
The target database is resolved via config.settings.load_settings().DB_PATH —
never a hardcoded relative path.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/migrations/add_order_ids.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Bootstrap: make `olympus/` importable regardless of CWD.
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

from config.settings import load_settings  # noqa: E402

# Columns this migration ensures exist on `trades`. (name, column_type)
NEW_COLUMNS: list[tuple[str, str]] = [
    ("entry_order_id", "TEXT"),
    ("exit_order_id", "TEXT"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names currently on `table`."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(db_path: Path) -> int:
    """
    Apply the migration to db_path. Returns 0 on success, 1 on failure.
    """
    print(f"add_order_ids migration — target: {db_path}")

    if not db_path.exists():
        print(f"  ERROR: database file does not exist: {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    try:
        existing = _existing_columns(conn, "trades")
        if not existing:
            print("  ERROR: 'trades' table not found in this database")
            return 1

        for name, col_type in NEW_COLUMNS:
            if name in existing:
                print(f"  skip   : column '{name}' already present")
                continue
            # ALTER TABLE ADD COLUMN with no default is a fast metadata-only
            # change; existing rows receive NULL. No row data is touched.
            conn.execute(f"ALTER TABLE trades ADD COLUMN {name} {col_type}")
            conn.commit()
            print(f"  added  : column '{name}' {col_type}")

        final = _existing_columns(conn, "trades")
        missing = [name for name, _ in NEW_COLUMNS if name not in final]
        if missing:
            print(f"  FAILED : columns still missing after migration: {missing}")
            return 1

        print("  result : OK — entry_order_id and exit_order_id present on 'trades'")
        return 0
    finally:
        conn.close()


def main() -> int:
    db_path = load_settings().DB_PATH
    return migrate(db_path)


if __name__ == "__main__":
    sys.exit(main())
