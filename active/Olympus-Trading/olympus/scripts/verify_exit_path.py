"""
Exit-path verification — exercises the full lifecycle of an open
position through the real MemoryAwarePaperTradingLoop code path on a
temp DB. Does NOT modify the live DB. Not for committing as a runtime
artifact; lives under scripts/ as a regression check.

Two cases:
  1. Lifecycle: open via _run_cycle_inner (entry path), then close via
     _register_completed_trade. Confirms open_positions row is deleted
     atomically with the trades insert.
  2. Orphaned exit: call _register_completed_trade with a TradeRecord
     whose position_id has no open_positions row. Confirms trade is
     still inserted, an 'orphaned_exit_no_open_row' system_event is
     written, and no exception propagates.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory.database import Database
from core.memory.writer import MemoryAwarePaperTradingLoop, MemoryWriter
from core.models import (
    BarFeatures,
    Direction,
    Position,
    TradeRecord,
    TradeStatus,
)
from core.trading.loop import PaperTradingLoop


def _make_features() -> BarFeatures:
    return BarFeatures(
        symbol="AAPL",
        timestamp=datetime.now(timezone.utc),
        close=150.0, volume=1_000_000.0,
        roc_5=0.01, roc_10=0.02, roc_20=0.03,
        acceleration=-0.01,
        rvol=1.2, vwap_deviation=0.005, range_position=0.7,
        raw_score=85.0, normalized_score=85.0,
    )


def _make_position(position_id: str) -> Position:
    return Position(
        position_id=position_id,
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
        features=_make_features(),
    )


def _make_trade_record(position_id: str, trade_id: str) -> TradeRecord:
    entry = datetime.now(timezone.utc) - timedelta(hours=1)
    exit_ = datetime.now(timezone.utc)
    return TradeRecord(
        trade_id=trade_id,
        position_id=position_id,
        symbol="AAPL",
        direction="long",
        entry_price=150.0,
        exit_price=155.0,
        stop_price=145.0,
        target_price=160.0,
        size=100,
        entry_time=entry,
        exit_time=exit_,
        hold_duration_minutes=60.0,
        realized_pnl=500.0,
        r_multiple=1.0,
        exit_reason="target",
        rank_at_entry=1,
        score_at_entry=85.0,
        rank_at_exit=1,
        score_at_exit=82.0,
        status="closed",
        features=_make_features(),
    )


def _build_loop(db: Database) -> MemoryAwarePaperTradingLoop:
    writer = MemoryWriter(db, allow_network_fallback=False)
    settings = MagicMock()
    settings.RANKING_INTERVAL_MINUTES = 20

    ranking_cycle = MagicMock()
    ranked = MagicMock()
    ranked.cycle_id = "test_cycle_xyz"
    ranking_cycle.get_latest.return_value = ranked

    execution = MagicMock()

    from core.trading.manager import PositionManager
    position_manager = PositionManager(execution, settings)

    fetcher = MagicMock()
    alpaca = MagicMock()

    return MemoryAwarePaperTradingLoop(
        memory_writer=writer,
        ranking_cycle=ranking_cycle,
        position_manager=position_manager,
        execution=execution,
        fetcher=fetcher,
        settings=settings,
        alpaca_client=alpaca,
    )


def _patched_parent_run_cycle_inner(position):
    def _patched(self):
        self._position_manager.add_position(position)
    return _patched


def _row_counts(db_path: Path) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    op = conn.execute("SELECT COUNT(*) FROM open_positions").fetchone()[0]
    tr = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    return op, tr


def _events(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT event_type, description FROM system_events ORDER BY rowid"
    ).fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]


def case_lifecycle() -> None:
    print("\n=== Case: full lifecycle (open then close) ===")
    tmpdir = tempfile.mkdtemp(prefix="olympus_exit_lifecycle_")
    db_path = Path(tmpdir) / "test.db"
    db = Database(db_path)
    db.initialize()
    try:
        position = _make_position(position_id="pos_lifecycle_1")
        loop = _build_loop(db)

        # --- Entry path
        with patch.object(
            PaperTradingLoop, "_run_cycle_inner",
            _patched_parent_run_cycle_inner(position),
        ):
            loop._run_cycle_inner()

        op, tr = _row_counts(db_path)
        print(f"after entry:  open_positions={op}  trades={tr}")
        assert op == 1, f"expected 1 open_position, got {op}"
        assert tr == 0, f"expected 0 trades, got {tr}"

        # --- Exit path via _register_completed_trade
        record = _make_trade_record(
            position_id=position.position_id,
            trade_id="trade_lifecycle_1",
        )
        loop._register_completed_trade(record)

        op, tr = _row_counts(db_path)
        print(f"after exit:   open_positions={op}  trades={tr}")
        assert op == 0, f"expected 0 open_positions, got {op}"
        assert tr == 1, f"expected 1 trade, got {tr}"

        # Confirm the linkage
        conn = sqlite3.connect(db_path)
        link = conn.execute(
            "SELECT trade_id, position_id FROM trades WHERE trade_id = ?",
            (record.trade_id,),
        ).fetchone()
        conn.close()
        assert link == (record.trade_id, position.position_id), \
            f"trade/position linkage wrong: {link}"
        print(f"linkage:      trade_id={link[0]}  position_id={link[1]}  OK")

        # No orphan event expected
        events = _events(db_path)
        orphan_events = [e for e in events if e[0] == "orphaned_exit_no_open_row"]
        assert not orphan_events, f"unexpected orphan event: {orphan_events}"
        print("orphan event: none (correct)")
        print("VERDICT: lifecycle PASSED")
    finally:
        db.close()


def case_orphaned_exit() -> None:
    print("\n=== Case: orphaned exit (no matching open_positions row) ===")
    tmpdir = tempfile.mkdtemp(prefix="olympus_exit_orphan_")
    db_path = Path(tmpdir) / "test.db"
    db = Database(db_path)
    db.initialize()
    try:
        loop = _build_loop(db)

        op, tr = _row_counts(db_path)
        print(f"initial:      open_positions={op}  trades={tr}")
        assert op == 0 and tr == 0

        # Exit path with a position_id that has no open_positions row
        record = _make_trade_record(
            position_id="pos_does_not_exist",
            trade_id="trade_orphan_1",
        )

        raised = None
        try:
            loop._register_completed_trade(record)
        except Exception as exc:
            raised = exc

        op, tr = _row_counts(db_path)
        print(f"after orphan exit:  open_positions={op}  trades={tr}")
        assert raised is None, f"unexpected exception: {raised}"
        assert op == 0, f"expected 0 open_positions, got {op}"
        assert tr == 1, f"expected 1 trade (still inserted), got {tr}"

        events = _events(db_path)
        orphan_events = [e for e in events if e[0] == "orphaned_exit_no_open_row"]
        print(f"orphan events written: {len(orphan_events)}")
        for et, desc in orphan_events:
            print(f"  - {et}: {desc}")
        assert len(orphan_events) == 1, \
            f"expected 1 orphaned_exit_no_open_row event, got {len(orphan_events)}"
        print("VERDICT: orphaned-exit PASSED")
    finally:
        db.close()


def main() -> int:
    print(f"sys.path[0]={sys.path[0]}")
    failures = []
    for name, fn in [("lifecycle", case_lifecycle), ("orphaned_exit", case_orphaned_exit)]:
        try:
            fn()
        except Exception:
            print(f"\nCASE {name} FAILED:")
            traceback.print_exc()
            failures.append(name)
    print("\n=== summary ===")
    if failures:
        print(f"FAILURES: {failures}")
        return 1
    print("ALL CASES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
