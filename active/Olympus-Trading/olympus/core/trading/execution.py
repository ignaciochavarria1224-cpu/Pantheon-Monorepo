"""
Paper order placement for Olympus Phase 3.
All orders go to Alpaca's paper environment — the guard in AlpacaClient enforces this.
Never raises — all failures are logged and None is returned.

Part A — Fill-confirmation gate
-------------------------------
Every TradeRecord / Position this module produces is backed by a real,
broker-confirmed fill at the real fill price. After an order is submitted,
the order is polled (AlpacaClient.get_order) on a fixed backoff schedule
until it reaches a terminal status. A trade is recorded ONLY when the broker
confirms a fill, and ALWAYS at the broker's filled_avg_price / filled_qty /
filled_at — never at the planned price, the requested qty, or a local clock.
If the order is canceled / expired / rejected, or polling times out without
confirmation, NO TradeRecord is written; an 'order_unfilled' system_event is
emitted instead and the method returns cleanly so the trading loop continues.

Concurrency model
-----------------
Each enter_position()/exit_position() call confirms its own order by
submitting the poll loop to a shared module-level thread pool. The pool is
the concurrency primitive: with loop.py's current sequential call sites only
one confirmation is in flight at a time, but a future batched call site
(submit all orders, then collect) would get true parallel polling for free
without touching this module again. The pool also gives each confirmation a
hard wall-clock ceiling via Future.result(timeout=...), so a pathologically
hung broker HTTP call cannot stall a trading cycle.
"""

from __future__ import annotations

import concurrent.futures
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger
from core.models import Direction, Position, TradeRecord, TradeStatus

if TYPE_CHECKING:
    from core.broker.alpaca import AlpacaClient
    from core.memory.writer import MemoryWriter

logger = get_logger(__name__)


# Shared pool for fill-confirmation polling — see module docstring.
_FILL_POLL_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=16, thread_name_prefix="fill-confirm"
)

