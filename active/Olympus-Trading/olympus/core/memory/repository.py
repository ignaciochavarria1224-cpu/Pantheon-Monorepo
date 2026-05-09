"""
Read-only query layer for Olympus Phase 4.
Repository provides all structured reads against the SQLite database.
All methods return plain dicts or lists of dicts — no ORM objects.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.memory.database import Database

logger = get_logger(__name__)


class Repository:
    """
    All read queries for Olympus.

    Designed for Phase 5 (Apex) consumption — returns clean, flat dicts.
    Every query is a SELECT — zero writes happen here.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        logger.info("Repository initialized")

    # ------------------------------------------------------------------
    # Trade queries
    # ------------------------------------------------------------------

    def get_trades(
        self,
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        exit_reason: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Return completed trades with optional filters.
        Results are ordered by entry_time DESC.
        """
        clauses = []
        params: list = []

        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(symbol)
        if direction is not None:
            clauses.append("direction = ?")
            params.append(direction)
        if exit_reason is not None:
            clauses.append("exit_reason = ?")
            params.append(exit_reason)
        if since is not None:
            clauses.append("entry_time >= ?")
            params.append(since.isoformat())

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""

        sql = f"SELECT * FROM trades {where} ORDER BY entry_time DESC {limit_clause}"
        return self._db.query(sql, tuple(params))

    def get_recent_trades(self, n: int = 20) -> list[dict]:
        """Return the n most recently closed trades."""
        return self._db.query(
            "SELECT * FROM trades ORDER BY exit_time DESC LIMIT ?",
            (int(n),),
        )

    def get_trade_count(
        self,
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
    ) -> int:
        """Return total number of completed trades, optionally filtered."""
        clauses = []
        params: list = []
        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(symbol)
        if direction is not None:
            clauses.append("direction = ?")
            params.append(direction)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        row = self._db.query_one(
            f"SELECT COUNT(*) AS n FROM trades {where}", tuple(params)
        )
        return row["n"] if row else 0

    def get_trades_for_apex(self, limit: int = 500, quality: str = "clean") -> list[dict]:
        """
        Return the most recent trades joined with feature data.
        Used by Apex to build analysis context.
        """
        if quality == "all":
            return self._db.query(
                "SELECT * FROM v_trades_enriched ORDER BY entry_time DESC LIMIT ?",
                (int(limit),),
            )
        return self._db.query(
            """
            SELECT e.*, q.quality, q.primary_reason, q.apex_trainable
            FROM v_trades_enriched e
            JOIN v_trade_quality_flags q ON q.trade_id = e.trade_id
            WHERE q.quality = ?
            ORDER BY e.entry_time DESC
            LIMIT ?
            """,
            (quality, int(limit)),
        )

    def get_apex_training_trades(self, quality: str = "clean", limit: int = 500) -> list[dict]:
        """Return trades intended for Apex training; defaults to clean rows only."""
        return self.get_trades_for_apex(limit=limit, quality=quality)

    def get_trade_quality_summary(self) -> dict:
        """Return trade counts by Apex quality label."""
        rows = self._db.query(
            """
            SELECT quality, COUNT(*) AS n
            FROM v_trade_quality_flags
            GROUP BY quality
            ORDER BY quality
            """
        )
        summary = {row["quality"]: row["n"] for row in rows}
        latest_clean = self._db.query_one(
            """
            SELECT MAX(t.entry_time) AS latest_clean_trade_at
            FROM trades t
            JOIN v_trade_quality_flags q ON q.trade_id = t.trade_id
            WHERE q.quality = 'clean'
            """
        )
        mismatch_count = self._db.query_one(
            "SELECT COUNT(*) AS n FROM system_events WHERE event_type = 'broker_mismatch'"
        )
        return {
            "counts": summary,
            "total": sum(summary.values()),
            "latest_clean_trade_at": (
                latest_clean.get("latest_clean_trade_at") if latest_clean else None
            ),
            "broker_mismatch_events": mismatch_count["n"] if mismatch_count else 0,
        }

    # ------------------------------------------------------------------
    # Open positions queries
    # ------------------------------------------------------------------

    def insert_open_position(
        self,
        position_id: str,
        symbol: str,
        direction: str,
        size: int,
        entry_time: str,
        entry_price: float,
        entry_cycle_id: Optional[str] = None,
        features: Optional[str] = None,
        broker_order_id: Optional[str] = None,
        last_seen_at: Optional[str] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        source: Optional[str] = None,
    ) -> None:
        """Insert a new open position row."""
        now_utc = datetime.now().isoformat()
        self._db.execute(
            """
            INSERT INTO open_positions (
                position_id, symbol, direction, size, entry_time, entry_price,
                entry_cycle_id, features, broker_order_id, last_seen_at,
                stop_price, target_price, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position_id, symbol, direction, size, entry_time, entry_price,
                entry_cycle_id, features, broker_order_id, last_seen_at,
                stop_price, target_price, source, now_utc, now_utc,
            ),
        )

    def delete_open_position_by_id(self, position_id: str) -> None:
        """Delete an open position by its position_id."""
        self._db.execute(
            "DELETE FROM open_positions WHERE position_id = ?",
            (position_id,),
        )

    def get_open_positions(self) -> list[dict]:
        """Return all open positions."""
        return self._db.query("SELECT * FROM open_positions")

    def get_open_position_by_id(self, position_id: str) -> Optional[dict]:
        """Return a single open position by position_id."""
        return self._db.query_one(
            "SELECT * FROM open_positions WHERE position_id = ?",
            (position_id,),
        )

    def update_open_position_last_seen(self, position_id: str, timestamp: str) -> None:
        """Update the last_seen_at and updated_at for an open position."""
        now_utc = datetime.now().isoformat()
        self._db.execute(
            """
            UPDATE open_positions
            SET last_seen_at = ?, updated_at = ?
            WHERE position_id = ?
            """,
            (timestamp, now_utc, position_id),
        )

    # ------------------------------------------------------------------
    # Apex reports
    # ------------------------------------------------------------------

    def get_latest_apex_report(self, report_type: str) -> Optional[dict]:
        """Return the latest Apex report for a given type."""
        row = self._db.query_one(
            """
            SELECT *
            FROM apex_reports
            WHERE report_type = ?
            ORDER BY period_end DESC, generated_at DESC
            LIMIT 1
            """,
            (report_type,),
        )
        return self._decode_apex_report(row)

    def get_apex_reports(
        self,
        report_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Return Apex reports with optional type and date filtering."""
        clauses = []
        params: list = []
        if report_type is not None:
            clauses.append("report_type = ?")
            params.append(report_type)
        if since is not None:
            clauses.append("period_end >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("period_start <= ?")
            params.append(until.isoformat())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        rows = self._db.query(
            f"""
            SELECT *
            FROM apex_reports
            {where}
            ORDER BY period_end DESC, generated_at DESC
            {limit_clause}
            """,
            tuple(params),
        )
        return [self._decode_apex_report(row) for row in rows]

    def get_unconsumed_apex_reports(self, limit: int = 20) -> list[dict]:
        """Return the newest reports not yet marked consumed by Pantheon."""
        rows = self._db.query(
            """
            SELECT *
            FROM apex_reports
            WHERE consumed_by_pantheon = 0
            ORDER BY period_end DESC, generated_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [self._decode_apex_report(row) for row in rows]

    def get_latest_apex_summary_bundle(self) -> dict:
        """Return the latest report row for each core Apex report type."""
        bundle = {}
        for report_type in (
            "daily_performance",
            "weekly_performance",
            "risk_watch",
            "ranking_behavior",
        ):
            bundle[report_type] = self.get_latest_apex_report(report_type)
        return bundle

    # ------------------------------------------------------------------
    # Performance summary queries
    # ------------------------------------------------------------------

    def get_performance_summary(
        self,
        since: Optional[datetime] = None,
    ) -> dict:
        """
        Return aggregate performance metrics across all trades.
        Optionally restricted to trades since `since`.
        """
        where = ""
        params: tuple = ()
        if since is not None:
            where = "WHERE entry_time >= ?"
            params = (since.isoformat(),)

        row = self._db.query_one(
            f"""
            SELECT
                COUNT(*) AS total_trades,
                SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners,
                SUM(CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END) AS losers,
                ROUND(
                    100.0 * SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END)
                    / MAX(COUNT(*), 1),
                    1
                ) AS win_rate_pct,
                ROUND(AVG(r_multiple), 3) AS avg_r_multiple,
                ROUND(SUM(realized_pnl), 2) AS total_pnl,
                ROUND(AVG(realized_pnl), 2) AS avg_pnl,
                ROUND(AVG(hold_duration_minutes), 0) AS avg_hold_minutes,
                MIN(entry_time) AS first_trade_at,
                MAX(exit_time) AS last_trade_at
            FROM trades
            {where}
            """,
            params,
        )
        return row if row else {}

    def get_symbol_performance(self) -> list[dict]:
        """Per-symbol, per-direction win rate, avg R, total PnL."""
        return self._db.query("SELECT * FROM v_symbol_performance ORDER BY total_pnl DESC")

    def get_exit_reason_stats(self) -> list[dict]:
        """Stats broken down by exit reason and direction."""
        return self._db.query("SELECT * FROM v_exit_reason_stats ORDER BY exit_reason, direction")

    def get_rolling_7day(self) -> list[dict]:
        """Daily trade stats for the trailing 7 days."""
        return self._db.query("SELECT * FROM v_rolling_7day")

    def get_feature_buckets(self) -> list[dict]:
        """Performance bucketed by momentum regime (uses roc_20)."""
        return self._db.query(
            "SELECT * FROM v_feature_buckets ORDER BY direction, momentum_bucket"
        )

    # ------------------------------------------------------------------
    # Ranking cycle queries
    # ------------------------------------------------------------------

    def get_latest_cycle(self) -> Optional[dict]:
        """Return the most recently ingested ranking cycle."""
        return self._db.query_one(
            "SELECT * FROM ranking_cycles ORDER BY cycle_timestamp DESC LIMIT 1"
        )

    def get_cycle_count(self) -> int:
        """Total number of ranking cycles stored."""
        row = self._db.query_one("SELECT COUNT(*) AS n FROM ranking_cycles")
        return row["n"] if row else 0

    def get_symbol_rank_history(
        self,
        symbol: str,
        direction: str,
        limit: int = 100,
    ) -> list[dict]:
        """
        Return rank/score history for a symbol in a given direction,
        most recent first.
        """
        return self._db.query(
            """
            SELECT cycle_timestamp, rank, score
            FROM cycle_rankings
            WHERE symbol = ? AND direction = ?
            ORDER BY cycle_timestamp DESC
            LIMIT ?
            """,
            (symbol, direction, int(limit)),
        )

    # ------------------------------------------------------------------
    # Risk / pattern queries
    # ------------------------------------------------------------------

    def get_loss_streaks(self, min_streak: int = 3) -> list[dict]:
        """
        Return consecutive loss streaks of at least `min_streak` trades.
        Uses the gap-and-islands pattern with window functions (SQLite 3.25+).
        Each row: streak_start, streak_end, streak_length, total_loss.
        """
        return self._db.query(
            """
            WITH ordered AS (
                SELECT
                    trade_id,
                    exit_time,
                    realized_pnl,
                    CASE WHEN realized_pnl <= 0 THEN 1 ELSE 0 END AS is_loss,
                    ROW_NUMBER() OVER (ORDER BY exit_time) AS rn
                FROM trades
            ),
            flagged AS (
                SELECT *,
                    rn - ROW_NUMBER() OVER (
                        PARTITION BY is_loss ORDER BY exit_time
                    ) AS grp
                FROM ordered
            ),
            streaks AS (
                SELECT
                    MIN(exit_time) AS streak_start,
                    MAX(exit_time) AS streak_end,
                    COUNT(*)       AS streak_length,
                    ROUND(SUM(realized_pnl), 2) AS total_loss
                FROM flagged
                WHERE is_loss = 1
                GROUP BY grp
            )
            SELECT *
            FROM streaks
            WHERE streak_length >= ?
            ORDER BY streak_start DESC
            """,
            (int(min_streak),),
        )

    def get_drawdown_periods(self) -> list[dict]:
        """
        Return the running cumulative PnL and peak drawdown per trade.
        Ordered by exit_time ASC.
        """
        return self._db.query(
            """
            SELECT
                trade_id,
                symbol,
                exit_time,
                realized_pnl,
                ROUND(SUM(realized_pnl) OVER (ORDER BY exit_time), 2) AS cumulative_pnl,
                ROUND(
                    SUM(realized_pnl) OVER (ORDER BY exit_time)
                    - MAX(SUM(realized_pnl) OVER (ORDER BY exit_time))
                          OVER (ORDER BY exit_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
                    2
                ) AS drawdown
            FROM trades
            ORDER BY exit_time ASC
            """
        )

    # ------------------------------------------------------------------
    # System events
    # ------------------------------------------------------------------

    def get_system_events(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return system events, optionally filtered by type and time."""
        clauses = []
        params: list = []
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            clauses.append("event_time >= ?")
            params.append(since.isoformat())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        return self._db.query(
            f"SELECT * FROM system_events {where} ORDER BY event_time DESC LIMIT ?",
            tuple(params),
        )

    def _decode_apex_report(self, row: Optional[dict]) -> Optional[dict]:
        if row is None:
            return None
        decoded = dict(row)
        raw = decoded.get("content_json")
        if raw:
            try:
                decoded["content"] = json.loads(raw)
            except Exception:
                decoded["content"] = None
        else:
            decoded["content"] = None
        return decoded
