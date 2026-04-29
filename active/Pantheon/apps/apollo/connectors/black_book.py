import sqlite3
from datetime import date
from config import BLACKBOOK_DB_PATH
from core.audit import log


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(BLACKBOOK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _resolve_account_id(cur, account_name: str) -> int | None:
    cur.execute("SELECT id FROM accounts WHERE LOWER(name) = LOWER(?)", (account_name,))
    row = cur.fetchone()
    return row["id"] if row else None


def _get_all_accounts(cur) -> list:
    cur.execute("SELECT id, name FROM accounts ORDER BY sort_order")
    return cur.fetchall()


def add_expense(amount: float, description: str, category: str,
                account: str, date_str: str = None) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        account_id = _resolve_account_id(cur, account)
        if account_id is None:
            names = [a["name"] for a in _get_all_accounts(cur)]
            conn.close()
            return {"success": False, "error": f"Account '{account}' not found. Available: {names}"}
        cur.execute(
            "INSERT INTO transactions (date, description, category, amount, account_id, type) "
            "VALUES (?, ?, ?, ?, ?, 'expense')",
            (date_str or date.today().isoformat(), description, category, amount, account_id),
        )
        conn.commit()
        conn.close()
        log(f"Added expense ${amount} - {description} [{category}]", system="BLACK_BOOK")
        return {"success": True}
    except Exception as e:
        log(f"DB error: {e}", system="BLACK_BOOK")
        return {"success": False, "error": str(e)}


def add_income(amount: float, description: str, account: str, date_str: str = None) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        account_id = _resolve_account_id(cur, account)
        if account_id is None:
            names = [a["name"] for a in _get_all_accounts(cur)]
            conn.close()
            return {"success": False, "error": f"Account '{account}' not found. Available: {names}"}
        cur.execute(
            "INSERT INTO transactions (date, description, category, amount, account_id, type) "
            "VALUES (?, ?, 'Income', ?, ?, 'income')",
            (date_str or date.today().isoformat(), description, amount, account_id),
        )
        conn.commit()
        conn.close()
        log(f"Added income ${amount} - {description}", system="BLACK_BOOK")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recent_transactions(limit: int = 20) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT t.id, t.date, t.description, t.category, t.amount, t.type, t.notes,
                      a.name as account_name
               FROM transactions t
               JOIN accounts a ON a.id = t.account_id
               ORDER BY t.date DESC, t.id DESC
               LIMIT ?""",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"success": True, "data": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_spending_summary(period: str = "month") -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        if period == "month":
            date_filter = "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')"
        elif period == "week":
            date_filter = "date >= date('now', '-7 days')"
        else:  # year
            date_filter = "strftime('%Y', date) = strftime('%Y', 'now')"
        cur.execute(
            f"""SELECT category,
                       ROUND(SUM(amount), 2) AS total,
                       COUNT(*) AS count
                FROM transactions
                WHERE type = 'expense' AND {date_filter}
                GROUP BY category
                ORDER BY total DESC"""
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"success": True, "data": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_account_balances() -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT
                   a.name,
                   a.account_type,
                   a.is_debt,
                   ROUND((
                       a.starting_balance +
                       COALESCE(SUM(
                           CASE
                               WHEN t.type = 'income'   THEN  t.amount
                               WHEN t.type = 'expense'  THEN -t.amount
                               WHEN t.type = 'transfer' AND t.to_account_id = a.id THEN  t.amount
                               WHEN t.type = 'transfer' AND t.account_id   = a.id THEN -t.amount
                               ELSE 0
                           END
                       ), 0)
                   ), 2) AS balance
               FROM accounts a
               LEFT JOIN transactions t
                   ON t.account_id = a.id OR t.to_account_id = a.id
               GROUP BY a.id, a.name, a.account_type, a.is_debt, a.starting_balance
               ORDER BY a.sort_order"""
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"success": True, "data": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_category_average(category: str) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT AVG(weekly_total) AS avg_weekly FROM (
                   SELECT strftime('%Y-%W', date) AS week,
                          SUM(amount) AS weekly_total
                   FROM transactions
                   WHERE type = 'expense'
                     AND category = ?
                     AND date >= date('now', '-12 weeks')
                   GROUP BY week
               ) weekly_sums""",
            (category,),
        )
        row = cur.fetchone()
        conn.close()
        return {"success": True, "avg_weekly": float(row["avg_weekly"] or 0)}
    except Exception as e:
        return {"success": False, "error": str(e)}
