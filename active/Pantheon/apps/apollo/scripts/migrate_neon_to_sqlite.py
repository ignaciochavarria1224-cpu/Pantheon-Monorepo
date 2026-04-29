"""
Migrate BlackBook data from Neon PostgreSQL (CSV export) to SQLite.
Source: CSV files from Pantheon_Backup_2026-04-18/neon_export/
Target: Pantheon/data/blackbook.db

Run once from anywhere:
  python migrate_neon_to_sqlite.py
"""

import csv
import sqlite3
from pathlib import Path

CSV_DIR = Path(r"C:\Users\Ignac\Dropbox\Pantheon_Backup_2026-04-18\neon_export")
DB_PATH = Path(r"C:\Users\Ignac\Dropbox\TBD\Pantheon\data\blackbook.db")

DDL = [
    """CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        account_type TEXT NOT NULL,
        is_debt INTEGER NOT NULL DEFAULT 0,
        include_in_runway INTEGER NOT NULL DEFAULT 1,
        starting_balance REAL NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        current_balance_override REAL DEFAULT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        account_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        to_account_id INTEGER,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        FOREIGN KEY(to_account_id) REFERENCES accounts(id)
    )""",
    """CREATE TABLE IF NOT EXISTS holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        display_name TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        account_id INTEGER NOT NULL,
        amount_invested REAL NOT NULL DEFAULT 0,
        quantity REAL NOT NULL DEFAULT 0,
        avg_price REAL NOT NULL DEFAULT 0,
        coingecko_id TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )""",
    """CREATE TABLE IF NOT EXISTS allocation_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paycheck_amount REAL NOT NULL,
        run_date TEXT NOT NULL,
        debt_total REAL NOT NULL,
        food_reserved REAL NOT NULL,
        debt_reserved REAL NOT NULL,
        savings_reserved REAL NOT NULL,
        surplus_savings REAL NOT NULL DEFAULT 0,
        spending_reserved REAL NOT NULL,
        crypto_reserved REAL NOT NULL,
        taxable_reserved REAL NOT NULL,
        roth_reserved REAL NOT NULL,
        debt_breakdown_json TEXT NOT NULL,
        meta_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS price_cache (
        symbol TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        price REAL NOT NULL,
        previous_close REAL,
        currency TEXT NOT NULL DEFAULT 'USD',
        source TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        fetched_at TEXT NOT NULL,
        PRIMARY KEY(symbol, asset_type)
    )""",
    """CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        price REAL NOT NULL,
        previous_close REAL,
        as_of_date TEXT NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL UNIQUE,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT NOT NULL,
        tag TEXT NOT NULL DEFAULT 'General',
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS advisor_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_date TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS advisor_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS meridian_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        started_at TEXT,
        completed_at TEXT,
        result TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS meridian_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        note_id TEXT NOT NULL,
        title TEXT NOT NULL,
        stage TEXT NOT NULL,
        fitness REAL,
        maturity INTEGER,
        domains TEXT,
        body TEXT,
        cycle INTEGER,
        synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS meridian_brain (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theme TEXT NOT NULL UNIQUE,
        body TEXT NOT NULL,
        cycle INTEGER,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS meridian_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_date TEXT NOT NULL,
        questions TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
]


def _null(v: str):
    return None if v == "" else v


def _int(v: str):
    return None if v == "" else int(float(v))


def _float(v: str):
    return None if v == "" else float(v)


def load_csv(name: str) -> list[dict]:
    path = CSV_DIR / f"{name}.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


DB_PATH.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=OFF")  # off during bulk insert
cur = conn.cursor()

print(f"Creating schema in {DB_PATH}...")
for stmt in DDL:
    cur.execute(stmt)
conn.commit()

# ── accounts ───────────────────────────────────────────────────────────────────
rows = load_csv("accounts")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO accounts (id, name, account_type, is_debt, include_in_runway, "
        "starting_balance, sort_order, current_balance_override, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["name"], r["account_type"],
            _int(r["is_debt"]), _int(r["include_in_runway"]),
            _float(r["starting_balance"]), _int(r["sort_order"]),
            _float(r["current_balance_override"]) if r.get("current_balance_override") else None,
            _null(r.get("created_at", "")),
        ),
    )
print(f"  accounts: {len(rows)} rows")

# ── settings ───────────────────────────────────────────────────────────────────
rows = load_csv("settings")
for r in rows:
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (r["key"], r["value"]))
print(f"  settings: {len(rows)} rows")

# ── transactions ───────────────────────────────────────────────────────────────
rows = load_csv("transactions")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO transactions (id, date, description, category, amount, "
        "account_id, type, to_account_id, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["date"], r["description"], r["category"],
            _float(r["amount"]), _int(r["account_id"]), r["type"],
            _int(r["to_account_id"]) if r.get("to_account_id") else None,
            _null(r.get("notes", "")), _null(r.get("created_at", "")),
        ),
    )
print(f"  transactions: {len(rows)} rows")

# ── holdings ───────────────────────────────────────────────────────────────────
rows = load_csv("holdings")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO holdings (id, symbol, display_name, asset_type, account_id, "
        "amount_invested, quantity, avg_price, coingecko_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["symbol"], r["display_name"], r["asset_type"],
            _int(r["account_id"]), _float(r["amount_invested"]),
            _float(r["quantity"]), _float(r["avg_price"]),
            _null(r.get("coingecko_id", "")),
            _null(r.get("created_at", "")), _null(r.get("updated_at", "")),
        ),
    )
print(f"  holdings: {len(rows)} rows")

# ── price_cache ────────────────────────────────────────────────────────────────
rows = load_csv("price_cache")
for r in rows:
    cur.execute(
        "INSERT OR REPLACE INTO price_cache (symbol, asset_type, price, previous_close, "
        "currency, source, as_of_date, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            r["symbol"], r["asset_type"], _float(r["price"]),
            _float(r.get("previous_close", "")) if r.get("previous_close") else None,
            r.get("currency", "USD"), r["source"], r["as_of_date"], r["fetched_at"],
        ),
    )
print(f"  price_cache: {len(rows)} rows")

# ── price_history ──────────────────────────────────────────────────────────────
rows = load_csv("price_history")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO price_history (id, symbol, asset_type, price, previous_close, "
        "as_of_date, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["symbol"], r["asset_type"], _float(r["price"]),
            _float(r.get("previous_close", "")) if r.get("previous_close") else None,
            r["as_of_date"], r["source"], _null(r.get("created_at", "")),
        ),
    )
print(f"  price_history: {len(rows)} rows")

# ── journal_entries ────────────────────────────────────────────────────────────
rows = load_csv("journal_entries")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO journal_entries (id, entry_date, tag, body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (_int(r["id"]), r["entry_date"], r["tag"], r["body"], _null(r.get("created_at", ""))),
    )
print(f"  journal_entries: {len(rows)} rows")

# ── daily_reports ──────────────────────────────────────────────────────────────
rows = load_csv("daily_reports")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO daily_reports (id, report_date, snapshot_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (_int(r["id"]), r["report_date"], r["snapshot_json"], _null(r.get("created_at", ""))),
    )
print(f"  daily_reports: {len(rows)} rows")

# ── advisor_conversations ──────────────────────────────────────────────────────
rows = load_csv("advisor_conversations")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO advisor_conversations (id, session_id, role, content, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (_int(r["id"]), r["session_id"], r["role"], r["content"], _null(r.get("created_at", ""))),
    )
print(f"  advisor_conversations: {len(rows)} rows")

# ── meridian_notes ────────────────────────────────────────────────────────────
rows = load_csv("meridian_notes")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO meridian_notes (id, note_id, title, stage, fitness, maturity, "
        "domains, body, cycle, synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["note_id"], r["title"], r["stage"],
            _float(r.get("fitness", "")) if r.get("fitness") else None,
            _int(r.get("maturity", "")) if r.get("maturity") else None,
            _null(r.get("domains", "")), _null(r.get("body", "")),
            _int(r.get("cycle", "")) if r.get("cycle") else None,
            _null(r.get("synced_at", "")),
        ),
    )
print(f"  meridian_notes: {len(rows)} rows")

# ── meridian_jobs ──────────────────────────────────────────────────────────────
rows = load_csv("meridian_jobs")
for r in rows:
    cur.execute(
        "INSERT OR IGNORE INTO meridian_jobs (id, status, requested_at, started_at, completed_at, result) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            _int(r["id"]), r["status"], _null(r.get("requested_at", "")),
            _null(r.get("started_at", "")), _null(r.get("completed_at", "")),
            _null(r.get("result", "")),
        ),
    )
print(f"  meridian_jobs: {len(rows)} rows")

conn.commit()
conn.execute("PRAGMA foreign_keys=ON")

# Verify
total = 0
for tbl in ["accounts", "transactions", "holdings", "price_cache", "price_history",
            "settings", "journal_entries", "daily_reports", "advisor_conversations",
            "meridian_notes", "meridian_jobs"]:
    count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    total += count

conn.close()
print(f"\nDone. {total} total rows in {DB_PATH}")
