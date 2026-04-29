"""
Daily report generator for Olympus.

Queries SQLite for all activity during the current trading day (ET) and
emits a structured Markdown report to data/reports/YYYY-MM-DD.md.
Also writes data/reports/latest.md so Apex can always read the most
recent report without knowing the date.

No external dependencies — stdlib only: sqlite3, json, re, collections,
datetime, pathlib, zoneinfo.
"""

from __future__ import annotations

import json
import re
import sqlite3
import traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from core.logger import get_logger

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")

# Log line pattern: [2026-04-09 15:40:22 EDT] [ERROR   ] [module] — message
_LOG_DATE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\s")
_LOG_LEVEL_RE = re.compile(r"\[(ERROR|WARNING)\s*\]")

# Scored count below this threshold is flagged in System Health
_DEGRADED_SCORED_THRESHOLD = 150

# Regime snapshot target hours in ET (used to pick the nearest cycle)
_SNAPSHOT_TARGETS_ET = [
    ("Open",      9,  30),
    ("Midday",   12,   0),
    ("Afternoon", 14, 30),
    ("Close",    15,  40),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class DailyReportGenerator:
    """
    Generates the Olympus daily trading report.

    Opens its own read-only SQLite connection — does not share or
    interfere with the live database connection held by the trading loop.
    """

    def __init__(self, db_path=None) -> None:
        from config.settings import settings as _s
        if db_path is None:
            db_path = _s.DB_PATH
        self._db_path = Path(db_path)
        self._log_dir: Path = _s.LOG_DIR
        self._reports_dir: Path = self._db_path.parent / "reports"

    def generate(self, report_date: Optional[date] = None) -> Optional[Path]:
        """
        Generate the daily report for `report_date` (defaults to today ET).
        Returns the path to the written report file, or None on failure.
        Never raises.
        """
        try:
            return self._generate_inner(report_date)
        except Exception:
            logger.error(
                "DailyReportGenerator.generate() failed:\n%s",
                traceback.format_exc(),
            )
            return None

    # ------------------------------------------------------------------
    # Inner implementation
    # ------------------------------------------------------------------

    def _generate_inner(self, report_date: Optional[date]) -> Path:
        if report_date is None:
            report_date = datetime.now(_ET).date()

        # UTC range covering the full ET calendar day
        start_et = datetime(report_date.year, report_date.month, report_date.day,
                            0, 0, 0, tzinfo=_ET)
        end_et   = datetime(report_date.year, report_date.month, report_date.day,
                            23, 59, 59, tzinfo=_ET)
        start_utc = start_et.astimezone(timezone.utc).isoformat()
        end_utc   = end_et.astimezone(timezone.utc).isoformat()

        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            data = self._collect_data(conn, start_utc, end_utc, report_date)
        finally:
            conn.close()

        lines: list[str] = []
        lines += ["# OLYMPUS DAILY REPORT", f"# {report_date.isoformat()}", ""]
        lines += self._section_daily_summary(data, report_date)
        lines += self._section_ranking_behavior(data)
        lines += self._section_trade_log(data)
        lines += self._section_factor_analysis(data)
        lines += self._section_system_health(data, report_date)
        lines += self._section_apex_context(data, report_date)

        content = "\n".join(lines)

        self._reports_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._reports_dir / f"{report_date.isoformat()}.md"
        out_path.write_text(content, encoding="utf-8")

        # latest.md — copy for Apex to always find
        (self._reports_dir / "latest.md").write_text(content, encoding="utf-8")

        # Append one row to the running multi-day performance ledger
        self._append_performance_log(data, report_date)

        logger.info("Daily report written -> %s", out_path)
        return out_path

    def _append_performance_log(self, data: dict, report_date: date) -> None:
        """
        Append one row to data/reports/performance-log.md.
        Creates the file with a header row if it doesn't exist.
        Idempotent — if a row for this date already exists it is replaced,
        so re-running the report doesn't produce duplicate entries.
        Never raises.
        """
        try:
            trades = data["trades"]
            n = len(trades)
            winners  = [t for t in trades if t["realized_pnl"] > 0]
            losers   = [t for t in trades if t["realized_pnl"] <= 0]
            total_pnl    = sum(t["realized_pnl"] for t in trades)
            win_rate     = (len(winners) / n * 100) if n > 0 else 0.0
            gross_wins   = sum(t["realized_pnl"] for t in winners)
            gross_losses = abs(sum(t["realized_pnl"] for t in losers))
            pf_str = f"{gross_wins / gross_losses:.2f}" if gross_losses > 0 else "∞"

            _HEADER = (
                "| DATE | START_EQUITY | END_EQUITY | DAY_PNL | DAY_PNL_PCT"
                " | WIN_RATE | TOTAL_TRADES | PROFIT_FACTOR |"
            )
            _SEP = (
                "|------|--------------|------------|---------|-------------"
                "|----------|--------------|---------------|"
            )

            date_str = report_date.isoformat()
            new_row  = (
                f"| {date_str} | - | - | ${total_pnl:+.2f} | -"
                f" | {win_rate:.1f}% | {n} | {pf_str} |"
            )

            log_path = self._reports_dir / "performance-log.md"

            if not log_path.exists():
                log_path.write_text(
                    f"{_HEADER}\n{_SEP}\n{new_row}\n",
                    encoding="utf-8",
                )
            else:
                lines = log_path.read_text(encoding="utf-8").splitlines()
                # Drop any existing row for this date so re-runs stay clean
                lines = [l for l in lines if not l.startswith(f"| {date_str} ")]
                lines.append(new_row)
                log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            logger.info("Performance log updated -> %s", log_path)

        except Exception:
            logger.error(
                "Failed to update performance log:\n%s", traceback.format_exc()
            )

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def _collect_data(
        self,
        conn: sqlite3.Connection,
        start_utc: str,
        end_utc: str,
        report_date: date,
    ) -> dict:
        """Run all queries and return a single data dict."""
        data: dict = {}

        # -- Trades for today (with feature join) --
        rows = conn.execute(
            """
            SELECT
                t.trade_id, t.symbol, t.direction,
                t.entry_price, t.exit_price, t.stop_price, t.target_price,
                t.size, t.entry_time, t.exit_time,
                t.hold_duration_minutes, t.realized_pnl,
                t.r_multiple, t.exit_reason,
                t.rank_at_entry, t.score_at_entry,
                tf.roc_20, tf.rvol, tf.vwap_deviation, tf.range_position,
                tf.normalized_score, tf.atr_at_entry
            FROM trades t
            LEFT JOIN trade_features tf ON t.trade_id = tf.trade_id
            WHERE t.exit_time >= ? AND t.exit_time <= ?
            ORDER BY t.exit_time ASC
            """,
            (start_utc, end_utc),
        ).fetchall()
        data["trades"] = [dict(r) for r in rows]

        # -- Ranking cycles for today --
        rows = conn.execute(
            """
            SELECT cycle_id, cycle_timestamp, universe_size, scored_count,
                   error_count, duration_seconds,
                   top_longs_json, top_shorts_json
            FROM ranking_cycles
            WHERE cycle_timestamp >= ? AND cycle_timestamp <= ?
            ORDER BY cycle_timestamp ASC
            """,
            (start_utc, end_utc),
        ).fetchall()
        raw_cycles = [dict(r) for r in rows]
        # Parse JSON fields
        for c in raw_cycles:
            c["top_longs"] = json.loads(c["top_longs_json"] or "[]")
            c["top_shorts"] = json.loads(c["top_shorts_json"] or "[]")
        data["cycles"] = raw_cycles

        # -- Degraded cycles (scored < threshold) today --
        data["degraded_cycles"] = [
            c for c in raw_cycles
            if c["scored_count"] < _DEGRADED_SCORED_THRESHOLD
        ]

        # -- Exit-reason breakdown for today --
        rows = conn.execute(
            """
            SELECT exit_reason, direction,
                   COUNT(*) AS count,
                   SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) AS winners,
                   ROUND(AVG(r_multiple), 3) AS avg_r,
                   ROUND(AVG(hold_duration_minutes), 1) AS avg_hold_min,
                   ROUND(SUM(realized_pnl), 2) AS total_pnl
            FROM trades
            WHERE exit_time >= ? AND exit_time <= ?
            GROUP BY exit_reason, direction
            ORDER BY exit_reason, direction
            """,
            (start_utc, end_utc),
        ).fetchall()
        data["exit_reason_stats"] = [dict(r) for r in rows]

        # -- Momentum regime performance for today --
        rows = conn.execute(
            """
            SELECT
                CASE
                    WHEN tf.roc_20 > 5  THEN 'strong_momentum'
                    WHEN tf.roc_20 > 0  THEN 'mild_momentum'
                    WHEN tf.roc_20 > -5 THEN 'mild_weakness'
                    ELSE                     'strong_weakness'
                END AS momentum_bucket,
                t.direction,
                COUNT(*) AS trades,
                ROUND(AVG(t.r_multiple), 2) AS avg_r,
                ROUND(AVG(t.realized_pnl), 2) AS avg_pnl,
                SUM(CASE WHEN t.realized_pnl > 0 THEN 1 ELSE 0 END) AS winners
            FROM trades t
            JOIN trade_features tf ON t.trade_id = tf.trade_id
            WHERE t.exit_time >= ? AND t.exit_time <= ?
              AND tf.roc_20 IS NOT NULL
            GROUP BY momentum_bucket, t.direction
            ORDER BY momentum_bucket, t.direction
            """,
            (start_utc, end_utc),
        ).fetchall()
        data["momentum_buckets"] = [dict(r) for r in rows]

        # -- Log errors for today --
        data["log_errors"] = self._read_log_errors(report_date)

        return data

    # ------------------------------------------------------------------
    # Report sections
    # ------------------------------------------------------------------

    def _section_daily_summary(self, data: dict, report_date: date) -> list[str]:
        trades = data["trades"]
        n = len(trades)
        winners = [t for t in trades if t["realized_pnl"] > 0]
        losers  = [t for t in trades if t["realized_pnl"] <= 0]

        win_count  = len(winners)
        loss_count = len(losers)
        win_rate   = (win_count / n * 100) if n > 0 else 0.0

        total_pnl  = sum(t["realized_pnl"] for t in trades)
        avg_winner = (sum(t["realized_pnl"] for t in winners) / win_count) if winners else 0.0
        avg_loser  = (sum(t["realized_pnl"] for t in losers)  / loss_count) if losers  else 0.0

        gross_wins   = sum(t["realized_pnl"] for t in winners)
        gross_losses = abs(sum(t["realized_pnl"] for t in losers))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else float("inf")

        max_dd = _compute_max_drawdown(trades)

        # Trade-level Sharpe proxy: mean(pnl) / std(pnl)
        sharpe_str = "n/a (< 2 trades)"
        if n >= 2:
            pnls = [t["realized_pnl"] for t in trades]
            mean_pnl = sum(pnls) / n
            variance = sum((p - mean_pnl) ** 2 for p in pnls) / (n - 1)
            std_pnl  = variance ** 0.5
            if std_pnl > 0:
                sharpe_str = f"{mean_pnl / std_pnl:.3f} (trade-level)"

        long_count  = sum(1 for t in trades if t["direction"] == "long")
        short_count = sum(1 for t in trades if t["direction"] == "short")

        lines = [
            "## DAILY SUMMARY",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Date | {report_date.isoformat()} |",
            f"| Session | 09:30 – 16:00 ET |",
            f"| Total Trades | {n} ({long_count} long / {short_count} short) |",
            f"| Winners / Losers | {win_count} / {loss_count} |",
            f"| Win Rate | {win_rate:.1f}% |",
            f"| Total P&L | ${total_pnl:+.2f} |",
            f"| Avg Winner | ${avg_winner:+.2f} |",
            f"| Avg Loser | ${avg_loser:+.2f} |",
            f"| Profit Factor | {profit_factor:.2f} |" if profit_factor != float("inf") else "| Profit Factor | ∞ (no losses) |",
            f"| Max Drawdown | ${max_dd:.2f} |",
            f"| Trade Sharpe | {sharpe_str} |",
            "",
        ]
        return lines

    def _section_ranking_behavior(self, data: dict) -> list[str]:
        cycles = data["cycles"]
        n = len(cycles)

        lines = ["## RANKING BEHAVIOR", ""]

        if not cycles:
            lines += ["_No ranking cycles recorded today._", ""]
            return lines

        scored_counts = [c["scored_count"] for c in cycles]
        avg_scored = sum(scored_counts) / len(scored_counts)

        lines += [
            f"Cycles fired today: **{n}**",
            f"Universe size: {cycles[0].get('universe_size', '?')} | Avg scored: {avg_scored:.0f}",
            "",
        ]

        # -- 4 regime snapshots --
        lines += ["### Regime Snapshots", ""]
        lines += ["| Snapshot | Cycle Time (ET) | #1 Long | Score | #1 Short | Score |"]
        lines += ["|----------|-----------------|---------|-------|----------|-------|"]

        for label, target_h, target_m in _SNAPSHOT_TARGETS_ET:
            cycle = _nearest_cycle(cycles, target_h, target_m)
            if cycle is None:
                lines.append(f"| {label} | - | - | - | - | - |")
                continue
            ct_et = _parse_utc_to_et(cycle["cycle_timestamp"])
            ct_str = ct_et.strftime("%H:%M") if ct_et else "?"
            top_long  = cycle["top_longs"][0]  if cycle["top_longs"]  else None
            top_short = cycle["top_shorts"][0] if cycle["top_shorts"] else None
            long_sym   = top_long["symbol"]          if top_long  else "-"
            long_score = f"{top_long['score']:.1f}"  if top_long  else "-"
            short_sym   = top_short["symbol"]         if top_short else "-"
            short_score = f"{top_short['score']:.1f}" if top_short else "-"
            lines.append(
                f"| {label} | {ct_str} | {long_sym} | {long_score} | {short_sym} | {short_score} |"
            )

        lines.append("")

        # -- Regime changes: when the #1 long or #1 short symbol changed --
        lines += ["### Regime Changes (when #1 ranking shifted)", ""]
        changes = _detect_regime_changes(cycles)
        if changes:
            for ch in changes:
                lines.append(f"- {ch}")
        else:
            lines.append("_No regime changes detected today._")
        lines.append("")

        # -- Most frequently appearing symbols --
        long_counter: Counter = Counter()
        short_counter: Counter = Counter()
        for c in cycles:
            for entry in c["top_longs"]:
                long_counter[entry["symbol"]] += 1
            for entry in c["top_shorts"]:
                short_counter[entry["symbol"]] += 1

        lines += ["### Most Frequent Ranking Appearances", ""]
        long_top = long_counter.most_common(5)
        short_top = short_counter.most_common(5)

        lines.append("**Longs:** " + (
            ", ".join(f"{sym} ({cnt}/{n})" for sym, cnt in long_top)
            if long_top else "-"
        ))
        lines.append("**Shorts:** " + (
            ", ".join(f"{sym} ({cnt}/{n})" for sym, cnt in short_top)
            if short_top else "-"
        ))
        lines.append("")

        return lines

    def _section_trade_log(self, data: dict) -> list[str]:
        trades = sorted(data["trades"], key=lambda t: t["realized_pnl"], reverse=True)

        lines = ["## TRADE LOG", ""]

        if not trades:
            lines += ["_No trades executed today._", ""]
            return lines

        lines += [
            "| # | Symbol | Side | Entry | Exit | Size | P&L | R | Hold | Reason |",
            "|---|--------|------|-------|------|------|-----|---|------|--------|",
        ]

        for i, t in enumerate(trades, 1):
            hold = t["hold_duration_minutes"] or 0.0
            hold_str = f"{hold:.0f}m" if hold < 60 else f"{hold/60:.1f}h"
            pnl_str = f"${t['realized_pnl']:+.2f}"
            r_str   = f"{t['r_multiple']:+.2f}R"
            side    = t["direction"].upper()
            lines.append(
                f"| {i} | {t['symbol']} | {side} | {t['entry_price']:.2f} | "
                f"{t['exit_price']:.2f} | {t['size']} | {pnl_str} | {r_str} | "
                f"{hold_str} | {t['exit_reason']} |"
            )

        lines.append("")
        return lines

    def _section_factor_analysis(self, data: dict) -> list[str]:
        trades = data["trades"]
        lines = ["## FACTOR ANALYSIS", ""]

        if not trades:
            lines += ["_No trades to analyze today._", ""]
            return lines

        # Win rate and P&L by exit reason
        lines += ["### Win Rate by Exit Reason", ""]
        if data["exit_reason_stats"]:
            lines += [
                "| Reason | Direction | Count | Win% | Avg R | Avg Hold | P&L |",
                "|--------|-----------|-------|------|-------|----------|-----|",
            ]
            for row in data["exit_reason_stats"]:
                win_pct = (row["winners"] / row["count"] * 100) if row["count"] > 0 else 0
                lines.append(
                    f"| {row['exit_reason']} | {row['direction']} | {row['count']} | "
                    f"{win_pct:.0f}% | {row['avg_r']:+.2f} | "
                    f"{row['avg_hold_min']:.0f}m | ${row['total_pnl']:+.2f} |"
                )
        else:
            lines.append("_No exit data._")
        lines.append("")

        # Hold time: winners vs losers
        winners = [t for t in trades if t["realized_pnl"] > 0]
        losers  = [t for t in trades if t["realized_pnl"] <= 0]
        avg_win_hold  = (sum(t["hold_duration_minutes"] or 0 for t in winners) / len(winners)) if winners else 0
        avg_loss_hold = (sum(t["hold_duration_minutes"] or 0 for t in losers)  / len(losers))  if losers  else 0

        lines += [
            "### Hold Time - Winners vs Losers",
            "",
            "| Outcome | Avg Hold |",
            "|---------|----------|",
            f"| Winners ({len(winners)}) | {avg_win_hold:.0f} min |",
            f"| Losers ({len(losers)}) | {avg_loss_hold:.0f} min |",
            "",
        ]

        # Momentum regime
        lines += ["### Momentum Regime Performance", ""]
        if data["momentum_buckets"]:
            lines += [
                "| Bucket | Direction | Trades | Winners | Avg R | Avg P&L |",
                "|--------|-----------|--------|---------|-------|---------|",
            ]
            for row in data["momentum_buckets"]:
                win_pct = (row["winners"] / row["trades"] * 100) if row["trades"] > 0 else 0
                lines.append(
                    f"| {row['momentum_bucket']} | {row['direction']} | {row['trades']} | "
                    f"{row['winners']} ({win_pct:.0f}%) | {row['avg_r']:+.2f} | ${row['avg_pnl']:+.2f} |"
                )
        else:
            lines.append("_No feature data for today's trades (trade_features rows may be missing)._")
        lines.append("")

        # Best and worst individual trades
        sorted_trades = sorted(trades, key=lambda t: t["realized_pnl"], reverse=True)
        if sorted_trades:
            best  = sorted_trades[0]
            worst = sorted_trades[-1]
            lines += [
                "### Best / Worst Trade",
                "",
                f"**Best:**  {best['symbol']} {best['direction'].upper()} "
                f"${best['realized_pnl']:+.2f} ({best['r_multiple']:+.2f}R) - {best['exit_reason']}",
                f"**Worst:** {worst['symbol']} {worst['direction'].upper()} "
                f"${worst['realized_pnl']:+.2f} ({worst['r_multiple']:+.2f}R) - {worst['exit_reason']}",
                "",
            ]

        return lines

    def _section_system_health(self, data: dict, report_date: date) -> list[str]:
        lines = ["## SYSTEM HEALTH", ""]

        errors = data["log_errors"]
        degraded = data["degraded_cycles"]
        cycles = data["cycles"]

        # Error summary
        if not errors:
            lines.append("**Errors today:** 0 OK")
        else:
            lines.append(f"**Errors today:** {len(errors)}")
            lines.append("")

            # Group by pattern to avoid wall-of-text for repeated errors
            groups = _group_errors(errors)
            lines.append("| Count | Module | Summary |")
            lines.append("|-------|--------|---------|")
            for module, msg, count in groups[:15]:
                safe_msg = msg[:90].replace("\u2014", " - ").replace("\u2013", " - ")
                lines.append(f"| {count}x | {module} | {safe_msg} |")
        lines.append("")

        # Degraded ranking cycles
        if not degraded:
            lines.append(f"**Degraded ranking cycles (scored < {_DEGRADED_SCORED_THRESHOLD}):** 0 OK")
        else:
            lines.append(
                f"**Degraded ranking cycles (scored < {_DEGRADED_SCORED_THRESHOLD}):** {len(degraded)}"
            )
            for c in degraded[:5]:
                ct_et = _parse_utc_to_et(c["cycle_timestamp"])
                ct_str = ct_et.strftime("%H:%M ET") if ct_et else "?"
                lines.append(f"  - {ct_str}: scored={c['scored_count']} / {c['universe_size']}")
        lines.append("")

        # API retry events (look for retry pattern in errors)
        retry_count = sum(
            1 for _, msg, _ in _group_errors(errors) if "retrying" in msg.lower() or "attempt" in msg.lower()
        )
        if retry_count > 0:
            lines.append(f"**API retry events detected:** {retry_count} patterns")
        else:
            lines.append("**API retry events:** 0 OK")
        lines.append("")

        # Cycle stats
        if cycles:
            scored_counts = [c["scored_count"] for c in cycles]
            min_scored = min(scored_counts)
            avg_scored = sum(scored_counts) / len(scored_counts)
            lines.append(
                f"**Cycle stats:** {len(cycles)} cycles | "
                f"avg scored={avg_scored:.0f} | min scored={min_scored}"
            )
        lines.append("")

        return lines

    def _section_apex_context(self, data: dict, report_date: date) -> list[str]:
        trades = data["trades"]
        n = len(trades)
        cycles = data["cycles"]
        errors = data["log_errors"]

        long_trades  = [t for t in trades if t["direction"] == "long"]
        short_trades = [t for t in trades if t["direction"] == "short"]
        winners = [t for t in trades if t["realized_pnl"] > 0]
        losers  = [t for t in trades if t["realized_pnl"] <= 0]

        total_pnl  = sum(t["realized_pnl"] for t in trades)
        win_rate   = (len(winners) / n * 100) if n > 0 else 0.0
        gross_wins   = sum(t["realized_pnl"] for t in winners)
        gross_losses = abs(sum(t["realized_pnl"] for t in losers))
        pf_str = f"{gross_wins / gross_losses:.2f}" if gross_losses > 0 else "∞"

        # Best exit reason
        reason_pnl: dict[str, float] = defaultdict(float)
        for t in trades:
            reason_pnl[t["exit_reason"]] += t["realized_pnl"]
        best_reason = max(reason_pnl, key=reason_pnl.get) if reason_pnl else None

        # Best momentum bucket
        mb_data = data["momentum_buckets"]
        best_bucket = None
        best_bucket_avg_r = -999.0
        for mb in mb_data:
            if mb["avg_r"] > best_bucket_avg_r and mb["trades"] >= 2:
                best_bucket_avg_r = mb["avg_r"]
                best_bucket = f"{mb['momentum_bucket']} {mb['direction']}"

        # Worst momentum bucket
        worst_bucket = None
        worst_bucket_avg_r = 999.0
        for mb in mb_data:
            if mb["avg_r"] < worst_bucket_avg_r and mb["trades"] >= 2:
                worst_bucket_avg_r = mb["avg_r"]
                worst_bucket = f"{mb['momentum_bucket']} {mb['direction']}"

        # Build paragraph sentences
        sentences: list[str] = []

        if n == 0:
            sentences.append(
                f"On {report_date.isoformat()}, Olympus executed 0 trades; "
                f"the market may have been closed or no candidates passed entry filters."
            )
        else:
            sentences.append(
                f"On {report_date.isoformat()}, Olympus executed {n} trades "
                f"({len(long_trades)} long, {len(short_trades)} short) "
                f"with a {win_rate:.0f}% win rate and total realized P&L of ${total_pnl:+.2f} "
                f"(profit factor {pf_str})."
            )

        if best_reason and n > 0:
            sentences.append(
                f"Best-performing exit reason was '{best_reason}' contributing ${reason_pnl[best_reason]:+.2f} P&L; "
                f"worst was '{min(reason_pnl, key=reason_pnl.get)}' at ${min(reason_pnl.values()):+.2f}."
            )

        if best_bucket:
            sentences.append(
                f"Strongest momentum regime was '{best_bucket}' (avg R={best_bucket_avg_r:+.2f})"
                + (f"; weakest was '{worst_bucket}' (avg R={worst_bucket_avg_r:+.2f})." if worst_bucket and worst_bucket != best_bucket else ".")
            )

        if len(cycles) > 0:
            degraded_n = len(data["degraded_cycles"])
            scored_avg = sum(c["scored_count"] for c in cycles) / len(cycles)
            sentences.append(
                f"Ranking engine fired {len(cycles)} cycles (avg scored={scored_avg:.0f}"
                + (f", {degraded_n} degraded below {_DEGRADED_SCORED_THRESHOLD}" if degraded_n else "")
                + ")."
            )

        if errors:
            # Count distinct buying-power errors
            bp_errors = sum(1 for _, msg, _ in _group_errors(errors) if "buying_power" in msg or "buying power" in msg)
            if bp_errors > 0:
                sentences.append(
                    f"System logged {len(errors)} errors including {bp_errors} buying-power rejection pattern(s); "
                    f"the Fix 1 capital reservation logic should reduce these tomorrow."
                )
            else:
                sentences.append(
                    f"System logged {len(errors)} errors today; review System Health section for detail."
                )

        paragraph = " ".join(sentences)

        lines = [
            "## APEX CONTEXT BLOCK",
            "",
            "---APEX_CONTEXT_START---",
            paragraph,
            "---APEX_CONTEXT_END---",
            "",
        ]
        return lines

    # ------------------------------------------------------------------
    # Log reader
    # ------------------------------------------------------------------

    def _read_log_errors(self, report_date: date) -> list[str]:
        """Return all ERROR lines from today's log file. Never raises."""
        log_path = self._log_dir / "olympus.log"
        if not log_path.exists():
            return []
        try:
            date_prefix = f"[{report_date.strftime('%Y-%m-%d')}"
            errors: list[str] = []
            with open(log_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if date_prefix in line and "[ERROR" in line:
                        errors.append(line.rstrip())
            return errors
        except Exception as exc:
            logger.warning("Could not read log file: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _compute_max_drawdown(trades: list[dict]) -> float:
    """Peak-to-trough drawdown from the running cumulative P&L of today's trades."""
    if not trades:
        return 0.0
    sorted_trades = sorted(trades, key=lambda t: t["exit_time"])
    peak = 0.0
    cum  = 0.0
    max_dd = 0.0
    for t in sorted_trades:
        cum += t["realized_pnl"]
        if cum > peak:
            peak = cum
        dd = cum - peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _parse_utc_to_et(ts_str: str) -> Optional[datetime]:
    """Parse a UTC ISO string from the DB and return an ET-aware datetime."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_ET)
    except Exception:
        return None


def _nearest_cycle(cycles: list[dict], target_hour: int, target_minute: int) -> Optional[dict]:
    """Return the cycle whose ET time is closest to the target hour:minute."""
    if not cycles:
        return None
    best = None
    best_delta = float("inf")
    for c in cycles:
        dt_et = _parse_utc_to_et(c["cycle_timestamp"])
        if dt_et is None:
            continue
        delta = abs(dt_et.hour * 60 + dt_et.minute - (target_hour * 60 + target_minute))
        if delta < best_delta:
            best_delta = delta
            best = c
    return best


def _detect_regime_changes(cycles: list[dict]) -> list[str]:
    """
    Return a list of human-readable strings describing when the #1 long
    or #1 short symbol changed between consecutive cycles.
    """
    changes: list[str] = []
    prev_long = prev_short = None
    for c in cycles:
        cur_long  = c["top_longs"][0]["symbol"]  if c["top_longs"]  else None
        cur_short = c["top_shorts"][0]["symbol"] if c["top_shorts"] else None
        dt_et = _parse_utc_to_et(c["cycle_timestamp"])
        ts_str = dt_et.strftime("%H:%M ET") if dt_et else "?"

        if prev_long is not None and cur_long != prev_long:
            changes.append(f"{ts_str}: Long leader changed {prev_long} -> {cur_long}")
        if prev_short is not None and cur_short != prev_short:
            changes.append(f"{ts_str}: Short leader changed {prev_short} -> {cur_short}")

        prev_long  = cur_long
        prev_short = cur_short
    return changes


def _group_errors(error_lines: list[str]) -> list[tuple[str, str, int]]:
    """
    Group error lines by (module, message-prefix) and return a list of
    (module, summary, count) tuples sorted by count descending.
    """
    # Extract module and first 100 chars of the message
    module_re = re.compile(r"\[([^\]]+)\] — (.{1,120})")
    groups: dict[tuple[str, str], int] = defaultdict(int)
    for line in error_lines:
        m = module_re.search(line)
        if m:
            module  = m.group(1)
            summary = m.group(2)[:100].strip()
            # Normalize: strip variable parts (prices, IDs) for grouping
            key_msg = re.sub(r"[\d,.]+", "N", summary)[:80]
            groups[(module, key_msg)] += 1
        else:
            groups[("unknown", line[-80:])] += 1

    return sorted(
        [(mod, msg, cnt) for (mod, msg), cnt in groups.items()],
        key=lambda x: x[2],
        reverse=True,
    )
