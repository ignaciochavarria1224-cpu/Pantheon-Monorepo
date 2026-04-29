"""
Phase 5b: Agent Hub
Allows Apollo to spawn and manage persistent sub-agents.
Each agent is a scoped background task with its own prompt, tools, and schedule.
"""
import json
import threading
import schedule
import time
from datetime import datetime
from pathlib import Path
from core.audit import log
from config import APOLLO_DB_PATH
import sqlite3

def get_connection():
    conn = sqlite3.connect(APOLLO_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_hub():
    """Create the agents table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            schedule_expression TEXT,
            tools_allowed TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            last_run TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_agent(name: str, description: str, system_prompt: str,
                 schedule_expr: str, tools_allowed: list) -> int:
    """Register a new sub-agent. Returns the agent ID."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO agents (created_at, name, description, system_prompt,
                           schedule_expression, tools_allowed)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), name, description, system_prompt,
          schedule_expr, json.dumps(tools_allowed)))
    conn.commit()
    agent_id = cur.lastrowid
    conn.close()
    log(f"Created agent: {name} (ID {agent_id})", system="HUB")
    return agent_id

def list_agents() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM agents WHERE active = 1").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def retire_agent(agent_id: int):
    conn = get_connection()
    conn.execute("UPDATE agents SET active = 0 WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()
    log(f"Retired agent ID {agent_id}", system="HUB")

def run_agent(agent: dict):
    """Execute a sub-agent's task."""
    from core.brain import _run_with_tools
    log(f"Running agent: {agent['name']}", system="HUB")
    try:
        messages = [{"role": "user", "content": agent["system_prompt"]}]
        response = _run_with_tools(messages)
        conn = get_connection()
        conn.execute("UPDATE agents SET last_run = ? WHERE id = ?",
                     (datetime.now().isoformat(), agent["id"]))
        conn.commit()
        conn.close()
        log(f"Agent {agent['name']} completed: {response[:100]}", system="HUB")
    except Exception as e:
        log(f"Agent {agent['name']} failed: {e}", system="HUB")

# Initialize the hub table on import
initialize_hub()
