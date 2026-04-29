"""
SQLite database connection and schema management for Olympus Phase 4.
Single entry point for all database access. All timestamps written as UTC ISO 8601.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)

# schema.sql lives alongside this file
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_REFRESHABLE_VIEWS = (
    "v_trades_full",
    "v_trades_enriched",
    "v_symbol_performance",
    "v_exit_reason_stats",
    "v_rolling_7day",
    "v_feature_buckets",
)


class Database:
    """
    Manages a single SQLite connection with WAL mode and foreign keys enabled.

    Usage:
        db = Database(Path("data/olympus.db"))
        db.initialize()          # idempotent — safe on every startup
        rows = db.query("SELECT * FROM trades WHERE symbol = ?", ("AAPL",))
        db.close()

    Thread-safety: uses a lock around connection access. Safe to share across
    threads for Phase 4's single-writer model.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        logger.debug("Database created (path=%s)", db_path)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """
        Return the database connection, creating it on first call.
        Idempotent — subsequent calls return the existing connection.

        Connection is configured with:
          - WAL journal mode (set here and in schema.sql)
          - foreign_keys = ON
          - row_factory = sqlite3.Row (enables dict-style access)
          - detect_types = PARSE_DECLTYPES
        """
        with self._lock:
            if self._conn is None:
                self._conn = sqlite3.connect(
                    str(self._db_path),
                    check_same_thread=False,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode = WAL")
                self._conn.execute("PRAGMA foreign_keys = ON")
                logger.debug("SQLite connection opened (path=%s)", self._db_path)
            return self._conn

    def initialize(self) -> None:
        """
        Read schema.sql and execute it against the database.
        Idempotent — CREATE TABLE/INDEX IF NOT EXISTS everywhere.
        Safe to call on every startup.
        """
        schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        conn = self.connect()

        # Execute each non-empty statement individually to avoid executescript()
        # quirks (executescript does implicit COMMIT and disables isolation level).
        with self._lock:
            statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
            view_statements = [
                stmt for stmt in statements
                if "CREATE VIEW IF NOT EXISTS" in stmt.upper()
            ]
            base_statements = [
                stmt for stmt in statements
                if "CREATE VIEW IF NOT EXISTS" not in stmt.upper()
            ]
            for stmt in base_statements:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    # IF NOT EXISTS guards handle most cases; log unexpected errors
                    logger.warning("Schema statement warning: %s | stmt=%.60s", exc, stmt)
            for view_name in _REFRESHABLE_VIEWS:
                conn.execute(f"DROP VIEW IF EXISTS {view_name}")
            for stmt in view_statements:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    logger.warning("View refresh warning: %s | stmt=%.60s", exc, stmt)
            conn.commit()

        # Report confirmed objects
        tables = self.query(
            "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
        )
        indexes = self.query(
            "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='index'"
        )
        views = self.query(
            "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='view'"
        )
        table_count = tables[0]["n"] if tables else 0
        index_count = indexes[0]["n"] if indexes else 0
        view_count = views[0]["n"] if views else 0
        logger.info(
            "Database initialized — %d tables, %d indexes, %d views (path=%s)",
            table_count, index_count, view_count, self._db_path,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a single SQL statement and commit.
        Returns the cursor (useful for rowcount / lastrowid).
        Logs at DEBUG level.
        """
        conn = self.connect()
        logger.debug("execute: %.80s", sql.strip())
        with self._lock:
            cur = conn.execute(sql, params)
            conn.commit()
        return cur

    def executemany(self, sql: str, params_list: list) -> int:
        """
        Execute a statement for each item in params_list in a single transaction.
        Returns the number of rows affected.
        """
        if not params_list:
            return 0
        conn = self.connect()
        logger.debug("executemany (%d rows): %.80s", len(params_list), sql.strip())
        with self._lock:
            cur = conn.executemany(sql, params_list)
            conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT and return all rows as a list of dicts."""
        conn = self.connect()
        logger.debug("query: %.80s", sql.strip())
        with self._lock:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute a SELECT returning at most one row as a dict, or None."""
        conn = self.connect()
        with self._lock:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                logger.debug("SQLite connection closed (path=%s)", self._db_path)
