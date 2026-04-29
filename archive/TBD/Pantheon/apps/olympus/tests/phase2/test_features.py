"""
Phase 2 tests — feature engineering.
Run with: pytest tests/phase2/test_features.py -v -m "not integration"
All tests here are pure unit tests requiring no network or filesystem access.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
import pytz

# Add olympus root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.ranking.features import compute_features

_ET = pytz.timezone("America/New_York")
_BASE_TS = datetime(2024, 1, 10, 9, 30, tzinfo=_ET)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bar(
    close: float,
    high: float | None = None,
    low: float | None = None,
    volume: float = 1000.0,
    vwap: float | None = None,
    idx: int = 0,
) -> dict:
    ts = _BASE_TS + timedelta(minutes=5 * idx)
    return {
        "symbol": "TEST",
        "timestamp": ts,
        "open": close,
        "high": high if high is not None else close * 1.01,
        "low": low if low is not None else close * 0.99,
        "close": close,
        "volume": volume,
        "vwap": vwap,
    }


def _make_flat_bars(n: int = 30, close: float = 100.0, volume: float = 1000.0) -> list[dict]:
    """n bars all at the same close price (except index 0 to avoid constant-close guard)."""
    bars = []
    for i in range(n):
        # Slightly vary so the constant-close guard does not fire
        c = close + (0.01 * i)
        bars.append(_make_bar(c, volume=volume, idx=i))
    return bars


def _make_deterministic_bars() -> list[dict]:
    """
    25 bars with these specific closes at reference positions:
        bars[4]  = 80.0   (index -21 → close_20ago)
        bars[14] = 90.0   (index -11 → close_10ago)
        bars[19] = 100.0  (index -6  → close_5ago)
        bars[24] = 110.0  (index -1  → close_now / latest)
        All others = 100.0

    Computed expected values:
        roc_20  = (110 - 80)  / 80  * 100 = 37.5
        roc_10  = (110 - 90)  / 90  * 100 ≈ 22.222
        roc_5   = (110 - 100) / 100 * 100 = 10.0
        accel   = roc_5 - roc_10 = 10 - 22.222 ≈ -12.222
    """
    closes = [100.0] * 25
    closes[4] = 80.0
    closes[14] = 90.0
    closes[19] = 100.0
    closes[24] = 110.0

    bars = []
    for i, c in enumerate(closes):
        bars.append(_make_bar(c, volume=1000.0, vwap=None, idx=i))
    return bars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComputeFeaturesGuards:

    def test_returns_none_when_fewer_than_25_bars(self):
        bars = _make_flat_bars(n=24)
        result = compute_features("TEST", bars)
        assert result is None

    def test_returns_none_when_exactly_24_bars(self):
        bars = _make_flat_bars(n=24)
        result = compute_features("TEST", bars)
        assert result is None

    def test_returns_not_none_when_exactly_25_bars(self):
        bars = _make_flat_bars(n=25)
        result = compute_features("TEST", bars)
        assert result is not None

    def test_returns_none_when_volume_all_zero(self):
        bars = _make_flat_bars(n=30, volume=0.0)
        result = compute_features("TEST", bars)
        assert result is None

    def test_returns_none_when_close_prices_constant(self):
        # All closes identical — no signal possible
        bars = [_make_bar(100.0, idx=i) for i in range(30)]
        result = compute_features("TEST", bars)
        assert result is None

    def test_returns_none_on_empty_bars(self):
        result = compute_features("TEST", [])
        assert result is None


class TestComputeFeaturesMomentum:

    def test_roc_5_correct(self):
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None
        assert pytest.approx(result.roc_5, abs=1e-6) == 10.0

    def test_roc_10_correct(self):
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None
        expected = (110.0 - 90.0) / 90.0 * 100.0
        assert pytest.approx(result.roc_10, abs=1e-6) == expected

    def test_roc_20_correct(self):
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None
        assert pytest.approx(result.roc_20, abs=1e-6) == 37.5

    def test_acceleration_is_roc5_minus_roc10(self):
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None
        assert pytest.approx(result.acceleration, abs=1e-6) == result.roc_5 - result.roc_10

    def test_acceleration_value_correct(self):
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None
        expected_roc_5 = 10.0
        expected_roc_10 = (110.0 - 90.0) / 90.0 * 100.0
        assert pytest.approx(result.acceleration, abs=1e-6) == expected_roc_5 - expected_roc_10


class TestComputeFeaturesVwap:

    def test_missing_vwap_uses_zero_deviation_does_not_return_none(self):
        bars = _make_deterministic_bars()
        # vwap is already None in _make_deterministic_bars
        result = compute_features("TEST", bars)
        assert result is not None
        assert result.vwap_deviation == 0.0

    def test_vwap_none_does_not_disqualify_symbol(self):
        bars = _make_flat_bars(n=30)
        for b in bars:
            b["vwap"] = None
        result = compute_features("TEST", bars)
        assert result is not None

    def test_vwap_zero_does_not_disqualify_symbol(self):
        bars = _make_flat_bars(n=30)
        for b in bars:
            b["vwap"] = 0.0
        result = compute_features("TEST", bars)
        assert result is not None
        assert result.vwap_deviation == 0.0

    def test_vwap_deviation_correct_when_present(self):
        bars = _make_flat_bars(n=30, close=110.0)
        # Use actual close of the last bar (slightly above 110 due to variation)
        close_now = bars[-1]["close"]
        vwap_val = 100.0
        bars[-1]["vwap"] = vwap_val
        result = compute_features("TEST", bars)
        assert result is not None
        expected_deviation = (close_now - vwap_val) / vwap_val
        assert pytest.approx(result.vwap_deviation, abs=1e-6) == expected_deviation


class TestComputeFeaturesRangePosition:

    def test_range_position_is_0_5_when_high_equals_low(self):
        # Make all bars identical so high_20 == low_20
        bars = [_make_bar(100.0, high=100.0, low=100.0, idx=i) for i in range(30)]
        # Override close variation so constant-close guard doesn't fire
        for i, b in enumerate(bars):
            b["close"] = 100.0 + i * 0.01
        # Still all highs and lows are 100 (flat range)
        result = compute_features("TEST", bars)
        assert result is not None
        assert result.range_position == 0.5

    def test_range_position_between_0_and_1(self):
        bars = _make_flat_bars(n=30)
        result = compute_features("TEST", bars)
        assert result is not None
        assert 0.0 <= result.range_position <= 1.0


class TestComputeFeaturesRawScore:

    def test_raw_score_formula_with_known_inputs(self):
        """
        With deterministic bars:
          roc_20 = 37.5, roc_10 ≈ 22.222, roc_5 = 10.0
          acceleration = 10 - 22.222 = -12.222
          vwap_deviation = 0.0 (no vwap)

        raw_score = roc_20*0.35 + roc_10*0.25 + roc_5*0.15
                  + acceleration*0.15 + vwap_deviation*100*0.10
        """
        bars = _make_deterministic_bars()
        result = compute_features("TEST", bars)
        assert result is not None

        roc_20 = 37.5
        roc_10 = (110.0 - 90.0) / 90.0 * 100.0
        roc_5 = 10.0
        accel = roc_5 - roc_10
        vwap_dev = 0.0

        expected = (
            roc_20 * 0.35
            + roc_10 * 0.25
            + roc_5 * 0.15
            + accel * 0.15
            + vwap_dev * 100.0 * 0.10
        )
        assert pytest.approx(result.raw_score, abs=1e-6) == expected

    def test_normalized_score_is_zero_placeholder(self):
        """features.py sets normalized_score=0.0 — scorer.py populates it."""
        bars = _make_flat_bars(n=30)
        result = compute_features("TEST", bars)
        assert result is not None
        assert result.normalized_score == 0.0

    def test_symbol_propagated_correctly(self):
        bars = _make_flat_bars(n=30)
        result = compute_features("NVDA", bars)
        assert result is not None
        assert result.symbol == "NVDA"
