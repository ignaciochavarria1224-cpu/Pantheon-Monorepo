"""
Phase 4 — Open positions lifecycle tests.
Verifies entry, exit, and startup seeding behavior for open_positions table.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.memory.database import Database
from core.memory.repository import Repository
from core.memory.writer import MemoryAwarePaperTradingLoop, MemoryWriter
from core.models import BarFeatures, Direction, Position, TradeRecord, TradeStatus
from core.trading.loop import PaperTradingLoop
from core.trading.manager import PositionManager
from run_live import _seed_open_positions


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
def repo(mem_db):
    return Repository(mem_db)


def _make_position(with_features: bool = False) -> Position:
    feats = None
    if with_features:
        feats = BarFeatures(
            symbol="AAPL",
            timestamp=datetime.now(timezone.utc),
            close=150.0, volume=1_000_000.0,
            roc_5=0.01, roc_10=0.02, roc_20=0.03,
            acceleration=-0.01,
            rvol=1.2, vwap_deviation=0.005, range_position=0.7,
            raw_score=85.0, normalized_score=85.0,
        )
    return Position(
        position_id=f"pos_{uuid.uuid4().hex[:8]}",
        symbol="AAPL",
        direction=Direction.LONG,
        entry_price=150.0,
        stop_price=145.0,
        target_price=160.0,
        size=100,
        entry_time=datetime.now(timezone.utc),
        rank_at_entry=1,
        score_at_entry=85.0,
        current_price=150.0,
        unrealized_pnl=0.0,
        status=TradeStatus.OPEN,
        features=feats,
    )


def _make_trade_record(position_id: str, symbol: str = "AAPL") -> TradeRecord:
    return TradeRecord(
        trade_id=str(uuid.uuid4()),
        position_id=position_id,
        symbol=symbol,
        direction="long",
        entry_price=150.0,
        exit_price=155.0,
        stop_price=145.0,
        target_price=160.0,
        size=100,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        hold_duration_minutes=60.0,
        realized_pnl=500.0,
        r_multiple=0.033,
        exit_reason="target",
        status="closed",
        rank_at_entry=1,
        score_at_entry=85.0,
        rank_at_exit=1,
        score_at_exit=85.0,
        features=None,
    )


def _build_loop(db: Database, position: Position) -> MemoryAwarePaperTradingLoop:
    writer = MemoryWriter(db, allow_network_fallback=False)

    settings = MagicMock()
    settings.RANKING_INTERVAL_MINUTES = 20

    ranking_cycle = MagicMock()
    ranked = MagicMock()
    ranked.cycle_id = "test_cycle_xyz"
    ranking_cycle.get_latest.return_value = ranked

    execution = MagicMock()
    position_manager = PositionManager(execution, settings)
    fetcher = MagicMock()
    alpaca = MagicMock()

    loop = MemoryAwarePaperTradingLoop(
        memory_writer=writer,
        ranking_cycle=ranking_cycle,
        position_manager=position_manager,
        execution=execution,
        fetcher=fetcher,
        settings=settings,
        alpaca_client=alpaca,
    )
    return loop


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_entry_path_inserts_open_position(mem_db):
    """MemoryAwarePaperTradingLoop._run_cycle_inner inserts a row into open_positions when a new position is added."""
    position = _make_position()
    loop = _build_loop(mem_db, position)

    # Patch parent _run_cycle_inner to simulate adding the position
    def _patched_parent_run_cycle_inner(self):
        self._position_manager.add_position(position)

    with patch.object(PaperTradingLoop, '_run_cycle_inner', _patched_parent_run_cycle_inner):
        loop._run_cycle_inner()

    # Check DB
    rows = mem_db.query("SELECT * FROM open_positions")
    assert len(rows) == 1
    row = rows[0]
    assert row['position_id'] == position.position_id
    assert row['symbol'] == position.symbol
    assert row['direction'] == position.direction.value
    assert row['size'] == position.size
    assert row['entry_price'] == position.entry_price
    assert row['stop_price'] == position.stop_price
    assert row['target_price'] == position.target_price


def test_entry_path_with_features(mem_db):
    """Entry path with features: confirms features JSON is populated with serialized BarFeatures.to_dict() output."""
    position = _make_position(with_features=True)
    loop = _build_loop(mem_db, position)

    def _patched_parent_run_cycle_inner(self):
        self._position_manager.add_position(position)

    with patch.object(PaperTradingLoop, '_run_cycle_inner', _patched_parent_run_cycle_inner):
        loop._run_cycle_inner()

    rows = mem_db.query("SELECT features FROM open_positions")
    assert len(rows) == 1
    features_json = rows[0]['features']
    assert features_json is not None
    parsed = json.loads(features_json)
    assert parsed['symbol'] == 'AAPL'
    assert parsed['close'] == 150.0


def test_entry_path_without_features(mem_db):
    """Entry path without features: confirms features is NULL when position.features is None."""
    position = _make_position(with_features=False)
    loop = _build_loop(mem_db, position)

    def _patched_parent_run_cycle_inner(self):
        self._position_manager.add_position(position)

    with patch.object(PaperTradingLoop, '_run_cycle_inner', _patched_parent_run_cycle_inner):
        loop._run_cycle_inner()

    rows = mem_db.query("SELECT features FROM open_positions")
    assert len(rows) == 1
    assert rows[0]['features'] is None


def test_exit_path_deletes_open_position(mem_db):
    """MemoryWriter.write_trade_and_close_position atomically inserts into trades and deletes from open_positions."""
    position = _make_position()
    writer = MemoryWriter(mem_db)

    # Insert open position manually
    repo = Repository(mem_db)
    repo.insert_open_position(
        position_id=position.position_id,
        symbol=position.symbol,
        direction=position.direction.value,
        size=position.size,
        entry_time=position.entry_time.isoformat(),
        entry_price=position.entry_price,
        stop_price=position.stop_price,
        target_price=position.target_price,
        features=None,
    )

    # Verify inserted
    assert len(mem_db.query("SELECT * FROM open_positions")) == 1
    assert len(mem_db.query("SELECT * FROM trades")) == 0

    # Close it
    trade = _make_trade_record(position.position_id)
    success = writer.write_trade_and_close_position(trade)

    assert success
    assert len(mem_db.query("SELECT * FROM open_positions")) == 0
    assert len(mem_db.query("SELECT * FROM trades")) == 1


def test_orphaned_exit_writes_event(mem_db):
    """Orphaned exit: when no open_positions row exists, trade is inserted and orphaned_exit_no_open_row event is written."""
    writer = MemoryWriter(mem_db)

    # No open position
    assert len(mem_db.query("SELECT * FROM open_positions")) == 0

    # Try to close a trade
    trade = _make_trade_record("nonexistent_pos")
    success = writer.write_trade_and_close_position(trade)

    assert success  # Trade inserted despite no open row
    assert len(mem_db.query("SELECT * FROM trades")) == 1

    # Check event
    events = mem_db.query("SELECT * FROM system_events WHERE event_type = 'orphaned_exit_no_open_row'")
    assert len(events) == 1
    event = events[0]
    assert event['symbol'] == trade.symbol
    metadata = json.loads(event['metadata_json'])
    assert metadata['trade_id'] == trade.trade_id
    assert metadata['position_id'] == trade.position_id


def test_startup_seeding_classifies_positions(mem_db):
    """_seed_open_positions correctly classifies fresh/warning/stale rows and writes expected system_events."""
    repo = Repository(mem_db)
    execution = MagicMock()
    settings = MagicMock()
    settings.OPEN_POSITION_STALE_WARN_HOURS = 24
    settings.OPEN_POSITION_STALE_SKIP_DAYS = 7
    position_manager = PositionManager(execution, settings)
    writer = MemoryWriter(mem_db)

    now = datetime.now(timezone.utc)
    fresh_time = (now - timedelta(hours=1)).isoformat()
    warning_time = (now - timedelta(hours=30)).isoformat()
    stale_time = (now - timedelta(days=8)).isoformat()

    # Insert positions
    repo.insert_open_position(
        position_id="fresh1", symbol="AAPL", direction="long", size=10,
        entry_time=fresh_time, entry_price=150.0, stop_price=145.0, target_price=155.0, features=None
    )
    repo.insert_open_position(
        position_id="warn1", symbol="TSLA", direction="short", size=5,
        entry_time=warning_time, entry_price=700.0, stop_price=720.0, target_price=680.0, features=None
    )
    repo.insert_open_position(
        position_id="stale1", symbol="MSFT", direction="long", size=8,
        entry_time=stale_time, entry_price=300.0, stop_price=295.0, target_price=310.0, features=None
    )

    log = MagicMock()

    _seed_open_positions(repo, position_manager, writer, settings, log)

    # Check loaded positions
    open_positions = position_manager.get_open_positions()
    loaded_ids = [p.position_id for p in open_positions]
    assert "fresh1" in loaded_ids
    assert "warn1" in loaded_ids
    assert "stale1" not in loaded_ids

    # Check events
    events = mem_db.query("SELECT id, event_type, description FROM system_events ORDER BY id")
    event_types = [e['event_type'] for e in events]
    assert 'stale_open_position_loaded' in event_types
    assert 'stale_open_position_skipped' in event_types
    assert 'local_state_seeded' in event_types

    # Check seeded summary
    seeded_event = next(e for e in events if e['event_type'] == 'local_state_seeded')
    metadata = json.loads(mem_db.query("SELECT metadata_json FROM system_events WHERE id = ?", (seeded_event['id'],))[0]['metadata_json'])
    assert metadata['loaded_positions'] == 2
    assert metadata['skipped_positions'] == 1