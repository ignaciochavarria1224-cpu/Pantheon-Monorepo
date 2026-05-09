"""
Option B verification — exercise MemoryAwarePaperTradingLoop._run_cycle_inner
against a temp DB. Does NOT modify the live DB. Not for committing.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.memory.database import Database
from core.memory.repository import Repository
from core.memory.writer import MemoryAwarePaperTradingLoop, MemoryWriter
from core.models import BarFeatures, Direction, Position, TradeStatus
from core.trading.loop import PaperTradingLoop


def _make_position(with_features: bool) -> Position:
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
        position_id=f"pos_{int(datetime.now().timestamp()*1000)}",
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


def _build_loop(db: Database, monkey_position: Position) -> MemoryAwarePaperTradingLoop:
    """Build a real loop, but monkey-patch the parent's _run_cycle_inner to
    just add the supplied Position to the position_manager (simulating an
    entry)."""
    writer = MemoryWriter(db, allow_network_fallback=False)

    settings = MagicMock()
    settings.RANKING_INTERVAL_MINUTES = 20

    ranking_cycle = MagicMock()
    ranked = MagicMock()
    ranked.cycle_id = "test_cycle_xyz"
    ranking_cycle.get_latest.return_value = ranked

    execution = MagicMock()

    # Use the real PositionManager so add_position / get_open_positions behave
    # as in production.
    from core.trading.manager import PositionManager
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


def _patched_parent_run_cycle_inner_factory(position: Position):
    def _patched(self):
        # Simulate a successful entry: parent would normally add the position
        # to the manager during entry processing.
        self._position_manager.add_position(position)
    return _patched


def run_case(label: str, with_features: bool) -> None:
    print(f"\n=== Case: {label} (features={'BarFeatures' if with_features else 'None'}) ===")
    tmpdir = tempfile.mkdtemp(prefix="olympus_optionB_")
    db_path = Path(tmpdir) / "test.db"
    db = Database(db_path)
    db.initialize()
    try:
        position = _make_position(with_features=with_features)
        loop = _build_loop(db, position)

        patched = _patched_parent_run_cycle_inner_factory(position)
        with patch.object(PaperTradingLoop, "_run_cycle_inner", patched):
            try:
                loop._run_cycle_inner()
                print("loop._run_cycle_inner() returned without raising")
            except Exception:
                print("loop._run_cycle_inner() RAISED:")
                traceback.print_exc()

        # Inspect the temp DB directly via sqlite3 to bypass repo.
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT position_id, symbol, direction, size, entry_time, "
            "entry_price, features, last_seen_at, created_at, updated_at "
            "FROM open_positions"
        ).fetchall()
        conn.close()

        print(f"open_positions row count: {len(rows)}")
        for r in rows:
            print(
                "  position_id=%s symbol=%s direction=%s size=%s "
                "features_is_null=%s entry_time=%s last_seen_at=%s"
                % (r[0][:12], r[1], r[2], r[3], r[6] is None, r[4], r[7])
            )

        if not rows:
            print(
                "VERDICT: ENTRY PATH DID NOT INSERT — silent failure "
                "(matches the 'NULL features' regression class)"
            )
        else:
            features_present = rows[0][6] is not None
            print(
                f"VERDICT: row inserted, features {'PRESENT' if features_present else 'NULL'}"
            )
    finally:
        db.close()


def main() -> int:
    print(f"sys.path[0]={sys.path[0]}")
    run_case("position with features (production case)", with_features=True)
    run_case("position with no features (rare/data-quality case)", with_features=False)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
