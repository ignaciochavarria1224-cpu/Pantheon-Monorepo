"""
Phase 5 backtesting harness for Olympus.

Standalone script that loads one symbol's 5-minute bar cache from data/cache/,
runs a backtesting.py simulation using a strategy that mimics Olympus entry
logic, and prints summary statistics.

Entry logic mirrors the Olympus ranking engine:
  - A momentum signal is computed from the same weighted ROC formula used in
    core/ranking/features.py (roc_20, roc_10, roc_5, acceleration, vwap_deviation).
  - The signal is normalized to 0–100 via a rolling percentile rank over a 50-bar
    window, matching how scorer.py normalizes raw scores across the universe.
  - A long entry fires when the normalized signal >= 60 (Olympus long threshold).
  - The stop is placed at entry_price − 2 × ATR(14), mirroring the ATR-based
    stop logic in core/trading/sizing.py.

No imports from core/ — this is a fully self-contained read-only tool.
Run from the olympus/ directory:
    python tools/backtest_runner.py
"""

from __future__ import annotations

import os
import glob

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy


# ---------------------------------------------------------------------------
# Indicator helpers (pure numpy — called via Strategy.I())
# ---------------------------------------------------------------------------

def _compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range using Wilder's smoothing."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]

    atr = np.full(n, np.nan)
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def _compute_momentum_signal(
    close: np.ndarray,
    vwap: np.ndarray,
    norm_window: int = 50,
) -> np.ndarray:
    """
    Compute a normalized momentum signal (0–100) that mirrors the Olympus
    raw_score formula from core/ranking/features.py, then percentile-ranks it
    over a rolling window to approximate scorer.py's cross-symbol normalization.
    """
    n = len(close)
    raw = np.full(n, np.nan)

    for i in range(20, n):
        c = close[: i + 1]
        if len(c) < 21:
            continue
        roc_5 = (c[-1] - c[-6]) / c[-6] * 100.0 if c[-6] != 0.0 else 0.0
        roc_10 = (c[-1] - c[-11]) / c[-11] * 100.0 if c[-11] != 0.0 else 0.0
        roc_20 = (c[-1] - c[-21]) / c[-21] * 100.0 if c[-21] != 0.0 else 0.0
        accel = roc_5 - roc_10
        vd = vwap[i]
        vwap_dev = (c[-1] - vd) / vd * 100.0 if vd != 0.0 else 0.0
        raw[i] = (
            roc_20 * 0.35
            + roc_10 * 0.25
            + roc_5 * 0.15
            + accel * 0.15
            + vwap_dev * 0.10
        )

    # Rolling percentile rank → 0–100
    signal = np.full(n, 50.0)
    for i in range(20, n):
        start = max(20, i - norm_window + 1)
        window = raw[start : i + 1]
        valid = window[~np.isnan(window)]
        if len(valid) > 1:
            signal[i] = float(np.sum(valid[:-1] < valid[-1]) / (len(valid) - 1) * 100.0)
        elif len(valid) == 1:
            signal[i] = 50.0
    return signal


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

class OlympusMomentumStrategy(Strategy):
    """
    Single-symbol momentum strategy mimicking Olympus Phase 3 entry logic.

    Entry:  normalized_signal >= 60  (mirrors long threshold in scorer.py)
    Stop:   entry_price − 2 × ATR(14)  (mirrors ATR-based stop in sizing.py)
    Exit:   stop-loss only (backtesting.py manages the sl= order)
    """

    atr_period: int = 14
    entry_threshold: float = 60.0
    atr_multiplier: float = 2.0

    def init(self) -> None:
        vwap_arr = self.data.df["vwap"].to_numpy(dtype=float)
        self.atr = self.I(
            _compute_atr,
            self.data.High,
            self.data.Low,
            self.data.Close,
            self.atr_period,
            name="ATR",
        )
        self.signal = self.I(
            _compute_momentum_signal,
            self.data.Close,
            vwap_arr,
            name="MomentumSignal",
        )

    def next(self) -> None:
        if not self.position:
            if self.signal[-1] >= self.entry_threshold and not np.isnan(self.atr[-1]):
                stop_price = self.data.Close[-1] - self.atr_multiplier * self.atr[-1]
                self.buy(sl=stop_price)
        # Exits are handled exclusively by the stop-loss order placed at entry.


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _find_cache_file() -> str:
    """Return path to the AAPL parquet cache, falling back to any available file."""
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
    cache_dir = os.path.normpath(cache_dir)

    preferred = glob.glob(os.path.join(cache_dir, "AAPL_*.parquet"))
    if preferred:
        return preferred[0]

    all_files = glob.glob(os.path.join(cache_dir, "*.parquet"))
    if not all_files:
        raise FileNotFoundError(f"No parquet files found in {cache_dir}")
    return all_files[0]


def main() -> None:
    cache_path = _find_cache_file()
    symbol = os.path.basename(cache_path).split("_")[0]
    print(f"Loading cache: {cache_path}")

    df = pd.read_parquet(cache_path)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # backtesting.py requires a DatetimeIndex and capitalized OHLCV columns.
    df.index = pd.DatetimeIndex(df["timestamp"])
    df = df.rename(columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    # Keep vwap accessible for the indicator function via self.data.df
    df = df[["Open", "High", "Low", "Close", "Volume", "vwap"]]
    df.index = df.index.tz_localize(None)  # backtesting.py requires tz-naive index

    print(f"Symbol: {symbol}  |  Bars loaded: {len(df)}")
    print(f"Date range: {df.index[0]} -> {df.index[-1]}")
    print()

    bt = Backtest(
        df,
        OlympusMomentumStrategy,
        cash=100_000,
        commission=0.001,
        exclusive_orders=True,
    )
    stats = bt.run()

    print("=" * 60)
    print(f"BACKTEST RESULTS - {symbol}  (Olympus Momentum Strategy)")
    print("=" * 60)
    relevant_keys = [
        "Start",
        "End",
        "Duration",
        "Exposure Time [%]",
        "Equity Final [$]",
        "Equity Peak [$]",
        "Return [%]",
        "Buy & Hold Return [%]",
        "Return (Ann.) [%]",
        "Volatility (Ann.) [%]",
        "Sharpe Ratio",
        "Sortino Ratio",
        "Calmar Ratio",
        "Max. Drawdown [%]",
        "Avg. Drawdown [%]",
        "# Trades",
        "Win Rate [%]",
        "Best Trade [%]",
        "Worst Trade [%]",
        "Avg. Trade [%]",
        "Profit Factor",
        "Expectancy [%]",
        "SQN",
    ]
    for key in relevant_keys:
        if key in stats:
            print(f"  {key:<30} {stats[key]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
