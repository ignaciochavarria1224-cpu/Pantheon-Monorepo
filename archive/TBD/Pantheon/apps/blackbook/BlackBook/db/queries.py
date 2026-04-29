"""
db/queries.py — SQLite queries for Black Book.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DATE_FMT = "%Y-%m-%d"

DEFAULT_SETTINGS = {
    "daily_food_budget": "30",
    "pay_period_days": "14",
    "statement_day": "2",
    "due_day": "27",
    "savings_pct": "0.30",
    "spending_pct": "0.40",
    "crypto_pct": "0.10",
    "taxable_investing_pct": "0.10",
    "roth_ira_pct": "0.10",
    "debt_allocation_mode": "proportional",
    "migration_completed": "0",
    "last_price_refresh_at": "",
    "next_payday": "",
}

DEFAULT_ACCOUNTS = [
    {"name": "Checking",    "account_type": "cash",       "is_debt": 0, "include_in_runway": 1, "sort_order": 1},
    {"name": "Savings",     "account_type": "savings",    "is_debt": 0, "include_in_runway": 1, "sort_order": 2},
    {"name": "Savor",       "account_type": "credit",     "is_debt": 1, "include_in_runway": 0, "sort_order": 3},
    {"name": "Venture",     "account_type": "credit",     "is_debt": 1, "include_in_runway": 0, "sort_order": 4},
    {"name": "Coinbase",    "account_type": "investment", "is_debt": 0, "include_in_runway": 0, "sort_order": 5},
    {"name": "Roth IRA",    "account_type": "investment", "is_debt": 0, "include_in_runway": 0, "sort_order": 6},
    {"name": "Investments", "account_type": "investment", "is_debt": 0, "include_in_runway": 0, "sort_order": 7},
]

COMMON_CATEGORIES = [
    "Food", "Bills", "Subscriptions", "Income", "Debt Payment",
    "Gas", "Health", "Shopping", "Entertainment", "Savings",
    "Transfer", "Investing", "Other",
]

JOURNAL_TAGS = ["General", "Finance", "Reflection", "Decision", "Goals", "Other"]

CRYPTO_NAME_TO_ID = {
    "XRP": "ripple",
    "Bitcoin (BTC)": "bitcoin",
    "Bittensor (TAO)": "bittensor",
    "Worldcoin (WLD)": "worldcoin-wld",
    "Sui (SUI)": "sui",
    "Solana (SOL)": "solana",
    "Cash (USD)": "",
}

STOCK_NAME_TO_TICKER = {
    "NVIDIA (NVDA)": "NVDA",
    "Palantir (PLTR)": "PLTR",
    "Tesla (TSLA)": "TSLA",
    "Invesco QQQ (QQQ)": "QQQ",
    "SPDR S&P 500 (SPY)": "SPY",
}


# ── Connection ─────────────────────────────────────────────────────────────────

BLACKBOOK_DB_PATH = os.environ.get(
    "BLACKBOOK_DB_PATH",
    str(Path(__file__).resolve().parents[4] / "TBD" / "Pantheon" / "data" / "blackbook.db"),
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(BLACKBOOK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _one(cur) -> dict | None:
    row = cur.fetchone()
    return dict(row) if row else None


# ── Schema init ────────────────────────────────────────────────────────────────

def init_db() -> None:
    ddl = [
        "CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, account_type TEXT NOT NULL, is_debt INTEGER NOT NULL DEFAULT 0, include_in_runway INTEGER NOT NULL DEFAULT 1, starting_balance REAL NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0, current_balance_override REAL DEFAULT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL, account_id INTEGER NOT NULL, type TEXT NOT NULL, to_account_id INTEGER, notes TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(account_id) REFERENCES accounts(id), FOREIGN KEY(to_account_id) REFERENCES accounts(id))",
        "CREATE TABLE IF NOT EXISTS holdings (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, display_name TEXT NOT NULL, asset_type TEXT NOT NULL, account_id INTEGER NOT NULL, amount_invested REAL NOT NULL DEFAULT 0, quantity REAL NOT NULL DEFAULT 0, avg_price REAL NOT NULL DEFAULT 0, coingecko_id TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(account_id) REFERENCES accounts(id))",
        "CREATE TABLE IF NOT EXISTS allocation_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, paycheck_amount REAL NOT NULL, run_date TEXT NOT NULL, debt_total REAL NOT NULL, food_reserved REAL NOT NULL, debt_reserved REAL NOT NULL, savings_reserved REAL NOT NULL, surplus_savings REAL NOT NULL DEFAULT 0, spending_reserved REAL NOT NULL, crypto_reserved REAL NOT NULL, taxable_reserved REAL NOT NULL, roth_reserved REAL NOT NULL, debt_breakdown_json TEXT NOT NULL, meta_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS price_cache (symbol TEXT NOT NULL, asset_type TEXT NOT NULL, price REAL NOT NULL, previous_close REAL, currency TEXT NOT NULL DEFAULT 'USD', source TEXT NOT NULL, as_of_date TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY(symbol, asset_type))",
        "CREATE TABLE IF NOT EXISTS price_history (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, asset_type TEXT NOT NULL, price REAL NOT NULL, previous_close REAL, as_of_date TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS daily_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, report_date TEXT NOT NULL UNIQUE, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_date TEXT NOT NULL, tag TEXT NOT NULL DEFAULT 'General', body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS advisor_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, memory_date TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS advisor_conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS meridian_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT NOT NULL DEFAULT 'pending', requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, started_at TEXT, completed_at TEXT, result TEXT)",
        "CREATE TABLE IF NOT EXISTS meridian_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, note_id TEXT NOT NULL, title TEXT NOT NULL, stage TEXT NOT NULL, fitness REAL, maturity INTEGER, domains TEXT, body TEXT, cycle INTEGER, synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS meridian_brain (id INTEGER PRIMARY KEY AUTOINCREMENT, theme TEXT NOT NULL UNIQUE, body TEXT NOT NULL, cycle INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS meridian_questions (id INTEGER PRIMARY KEY AUTOINCREMENT, generated_date TEXT NOT NULL, questions TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)",
    ]
    conn = get_connection()
    try:
        cur = conn.cursor()
        for stmt in ddl:
            cur.execute(stmt)
        for k, v in DEFAULT_SETTINGS.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v),
            )
        for a in DEFAULT_ACCOUNTS:
            cur.execute(
                "INSERT OR IGNORE INTO accounts (name, account_type, is_debt, include_in_runway, starting_balance, sort_order) "
                "VALUES (?, ?, ?, ?, 0.0, ?)",
                (a["name"], a["account_type"], a["is_debt"], a["include_in_runway"], a["sort_order"]),
            )
        conn.commit()
    finally:
        conn.close()


# ── Settings ───────────────────────────────────────────────────────────────────

def get_settings() -> dict[str, str]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        return {str(r["key"]): str(r["value"]) for r in cur.fetchall()}
    finally:
        conn.close()


def set_settings(settings: dict[str, Any]) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        for k, v in settings.items():
            cur.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (k, str(v)),
            )
        conn.commit()
    finally:
        conn.close()


# ── Accounts ───────────────────────────────────────────────────────────────────

def load_accounts() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, account_type, is_debt, include_in_runway, "
            "starting_balance, sort_order, current_balance_override "
            "FROM accounts ORDER BY sort_order, name"
        )
        return _rows(cur)
    finally:
        conn.close()


def add_account(name: str, account_type: str, is_debt: int, include_in_runway: int) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS count FROM accounts")
        sort_order = int(_one(cur)["count"]) + 1
        cur.execute(
            "INSERT OR IGNORE INTO accounts (name, account_type, is_debt, include_in_runway, starting_balance, sort_order) "
            "VALUES (?, ?, ?, ?, 0.0, ?)",
            (name, account_type, is_debt, include_in_runway, sort_order),
        )
        conn.commit()
    finally:
        conn.close()


def update_account_balance_override(account_id: int, override: float | None) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE accounts SET current_balance_override = ? WHERE id = ?",
            (override, account_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Transactions ───────────────────────────────────────────────────────────────

def add_transaction(
    tx_date: date, description: str, category: str, amount: float,
    account_id: int, tx_type: str, to_account_id: int | None, notes: str,
) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transactions (date, description, category, amount, account_id, type, to_account_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tx_date.strftime(DATE_FMT), description.strip(), category,
                float(amount), int(account_id), tx_type,
                int(to_account_id) if to_account_id else None,
                notes.strip() or None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete_transaction(tx_id: int) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM transactions WHERE id = ?", (int(tx_id),))
        conn.commit()
    finally:
        conn.close()


def load_transactions(limit: int = 200) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.id, t.date, t.description, t.category, t.amount, t.type, t.notes,
                      a.name AS account, a.id AS account_id,
                      ta.name AS to_account, ta.id AS to_account_id
               FROM transactions t
               JOIN accounts a ON a.id = t.account_id
               LEFT JOIN accounts ta ON ta.id = t.to_account_id
               ORDER BY t.date DESC, t.id DESC
               LIMIT ?""",
            (limit,),
        )
        return _rows(cur)
    finally:
        conn.close()


