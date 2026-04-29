"""
Trade-context enrichment helpers for Olympus.

This module centralizes the logic that makes trades self-describing:
- link a trade to the ranking cycle active at entry
- classify the persisted regime label from that cycle
- reconstruct entry-time feature snapshots from cached or fetched bars

Historical regime backfill is necessarily approximate because older trades did
not store entry_cycle_id at execution time. We therefore link each trade to the
nearest ranking cycle at or before entry_time and classify regime from the
cross-sectional ranking snapshot stored for that cycle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pandas as pd

from config.settings import settings
from core.data.cache import DataCache
from core.data.fetcher import DataFetcher
from core.data.normalizer import normalize_bars
from core.logger import get_logger
from core.models import BarFeatures
from core.ranking.features import compute_features
from core.ranking.scorer import normalize_scores
from core.trading.loop import _ATR_FETCH_DAYS, _ATR_LOOKBACK_BARS, _compute_atr
from core.trading.regime import RegimeDecision, classify_regime

logger = get_logger(__name__)

_FEATURE_LOOKBACK_BARS = 30
_RANKING_BUFFER_MINUTES = 90


@dataclass(frozen=True)
class EntryFeatureSnapshot:
    rvol_at_entry: Optional[float]
    score_at_entry: Optional[float]
    range_position_at_entry: Optional[float]
    vwap_deviation_at_entry: Optional[float]
    atr_at_entry: Optional[float]
    close_at_entry: Optional[float]
    volume_at_entry: Optional[float]
    vwap_at_entry: Optional[float]
    high_20: Optional[float]
    low_20: Optional[float]
    bar_count_used: Optional[int]
    roc_5: Optional[float]
    roc_10: Optional[float]
    roc_20: Optional[float]
    acceleration: Optional[float]
    raw_score: Optional[float]
    captured_at: Optional[str]


class TradeContextEnricher:
    """Resolves cycle linkage, regime labels, and entry snapshots for trades."""

    def __init__(self, db, allow_network_fallback: bool = True) -> None:
        self._db = db
        self._allow_network_fallback = allow_network_fallback
        self._cache_dir = Path(settings.CACHE_DIR)
        self._cache_frames: dict[str, pd.DataFrame] = {}
        self._fetcher: Optional[DataFetcher] = None

    def resolve_entry_cycle_id(self, entry_time_iso: str) -> Optional[str]:
        row = self._db.query_one(
            """
            SELECT cycle_id
            FROM ranking_cycles
            WHERE cycle_timestamp <= ?
            ORDER BY cycle_timestamp DESC
            LIMIT 1
            """,
            (entry_time_iso,),
        )
        if row:
            return row["cycle_id"]

        row = self._db.query_one(
            """
            SELECT cycle_id
            FROM ranking_cycles
            ORDER BY ABS((julianday(cycle_timestamp) - julianday(?)) * 86400.0) ASC
            LIMIT 1
            """,
            (entry_time_iso,),
        )
        return row["cycle_id"] if row else None

    def resolve_regime(self, cycle_id: Optional[str]) -> Optional[str]:
        if not cycle_id:
            return None

        cycle = self._db.query_one(
            """
            SELECT
                cycle_id, cycle_timestamp, universe_size, scored_count,
                error_count, duration_seconds, top_longs_json, top_shorts_json
            FROM ranking_cycles
            WHERE cycle_id = ?
            """,
            (cycle_id,),
        )
        if cycle is None:
            return None

        rankings = self._db.query(
            """
            SELECT symbol, direction, rank, score
            FROM cycle_rankings
            WHERE cycle_id = ?
            ORDER BY direction, rank
            """,
            (cycle_id,),
        )
        if not rankings:
            rankings = self._rankings_from_cycle_json(cycle)
            if not rankings:
                return None

        ranked = self._build_ranked_universe(cycle, rankings)
        decision = classify_regime(ranked, settings)
        return persisted_regime_name(decision)

    def reconstruct_entry_snapshot(
        self,
        symbol: str,
        entry_time_iso: str,
        existing_score: Optional[float] = None,
    ) -> EntryFeatureSnapshot:
        bars = self._get_symbol_bars_for_entry(symbol, entry_time_iso)
        if not bars:
            return EntryFeatureSnapshot(
                rvol_at_entry=None,
                score_at_entry=existing_score,
                range_position_at_entry=None,
                vwap_deviation_at_entry=None,
                atr_at_entry=None,
                close_at_entry=None,
                volume_at_entry=None,
                vwap_at_entry=None,
                high_20=None,
                low_20=None,
                bar_count_used=None,
                roc_5=None,
                roc_10=None,
                roc_20=None,
                acceleration=None,
                raw_score=None,
                captured_at=entry_time_iso,
            )

        latest = bars[-1]
        features = compute_features(symbol, bars)
        atr = _compute_atr(bars, period=_ATR_LOOKBACK_BARS) if bars else None
        highs = [float(b["high"]) for b in bars[-20:]] if bars else []
        lows = [float(b["low"]) for b in bars[-20:]] if bars else []

        score = existing_score
        raw_score = None
        roc_5 = roc_10 = roc_20 = acceleration = None
        rvol = range_position = vwap_deviation = None
        if features is not None:
            features.normalized_score = existing_score if existing_score is not None else 0.0
            normalize_scores([features])
            score = existing_score if existing_score is not None else features.normalized_score
            raw_score = features.raw_score
            roc_5 = features.roc_5
            roc_10 = features.roc_10
            roc_20 = features.roc_20
            acceleration = features.acceleration
            rvol = features.rvol
            range_position = features.range_position
            vwap_deviation = features.vwap_deviation

        return EntryFeatureSnapshot(
            rvol_at_entry=rvol,
            score_at_entry=score,
            range_position_at_entry=range_position,
            vwap_deviation_at_entry=vwap_deviation,
            atr_at_entry=atr,
            close_at_entry=float(latest["close"]),
            volume_at_entry=float(latest["volume"]),
            vwap_at_entry=(
                float(latest["vwap"])
                if latest.get("vwap") is not None
                else None
            ),
            high_20=max(highs) if highs else None,
            low_20=min(lows) if lows else None,
            bar_count_used=len(bars),
            roc_5=roc_5,
            roc_10=roc_10,
            roc_20=roc_20,
            acceleration=acceleration,
            raw_score=raw_score,
            captured_at=_to_utc_iso(latest["timestamp"]),
        )

    def _build_ranked_universe(self, cycle: dict, rankings: list[dict]) -> SimpleNamespace:
        longs = []
        shorts = []
        cycle_ts = _parse_iso(cycle["cycle_timestamp"])
        for row in rankings:
            placeholder_features = BarFeatures(
                symbol=row["symbol"],
                timestamp=cycle_ts,
                close=0.0,
                volume=0.0,
                roc_5=0.0,
                roc_10=0.0,
                roc_20=0.0,
                acceleration=0.0,
                rvol=0.0,
                vwap_deviation=0.0,
                range_position=0.5,
                raw_score=0.0,
                normalized_score=float(row["score"]),
            )
            ranked_symbol = SimpleNamespace(
                symbol=row["symbol"],
                score=float(row["score"]),
                direction=row["direction"],
                rank=int(row["rank"]),
                features=placeholder_features,
                timestamp=cycle_ts,
            )
            if row["direction"] == "long":
                longs.append(ranked_symbol)
            else:
                shorts.append(ranked_symbol)

        longs.sort(key=lambda rs: rs.rank)
        shorts.sort(key=lambda rs: rs.rank)
        return SimpleNamespace(
            cycle_id=cycle["cycle_id"],
            timestamp=cycle_ts,
            longs=longs,
            shorts=shorts,
            universe_size=int(cycle["universe_size"]),
            scored_count=int(cycle["scored_count"]),
            error_count=int(cycle["error_count"]),
            duration_seconds=float(cycle["duration_seconds"]),
        )

    def _rankings_from_cycle_json(self, cycle: dict) -> list[dict]:
        rankings: list[dict] = []
        for direction, key in (("long", "top_longs_json"), ("short", "top_shorts_json")):
            payload = cycle.get(key)
            if not payload:
                continue
            try:
                entries = json.loads(payload)
            except json.JSONDecodeError:
                continue
            for entry in entries:
                rankings.append(
                    {
                        "symbol": entry["symbol"],
                        "direction": direction,
                        "rank": int(entry["rank"]),
                        "score": float(entry["score"]),
                    }
                )
        return rankings

    def _get_symbol_bars_for_entry(self, symbol: str, entry_time_iso: str) -> list[dict]:
        entry_dt = _parse_iso(entry_time_iso)
        frame = self._load_cached_symbol_frame(symbol)
        selected = _select_entry_bars(frame, entry_dt)
        if selected:
            return selected

        if not self._allow_network_fallback:
            return []

        try:
            fetcher = self._get_fetcher()
            hist_df = fetcher.fetch_historical_bars(
                [symbol],
                start=entry_dt - timedelta(days=_ATR_FETCH_DAYS),
                end=entry_dt + timedelta(minutes=5),
                timeframe=settings.BAR_TIMEFRAME,
            )
            if hist_df is None or hist_df.empty:
                return []
            normalized = normalize_bars(hist_df)
            bars = [row for row in normalized if row["symbol"] == symbol]
            bars.sort(key=lambda row: row["timestamp"])
            return _trim_bars_at_entry(bars, entry_dt)
        except Exception as exc:
            logger.warning("Entry snapshot fetch failed for %s at %s: %s", symbol, entry_time_iso, exc)
            return []

    def _load_cached_symbol_frame(self, symbol: str) -> pd.DataFrame:
        symbol = symbol.upper()
        cached = self._cache_frames.get(symbol)
        if cached is not None:
            return cached

        frames: list[pd.DataFrame] = []
        for path in self._cache_dir.glob(f"{symbol}_*.parquet"):
            try:
                frame = pd.read_parquet(path)
                if frame is None or frame.empty:
                    continue
                normalized = pd.DataFrame(normalize_bars(frame))
                if not normalized.empty:
                    frames.append(normalized)
            except Exception as exc:
                logger.debug("Skipping unreadable cache file %s: %s", path.name, exc)

        if not frames:
            empty = pd.DataFrame()
            self._cache_frames[symbol] = empty
            return empty

        merged = pd.concat(frames, ignore_index=True)
        merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
        merged = (
            merged.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp"], keep="last")
            .reset_index(drop=True)
        )
        self._cache_frames[symbol] = merged
        return merged

    def _get_fetcher(self) -> DataFetcher:
        if self._fetcher is None:
            self._fetcher = DataFetcher()
        return self._fetcher


def persisted_regime_name(decision: RegimeDecision) -> str:
    if decision.name == "degraded":
        return "degraded"
    if decision.name == "mixed":
        return "mixed"
    if decision.name == "trend":
        if decision.dominant_side == "long":
            return "trend_up"
        if decision.dominant_side == "short":
            return "trend_down"
        return "mixed"
    return "degraded"


def _select_entry_bars(frame: pd.DataFrame, entry_dt: datetime) -> list[dict]:
    if frame is None or frame.empty:
        return []
    eligible = frame[frame["timestamp"] <= pd.Timestamp(entry_dt)]
    if eligible.empty:
        return []
    records = eligible.to_dict("records")
    bars = []
    for row in records:
        bars.append(
            {
                "symbol": row["symbol"],
                "timestamp": _to_python_dt(row["timestamp"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "vwap": (float(row["vwap"]) if pd.notna(row["vwap"]) else None),
            }
        )
    return _trim_bars_at_entry(bars, entry_dt)


def _trim_bars_at_entry(bars: list[dict], entry_dt: datetime) -> list[dict]:
    filtered = [bar for bar in bars if bar["timestamp"] <= entry_dt]
    filtered.sort(key=lambda row: row["timestamp"])
    if not filtered:
        return []
    return filtered[-_FEATURE_LOOKBACK_BARS:]


def _parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_utc_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


def _to_python_dt(value) -> datetime:
    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
