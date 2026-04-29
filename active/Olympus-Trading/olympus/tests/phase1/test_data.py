"""
Phase 1 tests — data fetching and normalization.
Run with: pytest tests/phase1/test_data.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz
import pytest

# Add olympus root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ---------------------------------------------------------------------------
# Normalizer tests (pure functions — no network required)
# ---------------------------------------------------------------------------

class TestNormalizerPure:
    """Tests for core/data/normalizer.py — no API calls needed."""

    def _make_raw_df(self, n: int = 3) -> pd.DataFrame:
        et = pytz.timezone("America/New_York")
        rows = []
        for i in range(n):
            rows.append({
                "symbol":    "AAPL",
                "timestamp": datetime.now(pytz.utc) - timedelta(minutes=i * 5),
                "open":      150.0 + i,
                "high":      152.0 + i,
                "low":       149.0 + i,
                "close":     151.0 + i,
                "volume":    100000.0 + i * 1000,
                "vwap":      150.5 + i,
            })
        return pd.DataFrame(rows)

    def test_normalize_returns_list_of_dicts(self):
        from core.data.normalizer import normalize_bars
        df = self._make_raw_df(3)
        records = normalize_bars(df)
        assert isinstance(records, list)
        assert len(records) == 3
        assert isinstance(records[0], dict)

    def test_normalize_schema_keys(self):
        from core.data.normalizer import normalize_bars, SCHEMA_COLUMNS
        df = self._make_raw_df(2)
        records = normalize_bars(df)
        for rec in records:
            for col in SCHEMA_COLUMNS:
                assert col in rec, f"Missing key '{col}' in normalized record"

    def test_normalize_numeric_types(self):
        from core.data.normalizer import normalize_bars
        df = self._make_raw_df(2)
        records = normalize_bars(df)
        for rec in records:
            for col in ["open", "high", "low", "close", "volume"]:
                assert isinstance(rec[col], float), f"'{col}' should be float, got {type(rec[col])}"

    def test_normalize_timestamp_is_et_aware(self):
        from core.data.normalizer import normalize_bars
        df = self._make_raw_df(2)
        records = normalize_bars(df)
        et = pytz.timezone("America/New_York")
        for rec in records:
            ts = rec["timestamp"]
            assert ts.tzinfo is not None, "timestamp must be timezone-aware"

    def test_normalize_zero_volume_preserved(self):
        from core.data.normalizer import normalize_bars
        df = self._make_raw_df(1)
        df["volume"] = 0.0
        records = normalize_bars(df)
        assert records[0]["volume"] == 0.0

    def test_normalize_missing_vwap_is_none(self):
        from core.data.normalizer import normalize_bars
        df = self._make_raw_df(1)
        del df["vwap"]  # remove vwap column
        records = normalize_bars(df)
        assert records[0]["vwap"] is None

    def test_normalize_nan_ohlcv_filled_with_zero(self):
        from core.data.normalizer import normalize_bars
        import numpy as np
        df = self._make_raw_df(1)
        df["close"] = float("nan")
        records = normalize_bars(df)
        assert records[0]["close"] == 0.0

    def test_normalize_empty_df_returns_empty_list(self):
        from core.data.normalizer import normalize_bars
        records = normalize_bars(pd.DataFrame())
        assert records == []

    def test_validate_schema_passes_on_valid_records(self):
        from core.data.normalizer import normalize_bars, validate_schema
        df = self._make_raw_df(3)
        records = normalize_bars(df)
        valid, errors = validate_schema(records)
        assert valid, f"Schema validation failed: {errors}"

    def test_normalize_to_df_returns_dataframe(self):
        from core.data.normalizer import normalize_bars_to_df, SCHEMA_COLUMNS
        df = self._make_raw_df(3)
        result = normalize_bars_to_df(df)
        assert isinstance(result, pd.DataFrame)
        for col in SCHEMA_COLUMNS:
            assert col in result.columns


# ---------------------------------------------------------------------------
# Cache tests (disk I/O — no network required)
# ---------------------------------------------------------------------------

class TestDataCache:
    """Tests for core/data/cache.py."""

    @pytest.fixture
    def cache(self, tmp_path):
        from core.data.cache import DataCache
        return DataCache(tmp_path)

    def _sample_df(self) -> pd.DataFrame:
        et = pytz.timezone("America/New_York")
        return pd.DataFrame([{
            "symbol":    "MSFT",
            "timestamp": datetime.now(et),
            "open": 300.0, "high": 305.0, "low": 298.0, "close": 302.0,
            "volume": 50000.0, "vwap": 301.5,
        }])

    def test_cache_miss_returns_none(self, cache):
        result = cache.get("MSFT", "20240101", "20240110", "5Min")
        assert result is None

    def test_cache_set_and_get_roundtrip(self, cache):
        df = self._sample_df()
        cache.set("MSFT", "20240101", "20240110", "5Min", df)
        result = cache.get("MSFT", "20240101", "20240110", "5Min")
        assert result is not None
        assert len(result) == 1
        assert result["symbol"].iloc[0] == "MSFT"

    def test_cache_key_is_deterministic(self, cache):
        df = self._sample_df()
        cache.set("AAPL", "20240101", "20240110", "5Min", df)
        # Different date format — should still miss (different key)
        result = cache.get("AAPL", "2024-01-01", "2024-01-10", "5Min")
        # Both formats should produce same key via _to_str normalization
        assert result is not None  # same canonical key

    def test_cache_invalidate(self, cache):
        df = self._sample_df()
        cache.set("NVDA", "20240101", "20240110", "5Min", df)
        cache.set("NVDA", "20240101", "20240120", "5Min", df)
        removed = cache.invalidate("NVDA")
        assert removed == 2
        assert cache.get("NVDA", "20240101", "20240110", "5Min") is None

    def test_cache_empty_df_not_written(self, cache):
        cache.set("XYZ", "20240101", "20240110", "5Min", pd.DataFrame())
        result = cache.get("XYZ", "20240101", "20240110", "5Min")
        assert result is None


# ---------------------------------------------------------------------------
# Fetcher integration tests (requires valid Alpaca credentials in .env)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDataFetcherIntegration:
    """
    Integration tests that hit the Alpaca API.
    Requires valid credentials in .env. Skip with: pytest -m "not integration"
    """

    @pytest.fixture(scope="class")
    def fetcher(self):
        from core.data.fetcher import DataFetcher
        return DataFetcher()

    def test_fetch_latest_bars_single_symbol(self, fetcher):
        df = fetcher.fetch_latest_bars("AAPL")
        assert isinstance(df, pd.DataFrame)
        # May be empty outside market hours — just check no exception raised

    def test_fetch_latest_bars_multi_symbol(self, fetcher):
        df = fetcher.fetch_latest_bars(["AAPL", "MSFT", "GOOGL"])
        assert isinstance(df, pd.DataFrame)

    def test_fetch_historical_returns_expected_columns(self, fetcher):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        df = fetcher.fetch_historical_bars("AAPL", start=start, end=end, timeframe="5Min")
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            for col in ["symbol", "timestamp", "open", "high", "low", "close", "volume"]:
                assert col in df.columns, f"Missing column: {col}"

    def test_fetch_historical_timestamps_are_et(self, fetcher):
        import pytz
        et = pytz.timezone("America/New_York")
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        df = fetcher.fetch_historical_bars("MSFT", start=start, end=end, timeframe="5Min")
        if not df.empty:
            ts = df["timestamp"].iloc[0]
            assert ts.tzinfo is not None

    def test_fetch_historical_market_hours_filter(self, fetcher):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        df = fetcher.fetch_historical_bars("MSFT", start=start, end=end, timeframe="5Min",
                                           filter_market_hours=True)
        if not df.empty:
            for ts in df["timestamp"]:
                hour_minute = ts.hour * 60 + ts.minute
                assert 9 * 60 + 30 <= hour_minute < 16 * 60, \
                    f"Bar outside market hours: {ts}"
