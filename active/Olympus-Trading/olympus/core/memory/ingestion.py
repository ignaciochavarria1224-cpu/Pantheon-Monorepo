"""
JSON → SQLite ingestion for Olympus Phase 4.
Ingests existing data/trades/ and data/rankings/ JSON files into the database.
Idempotent — INSERT OR IGNORE everywhere. Running twice produces no duplicates.
"""

from __future__ import annotations

import json
import math
import re
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

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_ALLOWED_DIRECTIONS = {"long", "short"}
_ALLOWED_EXIT_REASONS = {"stop", "target", "rotation", "manual", "eod_close"}
_ALLOWED_STATUSES = {"closed"}

# JSON validation schemas
TRADE_SCHEMA = {
    "trade_id": {"type": "string", "required": True},
    "position_id": {"type": "string", "required": True},
    "symbol": {"type": "string", "required": True},
    "direction": {"type": "string", "required": True},
    "entry_price": {"type": "number", "required": True},
    "exit_price": {"type": "number", "required": True},
    "stop_price": {"type": "number", "required": True},
    "target_price": {"type": "number", "required": True},
    "size": {"type": "integer", "required": True},
    "entry_time": {"type": "string", "required": True},
    "exit_time": {"type": "string", "required": True},
    "hold_duration_minutes": {"type": "number", "required": True},
    "realized_pnl": {"type": "number", "required": True},
    "r_multiple": {"type": "number", "required": True},
    "exit_reason": {"type": "string", "required": True},
    "status": {"type": "string", "required": False},
    "rank_at_entry": {"type": "integer", "required": False},
    "score_at_entry": {"type": "number", "required": False},
    "rank_at_exit": {"type": "integer", "required": False},
    "score_at_exit": {"type": "number", "required": False},
}

RANKING_SCHEMA = {
    "cycle_id": {"type": "string", "required": True},
    "timestamp": {"type": "string", "required": True},
    "universe_size": {"type": "integer", "required": False},
    "scored_count": {"type": "integer", "required": False},
    "error_count": {"type": "integer", "required": False},
    "duration_seconds": {"type": "number", "required": False},
    "longs": {"type": "array", "required": False},
    "shorts": {"type": "array", "required": False},
}


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"Invalid JSON numeric constant: {token}")


def _load_json_object(filepath: Path, data_type: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f, parse_constant=_reject_json_constant)
    if not isinstance(data, dict):
        raise ValueError(f"{data_type} JSON must be an object, got {type(data)}")
    return data


def _file_fingerprint(filepath: Path) -> tuple[int, int]:
    stat = filepath.stat()
    return int(stat.st_size), int(stat.st_mtime_ns)


def _ensure_finite_number(value, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Field '{field}' must be numeric, got boolean")
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str) and value.strip():
        numeric = float(value)
    else:
        raise ValueError(f"Field '{field}' must be numeric, got {value!r}")

    if not math.isfinite(numeric):
        raise ValueError(f"Field '{field}' must be finite, got {value!r}")
    return numeric


