"""
Persistent Apex report generation for Olympus Phase 5.

The SQLite row in apex_reports is the canonical artifact. Historical markdown
reports remain useful for humans, but Apex and future Pantheon consumers should
read structured content_json from the database first.
"""

from __future__ import annotations

import json
import sqlite3
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from core.logger import get_logger

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_SCHEMA_VERSION = 1
_REPORT_TYPES = {
    "daily_performance",
    "weekly_performance",
    "risk_watch",
    "ranking_behavior",
}
_DEGRADED_SCORED_THRESHOLD = 150
_REQUIRED_FEATURE_COLUMNS = (
    "rvol_at_entry",
    "feature_score_at_entry",
    "range_position_at_entry",
    "vwap_deviation_at_entry",
    "atr_at_entry",
    "close_at_entry",
    "volume_at_entry",
)


@dataclass(frozen=True)
class ReportWindow:
    report_type: str
    report_date: date
    period_start_et: datetime
    period_end_et: datetime

    @property
    def period_start_utc(self) -> str:
        return self.period_start_et.astimezone(timezone.utc).isoformat()

    @property
    def period_end_utc(self) -> str:
        return self.period_end_et.astimezone(timezone.utc).isoformat()

    @property
    def report_id(self) -> str:
        start_key = self.period_start_et.isoformat()
        end_key = self.period_end_et.isoformat()
        return f"{self.report_type}:{start_key}:{end_key}"