def calculate_account_balances(
    accounts: list[dict] | None = None,
    transactions: list[dict] | None = None,
) -> list[dict]:
    accounts = accounts if accounts is not None else load_accounts()
    transactions = transactions if transactions is not None else load_transactions(limit=5000)

    balances: dict[int, float] = {}
    locked_overrides: set[int] = set()
    for acct in accounts:
        aid = int(acct["id"])
        starting_balance = float(acct.get("starting_balance") or 0)
        override = acct.get("current_balance_override")
        if override is not None:
            balances[aid] = float(override)
            locked_overrides.add(aid)
        else:
            balances[aid] = starting_balance

    for tx in transactions:
        aid = int(tx.get("account_id") or 0)
        to_account_id = tx.get("to_account_id")
        amount = float(tx.get("amount") or 0)
        tx_type = str(tx.get("type") or "")
        if tx_type == "income":
            if aid not in locked_overrides:
                balances[aid] = balances.get(aid, 0.0) + amount
        elif tx_type == "expense":
            if aid not in locked_overrides:
                balances[aid] = balances.get(aid, 0.0) - amount
        elif tx_type == "transfer" and to_account_id:
            to_account_id = int(to_account_id)
            if aid not in locked_overrides:
                balances[aid] = balances.get(aid, 0.0) - amount
            if to_account_id not in locked_overrides:
                balances[to_account_id] = balances.get(to_account_id, 0.0) + amount

    results: list[dict] = []
    for acct in accounts:
        aid = int(acct["id"])
        balance = round(balances.get(aid, 0.0), 2)
        is_debt = bool(int(acct.get("is_debt") or 0))
        results.append(
            {
                "id": aid,
                "name": str(acct.get("name") or ""),
                "account_type": str(acct.get("account_type") or ""),
                "is_debt": is_debt,
                "balance": balance,
                "current_balance_override": acct.get("current_balance_override"),
                "starting_balance": float(acct.get("starting_balance") or 0),
                "sort_order": int(acct.get("sort_order") or 0),
            }
        )
    return results


