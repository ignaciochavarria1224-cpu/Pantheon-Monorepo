"""
Market data fetcher for Olympus.
Uses alpaca-py to fetch real-time latest bars and historical OHLCV bars.
Handles batch requests, timezone conversion, market-hours filtering, and retries.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo

import pandas as pd
import pytz
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

_ET = pytz.timezone("America/New_York")
_UTC = pytz.utc

# Maximum symbols per batch request (Alpaca supports multi-symbol natively)
_MAX_BATCH_SIZE = 200
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0  # seconds — doubles on each retry


def _parse_timeframe(tf_str: str) -> TimeFrame:
    """
    Convert a human-readable timeframe string to an alpaca-py TimeFrame.
    Supported: '1Min', '5Min', '15Min', '30Min', '1Hour', '1Day'
    """
    tf_map: dict[str, TimeFrame] = {
        "1min":  TimeFrame(1,  TimeFrameUnit.Minute),
        "5min":  TimeFrame(5,  TimeFrameUnit.Minute),
        "15min": TimeFrame(15, TimeFrameUnit.Minute),
        "30min": TimeFrame(30, TimeFrameUnit.Minute),
        "1hour": TimeFrame(1,  TimeFrameUnit.Hour),
        "1day":  TimeFrame(1,  TimeFrameUnit.Day),
    }
    key = tf_str.lower().replace(" ", "")
    if key not in tf_map:
        raise ValueError(
            f"Unsupported timeframe '{tf_str}'. "
            f"Supported values: {list(tf_map.keys())}"
        )
    return tf_map[key]


def _flatten_bars_response(bars_response) -> pd.DataFrame:
    """
    Convert alpaca-py StockBarsResponse (multi-index or dict) into a flat DataFrame
    with 'symbol' as a plain column (not an index level).
    """
    # bars_response.df returns a multi-index DataFrame: (symbol, timestamp)
    try:
        raw_df = bars_response.df
    except Exception:
        raw_df = None

    if raw_df is None or (hasattr(raw_df, "empty") and raw_df.empty):
        return pd.DataFrame()

    # Reset multi-index so symbol and timestamp become regular columns
    df = raw_df.reset_index()

    # Ensure column names are lowercase
    df.columns = [c.lower() for c in df.columns]

    # Rename 'symbol' if it came through as 'level_0' or similar
    if "symbol" not in df.columns and "level_0" in df.columns:
        df = df.rename(columns={"level_0": "symbol"})

    return df


def _to_et(ts: pd.Series) -> pd.Series:
    """Convert a UTC-aware timestamp Series to US/Eastern."""
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    return ts.dt.tz_convert(_ET)


def _filter_market_hours(df: pd.DataFrame, market_open: str, market_close: str) -> pd.DataFrame:
    """
    Keep only bars whose timestamp falls within market hours (inclusive of open, exclusive of close).
    Operates on an ET-timezone-aware 'timestamp' column.
    """
    if df.empty or "timestamp" not in df.columns:
        return df

    open_h, open_m   = map(int, market_open.split(":"))
    close_h, close_m = map(int, market_close.split(":"))

    open_minutes  = open_h  * 60 + open_m
    close_minutes = close_h * 60 + close_m

    def _in_market(ts: datetime) -> bool:
        bar_minutes = ts.hour * 60 + ts.minute
        return open_minutes <= bar_minutes < close_minutes

    mask = df["timestamp"].apply(_in_market)
    return df[mask].reset_index(drop=True)


def _retry(fn, *args, attempts: int = _RETRY_ATTEMPTS, base_delay: float = _RETRY_BASE_DELAY, **kwargs):
    """
    Call fn(*args, **kwargs) with exponential backoff retry on any exception.
    Raises the last exception if all attempts fail.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Attempt %d/%d failed: %s — retrying in %.1fs",
                attempt, attempts, exc, delay,
            )
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