class ApexReportGenerator:
    """Generate and persist structured Apex reports."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        from config.settings import settings as _settings

        if db_path is None:
            db_path = _settings.DB_PATH
        self._db_path = Path(db_path)
        self._reports_dir = self._db_path.parent / "reports" / "apex"

    def generate(self, report_type: str, report_date: Optional[date] = None) -> Optional[dict]:
        """
        Generate one report and upsert it into apex_reports.
        Returns a small result dict on success, or None on failure.
        Never raises.
        """
        if report_type not in _REPORT_TYPES:
            raise ValueError(f"Unsupported report_type: {report_type}")

        try:
            window = self._resolve_window(report_type, report_date)
            from core.memory.database import Database

            db = Database(self._db_path)
            db.initialize()
            db.close()
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            try:
                payload = self._build_payload(conn, window)
                summary_text = self._build_summary_text(payload)
                self._upsert_report(conn, window, payload, summary_text)
                self._write_markdown_summary(window, payload, summary_text)
                conn.commit()
            finally:
                conn.close()

            logger.info(
                "Apex report generated -> %s (%s to %s)",
                report_type,
                payload["meta"]["period_start"],
                payload["meta"]["period_end"],
            )
            return {
                "report_id": window.report_id,
                "report_type": report_type,
                "period_start": payload["meta"]["period_start"],
                "period_end": payload["meta"]["period_end"],
                "summary_text": summary_text,
            }
        except Exception:
            logger.error(
                "ApexReportGenerator.generate(%s) failed:\n%s",
                report_type,
                traceback.format_exc(),
            )
            self._log_failure(report_type, report_date, traceback.format_exc())
            return None

    def generate_daily_suite(
        self,
        report_date: Optional[date] = None,
        include_weekly: bool = False,
    ) -> list[dict]:
        """Generate the daily Apex suite and optionally the weekly report."""
        generated: list[dict] = []
        for report_type in ("daily_performance", "risk_watch", "ranking_behavior"):
            result = self.generate(report_type, report_date=report_date)
            if result is not None:
                generated.append(result)
        if include_weekly:
            result = self.generate("weekly_performance", report_date=report_date)
            if result is not None:
                generated.append(result)
        return generated

    def _resolve_window(self, report_type: str, report_date: Optional[date]) -> ReportWindow:
        if report_date is None:
            report_date = datetime.now(_ET).date()

        if report_type == "weekly_performance":
            period_end_et = datetime.combine(report_date, time(23, 59, 59), tzinfo=_ET)
            period_start_et = datetime.combine(
                report_date - timedelta(days=6),
                time(0, 0, 0),
                tzinfo=_ET,
            )
        else:
            period_start_et = datetime.combine(report_date, time(0, 0, 0), tzinfo=_ET)
            period_end_et = datetime.combine(report_date, time(23, 59, 59), tzinfo=_ET)

        return ReportWindow(
            report_type=report_type,
            report_date=report_date,
            period_start_et=period_start_et,
            period_end_et=period_end_et,
        )

    def _build_payload(self, conn: sqlite3.Connection, window: ReportWindow) -> dict:
        trades = self._query_trades(conn, window)
        cycles = self._query_cycles(conn, window)
        system_events = self._query_system_events(conn, window)
        last_50_trades = self._query_recent_trades(conn, window.period_end_utc, limit=50)

        performance = self._build_performance(trades)
        risk = self._build_risk(trades, cycles, system_events, last_50_trades)
        ranking = self._build_ranking(trades, cycles)
        regime = self._build_regime(trades, cycles, system_events)
        symbols = self._build_symbols(trades, last_50_trades)
        anomalies = self._build_anomalies(trades, cycles, system_events, ranking, risk)
        recommendations = self._build_recommendations(
            performance=performance,
            risk=risk,
            ranking=ranking,
            regime=regime,
            anomalies=anomalies,
        )

        latest_trade_at = trades[-1]["exit_time"] if trades else None
        latest_cycle_at = cycles[-1]["cycle_timestamp"] if cycles else None
        latest_event_at = system_events[-1]["event_time"] if system_events else None

        return {
            "meta": {
                "schema_version": _SCHEMA_VERSION,
                "report_type": window.report_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period_start": window.period_start_utc,
                "period_end": window.period_end_utc,
                "trade_count": len(trades),
                "cycle_count": len(cycles),
                "system_event_count": len(system_events),
                "data_freshness": {
                    "latest_trade_at": latest_trade_at,
                    "latest_cycle_at": latest_cycle_at,
                    "latest_event_at": latest_event_at,
                    "has_trade_data": bool(trades),
                    "has_cycle_data": bool(cycles),
                    "has_system_events": bool(system_events),
                },
            },
            "performance": performance,
            "risk": risk,
            "ranking": ranking,
            "regime": regime,
            "symbols": symbols,
            "anomalies": anomalies,
            "recommendations": recommendations,
        }

    def _query_trades(self, conn: sqlite3.Connection, window: ReportWindow) -> list[dict]:
        rows = conn.execute(
            """
            SELECT *
            FROM v_trades_enriched
            WHERE exit_time >= ? AND exit_time <= ?
            ORDER BY exit_time ASC
            """,
            (window.period_start_utc, window.period_end_utc),
        ).fetchall()
        return [dict(row) for row in rows]

    def _query_cycles(self, conn: sqlite3.Connection, window: ReportWindow) -> list[dict]:
        rows = conn.execute(
            """
            SELECT cycle_id, cycle_timestamp, universe_size, scored_count, error_count,
                   duration_seconds, top_longs_json, top_shorts_json
            FROM ranking_cycles
            WHERE cycle_timestamp >= ? AND cycle_timestamp <= ?
            ORDER BY cycle_timestamp ASC
            """,
            (window.period_start_utc, window.period_end_utc),
        ).fetchall()
        cycles = [dict(row) for row in rows]
        for cycle in cycles:
            cycle["top_longs"] = self._loads_json(cycle.get("top_longs_json"), [])
            cycle["top_shorts"] = self._loads_json(cycle.get("top_shorts_json"), [])
        return cycles

    def _query_system_events(self, conn: sqlite3.Connection, window: ReportWindow) -> list[dict]:
        rows = conn.execute(
            """
            SELECT event_time, event_type, symbol, description, metadata_json
            FROM system_events
            WHERE event_time >= ? AND event_time <= ?
            ORDER BY event_time ASC
            """,
            (window.period_start_utc, window.period_end_utc),
        ).fetchall()
        events = [dict(row) for row in rows]
        for event in events:
            event["metadata"] = self._loads_json(event.get("metadata_json"), {})
        return events

    def _query_recent_trades(self, conn: sqlite3.Connection, end_utc: str, limit: int) -> list[dict]:
        rows = conn.execute(
            """
            SELECT trade_id, symbol, exit_time, realized_pnl, direction, exit_reason, regime
            FROM v_trades_enriched
            WHERE exit_time <= ?
            ORDER BY exit_time DESC
            LIMIT ?
            """,
            (end_utc, int(limit)),
        ).fetchall()
        recent = [dict(row) for row in rows]
        recent.reverse()
        return recent

    def _build_performance(self, trades: list[dict]) -> dict:
        total_trades = len(trades)
        winners = [trade for trade in trades if float(trade["realized_pnl"]) > 0]
        losers = [trade for trade in trades if float(trade["realized_pnl"]) <= 0]
        total_pnl = round(sum(float(trade["realized_pnl"]) for trade in trades), 4)
        avg_pnl = round(total_pnl / total_trades, 4) if total_trades else 0.0
        avg_r = round(
            sum(float(trade["r_multiple"]) for trade in trades) / total_trades,
            4,
        ) if total_trades else 0.0
        gross_wins = sum(float(trade["realized_pnl"]) for trade in winners)
        gross_losses = abs(sum(float(trade["realized_pnl"]) for trade in losers))
        profit_factor = round(gross_wins / gross_losses, 4) if gross_losses else None
        by_side: dict[str, dict] = {}

        for side in ("long", "short"):
            side_trades = [trade for trade in trades if trade["direction"] == side]
            side_count = len(side_trades)
            side_winners = [trade for trade in side_trades if float(trade["realized_pnl"]) > 0]
            side_total_pnl = sum(float(trade["realized_pnl"]) for trade in side_trades)
            by_side[side] = {
                "trade_count": side_count,
                "win_rate_pct": round(100.0 * len(side_winners) / side_count, 2) if side_count else 0.0,
                "avg_pnl": round(side_total_pnl / side_count, 4) if side_count else 0.0,
                "avg_r_multiple": round(
                    sum(float(trade["r_multiple"]) for trade in side_trades) / side_count,
                    4,
                ) if side_count else 0.0,
                "total_pnl": round(side_total_pnl, 4),
            }

        return {
            "trade_count": total_trades,
            "win_rate_pct": round(100.0 * len(winners) / total_trades, 2) if total_trades else 0.0,
            "avg_pnl": avg_pnl,
            "avg_r_multiple": avg_r,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "avg_winner_pnl": round(gross_wins / len(winners), 4) if winners else 0.0,
            "avg_loser_pnl": round(-gross_losses / len(losers), 4) if losers else 0.0,
            "by_side": by_side,
        }

    def _build_risk(
        self,
        trades: list[dict],
        cycles: list[dict],
        system_events: list[dict],
        last_50_trades: list[dict],
    ) -> dict:
        stop_trades = [trade for trade in trades if trade.get("exit_reason") == "stop"]
        stop_counter = Counter(trade["symbol"] for trade in stop_trades)
        degraded_cycles = [
            cycle for cycle in cycles
            if int(cycle.get("scored_count", 0)) < _DEGRADED_SCORED_THRESHOLD
        ]
        cycle_diagnostics = [
            event for event in system_events if event.get("event_type") == "cycle_diagnostics"
        ]
        degraded_events = [
            event
            for event in cycle_diagnostics
            if self._event_regime_name(event) == "degraded"
        ]
        weak_symbols = self._symbol_rollup(trades, ascending=True)[:5]
        loss_streaks = self._compute_loss_streaks(trades)
        cooldown_candidates = self._compute_cooldown_candidates(last_50_trades)
        return {
            "loss_streaks": loss_streaks[:5],
            "weak_symbols": weak_symbols,
            "stop_concentration": [
                {"symbol": symbol, "stop_count": count}
                for symbol, count in stop_counter.most_common(5)
            ],
            "degraded_cycle_count": len(degraded_cycles),
            "degraded_cycle_pct": round(100.0 * len(degraded_cycles) / len(cycles), 2) if cycles else 0.0,
            "degraded_diagnostic_count": len(degraded_events),
            "cycle_diagnostic_count": len(cycle_diagnostics),
            "cooldown_candidates": cooldown_candidates,
        }

    def _build_ranking(self, trades: list[dict], cycles: list[dict]) -> dict:
        rank_buckets: dict[str, list[dict]] = defaultdict(list)
        rank_drift_samples: list[float] = []
        for trade in trades:
            rank_at_entry = trade.get("entry_rank_from_cycle_rankings") or trade.get("rank_at_entry")
            rank_at_exit = trade.get("rank_at_exit")
            bucket = self._rank_bucket(rank_at_entry)
            rank_buckets[bucket].append(trade)
            if rank_at_entry is not None and rank_at_exit is not None:
                rank_drift_samples.append(float(rank_at_exit) - float(rank_at_entry))

        bucket_rows = []
        for bucket in ("1-3", "4-10", "11+", "unknown"):
            bucket_trades = rank_buckets.get(bucket, [])
            count = len(bucket_trades)
            winners = [trade for trade in bucket_trades if float(trade["realized_pnl"]) > 0]
            bucket_rows.append(
                {
                    "bucket": bucket,
                    "trade_count": count,
                    "win_rate_pct": round(100.0 * len(winners) / count, 2) if count else 0.0,
                    "avg_pnl": round(
                        sum(float(trade["realized_pnl"]) for trade in bucket_trades) / count,
                        4,
                    ) if count else 0.0,
                    "avg_r_multiple": round(
                        sum(float(trade["r_multiple"]) for trade in bucket_trades) / count,
                        4,
                    ) if count else 0.0,
                }
            )

        leader_changes = self._detect_leader_changes(cycles)
        return {
            "rank_bucket_performance": bucket_rows,
            "avg_rank_drift": round(sum(rank_drift_samples) / len(rank_drift_samples), 4) if rank_drift_samples else 0.0,
            "mean_abs_rank_drift": round(
                sum(abs(sample) for sample in rank_drift_samples) / len(rank_drift_samples),
                4,
            ) if rank_drift_samples else 0.0,
            "leader_change_count": len(leader_changes),
            "leader_changes": leader_changes[:10],
            "top_symbols_by_pnl": self._symbol_rollup(trades, ascending=False)[:5],
            "bottom_symbols_by_pnl": self._symbol_rollup(trades, ascending=True)[:5],
        }

    def _build_regime(
        self,
        trades: list[dict],
        cycles: list[dict],
        system_events: list[dict],
    ) -> dict:
        regime_rows = []
        grouped: dict[str, list[dict]] = defaultdict(list)
        for trade in trades:
            grouped[(trade.get("regime") or "unknown")].append(trade)

        for regime_name in ("trend_up", "trend_down", "mixed", "degraded", "unknown"):
            regime_trades = grouped.get(regime_name, [])
            count = len(regime_trades)
            regime_rows.append(
                {
                    "regime": regime_name,
                    "trade_count": count,
                    "avg_pnl": round(
                        sum(float(trade["realized_pnl"]) for trade in regime_trades) / count,
                        4,
                    ) if count else 0.0,
                    "avg_r_multiple": round(
                        sum(float(trade["r_multiple"]) for trade in regime_trades) / count,
                        4,
                    ) if count else 0.0,
                }
            )

        cycle_diagnostics = [
            self._event_regime_name(event)
            for event in system_events
            if event.get("event_type") == "cycle_diagnostics"
        ]
        regime_counter = Counter(cycle_diagnostics)
        if not regime_counter and cycles:
            regime_counter["unknown"] = len(cycles)

        return {
            "trade_performance": regime_rows,
            "cycle_distribution": [
                {"regime": name, "count": count}
                for name, count in regime_counter.items()
            ],
        }

    def _build_symbols(self, trades: list[dict], last_50_trades: list[dict]) -> dict:
        symbol_rows = self._symbol_rollup(trades, ascending=False)
        leaders = symbol_rows[:5]
        laggards = list(reversed(symbol_rows[-5:])) if symbol_rows else []
        return {
            "leaders": leaders,
            "laggards": laggards,
            "cooldown_candidates": self._compute_cooldown_candidates(last_50_trades),
        }

    def _build_anomalies(
        self,
        trades: list[dict],
        cycles: list[dict],
        system_events: list[dict],
        ranking: dict,
        risk: dict,
    ) -> dict:
        missing_features = {
            column: sum(1 for trade in trades if trade.get(column) is None)
            for column in _REQUIRED_FEATURE_COLUMNS
        }
        broker_mismatch_events = [
            event for event in system_events if event.get("event_type") == "broker_mismatch"
        ]
        suspicious = []
        if cycles and not trades:
            suspicious.append("ranking_cycles_without_trades")
        if ranking["leader_change_count"] >= 10:
            suspicious.append("high_leader_turnover")
        if risk["degraded_cycle_pct"] >= 25.0:
            suspicious.append("degraded_cycle_cluster")

        return {
            "missing_feature_counts": missing_features,
            "zero_cycle_window": len(cycles) == 0,
            "broker_mismatch_count": len(broker_mismatch_events),
            "broker_mismatch_samples": [
                {
                    "event_time": event["event_time"],
                    "description": event["description"],
                }
                for event in broker_mismatch_events[:5]
            ],
            "data_quality_events": sum(
                1 for event in system_events if event.get("event_type") == "data_quality"
            ),
            "suspicious_shifts": suspicious,
        }

    def _build_recommendations(
        self,
        *,
        performance: dict,
        risk: dict,
        ranking: dict,
        regime: dict,
        anomalies: dict,
    ) -> list[dict]:
        recommendations: list[dict] = []
        long_pnl = performance["by_side"]["long"]["total_pnl"]
        short_pnl = performance["by_side"]["short"]["total_pnl"]
        if performance["total_pnl"] < 0 and long_pnl < short_pnl:
            recommendations.append(
                {
                    "priority": "high",
                    "topic": "long_book",
                    "message": "Long-side performance is dragging the period result.",
                    "evidence": {
                        "long_total_pnl": long_pnl,
                        "short_total_pnl": short_pnl,
                    },
                }
            )
        if risk["degraded_cycle_pct"] >= 20.0:
            recommendations.append(
                {
                    "priority": "medium",
                    "topic": "ranking_health",
                    "message": "Ranking quality degraded frequently enough to justify a data or universe audit.",
                    "evidence": {
                        "degraded_cycle_pct": risk["degraded_cycle_pct"],
                        "degraded_cycle_count": risk["degraded_cycle_count"],
                    },
                }
            )
        bucket_rows = ranking["rank_bucket_performance"]
        bucket_13 = next((row for row in bucket_rows if row["bucket"] == "1-3"), None)
        bucket_410 = next((row for row in bucket_rows if row["bucket"] == "4-10"), None)
        if bucket_13 and bucket_410 and bucket_13["avg_pnl"] < bucket_410["avg_pnl"]:
            recommendations.append(
                {
                    "priority": "medium",
                    "topic": "entry_ranking",
                    "message": "Front-ranked entries underperformed the 4-10 cohort in this window.",
                    "evidence": {
                        "rank_1_3_avg_pnl": bucket_13["avg_pnl"],
                        "rank_4_10_avg_pnl": bucket_410["avg_pnl"],
                    },
                }
            )
        if risk["cooldown_candidates"]:
            recommendations.append(
                {
                    "priority": "medium",
                    "topic": "cooldowns",
                    "message": "Recent symbols show repeated losses and should be reviewed for temporary suppression.",
                    "evidence": {
                        "symbols": [row["symbol"] for row in risk["cooldown_candidates"]],
                    },
                }
            )
        if any(anomalies["missing_feature_counts"].values()):
            recommendations.append(
                {
                    "priority": "low",
                    "topic": "data_quality",
                    "message": "Some required feature fields were still missing inside the reporting window.",
                    "evidence": anomalies["missing_feature_counts"],
                }
            )
        if not recommendations:
            recommendations.append(
                {
                    "priority": "low",
                    "topic": "steady_state",
                    "message": "No urgent rule-based intervention was triggered for this report window.",
                    "evidence": {
                        "total_pnl": performance["total_pnl"],
                        "trade_count": performance["trade_count"],
                    },
                }
            )
        return recommendations

    def _build_summary_text(self, payload: dict) -> str:
        meta = payload["meta"]
        performance = payload["performance"]
        risk = payload["risk"]
        recommendations = payload["recommendations"]
        summary = (
            f"{meta['report_type']} | trades={performance['trade_count']} "
            f"| pnl={performance['total_pnl']:+.2f} "
            f"| win_rate={performance['win_rate_pct']:.1f}%"
        )
        if risk["cooldown_candidates"]:
            summary += f" | cooldowns={len(risk['cooldown_candidates'])}"
        if recommendations:
            summary += f" | top_call={recommendations[0]['topic']}"
        return summary

    def _upsert_report(
        self,
        conn: sqlite3.Connection,
        window: ReportWindow,
        payload: dict,
        summary_text: str,
    ) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO apex_reports (
                report_id, report_type, generated_at, period_start, period_end,
                content_json, summary_text, consumed_by_pantheon, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                generated_at = excluded.generated_at,
                content_json = excluded.content_json,
                summary_text = excluded.summary_text,
                consumed_by_pantheon = 0,
                updated_at = excluded.updated_at
            """,
            (
                window.report_id,
                window.report_type,
                payload["meta"]["generated_at"],
                payload["meta"]["period_start"],
                payload["meta"]["period_end"],
                json.dumps(payload, sort_keys=True),
                summary_text,
                now_utc,
                now_utc,
            ),
        )
        conn.execute(
            """
            INSERT INTO system_events (
                event_time, event_type, symbol, description, metadata_json, created_at, updated_at
            ) VALUES (?, 'apex_report_generated', NULL, ?, ?, ?, ?)
            """,
            (
                now_utc,
                f"Apex report persisted: {window.report_type}",
                json.dumps(
                    {
                        "report_id": window.report_id,
                        "report_type": window.report_type,
                        "period_start": payload["meta"]["period_start"],
                        "period_end": payload["meta"]["period_end"],
                    }
                ),
                now_utc,
                now_utc,
            ),
        )

    def _write_markdown_summary(self, window: ReportWindow, payload: dict, summary_text: str) -> None:
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        report_date = window.report_date.isoformat()
        path = self._reports_dir / f"{window.report_type}_{report_date}.md"
        performance = payload["performance"]
        risk = payload["risk"]
        recommendations = payload["recommendations"]
        lines = [
            "# APEX REPORT",
            "",
            f"- Type: {window.report_type}",
            f"- Period: {payload['meta']['period_start']} to {payload['meta']['period_end']}",
            f"- Summary: {summary_text}",
            "",
            "## Performance",
            "",
            f"- Trades: {performance['trade_count']}",
            f"- Total PnL: {performance['total_pnl']:+.2f}",
            f"- Win Rate: {performance['win_rate_pct']:.1f}%",
            f"- Profit Factor: {performance['profit_factor'] if performance['profit_factor'] is not None else 'n/a'}",
            "",
            "## Risk",
            "",
            f"- Degraded Cycle %: {risk['degraded_cycle_pct']:.1f}",
            f"- Cooldown Candidates: {', '.join(row['symbol'] for row in risk['cooldown_candidates']) or 'none'}",
            "",
            "## Recommendations",
            "",
        ]
        for recommendation in recommendations:
            lines.append(
                f"- [{recommendation['priority']}] {recommendation['topic']}: {recommendation['message']}"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _log_failure(self, report_type: str, report_date: Optional[date], error_text: str) -> None:
        try:
            conn = sqlite3.connect(str(self._db_path))
            now_utc = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """
                INSERT INTO system_events (
                    event_time, event_type, symbol, description, metadata_json, created_at, updated_at
                ) VALUES (?, 'apex_report_failure', NULL, ?, ?, ?, ?)
                """,
                (
                    now_utc,
                    f"Apex report generation failed: {report_type}",
                    json.dumps(
                        {
                            "report_type": report_type,
                            "report_date": report_date.isoformat() if report_date else None,
                            "error": error_text[-4000:],
                        }
                    ),
                    now_utc,
                    now_utc,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            logger.error("Failed to persist apex_report_failure:\n%s", traceback.format_exc())

    def _loads_json(self, raw: Optional[str], default):
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    def _symbol_rollup(self, trades: list[dict], ascending: bool) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for trade in trades:
            grouped[trade["symbol"]].append(trade)

        rows = []
        for symbol, symbol_trades in grouped.items():
            count = len(symbol_trades)
            winners = [trade for trade in symbol_trades if float(trade["realized_pnl"]) > 0]
            total_pnl = sum(float(trade["realized_pnl"]) for trade in symbol_trades)
            rows.append(
                {
                    "symbol": symbol,
                    "trade_count": count,
                    "win_rate_pct": round(100.0 * len(winners) / count, 2) if count else 0.0,
                    "avg_pnl": round(total_pnl / count, 4) if count else 0.0,
                    "total_pnl": round(total_pnl, 4),
                }
            )

        return sorted(rows, key=lambda row: row["total_pnl"], reverse=not ascending)

    def _compute_loss_streaks(self, trades: list[dict]) -> list[dict]:
        streaks: list[dict] = []
        current: Optional[dict] = None
        for trade in trades:
            pnl = float(trade["realized_pnl"])
            if pnl <= 0:
                if current is None:
                    current = {
                        "streak_start": trade["exit_time"],
                        "streak_end": trade["exit_time"],
                        "streak_length": 1,
                        "total_loss": round(pnl, 4),
                    }
                else:
                    current["streak_end"] = trade["exit_time"]
                    current["streak_length"] += 1
                    current["total_loss"] = round(current["total_loss"] + pnl, 4)
            elif current is not None:
                streaks.append(current)
                current = None
        if current is not None:
            streaks.append(current)
        return sorted(streaks, key=lambda row: row["streak_length"], reverse=True)

    def _compute_cooldown_candidates(self, trades: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for trade in trades:
            grouped[trade["symbol"]].append(trade)

        candidates = []
        for symbol, symbol_trades in grouped.items():
            consecutive = 0
            streak_start = None
            streak_end = None
            for trade in symbol_trades:
                if float(trade["realized_pnl"]) <= 0:
                    consecutive += 1
                    streak_end = trade["exit_time"]
                    if streak_start is None:
                        streak_start = trade["exit_time"]
                else:
                    consecutive = 0
                    streak_start = None
                    streak_end = None
                if consecutive >= 3:
                    candidates.append(
                        {
                            "symbol": symbol,
                            "consecutive_losses": consecutive,
                            "streak_start": streak_start,
                            "streak_end": streak_end,
                            "flag": "Cooldown Candidate",
                        }
                    )
                    break
        return sorted(candidates, key=lambda row: row["consecutive_losses"], reverse=True)

    def _rank_bucket(self, rank_at_entry) -> str:
        if rank_at_entry is None:
            return "unknown"
        rank_value = int(rank_at_entry)
        if 1 <= rank_value <= 3:
            return "1-3"
        if 4 <= rank_value <= 10:
            return "4-10"
        if rank_value >= 11:
            return "11+"
        return "unknown"

    def _detect_leader_changes(self, cycles: list[dict]) -> list[str]:
        changes: list[str] = []
        prev_long = None
        prev_short = None
        for cycle in cycles:
            current_long = cycle["top_longs"][0]["symbol"] if cycle["top_longs"] else None
            current_short = cycle["top_shorts"][0]["symbol"] if cycle["top_shorts"] else None
            if prev_long is not None and current_long != prev_long:
                changes.append(
                    f"{cycle['cycle_timestamp']}: long leader changed {prev_long} -> {current_long}"
                )
            if prev_short is not None and current_short != prev_short:
                changes.append(
                    f"{cycle['cycle_timestamp']}: short leader changed {prev_short} -> {current_short}"
                )
            prev_long = current_long
            prev_short = current_short
        return changes

    def _event_regime_name(self, event: dict) -> str:
        regime = (event.get("metadata") or {}).get("regime")
        if isinstance(regime, dict):
            return str(regime.get("name", "unknown"))
        if isinstance(regime, str) and regime:
            return regime
        return "unknown"
