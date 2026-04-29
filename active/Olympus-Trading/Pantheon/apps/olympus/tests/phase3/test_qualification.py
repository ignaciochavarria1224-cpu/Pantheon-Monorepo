"""
Tests for the qualification and regime helpers added in the profitability upgrade.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import BarFeatures, Direction, RankedSymbol, RankedUniverse, TradeRecord
from core.trading.qualification import build_symbol_trade_stats, qualify_ranked_symbol
from core.trading.regime import classify_regime


def _make_settings():
    s = MagicMock()
    s.REGIME_MIN_SCORED_COUNT = 10
    s.REGIME_MAX_ERROR_COUNT = 10
    s.REGIME_TOP_N = 5
    s.REGIME_TREND_STRENGTH_MIN = 70.0
    s.REGIME_MIXED_STRENGTH_MIN = 58.0
    s.REGIME_MIXED_POSITION_SCALE = 0.5
    s.LONG_ENTRY_SCORE_THRESHOLD = 72.0
    s.SHORT_ENTRY_SCORE_THRESHOLD = 28.0
    s.LONG_MIN_RVOL = 1.15
    s.SHORT_MIN_RVOL = 1.05
    s.LONG_MIN_RANGE_POSITION = 0.55
    s.SHORT_MAX_RANGE_POSITION = 0.45
    s.LONG_MAX_VWAP_DEVIATION = 0.03
    s.SHORT_MAX_VWAP_DEVIATION = 0.03
    s.MIN_ATR_PCT = 0.001
    s.MAX_ATR_PCT = 0.25
    s.SYMBOL_COOLDOWN_TRIGGER_STOPS = 2
    s.SYMBOL_COOLDOWN_MINUTES = 90
    s.SYMBOL_SUPPRESSION_MIN_TRADES = 3
    s.SYMBOL_SUPPRESSION_MAX_STOP_RATE = 0.7
    s.SYMBOL_SUPPRESSION_MAX_PNL = -50.0
    return s


def _make_features(symbol="AAPL", normalized_score=80.0, rvol=1.5, range_position=0.8, vwap_deviation=0.01):
    return BarFeatures(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        close=100.0,
        volume=1_000_000.0,
        roc_5=1.0,
        roc_10=2.0,
        roc_20=4.0,
        acceleration=0.2,
        rvol=rvol,
        vwap_deviation=vwap_deviation,
        range_position=range_position,
        raw_score=0.8,
        normalized_score=normalized_score,
    )


def _make_ranked_symbol(symbol="AAPL", direction="long", score=80.0, rvol=1.5, range_position=0.8):
    return RankedSymbol(
        symbol=symbol,
        score=score,
        direction=direction,
        rank=1,
        features=_make_features(symbol, normalized_score=score, rvol=rvol, range_position=range_position),
        timestamp=datetime.now(timezone.utc),
    )


def _make_ranked_universe(longs=None, shorts=None, scored_count=100, error_count=0):
    return RankedUniverse(
        cycle_id="cycle-1",
        timestamp=datetime.now(timezone.utc),
        longs=longs or [],
        shorts=shorts or [],
        universe_size=100,
        scored_count=scored_count,
        error_count=error_count,
        duration_seconds=1.0,
    )


def _make_trade(symbol="AAPL", exit_reason="stop", pnl=-30.0):
    now = datetime.now(timezone.utc)
    return TradeRecord(
        trade_id=f"trade-{symbol}-{exit_reason}-{abs(int(pnl))}",
        position_id=f"pos-{symbol}",
        symbol=symbol,
        direction="long",
        entry_price=100.0,
        exit_price=97.0,
        stop_price=97.0,
        target_price=109.0,
        size=10,
        entry_time=now,
        exit_time=now,
        hold_duration_minutes=30.0,
        realized_pnl=pnl,
        r_multiple=-1.0,
        exit_reason=exit_reason,
        rank_at_entry=1,
        score_at_entry=80.0,
        rank_at_exit=5,
        score_at_exit=60.0,
        status="closed",
    )


def test_long_candidate_passes_and_short_candidate_fails():
    settings = _make_settings()
    regime = classify_regime(
        _make_ranked_universe(
            longs=[_make_ranked_symbol("AAPL", "long", 82.0)],
            shorts=[_make_ranked_symbol("TSLA", "short", 18.0, range_position=0.2)],
        ),
        settings,
    )

    long_result = qualify_ranked_symbol(
        ranked_symbol=_make_ranked_symbol("AAPL", "long", 82.0),
        direction=Direction.LONG,
        entry_price=100.0,
        atr=2.0,
        now_utc=datetime.now(timezone.utc),
        symbol_stats=None,
        regime=regime,
        settings=settings,
    )
    short_result = qualify_ranked_symbol(
        ranked_symbol=_make_ranked_symbol("TSLA", "short", 80.0, range_position=0.2),
        direction=Direction.SHORT,
        entry_price=100.0,
        atr=2.0,
        now_utc=datetime.now(timezone.utc),
        symbol_stats=None,
        regime=regime,
        settings=settings,
    )

    assert long_result.allowed is True
    assert short_result.allowed is False


def test_low_rvol_is_rejected():
    settings = _make_settings()
    regime = classify_regime(
        _make_ranked_universe(
            longs=[_make_ranked_symbol("AAPL", "long", 82.0)],
            shorts=[_make_ranked_symbol("TSLA", "short", 18.0, range_position=0.2)],
        ),
        settings,
    )

    result = qualify_ranked_symbol(
        ranked_symbol=_make_ranked_symbol(rvol=1.01),
        direction=Direction.LONG,
        entry_price=100.0,
        atr=2.0,
        now_utc=datetime.now(timezone.utc),
        symbol_stats=None,
        regime=regime,
        settings=settings,
    )

    assert result.allowed is False
    assert "rvol" in result.reason


def test_poor_range_position_is_rejected():
    settings = _make_settings()
    regime = classify_regime(
        _make_ranked_universe(
            longs=[_make_ranked_symbol("AAPL", "long", 82.0)],
            shorts=[_make_ranked_symbol("TSLA", "short", 18.0, range_position=0.2)],
        ),
        settings,
    )

    result = qualify_ranked_symbol(
        ranked_symbol=_make_ranked_symbol(range_position=0.3),
        direction=Direction.LONG,
        entry_price=100.0,
        atr=2.0,
        now_utc=datetime.now(timezone.utc),
        symbol_stats=None,
        regime=regime,
        settings=settings,
    )

    assert result.allowed is False
    assert "range_position" in result.reason


def test_degraded_regime_blocks_entries():
    settings = _make_settings()
    regime = classify_regime(
        _make_ranked_universe(
            longs=[_make_ranked_symbol()],
            scored_count=100,
            error_count=11,
        ),
        settings,
    )

    assert regime.name == "degraded"
    assert regime.allow_entries is False


def test_build_symbol_trade_stats_sets_cooldown_and_suppression():
    settings = _make_settings()
    now = datetime.now(timezone.utc)
    trades = [
        _make_trade("AAPL", "stop", -40.0),
        _make_trade("AAPL", "stop", -35.0),
        _make_trade("AAPL", "stop", -30.0),
    ]

    stats = build_symbol_trade_stats(trades, now_utc=now, settings=settings)

    assert stats["AAPL"]["cooldown_until"] is not None
    assert stats["AAPL"]["suppressed"] is True
