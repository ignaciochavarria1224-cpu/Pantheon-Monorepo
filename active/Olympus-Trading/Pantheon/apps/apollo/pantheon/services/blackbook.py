from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import BLACKBOOK_APP_PATH, BLACKBOOK_DB_PATH


def _queries():
    app_path = Path(BLACKBOOK_APP_PATH)
    os.environ.setdefault("BLACKBOOK_DB_PATH", BLACKBOOK_DB_PATH)
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    from BlackBook.db import queries
    return queries


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(BLACKBOOK_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _compute_dashboard_metrics(balances: list[dict], all_txns: list[dict], settings: dict) -> dict:
    today = date.today().isoformat()
    today_txns = [t for t in all_txns if t.get("date", "") == today]

    daily_food_budget = float(settings.get("daily_food_budget", 30))
    pay_period_days = int(settings.get("pay_period_days", 14))

    food_today = sum(float(t["amount"]) for t in today_txns if t.get("category") == "Food" and t.get("type") == "expense")
    food_this_week = sum(
        float(t["amount"]) for t in all_txns
        if t.get("category") == "Food" and t.get("type") == "expense"
        and t.get("date", "") >= _week_start()
    )
    weekly_food_budget = daily_food_budget * 7

    total_income = sum(float(t["amount"]) for t in all_txns if t.get("type") == "income")
    total_expenses = sum(float(t["amount"]) for t in all_txns if t.get("type") == "expense")
    lifetime_surplus = round(total_income - total_expenses, 2)

    liquid_balances = [b for b in balances if b.get("account_type") in ("cash", "savings") and not b.get("is_debt")]
    liquid_total = sum(float(b["balance"]) for b in liquid_balances)

    # Runway: liquid assets / (30-day expenses / 30)
    expenses_30d = sum(
        float(t["amount"]) for t in all_txns
        if t.get("type") == "expense" and t.get("date", "") >= _days_ago(30)
    )
    daily_burn = expenses_30d / 30 if expenses_30d else 1
    runway_days = int(liquid_total / daily_burn) if daily_burn > 0 else 0

    return {
        "daily_food_left": round(daily_food_budget - food_today, 2),
        "weekly_food_left": round(weekly_food_budget - food_this_week, 2),
        "daily_food_budget": daily_food_budget,
        "weekly_food_budget": weekly_food_budget,
        "lifetime_surplus": lifetime_surplus,
        "runway_days": runway_days,
        "daily_burn": round(daily_burn, 2),
        "txns_today": len(today_txns),
    }


def _week_start() -> str:
    today = date.today()
    return (today - __import__("datetime").timedelta(days=today.weekday())).isoformat()


def _days_ago(n: int) -> str:
    from datetime import timedelta
    return (date.today() - timedelta(days=n)).isoformat()


def get_snapshot() -> dict[str, Any]:
    try:
        queries = _queries()
        accounts = queries.load_accounts()
        all_txns = queries.load_transactions(limit=5000)
        balances = queries.calculate_account_balances(accounts, all_txns)
        reports = queries.load_daily_reports(limit=3)
        spending = queries.get_spending_summary("month")
        settings = queries.get_settings()

        total_assets = sum(float(item["balance"]) for item in balances if not item["is_debt"])
        total_debt = sum(abs(float(item["balance"])) for item in balances if item["is_debt"])
        dashboard = _compute_dashboard_metrics(balances, all_txns, settings)

        return {
            "connected": True,
            "accounts": accounts,
            "balances": balances,
            "recent_transactions": all_txns[:8],
            "spending_month": spending[:8],
            "reports": reports,
            "net_worth": round(total_assets - total_debt, 2),
            "total_assets": round(total_assets, 2),
            "total_debt": round(total_debt, 2),
            **dashboard,
        }
    except Exception as exc:
        return {
            "connected": False,
            "error": str(exc),
            "accounts": [],
            "balances": [],
            "recent_transactions": [],
            "spending_month": [],
            "reports": [],
            "net_worth": 0,
            "total_assets": 0,
            "total_debt": 0,
            "daily_food_left": 0,
            "weekly_food_left": 0,
            "lifetime_surplus": 0,
            "runway_days": 0,
            "daily_burn": 0,
            "txns_today": 0,
        }


def get_account_balances() -> list[dict[str, Any]]:
    return get_snapshot().get("balances", [])


def get_recent_transactions(limit: int = 20) -> list[dict[str, Any]]:
    try:
        return _queries().load_transactions(limit=limit)
    except Exception:
        return []


def get_spending_summary(period: str = "month") -> list[dict[str, Any]]:
    try:
        return _queries().get_spending_summary(period=period)
    except Exception:
        return []


def get_accounts() -> list[dict[str, Any]]:
    try:
        return _queries().load_accounts()
    except Exception:
        return []


def add_expense(
    amount: float,
    description: str,
    category: str,
    account_name: str,
    tx_date: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    queries = _queries()
    accounts = queries.load_accounts()
    account = next((a for a in accounts if a["name"].lower() == account_name.lower()), None)
    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found."}
    queries.add_transaction(
        tx_date=date.fromisoformat(tx_date) if tx_date else date.today(),
        description=description,
        category=category,
        amount=amount,
        account_id=int(account["id"]),
        tx_type="expense",
        to_account_id=None,
        notes=notes,
    )
    return {"success": True}


def add_income(
    amount: float,
    description: str,
    account_name: str,
    tx_date: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    queries = _queries()
    accounts = queries.load_accounts()
    account = next((a for a in accounts if a["name"].lower() == account_name.lower()), None)
    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found."}
    queries.add_transaction(
        tx_date=date.fromisoformat(tx_date) if tx_date else date.today(),
        description=description,
        category="Income",
        amount=amount,
        account_id=int(account["id"]),
        tx_type="income",
        to_account_id=None,
        notes=notes,
    )
    return {"success": True}


# ── Holdings ───────────────────────────────────────────────────────────────────

def get_holdings_snapshot() -> dict[str, Any]:
    try:
        queries = _queries()
        holdings = queries.load_holdings()
        price_cache = {(p["symbol"], p["asset_type"]): p for p in queries.load_price_cache()}
        settings = queries.get_settings()
        last_refresh = settings.get("last_price_refresh_at", "")

        enriched = []
        portfolio_value = 0.0
        portfolio_invested = 0.0

        for h in holdings:
            key = (h["symbol"], h["asset_type"])
            price_row = price_cache.get(key)
            price = float(price_row["price"]) if price_row else 0.0
            qty = float(h.get("quantity") or 0)
            invested = float(h.get("amount_invested") or 0)
            value = round(price * qty, 2)
            pnl = round(value - invested, 2)
            pnl_pct = round((pnl / invested * 100), 2) if invested else 0.0

            portfolio_value += value
            portfolio_invested += invested

            enriched.append({
                "id": h["id"],
                "symbol": h["symbol"],
                "display_name": h["display_name"],
                "asset_type": h["asset_type"],
                "account": h["account"],
                "quantity": qty,
                "price": price,
                "value": value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "is_positive": pnl >= 0,
            })

        portfolio_pnl = round(portfolio_value - portfolio_invested, 2)
        return {
            "holdings": enriched,
            "portfolio_value": round(portfolio_value, 2),
            "portfolio_pnl": portfolio_pnl,
            "portfolio_invested": round(portfolio_invested, 2),
            "last_refresh": last_refresh,
        }
    except Exception as exc:
        return {
            "holdings": [],
            "portfolio_value": 0,
            "portfolio_pnl": 0,
            "portfolio_invested": 0,
            "last_refresh": "",
            "error": str(exc),
        }


# ── Journal ────────────────────────────────────────────────────────────────────

def get_journal_entries(tag_filter: str = "All", limit: int = 50) -> list[dict[str, Any]]:
    try:
        return _queries().load_journal_entries(limit=limit, tag_filter=tag_filter)
    except Exception:
        return []


def create_journal_entry(entry_date: str, tag: str, body: str) -> dict[str, Any]:
    try:
        _queries().save_journal_entry(
            entry_date=date.fromisoformat(entry_date) if entry_date else date.today(),
            tag=tag,
            body=body,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def delete_journal_entry(entry_id: int) -> dict[str, Any]:
    try:
        _queries().delete_journal_entry(entry_id)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Settings ───────────────────────────────────────────────────────────────────

def get_bb_settings() -> dict[str, str]:
    try:
        return _queries().get_settings()
    except Exception:
        return {}


def save_bb_settings(data: dict[str, Any]) -> dict[str, Any]:
    try:
        _queries().set_settings(data)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def set_balance_override(account_id: int, override: float | None) -> dict[str, Any]:
    try:
        _queries().update_account_balance_override(account_id, override)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Transactions ───────────────────────────────────────────────────────────────

def list_transactions(limit: int = 200) -> list[dict[str, Any]]:
    try:
        return _queries().load_transactions(limit=limit)
    except Exception:
        return []


def add_transaction(
    tx_date: str | None,
    description: str,
    category: str,
    amount: float,
    account_name: str,
    tx_type: str,
    to_account_name: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    queries = _queries()
    accounts = queries.load_accounts()
    account = next((a for a in accounts if a["name"].lower() == account_name.lower()), None)
    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found."}
    to_account_id = None
    if to_account_name:
        to_acct = next((a for a in accounts if a["name"].lower() == to_account_name.lower()), None)
        if not to_acct:
            return {"success": False, "error": f"Destination account '{to_account_name}' not found."}
        to_account_id = int(to_acct["id"])
    try:
        queries.add_transaction(
            tx_date=date.fromisoformat(tx_date) if tx_date else date.today(),
            description=description,
            category=category,
            amount=amount,
            account_id=int(account["id"]),
            tx_type=tx_type,
            to_account_id=to_account_id,
            notes=notes,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def delete_transaction(tx_id: int) -> dict[str, Any]:
    try:
        _queries().delete_transaction(tx_id)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Holdings (buy/sell) ────────────────────────────────────────────────────────

def add_holding(
    symbol: str,
    display_name: str,
    asset_type: str,
    account_name: str,
    amount_invested: float,
    quantity: float,
    avg_price: float,
    coingecko_id: str = "",
) -> dict[str, Any]:
    queries = _queries()
    accounts = queries.load_accounts()
    account = next((a for a in accounts if a["name"].lower() == account_name.lower()), None)
    if not account:
        return {"success": False, "error": f"Account '{account_name}' not found."}
    try:
        queries.add_holding(
            symbol=symbol,
            display_name=display_name,
            asset_type=asset_type,
            account_id=int(account["id"]),
            amount_invested=amount_invested,
            quantity=quantity,
            avg_price=avg_price,
            coingecko_id=coingecko_id,
        )
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def update_holding(holding_id: int, amount_invested: float, quantity: float, avg_price: float) -> dict[str, Any]:
    try:
        _queries().update_holding(holding_id, amount_invested, quantity, avg_price)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def delete_holding(holding_id: int) -> dict[str, Any]:
    try:
        _queries().delete_holding(holding_id)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Allocation snapshots ───────────────────────────────────────────────────────

def list_allocation_snapshots(limit: int = 10) -> list[dict[str, Any]]:
    try:
        return _queries().load_allocation_snapshots(limit=limit)
    except Exception:
        return []


def save_allocation_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        _queries().save_allocation_snapshot(payload)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Reports ────────────────────────────────────────────────────────────────────

def list_daily_reports(limit: int = 30) -> list[dict[str, Any]]:
    try:
        return _queries().load_daily_reports(limit=limit)
    except Exception:
        return []


def delete_daily_report(report_date: str) -> dict[str, Any]:
    try:
        _queries().delete_daily_report(report_date)
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ── Agenda (financial deadlines from settings) ────────────────────────────────

def get_agenda() -> dict[str, Any]:
    settings = get_bb_settings()
    items: list[dict[str, Any]] = []
    today = date.today()

    def _next_dom(day: int) -> str:
        if day < 1:
            return ""
        try:
            from datetime import timedelta
            target = today.replace(day=min(day, 28))
            if target < today:
                month = today.month + 1
                year = today.year + (1 if month > 12 else 0)
                month = 1 if month > 12 else month
                target = today.replace(year=year, month=month, day=min(day, 28))
            return target.isoformat()
        except Exception:
            return ""

    for key, label in (
        ("payday_day", "Payday"),
        ("cc_due_day", "Credit card due"),
        ("statement_close_day", "Statement close"),
        ("rent_due_day", "Rent due"),
    ):
        raw = settings.get(key)
        if not raw:
            continue
        try:
            day = int(raw)
        except (TypeError, ValueError):
            continue
        items.append({"label": label, "date": _next_dom(day), "source": "settings"})

    items.sort(key=lambda x: x.get("date") or "9999")
    return {"items": items}
