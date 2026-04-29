"""
Phase 4 — ingestion tests.
Verifies Ingestion correctly maps JSON files to DB rows and is idempotent.
"""

import json
import uuid
from pathlib import Path

import pytest

from core.memory.database import Database
from core.memory.ingestion import Ingestion


@pytest.fixture
def mem_db():
    db = Database(Path(":memory:"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def trade_data():
    return {
        "trade_id": str(uuid.uuid4()),
        "position_id": str(uuid.uuid4()),
        "symbol": "AAPL",
        "direction": "long",
        "entry_price": "150.00",
        "exit_price": "155.00",
        "stop_price": "148.00",
        "target_price": "156.00",
        "size": "10",
        "entry_time": "2025-01-15T14:30:00+00:00",
        "exit_time": "2025-01-15T16:00:00+00:00",
        "hold_duration_minutes": "90.0",
        "realized_pnl": "50.00",
        "r_multiple": "2.5",
        "exit_reason": "target",
        "status": "closed",
        "rank_at_entry": 1,
        "score_at_entry": 82.5,
        "rank_at_exit": 2,
        "score_at_exit": 79.0,
    }


@pytest.fixture
def ranking_data():
    cycle_id = str(uuid.uuid4())
    return {
        "cycle_id": cycle_id,
        "timestamp": "2025-01-15T14:00:00+00:00",
        "universe_size": 185,
        "scored_count": 180,
        "error_count": 5,
        "duration_seconds": 12.5,
        "longs": [
            {"symbol": "AAPL", "rank": 1, "score": 82.5, "direction": "long"},
            {"symbol": "MSFT", "rank": 2, "score": 78.0, "direction": "long"},
        ],
        "shorts": [
            {"symbol": "NFLX", "rank": 1, "score": 22.0, "direction": "short"},
        ],
    }


def _write_trade_file(tmp_path: Path, data: dict) -> Path:
    fp = tmp_path / f"trade_{data['trade_id']}.json"
    fp.write_text(json.dumps(data), encoding="utf-8")
    return fp


def _write_ranking_file(tmp_path: Path, data: dict) -> Path:
    fp = tmp_path / f"ranking_{data['cycle_id']}.json"
    fp.write_text(json.dumps(data), encoding="utf-8")
    return fp


def test_ingest_trade_fields_mapped(mem_db, tmp_path, trade_data):
    """All fields from the JSON must appear correctly in the trades table."""
    ranking = {
        "cycle_id": str(uuid.uuid4()),
        "timestamp": "2025-01-15T14:00:00+00:00",
        "universe_size": 185,
        "scored_count": 180,
        "error_count": 5,
        "duration_seconds": 12.5,
        "longs": [
            {"symbol": "AAPL", "rank": 1, "score": 95.0, "direction": "long"},
            {"symbol": "MSFT", "rank": 2, "score": 94.0, "direction": "long"},
            {"symbol": "NVDA", "rank": 3, "score": 93.0, "direction": "long"},
        ],
        "shorts": [
            {"symbol": "NFLX", "rank": 1, "score": 40.0, "direction": "short"},
            {"symbol": "TSLA", "rank": 2, "score": 35.0, "direction": "short"},
            {"symbol": "META", "rank": 3, "score": 30.0, "direction": "short"},
        ],
    }
    _write_ranking_file(tmp_path, ranking)
    Ingestion(mem_db, tmp_path, tmp_path).ingest_rankings()
    _write_trade_file(tmp_path, trade_data)
    ingestion = Ingestion(mem_db, tmp_path, tmp_path)
    result = ingestion.ingest_trades()

    assert result.status == "completed"
    assert result.rows_written == 1

    row = mem_db.query_one(
        "SELECT * FROM trades WHERE trade_id = ?", (trade_data["trade_id"],)
    )
    assert row is not None
    assert row["symbol"] == "AAPL"
    assert row["direction"] == "long"
    assert row["exit_reason"] == "target"
    assert row["r_multiple"] == pytest.approx(2.5)
    assert row["rank_at_entry"] == 1
    assert row["entry_cycle_id"] == ranking["cycle_id"]
    assert row["regime"] == "trend_up"


def test_ingest_trade_creates_stub_features(mem_db, tmp_path, trade_data):
    """Ingesting a trade must also create a stub trade_features row."""
    _write_trade_file(tmp_path, trade_data)
    Ingestion(mem_db, tmp_path, tmp_path).ingest_trades()

    row = mem_db.query_one(
        "SELECT * FROM trade_features WHERE trade_id = ?", (trade_data["trade_id"],)
    )
    assert row is not None
    assert row["symbol"] == "AAPL"
    assert "rvol_at_entry" in row


def test_ingest_trade_is_idempotent(mem_db, tmp_path, trade_data):
    """Running ingest_trades() twice must not duplicate rows."""
    _write_trade_file(tmp_path, trade_data)
    ingestion = Ingestion(mem_db, tmp_path, tmp_path)
    ingestion.ingest_trades()
    ingestion.ingest_trades()

    count = mem_db.query_one(
        "SELECT COUNT(*) AS n FROM trades WHERE trade_id = ?",
        (trade_data["trade_id"],),
    )
    assert count["n"] == 1


def test_ingest_ranking_fields_mapped(mem_db, tmp_path, ranking_data):
    """Ranking cycle fields must be stored correctly."""
    _write_ranking_file(tmp_path, ranking_data)
    result = Ingestion(mem_db, tmp_path, tmp_path).ingest_rankings()

    assert result.status == "completed"
    assert result.rows_written == 1

    row = mem_db.query_one(
        "SELECT * FROM ranking_cycles WHERE cycle_id = ?",
        (ranking_data["cycle_id"],),
    )
    assert row is not None
    assert row["universe_size"] == 185
    assert row["scored_count"] == 180


def test_ingest_ranking_individual_rows(mem_db, tmp_path, ranking_data):
    """Each symbol in longs/shorts gets a cycle_rankings row."""
    _write_ranking_file(tmp_path, ranking_data)
    Ingestion(mem_db, tmp_path, tmp_path).ingest_rankings()

    rows = mem_db.query(
        "SELECT * FROM cycle_rankings WHERE cycle_id = ? ORDER BY rank",
        (ranking_data["cycle_id"],),
    )
    symbols = {r["symbol"] for r in rows}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "NFLX" in symbols


def test_ingest_ranking_is_idempotent(mem_db, tmp_path, ranking_data):
    """Running ingest_rankings() twice must not duplicate ranking_cycles rows."""
    _write_ranking_file(tmp_path, ranking_data)
    ingestion = Ingestion(mem_db, tmp_path, tmp_path)
    ingestion.ingest_rankings()
    ingestion.ingest_rankings()

    count = mem_db.query_one(
        "SELECT COUNT(*) AS n FROM ranking_cycles WHERE cycle_id = ?",
        (ranking_data["cycle_id"],),
    )
    assert count["n"] == 1


def test_ingestion_runs_row_created(mem_db, tmp_path, trade_data):
    """A completed ingestion_runs row must exist after ingest_trades()."""
    _write_trade_file(tmp_path, trade_data)
    result = Ingestion(mem_db, tmp_path, tmp_path).ingest_trades()

    row = mem_db.query_one(
        "SELECT * FROM ingestion_runs WHERE run_id = ?", (result.run_id,)
    )
    assert row is not None
    assert row["status"] == "completed"
    assert row["files_seen"] == 1
    assert row["rows_written"] == 1


def test_malformed_file_skipped_gracefully(mem_db, tmp_path, trade_data):
    """A malformed JSON file must be skipped — valid files in the same batch still ingest."""
    # Write one valid file
    _write_trade_file(tmp_path, trade_data)
    # Write one malformed file with the trade_ prefix so it's picked up
    bad = tmp_path / "trade_bad-file.json"
    bad.write_text("{not valid json", encoding="utf-8")

    result = Ingestion(mem_db, tmp_path, tmp_path).ingest_trades()

    # Overall status is still completed
    assert result.status == "completed"
    # Valid trade was still written
    assert result.rows_written == 1


def test_empty_directory_produces_zero_rows(mem_db, tmp_path):
    """Ingesting an empty directory must succeed with zero rows."""
    result = Ingestion(mem_db, tmp_path, tmp_path).ingest_trades()
    assert result.status == "completed"
    assert result.files_seen == 0
    assert result.rows_written == 0
