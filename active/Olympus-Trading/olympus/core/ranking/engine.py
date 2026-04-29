"""
Ranking engine for Olympus.
Orchestrates data fetching, feature computation, scoring, and ranking
for the full universe in a single cycle.

run_cycle() never raises under any circumstances — all exceptions are
caught, logged, and a minimal valid RankedUniverse is always returned.
"""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from core.logger import get_logger
from core.models import BarFeatures, RankedSymbol, RankedUniverse
from core.ranking.features import compute_features
from core.ranking.scorer import normalize_scores, classify_direction
from core.data.normalizer import normalize_bars

if TYPE_CHECKING:
    from config.settings import Settings
    from core.data.fetcher import DataFetcher
    from core.data.cache import DataCache
    from core.universe import UniverseManager

logger = get_logger(__name__)

_LOOKBACK_DAYS = 7       # Calendar days to look back for bar data
_BARS_NEEDED = 30        # Bars to pass into compute_features per symbol
_MIN_SCORED_WARN = 10    # Log ERROR if fewer than this many symbols scored
_FULL_REFRESH_EVERY = 6  # Force full 185-symbol re-fetch every N cycles (~2 hours at 20-min interval)


class RankingEngine:
    """
    Orchestrates one full ranking cycle across the universe.
    run_cycle() never raises — all exceptions are caught and logged.
    """

    def __init__(
        self,
        settings,
        fetcher,
        cache,
        universe,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._cache = cache
        self._universe = universe
        self._cycle_count = 0
        logger.info("RankingEngine initialized")

    def run_cycle(self) -> RankedUniverse:
        """
        Execute one full ranking cycle.
        Fetches bars, computes features, normalizes scores, classifies directions.
        Returns a RankedUniverse. Never raises.
        """
        import time as _time
        t0 = _time.monotonic()
        cycle_id = str(uuid.uuid4())
        cycle_ts = datetime.now(timezone.utc)

        try:
            return self._run_cycle_inner(cycle_id, cycle_ts, t0)
        except Exception:
            duration = _time.monotonic() - t0
            logger.error(
                "run_cycle [%s] — unhandled exception caught at engine level:\n%s",
                cycle_id[:8],
                traceback.format_exc(),
            )
            return RankedUniverse(
                cycle_id=cycle_id,
                timestamp=cycle_ts,
                longs=[],
                shorts=[],
                universe_size=0,
                scored_count=0,
                error_count=0,
                duration_seconds=duration,
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_cycle_inner(
        self,
        cycle_id: str,
        cycle_ts: datetime,
        t0: float,
    ) -> RankedUniverse:
        import time as _time

        self._cycle_count += 1
        all_symbols = self._universe.get_all_symbols()
        universe_size = len(all_symbols)

        # Fetch bars with a consistent lookback window.
        # Subtract 15 min so we never request data right at Alpaca's IEX latency
        # boundary — avoids the midnight-UTC cache-key rollover producing a
        # partial API response that then poisons the cache for the whole day.
        end_dt = datetime.now(timezone.utc) - timedelta(minutes=15)
        start_dt = end_dt - timedelta(days=_LOOKBACK_DAYS)

        # Every _FULL_REFRESH_EVERY cycles, bypass the cache entirely and
        # re-fetch all 185 symbols from the API.  This prevents the post-midnight
        # degraded state where only a handful of symbols have valid cache entries
        # and subsequent cycles keep fetching the same small failing subset.
        force_full_refresh = (self._cycle_count % _FULL_REFRESH_EVERY == 0)
        if force_full_refresh:
            logger.info(
                "Cycle %d: forcing full %d-symbol refresh (every %d cycles)",
                self._cycle_count, universe_size, _FULL_REFRESH_EVERY,
            )

        bars_by_symbol = self._fetch_with_cache(
            all_symbols, start_dt, end_dt, force_full_refresh=force_full_refresh
        )

        # Compute features per symbol — one failure never aborts the cycle
        valid_features: list[BarFeatures] = []
        error_count = 0

        for sym in all_symbols:
            sym_bars = bars_by_symbol.get(sym)
            if not sym_bars:
                error_count += 1
                continue

            # Take last _BARS_NEEDED bars (oldest-first preserved)
            sym_bars_trimmed = (
                sym_bars[-_BARS_NEEDED:] if len(sym_bars) > _BARS_NEEDED else sym_bars
            )

            try:
                feat = compute_features(sym, sym_bars_trimmed)
                if feat is not None:
                    valid_features.append(feat)
                else:
                    error_count += 1
            except Exception:
                error_count += 1
                logger.warning(
                    "run_cycle [%s] — feature error for %s:\n%s",
                    cycle_id[:8],
                    sym,
                    traceback.format_exc(),
                )

        scored_count = len(valid_features)

        if scored_count < _MIN_SCORED_WARN:
            logger.error(
                "run_cycle [%s] — only %d symbols scored (minimum expected: %d). "
                "Data may be unavailable. Returning sparse RankedUniverse.",
                cycle_id[:8],
                scored_count,
                _MIN_SCORED_WARN,
            )

        # Normalize and classify
        if valid_features:
            normalize_scores(valid_features)
            long_features, short_features = classify_direction(valid_features)
        else:
            long_features, short_features = [], []

        # Build RankedSymbol objects with 1-based ranks
        longs = [
            RankedSymbol(
                symbol=f.symbol,
                score=f.normalized_score,
                direction="long",
                rank=i + 1,
                features=f,
                timestamp=cycle_ts,
            )
            for i, f in enumerate(long_features)
        ]
        shorts = [
            RankedSymbol(
                symbol=f.symbol,
                score=f.normalized_score,
                direction="short",
                rank=i + 1,
                features=f,
                timestamp=cycle_ts,
            )
            for i, f in enumerate(short_features)
        ]

        duration = _time.monotonic() - t0

        # One-line cycle summary log
        top3_longs = ", ".join(
            f"{s.symbol}({s.score:.1f})" for s in longs[:3]
        ) or "none"
        top3_shorts = ", ".join(
            f"{s.symbol}({s.score:.1f})" for s in shorts[:3]
        ) or "none"
        logger.info(
            "Cycle %s | %s | universe=%d scored=%d errors=%d | "
            "longs=[%s] shorts=[%s] | %.2fs",
            cycle_id[:8],
            cycle_ts.strftime("%H:%M:%S"),
            universe_size,
            scored_count,
            error_count,
            top3_longs,
            top3_shorts,
            duration,
        )

        return RankedUniverse(
            cycle_id=cycle_id,
            timestamp=cycle_ts,
            longs=longs,
            shorts=shorts,
            universe_size=universe_size,
            scored_count=scored_count,
            error_count=error_count,
            duration_seconds=duration,
        )

    def _fetch_with_cache(
        self,
        symbols: list[str],
        start_dt: datetime,
        end_dt: datetime,
        force_full_refresh: bool = False,
    ) -> dict[str, list[dict]]:
        """
        Check cache per symbol; batch-fetch all misses in a single API call.
        Returns dict[symbol → list[bar_dict]] sorted oldest-first.

        If force_full_refresh is True, skip the cache lookup and treat all
        symbols as misses so a fresh API fetch is guaranteed for every symbol.
        """
        import pandas as pd

        result: dict[str, list[dict]] = {}
        cache_misses: list[str] = []

        if force_full_refresh:
            # Bypass cache — every symbol goes straight to the batch fetch.
            cache_misses = list(symbols)
        else:
            for sym in symbols:
                try:
                    cached_df = self._cache.get(
                        sym, start_dt, end_dt, self._settings.BAR_TIMEFRAME
                    )
                    if cached_df is not None and not cached_df.empty:
                        records = normalize_bars(cached_df)
                        if records:
                            result[sym] = sorted(records, key=lambda r: r["timestamp"])
                            continue
                except Exception:
                    pass
                cache_misses.append(sym)

        if not cache_misses:
            return result

        # Single batch fetch for all cache misses
        try:
            df = self._fetcher.fetch_historical_bars(
                symbols=cache_misses,
                start=start_dt,
                end=end_dt,
                timeframe=self._settings.BAR_TIMEFRAME,
                filter_market_hours=True,
            )
            if df is not None and not df.empty:
                records = normalize_bars(df)

                # Group by symbol
                by_sym: dict[str, list[dict]] = {}
                for rec in records:
                    by_sym.setdefault(rec["symbol"], []).append(rec)

                # Detect degraded API responses early so operators can act.
                if len(by_sym) < max(len(cache_misses) // 2, 1):
                    logger.error(
                        "Degraded API response: received bars for %d/%d requested "
                        "symbols — ranking this cycle will be unreliable",
                        len(by_sym), len(cache_misses),
                    )

                for sym, sym_records in by_sym.items():
                    sym_records.sort(key=lambda r: r["timestamp"])
                    result[sym] = sym_records

                    # Write to cache (per-symbol slice)
                    try:
                        sym_df = df[df["symbol"] == sym].copy()
                        if not sym_df.empty:
                            self._cache.set(
                                sym, start_dt, end_dt,
                                self._settings.BAR_TIMEFRAME, sym_df,
                            )
                    except Exception:
                        pass  # Cache write failure is non-fatal

        except Exception:
            logger.error(
                "Batch fetch FAILED for %d symbols — ranking will be sparse:\n%s",
                len(cache_misses),
                traceback.format_exc(),
            )

        return result
