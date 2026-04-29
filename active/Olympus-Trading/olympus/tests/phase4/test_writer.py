"""
Phase 4 — MemoryWriter tests.
Verifies live writes from the paper trading loop hit the correct tables.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.memory.database import Database
from core.memory.writer import MemoryWriter
from core.models import BarFeatures, TradeRecord, RankedSymbol, RankedUniverse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mem_db():
    db = Database(Path(":memory:"))
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def writer(mem_db):
    return MemoryWriter(mem_db, allow_network_fallback=False)


def _make_trade(symbol="AAPL", exit_reason="target"):
    now = datetime.now(timezone.utc)
    return TradeRecord(
        trade_id=str(uuid.uuid4()),
        position_id=str(uuid.uuid4()),
        symbol=symbol,
        direction="long",
        entry_price=150.0,
        exit_price=155.0,
        stop_price=148.0,
        target_price=156.0,
        size=10,
        entry_time=now,
        exit_time=now,
        hold_duration_minutes=90.0,
        realized_pnl=50.0,
        r_multiple=2.5,
        exit_reason=exit_reason,
        rank_at_entry=1,
        score_at_entry=82.5,
        rank_at_exit=2,
        score_at_exit=79.0,
        status="closed",
    )


def _make_features(symbol="AAPL"):
    return BarFeatures(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        close=150.0,
        volume=1_000_000.0,
        roc_5=1.2,
        roc_10=2.5,
        roc_20=4.0,
        acceleration=0.3,
        rvol=1.8,
        vwap_deviation=0.5,
        range_position=0.75,
        raw_score=0.68,
        normalized_score=82.5,
    )


def _make_cycle():
    now = datetime.now(timezone.utc)
    rs_long = RankedSymbol(
        symbol="AAPL", score=82.5, direction="long", rank=1,
        features=_make_features("AAPL"), timestamp=now,
    )
    rs_short = RankedSymbol(
        symbol="NFLX", score=22.0, direction="short", rank=1,
        features=_make_features("NFLX"), timestamp=now,
    )
    return RankedUniverse(
        cycle_id=str(uuid.uuid4()),
        timestamp=now,
        longs=[rs_long],
        shorts=[rs_short],
        universe_size=185,
        scored_count=180,
        error_count=5,
        duration_seconds=11.3,
    )


def _insert_ranked_cycle(mem_db, cycle_ts: datetime):
    cycle_id = str(uuid.uuid4())
    cycle_ts_iso = cycle_ts.isoformat()
    mem_db.execute(
        """
        INSERT INTO ranking_cycles (
            cycle_id, cycle_timestamp, universe_size, scored_count,
            error_count, duration_seconds, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (cycle_id, cycle_ts_iso, 185, 180, 5, 10.0, cycle_ts_iso),
    )
    mem_db.executemany(
        """
        INSERT INTO cycle_rankings (cycle_id, cycle_timestamp, symbol, direction, rank, score)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (cycle_id, cycle_ts_iso, "AAPL", "long", 1, 95.0),
            (cycle_id, cycle_ts_iso, "MSFT", "long", 2, 94.0),
            (cycle_id, cycle_ts_iso, "NVDA", "long", 3, 93.0),
            (cycle_id, cycle_ts_iso, "NFLX", "short", 1, 40.0),
            (cycle_id, cycle_ts_iso, "TSLA", "short", 2, 35.0),
            (cycle_id, cycle_ts_iso, "META", "short", 3, 30.0),
        ],
    )
    return cycle_id


# ---------------------------------------------------------------------------
# write_trade tests
# ---------------------------------------------------------------------------


def test_write_trade_inserts_row(writer, mem_db):
    record = _make_trade()
    ok = writer.write_trade(record)
    assert ok is True
    row = mem_db.query_one("SELECT * FROM trades WHERE trade_id = ?", (record.trade_id,))
    assert row is not None
    assert row["symbol"] == "AAPL"
    assert row["r_multiple"] == pytest.approx(2.5)
    assert row["regime"] is None


def test_write_trade_creates_stub_features(writer, mem_db):
    record = _make_trade()
    writer.write_trade(record)
    row = mem_db.query_one(
        "SELECT * FROM trade_features WHERE trade_id = ?", (record.trade_id,)
    )
    assert row is not None
    assert row["score_at_entry"] == pytest.approx(82.5)


def test_write_trade_with_features_populates_columns(writer, mem_db):
    record = _make_trade()
    features = _make_features()
    writer.write_trade(record, features=features)
    row = mem_db.query_one(
        "SELECT * FROM trade_features WHERE trade_id = ?", (record.trade_id,)
    )
    assert row is not None
    assert row["roc_5"] == pytest.approx(1.2)
    assert row["score_at_entry"] == pytest.approx(82.5)
    assert row["rvol_at_entry"] == pytest.approx(1.8)


def test_write_trade_is_idempotent(writer, mem_db):
    record = _make_trade()
    writer.write_trade(record)
    writer.write_trade(record)  # second call — INSERT OR IGNORE
    count = mem_db.query_one(
        "SELECT COUNT(*) AS n FROM trades WHERE trade_id = ?", (record.trade_id,)
    )
    assert count["n"] == 1


def test_write_trade_links_entry_cycle_and_regime(writer, mem_db):
    record = _make_trade()
    cycle_id = _insert_ranked_cycle(mem_db, record.entry_time)

    ok = writer.write_trade(record)

    assert ok is True
    row = mem_db.query_one(
        "SELECT entry_cycle_id, regime FROM trades WHERE trade_id = ?",
        (record.trade_id,),
    )
    assert row is not None
    assert row["entry_cycle_id"] == cycle_id
    assert row["regime"] == "trend_up"


def test_write_trade_features_via_record_field(writer, mem_db):
    """Regression: features attached to TradeRecord.features flow through to DB columns."""
    features = _make_features()
    record = _make_trade()
    record.features = features  # simulate the path: Position.features → TradeRecord.features
    writer.write_trade(record, features=record.features)
    row = mem_db.query_one(
        "SELECT roc_5, roc_10, roc_20, acceleration, rvol_at_entry, vwap_deviation_at_entry, "
        "range_position_at_entry, raw_score, score_at_entry "
        "FROM trade_features WHERE trade_id = ?",
        (record.trade_id,),
    )
    assert row is not None
    assert row["roc_5"] is not None, "roc_5 must not be NULL after fix"
    assert row["roc_5"] == pytest.approx(1.2)
    assert row["score_at_entry"] == pytest.approx(82.5)


def test_write_trade_never_raises_on_db_failure(mem_db):
    """MemoryWriter must return False (not raise) when the DB call fails."""
    writer = MemoryWriter(mem_db, allow_network_fallback=False)
    # Close the connection so all DB calls fail
    mem_db.close()

    record = _make_trade()
    result = writer.write_trade(record)
    assert result is False


# ---------------------------------------------------------------------------
# write_cycle tests
# ---------------------------------------------------------------------------


def test_write_cycle_inserts_ranking_cycle(writer, mem_db):
    cycle = _make_cycle()
    ok = writer.write_cycle(cycle)
    assert ok is True
    row = mem_db.query_one(
        "SELECT * FROM ranking_cycles WHERE cycle_id = ?", (cycle.cycle_id,)
    )
    assert row is not None
    assert row["universe_size"] == 185


def test_write_cycle_inserts_individual_rankings(writer, mem_db):
    cycle = _make_cycle()
    writer.write_cycle(cycle)
    rows = mem_db.query(
        "SELECT symbol FROM cycle_rankings WHERE cycle_id = ?", (cycle.cycle_id,)
    )
    symbols = {r["symbol"] for r in rows}
    assert "AAPL" in symbols
    assert "NFLX" in symbols


# ---------------------------------------------------------------------------
# write_event tests
# ---------------------------------------------------------------------------


def test_write_event_inserts_row(writer, mem_db):
    ok = writer.write_event("cycle_start", "Ranking cycle started", symbol=None)
    assert ok is True
    rows = mem_db.query("SELECT * FROM system_events WHERE event_type = 'cycle_start'")
    assert len(rows) == 1
    assert rows[0]["description"] == "Ranking cycle started"


def test_write_event_with_metadata(writer, mem_db):
    ok = writer.write_event(
        "trade_exit", "Target hit", symbol="AAPL", metadata={"r": 2.5}
    )
    assert ok is True
    row = mem_db.query_one("SELECT * FROM system_events WHERE symbol = 'AAPL'")
    assert row is not None
    assert '"r": 2.5' in row["metadata_json"]
