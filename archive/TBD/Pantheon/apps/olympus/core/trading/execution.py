"""
Paper order placement for Olympus Phase 3.
All orders go to Alpaca's paper environment — the guard in AlpacaClient enforces this.
Never raises — all failures are logged and None is returned.
"""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from core.models import Direction, Position, TradeRecord, TradeStatus

if TYPE_CHECKING:
    from core.broker.alpaca import AlpacaClient

logger = get_logger(__name__)


class ExecutionEngine:
    """
    Wraps Alpaca paper order placement.

    enter_position() — places a market order and returns a Position on success.
    exit_position()  — places a counter-side market order and returns a TradeRecord on success.

    Both methods return None on any failure (never raise).
    """

    def __init__(self, alpaca_client: "AlpacaClient", settings) -> None:
        self._alpaca = alpaca_client
        self._settings = settings
        logger.info("ExecutionEngine initialized (paper=True)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enter_position(
        self,
        symbol: str,
        direction: Direction,
        size: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
        rank: int,
        score: float,
    ) -> Optional[Position]:
        """
        Place a market entry order via the Alpaca paper account.

        Returns a Position object on success, None on any failure.
        The actual fill price from Alpaca is used when available;
        otherwise entry_price is used as the fill price.
        """
        try:
            side = "buy" if direction == Direction.LONG else "sell"
            order_info = self._alpaca.submit_market_order(symbol, size, side)

            # Use actual fill price if Alpaca populated it; otherwise fall back to entry_price
            fill_price = order_info.get("filled_avg_price") or entry_price

            position = Position(
                position_id=str(uuid.uuid4()),
                symbol=symbol,
                direction=direction,
                entry_price=float(fill_price),
                stop_price=stop_price,
                target_price=target_price,
                size=size,
                entry_time=datetime.now(timezone.utc),
                rank_at_entry=rank,
                score_at_entry=score,
                current_price=float(fill_price),
                unrealized_pnl=0.0,
                status=TradeStatus.OPEN,
            )
            logger.info(
                "ENTER %s %s | size=%d entry=%.2f stop=%.2f target=%.2f rank=%d score=%.1f",
                direction.value.upper(), symbol,
                size, fill_price, stop_price, target_price, rank, score,
            )
            return position

        except Exception:
            logger.error(
                "enter_position failed — %s %s size=%d:\n%s",
                direction.value.upper(), symbol, size,
                traceback.format_exc(),
            )
            return None

    def exit_position(
        self,
        position: Position,
        exit_price: float,
        exit_reason: str,
        rank_at_exit: Optional[int],
        score_at_exit: Optional[float],
    ) -> Optional[TradeRecord]:
        """
        Place a market exit order via the Alpaca paper account.

        Returns a TradeRecord on success, None on any failure.
        exit_reason must be one of: "stop", "target", "rotation", "manual".
        """
        try:
            # Counter-side to flatten the position
            side = "sell" if position.direction == Direction.LONG else "buy"
            order_info = self._alpaca.submit_market_order(position.symbol, position.size, side)

            fill_price = order_info.get("filled_avg_price") or exit_price
            fill_price = float(fill_price)
            exit_time = datetime.now(timezone.utc)

            # Realized P&L
            if position.direction == Direction.LONG:
                realized_pnl = (fill_price - position.entry_price) * position.size
            else:
                realized_pnl = (position.entry_price - fill_price) * position.size

            # R-multiple
            risk_per_share = position.risk_per_share()
            if risk_per_share > 0 and position.size > 0:
                r_multiple = realized_pnl / (risk_per_share * position.size)
            else:
                r_multiple = 0.0

            hold_duration_minutes = (
                (exit_time - position.entry_time).total_seconds() / 60.0
            )

            record = TradeRecord(
                trade_id=str(uuid.uuid4()),
                position_id=position.position_id,
                symbol=position.symbol,
                direction=position.direction.value,
                entry_price=position.entry_price,
                exit_price=fill_price,
                stop_price=position.stop_price,
                target_price=position.target_price,
                size=position.size,
                entry_time=position.entry_time,
                exit_time=exit_time,
                hold_duration_minutes=hold_duration_minutes,
                realized_pnl=realized_pnl,
                r_multiple=r_multiple,
                exit_reason=exit_reason,
                rank_at_entry=position.rank_at_entry,
                score_at_entry=position.score_at_entry,
                rank_at_exit=rank_at_exit,
                score_at_exit=score_at_exit,
                status="closed",
                features=position.features,
            )
            logger.info(
                "EXIT %s %s | exit=%.2f reason=%s pnl=%.2f r=%.2f hold=%.1fmin",
                position.direction.value.upper(), position.symbol,
                fill_price, exit_reason, realized_pnl, r_multiple, hold_duration_minutes,
            )
            return record

        except Exception:
            logger.error(
                "exit_position failed — %s %s reason=%s:\n%s",
                position.direction.value.upper(), position.symbol, exit_reason,
                traceback.format_exc(),
            )
            return None
