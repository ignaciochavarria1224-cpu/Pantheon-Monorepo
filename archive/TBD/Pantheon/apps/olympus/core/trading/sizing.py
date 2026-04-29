"""
Position sizing for Olympus Phase 3.
Pure functions — no I/O, no side effects, no external dependencies.
"""

from __future__ import annotations

from math import floor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Direction


def calculate_size(
    equity: float,
    entry_price: float,
    stop_price: float,
    max_risk_pct: float,
) -> int:
    """
    Risk-based position sizing.

    Sizes the position so that the dollar risk (entry to stop) equals
    max_risk_pct of equity. Returns at least 1 share.

    Args:
        equity: Total account equity in dollars.
        entry_price: Planned entry price.
        stop_price: Planned stop price.
        max_risk_pct: Fraction of equity to risk (e.g. 0.005 = 0.5%).

    Returns:
        Integer number of shares (minimum 1).
    """
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return 1
    max_risk_dollars = equity * max_risk_pct
    size = floor(max_risk_dollars / risk_per_share)
    return max(1, size)


def calculate_stop_and_target(
    entry_price: float,
    direction: "Direction",
    atr: float,
    stop_multiplier: float,
    target_multiplier: float,
) -> tuple[float, float]:
    """
    Compute ATR-based stop and target prices.

    Args:
        entry_price: Actual or expected fill price.
        direction: Direction.LONG or Direction.SHORT.
        atr: Average True Range value for the symbol.
        stop_multiplier: ATR multiplier for stop distance.
        target_multiplier: ATR multiplier for target distance.

    Returns:
        (stop_price, target_price) both rounded to 2 decimal places.
    """
    from core.models import Direction

    # Fallback ATR if zero or negative
    effective_atr = atr if atr > 0 else entry_price * 0.01

    if direction == Direction.LONG:
        stop_price = entry_price - (effective_atr * stop_multiplier)
        target_price = entry_price + (effective_atr * target_multiplier)
    else:
        stop_price = entry_price + (effective_atr * stop_multiplier)
        target_price = entry_price - (effective_atr * target_multiplier)

    return round(stop_price, 2), round(target_price, 2)
