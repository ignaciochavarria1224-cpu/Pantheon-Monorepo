import sqlite3
import json
from datetime import datetime
from config import APOLLO_DB_PATH

def get_connection():
    conn = sqlite3.connect(APOLLO_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            intent TEXT,
            system_used TEXT,
            channel TEXT DEFAULT 'ui'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            decision TEXT NOT NULL,
            reasoning TEXT,
            domain TEXT,
            outcome TEXT,
            tags TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            confidence REAL,
            data_points INTEGER,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS action_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queued_at TEXT NOT NULL,
            target_system TEXT NOT NULL,
            action_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            retries INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action_type TEXT NOT NULL UNIQUE,
            scope TEXT NOT NULL,
            expires_at TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            audit_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            message TEXT NOT NULL,
            provider_used TEXT,
            model_name TEXT,
            grounded INTEGER DEFAULT 0,
            degraded INTEGER DEFAULT 0,
            latency_ms INTEGER,
            subsystems_json TEXT,
            error_reason TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("Apollo database initialized.")

# --- Conversation Functions ---

def log_conversation(role: str, content: str, intent: str = None,
                     system_used: str = None, channel: str = "ui"):
    conn = get_connection()
    conn.execute("""
        INSERT INTO conversations (timestamp, role, content, intent, system_used, channel)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), role, content, intent, system_used, channel))
    conn.commit()
    conn.close()

def get_recent_conversations(limit: int = 20) -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Decision Functions ---

def log_decision(decision: str, reasoning: str = None, domain: str = None, tags: list = None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO decisions (timestamp, decision, reasoning, domain, tags)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), decision, reasoning, domain, json.dumps(tags or [])))
    conn.commit()
    conn.close()

def get_decisions(domain: str = None, limit: int = 50) -> list:
    conn = get_connection()
    if domain:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE domain = ? ORDER BY timestamp DESC LIMIT ?",
            (domain, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Pattern Functions ---

def save_pattern(pattern_type: str, description: str, confidence: float, data_points: int):
    conn = get_connection()
    conn.execute("UPDATE patterns SET active = 0 WHERE pattern_type = ?", (pattern_type,))
    conn.execute("""
        INSERT INTO patterns (detected_at, pattern_type, description, confidence, data_points)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), pattern_type, description, confidence, data_points))
    conn.commit()
    conn.close()

def get_active_patterns() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM patterns WHERE active = 1 ORDER BY confidence DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Queue Functions ---

def queue_action(target_system: str, action_type: str, payload: dict):
    conn = get_connection()
    conn.execute("""
        INSERT INTO action_queue (queued_at, target_system, action_type, payload)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(), target_system, action_type, json.dumps(payload)))
    conn.commit()
    conn.close()

def get_pending_queue() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM action_queue WHERE status = 'pending' ORDER BY queued_at ASC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Approval Rule Functions ---

def set_approval_rule(action_type: str, scope: str, expires_at: str = None):
    """Save an 'always allow' or session rule for an action type."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO approval_rules (created_at, action_type, scope, expires_at, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(action_type) DO UPDATE SET
            scope = excluded.scope,
            expires_at = excluded.expires_at,
            active = 1,
            created_at = excluded.created_at
    """, (datetime.now().isoformat(), action_type, scope, expires_at))
    conn.commit()
    conn.close()

def get_approval_rule(action_type: str) -> dict | None:
    """Check if a permanent approval rule exists for an action type."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM approval_rules
        WHERE action_type = ? AND active = 1 AND scope = 'permanent'
    """, (action_type,)).fetchone()
    conn.close()
    return dict(row) if row else None

def clear_session_rules():
    """Call this at the start of each new session to clear 'just this once' rules."""
    conn = get_connection()
    conn.execute("UPDATE approval_rules SET active = 0 WHERE scope = 'session'")
    conn.commit()
    conn.close()


def save_request_trace(
    audit_id: str,
    channel: str,
    message: str,
    provider_used: str | None,
    model_name: str | None,
    grounded: bool,
    degraded: bool,
    latency_ms: int | None,
    subsystems: list[str],
    error_reason: str | None = None,
):
    conn = get_connection()
    conn.execute("""
        INSERT INTO request_traces (
            timestamp, audit_id, channel, message, provider_used, model_name,
            grounded, degraded, latency_ms, subsystems_json, error_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        audit_id,
        channel,
        message,
        provider_used,
        model_name,
        1 if grounded else 0,
        1 if degraded else 0,
        latency_ms,
        json.dumps(subsystems),
        error_reason,
    ))
    conn.commit()
    conn.close()


def get_recent_traces(limit: int = 25) -> list:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM request_traces ORDER BY timestamp DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    results = []
    for row in rows:
        item = dict(row)
        try:
            item["subsystems"] = json.loads(item.get("subsystems_json") or "[]")
        except Exception:
            item["subsystems"] = []
        results.append(item)
    return results

if __name__ == "__main__":
    initialize_database()
