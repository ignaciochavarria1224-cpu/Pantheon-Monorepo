"""
Alpaca broker client for Olympus.
Paper trading only in Phase 1. A hard guard prevents live trading instantiation.
Live trading is not enabled until Phase 8.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetCalendarRequest, GetOrdersRequest, MarketOrderRequest

from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)


class LiveTradingGuardError(RuntimeError):
    """Raised if someone attempts to initialize a live (non-paper) trading client."""


class AlpacaClient:
    """
    Authenticated Alpaca trading client (paper only in Phase 1).

    Phase 1 provides:
      - get_account()    — account equity, buying power, status
      - is_market_open() — bool
      - get_clock()      — current market clock from Alpaca
      - ping()           — lightweight connectivity check with latency
    """

    def __init__(self) -> None:
        # --- Hard guard: refuse to initialize in live mode ---
        if not settings.ALPACA_PAPER:
            raise LiveTradingGuardError(
                "ALPACA_PAPER=False is set, but live trading is not enabled until Phase 8. "
                "Set ALPACA_PAPER=true in your .env to use the paper trading client."
            )

        self._client = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=True,
        )
        logger.info("AlpacaClient initialized (paper=True)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_account(self) -> dict[str, Any]:
        """
        Return account information: equity, buying_power, status, currency.
        Raises on connection failure (logged before raising).
        """
        try:
            acct = self._client.get_account()
            result = {
                "equity":       float(acct.equity),
                "buying_power": float(acct.buying_power),
                "status":       str(acct.status.value),
                "currency":     str(acct.currency),
                "account_number": str(acct.account_number),
            }
            logger.info(
                "Account: equity=$%.2f, buying_power=$%.2f, status=%s",
                result["equity"], result["buying_power"], result["status"],
            )
            return result
        except Exception as exc:
            logger.error("AlpacaClient.get_account() failed: %s", exc)
            raise

    def is_market_open(self) -> bool:
        """Return True if the US equity market is currently open."""
        try:
            clock = self._client.get_clock()
            is_open = bool(clock.is_open)
            logger.debug("Market is_open=%s", is_open)
            return is_open
        except Exception as exc:
            logger.error("AlpacaClient.is_market_open() failed: %s", exc)
            raise

    def get_clock(self) -> dict[str, Any]:
        """
        Return current market clock from Alpaca.
        Keys: timestamp, is_open, next_open, next_close
        """
        try:
            clock = self._client.get_clock()
            result = {
                "timestamp":  clock.timestamp,
                "is_open":    bool(clock.is_open),
                "next_open":  clock.next_open,
                "next_close": clock.next_close,
            }
            logger.info(
                "Market clock: is_open=%s, next_open=%s, next_close=%s",
                result["is_open"],
                result["next_open"],
                result["next_close"],
            )
            return result
        except Exception as exc:
            logger.error("AlpacaClient.get_clock() failed: %s", exc)
            raise

    def submit_market_order(
        self,
        symbol: str,
        qty: int,
        side: str,
    ) -> dict[str, Any]:
        """
        Submit a market order to the Alpaca paper account.

        Args:
            symbol: Ticker symbol (e.g. "AAPL").
            qty: Number of shares (positive integer).
            side: "buy" or "sell".

        Returns:
            Dict with order_id, symbol, qty, side, status, filled_avg_price.
        Raises on any failure — callers must handle exceptions.
        """
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        try:
            order = self._client.submit_order(order_data=req)
            result = {
                "order_id": str(order.id),
                "symbol": str(order.symbol),
                "qty": int(float(order.qty)) if order.qty is not None else qty,
                "side": side.lower(),
                "status": str(order.status.value) if order.status else "unknown",
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price is not None else None
                ),
            }
            logger.info(
                "Order submitted: %s %d %s — id=%s status=%s fill=%.2f",
                side.upper(), qty, symbol,
                result["order_id"][:8],
                result["status"],
                result["filled_avg_price"] or 0.0,
            )
            return result
        except Exception as exc:
            logger.error(
                "submit_market_order failed: %s %d %s — %s", side.upper(), qty, symbol, exc
            )
            raise

    def get_positions(self) -> list[dict[str, Any]]:
        """
        Return all current open positions in the paper account.
        Returns empty list if no positions or on failure.
        """
        try:
            positions = self._client.get_all_positions()
            result = []
            for pos in positions:
                result.append({
                    "symbol": str(pos.symbol),
                    "qty": float(pos.qty) if pos.qty is not None else 0.0,
                    "side": str(pos.side.value) if pos.side else "unknown",
                    "avg_entry_price": float(pos.avg_entry_price) if pos.avg_entry_price else 0.0,
                    "current_price": float(pos.current_price) if pos.current_price else None,
                    "unrealized_pl": float(pos.unrealized_pl) if pos.unrealized_pl else 0.0,
                })
            logger.debug("get_positions: %d open position(s)", len(result))
            return result
        except Exception as exc:
            logger.error("AlpacaClient.get_positions() failed: %s", exc)
            return []

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Return all open (pending) orders, optionally filtered to a specific symbol.
        Returns empty list on failure — callers must not raise based on this result.
        """
        try:
            params = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[symbol.upper()] if symbol else None,
            )
            orders = self._client.get_orders(filter=params)
            result = []
            for order in orders:
                result.append({
                    "order_id": str(order.id),
                    "symbol": str(order.symbol),
                    "side": str(order.side.value) if order.side else "unknown",
                    "status": str(order.status.value) if order.status else "unknown",
                })
            logger.debug(
                "get_open_orders(%s): %d order(s)", symbol or "all", len(result)
            )
            return result
        except Exception as exc:
            logger.error("AlpacaClient.get_open_orders() failed: %s", exc)
            return []

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders in the paper account.
        Returns True on success, False on failure.
        """
        try:
            responses = self._client.cancel_orders()
            logger.info("Cancelled %d open Alpaca order(s)", len(responses))
            return True
        except Exception as exc:
            logger.error("AlpacaClient.cancel_all_orders() failed: %s", exc)
            return False

    def close_all_positions(self, cancel_orders: bool = True) -> bool:
        """
        Ask Alpaca to liquidate all open positions, optionally cancelling open orders first.
        Returns True when the liquidation request is accepted, False on failure.
        """
        try:
            responses = self._client.close_all_positions(cancel_orders=cancel_orders)
            logger.warning(
                "Broker fail-safe liquidation submitted for %d position(s) (cancel_orders=%s)",
                len(responses),
                cancel_orders,
            )
            return True
        except Exception as exc:
            logger.error(
                "AlpacaClient.close_all_positions(cancel_orders=%s) failed: %s",
                cancel_orders,
                exc,
            )
            return False

    def ping(self) -> tuple[bool, float]:
        """
        Lightweight connectivity check.
        Returns (success: bool, latency_ms: float).
        Never raises — connection failures return (False, -1.0).
        """
        t0 = time.monotonic()
        try:
            self._client.get_clock()
            latency_ms = (time.monotonic() - t0) * 1000
            logger.info("Alpaca ping OK — latency=%.1fms", latency_ms)
            return True, latency_ms
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error("Alpaca ping FAILED (%.1fms): %s", latency_ms, exc)
            return False, -1.0
