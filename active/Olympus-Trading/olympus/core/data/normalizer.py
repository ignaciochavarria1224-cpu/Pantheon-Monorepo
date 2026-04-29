"""
Data normalization pipeline for Olympus.
Pure-function layer: accepts raw bar data and returns a consistently structured format.
No business logic. Data cleaning and structure only.

Output format: list[dict]
Each dict is guaranteed to have:
    symbol      str
    timestamp   datetime (timezone-aware, US/Eastern)
    open        float64
    high        float64
    low         float64
    close       float64
    volume      float64
    vwap        float64 | None
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytz

from core.logger import get_logger

logger = get_logger(__name__)

_ET = pytz.timezone("America/New_York")

# Canonical output columns in guaranteed order
SCHEMA_COLUMNS = ["symbol", "timestamp", "open", "high", "low", "close", "volume", "vwap"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "vwap"]


def normalize_bars(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Normalize a raw bar DataFrame (as returned by DataFetcher) into a list of
    canonical bar dicts.

    Input: flat DataFrame with at minimum columns — symbol, timestamp, open,
           high, low, close, volume. vwap is optional.

    Output: list of dicts matching SCHEMA_COLUMNS. vwap is None if not present
            or not computable.

    Guarantees:
    - All numeric fields are float64 (NaN → None for vwap, 0.0 for price/vol)
    - Zero-volume bars are preserved (volume = 0.0), never dropped
    - No NaN propagation for ohlcv fields
    - timestamp is timezone-aware ET datetime
    """
    if df is None or df.empty:
        logger.debug("normalize_bars received empty DataFrame — returning []")
        return []

    df = df.copy()

    # --- Ensure required columns exist ---
    required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"normalize_bars: missing required columns: {missing}")

    # --- Add vwap column if absent ---
    if "vwap" not in df.columns:
        df["vwap"] = None

    # --- Normalize timestamp to ET timezone-aware ---
    df["timestamp"] = _normalize_timestamps(df["timestamp"])

    # --- Coerce numeric columns to float64 ---
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    df["vwap"] = pd.to_numeric(df["vwap"], errors="coerce").astype("float64")

    # --- Handle NaN in ohlcv — fill with 0.0 to prevent downstream divide-by-zero ---
    for col in ["open", "high", "low", "close", "volume"]:
        nan_count = df[col].isna().sum()
        if nan_count > 0:
            logger.warning(
                "normalize_bars: %d NaN values in column '%s' — filling with 0.0",
                nan_count, col,
            )
        df[col] = df[col].fillna(0.0)

    # vwap: keep as NaN → will be converted to None in output dicts
    # No fill — None is the correct signal for "not available"

    # --- Ensure symbol is string ---
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    # --- Build output list of dicts ---
    records: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        vwap_val = getattr(row, "vwap", None)
        # Convert NaN to None
        if vwap_val is not None and pd.isna(vwap_val):
            vwap_val = None
        elif isinstance(vwap_val, float) and not pd.isna(vwap_val):
            pass  # keep as float64

        records.append({
            "symbol":    str(row.symbol),
            "timestamp": row.timestamp,
            "open":      float(row.open),
            "high":      float(row.high),
            "low":       float(row.low),
            "close":     float(row.close),
            "volume":    float(row.volume),
            "vwap":      vwap_val,
        })

    logger.debug("normalize_bars: produced %d normalized records", len(records))
    return records


def normalize_bars_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience wrapper — returns normalized data as a DataFrame instead of
    a list of dicts. Uses normalize_bars internally for consistency.
    """
    records = normalize_bars(df)
    if not records:
        return pd.DataFrame(columns=SCHEMA_COLUMNS)
    return pd.DataFrame(records, columns=SCHEMA_COLUMNS)


def validate_schema(records: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    """
    Validate that a list of normalized bar dicts matches the expected schema.
    Returns (is_valid, list_of_errors).
    Used by main.py gate check.
    """
    if not records:
        return False, ["No records to validate"]

    errors: list[str] = []
    sample = records[0]

    # Check all expected keys present
    for col in SCHEMA_COLUMNS:
        if col not in sample:
            errors.append(f"Missing key: '{col}'")

    # Check numeric types
    for col in NUMERIC_COLUMNS:
        if col in sample and col != "vwap":
            val = sample[col]
            if not isinstance(val, (int, float)):
                errors.append(f"Column '{col}' is not numeric: {type(val)}")

    # Check timestamp is timezone-aware
    ts = sample.get("timestamp")
    if ts is not None and hasattr(ts, "tzinfo"):
        if ts.tzinfo is None:
            errors.append("timestamp is not timezone-aware")
    elif ts is not None:
        errors.append(f"timestamp has unexpected type: {type(ts)}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_timestamps(ts_series: pd.Series) -> pd.Series:
    """
    Convert a timestamp series to US/Eastern timezone-aware datetimes.
    Handles: UTC-aware Timestamps, naive Timestamps (assumed UTC), strings.
    """
    # Convert to datetime if needed
    ts_series = pd.to_datetime(ts_series, utc=True, errors="coerce")

    # Convert UTC → ET
    if hasattr(ts_series, "dt"):
        return ts_series.dt.tz_convert(_ET)

    # Fallback for object series
    def _convert(ts: Any) -> Any:
        if ts is None or (isinstance(ts, float) and pd.isna(ts)):
            return None
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            return ts.astimezone(_ET)
        return _ET.localize(ts)

    return ts_series.apply(_convert)
