# db/neon_bridge.py — SQLite backend (migrated from Neon PostgreSQL)
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

if not os.environ.get("BLACKBOOK_DB_PATH"):
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except Exception:
        pass

BLACKBOOK_DB_PATH = os.environ.get(
    "BLACKBOOK_DB_PATH",
    str(Path(__file__).resolve().parents[3] / "TBD" / "Pantheon" / "data" / "blackbook.db"),
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(BLACKBOOK_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_tables():
    """Ensure Meridian tables exist (they are created by queries.py init_db)."""
    conn = get_connection()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meridian_brain ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, theme TEXT NOT NULL UNIQUE, "
        "body TEXT NOT NULL, cycle INTEGER, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meridian_questions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, generated_date TEXT NOT NULL, "
        "questions TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    print("  [DB] Tables initialized.")


def pull_new_entries(processed_ids: list) -> list:
    """Pull all journal entries not yet processed by Meridian."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        if processed_ids:
            placeholders = ",".join(["?"] * len(processed_ids))
            cur.execute(
                f"SELECT id, entry_date, tag, body FROM journal_entries "
                f"WHERE id NOT IN ({placeholders}) ORDER BY entry_date ASC",
                processed_ids,
            )
        else:
            cur.execute(
                "SELECT id, entry_date, tag, body FROM journal_entries ORDER BY entry_date ASC"
            )
        return [{"id": r["id"], "entry_date": str(r["entry_date"]), "tag": r["tag"], "body": r["body"]}
                for r in cur.fetchall()]
    except Exception as e:
        print(f"  [DB] Pull failed: {e}")
        return []
    finally:
        conn.close()


def push_questions(questions: list, generated_date: str) -> bool:
    """Push daily adaptive questions to SQLite."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO meridian_questions (generated_date, questions) VALUES (?, ?)",
            (generated_date, json.dumps(questions)),
        )
        conn.commit()
        conn.close()
        print(f"  [DB] Questions pushed for {generated_date}.")
        return True
    except Exception as e:
        print(f"  [DB] Question push failed: {e}")
        return False


def push_framework(title: str, body: str, metadata: dict) -> bool:
    """Push a published framework (stored as a meridian_brain entry)."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO meridian_brain (theme, body, cycle, updated_at) VALUES (?, ?, ?, ?)",
            (f"FRAMEWORK:{title}", body[:5000], metadata.get("cycle", 0), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        print(f"  [DB] Framework '{title}' pushed.")
        return True
    except Exception as e:
        print(f"  [DB] Framework push failed: {e}")
        return False


def push_insight(insight_type: str, body: str, generated_date: str) -> bool:
    """Push a pattern report or insight (stored as meridian_brain entry)."""
    try:
        conn = get_connection()
        theme = f"INSIGHT:{insight_type}:{generated_date}"
        conn.execute(
            "INSERT OR REPLACE INTO meridian_brain (theme, body, cycle, updated_at) VALUES (?, ?, ?, ?)",
            (theme, body[:5000], 0, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        print(f"  [DB] Insight ({insight_type}) pushed.")
        return True
    except Exception as e:
        print(f"  [DB] Insight push failed: {e}")
        return False


def push_vault_snapshot(notes: list, cycle: int) -> bool:
    """Sync all vault notes to SQLite so Pantheon/Apollo can display them."""
    try:
        conn = get_connection()
        conn.execute("DELETE FROM meridian_notes")
        for n in notes:
            fm = n.get("frontmatter", {})
            domains = ",".join(fm.get("domains", []))
            conn.execute(
                "INSERT INTO meridian_notes "
                "(note_id, title, stage, fitness, maturity, domains, body, cycle, synced_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fm.get("id", ""),
                    fm.get("title", n.get("path", "")),
                    fm.get("stage", "seed"),
                    fm.get("fitness"),
                    fm.get("maturity"),
                    domains,
                    n.get("body", "")[:2000],
                    cycle,
                    datetime.now().isoformat(),
                ),
            )
        conn.commit()
        conn.close()
        print(f"  [DB] Vault snapshot pushed: {len(notes)} notes.")
        return True
    except Exception as e:
        print(f"  [DB] Vault snapshot failed: {e}")
        return False


def push_brain_themes(themes: list, index_body: str, cycle: int) -> bool:
    """Push Brain/ theme documents so Pantheon can display them."""
    try:
        conn = get_connection()
        conn.execute("DELETE FROM meridian_brain WHERE theme NOT LIKE 'FRAMEWORK:%' AND theme NOT LIKE 'INSIGHT:%'")
        for t in themes:
            conn.execute(
                "INSERT OR REPLACE INTO meridian_brain (theme, body, cycle, updated_at) VALUES (?, ?, ?, ?)",
                (t["theme"], t["body"][:5000], cycle, datetime.now().isoformat()),
            )
        if index_body:
            conn.execute(
                "INSERT OR REPLACE INTO meridian_brain (theme, body, cycle, updated_at) VALUES (?, ?, ?, ?)",
                ("INDEX", index_body[:5000], cycle, datetime.now().isoformat()),
            )
        conn.commit()
        conn.close()
        print(f"  [DB] Brain pushed: {len(themes)} themes.")
        return True
    except Exception as e:
        print(f"  [DB] Brain push failed: {e}")
        return False


def get_entry_count() -> int:
    try:
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0