def _ensure_integer(value, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Field '{field}' must be integer, got boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and _INTEGER_RE.fullmatch(value.strip()):
        return int(value)
    raise ValueError(f"Field '{field}' must be integer, got {value!r}")


def _ensure_string(value, field: str, *, max_length: int = 128) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Field '{field}' must be string, got {type(value)}")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"Field '{field}' must not be empty")
    if len(normalized) > max_length:
        raise ValueError(f"Field '{field}' exceeds {max_length} characters")
    if any(ord(ch) < 32 for ch in normalized):
        raise ValueError(f"Field '{field}' contains control characters")
    return normalized


def _ensure_uuid(value, field: str) -> str:
    normalized = _ensure_string(value, field, max_length=64)
    try:
        return str(uuid.UUID(normalized))
    except ValueError as exc:
        raise ValueError(f"Field '{field}' must be a UUID") from exc


def _ensure_symbol(value, field: str = "symbol") -> str:
    symbol = _ensure_string(value, field, max_length=10).upper()
    if not _SYMBOL_RE.fullmatch(symbol):
        raise ValueError(f"Field '{field}' has invalid symbol: {value!r}")
    return symbol


def _parse_utc_iso(ts: str, field: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Field '{field}' must be ISO 8601 timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError(f"Field '{field}' must include timezone")
    return dt.astimezone(timezone.utc)


def _validate_json_data(data: dict, schema: dict, data_type: str) -> None:
    """
    Validate JSON data against a schema to prevent database corruption.
    Raises ValueError if validation fails.
    """
    if not isinstance(data, dict):
        raise ValueError(f"{data_type} JSON must be an object, got {type(data)}")

    for field, field_type in schema.items():
        if field not in data:
            if field_type.get("required", True):
                raise ValueError(f"Required field '{field}' missing from {data_type} JSON")
            continue

        value = data[field]
        if value is None:
            if field_type.get("required", True):
                raise ValueError(f"Required field '{field}' is null in {data_type} JSON")
            continue
        expected_type = field_type["type"]

        if expected_type == "string":
            data[field] = _ensure_string(value, field)
        elif expected_type == "number":
            data[field] = _ensure_finite_number(value, field)
        elif expected_type == "integer":
            data[field] = _ensure_integer(value, field)
        elif expected_type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Field '{field}' must be boolean, got {type(value)}")
        elif expected_type == "array" and not isinstance(value, list):
            raise ValueError(f"Field '{field}' must be array, got {type(value)}")


def _validate_trade_data(data: dict) -> None:
    _validate_json_data(data, TRADE_SCHEMA, "trade")
    data["trade_id"] = _ensure_uuid(data["trade_id"], "trade_id")
    data["position_id"] = _ensure_uuid(data["position_id"], "position_id")
    data["symbol"] = _ensure_symbol(data["symbol"])
    if data["direction"] not in _ALLOWED_DIRECTIONS:
        raise ValueError(f"Field 'direction' must be one of {_ALLOWED_DIRECTIONS}")
    if data["exit_reason"] not in _ALLOWED_EXIT_REASONS:
        raise ValueError(f"Field 'exit_reason' must be one of {_ALLOWED_EXIT_REASONS}")
    if data.get("status", "closed") not in _ALLOWED_STATUSES:
        raise ValueError(f"Field 'status' must be one of {_ALLOWED_STATUSES}")
    if data["size"] <= 0:
        raise ValueError("Field 'size' must be positive")
    if data["hold_duration_minutes"] < 0:
        raise ValueError("Field 'hold_duration_minutes' must be non-negative")
    _parse_utc_iso(data["entry_time"], "entry_time")
    _parse_utc_iso(data["exit_time"], "exit_time")


def _validate_ranking_item(item: dict, direction: str) -> None:
    if not isinstance(item, dict):
        raise ValueError("Ranking items must be objects")
    item["symbol"] = _ensure_symbol(item.get("symbol"), "symbol")
    item["rank"] = _ensure_integer(item.get("rank"), "rank")
    item["score"] = _ensure_finite_number(item.get("score"), "score")
    if item["rank"] <= 0:
        raise ValueError("Ranking field 'rank' must be positive")
    if "direction" in item and item["direction"] != direction:
        raise ValueError("Ranking item direction does not match its collection")


def _validate_ranking_data(data: dict) -> None:
    _validate_json_data(data, RANKING_SCHEMA, "ranking")
    data["cycle_id"] = _ensure_uuid(data["cycle_id"], "cycle_id")
    _parse_utc_iso(data["timestamp"], "timestamp")
    for field in ("universe_size", "scored_count", "error_count"):
        if data.get(field, 0) < 0:
            raise ValueError(f"Field '{field}' must be non-negative")
    if data.get("duration_seconds", 0.0) < 0:
        raise ValueError("Field 'duration_seconds' must be non-negative")
    for item in data.get("longs", []):
        _validate_ranking_item(item, "long")
    for item in data.get("shorts", []):
        _validate_ranking_item(item, "short")


def _ensure_utc_iso(ts: Optional[str]) -> Optional[str]:
    """
    Parse a timestamp string and normalize it to a UTC ISO 8601 string.
    Handles formats produced by datetime.isoformat() with or without timezone info.
    Returns the input as-is if parsing fails (logged at WARNING).
    """
    if ts is None:
        return None
    try:
        return _parse_utc_iso(str(ts), "timestamp").isoformat()
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
                    if self._is_unchanged_ingested_file(result.source_type, filepath):
                        logger.debug("Skipping unchanged trade file %s", filepath.name)
                        continue
                    self._ingest_one_trade(filepath, result)
                    self._record_source_file(result.source_type, filepath, "ingested")
                except Exception as exc:
                    logger.error(
                        "Failed to ingest trade file %s:\n%s",
                        filepath.name, traceback.format_exc(),
                    )
                    self._record_source_file(result.source_type, filepath, "failed", str(exc))

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
                    if self._is_unchanged_ingested_file(result.source_type, filepath):
                        logger.debug("Skipping unchanged ranking file %s", filepath.name)
                        continue
                    self._ingest_one_ranking(filepath, result)
                    self._record_source_file(result.source_type, filepath, "ingested")
                except Exception as exc:
                    logger.error(
                        "Failed to ingest ranking file %s:\n%s",
                        filepath.name, traceback.format_exc(),
                    )
                    self._record_source_file(result.source_type, filepath, "failed", str(exc))

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

    def _is_unchanged_ingested_file(self, source_type: str, filepath: Path) -> bool:
        try:
            file_size, mtime_ns = _file_fingerprint(filepath)
            row = self._db.query_one(
                """
                SELECT file_size, mtime_ns, status
                FROM ingestion_source_files
                WHERE source_type = ? AND source_file = ?
                """,
                (source_type, filepath.name),
            )
            return bool(
                row
                and row["status"] == "ingested"
                and int(row["file_size"]) == file_size
                and int(row["mtime_ns"]) == mtime_ns
            )
        except Exception:
            return False

    def _record_source_file(
        self,
        source_type: str,
        filepath: Path,
        status: str,
        error_text: Optional[str] = None,
    ) -> None:
        try:
            file_size, mtime_ns = _file_fingerprint(filepath)
            now_utc = datetime.now(timezone.utc).isoformat()
            self._db.execute(
                """
                INSERT INTO ingestion_source_files (
                    source_type, source_file, file_size, mtime_ns,
                    status, last_ingested_at, error_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_file) DO UPDATE SET
                    file_size = excluded.file_size,
                    mtime_ns = excluded.mtime_ns,
                    status = excluded.status,
                    last_ingested_at = excluded.last_ingested_at,
                    error_text = excluded.error_text
                """,
                (
                    source_type,
                    filepath.name,
                    file_size,
                    mtime_ns,
                    status,
                    now_utc,
                    error_text[:2000] if error_text else None,
                ),
            )
        except Exception:
            logger.warning("Could not record ingestion source file state for %s", filepath.name)

    def _ingest_one_trade(self, filepath: Path, result: IngestionResult) -> None:
        """Parse one trade JSON file and insert into trades + trade_features."""
        data = _load_json_object(filepath, "trade")

        # Validate and normalize JSON before anything reaches SQLite.
        _validate_trade_data(data)

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
        data = _load_json_object(filepath, "ranking")

        # Validate and normalize JSON before anything reaches SQLite.
        _validate_ranking_data(data)

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
                json.dumps(longs[:10], allow_nan=False),   # store top 10 longs summary
                json.dumps(shorts[:10], allow_nan=False),  # store top 10 shorts summary
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