def get_spending_summary(period: str = "month") -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if period == "month":
            date_filter = "DATE_TRUNC('month', CAST(date AS DATE)) = DATE_TRUNC('month', CURRENT_DATE)"
        elif period == "week":
            date_filter = "CAST(date AS DATE) >= CURRENT_DATE - INTERVAL '7 days'"
        else:
            date_filter = "DATE_TRUNC('year', CAST(date AS DATE)) = DATE_TRUNC('year', CURRENT_DATE)"

        cur.execute(
            f"""
            SELECT category,
                   ROUND(SUM(amount)::numeric, 2) AS total,
                   COUNT(*) AS count
            FROM transactions
            WHERE type = 'expense' AND {date_filter}
            GROUP BY category
            ORDER BY total DESC
            """
        )
        return _rows(cur)
    finally:
        conn.close()


# ── Holdings ───────────────────────────────────────────────────────────────────

def calculate_account_balances(
    accounts: list[dict],
    transactions: list[dict],
    mode: str = "ledger",
) -> list[dict]:
    """Calculate per-account balances from transaction truth."""

    ledger_balances: dict[int, float] = {}
    override_balances: dict[int, float | None] = {}

    for acct in accounts:
        aid = int(acct["id"])
        ledger_balances[aid] = float(acct.get("starting_balance") or 0)
        override = acct.get("current_balance_override")
        override_balances[aid] = float(override) if override is not None else None

    for tx in transactions:
        aid = int(tx.get("account_id") or 0)
        to_account_id = tx.get("to_account_id")
        amount = float(tx.get("amount") or 0)
        tx_type = str(tx.get("type") or "")

        if tx_type == "income":
            ledger_balances[aid] = ledger_balances.get(aid, 0) + amount
        elif tx_type == "expense":
            ledger_balances[aid] = ledger_balances.get(aid, 0) - amount
        elif tx_type == "transfer" and to_account_id:
            to_aid = int(to_account_id)
            ledger_balances[aid] = ledger_balances.get(aid, 0) - amount
            ledger_balances[to_aid] = ledger_balances.get(to_aid, 0) + amount

    results: list[dict] = []
    for acct in accounts:
        aid = int(acct["id"])
        ledger_balance = round(ledger_balances.get(aid, 0.0), 2)
        override_balance = override_balances.get(aid)
        final_balance = override_balance if mode == "override" and override_balance is not None else ledger_balance
        results.append(
            {
                "id": aid,
                "name": str(acct.get("name") or ""),
                "account_type": str(acct.get("account_type") or ""),
                "is_debt": bool(int(acct.get("is_debt") or 0)),
                "include_in_runway": bool(int(acct.get("include_in_runway") or 0)),
                "starting_balance": round(float(acct.get("starting_balance") or 0), 2),
                "ledger_balance": ledger_balance,
                "override_balance": override_balance,
                "override_active": override_balance is not None,
                "balance": round(float(final_balance or 0), 2),
            }
        )
    return results