class DataFetcher:
    """
    Fetches market data from Alpaca (paper feed by default).
    Handles batch requests, timezone conversion, market-hours filtering, and retries.
    """

    def __init__(self) -> None:
        self._client = StockHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
        self._feed = settings.DATA_FEED
        logger.info("DataFetcher initialized (feed=%s)", self._feed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_latest_bars(
        self,
        symbols: Union[str, list[str]],
    ) -> pd.DataFrame:
        """
        Fetch the latest available bar for each symbol.
        Returns a flat DataFrame with columns: symbol, timestamp, open, high, low, close, volume, vwap.
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        symbols = [s.upper() for s in symbols]
        logger.info("Fetching latest bars for %d symbol(s)", len(symbols))
        t0 = time.monotonic()

        def _do_fetch():
            req = StockLatestBarRequest(
                symbol_or_symbols=symbols,
                feed=self._feed,
            )
            return self._client.get_stock_latest_bar(req)

        try:
            response = _retry(_do_fetch)
            latency = time.monotonic() - t0
        except Exception as exc:
            logger.error("fetch_latest_bars failed for %d symbols: %s", len(symbols), exc)
            raise

        # Convert dict[symbol → Bar] to flat DataFrame
        rows = []
        for sym, bar in response.items():
            rows.append({
                "symbol":    sym,
                "timestamp": bar.timestamp,
                "open":      float(bar.open),
                "high":      float(bar.high),
                "low":       float(bar.low),
                "close":     float(bar.close),
                "volume":    float(bar.volume),
                "vwap":      float(bar.vwap) if bar.vwap is not None else None,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df["timestamp"] = _to_et(df["timestamp"])

        logger.info(
            "fetch_latest_bars: got %d bars for %d symbols in %.2fs",
            len(df), len(symbols), latency,
        )
        return df

    def fetch_historical_bars(
        self,
        symbols: Union[str, list[str]],
        start: datetime,
        end: Optional[datetime] = None,
        timeframe: Optional[str] = None,
        filter_market_hours: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV bars for one or more symbols.
        Returns a flat DataFrame with columns: symbol, timestamp, open, high, low, close, volume, vwap.

        Args:
            symbols: Single symbol or list of symbols.
            start: Start datetime (UTC or ET).
            end: End datetime. Defaults to now.
            timeframe: Bar resolution string e.g. '5Min', '1Hour'. Defaults to settings.BAR_TIMEFRAME.
            filter_market_hours: If True, remove bars outside 09:30–16:00 ET.
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        symbols = [s.upper() for s in symbols]

        if end is None:
            end = datetime.now(_UTC)
        if timeframe is None:
            timeframe = settings.BAR_TIMEFRAME

        alpaca_tf = _parse_timeframe(timeframe)

        logger.info(
            "Fetching historical bars: %d symbol(s), %s -> %s, tf=%s",
            len(symbols),
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
            timeframe,
        )
        t0 = time.monotonic()

        all_frames: list[pd.DataFrame] = []

        # Alpaca supports multi-symbol in one call — send in batches of _MAX_BATCH_SIZE
        for batch_start in range(0, len(symbols), _MAX_BATCH_SIZE):
            batch = symbols[batch_start: batch_start + _MAX_BATCH_SIZE]

            def _do_fetch(b=batch):
                req = StockBarsRequest(
                    symbol_or_symbols=b,
                    timeframe=alpaca_tf,
                    start=start,
                    end=end,
                    feed=self._feed,
                )
                return self._client.get_stock_bars(req)

            try:
                response = _retry(_do_fetch)
            except Exception as exc:
                logger.error(
                    "fetch_historical_bars batch failed (%d symbols): %s", len(batch), exc
                )
                raise

            batch_df = _flatten_bars_response(response)
            if not batch_df.empty:
                all_frames.append(batch_df)

        latency = time.monotonic() - t0

        if not all_frames:
            logger.warning("fetch_historical_bars: no data returned for any symbol")
            return pd.DataFrame()

        df = pd.concat(all_frames, ignore_index=True)

        # Normalize timestamps to ET
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df["timestamp"] = _to_et(df["timestamp"])

        # Ensure vwap column exists
        if "vwap" not in df.columns:
            df["vwap"] = None

        # Add symbol column if flattening produced it as index
        if "symbol" not in df.columns:
            logger.warning("fetch_historical_bars: 'symbol' column missing from response")

        # Filter to market hours if requested and timeframe is intraday
        if filter_market_hours and timeframe.lower() not in ("1day",):
            before = len(df)
            df = _filter_market_hours(df, settings.MARKET_OPEN, settings.MARKET_CLOSE)
            logger.debug(
                "Market-hours filter: %d → %d bars (removed %d)", before, len(df), before - len(df)
            )

        logger.info(
            "fetch_historical_bars: got %d total bars for %d symbols in %.2fs",
            len(df), len(symbols), latency,
        )
        return df
