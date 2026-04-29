"""
Live memory writer for Olympus Phase 4.
MemoryWriter is the thin write layer between the paper trading loop and the database.
Every method catches all exceptions, logs at ERROR, and returns False — never raises.

MemoryAwarePaperTradingLoop subclasses PaperTradingLoop and integrates the writer
without touching core/trading/loop.py.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from core.memory.enrichment import TradeContextEnricher
from core.trading.loop import PaperTradingLoop

if TYPE_CHECKING:
    from core.memory.database import Database
    from core.models import BarFeatures, RankedUniverse, TradeRecord

logger = get_logger(__name__)


class MemoryWriter:
    """
    Thin write layer — translates in-memory objects into database rows.

    All public methods:
    - Accept the canonical in-memory object (TradeRecord, RankedUniverse, etc.)
    - Execute INSERT OR IGNORE so they are idempotent
    - Catch all exceptions, log at ERROR with full traceback, return False
    - Return True on success, False on any failure
    """

    def __init__(
        self,
        db: "Database",
        allow_network_fallback: bool = True,
    ) -> None:
        self._db = db
        self._enricher = TradeContextEnricher(
            db,
            allow_network_fallback=allow_network_fallback,
        )
        logger.info("MemoryWriter initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_trade(
        self,
        record: "TradeRecord",
        features: Optional["BarFeatures"] = None,
    ) -> bool:
        """
        Write a completed TradeRecord to the trades table.
        Optionally enriches the trade_features row with feature data.
        Returns True on success, False on any failure.
        """
        try:
            now_utc = datetime.now(timezone.utc).isoformat()
            entry_ts = record.entry_time.isoformat() if record.entry_time is not None else now_utc
            exit_ts = record.exit_time.isoformat() if record.exit_time is not None else now_utc
            entry_cycle_id = self._enricher.resolve_entry_cycle_id(entry_ts)
            regime = self._enricher.resolve_regime(entry_cycle_id)

            cur = self._db.execute(
                """
                INSERT OR IGNORE INTO trades (
                    trade_id, position_id, symbol, direction,
                    entry_price, exit_price, stop_price, target_price,
                    size, entry_time, exit_time, hold_duration_minutes,
                    realized_pnl, r_multiple, exit_reason, status, regime,
                    rank_at_entry, score_at_entry, rank_at_exit, score_at_exit,
                    entry_cycle_id, exit_cycle_id,
                    ingested_at, source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.trade_id,
                    record.position_id,
                    record.symbol,
                    record.direction,
                    float(record.entry_price),
                    float(record.exit_price),
                    float(record.stop_price),
                    float(record.target_price),
                    int(record.size),
                    entry_ts,
                    exit_ts,
                    float(record.hold_duration_minutes),
                    float(record.realized_pnl),
                    float(record.r_multiple),
                    record.exit_reason,
                    record.status,
                    regime,
                    record.rank_at_entry,
                    record.score_at_entry,
                    record.rank_at_exit,
                    record.score_at_exit,
                    entry_cycle_id,
                    None,  # exit_cycle_id — live integration wired in Phase 5+
                    now_utc,
                    None,  # source_file — live writes have no source file
                ),
            )

            if cur.rowcount > 0:
                self._write_trade_features(record, features, entry_ts, now_utc)
                logger.debug(
                    "write_trade: inserted %s (%s %s r=%.2f)",
                    record.trade_id[:8], record.direction.upper(), record.symbol,
                    record.r_multiple,
                )
            else:
                logger.debug("write_trade: duplicate skipped %s", record.trade_id[:8])

            return True

        except Exception:
            logger.error(
                "write_trade FAILED for trade %s:\n%s",
                getattr(record, "trade_id", "?")[:8],
                traceback.format_exc(),
            )
            return False

    def write_cycle(self, ranked: "RankedUniverse") -> bool:
        """
        Write a completed RankedUniverse to ranking_cycles and cycle_rankings.
        Returns True on success, False on any failure.
        """
        try:
            now_utc = datetime.now(timezone.utc).isoformat()
            cycle_ts = (
                ranked.timestamp.isoformat()
                if ranked.timestamp is not None
                else now_utc
            )

            longs = [rs.to_dict() for rs in ranked.longs]
            shorts = [rs.to_dict() for rs in ranked.shorts]

            cur = self._db.execute(
                """
                INSERT OR IGNORE INTO ranking_cycles (
                    cycle_id, cycle_timestamp, universe_size, scored_count,
                    error_count, duration_seconds,
                    top_longs_json, top_shorts_json, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    ranked.cycle_id,
                    cycle_ts,
                    int(ranked.universe_size),
                    int(ranked.scored_count),
                    int(ranked.error_count),
                    float(ranked.duration_seconds),
                    json.dumps(longs[:10]),
                    json.dumps(shorts[:10]),
                    now_utc,
                ),
            )

            cycle_inserted = cur.rowcount > 0

            # Individual cycle_rankings rows for every ranked symbol
            ranking_rows = []
            for rs in ranked.longs:
                ranking_rows.append((
                    ranked.cycle_id, cycle_ts, rs.symbol, "long",
                    int(rs.rank), float(rs.score),
                ))
            for rs in ranked.shorts:
                ranking_rows.append((
                    ranked.cycle_id, cycle_ts, rs.symbol, "short",
                    int(rs.rank), float(rs.score),
                ))

            if ranking_rows:
                self._db.executemany(
                    """
                    INSERT OR IGNORE INTO cycle_rankings
                        (cycle_id, cycle_timestamp, symbol, direction, rank, score)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ranking_rows,
                )

            if cycle_inserted:
                logger.debug(
                    "write_cycle: inserted %s (%d longs, %d shorts)",
                    ranked.cycle_id[:8], len(ranked.longs), len(ranked.shorts),
                )
            else:
                logger.debug("write_cycle: duplicate skipped %s", ranked.cycle_id[:8])

            return True

        except Exception:
            logger.error(
                "write_cycle FAILED for cycle %s:\n%s",
                getattr(ranked, "cycle_id", "?")[:8],
                traceback.format_exc(),
            )
            return False

    def write_event(
        self,
        event_type: str,
        description: str,
        symbol: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Write a system event to the system_events table.
        Returns True on success, False on any failure.
        """
        try:
            now_utc = datetime.now(timezone.utc).isoformat()
            self._db.execute(
                """
                INSERT INTO system_events
                    (event_time, event_type, symbol, description, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_utc,
                    event_type,
                    symbol,
                    description,
                    json.dumps(metadata) if metadata is not None else None,
                    now_utc,
                    now_utc,
                ),
            )
            logger.debug("write_event: %s — %s", event_type, description[:80])
            return True

        except Exception:
            logger.error(
                "write_event FAILED (type=%s):\n%s",
                event_type,
                traceback.format_exc(),
            )
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_trade_features(
        self,
        record: "TradeRecord",
        features: Optional["BarFeatures"],
        entry_ts: str,
        now_utc: str,
    ) -> None:
        """Insert or update the trade_features row for a newly inserted trade."""
        snapshot = self._enricher.reconstruct_entry_snapshot(
            record.symbol,
            entry_ts,
            existing_score=record.score_at_entry,
        )
        if features is None:
            # Stub row — all feature columns NULL
            self._db.execute(
                """
                INSERT OR IGNORE INTO trade_features (
                    trade_id, symbol,
                    roc_5, roc_10, roc_20, acceleration,
                    rvol_at_entry, vwap_deviation_at_entry, range_position_at_entry,
                    raw_score, score_at_entry,
                    close_at_entry, volume_at_entry, vwap_at_entry, atr_at_entry,
                    high_20, low_20, bar_count_used,
                    captured_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.trade_id,
                    record.symbol,
                    snapshot.roc_5,
                    snapshot.roc_10,
                    snapshot.roc_20,
                    snapshot.acceleration,
                    snapshot.rvol_at_entry,
                    snapshot.vwap_deviation_at_entry,
                    snapshot.range_position_at_entry,
                    snapshot.raw_score,
                    snapshot.score_at_entry,
                    snapshot.close_at_entry,
                    snapshot.volume_at_entry,
                    snapshot.vwap_at_entry,
                    snapshot.atr_at_entry,
                    snapshot.high_20,
                    snapshot.low_20,
                    snapshot.bar_count_used,
                    snapshot.captured_at or entry_ts,
                    now_utc,
                    now_utc,
                ),
            )
        else:
            self._db.execute(
                """
                INSERT OR IGNORE INTO trade_features (
                    trade_id, symbol,
                    roc_5, roc_10, roc_20, acceleration,
                    rvol_at_entry, vwap_deviation_at_entry, range_position_at_entry,
                    raw_score, score_at_entry,
                    close_at_entry, volume_at_entry, vwap_at_entry, atr_at_entry,
                    high_20, low_20, bar_count_used,
                    captured_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.trade_id,
                    record.symbol,
                    features.roc_5 if features.roc_5 is not None else snapshot.roc_5,
                    features.roc_10 if features.roc_10 is not None else snapshot.roc_10,
                    features.roc_20 if features.roc_20 is not None else snapshot.roc_20,
                    features.acceleration if features.acceleration is not None else snapshot.acceleration,
                    features.rvol if features.rvol is not None else snapshot.rvol_at_entry,
                    features.vwap_deviation if features.vwap_deviation is not None else snapshot.vwap_deviation_at_entry,
                    features.range_position if features.range_position is not None else snapshot.range_position_at_entry,
                    features.raw_score if features.raw_score is not None else snapshot.raw_score,
                    features.normalized_score if features.normalized_score is not None else snapshot.score_at_entry,
                    float(features.close) if features.close is not None else snapshot.close_at_entry,
                    float(features.volume) if features.volume is not None else snapshot.volume_at_entry,
                    snapshot.vwap_at_entry,
                    snapshot.atr_at_entry,
                    snapshot.high_20,
                    snapshot.low_20,
                    snapshot.bar_count_used,
                    snapshot.captured_at or entry_ts,
                    now_utc,
                    now_utc,
                ),
            )


