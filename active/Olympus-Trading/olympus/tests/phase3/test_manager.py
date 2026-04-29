"""
Phase 3 tests — PositionManager lifecycle logic.
All tests use mock positions — no network, no Alpaca.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import Direction, Position, RankedSymbol, RankedUniverse, TradeRecord, TradeStatus
from core.trading.manager import PositionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(rotation_threshold=15, max_open=20):
    s = MagicMock()
    s.ROTATION_RANK_DROP_THRESHOLD = rotation_threshold
    s.MAX_OPEN_POSITIONS = max_open
    return s


def _make_position(
    symbol="AAPL",
    direction=Direction.LONG,
    entry_price=100.0,
    stop_price=97.0,
    target_price=109.0,
    size=10,
) -> Position:
    return Position(
        position_id=f"pos-{symbol}",
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        size=size,
        entry_time=datetime.now(timezone.utc),
        rank_at_entry=1,
        score_at_entry=75.0,
        current_price=entry_price,
        unrealized_pnl=0.0,
        status=TradeStatus.OPEN,
    )


def _make_trade_record(symbol="AAPL") -> TradeRecord:
    now = datetime.now(timezone.utc)
    return TradeRecord(
        trade_id=f"trade-{symbol}",
        position_id=f"pos-{symbol}",
        symbol=symbol,
        direction="long",
        entry_price=100.0,
        exit_price=109.0,
        stop_price=97.0,
        target_price=109.0,
        size=10,
        entry_time=now,
        exit_time=now,
        hold_duration_minutes=30.0,
        realized_pnl=90.0,
        r_multiple=3.0,
        exit_reason="target",
        rank_at_entry=1,
        score_at_entry=75.0,
        rank_at_exit=1,
        score_at_exit=75.0,
        status="closed",
    )


def _make_ranked_universe(longs=None, shorts=None) -> RankedUniverse:
    from datetime import timezone
    longs = longs or []
    shorts = shorts or []
    return RankedUniverse(
        cycle_id="test-cycle",
        timestamp=datetime.now(timezone.utc),
        longs=longs,
        shorts=shorts,
        universe_size=100,
        scored_count=100,
        error_count=0,
        duration_seconds=1.0,
    )


def _make_ranked_symbol(symbol, rank, direction="long", score=70.0):
    from core.models import BarFeatures
    from datetime import timezone
    bf = MagicMock(spec=BarFeatures)
    bf.normalized_score = score
    return RankedSymbol(
        symbol=symbol,
        score=score,
        direction=direction,
        rank=rank,
        features=bf,
        timestamp=datetime.now(timezone.utc),
    )


def _make_execution_that_returns_record(symbol="AAPL"):
    execution = MagicMock()
    execution.exit_position.return_value = _make_trade_record(symbol)
    return execution


def _make_execution_that_returns_none():
    execution = MagicMock()
    execution.exit_position.return_value = None
    return execution


# ---------------------------------------------------------------------------
# evaluate_exits — LONG
# ---------------------------------------------------------------------------

def test_evaluate_exits_long_stop_triggered_when_bar_low_at_stop():
    execution = _make_execution_that_returns_record("AAPL")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0))

    records = pm.evaluate_exits({"AAPL": {"low": 97.0, "high": 100.0, "close": 98.0}})
    assert len(records) == 1
    assert records[0].symbol == "AAPL"
    execution.exit_position.assert_called_once()
    _, kwargs = execution.exit_position.call_args
    assert kwargs.get("exit_reason") == "stop" or execution.exit_position.call_args[0][2] == "stop"


def test_evaluate_exits_long_stop_triggered_when_bar_low_below_stop():
    execution = _make_execution_that_returns_record("AAPL")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0))

    records = pm.evaluate_exits({"AAPL": {"low": 96.0, "high": 100.0, "close": 97.5}})
    assert len(records) == 1


def test_evaluate_exits_long_target_triggered_when_bar_high_at_target():
    execution = _make_execution_that_returns_record("AAPL")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, target_price=109.0))

    records = pm.evaluate_exits({"AAPL": {"low": 105.0, "high": 109.0, "close": 108.0}})
    assert len(records) == 1
    # Verify exit reason
    call_args = execution.exit_position.call_args
    exit_reason = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("exit_reason")
    assert exit_reason == "target"


def test_evaluate_exits_long_no_exit_when_bar_within_range():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0, target_price=109.0))

    records = pm.evaluate_exits({"AAPL": {"low": 98.0, "high": 108.0, "close": 103.0}})
    assert len(records) == 0
    execution.exit_position.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_exits — SHORT
# ---------------------------------------------------------------------------

def test_evaluate_exits_short_stop_triggered_when_bar_high_at_stop():
    execution = _make_execution_that_returns_record("TSLA")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position(
        "TSLA", Direction.SHORT, entry_price=100.0, stop_price=103.0, target_price=91.0
    ))

    records = pm.evaluate_exits({"TSLA": {"low": 98.0, "high": 103.0, "close": 100.0}})
    assert len(records) == 1
    call_args = execution.exit_position.call_args
    exit_reason = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("exit_reason")
    assert exit_reason == "stop"


def test_evaluate_exits_short_target_triggered_when_bar_low_at_target():
    execution = _make_execution_that_returns_record("TSLA")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position(
        "TSLA", Direction.SHORT, entry_price=100.0, stop_price=103.0, target_price=91.0
    ))

    records = pm.evaluate_exits({"TSLA": {"low": 91.0, "high": 99.0, "close": 93.0}})
    assert len(records) == 1
    call_args = execution.exit_position.call_args
    exit_reason = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("exit_reason")
    assert exit_reason == "target"


def test_evaluate_exits_short_no_exit_when_within_range():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position(
        "TSLA", Direction.SHORT, entry_price=100.0, stop_price=103.0, target_price=91.0
    ))

    records = pm.evaluate_exits({"TSLA": {"low": 92.0, "high": 102.0, "close": 97.0}})
    assert len(records) == 0
    execution.exit_position.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_exits — position removed after successful exit
# ---------------------------------------------------------------------------

def test_evaluate_exits_removes_position_on_success():
    execution = _make_execution_that_returns_record("AAPL")
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0))

    assert pm.get_position("AAPL") is not None
    pm.evaluate_exits({"AAPL": {"low": 96.0, "high": 99.0, "close": 97.0}})
    assert pm.get_position("AAPL") is None


def test_evaluate_exits_keeps_position_when_order_fails():
    execution = _make_execution_that_returns_none()
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0))

    records = pm.evaluate_exits({"AAPL": {"low": 95.0, "high": 98.0, "close": 96.0}})
    assert len(records) == 0
    # Position should still be open
    assert pm.get_position("AAPL") is not None


# ---------------------------------------------------------------------------
# evaluate_exits — missing bar skipped
# ---------------------------------------------------------------------------

def test_evaluate_exits_skips_position_with_no_bar():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings())
    pm.add_position(_make_position("AAPL", Direction.LONG, stop_price=97.0))

    # No bar for AAPL
    records = pm.evaluate_exits({})
    assert len(records) == 0
    execution.exit_position.assert_not_called()


# ---------------------------------------------------------------------------
# evaluate_rotations — LONG
# ---------------------------------------------------------------------------

def test_evaluate_rotations_flags_long_not_in_ranked_longs():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings(rotation_threshold=15))
    pm.add_position(_make_position("AAPL", Direction.LONG))

    # AAPL not in ranked longs at all
    universe = _make_ranked_universe(
        longs=[_make_ranked_symbol("GOOG", 1)],
    )
    symbols = pm.evaluate_rotations(universe)
    assert "AAPL" in symbols


def test_evaluate_rotations_flags_long_rank_exceeds_threshold():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings(rotation_threshold=5))
    pm.add_position(_make_position("AAPL", Direction.LONG))

    # AAPL present but rank=6 > threshold=5
    universe = _make_ranked_universe(
        longs=[_make_ranked_symbol("AAPL", 6)],
    )
    symbols = pm.evaluate_rotations(universe)
    assert "AAPL" in symbols


def test_evaluate_rotations_does_not_flag_long_still_ranked():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings(rotation_threshold=15))
    pm.add_position(_make_position("AAPL", Direction.LONG))

    # AAPL at rank 3 — below threshold=15 → should NOT be rotated
    universe = _make_ranked_universe(
        longs=[_make_ranked_symbol("AAPL", 3)],
    )
    symbols = pm.evaluate_rotations(universe)
    assert "AAPL" not in symbols


# ---------------------------------------------------------------------------
# evaluate_rotations — SHORT
# ---------------------------------------------------------------------------

def test_evaluate_rotations_flags_short_not_in_ranked_shorts():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings(rotation_threshold=15))
    pm.add_position(_make_position("TSLA", Direction.SHORT))

    # TSLA not in shorts
    universe = _make_ranked_universe(
        shorts=[_make_ranked_symbol("GOOG", 1, direction="short")],
    )
    symbols = pm.evaluate_rotations(universe)
    assert "TSLA" in symbols


def test_evaluate_rotations_does_not_flag_short_still_ranked():
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings(rotation_threshold=15))
    pm.add_position(_make_position("TSLA", Direction.SHORT))

    # TSLA at rank 2 — below threshold=15 → keep
    universe = _make_ranked_universe(
        shorts=[_make_ranked_symbol("TSLA", 2, direction="short")],
    )
    symbols = pm.evaluate_rotations(universe)
    assert "TSLA" not in symbols


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

def test_thread_safety_concurrent_reads_do_not_raise():
    """Multiple threads reading positions simultaneously should not raise."""
    execution = MagicMock()
    pm = PositionManager(execution, _make_settings())

    for i in range(5):
        pm.add_position(_make_position(f"SYM{i}", Direction.LONG))

    errors = []

    def _read():
        try:
            for _ in range(100):
                _ = pm.get_open_positions()
                _ = pm.get_position("SYM0")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_read) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(errors) == 0, f"Thread safety errors: {errors}"
