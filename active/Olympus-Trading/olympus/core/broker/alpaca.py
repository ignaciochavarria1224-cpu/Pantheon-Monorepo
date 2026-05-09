"""
Alpaca broker client for Olympus.
Paper trading only in Phase 1. A hard guard prevents live trading instantiation.
Live trading is not enabled until Phase 8.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
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

    def get_account_snapshot(self) -> dict[str, Any]:
        """
        Read-only extended account snapshot for reconciliation tooling.

        Returns every field on the TradeAccount model that is useful for
        equity reconciliation. Does not modify any state. Raises on failure
        (callers should handle and report).
        """
        acct = self._client.get_account()

        def _f(v: Any) -> Optional[float]:
            return float(v) if v is not None else None

        return {
            "account_number":           str(acct.account_number),
            "status":                   str(acct.status.value) if acct.status else None,
            "currency":                 str(acct.currency) if acct.currency else None,
            "created_at":               acct.created_at,
            "equity":                   _f(acct.equity),
            "last_equity":              _f(acct.last_equity),
            "cash":                     _f(acct.cash),
            "buying_power":             _f(acct.buying_power),
            "portfolio_value":          _f(acct.portfolio_value),
            "long_market_value":        _f(acct.long_market_value),
            "short_market_value":       _f(acct.short_market_value),
            "initial_margin":           _f(acct.initial_margin),
            "maintenance_margin":       _f(acct.maintenance_margin),
            "accrued_fees":             _f(acct.accrued_fees),
            "pending_transfer_in":      _f(acct.pending_transfer_in),
            "pending_transfer_out":     _f(acct.pending_transfer_out),
            "multiplier":               _f(acct.multiplier),
            "daytrade_count":           int(acct.daytrade_count) if acct.daytrade_count is not None else None,
            "pattern_day_trader":       bool(acct.pattern_day_trader) if acct.pattern_day_trader is not None else None,
            "trading_blocked":          bool(acct.trading_blocked) if acct.trading_blocked is not None else None,
            "account_blocked":          bool(acct.account_blocked) if acct.account_blocked is not None else None,
        }

    def get_positions_snapshot(self) -> list[dict[str, Any]]:
        """
        Read-only extended positions snapshot for reconciliation tooling.

        Returns the full set of fields needed to reconcile market values and
        unrealized PnL against equity. Raises on failure.
        """
        positions = self._client.get_all_positions()
        result: list[dict[str, Any]] = []
        for p in positions:
            def _f(v: Any) -> Optional[float]:
                return float(v) if v is not None else None
            result.append({
                "symbol":                   str(p.symbol),
                "qty":                      _f(p.qty),
                "side":                     str(p.side.value) if p.side else None,
                "avg_entry_price":          _f(p.avg_entry_price),
                "current_price":            _f(p.current_price),
                "market_value":             _f(p.market_value),
                "cost_basis":               _f(p.cost_basis),
                "unrealized_pl":            _f(p.unrealized_pl),
                "unrealized_plpc":          _f(p.unrealized_plpc),
                "unrealized_intraday_pl":   _f(p.unrealized_intraday_pl),
                "lastday_price":            _f(p.lastday_price),
            })
        return result

    def get_activities(self, after: datetime) -> list[dict[str, Any]]:
        """
        Read-only fetch of account activities from Alpaca.

        Wraps the /v2/account/activities endpoint. Returns a list of raw
        activity dicts as returned by the API (each contains at minimum
        activity_type, date or transaction_time, net_amount or qty/price).
        Pages through results until exhausted.

        Args:
            after: Inclusive lower bound on activity date (UTC). Naive datetimes
                   are treated as UTC.

        Raises on transport-layer failure.
        """
        if after.tzinfo is None:
            after = after.replace(tzinfo=timezone.utc)
        # Alpaca expects RFC3339 timestamps for the `after` query param.
        after_str = after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        all_rows: list[dict[str, Any]] = []
        page_token: Optional[str] = None
        # Hard upper bound on pages to defend against runaway loops.
        for _ in range(200):
            params: dict[str, Any] = {
                "after": after_str,
                "direction": "asc",
                "page_size": 100,
            }
            if page_token:
                params["page_token"] = page_token
            resp = self._client.get("/account/activities", data=params)
            if not resp:
                break
            if not isinstance(resp, list):
                # Unexpected shape — return what we have.
                break
            all_rows.extend(resp)
            if len(resp) < 100:
                break
            # Use the last row's id as the next page_token.
            last = resp[-1]
            new_token = last.get("id") if isinstance(last, dict) else None
            if not new_token or new_token == page_token:
                break
            page_token = new_token
        return all_rows

    def get_order(self, order_id: str) -> Optional[dict[str, Any]]:
        """
        Get details for a specific order by ID.
        Returns None if order not found or on error.
        """
        try:
            order = self._client.get_order(order_id)
            return {
                "order_id": str(order.id),
                "client_order_id": str(order.client_order_id) if order.client_order_id else None,
                "symbol": str(order.symbol),
                "qty": int(float(order.qty)) if order.qty is not None else None,
                "filled_qty": int(float(order.filled_qty)) if order.filled_qty is not None else None,
                "side": str(order.side.value) if order.side else None,
                "type": str(order.type.value) if order.type else None,
                "status": str(order.status.value) if order.status else None,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price is not None else None,
                "submitted_at": order.submitted_at,
                "filled_at": order.filled_at,
                "expired_at": order.expired_at,
                "canceled_at": order.canceled_at,
            }
        except Exception as exc:
            logger.debug("AlpacaClient.get_order(%s) failed: %s", order_id, exc)
            return None

    def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        after: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Get orders with optional filters.
        Returns list of order dicts, empty on error.
        """
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            params = GetOrdersRequest(
                status=QueryOrderStatus(status) if status else None,
                symbols=[symbol.upper()] if symbol else None,
                after=after,
                until=until,
                limit=limit,
            )
            orders = self._client.get_orders(filter=params)
            result = []
            for order in orders:
                result.append({
                    "order_id": str(order.id),
                    "client_order_id": str(order.client_order_id) if order.client_order_id else None,
                    "symbol": str(order.symbol),
                    "qty": int(float(order.qty)) if order.qty is not None else None,
                    "filled_qty": int(float(order.filled_qty)) if order.filled_qty is not None else None,
                    "side": str(order.side.value) if order.side else None,
                    "type": str(order.type.value) if order.type else None,
                    "status": str(order.status.value) if order.status else None,
                    "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price is not None else None,
                    "submitted_at": order.submitted_at,
                    "filled_at": order.filled_at,
                    "expired_at": order.expired_at,
                    "canceled_at": order.canceled_at,
                })
            return result
        except Exception as exc:
            logger.error("AlpacaClient.get_orders() failed: %s", exc)
            return []

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
