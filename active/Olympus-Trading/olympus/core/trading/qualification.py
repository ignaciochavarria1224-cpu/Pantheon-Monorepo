"""
Entry qualification helpers for Olympus.

This layer sits between ranking and order placement. It keeps the ranking
engine intact while enforcing side-aware thresholds and dynamic symbol
eligibility rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from core.models import Direction

if TYPE_CHECKING:
    from core.models import RankedSymbol, TradeRecord
    from core.trading.regime import RegimeDecision


@dataclass(frozen=True)
class QualificationResult:
    allowed: bool
    reason: str
    atr: float = 0.0
    atr_pct: float = 0.0


def build_symbol_trade_stats(
    trades: list["TradeRecord"],
    now_utc: datetime,
    settings,
) -> dict[str, dict]:
    """
    Build rolling in-session trade quality stats used by execution suppression.
    """
    stats: dict[str, dict] = {}
    cooldown_window = timedelta(minutes=int(settings.SYMBOL_COOLDOWN_MINUTES))

    for trade in trades:
        symbol_stats = stats.setdefault(
            trade.symbol,
            {
                "trade_count": 0,
                "stop_count": 0,
                "total_pnl": 0.0,
                "recent_stop_times": [],
                "cooldown_until": None,
                "suppressed": False,
                "stop_rate": 0.0,
            },
        )
        symbol_stats["trade_count"] += 1
        symbol_stats["total_pnl"] += float(trade.realized_pnl)
        if trade.exit_reason == "stop":
            symbol_stats["stop_count"] += 1
            symbol_stats["recent_stop_times"].append(trade.exit_time)

    for symbol, symbol_stats in stats.items():
        recent_stop_times = [
            ts
            for ts in symbol_stats["recent_stop_times"]
            if now_utc - ts <= cooldown_window
        ]
        symbol_stats["recent_stop_times"] = recent_stop_times
        symbol_stats["stop_rate"] = (
            symbol_stats["stop_count"] / symbol_stats["trade_count"]
            if symbol_stats["trade_count"] > 0 else 0.0
        )
        if len(recent_stop_times) >= settings.SYMBOL_COOLDOWN_TRIGGER_STOPS:
            symbol_stats["cooldown_until"] = max(recent_stop_times) + cooldown_window
        if (
            symbol_stats["trade_count"] >= settings.SYMBOL_SUPPRESSION_MIN_TRADES
            and symbol_stats["stop_rate"] >= settings.SYMBOL_SUPPRESSION_MAX_STOP_RATE
            and symbol_stats["total_pnl"] <= settings.SYMBOL_SUPPRESSION_MAX_PNL
        ):
            symbol_stats["suppressed"] = True

    return stats


def qualify_ranked_symbol(
    ranked_symbol: "RankedSymbol",
    direction: Direction,
    entry_price: float,
    atr: float,
    now_utc: datetime,
    symbol_stats: Optional[dict],
    regime: "RegimeDecision",
    settings,
) -> QualificationResult:
    """
    Apply side-aware entry gates to a ranked symbol before risk sizing.
    """
    features = ranked_symbol.features
    score = float(features.normalized_score)
    rvol = float(features.rvol)
    range_position = float(features.range_position)
    vwap_deviation = abs(float(features.vwap_deviation))
    atr_pct = (atr / entry_price) if entry_price > 0 else 0.0

    if not regime.allow_entries:
        return QualificationResult(False, f"regime={regime.name}")

    if direction == Direction.LONG and not regime.long_enabled:
        return QualificationResult(False, f"regime blocks long ({regime.name})")
    if direction == Direction.SHORT and not regime.short_enabled:
        return QualificationResult(False, f"regime blocks short ({regime.name})")

    if direction == Direction.LONG:
        score_threshold = float(settings.LONG_ENTRY_SCORE_THRESHOLD)
        rvol_threshold = float(settings.LONG_MIN_RVOL)
        range_ok = range_position >= float(settings.LONG_MIN_RANGE_POSITION)
        if not range_ok:
            return QualificationResult(False, f"range_position too low ({range_position:.2f})")
        score_value = score
    else:
        score_threshold = float(settings.SHORT_ENTRY_SCORE_THRESHOLD)
        rvol_threshold = float(settings.SHORT_MIN_RVOL)
        range_ok = range_position <= float(settings.SHORT_MAX_RANGE_POSITION)
        if not range_ok:
            return QualificationResult(False, f"range_position too high ({range_position:.2f})")
        score_value = 100.0 - score

    if score_value < score_threshold:
        return QualificationResult(False, f"score below threshold ({score_value:.1f} < {score_threshold:.1f})")
    if rvol < rvol_threshold:
        return QualificationResult(False, f"rvol below threshold ({rvol:.2f} < {rvol_threshold:.2f})")
    if vwap_deviation > float(settings.LONG_MAX_VWAP_DEVIATION if direction == Direction.LONG else settings.SHORT_MAX_VWAP_DEVIATION):
        return QualificationResult(False, f"vwap deviation too large ({vwap_deviation:.3f})")
    if atr_pct < float(settings.MIN_ATR_PCT):
        return QualificationResult(False, f"atr too small ({atr_pct:.4f})", atr=atr, atr_pct=atr_pct)
    if atr_pct > float(settings.MAX_ATR_PCT):
        return QualificationResult(False, f"atr too large ({atr_pct:.4f})", atr=atr, atr_pct=atr_pct)

    if symbol_stats:
        cooldown_until = symbol_stats.get("cooldown_until")
        if cooldown_until is not None and cooldown_until > now_utc:
            return QualificationResult(False, f"cooldown active until {cooldown_until.isoformat()}")
        if symbol_stats.get("suppressed"):
            return QualificationResult(False, "symbol suppressed by recent trade quality")

    return QualificationResult(True, "ok", atr=atr, atr_pct=atr_pct)
