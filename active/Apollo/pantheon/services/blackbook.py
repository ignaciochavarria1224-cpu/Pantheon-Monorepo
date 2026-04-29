from __future__ import annotations

import sys
import os
import queue
import threading
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import BLACKBOOK_APP_PATH, BLACK_BOOK_DB_URL, DATA_DIR


BLACKBOOK_CACHE_PATH = Path(DATA_DIR) / "blackbook_snapshot.json"


def _queries():
    app_path = Path(BLACKBOOK_APP_PATH)
    if BLACK_BOOK_DB_URL and not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = BLACK_BOOK_DB_URL
    if str(app_path) not in sys.path:
        sys.path.insert(0, str(app_path))
    from BlackBook.db import queries

    return queries


def _empty_snapshot(error: str) -> dict[str, Any]:
    return {
        "connected": False,
        "error": error,
        "stale": False,
        "source": "unavailable",
        "fetched_at": datetime.now().isoformat(),
        "accounts": [],
        "balances": [],
        "recent_transactions": [],
        "spending_month": [],
        "reports": [],
        "net_worth": 0,
        "total_assets": 0,
        "total_debt": 0,
    }


def _snapshot_inner() -> dict[str, Any]:
    queries = _queries()
    accounts = queries.load_accounts()
    ledger_transactions = queries.load_transactions(limit=5000)
    balances = queries.calculate_account_balances(accounts, ledger_transactions)
    reports = queries.load_daily_reports(limit=3)
    spending = queries.get_spending_summary("month")

    total_assets = sum(float(item["balance"]) for item in balances if not item["is_debt"])
    total_debt = sum(abs(float(item["balance"])) for item in balances if item["is_debt"])

    return {
        "connected": True,
        "stale": False,
        "source": "live",
        "fetched_at": datetime.now().isoformat(),
        "accounts": accounts,
        "balances": balances,
        "recent_transactions": ledger_transactions[:8],
        "spending_month": spending[:8],
        "reports": reports,
        "net_worth": round(total_assets - total_debt, 2),
        "total_assets": round(total_assets, 2),
        "total_debt": round(total_debt, 2),
    }


def _load_cached_snapshot(error: str) -> dict[str, Any] | None:
    if not BLACKBOOK_CACHE_PATH.exists():
        return None
    try:
        payload = json.loads(BLACKBOOK_CACHE_PATH.read_text(encoding="utf-8"))
        payload["connected"] = False
        payload["stale"] = True
        payload["source"] = "cache"
        payload["error"] = error
        payload.setdefault("fetched_at", datetime.now().isoformat())
        return payload
    except Exception:
        return None


def _store_cached_snapshot(snapshot: dict[str, Any]) -> None:
    try:
        BLACKBOOK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BLACKBOOK_CACHE_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    except Exception:
        return


def get_snapshot(timeout_seconds: int = 8) -> dict[str, Any]:
    result_queue: queue.Queue[tuple[str, dict[str, Any] | Exception]] = queue.Queue(maxsize=1)

    def runner() -> None:
        try:
            result_queue.put(("ok", _snapshot_inner()))
        except Exception as exc:
            result_queue.put(("error", exc))

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    try:
        status, payload = result_queue.get(timeout=timeout_seconds)
        if status == "ok":
            _store_cached_snapshot(payload)  # type: ignore[arg-type]
            return payload  # type: ignore[return-value]
        raise payload  # type: ignore[misc]
    except queue.Empty:
        error = (
            "BlackBook connection timed out. Check DATABASE_URL/BLACK_BOOK_DB_URL and confirm the Neon database is reachable from this laptop."
        )
        return _load_cached_snapshot(error) or _empty_snapshot(error)
    except Exception as exc:
        error = str(exc)
        return _load_cached_snapshot(error) or _empty_snapshot(error)


def get_account_balances() -> list[dict[str, Any]]:
    snapshot = get_snapshot()
    return snapshot.get("balances", [])


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
    account = next((item for item in accounts if item["name"].lower() == account_name.lower()), None)
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
    account = next((item for item in accounts if item["name"].lower() == account_name.lower()), None)
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