def add_holding(
    symbol: str, display_name: str, asset_type: str, account_id: int,
    amount_invested: float, quantity: float, avg_price: float, coingecko_id: str,
) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO holdings (symbol, display_name, asset_type, account_id, "
            "amount_invested, quantity, avg_price, coingecko_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol.upper().strip(), display_name.strip(), asset_type,
                int(account_id), float(amount_invested), float(quantity),
                float(avg_price), coingecko_id.strip() or None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_holding(holding_id: int, amount_invested: float, quantity: float, avg_price: float) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE holdings SET amount_invested=?, quantity=?, avg_price=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (float(amount_invested), float(quantity), float(avg_price), int(holding_id)),
        )
        conn.commit()
    finally:
        conn.close()


def delete_holding(holding_id: int) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM holdings WHERE id = ?", (int(holding_id),))
        conn.commit()
    finally:
        conn.close()


def load_holdings() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT h.id, h.symbol, h.display_name, h.asset_type,
                      h.amount_invested, h.quantity, h.avg_price, h.coingecko_id,
                      a.name AS account, a.id AS account_id
               FROM holdings h JOIN accounts a ON a.id = h.account_id
               ORDER BY a.sort_order, h.display_name"""
        )
        return _rows(cur)
    finally:
        conn.close()


# ── Price cache ────────────────────────────────────────────────────────────────

def upsert_price(
    symbol: str, asset_type: str, price: float,
    previous_close: float | None, source: str, as_of_date: str,
) -> None:
    fetched_at = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO price_cache "
            "(symbol, asset_type, price, previous_close, currency, source, as_of_date, fetched_at) "
            "VALUES (?, ?, ?, ?, 'USD', ?, ?, ?)",
            (symbol, asset_type, price, previous_close, source, as_of_date, fetched_at),
        )
        cur.execute(
            "INSERT INTO price_history (symbol, asset_type, price, previous_close, as_of_date, source) "
            "SELECT ?, ?, ?, ?, ?, ? WHERE NOT EXISTS "
            "(SELECT 1 FROM price_history WHERE symbol=? AND asset_type=? AND as_of_date=?)",
            (symbol, asset_type, price, previous_close, as_of_date, source, symbol, asset_type, as_of_date),
        )
        conn.commit()
    finally:
        conn.close()


def load_price_cache() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM price_cache")
        return _rows(cur)
    finally:
        conn.close()


def load_price_history() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT symbol, asset_type, price, previous_close, as_of_date "
            "FROM price_history ORDER BY as_of_date"
        )
        return _rows(cur)
    finally:
        conn.close()


# ── Allocation snapshots ───────────────────────────────────────────────────────

def save_allocation_snapshot(payload: dict[str, Any]) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO allocation_snapshots
               (paycheck_amount, run_date, debt_total, food_reserved, debt_reserved,
                savings_reserved, surplus_savings, spending_reserved, crypto_reserved,
                taxable_reserved, roth_reserved, debt_breakdown_json, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload["paycheck_amount"], payload["run_date"], payload["debt_total"],
                payload["food_reserved"], payload["debt_reserved"], payload["savings_reserved"],
                payload.get("surplus_savings", 0.0), payload["spending_reserved"],
                payload["crypto_reserved"], payload["taxable_reserved"], payload["roth_reserved"],
                json.dumps(payload["debt_breakdown"]), json.dumps(payload["meta"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_allocation_snapshots(limit: int = 10) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM allocation_snapshots ORDER BY run_date DESC, id DESC LIMIT ?",
            (limit,),
        )
        return _rows(cur)
    finally:
        conn.close()


# ── Daily reports ──────────────────────────────────────────────────────────────

def save_daily_report(report_date: str, snapshot: dict[str, Any]) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO daily_reports (report_date, snapshot_json) VALUES (?, ?)",
            (report_date, json.dumps(snapshot)),
        )
        conn.commit()
    finally:
        conn.close()


def load_daily_reports(limit: int = 30) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT report_date, snapshot_json FROM daily_reports ORDER BY report_date DESC LIMIT ?",
            (limit,),
        )
        result = []
        for r in cur.fetchall():
            try:
                snap = json.loads(r["snapshot_json"])
                snap["report_date"] = r["report_date"]
                result.append(snap)
            except Exception:
                pass
        return result
    finally:
        conn.close()


def delete_daily_report(report_date: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM daily_reports WHERE report_date = ?", (report_date,))
        conn.commit()
    finally:
        conn.close()


def report_exists(report_date: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS count FROM daily_reports WHERE report_date = ?", (report_date,))
        return bool(int(_one(cur)["count"]))
    finally:
        conn.close()


# ── Journal ────────────────────────────────────────────────────────────────────

def save_journal_entry(entry_date: date, tag: str, body: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO journal_entries (entry_date, tag, body) VALUES (?, ?, ?)",
            (entry_date.strftime(DATE_FMT), tag, body.strip()),
        )
        conn.commit()
    finally:
        conn.close()


def load_journal_entries(limit: int = 50, tag_filter: str = "All") -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if tag_filter == "All":
            cur.execute(
                "SELECT id, entry_date, tag, body FROM journal_entries "
                "ORDER BY entry_date DESC, id DESC LIMIT ?",
                (limit,),
            )
        else:
            cur.execute(
                "SELECT id, entry_date, tag, body FROM journal_entries "
                "WHERE tag = ? ORDER BY entry_date DESC, id DESC LIMIT ?",
                (tag_filter, limit),
            )
        return _rows(cur)
    finally:
        conn.close()


def delete_journal_entry(entry_id: int) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM journal_entries WHERE id = ?", (int(entry_id),))
        conn.commit()
    finally:
        conn.close()


# ── Advisor memory ─────────────────────────────────────────────────────────────

def save_advisor_memory(body: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO advisor_memory (memory_date, body) VALUES (?, ?)",
            (date.today().strftime(DATE_FMT), body.strip()),
        )
        conn.commit()
    finally:
        conn.close()


def load_advisor_memory(limit: int = 50) -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT memory_date, body FROM advisor_memory ORDER BY memory_date DESC, id DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        if not rows:
            return "No memory entries yet."
        return "\n\n".join(f"[{r['memory_date']}]\n{r['body']}" for r in rows)
    finally:
        conn.close()


def load_advisor_memory_list(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, memory_date, body FROM advisor_memory ORDER BY memory_date DESC, id DESC LIMIT ?",
            (limit,),
        )
        return _rows(cur)
    finally:
        conn.close()


def delete_advisor_memory_entry(entry_id: int) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM advisor_memory WHERE id = ?", (int(entry_id),))
        conn.commit()
    finally:
        conn.close()


# ── Advisor conversations ──────────────────────────────────────────────────────

def save_conversation_message(session_id: str, role: str, content: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO advisor_conversations (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()
    finally:
        conn.close()


def load_conversation_history(session_id: str) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM advisor_conversations "
            "WHERE session_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        )
        return [{"role": str(r["role"]), "content": str(r["content"])} for r in cur.fetchall()]
    finally:
        conn.close()


def list_conversation_sessions(limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT session_id,
                      MIN(created_at) AS created_at,
                      (SELECT content FROM advisor_conversations c2
                       WHERE c2.session_id = c1.session_id AND c2.role = 'user'
                       ORDER BY c2.created_at ASC, c2.id ASC LIMIT 1) AS first_message
               FROM advisor_conversations c1
               GROUP BY session_id
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        )
        return _rows(cur)
    finally:
        conn.close()


def delete_conversation_session(session_id: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM advisor_conversations WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


# ── Meridian ───────────────────────────────────────────────────────────────────

def get_spending_summary(period: str = "month") -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if period == "month":
            date_filter = "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == "week":
            date_filter = "date >= date('now', '-7 days')"
        else:
            date_filter = "strftime('%Y', date) = strftime('%Y', 'now')"
        cur.execute(
            f"SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS count "
            f"FROM transactions WHERE type = 'expense' AND {date_filter} "
            f"GROUP BY category ORDER BY total DESC"
        )
        return _rows(cur)
    finally:
        conn.close()


def load_meridian_brain() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT theme, body, cycle FROM meridian_brain "
            "WHERE theme != 'INDEX' ORDER BY theme"
        )
        return _rows(cur)
    except Exception:
        return []
    finally:
        conn.close()


def load_meridian_index() -> str:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT body FROM meridian_brain WHERE theme = 'INDEX' LIMIT 1")
        row = _one(cur)
        return row["body"] if row else ""
    except Exception:
        return ""
    finally:
        conn.close()


def load_meridian_questions(limit: int = 5) -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT generated_date, questions FROM meridian_questions "
            "ORDER BY generated_date DESC LIMIT ?",
            (limit,),
        )
        result = []
        for r in cur.fetchall():
            try:
                result.append({
                    "date": r["generated_date"],
                    "questions": json.loads(r["questions"]),
                })
            except Exception:
                pass
        return result
    except Exception:
        return []
    finally:
        conn.close()
