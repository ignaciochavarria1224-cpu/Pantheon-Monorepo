"""
Feature engineering for Olympus ranking engine.
Pure-function module. No classes. No side effects. No I/O.
Takes bar data for a single symbol and computes all scoring inputs.

Zero external dependencies beyond stdlib. Testable with zero network or filesystem access.
"""

from __future__ import annotations

from typing import Optional

from core.models import BarFeatures

_MIN_BARS = 25
_RVOL_WINDOW = 20
_RANGE_WINDOW = 20


def compute_features(symbol: str, bars: list[dict]) -> Optional[BarFeatures]:
    """
    Compute all scoring inputs for a single symbol.

    Args:
        symbol: Ticker symbol.
        bars: List of normalized bar dicts from Phase 1's normalizer — each has
              symbol, timestamp, open, high, low, close, volume, vwap.
              May be in any order; will be sorted oldest-first internally.

    Returns:
        BarFeatures with raw_score populated and normalized_score=0.0 (placeholder,
        set by scorer.py). Returns None if there are insufficient bars or
        degenerate data conditions.
    """
    if not bars or len(bars) < _MIN_BARS:
        return None

    # Sort bars oldest-first by timestamp
    try:
        bars = sorted(bars, key=lambda b: b["timestamp"])
    except Exception:
        return None

    # Extract price and volume series
    try:
        closes = [float(b["close"]) for b in bars]
        volumes = [float(b["volume"]) for b in bars]
        highs = [float(b["high"]) for b in bars]
        lows = [float(b["low"]) for b in bars]
    except (KeyError, TypeError, ValueError):
        return None

    # Guard: constant close prices (no signal)
    if len(set(closes)) == 1:
        return None

    # Guard: all volume zero (bad data)
    if all(v == 0.0 for v in volumes):
        return None

    latest = bars[-1]
    close_now = closes[-1]
    volume_now = volumes[-1]

    # --- Rate of Change ---
    roc_5 = _roc(closes, 5)
    roc_10 = _roc(closes, 10)
    roc_20 = _roc(closes, 20)

    # Any window failure disqualifies the symbol
    if roc_5 is None or roc_10 is None or roc_20 is None:
        return None

    # --- Acceleration: is short-term momentum intensifying? ---
    acceleration = roc_5 - roc_10

    # --- Relative Volume ---
    rvol_vols = volumes[-_RVOL_WINDOW:]
    mean_vol = sum(rvol_vols) / len(rvol_vols) if rvol_vols else 0.0
    if mean_vol == 0.0:
        return None
    rvol = volume_now / mean_vol

    # --- VWAP Deviation ---
    vwap = latest.get("vwap")
    if vwap is None or vwap == 0.0:
        vwap_deviation = 0.0
    else:
        try:
            vwap_deviation = (close_now - float(vwap)) / float(vwap)
        except (ZeroDivisionError, TypeError, ValueError):
            vwap_deviation = 0.0

    # --- Range Position ---
    range_bars_high = highs[-_RANGE_WINDOW:]
    range_bars_low = lows[-_RANGE_WINDOW:]
    high_20 = max(range_bars_high)
    low_20 = min(range_bars_low)

    if high_20 == low_20:
        range_position = 0.5
    else:
        range_position = (close_now - low_20) / (high_20 - low_20)

    # --- Raw Score (composite) ---
    # RVOL and range_position are stored but not included in raw_score.
    # They are reserved for Phase 3's entry filtering.
    raw_score = (
        roc_20 * 0.35
        + roc_10 * 0.25
        + roc_5 * 0.15
        + acceleration * 0.15
        + vwap_deviation * 100.0 * 0.10
    )

    return BarFeatures(
        symbol=symbol,
        timestamp=latest["timestamp"],
        close=close_now,
        volume=volume_now,
        roc_5=roc_5,
        roc_10=roc_10,
        roc_20=roc_20,
        acceleration=acceleration,
        rvol=rvol,
        vwap_deviation=vwap_deviation,
        range_position=range_position,
        raw_score=raw_score,
        normalized_score=0.0,  # populated by scorer.py
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _roc(closes: list[float], n: int) -> Optional[float]:
    """
    Rate of change over n bars.
    roc_n = (close_now - close_n_bars_ago) / close_n_bars_ago * 100

    Returns None if there aren't enough bars or the reference close is zero.
    """
    if len(closes) < n + 1:
        return None
    close_n_ago = closes[-(n + 1)]
    if close_n_ago == 0.0:
        return None
    return (closes[-1] - close_n_ago) / close_n_ago * 100.0
