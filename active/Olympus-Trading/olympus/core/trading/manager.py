"""
Position lifecycle manager for Olympus Phase 3.
Maintains the live set of open positions and evaluates stops/targets/rotations each cycle.
All position state mutations are protected by a threading lock.
"""

from __future__ import annotations

import threading
import traceback
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from core.models import Direction, Position, RankedUniverse, TradeRecord

if TYPE_CHECKING:
    from core.trading.execution import ExecutionEngine

logger = get_logger(__name__)


class PositionManager:
    """
    Manages open positions and evaluates exit conditions each cycle.

    Thread-safety: all mutations to self._positions are protected by self._lock.
    """

    def __init__(self, execution: "ExecutionEngine", settings) -> None:
        self._execution = execution
        self._settings = settings
        self._positions: dict[str, Position] = {}  # symbol → Position
        self._lock = threading.Lock()
        logger.info("PositionManager initialized")

    # ------------------------------------------------------------------
    # Public API — reads (thread-safe)
    # ------------------------------------------------------------------

    def get_open_positions(self) -> list[Position]:
        """Return a snapshot list of all open positions."""
        with self._lock:
            return list(self._positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """Return the open position for a symbol, or None if not open."""
        with self._lock:
            return self._positions.get(symbol)

    # ------------------------------------------------------------------
    # Public API — mutations (lock-protected)
    # ------------------------------------------------------------------

    def add_position(self, position: Position) -> None:
        """Register a newly entered position."""
        with self._lock:
            self._positions[position.symbol] = position
        logger.debug(
            "Position added: %s %s entry=%.2f",
            position.direction.value.upper(), position.symbol, position.entry_price,
        )

    def remove_position(self, symbol: str) -> None:
        """Remove a position (used after a successful rotation exit)."""
        with self._lock:
            removed = self._positions.pop(symbol, None)
        if removed:
            logger.debug("Position removed: %s", symbol)

    def update_prices(self, latest_bars: dict[str, dict]) -> None:
        """
        Update current_price and unrealized_pnl for all open positions.
        Bars missing from latest_bars are skipped silently.
        """
        with self._lock:
            for symbol, position in self._positions.items():
                bar = latest_bars.get(symbol)
                if bar is None:
                    continue
                try:
                    price = float(bar["close"])
                    position.current_price = price
                    if position.direction == Direction.LONG:
                        position.unrealized_pnl = (price - position.entry_price) * position.size
                    else:
                        position.unrealized_pnl = (position.entry_price - price) * position.size
                except Exception as exc:
                    logger.warning("update_prices failed for %s: %s", symbol, exc)

    def evaluate_exits(
        self,
        latest_bars: dict[str, dict],
    ) -> list[TradeRecord]:
        """
        Check each open position against its stop and target.

        For LONG: exit at stop if bar low <= stop_price; exit at target if bar high >= target_price.
        For SHORT: exit at stop if bar high >= stop_price; exit at target if bar low <= target_price.

        Returns a list of TradeRecords for positions that were successfully closed.
        Positions that fail to exit (e.g. order error) remain in self._positions.
        """
        # Build the exit list under the lock, then execute outside to avoid
        # holding the lock during network I/O.
        to_exit: list[tuple[str, Position, float, str]] = []

        with self._lock:
            for symbol, position in list(self._positions.items()):
                bar = latest_bars.get(symbol)
                if bar is None:
                    logger.debug("No bar for %s — skipping exit evaluation", symbol)
                    continue

                try:
                    bar_low = float(bar["low"])
                    bar_high = float(bar["high"])
                except Exception as exc:
                    logger.warning("Cannot read bar prices for %s: %s", symbol, exc)
                    continue

                exit_price = None
                exit_reason = None

                if position.direction == Direction.LONG:
                    if bar_low <= position.stop_price:
                        exit_price = position.stop_price
                        exit_reason = "stop"
                    elif bar_high >= position.target_price:
                        exit_price = position.target_price
                        exit_reason = "target"
                else:  # SHORT
                    if bar_high >= position.stop_price:
                        exit_price = position.stop_price
                        exit_reason = "stop"
                    elif bar_low <= position.target_price:
                        exit_price = position.target_price
                        exit_reason = "target"

                if exit_reason is not None:
                    to_exit.append((symbol, position, exit_price, exit_reason))

        # Execute exits — rank_at_exit is None because we don't have the ranked
        # universe at this point; score_at_exit likewise.
        records: list[TradeRecord] = []
        for symbol, position, exit_price, exit_reason in to_exit:
            try:
                record = self._execution.exit_position(
                    position, exit_price, exit_reason,
                    rank_at_exit=None, score_at_exit=None,
                )
                if record is not None:
                    with self._lock:
                        self._positions.pop(symbol, None)
                    records.append(record)
                    logger.info(
                        "Exit executed: %s %s reason=%s pnl=%.2f",
                        position.direction.value.upper(), symbol,
                        exit_reason, record.realized_pnl,
                    )
                else:
                    logger.error(
                        "Exit order failed for %s — position remains open", symbol
                    )
            except Exception:
                logger.error(
                    "evaluate_exits: unexpected error for %s:\n%s",
                    symbol, traceback.format_exc(),
                )

        return records

    def evaluate_rotations(
        self,
        ranked_universe: RankedUniverse,
        threshold_override: Optional[int] = None,
    ) -> list[str]:
        """
        Identify open positions that should be exited due to rank deterioration.

        A LONG position is flagged if its symbol:
          - No longer appears in ranked_universe.longs, OR
          - Its rank > ROTATION_RANK_DROP_THRESHOLD

        A SHORT position is flagged by the same logic against ranked_universe.shorts.

        Returns a list of symbols to exit. The loop handles the actual exit orders.
        """
        long_ranks: dict[str, int] = {rs.symbol: rs.rank for rs in ranked_universe.longs}
        short_ranks: dict[str, int] = {rs.symbol: rs.rank for rs in ranked_universe.shorts}
        threshold = (
            threshold_override
            if threshold_override is not None
            else self._settings.ROTATION_RANK_DROP_THRESHOLD
        )

        to_rotate: list[str] = []
        with self._lock:
            for symbol, position in self._positions.items():
                if position.direction == Direction.LONG:
                    rank = long_ranks.get(symbol)
                    if rank is None or rank > threshold:
                        to_rotate.append(symbol)
                else:  # SHORT
                    rank = short_ranks.get(symbol)
                    if rank is None or rank > threshold:
                        to_rotate.append(symbol)

        if to_rotate:
            logger.info("Rotation candidates: %s", to_rotate)
        return to_rotate
