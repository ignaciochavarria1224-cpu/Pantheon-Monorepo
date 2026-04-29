"""
Phase 4 — schema tests.
Verifies that database.py + schema.sql produce the expected structure.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from core.memory.database import Database


@pytest.fixture
def mem_db():
    db = Database(Path(":memory:"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def file_db(tmp_path):
    """Needed for WAL mode check — WAL requires a real file."""
    db = Database(tmp_path / "test.db")
    db.initialize()
    yield db
    db.close()


def test_expected_tables_exist(mem_db):
    rows = mem_db.query(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {r["name"] for r in rows}
    expected = {
        "ingestion_runs",
        "ranking_cycles",
        "cycle_rankings",
        "trades",
        "trade_features",
        "system_events",
        "apex_reports",
        "pantheon_conclusions",
    }
    assert expected.issubset(names), f"Missing tables: {expected - names}"


def test_expected_views_exist(mem_db):
    rows = mem_db.query(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    )
    names = {r["name"] for r in rows}
    expected = {
        "v_trades_full",
        "v_trades_enriched",
        "v_symbol_performance",
        "v_exit_reason_stats",
        "v_rolling_7day",
        "v_feature_buckets",
    }
    assert expected.issubset(names), f"Missing views: {expected - names}"


def test_expected_indexes_exist(mem_db):
    rows = mem_db.query(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    )
    names = {r["name"] for r in rows}
    expected_prefixes = {
        "idx_trades_symbol",
        "idx_trades_entry_time",
        "idx_trades_exit_time",
        "idx_trades_direction",
        "idx_trades_exit_reason",
        "idx_trades_r_multiple",
        "idx_cycle_rankings_symbol",
        "idx_cycle_rankings_cycle_id",
        "idx_ranking_cycles_timestamp",
        "idx_system_events_event_time",
        "idx_apex_reports_generated_at",
        "idx_pantheon_conclusions_tier",
    }
    assert expected_prefixes.issubset(names), f"Missing indexes: {expected_prefixes - names}"


def test_initialize_is_idempotent(tmp_path):
    """Calling initialize() twice must not raise and must produce same object counts."""
    db = Database(tmp_path / "idem.db")
    db.initialize()
    first = db.query("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'")[0]["n"]

    db.initialize()  # second call — must be idempotent
    second = db.query("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'")[0]["n"]

    assert first == second
    db.close()


def test_foreign_keys_enabled(mem_db):
    """Inserting a cycle_rankings row referencing a nonexistent cycle_id must fail."""
    with pytest.raises(sqlite3.IntegrityError):
        mem_db.execute(
            """
            INSERT INTO cycle_rankings
                (cycle_id, cycle_timestamp, symbol, direction, rank, score)
            VALUES ('nonexistent-id', '2025-01-01T00:00:00+00:00', 'AAPL', 'long', 1, 75.0)
            """
        )


def test_trade_schema_has_regime_and_self_describing_feature_columns(mem_db):
    trade_columns = {
        row["name"] for row in mem_db.query("PRAGMA table_info(trades)")
    }
    feature_columns = {
        row["name"] for row in mem_db.query("PRAGMA table_info(trade_features)")
    }

    assert "regime" in trade_columns
    assert "rvol_at_entry" in feature_columns
    assert "score_at_entry" in feature_columns
    assert "range_position_at_entry" in feature_columns
    assert "vwap_deviation_at_entry" in feature_columns


def test_wal_journal_mode(file_db):
    """Journal mode should be WAL when using a real file database."""
    rows = file_db.query("PRAGMA journal_mode")
    mode = rows[0]["journal_mode"] if rows else ""
    assert mode == "wal", f"Expected WAL, got: {mode}"
