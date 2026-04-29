"""
Phase 3 tests — position sizing functions.
Pure unit tests — no network, no Alpaca.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import Direction
from core.trading.sizing import calculate_size, calculate_stop_and_target


# ---------------------------------------------------------------------------
# calculate_size
# ---------------------------------------------------------------------------

def test_calculate_size_basic():
    # equity=$100k, risk_pct=0.5%, entry=$100, stop=$98 → risk_per_share=$2
    # max_risk = $500, size = floor(500/2) = 250
    size = calculate_size(equity=100_000.0, entry_price=100.0, stop_price=98.0, max_risk_pct=0.005)
    assert size == 250


def test_calculate_size_rounds_down():
    # max_risk=$500, risk_per_share=$3 → 500/3 = 166.67 → floor = 166
    size = calculate_size(equity=100_000.0, entry_price=100.0, stop_price=97.0, max_risk_pct=0.005)
    assert size == 166


def test_calculate_size_minimum_one_when_risk_very_large():
    # entry=$5, stop=$0.01 → risk_per_share=$4.99 → max_risk=$50 → floor(50/4.99)=10
    # Make risk_per_share bigger than max_risk_dollars
    # equity=$100, risk_pct=0.005 → max_risk=$0.50, risk=$4.99 → floor(0.1) = 0 → clamp to 1
    size = calculate_size(equity=100.0, entry_price=5.0, stop_price=0.01, max_risk_pct=0.005)
    assert size == 1


def test_calculate_size_zero_risk_per_share_returns_one():
    # stop == entry → zero risk, should return 1 without raising
    size = calculate_size(equity=100_000.0, entry_price=100.0, stop_price=100.0, max_risk_pct=0.005)
    assert size == 1


def test_calculate_size_short_stop_above_entry():
    # For SHORT: entry=$100, stop=$102 → risk_per_share = abs(100-102) = $2
    size = calculate_size(equity=100_000.0, entry_price=100.0, stop_price=102.0, max_risk_pct=0.005)
    assert size == 250


def test_calculate_size_scales_with_equity():
    # Double equity → double size
    s1 = calculate_size(equity=50_000.0, entry_price=100.0, stop_price=98.0, max_risk_pct=0.005)
    s2 = calculate_size(equity=100_000.0, entry_price=100.0, stop_price=98.0, max_risk_pct=0.005)
    assert s2 == 2 * s1


def test_calculate_size_no_exception_on_edge_cases():
    # Should never raise
    assert calculate_size(0.0, 100.0, 98.0, 0.005) == 1
    assert calculate_size(100_000.0, 0.0, 0.0, 0.005) == 1
    assert calculate_size(100_000.0, 100.0, 100.0, 0.0) == 1


# ---------------------------------------------------------------------------
# calculate_stop_and_target
# ---------------------------------------------------------------------------

def test_stop_and_target_long_stop_below_entry():
    stop, target = calculate_stop_and_target(
        entry_price=100.0,
        direction=Direction.LONG,
        atr=2.0,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    # stop = 100 - (2 * 1.5) = 97.0
    # target = 100 + (2 * 3.0) = 106.0
    assert stop == 97.0
    assert target == 106.0


def test_stop_and_target_long_stop_strictly_below_entry():
    stop, target = calculate_stop_and_target(
        entry_price=200.0,
        direction=Direction.LONG,
        atr=4.0,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    assert stop < 200.0
    assert target > 200.0


def test_stop_and_target_short_stop_above_entry():
    stop, target = calculate_stop_and_target(
        entry_price=100.0,
        direction=Direction.SHORT,
        atr=2.0,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    # stop = 100 + (2 * 1.5) = 103.0
    # target = 100 - (2 * 3.0) = 94.0
    assert stop == 103.0
    assert target == 94.0


def test_stop_and_target_short_stop_strictly_above_entry():
    stop, target = calculate_stop_and_target(
        entry_price=50.0,
        direction=Direction.SHORT,
        atr=1.0,
        stop_multiplier=2.0,
        target_multiplier=4.0,
    )
    assert stop > 50.0
    assert target < 50.0


def test_stop_and_target_prices_rounded_to_two_decimals():
    stop, target = calculate_stop_and_target(
        entry_price=100.0,
        direction=Direction.LONG,
        atr=1.333,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    # Ensure rounded to 2 decimal places
    assert stop == round(stop, 2)
    assert target == round(target, 2)


def test_stop_and_target_atr_zero_uses_fallback():
    # atr=0 → fallback = entry * 0.01 = 1.0
    stop, target = calculate_stop_and_target(
        entry_price=100.0,
        direction=Direction.LONG,
        atr=0.0,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    # fallback_atr = 100 * 0.01 = 1.0
    # stop = 100 - (1.0 * 1.5) = 98.5
    # target = 100 + (1.0 * 3.0) = 103.0
    assert stop == 98.5
    assert target == 103.0


def test_stop_and_target_negative_atr_uses_fallback():
    # Negative ATR should also use fallback
    stop, target = calculate_stop_and_target(
        entry_price=100.0,
        direction=Direction.LONG,
        atr=-5.0,
        stop_multiplier=1.5,
        target_multiplier=3.0,
    )
    assert stop < 100.0
    assert target > 100.0