# Alpaca order statuses that are NOT terminal — keep polling while in these.
# Everything else that is not 'filled' is treated as terminal-not-filled.
_NON_TERMINAL_STATUSES = frozenset({
    "new", "accepted", "pending_new", "partially_filled",
    "pending_replace", "pending_cancel", "accepted_for_bidding", "held",
})


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Coerce a broker-supplied datetime to a tz-aware UTC datetime, or None."""
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class _FillOutcome:
    """
    Result of confirming an order against the broker.

    filled=True  -> fill_price / fill_qty / fill_time are all populated with
                    broker-truth values and a trade may be recorded.
    filled=False -> the order did not produce a confirmed, fully-described
                    fill; no trade should be recorded.
    """
    filled: bool
    status: str
    fill_price: Optional[float] = None
    fill_qty: Optional[int] = None
    fill_time: Optional[datetime] = None
    reason: str = ""


class ExecutionEngine:
    """
    Wraps Alpaca paper order placement.

    enter_position() — places a market order, confirms the fill, and returns a
                       Position built from broker-truth values (None if the
                       order is not confirmed filled).
    exit_position()  — places a counter-side market order, confirms the fill,
                       and returns a TradeRecord built from broker-truth values
                       (None if the order is not confirmed filled).

    Both methods return None on any failure or non-fill (never raise).
    """

    def __init__(
        self,
        alpaca_client: "AlpacaClient",
        settings,
        memory_writer: "Optional[MemoryWriter]" = None,
    ) -> None:
        # memory_writer is optional: when present, unfilled orders are recorded
        # as 'order_unfilled' system_events. When absent (e.g. unit tests, or a
        # non-memory loop) the engine logs the same information instead. It is
        # used duck-typed (.write_event) so no import of MemoryWriter is needed.
        self._alpaca = alpaca_client
        self._settings = settings
        self._memory_writer = memory_writer
        logger.info("ExecutionEngine initialized (paper=True)")

    # ------------------------------------------------------------------
    # Fill confirmation (Part A)
    # ------------------------------------------------------------------

    def _poll_order(self, order_id: str) -> _FillOutcome:
        """
        Poll AlpacaClient.get_order() on the configured backoff schedule until
        the order reaches a terminal state. Runs inside the fill-confirm pool.

        Backoff schedule comes from settings.FILL_CONFIRM_BACKOFF — the spec
        default is (0.5, 1.0, 2.0, 4.0, 2.5), which sums to the 10s ceiling.
        The method waits, then polls, for each entry in the schedule.

        Never raises — a broker lookup failure is treated as 'keep polling',
        and an exhausted schedule is a timeout.
        """
        backoff = self._settings.FILL_CONFIRM_BACKOFF
        last_status = "unknown"
        last_order: Optional[dict] = None

        for wait in backoff:
            time.sleep(float(wait))
            order = self._alpaca.get_order(order_id)
            if order is None:
                # Transient broker lookup failure — keep polling.
                continue
            last_order = order
            last_status = str(order.get("status") or "unknown").lower()

            if last_status == "filled":
                return self._build_filled_outcome(order, last_status)
            if last_status not in _NON_TERMINAL_STATUSES:
                # canceled / expired / rejected / any other terminal status:
                # the trade did NOT happen.
                return _FillOutcome(
                    filled=False, status=last_status,
                    reason=f"terminal_not_filled:{last_status}",
                )
            # Non-terminal (new / accepted / pending_* / partially_filled) —
            # keep polling.

        # Schedule exhausted (10s poll ceiling reached). Per spec, accept a
        # genuine partial fill — but only if the broker confirms shares, an
        # average price, AND a fill timestamp. Otherwise the order is
        # UNCONFIRMED and no trade is recorded.
        if last_order is not None:
            outcome = self._build_filled_outcome(last_order, last_status)
            if outcome.filled:
                return outcome
        return _FillOutcome(
            filled=False, status=last_status, reason="timeout_unconfirmed",
        )

    @staticmethod
    def _build_filled_outcome(order: dict, status: str) -> _FillOutcome:
        """
        Extract broker-truth fill fields from a get_order() dict.

        Refuses to declare a fill (returns filled=False) if filled_avg_price,
        filled_qty, or filled_at is missing — there is NO fallback to planned
        prices, requested quantities, or a local clock.
        """
        fill_price = order.get("filled_avg_price")
        fill_qty = order.get("filled_qty")
        fill_time = _to_utc(order.get("filled_at"))
        if fill_price is None or not fill_qty or fill_time is None:
            return _FillOutcome(
                filled=False, status=status,
                reason=(
                    "missing_broker_truth("
                    f"price={fill_price}, qty={fill_qty}, "
                    f"time={'set' if fill_time is not None else 'none'})"
                ),
            )
        return _FillOutcome(
            filled=True, status=status,
            fill_price=float(fill_price),
            fill_qty=int(fill_qty),
            fill_time=fill_time,
            reason="filled" if status == "filled" else "accepted_partial_fill",
        )

    def _confirm_fill(self, order_id: str) -> _FillOutcome:
        """
        Confirm an order's fill via the shared poll pool, under a hard
        wall-clock ceiling.

        The backoff schedule already bounds the poll at the configured 10s
        budget; the Future timeout is an additional guard against a broker
        HTTP call that hangs beyond its own network timeout. The guard is set
        to the backoff budget plus a margin for the per-poll HTTP latency.
        """
        backoff = self._settings.FILL_CONFIRM_BACKOFF
        hard_ceiling = float(sum(backoff)) + 5.0  # +5s margin for HTTP latency
        future = _FILL_POLL_POOL.submit(self._poll_order, order_id)
        try:
            return future.result(timeout=hard_ceiling)
        except concurrent.futures.TimeoutError:
            future.cancel()
            logger.warning(
                "fill-confirm: order %s exceeded %.1fs hard ceiling — unconfirmed",
                order_id[:8], hard_ceiling,
            )
            return _FillOutcome(
                filled=False, status="unknown", reason="hard_ceiling_exceeded",
            )

    def _write_unfilled_event(
        self,
        symbol: str,
        side: str,
        requested_qty: int,
        requested_price: Optional[float],
        order_id: Optional[str],
        alpaca_status: str,
        reason: str,
    ) -> None:
        """
        Emit an 'order_unfilled' system_event when an order is not confirmed
        filled. Logs at WARN level regardless. If no memory writer is wired,
        the event is logged only.
        """
        metadata = {
            "symbol": symbol,
            "side": side,
            "requested_qty": int(requested_qty),
            "requested_price": (
                float(requested_price) if requested_price is not None else None
            ),
            "order_id": order_id,
            "alpaca_status": alpaca_status,
            "reason_if_known": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning(
            "ORDER UNFILLED %s %s qty=%d — status=%s reason=%s order=%s; no trade recorded",
            side.upper(), symbol, requested_qty, alpaca_status, reason,
            (order_id[:8] if order_id else "none"),
        )
        if self._memory_writer is not None:
            try:
                self._memory_writer.write_event(
                    "order_unfilled",
                    f"Order not confirmed filled: {side} {requested_qty} {symbol} "
                    f"({alpaca_status})",
                    symbol=symbol,
                    metadata=metadata,
                )
            except Exception:
                logger.error(
                    "failed to write order_unfilled event:\n%s",
                    traceback.format_exc(),
                )

    def _write_submission_failed_event(
        self,
        symbol: str,
        side: str,
        requested_qty: int,
        requested_price: Optional[float],
        exc: BaseException,
    ) -> None:
        """
        Emit an 'order_submission_failed' system_event when order placement
        raises before a broker order is confirmed to exist (e.g. Alpaca
        rejects the order at submission).

        This is the third visible outcome alongside 'order_unfilled' (order
        accepted but never filled) and a recorded trade (order filled) — so
        the database reflects everything Olympus tried to do.

        The event write is isolated in its own try/except so a writer failure
        cannot mask the original submission error.
        """
        metadata = {
            "symbol": symbol,
            "side": side,
            "requested_qty": int(requested_qty),
            "requested_price": (
                float(requested_price) if requested_price is not None else None
            ),
            "error_class": type(exc).__name__,
            "error_message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._memory_writer is None:
            return
        try:
            self._memory_writer.write_event(
                "order_submission_failed",
                f"Order submission failed: {side} {requested_qty} {symbol}",
                symbol=symbol,
                metadata=metadata,
            )
        except Exception:
            logger.error(
                "failed to write order_submission_failed event:\n%s",
                traceback.format_exc(),
            )

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
        Place a market entry order via the Alpaca paper account and confirm
        the fill before returning.

        Returns a Position built from broker-truth fill values on a confirmed
        fill; returns None (and emits an 'order_unfilled' event) if the order
        is canceled / rejected / expired or polling times out unconfirmed.
        Never raises.
        """
        side = "buy" if direction == Direction.LONG else "sell"
        try:
            order_info = self._alpaca.submit_market_order(symbol, size, side)
            order_id = order_info.get("order_id")
            if not order_id:
                self._write_unfilled_event(
                    symbol, side, size, entry_price, None,
                    "no_order_id", "submit_market_order returned no order_id",
                )
                return None

            outcome = self._confirm_fill(order_id)
            if not outcome.filled:
                # Order did not produce a confirmed fill — record NOTHING.
                self._write_unfilled_event(
                    symbol, side, size, entry_price, order_id,
                    outcome.status, outcome.reason,
                )
                return None

            # Broker-truth values only — never the planned entry_price or the
            # requested size.
            fill_price = outcome.fill_price
            fill_qty = outcome.fill_qty
            fill_time = outcome.fill_time

            position = Position(
                position_id=str(uuid.uuid4()),
                symbol=symbol,
                direction=direction,
                entry_price=float(fill_price),
                stop_price=stop_price,
                target_price=target_price,
                size=int(fill_qty),
                entry_time=fill_time,
                rank_at_entry=rank,
                score_at_entry=score,
                current_price=float(fill_price),
                unrealized_pnl=0.0,
                status=TradeStatus.OPEN,
                entry_order_id=order_id,
            )
            logger.info(
                "ENTER %s %s | size=%d entry=%.2f stop=%.2f target=%.2f "
                "rank=%d score=%.1f order=%s status=%s",
                direction.value.upper(), symbol,
                fill_qty, fill_price, stop_price, target_price, rank, score,
                order_id[:8], outcome.status,
            )
            return position

        except Exception as exc:
            self._write_submission_failed_event(
                symbol, side, size, entry_price, exc
            )
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
        Place a market exit order via the Alpaca paper account and confirm
        the fill before returning.

        Returns a TradeRecord built from broker-truth fill values on a
        confirmed fill; returns None (and emits an 'order_unfilled' event) if
        the order is canceled / rejected / expired or polling times out
        unconfirmed — in which case the position stays open locally and the
        loop will retry the exit on a later cycle. Never raises.

        exit_reason must be one of: "stop", "target", "rotation", "manual",
        "eod_close".
        """
        # Counter-side to flatten the position.
        side = "sell" if position.direction == Direction.LONG else "buy"
        try:
            order_info = self._alpaca.submit_market_order(
                position.symbol, position.size, side
            )
            order_id = order_info.get("order_id")
            if not order_id:
                self._write_unfilled_event(
                    position.symbol, side, position.size, exit_price, None,
                    "no_order_id", "submit_market_order returned no order_id",
                )
                return None

            outcome = self._confirm_fill(order_id)
            if not outcome.filled:
                # Exit order not confirmed — record NOTHING. The position
                # remains open locally; the loop retries the exit next cycle.
                self._write_unfilled_event(
                    position.symbol, side, position.size, exit_price, order_id,
                    outcome.status, outcome.reason,
                )
                return None

            # Broker-truth values only — never the planned exit_price, the
            # requested size, or a local clock.
            fill_price = outcome.fill_price
            fill_qty = outcome.fill_qty
            exit_time = outcome.fill_time

            if fill_qty != position.size:
                # Accepted partial exit: the broker filled fewer shares than
                # requested. We record the confirmed (partial) fill; the
                # residual open shares are a reconciler concern (Part A.5).
                logger.warning(
                    "EXIT partial %s %s — requested %d, filled %d "
                    "(residual %d left to reconciler)",
                    position.direction.value.upper(), position.symbol,
                    position.size, fill_qty, position.size - fill_qty,
                )

            # Realized P&L — computed on the broker-confirmed fill price and
            # the broker-confirmed filled quantity.
            if position.direction == Direction.LONG:
                realized_pnl = (fill_price - position.entry_price) * fill_qty
            else:
                realized_pnl = (position.entry_price - fill_price) * fill_qty

            # R-multiple
            risk_per_share = position.risk_per_share()
            if risk_per_share > 0 and fill_qty > 0:
                r_multiple = realized_pnl / (risk_per_share * fill_qty)
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
                size=int(fill_qty),
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
                entry_order_id=position.entry_order_id,
                exit_order_id=order_id,
            )
            logger.info(
                "EXIT %s %s | exit=%.2f reason=%s pnl=%.2f r=%.2f hold=%.1fmin "
                "order=%s status=%s",
                position.direction.value.upper(), position.symbol,
                fill_price, exit_reason, realized_pnl, r_multiple,
                hold_duration_minutes, order_id[:8], outcome.status,
            )
            return record

        except Exception as exc:
            self._write_submission_failed_event(
                position.symbol, side, position.size, exit_price, exc
            )
            logger.error(
                "exit_position failed — %s %s reason=%s:\n%s",
                position.direction.value.upper(), position.symbol, exit_reason,
                traceback.format_exc(),
            )
            return None
