"""
Pre-entry validation for Olympus Phase 3.
Pure function — no I/O, no side effects.
All 6 gates are independent and evaluated from settings, never hardcoded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import Direction, Position


def validate_entry(
    symbol: str,
    direction: "Direction",
    entry_price: float,
    stop_price: float,
    target_price: float,
    proposed_size: int,
    open_positions: "list[Position]",
    daily_pnl: float,
    equity: float,
    settings,
    side_open_positions: "list[Position] | None" = None,
    max_positions_for_side: int | None = None,
    sector: str | None = None,
    sector_by_symbol: dict[str, str] | None = None,
    sector_limit: int | None = None,
) -> tuple[bool, str]:
    """
    6-gate pre-entry validator. All gates must pass before an order is placed.

    Returns:
        (True, "ok") if all gates pass.
        (False, "<reason>") if any gate fails — first failing gate reported.
    """
    from core.models import Direction

    # Gate 1 — Max open positions
    if len(open_positions) >= settings.MAX_OPEN_POSITIONS:
        return False, (
            f"max open positions reached "
            f"({len(open_positions)}/{settings.MAX_OPEN_POSITIONS})"
        )
    if max_positions_for_side is not None and side_open_positions is not None:
        if len(side_open_positions) >= max_positions_for_side:
            return False, (
                f"max {direction.value} positions reached "
                f"({len(side_open_positions)}/{max_positions_for_side})"
            )

    # Gate 2 — No duplicate symbol
    open_symbols = {p.symbol for p in open_positions}
    if symbol in open_symbols:
        return False, f"duplicate symbol — {symbol} already has an open position"

    # Gate 2b — Sector concentration
    if sector and sector_by_symbol and sector_limit is not None and sector_limit > 0:
        same_sector = sum(
            1
            for position in open_positions
            if sector_by_symbol.get(position.symbol) == sector
        )
        if same_sector >= sector_limit:
            return False, (
                f"sector concentration reached for {sector} "
                f"({same_sector}/{sector_limit})"
            )

    # Gate 3 — Daily loss limit
    if equity > 0 and daily_pnl <= -(equity * settings.MAX_DAILY_LOSS_PCT):
        return False, (
            f"daily loss limit reached — "
            f"daily_pnl={daily_pnl:.2f}, limit={-(equity * settings.MAX_DAILY_LOSS_PCT):.2f}"
        )

    # Gate 4 — Valid stop distance
    if direction == Direction.LONG:
        if stop_price >= entry_price:
            return False, (
                f"invalid stop for LONG: stop={stop_price:.4f} >= entry={entry_price:.4f}"
            )
    else:
        if stop_price <= entry_price:
            return False, (
                f"invalid stop for SHORT: stop={stop_price:.4f} <= entry={entry_price:.4f}"
            )

    stop_distance = abs(entry_price - stop_price)
    if stop_distance < 0.01:
        return False, f"stop too tight: distance={stop_distance:.4f} < 0.01"

    # Gate 5 — Minimum reward/risk ratio
    reward = abs(target_price - entry_price)
    risk = abs(entry_price - stop_price)
    if risk <= 0:
        return False, "zero risk — cannot compute reward/risk ratio"
    rr = reward / risk
    if rr < settings.MIN_REWARD_RISK:
        return False, (
            f"reward/risk too low: {rr:.2f} < {settings.MIN_REWARD_RISK}"
        )

    # Gate 6 — Minimum position size
    if proposed_size < 1:
        return False, f"position size too small: {proposed_size} < 1"

    return True, "ok"