# ---------------------------------------------------------------------------
# Phase 4 integration — memory-aware subclass of PaperTradingLoop
# ---------------------------------------------------------------------------


class MemoryAwarePaperTradingLoop(PaperTradingLoop):
    """
    Extends PaperTradingLoop with live database writes.

    Strategy: minimal overrides, zero changes to core/trading/loop.py.

    - _register_completed_trade() — parent adds the record to the session list;
      we also call writer.write_trade() for every completed trade.
    - _run_cycle() — parent runs the full cycle; we also call writer.write_cycle()
      after each successful cycle so every ranking pass is persisted.
    """

    def __init__(self, memory_writer: MemoryWriter, **kwargs) -> None:
        super().__init__(**kwargs)
        self._memory_writer = memory_writer
        logger.info("MemoryAwarePaperTradingLoop initialized")

    def _register_completed_trade(self, record: "TradeRecord") -> None:
        """Add to session list (parent), then persist to DB (ours)."""
        super()._register_completed_trade(record)
        self._memory_writer.write_trade(record, features=record.features)
        if record.features is None:
            self._memory_writer.write_event(
                "data_quality",
                f"Trade {record.trade_id[:8]} closed without feature snapshot",
                symbol=record.symbol,
                metadata={
                    "trade_id": record.trade_id,
                    "issue": "missing_trade_features",
                    "exit_reason": record.exit_reason,
                },
            )
        if record.entry_time.date() != record.exit_time.date():
            self._memory_writer.write_event(
                "data_quality",
                f"Trade {record.trade_id[:8]} crossed sessions",
                symbol=record.symbol,
                metadata={
                    "trade_id": record.trade_id,
                    "issue": "overnight_hold",
                    "entry_time": record.entry_time.isoformat(),
                    "exit_time": record.exit_time.isoformat(),
                },
            )

    def _run_cycle(self) -> None:
        """Run the full cycle (parent), then persist the ranking cycle to DB."""
        ranked_before = self._ranking_cycle.get_latest()
        if ranked_before is not None:
            self._memory_writer.write_cycle(ranked_before)
        super()._run_cycle()
        # Persist whichever cycle the loop just consumed.
        # get_latest() is idempotent and returns None if no cycle exists yet.
        ranked = self._ranking_cycle.get_latest()
        if ranked is not None:
            self._memory_writer.write_cycle(ranked)
            diagnostics = self.get_last_cycle_diagnostics()
            if diagnostics:
                self._memory_writer.write_event(
                    "cycle_diagnostics",
                    f"Cycle {ranked.cycle_id[:8]} {diagnostics.get('regime', {}).get('name', 'unknown')}",
                    metadata={
                        "cycle_id": ranked.cycle_id,
                        "regime": diagnostics.get("regime"),
                        "qualification": diagnostics.get("qualification"),
                        "entries": diagnostics.get("entries"),
                        "exits": diagnostics.get("exits"),
                        "broker_state": diagnostics.get("broker_state"),
                    },
                )
                broker_state = diagnostics.get("broker_state") or {}
                if broker_state.get("mismatch"):
                    self._memory_writer.write_event(
                        "broker_mismatch",
                        "Local and broker open positions diverged",
                        metadata=broker_state,
                    )
