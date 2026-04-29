"""
Local disk cache for historical bar data.
Caches parquet files keyed by symbol + date range + timeframe.
Avoids redundant API calls during development iteration.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from core.logger import get_logger

logger = get_logger(__name__)

DateLike = Union[str, date, datetime]


def _cache_key(symbol: str, start: DateLike, end: DateLike, timeframe: str) -> str:
    """
    Build a deterministic filename-safe cache key from (symbol, start, end, timeframe).
    Format: {SYMBOL}_{start}_{end}_{timeframe_safe}.parquet
    """
    def _to_str(d: DateLike) -> str:
        if isinstance(d, datetime):
            return d.strftime("%Y%m%d")
        if isinstance(d, date):
            return d.strftime("%Y%m%d")
        # string — strip separators
        return str(d).replace("-", "").replace("/", "")[:8]

    tf_safe = timeframe.replace(" ", "").replace("/", "_")
    raw = f"{symbol.upper()}_{_to_str(start)}_{_to_str(end)}_{tf_safe}"

    # Hash the key to keep filenames short and safe for all filesystems
    key_hash = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{symbol.upper()}_{tf_safe}_{key_hash}.parquet"


class DataCache:
    """
    Disk-backed parquet cache for historical bar DataFrames.

    Cache structure:
        {CACHE_DIR}/{cache_key}.parquet

    Each file stores a normalized bar DataFrame for one (symbol, range, timeframe).
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        logger.debug("DataCache initialized at: %s", self._dir)

    def get(
        self,
        symbol: str,
        start: DateLike,
        end: DateLike,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """
        Return cached DataFrame for (symbol, start, end, timeframe), or None if not cached.
        """
        key = _cache_key(symbol, start, end, timeframe)
        path = self._dir / key

        if path.exists():
            try:
                df = pd.read_parquet(path)
                logger.debug("Cache HIT: %s (%d rows)", key, len(df))
                return df
            except Exception as exc:
                logger.warning("Cache read failed for %s: %s — treating as miss", key, exc)
                return None

        logger.debug("Cache MISS: %s", key)
        return None

    def set(
        self,
        symbol: str,
        start: DateLike,
        end: DateLike,
        timeframe: str,
        df: pd.DataFrame,
    ) -> None:
        """
        Write DataFrame to disk cache for (symbol, start, end, timeframe).
        """
        if df is None or df.empty:
            logger.debug("Cache SET skipped — empty DataFrame for %s", symbol)
            return

        key = _cache_key(symbol, start, end, timeframe)
        path = self._dir / key

        try:
            df.to_parquet(path, index=False, engine="pyarrow")
            logger.debug("Cache SET: %s (%d rows, %.1f KB)", key, len(df), path.stat().st_size / 1024)
        except Exception as exc:
            logger.error("Cache write failed for %s: %s", key, exc)
            raise

    def invalidate(self, symbol: str) -> int:
        """
        Delete all cached files for a given symbol. Returns count of files removed.
        """
        symbol_upper = symbol.upper()
        removed = 0
        for path in self._dir.glob(f"{symbol_upper}_*.parquet"):
            try:
                path.unlink()
                removed += 1
                logger.debug("Cache invalidated: %s", path.name)
            except Exception as exc:
                logger.warning("Could not delete cache file %s: %s", path.name, exc)

        logger.info("Cache invalidated %d file(s) for symbol: %s", removed, symbol_upper)
        return removed

    def list_keys(self) -> list[str]:
        """Return all cache file names currently on disk."""
        return [p.name for p in sorted(self._dir.glob("*.parquet"))]

    def size_on_disk_mb(self) -> float:
        """Return total cache size in MB."""
        total = sum(p.stat().st_size for p in self._dir.glob("*.parquet"))
        return total / (1024 * 1024)
