"""
Phase 3 tests — pre-entry risk validator.
All 6 gates tested independently. No network. No Alpaca.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import Direction, Position, TradeStatus
from core.trading.risk import validate_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(
    max_open=10,
    max_daily_loss_pct=0.02,
    min_rr=1.8,
):
    s = MagicMock()
    s.MAX_OPEN_POSITIONS = max_open
    s.MAX_DAILY_LOSS_PCT = max_daily_loss_pct
    s.MIN_REWARD_RISK = min_rr
    return s


def _make_position(symbol="AAPL", direction=Direction.LONG) -> Position:
    from datetime import datetime, timezone
    return Position(
        position_id="test-id",
        symbol=symbol,
        direction=direction,
        entry_price=100.0,
        stop_price=98.0,
        target_price=106.0,
        size=10,
        entry_time=datetime.now(timezone.utc),
        rank_at_entry=1,
        score_at_entry=75.0,
        current_price=100.0,
        unrealized_pnl=0.0,
        status=TradeStatus.OPEN,
    )


def _passing_kwargs(**overrides):
    """Return a valid set of kwargs that passes all 6 gates."""
    defaults = dict(
        symbol="TSLA",
        direction=Direction.LONG,
        entry_price=200.0,
        stop_price=196.0,     # $4 stop → ATR-style
        target_price=210.0,   # $10 target → RR = 2.5
        proposed_size=5,
        open_positions=[],
        daily_pnl=0.0,
        equity=100_000.0,
        settings=_make_settings(),
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Gate 1 — Max open positions
# ---------------------------------------------------------------------------

def test_gate1_fails_when_at_max_positions():
    settings = _make_settings(max_open=2)
    positions = [_make_position("AAPL"), _make_position("GOOG")]
    ok, reason = validate_entry(**_passing_kwargs(
        settings=settings,
        open_positions=positions,
    ))
    assert not ok
    assert "max open positions" in reason.lower()


def test_gate1_passes_when_one_below_max():
    settings = _make_settings(max_open=3)
    positions = [_make_position("AAPL"), _make_position("GOOG")]
    ok, _ = validate_entry(**_passing_kwargs(
        settings=settings,
        open_positions=positions,
    ))
    assert ok


# ---------------------------------------------------------------------------
# Gate 2 — No duplicate symbol
# ---------------------------------------------------------------------------

def test_gate2_fails_on_duplicate_symbol():
    positions = [_make_position("TSLA")]
    ok, reason = validate_entry(**_passing_kwargs(
        symbol="TSLA",
        open_positions=positions,
    ))
    assert not ok
    assert "duplicate" in reason.lower()


def test_gate2_passes_when_symbol_not_open():
    positions = [_make_position("AAPL")]
    ok, _ = validate_entry(**_passing_kwargs(
        symbol="TSLA",
        open_positions=positions,
    ))
    assert ok


# ---------------------------------------------------------------------------
# Gate 3 — Daily loss limit
# ---------------------------------------------------------------------------

def test_gate3_fails_when_daily_loss_at_limit():
    equity = 100_000.0
    settings = _make_settings(max_daily_loss_pct=0.02)
    # daily_pnl exactly at the limit (−$2000)
    ok, reason = validate_entry(**_passing_kwargs(
        daily_pnl=-2_000.0,
        equity=equity,
        settings=settings,
    ))
    assert not ok
    assert "daily loss" in reason.lower()


def test_gate3_fails_when_daily_loss_exceeds_limit():
    equity = 100_000.0
    settings = _make_settings(max_daily_loss_pct=0.02)
    ok, reason = validate_entry(**_passing_kwargs(
        daily_pnl=-2_500.0,
        equity=equity,
        settings=settings,
    ))
    assert not ok
    assert "daily loss" in reason.lower()


def test_gate3_passes_when_daily_loss_below_limit():
    equity = 100_000.0
    settings = _make_settings(max_daily_loss_pct=0.02)
    ok, _ = validate_entry(**_passing_kwargs(
        daily_pnl=-1_999.0,
        equity=equity,
        settings=settings,
    ))
    assert ok


def test_gate3_uses_equity_percentage():
    """Loss limit should scale with equity."""
    # 1% of 50_000 = $500
    settings = _make_settings(max_daily_loss_pct=0.01)
    ok, reason = validate_entry(**_passing_kwargs(
        daily_pnl=-501.0,
        equity=50_000.0,
        settings=settings,
    ))
    assert not ok
    assert "daily loss" in reason.lower()


# ---------------------------------------------------------------------------
# Gate 4 — Valid stop distance
# ---------------------------------------------------------------------------

def test_gate4_fails_long_stop_above_entry():
    ok, reason = validate_entry(**_passing_kwargs(
        direction=Direction.LONG,
        entry_price=100.0,
        stop_price=101.0,  # stop above entry for LONG — invalid
        target_price=110.0,
    ))
    assert not ok
    assert "invalid stop" in reason.lower()


def test_gate4_fails_long_stop_equal_to_entry():
    ok, reason = validate_entry(**_passing_kwargs(
        direction=Direction.LONG,
        entry_price=100.0,
        stop_price=100.0,
        target_price=110.0,
    ))
    assert not ok


def test_gate4_fails_short_stop_below_entry():
    ok, reason = validate_entry(**_passing_kwargs(
        direction=Direction.SHORT,
        entry_price=100.0,
        stop_price=99.0,   # stop below entry for SHORT — invalid
        target_price=90.0,
    ))
    assert not ok
    assert "invalid stop" in reason.lower()


def test_gate4_fails_stop_too_tight():
    ok, reason = validate_entry(**_passing_kwargs(
        direction=Direction.LONG,
        entry_price=100.0,
        stop_price=99.995,  # distance = 0.005 < 0.01
        target_price=110.0,
    ))
    assert not ok
    assert "tight" in reason.lower()


# ---------------------------------------------------------------------------
# Gate 5 — Reward/risk ratio
# ---------------------------------------------------------------------------

def test_gate5_fails_when_rr_below_minimum():
    settings = _make_settings(min_rr=1.8)
    # entry=200, stop=196 (risk=$4), target=206 (reward=$6) → RR=1.5
    ok, reason = validate_entry(**_passing_kwargs(
        entry_price=200.0,
        stop_price=196.0,
        target_price=206.0,  # $6 / $4 = 1.5 < 1.8
        settings=settings,
    ))
    assert not ok
    assert "reward/risk" in reason.lower()


def test_gate5_passes_when_rr_meets_minimum():
    settings = _make_settings(min_rr=1.8)
    # entry=200, stop=196 (risk=$4), target=208 (reward=$8) → RR=2.0
    ok, _ = validate_entry(**_passing_kwargs(
        entry_price=200.0,
        stop_price=196.0,
        target_price=208.0,
        settings=settings,
    ))
    assert ok


def test_gate5_rr_calculation_is_correct():
    settings = _make_settings(min_rr=3.0)
    # entry=100, stop=97 (risk=$3), target=109 (reward=$9) → RR=3.0 exactly
    # 3.0 >= 3.0 → should pass
    ok, _ = validate_entry(**_passing_kwargs(
        entry_price=100.0,
        stop_price=97.0,
        target_price=109.0,
        settings=settings,
    ))
    assert ok


def test_side_specific_cap_blocks_new_longs():
    settings = _make_settings(max_open=10)
    positions = [_make_position("AAPL", Direction.LONG), _make_position("MSFT", Direction.LONG)]
    ok, reason = validate_entry(**_passing_kwargs(
        settings=settings,
        open_positions=positions,
        side_open_positions=positions,
        max_positions_for_side=2,
    ))
    assert not ok
    assert "max long positions" in reason.lower()


def test_sector_concentration_blocks_entry():
    settings = _make_settings(max_open=10)
    positions = [_make_position("AAPL"), _make_position("MSFT")]
    ok, reason = validate_entry(**_passing_kwargs(
        settings=settings,
        open_positions=positions,
        sector="technology",
        sector_by_symbol={"AAPL": "technology", "MSFT": "technology"},
        sector_limit=2,
    ))
    assert not ok
    assert "sector concentration" in reason.lower()


# ---------------------------------------------------------------------------
# Gate 6 — Minimum position size
# ---------------------------------------------------------------------------

def test_gate6_fails_on_zero_size():
    ok, reason = validate_entry(**_passing_kwargs(proposed_size=0))
    assert not ok
    assert "size" in reason.lower()


def test_gate6_fails_on_negative_size():
    ok, reason = validate_entry(**_passing_kwargs(proposed_size=-5))
    assert not ok
    assert "size" in reason.lower()


def test_gate6_passes_on_size_one():
    ok, _ = validate_entry(**_passing_kwargs(proposed_size=1))
    assert ok


# ---------------------------------------------------------------------------
# All 6 gates passing
# ---------------------------------------------------------------------------

def test_all_gates_pass_returns_ok():
    ok, reason = validate_entry(**_passing_kwargs())
    assert ok is True
    assert reason == "ok"


def test_each_gate_fails_independently():
    """Verify that each gate failure doesn't depend on another gate also failing."""
    base = _passing_kwargs()

    # Gate 1
    s1 = _make_settings(max_open=0)
    ok1, _ = validate_entry(**{**base, "settings": s1})
    assert not ok1

    # Gate 2
    ok2, _ = validate_entry(**{**base, "open_positions": [_make_position("TSLA")]})
    assert not ok2

    # Gate 3
    ok3, _ = validate_entry(**{**base, "daily_pnl": -999_999.0})
    assert not ok3

    # Gate 4
    ok4, _ = validate_entry(**{**base, "stop_price": base["entry_price"] + 5})
    assert not ok4

    # Gate 5
    ok5, _ = validate_entry(**{**base, "target_price": base["entry_price"] + 0.10})
    assert not ok5

    # Gate 6
    ok6, _ = validate_entry(**{**base, "proposed_size": 0})
    assert not ok6
