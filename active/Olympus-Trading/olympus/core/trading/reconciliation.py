"""
Broker/local position reconciliation for Olympus.

Detection is always read-only. Repair is allowed only for Alpaca paper mode
when explicitly enabled by settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReconciliationResult:
    local_open_positions: dict[str, dict[str, Any]]
    broker_open_positions: dict[str, dict[str, Any]]
    broker_open_orders: list[dict[str, Any]]
    mismatch: bool
    reason: str = "clean"
    repair_attempted: bool = False
    repair_succeeded: bool = False
    entries_blocked: bool = False
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_event_metadata(self) -> dict[str, Any]:
        return {
            "checked_at": self.checked_at,
            "local_open_symbols": sorted(self.local_open_positions),
            "broker_open_symbols": sorted(self.broker_open_positions),
            "local_open_positions": self.local_open_positions,
            "broker_open_positions": self.broker_open_positions,
            "broker_open_orders": self.broker_open_orders,
            "mismatch": self.mismatch,
            "reason": self.reason,
            "repair_attempted": self.repair_attempted,
            "repair_succeeded": self.repair_succeeded,
            "entries_blocked": self.entries_blocked,
        }


def _normalize_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    if side in {"buy", "long"}:
        return "long"
    if side in {"sell", "short"}:
        return "short"
    return side or "unknown"


def _normalize_qty(value: Any) -> int:
    try:
        return int(abs(float(value or 0)))
    except Exception:
        return 0


def local_position_map(positions) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for position in positions:
        if isinstance(position, dict):
            symbol = str(position.get("symbol", "")).upper()
            side = position.get("side", position.get("direction"))
            size = position.get("size", position.get("qty", 0))
        else:
            symbol = str(getattr(position, "symbol", "")).upper()
            direction = getattr(position, "direction", None)
            side = getattr(direction, "value", direction)
            size = getattr(position, "size", 0)
        if not symbol:
            continue
        mapped[symbol] = {
            "side": _normalize_side(side),
            "qty": _normalize_qty(size),
        }
    return mapped


def broker_position_map(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for position in positions:
        symbol = str(position.get("symbol", "")).upper()
        if not symbol:
            continue
        mapped[symbol] = {
            "side": _normalize_side(position.get("side")),
            "qty": _normalize_qty(position.get("qty")),
        }
    return mapped


def detect_position_mismatch(
    local_positions: dict[str, dict[str, Any]] | list[Any],
    broker_positions: dict[str, dict[str, Any]] | list[dict[str, Any]],
    broker_orders: list[dict[str, Any]] | None = None,
) -> ReconciliationResult:
    broker_orders = broker_orders or []
    if not isinstance(local_positions, dict):
        local_positions = local_position_map(local_positions)
    if not isinstance(broker_positions, dict):
        broker_positions = broker_position_map(broker_positions)

    local_symbols = set(local_positions)
    broker_symbols = set(broker_positions)
    shared = local_symbols & broker_symbols

    if local_symbols != broker_symbols:
        if broker_symbols - local_symbols:
            reason = "broker_only_position"
        elif local_symbols - broker_symbols:
            reason = "local_only_position"
        else:
            reason = "symbol_set_mismatch"
        return ReconciliationResult(
            local_positions,
            broker_positions,
            broker_orders,
            mismatch=True,
            reason=reason,
            entries_blocked=True,
        )

    for symbol in shared:
        if local_positions[symbol] != broker_positions[symbol]:
            return ReconciliationResult(
                local_positions,
                broker_positions,
                broker_orders,
                mismatch=True,
                reason="quantity_or_side_mismatch",
                entries_blocked=True,
            )

    return ReconciliationResult(local_positions, broker_positions, broker_orders, mismatch=False)


class BrokerReconciler:
    def __init__(self, alpaca_client, settings) -> None:
        self._alpaca = alpaca_client
        self._settings = settings

    def check(self, local_positions) -> ReconciliationResult:
        local = local_position_map(local_positions)
        broker = broker_position_map(self._alpaca.get_positions())
        orders = self._alpaca.get_open_orders()
        return detect_position_mismatch(local, broker, orders)

    def check_and_repair(self, local_positions) -> ReconciliationResult:
        result = self.check(local_positions)
        if not result.mismatch:
            return result

        if not bool(getattr(self._settings, "OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS", False)):
            return ReconciliationResult(
                result.local_open_positions,
                result.broker_open_positions,
                result.broker_open_orders,
                mismatch=True,
                reason=result.reason,
                entries_blocked=bool(
                    getattr(self._settings, "OLYMPUS_BLOCK_ENTRIES_ON_BROKER_MISMATCH", True)
                ),
            )

        if not bool(getattr(self._settings, "ALPACA_PAPER", True)):
            raise RuntimeError("Broker auto-repair is forbidden unless ALPACA_PAPER=True")

        logger.warning("Broker/local mismatch detected (%s); attempting paper auto-repair", result.reason)
        orders_ok = self._alpaca.cancel_all_orders()
        positions_ok = self._alpaca.close_all_positions(cancel_orders=True)
        repair_ok = bool(orders_ok and positions_ok)
        return ReconciliationResult(
            result.local_open_positions,
            result.broker_open_positions,
            result.broker_open_orders,
            mismatch=True,
            reason=result.reason,
            repair_attempted=True,
            repair_succeeded=repair_ok,
            entries_blocked=True,
        )
