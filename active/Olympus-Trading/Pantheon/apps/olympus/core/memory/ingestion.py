"""
JSON → SQLite ingestion for Olympus Phase 4.
Ingests existing data/trades/ and data/rankings/ JSON files into the database.
Idempotent — INSERT OR IGNORE everywhere. Running twice produces no duplicates.
"""

from __future__ import annotations

import json
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from core.memory.database import Database
from core.memory.enrichment import TradeContextEnricher

logger = get_logger(__name__)


def _ensure_utc_iso(ts: Optional[str]) -> Optional[str]:
    """
    Parse a timestamp string and normalize it to a UTC ISO 8601 string.
    Handles formats produced by datetime.isoformat() with or without timezone info.
    Returns the input as-is if parsing fails (logged at WARNING).
    """
    if ts is None:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat()
    except Exception:
        logger.warning("Could not parse timestamp '%s' — storing as-is", ts)
        return str(ts)


@dataclass
class IngestionResult:
    source_type: str
    files_seen: int = 0
    rows_written: int = 0
    status: str = "completed"
    error: Optional[str] = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class Ingestion:
    """
    Ingests existing JSON files into the SQLite database.

    Both methods are idempotent — running them multiple times produces
    identical row counts (INSERT OR IGNORE skips duplicates silently).
    """

    def __init__(
        self,
        db: Database,
        trades_dir: Path,
        rankings_dir: Path,
        allow_network_fallback: bool = False,
    ) -> None:
        self._db = db
        self._trades_dir = trades_dir
        self._rankings_dir = rankings_dir
        self._enricher = TradeContextEnricher(
            db,
            allow_network_fallback=allow_network_fallback,
        )
        logger.info(
            "Ingestion initialized (trades=%s, rankings=%s)",
            trades_dir, rankings_dir,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest_trades(self) -> IngestionResult:
        """
        Ingest all trade_*.json files from trades_dir into the trades table.
        Creates a stub trade_features row for each inserted trade.
        Records an ingestion_runs row with status and counts.
        """
        result = IngestionResult(source_type="trades_json")
        now_utc = datetime.now(timezone.utc).isoformat()

        # Open an ingestion_runs row
        self._db.execute(
            """
            INSERT INTO ingestion_runs
                (run_id, source_type, started_at, status, created_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (result.run_id, result.source_type, now_utc, now_utc),
        )
        logger.info("Trade ingestion started — run_id=%s", result.run_id[:8])

        try:
            trade_files = sorted(self._trades_dir.glob("trade_*.json"))
            result.files_seen = len(trade_files)

            for filepath in trade_files:
                try:
                    self._ingest_one_trade(filepath, result)
                except Exception:
                    logger.error(
                        "Failed to ingest trade file %s:\n%s",
                        filepath.name, traceback.format_exc(),
                    )

            # Complete the ingestion_runs row
            completed_at = datetime.now(timezone.utc).isoformat()
            self._db.execute(
                """
                UPDATE ingestion_runs
                SET status='completed', completed_at=?, files_seen=?, rows_written=?
                WHERE run_id=?
                """,
                (completed_at, result.files_seen, result.rows_written, result.run_id),
            )
            result.status = "completed"
            logger.info(
                "Trade ingestion complete — files=%d rows_written=%d run_id=%s",
                result.files_seen, result.rows_written, result.run_id[:8],
            )

        except Exception:
            err = traceback.format_exc()
            logger.error("Trade ingestion FAILED:\n%s", err)
            result.status = "failed"
            result.error = err[:2000]
            try:
                self._db.execute(
                    """
                    UPDATE ingestion_runs
                    SET status='failed', completed_at=?, error_text=?
                    WHERE run_id=?
                    """,
                    (datetime.now(timezone.utc).isoformat(), result.error, result.run_id),
                )
            except Exception:
                pass

        return result

    def ingest_rankings(self) -> IngestionResult:
        """
        Ingest all ranking_*.json files from rankings_dir into the
        ranking_cycles and cycle_rankings tables.
        """
        result = IngestionResult(source_type="rankings_json")
        now_utc = datetime.now(timezone.utc).isoformat()

        self._db.execute(
            """
            INSERT INTO ingestion_runs
                (run_id, source_type, started_at, status, created_at)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (result.run_id, result.source_type, now_utc, now_utc),
        )
        logger.info("Rankings ingestion started — run_id=%s", result.run_id[:8])

        try:
            ranking_files = sorted(self._rankings_dir.glob("ranking_*.json"))
            result.files_seen = len(ranking_files)

            for filepath in ranking_files:
                try:
                    self._ingest_one_ranking(filepath, result)
                except Exception:
                    logger.error(
                        "Failed to ingest ranking file %s:\n%s",
                        filepath.name, traceback.format_exc(),
                    )

            completed_at = datetime.now(timezone.utc).isoformat()
            self._db.execute(
                """
                UPDATE ingestion_runs
                SET status='completed', completed_at=?, files_seen=?, rows_written=?
                WHERE run_id=?
                """,
                (completed_at, result.files_seen, result.rows_written, result.run_id),
            )
            result.status = "completed"
            logger.info(
                "Rankings ingestion complete — files=%d rows_written=%d run_id=%s",
                result.files_seen, result.rows_written, result.run_id[:8],
            )

        except Exception:
            err = traceback.format_exc()
            logger.error("Rankings ingestion FAILED:\n%s", err)
            result.status = "failed"
            result.error = err[:2000]
            try:
                self._db.execute(
                    """
                    UPDATE ingestion_runs
                    SET status='failed', completed_at=?, error_text=?
                    WHERE run_id=?
                    """,
                    (datetime.now(timezone.utc).isoformat(), result.error, result.run_id),
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest_one_trade(self, filepath: Path, result: IngestionResult) -> None:
        """Parse one trade JSON file and insert into trades + trade_features."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        now_utc = datetime.now(timezone.utc).isoformat()
        entry_time = _ensure_utc_iso(data.get("entry_time"))
        exit_time = _ensure_utc_iso(data.get("exit_time"))
        entry_cycle_id = self._enricher.resolve_entry_cycle_id(entry_time) if entry_time else None
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
                data["trade_id"],
                data["position_id"],
                data["symbol"],
                data["direction"],
                float(data["entry_price"]),
                float(data["exit_price"]),
                float(data["stop_price"]),
                float(data["target_price"]),
                int(data["size"]),
                entry_time,
                exit_time,
                float(data["hold_duration_minutes"]),
                float(data["realized_pnl"]),
                float(data["r_multiple"]),
                data["exit_reason"],
                data.get("status", "closed"),
                regime,
                data.get("rank_at_entry"),
                data.get("score_at_entry"),
                data.get("rank_at_exit"),
                data.get("score_at_exit"),
                entry_cycle_id,
                None,  # exit_cycle_id — NULL for historical trades
                now_utc,
                filepath.name,
            ),
        )

        if cur.rowcount > 0:
            snapshot = self._enricher.reconstruct_entry_snapshot(
                data["symbol"],
                entry_time or now_utc,
                existing_score=data.get("score_at_entry"),
            )
            self._db.execute(
                """
                INSERT OR IGNORE INTO trade_features (
                    trade_id, symbol,
                    roc_5, roc_10, roc_20, acceleration,
                    rvol_at_entry, vwap_deviation_at_entry, range_position_at_entry,
                    raw_score, score_at_entry,
                    close_at_entry, volume_at_entry, vwap_at_entry, atr_at_entry,
                    high_20, low_20, bar_count_used,
                    captured_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    data["trade_id"],
                    data["symbol"],
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
                    snapshot.captured_at or entry_time or now_utc,
                ),
            )
            result.rows_written += 1
            logger.debug("Ingested trade %s from %s", data["trade_id"][:8], filepath.name)
        else:
            logger.debug("Skipped duplicate trade %s (%s)", data["trade_id"][:8], filepath.name)

    def _ingest_one_ranking(self, filepath: Path, result: IngestionResult) -> None:
        """Parse one ranking JSON file and insert into ranking_cycles + cycle_rankings."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        now_utc = datetime.now(timezone.utc).isoformat()
        cycle_ts = _ensure_utc_iso(data.get("timestamp"))
        longs = data.get("longs", [])
        shorts = data.get("shorts", [])

        cur = self._db.execute(
            """
            INSERT OR IGNORE INTO ranking_cycles (
                cycle_id, cycle_timestamp, universe_size, scored_count,
                error_count, duration_seconds,
                top_longs_json, top_shorts_json, ingested_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                data["cycle_id"],
                cycle_ts,
                int(data.get("universe_size", 0)),
                int(data.get("scored_count", 0)),
                int(data.get("error_count", 0)),
                float(data.get("duration_seconds", 0.0)),
                json.dumps(longs[:10]),   # store top 10 longs summary
                json.dumps(shorts[:10]),  # store top 10 shorts summary
                now_utc,
            ),
        )

        cycle_inserted = cur.rowcount > 0

        # Insert individual cycle_rankings rows for all longs and shorts
        ranking_rows = []
        for rs in longs:
            ranking_rows.append((
                data["cycle_id"], cycle_ts, rs["symbol"], "long",
                int(rs["rank"]), float(rs["score"]),
            ))
        for rs in shorts:
            ranking_rows.append((
                data["cycle_id"], cycle_ts, rs["symbol"], "short",
                int(rs["rank"]), float(rs["score"]),
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
            result.rows_written += 1
            logger.debug(
                "Ingested ranking cycle %s from %s (%d longs, %d shorts)",
                data["cycle_id"][:8], filepath.name, len(longs), len(shorts),
            )
        else:
            logger.debug("Skipped duplicate ranking cycle %s", data["cycle_id"][:8])
