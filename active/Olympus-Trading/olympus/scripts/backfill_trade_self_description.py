"""
One-time Olympus trade self-description migration/backfill.

Historical regime labels are approximate because older trades did not persist
entry_cycle_id at execution time. We therefore link each trade to the nearest
ranking cycle at or before entry_time, then classify regime from that cycle's
stored cross-sectional rankings using core.trading.regime.py.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from core.logger import get_logger
from core.memory.database import Database
from core.memory.enrichment import TradeContextEnricher

logger = get_logger(__name__)

REQUIRED_FEATURE_FIELDS = [
    "rvol_at_entry",
    "score_at_entry",
    "range_position_at_entry",
    "vwap_deviation_at_entry",
    "atr_at_entry",
    "close_at_entry",
    "volume_at_entry",
]

VIEW_SQL = [
    """
    CREATE VIEW v_trades_full AS
    SELECT
        t.*,
        tf.roc_5, tf.roc_10, tf.roc_20, tf.acceleration,
        tf.rvol_at_entry, tf.vwap_deviation_at_entry, tf.range_position_at_entry,
        tf.raw_score, tf.score_at_entry AS feature_score_at_entry,
        tf.close_at_entry, tf.volume_at_entry, tf.vwap_at_entry,
        tf.atr_at_entry, tf.high_20, tf.low_20, tf.bar_count_used
    FROM trades t
    LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id
    """,
    """
    CREATE VIEW v_trades_enriched AS
    SELECT
        t.*,
        tf.symbol AS feature_symbol,
        tf.roc_5,
        tf.roc_10,
        tf.roc_20,
        tf.acceleration,
        tf.rvol_at_entry,
        tf.score_at_entry AS feature_score_at_entry,
        tf.range_position_at_entry,
        tf.vwap_deviation_at_entry,
        tf.raw_score,
        tf.close_at_entry,
        tf.volume_at_entry,
        tf.vwap_at_entry,
        tf.atr_at_entry,
        tf.high_20,
        tf.low_20,
        tf.bar_count_used,
        tf.captured_at AS feature_captured_at,
        cr.rank AS entry_rank_from_cycle_rankings,
        cr.score AS entry_score_from_cycle_rankings
    FROM trades t
    LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id
    LEFT JOIN cycle_rankings cr
        ON cr.cycle_id = t.entry_cycle_id
       AND cr.symbol = t.symbol
       AND cr.direction = t.direction
    """,
]


def _table_columns(db: Database, table_name: str) -> set[str]:
    return {row["name"] for row in db.query(f"PRAGMA table_info({table_name})")}


def _ensure_trade_regime_column(db: Database) -> None:
    if "regime" not in _table_columns(db, "trades"):
        db.execute(
            """
            ALTER TABLE trades
            ADD COLUMN regime TEXT
            CHECK (regime IN ('trend_up', 'trend_down', 'mixed', 'degraded'))
            """
        )


def _rename_trade_feature_columns(db: Database) -> None:
    renames = {
        "rvol": "rvol_at_entry",
        "normalized_score": "score_at_entry",
        "range_position": "range_position_at_entry",
        "vwap_deviation": "vwap_deviation_at_entry",
    }
    columns = _table_columns(db, "trade_features")
    for old_name, new_name in renames.items():
        if old_name in columns and new_name not in columns:
            db.execute(f"ALTER TABLE trade_features RENAME COLUMN {old_name} TO {new_name}")
            columns.remove(old_name)
            columns.add(new_name)


def _ensure_trade_indexes(db: Database) -> None:
    db.execute("CREATE INDEX IF NOT EXISTS idx_trades_regime ON trades(regime)")


def _drop_upgrade_sensitive_views(db: Database) -> None:
    for view_name in ("v_trades_enriched", "v_trades_full"):
        db.execute(f"DROP VIEW IF EXISTS {view_name}")


def _recreate_views(db: Database) -> None:
    _drop_upgrade_sensitive_views(db)
    for statement in VIEW_SQL:
        db.execute(statement)


def _ensure_trade_feature_rows(db: Database) -> int:
    cur = db.execute(
        """
        INSERT INTO trade_features (trade_id, symbol, captured_at)
        SELECT t.trade_id, t.symbol, t.entry_time
        FROM trades t
        LEFT JOIN trade_features tf ON tf.trade_id = t.trade_id
        WHERE tf.trade_id IS NULL
        """
    )
    return cur.rowcount if cur.rowcount != -1 else 0


def _delete_orphan_trade_features(db: Database) -> int:
    cur = db.execute(
        """
        DELETE FROM trade_features
        WHERE trade_id NOT IN (SELECT trade_id FROM trades)
        """
    )
    return cur.rowcount if cur.rowcount != -1 else 0


def _lookup_cycle_context(
    db: Database,
    cycle_id: Optional[str],
    symbol: str,
    direction: str,
) -> tuple[Optional[int], Optional[float]]:
    if not cycle_id:
        return None, None
    row = db.query_one(
        """
        SELECT rank, score
        FROM cycle_rankings
        WHERE cycle_id = ? AND symbol = ? AND direction = ?
        LIMIT 1
        """,
        (cycle_id, symbol, direction),
    )
    if row is None:
        return None, None
    return row["rank"], row["score"]


def _update_trade_row(
    db: Database,
    trade: dict,
    entry_cycle_id: Optional[str],
    regime: Optional[str],
    rank_from_cycle: Optional[int],
    score_from_cycle: Optional[float],
    now_utc: str,
) -> bool:
    new_rank = trade["rank_at_entry"] if trade["rank_at_entry"] is not None else rank_from_cycle
    new_score = trade["score_at_entry"] if trade["score_at_entry"] is not None else score_from_cycle
    changed = any(
        [
            entry_cycle_id != trade["entry_cycle_id"],
            regime != trade.get("regime"),
            new_rank != trade["rank_at_entry"],
            new_score != trade["score_at_entry"],
        ]
    )
    if not changed:
        return False

    db.execute(
        """
        UPDATE trades
        SET entry_cycle_id = ?,
            regime = ?,
            rank_at_entry = ?,
            score_at_entry = ?,
            updated_at = ?
        WHERE trade_id = ?
        """,
        (
            entry_cycle_id,
            regime,
            new_rank,
            new_score,
            now_utc,
            trade["trade_id"],
        ),
    )
    return True


def _update_trade_features_row(
    db: Database,
    trade: dict,
    existing_features: dict,
    score_hint: Optional[float],
    enricher: TradeContextEnricher,
    now_utc: str,
) -> None:
    snapshot = enricher.reconstruct_entry_snapshot(
        trade["symbol"],
        trade["entry_time"],
        existing_score=score_hint,
    )
    resolved = {
        "roc_5": snapshot.roc_5 if snapshot.roc_5 is not None else existing_features.get("roc_5"),
        "roc_10": snapshot.roc_10 if snapshot.roc_10 is not None else existing_features.get("roc_10"),
        "roc_20": snapshot.roc_20 if snapshot.roc_20 is not None else existing_features.get("roc_20"),
        "acceleration": snapshot.acceleration if snapshot.acceleration is not None else existing_features.get("acceleration"),
        "rvol_at_entry": snapshot.rvol_at_entry if snapshot.rvol_at_entry is not None else existing_features.get("rvol_at_entry"),
        "vwap_deviation_at_entry": snapshot.vwap_deviation_at_entry if snapshot.vwap_deviation_at_entry is not None else existing_features.get("vwap_deviation_at_entry"),
        "range_position_at_entry": snapshot.range_position_at_entry if snapshot.range_position_at_entry is not None else existing_features.get("range_position_at_entry"),
        "raw_score": snapshot.raw_score if snapshot.raw_score is not None else existing_features.get("raw_score"),
        "score_at_entry": snapshot.score_at_entry if snapshot.score_at_entry is not None else existing_features.get("score_at_entry") or score_hint,
        "close_at_entry": snapshot.close_at_entry if snapshot.close_at_entry is not None else existing_features.get("close_at_entry"),
        "volume_at_entry": snapshot.volume_at_entry if snapshot.volume_at_entry is not None else existing_features.get("volume_at_entry"),
        "vwap_at_entry": snapshot.vwap_at_entry if snapshot.vwap_at_entry is not None else existing_features.get("vwap_at_entry"),
        "atr_at_entry": snapshot.atr_at_entry if snapshot.atr_at_entry is not None else existing_features.get("atr_at_entry"),
        "high_20": snapshot.high_20 if snapshot.high_20 is not None else existing_features.get("high_20"),
        "low_20": snapshot.low_20 if snapshot.low_20 is not None else existing_features.get("low_20"),
        "bar_count_used": snapshot.bar_count_used if snapshot.bar_count_used is not None else existing_features.get("bar_count_used"),
        "captured_at": snapshot.captured_at or existing_features.get("captured_at") or trade["entry_time"],
    }

    db.execute(
        """
        UPDATE trade_features
        SET roc_5 = ?,
            roc_10 = ?,
            roc_20 = ?,
            acceleration = ?,
            rvol_at_entry = ?,
            vwap_deviation_at_entry = ?,
            range_position_at_entry = ?,
            raw_score = ?,
            score_at_entry = ?,
            close_at_entry = ?,
            volume_at_entry = ?,
            vwap_at_entry = ?,
            atr_at_entry = ?,
            high_20 = ?,
            low_20 = ?,
            bar_count_used = ?,
            captured_at = ?,
            updated_at = ?
        WHERE trade_id = ?
        """,
        (
            resolved["roc_5"],
            resolved["roc_10"],
            resolved["roc_20"],
            resolved["acceleration"],
            resolved["rvol_at_entry"],
            resolved["vwap_deviation_at_entry"],
            resolved["range_position_at_entry"],
            resolved["raw_score"],
            resolved["score_at_entry"],
            resolved["close_at_entry"],
            resolved["volume_at_entry"],
            resolved["vwap_at_entry"],
            resolved["atr_at_entry"],
            resolved["high_20"],
            resolved["low_20"],
            resolved["bar_count_used"],
            resolved["captured_at"],
            now_utc,
            trade["trade_id"],
        ),
    )


def _missing_feature_counts(db: Database) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field_name in REQUIRED_FEATURE_FIELDS:
        row = db.query_one(
            f"SELECT COUNT(*) AS missing_count FROM trade_features WHERE {field_name} IS NULL"
        )
        counts[field_name] = int(row["missing_count"]) if row else 0
    return counts


def _regime_distribution(db: Database) -> dict[str, int]:
    rows = db.query(
        """
        SELECT COALESCE(regime, 'NULL') AS regime_name, COUNT(*) AS trade_count
        FROM trades
        GROUP BY COALESCE(regime, 'NULL')
        ORDER BY trade_count DESC, regime_name
        """
    )
    return {row["regime_name"]: row["trade_count"] for row in rows}


def run(db_path: Optional[Path] = None, allow_network_fallback: bool = True) -> dict:
    if db_path is None:
        db_path = Path(settings.DB_PATH)

    db = Database(db_path)
    db.initialize()

    _drop_upgrade_sensitive_views(db)
    _ensure_trade_regime_column(db)
    _rename_trade_feature_columns(db)
    _ensure_trade_indexes(db)
    deleted_orphan_feature_rows = _delete_orphan_trade_features(db)
    inserted_feature_rows = _ensure_trade_feature_rows(db)
    _recreate_views(db)

    enricher = TradeContextEnricher(
        db,
        allow_network_fallback=allow_network_fallback,
    )

    trades = db.query(
        """
        SELECT
            trade_id,
            symbol,
            direction,
            entry_time,
            entry_cycle_id,
            regime,
            rank_at_entry,
            score_at_entry
        FROM trades
        ORDER BY entry_time ASC
        """
    )

    trade_updates = 0
    feature_updates = 0
    now_utc = datetime.now(timezone.utc).isoformat()
    for trade in trades:
        entry_cycle_id = enricher.resolve_entry_cycle_id(trade["entry_time"])
        rank_from_cycle, score_from_cycle = _lookup_cycle_context(
            db,
            entry_cycle_id,
            trade["symbol"],
            trade["direction"],
        )
        regime = enricher.resolve_regime(entry_cycle_id)
        if _update_trade_row(
            db,
            trade,
            entry_cycle_id,
            regime,
            rank_from_cycle,
            score_from_cycle,
            now_utc,
        ):
            trade_updates += 1

        feature_row = db.query_one(
            "SELECT * FROM trade_features WHERE trade_id = ?",
            (trade["trade_id"],),
        ) or {"trade_id": trade["trade_id"]}
        _update_trade_features_row(
            db,
            trade,
            feature_row,
            score_hint=trade["score_at_entry"] or score_from_cycle,
            enricher=enricher,
            now_utc=now_utc,
        )
        feature_updates += 1

    _recreate_views(db)

    smoke_rows = db.query(
        """
        SELECT regime, COUNT(*) AS trade_count, AVG(realized_pnl) AS avg_realized_pnl
        FROM v_trades_enriched
        GROUP BY regime
        ORDER BY regime
        """
    )
    missing_counts = _missing_feature_counts(db)
    regime_distribution = _regime_distribution(db)

    summary = {
        "db_path": str(db_path),
        "inserted_missing_trade_feature_rows": inserted_feature_rows,
        "deleted_orphan_trade_feature_rows": deleted_orphan_feature_rows,
        "trades_processed": len(trades),
        "trade_rows_updated": trade_updates,
        "trade_feature_rows_updated": feature_updates,
        "missing_feature_counts": missing_counts,
        "regime_distribution": regime_distribution,
        "smoke_query_rows": smoke_rows,
    }

    db.execute(
        """
        INSERT INTO system_events
            (event_time, event_type, symbol, description, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now_utc,
            "data_quality",
            None,
            "Trade self-description migration completed",
            json.dumps(summary),
            now_utc,
            now_utc,
        ),
    )

    logger.info("Trade self-description backfill summary: %s", summary)
    db.close()
    return summary


def main(argv: list[str]) -> int:
    db_path = Path(argv[1]) if len(argv) > 1 else Path(settings.DB_PATH)
    allow_network_fallback = "--no-network" not in argv[1:]
    summary = run(db_path=db_path, allow_network_fallback=allow_network_fallback)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
