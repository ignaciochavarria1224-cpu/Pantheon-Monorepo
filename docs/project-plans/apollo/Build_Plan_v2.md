# Project Apollo — Full System Build Plan

### Every Step. Every Phase. No Skipping.

> **Your Stack:** Python · FastAPI · Reflex (UI) · Anthropic API · SQLite · ChromaDB · faster-whisper · Windows

---

## PART 0: Technology Decisions

Before touching any code, understand what you are building and why each tool was chosen.

### The Full Stack

| Component            | Tool                        | Why                                                                                |
|----------------------|-----------------------------|------------------------------------------------------------------------------------|
| **Language**         | Python                      | Black Book is already Python. One language across everything.                      |
| **Backend API**      | FastAPI                     | Lightweight, fast, easy to build routes and function calls                         |
| **Chat UI**          | Reflex                      | You already know it from Black Book                                                |
| **LLM Brain**        | Anthropic API (Claude)      | Private (no training on API data), cheap (~$1-3/month personal use), no GPU needed |
| **Apollo Memory DB** | SQLite                      | Free, local, no server, stores conversations/decisions/patterns/approval rules     |
| **Vector Search**    | ChromaDB                    | Free, local, Python-native, powers RAG search over your vaults                    |
| **Voice Input**      | faster-whisper (tiny model) | Runs on CPU, free, offline, no data leaves your machine                            |
| **WhatsApp Bridge**  | whatsapp-web.js (Node.js)   | Open-source; lets you message Apollo from anywhere without a dedicated app         |
| **Obsidian Access**  | Direct file system          | Markdown files — no plugin needed, just read/write .md files                       |
| **Black Book**       | Direct Neon DB connection   | Apollo reads/writes the shared Postgres DB directly                                |
| **Olympus**          | Read JSON file              | Apex exports a status file; Apollo reads it                                        |

### Apollo's Folder Structure (end goal)

```
C:\Apollo\
├── main.py                  # FastAPI app entry point
├── config.py                # All settings and API keys
├── .env                     # Secret keys (never commit this)
├── requirements.txt         # All Python packages
│
├── core\
│   ├── brain.py             # Anthropic LLM client and reasoning
│   ├── intent.py            # Classifies what user wants to do
│   ├── functions.py         # All callable functions (the tools Apollo can use)
│   ├── memory.py            # Reads/writes to Apollo's SQLite database
│   ├── executor.py          # Executes function calls from the LLM
│   ├── mind.py              # Manages the Apollo Mind Vault
│   ├── patterns.py          # Detects behavioral patterns
│   └── triggers.py          # Cross-system trigger engine (Phase 4)
│
├── connectors\
│   ├── black_book.py        # All calls to Black Book (via shared Neon DB)
│   ├── meridian.py          # All reads/writes to Obsidian vault
│   └── olympus.py           # Reads Olympus/Apex status file
│
├── search\
│   ├── indexer.py           # Builds ChromaDB indexes from your vaults
│   └── retriever.py         # Queries ChromaDB to find relevant content
│
├── voice\
│   └── transcriber.py       # faster-whisper speech to text
│
├── agents\
│   ├── brief.py             # Daily Brief agent (scheduled)
│   └── hub.py               # Phase 5b: sub-agent spawning and management
│
├── channels\
│   └── whatsapp.py          # WhatsApp bridge integration
│
├── ui\
│   └── app.py               # Reflex chat interface
│
├── data\
│   ├── apollo.db            # SQLite database (Apollo's memory)
│   ├── chroma\              # ChromaDB vector store files
│   └── queue\               # Offline action queue (when systems are down)
│
├── mind_vault\              # Apollo's own Obsidian-style vault
│   ├── self_model.md        # Updated model of who you are
│   ├── mental_models\       # Your thinking frameworks
│   ├── decisions\           # Decision log notes
│   └── patterns\            # Detected behavioral patterns
│
└── logs\
    └── apollo_audit.log     # Every action Apollo takes, timestamped
```

---

## PART 1: Environment Setup

### Step 1.1 — Install Python

1. Go to `https://www.python.org/downloads/`
2. Download Python **3.11** (not 3.12 — some packages have issues with 3.12)
3. Run the installer
4. **CRITICAL:** On the first screen, check **"Add Python to PATH"** before clicking Install
5. Open a new Command Prompt (Win + R → `cmd` → Enter)
6. Type: `python --version`
7. You should see: `Python 3.11.x`

### Step 1.2 — Install Git

1. Go to `https://git-scm.com/download/win`
2. Download and run the installer, accept all defaults
3. In Command Prompt, type: `git --version`

### Step 1.3 — Install Node.js (required for WhatsApp bridge)

1. Go to `https://nodejs.org/`
2. Download the **LTS** version and install it
3. In Command Prompt, type: `node --version`
4. You should see a version number like `v20.x.x`

### Step 1.4 — Create the Project Folder

```
cd C:\
mkdir Apollo
cd Apollo
```

### Step 1.5 — Create a Virtual Environment

```
python -m venv venv
venv\Scripts\activate
```

You will see `(venv)` at the start of your prompt. **Every time you work on Apollo, activate this environment first.**

### Step 1.6 — Install All Python Dependencies

```
pip install fastapi uvicorn anthropic chromadb faster-whisper python-dotenv requests sqlalchemy aiofiles watchdog reflex psycopg2-binary schedule
```

### Step 1.7 — Create Your .env File

```
echo. > .env
notepad .env
```

Add this content:

```
ANTHROPIC_API_KEY=your_key_here
BLACK_BOOK_DB_URL=postgresql://user:password@host.neon.tech/dbname
MERIDIAN_VAULT_PATH=C:\path\to\your\obsidian\vault
OLYMPUS_STATUS_PATH=C:\path\to\olympus\status.json
APOLLO_MIND_VAULT_PATH=C:\Apollo\mind_vault
WHATSAPP_BRIDGE_PORT=3001
BRIEF_DELIVERY_TIME=07:00
```

Replace each value with your actual paths and credentials.

### Step 1.8 — Get Your Anthropic API Key

1. Go to `https://console.anthropic.com`
2. Create an account or sign in
3. Go to **API Keys** → **Create Key**
4. Paste the key into your `.env` file
5. Add $5 credit to start — this lasts months for personal use

### Step 1.9 — Create the Folder Structure

```
mkdir core connectors search voice agents channels ui data data\chroma data\queue mind_vault mind_vault\mental_models mind_vault\decisions mind_vault\patterns logs
```

### Step 1.10 — Create config.py

Create `C:\Apollo\config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# System connections
BLACK_BOOK_DB_URL = os.getenv("BLACK_BOOK_DB_URL")
MERIDIAN_VAULT_PATH = os.getenv("MERIDIAN_VAULT_PATH")
OLYMPUS_STATUS_PATH = os.getenv("OLYMPUS_STATUS_PATH")
APOLLO_MIND_VAULT_PATH = os.getenv("APOLLO_MIND_VAULT_PATH", r"C:\Apollo\mind_vault")

# Apollo internals
APOLLO_DB_PATH = r"C:\Apollo\data\apollo.db"
CHROMA_PATH = r"C:\Apollo\data\chroma"
AUDIT_LOG_PATH = r"C:\Apollo\logs\apollo_audit.log"
QUEUE_PATH = r"C:\Apollo\data\queue"

# Channels
WHATSAPP_BRIDGE_PORT = int(os.getenv("WHATSAPP_BRIDGE_PORT", "3001"))
BRIEF_DELIVERY_TIME = os.getenv("BRIEF_DELIVERY_TIME", "07:00")

# LLM settings
PRIMARY_MODEL = "claude-opus-4-5"
FAST_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
```

### Step 1.11 — Test Your Setup

Create `C:\Apollo\test_setup.py`:

```python
import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say: Apollo setup confirmed."}]
)
print(message.content[0].text)
```

Run: `python test_setup.py`

If you see `Apollo setup confirmed.` — your environment works. Delete the test file.

---

## PART 2: Apollo's Memory Database

### Step 2.1 — Create the Database Schema

Create `C:\Apollo\core\memory.py`:

```python
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
            channel TEXT DEFAULT 'ui'   -- 'ui', 'whatsapp', 'voice', 'brief'
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

    # Session approval rules — remembers what you've said "always allow" to
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action_type TEXT NOT NULL UNIQUE,  -- e.g. 'add_expense', 'log_journal_entry'
            scope TEXT NOT NULL,               -- 'session' or 'permanent'
            expires_at TEXT,                   -- NULL for permanent
            active INTEGER DEFAULT 1
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

if __name__ == "__main__":
    initialize_database()
```

### Step 2.2 — Initialize the Database

```
python core/memory.py
```

You should see: `Apollo database initialized.`

Verify that `C:\Apollo\data\apollo.db` now exists.

---

## PART 3: The Audit Logger

Create `C:\Apollo\core\audit.py`:

```python
from datetime import datetime
from config import AUDIT_LOG_PATH

def log(action: str, detail: str = None, system: str = None):
    """Write a permanent record of every action Apollo takes."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_tag = f" [{system}]" if system else ""
    detail_tag = f" — {detail}" if detail else ""
    entry = f"{timestamp}{system_tag} — {action}{detail_tag}\n"
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"[AUDIT]{system_tag} {action}{detail_tag}")
```

---

## PART 4: The Connectors

**Do not write any connector code yet.** Complete Step 4.0 first.

### Step 4.0 — System Discovery

Open each codebase and answer the questions below before writing a single line of connector code.

#### Black Book Discovery

Since Black Book uses Neon Postgres, you need three things:

1. **The exact connection string** — find it in Black Book's `.env` or `config.py`. It looks like `postgresql://user:pass@host.neon.tech/dbname`.
2. **The table names** — search for `CREATE TABLE`, `class Transaction`, `class Expense`, or SQLAlchemy model definitions. Write down every table name.
3. **The column names** — for each table, write down every column. These are what Apollo will query and insert into.

#### Meridian Discovery

1. What is the exact path to run the Meridian script?
2. What is your Obsidian vault path? (Obsidian Settings → About)
3. What is the filename format of your daily notes? (e.g. `2026-04-13.md`)

#### Olympus Discovery

1. Does Apex already write a status JSON file? If so, where?
2. If not, you will add the export function in Step 4.3.
3. What columns does Olympus use for PnL, positions, and alerts?

---

### Step 4.1 — Black Book Connector (Neon Direct)

Since Black Book uses Neon, Apollo reads the database directly — no HTTP calls needed.

```
pip install psycopg2-binary
```

Create `C:\Apollo\connectors\black_book.py`:

```python
import psycopg2
import psycopg2.extras
from datetime import date
from config import BLACK_BOOK_DB_URL
from core.audit import log

def get_connection():
    return psycopg2.connect(BLACK_BOOK_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def add_expense(amount: float, description: str, category: str,
                account: str, date_str: str = None) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        # UPDATE table and column names to match your actual schema
        cur.execute("""
            INSERT INTO transactions (amount, description, category, account, date, type)
            VALUES (%s, %s, %s, %s, %s, 'expense')
        """, (amount, description, category, account, date_str or date.today().isoformat()))
        conn.commit()
        cur.close(); conn.close()
        log(f"Added expense ${amount} — {description}", system="BLACK_BOOK")
        return {"success": True}
    except Exception as e:
        log(f"DB error: {e}", system="BLACK_BOOK")
        return {"success": False, "error": str(e)}

def add_income(amount: float, description: str, account: str, date_str: str = None) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (amount, description, account, date, type)
            VALUES (%s, %s, %s, %s, 'income')
        """, (amount, description, account, date_str or date.today().isoformat()))
        conn.commit()
        cur.close(); conn.close()
        log(f"Added income ${amount} — {description}", system="BLACK_BOOK")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_recent_transactions(limit: int = 20) -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM transactions ORDER BY date DESC, id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_spending_summary(period: str = "month") -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        if period == "month":
            date_filter = "DATE_TRUNC('month', date) = DATE_TRUNC('month', CURRENT_DATE)"
        elif period == "week":
            date_filter = "date >= CURRENT_DATE - INTERVAL '7 days'"
        else:
            date_filter = "DATE_TRUNC('year', date) = DATE_TRUNC('year', CURRENT_DATE)"
        cur.execute(f"""
            SELECT category, SUM(amount) as total, COUNT(*) as count
            FROM transactions
            WHERE type = 'expense' AND {date_filter}
            GROUP BY category ORDER BY total DESC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_account_balances() -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT account,
                   SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as balance
            FROM transactions GROUP BY account
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {"success": True, "data": [dict(r) for r in rows]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_category_average(category: str) -> dict:
    """Get the weekly average spend for a category (used by trigger engine)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT AVG(weekly_total) as avg_weekly FROM (
                SELECT DATE_TRUNC('week', date) as week, SUM(amount) as weekly_total
                FROM transactions
                WHERE type = 'expense' AND category = %s
                  AND date >= CURRENT_DATE - INTERVAL '12 weeks'
                GROUP BY week
            ) weekly_sums
        """, (category,))
        row = cur.fetchone()
        cur.close(); conn.close()
        return {"success": True, "avg_weekly": float(row["avg_weekly"] or 0)}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**After pasting:** Update every `FROM transactions` and every column name to match your actual Neon schema.

### Step 4.2 — Meridian Connector

Create `C:\Apollo\connectors\meridian.py`:

```python
import os
import subprocess
from datetime import datetime, date
from pathlib import Path
from config import MERIDIAN_VAULT_PATH
from core.audit import log

def _get_vault_path() -> Path:
    return Path(MERIDIAN_VAULT_PATH)

def get_daily_note(target_date: date = None) -> dict:
    target = target_date or date.today()
    possible_names = [
        f"{target.strftime('%Y-%m-%d')}.md",
        f"{target.strftime('%Y%m%d')}.md",
        f"{target.strftime('%B %d, %Y')}.md",
    ]
    vault = _get_vault_path()
    for name in possible_names:
        matches = list(vault.rglob(name))
        if matches:
            content = matches[0].read_text(encoding="utf-8")
            log(f"Read daily note: {name}", system="MERIDIAN")
            return {"success": True, "content": content, "path": str(matches[0])}
    return {"success": False, "error": f"No daily note found for {target}"}

def append_to_daily_note(content: str, target_date: date = None) -> dict:
    target = target_date or date.today()
    vault = _get_vault_path()
    daily_folder = vault / "Daily Notes"
    daily_folder.mkdir(exist_ok=True)
    note_path = daily_folder / f"{target.strftime('%Y-%m-%d')}.md"
    timestamp = datetime.now().strftime("%H:%M")
    entry = f"\n## {timestamp}\n{content}\n"
    with open(note_path, "a", encoding="utf-8") as f:
        f.write(entry)
    log(f"Appended to daily note: {note_path.name}", system="MERIDIAN")
    return {"success": True, "path": str(note_path)}

def queue_meridian_prompt(prompt: str, target_date: date = None) -> dict:
    """
    Add a triggered reflection prompt to tomorrow's Meridian question cycle.
    Apollo calls this when a cross-system trigger fires.
    """
    target = target_date or date.today()
    vault = _get_vault_path()
    # Write to a special Apollo-triggers file that Meridian reads
    triggers_folder = vault / "Apollo Triggers"
    triggers_folder.mkdir(exist_ok=True)
    trigger_file = triggers_folder / f"{target.strftime('%Y-%m-%d')}-triggers.md"
    entry = f"- {prompt}\n"
    with open(trigger_file, "a", encoding="utf-8") as f:
        f.write(entry)
    log(f"Queued Meridian prompt: {prompt[:80]}", system="MERIDIAN")
    return {"success": True}

def create_note(title: str, content: str, folder: str = None) -> dict:
    vault = _get_vault_path()
    target_folder = vault / folder if folder else vault
    target_folder.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    note_path = target_folder / f"{safe_title}.md"
    note_path.write_text(content, encoding="utf-8")
    log(f"Created note: {safe_title}.md", system="MERIDIAN")
    return {"success": True, "path": str(note_path)}

def search_vault(query: str, limit: int = 10) -> list:
    vault = _get_vault_path()
    results = []
    query_lower = query.lower()
    for md_file in vault.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                idx = content.lower().find(query_lower)
                start = max(0, idx - 100)
                end = min(len(content), idx + 200)
                snippet = content[start:end].replace("\n", " ").strip()
                results.append({
                    "file": md_file.name,
                    "path": str(md_file),
                    "snippet": f"...{snippet}...",
                    "modified": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
                })
                if len(results) >= limit:
                    break
        except Exception:
            continue
    log(f"Searched vault for: '{query}' — found {len(results)} results", system="MERIDIAN")
    return results

def get_all_notes_metadata() -> list:
    vault = _get_vault_path()
    notes = []
    for md_file in vault.rglob("*.md"):
        try:
            notes.append({
                "name": md_file.name,
                "path": str(md_file),
                "size": md_file.stat().st_size,
                "modified": datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
            })
        except Exception:
            continue
    return notes

def trigger_meridian_cycle() -> dict:
    meridian_script = Path(MERIDIAN_VAULT_PATH).parent / "meridian_cycle.py"
    if not meridian_script.exists():
        return {"success": False, "error": f"Meridian script not found at {meridian_script}"}
    try:
        result = subprocess.run(
            ["python", str(meridian_script)],
            capture_output=True, text=True, timeout=60
        )
        log("Triggered Meridian question cycle", system="MERIDIAN")
        return {"success": True, "output": result.stdout, "errors": result.stderr}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Meridian cycle timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### Step 4.3 — Olympus Connector

Create `C:\Apollo\connectors\olympus.py`:

```python
import json
from datetime import datetime
from pathlib import Path
from config import OLYMPUS_STATUS_PATH
from core.audit import log

def read_status() -> dict:
    path = Path(OLYMPUS_STATUS_PATH)
    if not path.exists():
        return {"success": False, "error": "Olympus status file not found. Is Apex running?"}
    age_minutes = (datetime.now().timestamp() - path.stat().st_mtime) / 60
    try:
        with open(path, "r") as f:
            data = json.load(f)
        data["file_age_minutes"] = round(age_minutes, 1)
        data["is_stale"] = age_minutes > 10
        log("Read Olympus status file", system="OLYMPUS")
        return {"success": True, "data": data}
    except json.JSONDecodeError:
        return {"success": False, "error": "Olympus status file is malformed JSON"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_pnl_summary() -> dict:
    result = read_status()
    if not result["success"]:
        return result
    data = result["data"]
    summary = {
        "daily_pnl": data.get("daily_pnl", "N/A"),
        "total_pnl": data.get("total_pnl", "N/A"),
        "open_positions": data.get("positions", []),
        "position_count": len(data.get("positions", [])),
        "alerts": data.get("alerts", []),
        "last_updated": data.get("timestamp", "Unknown"),
        "is_stale": data.get("is_stale", False)
    }
    return {"success": True, "summary": summary}

def get_drawdown_pct() -> float | None:
    """Return current drawdown percentage for trigger evaluation."""
    result = read_status()
    if not result["success"]:
        return None
    return result["data"].get("drawdown_pct", None)
```

**Add to Olympus/Apex** — run this on a timer every minute:

```python
import json
from datetime import datetime

def export_status():
    status = {
        "timestamp": datetime.now().isoformat(),
        "daily_pnl": get_daily_pnl(),
        "total_pnl": get_total_pnl(),
        "positions": get_open_positions(),
        "alerts": get_active_alerts(),
        "drawdown_pct": get_current_drawdown_pct()
    }
    with open(r"C:\path\to\olympus\status.json", "w") as f:
        json.dump(status, f)
```

### Step 4.4 — Test All Connectors

Create `C:\Apollo\test_connectors.py`:

```python
from connectors.black_book import get_account_balances
from connectors.meridian import search_vault
from connectors.olympus import get_pnl_summary

print("=== Testing Black Book ===")
print(get_account_balances())

print("\n=== Testing Meridian ===")
for r in search_vault("journal", limit=2):
    print(f"  {r['file']} — {r['snippet'][:60]}...")

print("\n=== Testing Olympus ===")
print(get_pnl_summary())
```

Fix any errors before continuing. The connectors must work before building the brain.

---

## PART 5: The Vector Search Engine

### Step 5.1 — Create the Indexer

Create `C:\Apollo\search\indexer.py`:

```python
import chromadb
from pathlib import Path
from connectors.meridian import get_all_notes_metadata
from config import CHROMA_PATH
from core.audit import log

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

def get_or_create_collection(name: str):
    return get_chroma_client().get_or_create_collection(name)

def index_meridian_vault():
    collection = get_or_create_collection("meridian_vault")
    notes = get_all_notes_metadata()
    indexed = skipped = 0
    for note in notes:
        try:
            content = Path(note["path"]).read_text(encoding="utf-8")
            if len(content.strip()) < 50:
                skipped += 1
                continue
            chunks = chunk_text(content, chunk_size=500, overlap=50)
            for i, chunk in enumerate(chunks):
                collection.upsert(
                    ids=[f"{note['name']}__chunk_{i}"],
                    documents=[chunk],
                    metadatas=[{
                        "source": note["name"],
                        "path": note["path"],
                        "modified": note["modified"],
                        "chunk_index": i
                    }]
                )
            indexed += 1
        except Exception as e:
            skipped += 1
    log(f"Indexed Meridian vault: {indexed} notes, {skipped} skipped", system="SEARCH")
    return {"indexed": indexed, "skipped": skipped}

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks

def index_decisions():
    from core.memory import get_decisions
    collection = get_or_create_collection("decisions")
    for d in get_decisions(limit=1000):
        text = f"Decision: {d['decision']}\nReasoning: {d.get('reasoning', '')}"
        collection.upsert(
            ids=[f"decision_{d['id']}"],
            documents=[text],
            metadatas={"timestamp": d["timestamp"], "domain": d.get("domain", "general")}
        )
    log("Indexed decisions", system="SEARCH")

if __name__ == "__main__":
    print("Indexing Meridian vault...")
    print(index_meridian_vault())
    print("Indexing decisions...")
    index_decisions()
    print("Done.")
```

### Step 5.2 — Create the Retriever

Create `C:\Apollo\search\retriever.py`:

```python
from search.indexer import get_or_create_collection
from core.audit import log

def search_meridian(query: str, n_results: int = 5) -> list:
    collection = get_or_create_collection("meridian_vault")
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "content": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "path": results["metadatas"][0][i]["path"],
                "relevance": 1 - results["distances"][0][i]
            })
        log(f"Semantic search: '{query}' — {len(formatted)} results", system="SEARCH")
        return formatted
    except Exception as e:
        log(f"Search failed: {e}", system="SEARCH")
        return []

def search_decisions(query: str, n_results: int = 5) -> list:
    collection = get_or_create_collection("decisions")
    try:
        results = collection.query(query_texts=[query], n_results=n_results)
        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "content": results["documents"][0][i],
                "timestamp": results["metadatas"][0][i]["timestamp"],
                "domain": results["metadatas"][0][i]["domain"]
            })
        return formatted
    except Exception:
        return []
```

### Step 5.3 — Build the Initial Index

```
python search/indexer.py
```

---

## PART 6: Apollo's Brain (The LLM Core)

### Step 6.1 — Define Apollo's Function Toolkit

Create `C:\Apollo\core\functions.py`:

```python
APOLLO_TOOLS = [
    {
        "name": "add_expense",
        "description": "Record a new expense in Black Book. Use when the user mentions spending money, buying something, or paying for something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "description": {"type": "string"},
                "category": {"type": "string", "description": "Food, Health, Transport, Entertainment, Shopping, Bills, Other"},
                "account": {"type": "string", "description": "checking, savings, credit card, cash"},
                "date": {"type": "string", "description": "YYYY-MM-DD. Omit for today."}
            },
            "required": ["amount", "description", "category", "account"]
        }
    },
    {
        "name": "add_income",
        "description": "Record income in Black Book.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "description": {"type": "string"},
                "account": {"type": "string"},
                "date": {"type": "string"}
            },
            "required": ["amount", "description", "account"]
        }
    },
    {
        "name": "log_journal_entry",
        "description": "Write a journal entry to today's Meridian daily note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "log_decision",
        "description": "Record a decision with reasoning. Use when user says they decided something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "reasoning": {"type": "string"},
                "domain": {"type": "string", "description": "finance, trading, personal, career, health, other"}
            },
            "required": ["decision"]
        }
    },
    {
        "name": "get_spending_summary",
        "description": "Get a spending summary from Black Book.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "week, month, or year"}
            },
            "required": ["period"]
        }
    },
    {
        "name": "get_account_balances",
        "description": "Get current account balances from Black Book.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_meridian",
        "description": "Search the Meridian vault for journal entries, notes, or any content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_results": {"type": "integer"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_olympus_status",
        "description": "Get Olympus/Apex trading status including PnL, positions, and alerts.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "trigger_meridian_cycle",
        "description": "Run the Meridian question generation cycle.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_morning_briefing",
        "description": "Get a full morning briefing combining all system statuses.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_past_decisions",
        "description": "Search through past decisions for relevant context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "queue_meridian_prompt",
        "description": "Add a reflection prompt to tomorrow's Meridian journal cycle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The question or reflection prompt to add"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "set_approval_rule",
        "description": "Remember that the user has approved an action type. Use when user says 'always allow' or 'just this once'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "description": "The function name being approved"},
                "scope": {"type": "string", "description": "'permanent' for 'always allow', 'session' for 'just this once'"}
            },
            "required": ["action_type", "scope"]
        }
    }
]
```

### Step 6.2 — Create the Function Executor

Create `C:\Apollo\core\executor.py`:

```python
from connectors.black_book import (
    add_expense, add_income, get_spending_summary, get_account_balances
)
from connectors.meridian import (
    append_to_daily_note, search_vault, trigger_meridian_cycle, queue_meridian_prompt
)
from connectors.olympus import get_pnl_summary
from search.retriever import search_meridian, search_decisions
from core.memory import log_decision, get_approval_rule, set_approval_rule
from core.audit import log


def execute_function(function_name: str, arguments: dict) -> str:
    log(f"Executing: {function_name}", detail=str(arguments)[:100], system="EXECUTOR")

    if function_name == "add_expense":
        result = add_expense(
            amount=arguments["amount"],
            description=arguments["description"],
            category=arguments["category"],
            account=arguments["account"],
            date=arguments.get("date")
        )
        if result["success"]:
            return f"Recorded expense: ${arguments['amount']} for {arguments['description']} ({arguments['category']}) from {arguments['account']}."
        return f"Failed to record expense: {result.get('error')}"

    elif function_name == "add_income":
        result = add_income(
            amount=arguments["amount"],
            description=arguments["description"],
            account=arguments["account"],
            date=arguments.get("date")
        )
        return f"Recorded income: ${arguments['amount']} — {arguments['description']}." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "log_journal_entry":
        result = append_to_daily_note(arguments["content"])
        return "Journal entry written." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "log_decision":
        log_decision(
            decision=arguments["decision"],
            reasoning=arguments.get("reasoning"),
            domain=arguments.get("domain", "general")
        )
        content = f"**Decision:** {arguments['decision']}\n**Reasoning:** {arguments.get('reasoning', 'Not provided')}"
        append_to_daily_note(content)
        return f"Decision logged: {arguments['decision']}"

    elif function_name == "get_spending_summary":
        result = get_spending_summary(arguments.get("period", "month"))
        return f"Spending summary: {result['data']}" if result["success"] else f"Could not get summary: {result.get('error')}"

    elif function_name == "get_account_balances":
        result = get_account_balances()
        return f"Account balances: {result['data']}" if result["success"] else f"Could not get balances: {result.get('error')}"

    elif function_name == "search_meridian":
        results = search_meridian(query=arguments["query"], n_results=arguments.get("n_results", 5))
        if not results:
            return f"No results found for: {arguments['query']}"
        return "Found {} relevant notes:\n{}".format(
            len(results),
            "\n".join([f"[{r['source']}]: {r['content'][:200]}..." for r in results])
        )

    elif function_name == "get_olympus_status":
        result = get_pnl_summary()
        if result["success"]:
            s = result["summary"]
            stale = " (WARNING: data is stale)" if s.get("is_stale") else ""
            positions = ", ".join([p.get("symbol", "?") for p in s.get("open_positions", [])]) or "None"
            alerts = "; ".join(s.get("alerts", [])) or "None"
            return (f"Olympus status{stale}:\nDaily PnL: {s['daily_pnl']}\n"
                    f"Total PnL: {s['total_pnl']}\nPositions ({s['position_count']}): {positions}\n"
                    f"Alerts: {alerts}")
        return f"Could not read Olympus: {result.get('error')}"

    elif function_name == "trigger_meridian_cycle":
        result = trigger_meridian_cycle()
        return f"Meridian cycle triggered.\n{result.get('output', '')[:300]}" if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "queue_meridian_prompt":
        result = queue_meridian_prompt(arguments["prompt"])
        return f"Prompt queued for tomorrow's Meridian cycle." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "get_morning_briefing":
        olympus = execute_function("get_olympus_status", {})
        spending = execute_function("get_spending_summary", {"period": "week"})
        return f"OLYMPUS:\n{olympus}\n\nTHIS WEEK'S SPENDING:\n{spending}"

    elif function_name == "search_past_decisions":
        results = search_decisions(arguments["query"])
        if not results:
            return f"No relevant past decisions for: {arguments['query']}"
        return "Relevant past decisions:\n" + "\n".join([
            f"[{r['timestamp'][:10]}] {r['content'][:200]}..." for r in results
        ])

    elif function_name == "set_approval_rule":
        set_approval_rule(arguments["action_type"], arguments["scope"])
        scope_label = "permanently" if arguments["scope"] == "permanent" else "for this session"
        return f"Got it — I'll skip asking for {arguments['action_type']} {scope_label}."

    return f"Unknown function: {function_name}"
```

### Step 6.3 — Create the Brain

Create `C:\Apollo\core\brain.py`:

```python
import anthropic
from config import ANTHROPIC_API_KEY, PRIMARY_MODEL, MAX_TOKENS
from core.functions import APOLLO_TOOLS
from core.executor import execute_function
from core.memory import log_conversation, get_approval_rule
from core.audit import log

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

APOLLO_SYSTEM_PROMPT = """You are Apollo — a personal AI operating system built for one person. You are deeply integrated with their financial system (Black Book), long-term memory vault (Meridian), and trading system (Olympus/Apex).

Your personality: Direct, clear, professional. No filler. No excessive affirmations. You speak like a trusted advisor who knows the person well.

Your rules:
1. Before writing or creating anything, check if the action has a permanent approval rule. If it does, proceed without asking. If not, confirm once — unless the user says "just this once" (proceed now, ask next time) or "always allow" (record permanent approval, never ask again).
2. Never duplicate data. If something was already recorded today, ask before recording again.
3. When you don't know something, say so. Never guess at financial figures.
4. Use the most specific tool available.
5. Every response should be useful. No padding.
6. If a system is unavailable, say so clearly and tell the user what was queued.

When you have retrieved data from systems, synthesize it into a clear, concise answer. Don't dump raw data."""

# --- Caching setup ---
CACHED_SYSTEM = [
    {"type": "text", "text": APOLLO_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
]
CACHED_TOOLS = [
    *APOLLO_TOOLS[:-1],
    {**APOLLO_TOOLS[-1], "cache_control": {"type": "ephemeral"}}
]


def chat(user_message: str, conversation_history: list = None,
         channel: str = "ui") -> tuple[str, list]:
    if conversation_history is None:
        conversation_history = []

    conversation_history.append({"role": "user", "content": user_message})
    log_conversation("user", user_message, channel=channel)
    log(f"User [{channel}]: {user_message[:100]}", system="BRAIN")

    recent_history = conversation_history[-20:]
    response_text = _run_with_tools(recent_history)

    conversation_history.append({"role": "assistant", "content": response_text})
    log_conversation("apollo", response_text, channel=channel)

    return response_text, conversation_history


def _run_with_tools(messages: list) -> str:
    current_messages = list(messages)

    while True:
        response = client.messages.create(
            model=PRIMARY_MODEL,
            max_tokens=MAX_TOKENS,
            system=CACHED_SYSTEM,
            tools=CACHED_TOOLS,
            messages=current_messages
        )

        # Log cache performance
        usage = response.usage
        if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
            log(f"Cache hit: {usage.cache_read_input_tokens} tokens cached, "
                f"{usage.input_tokens} billed at full price", system="CACHE")

        if response.stop_reason == "tool_use":
            current_messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_function(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            current_messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Action completed."

        else:
            return f"Unexpected stop reason: {response.stop_reason}"
```

---

## PART 7: The Voice Input Module

### Step 7.1 — Create the Transcriber

Create `C:\Apollo\voice\transcriber.py`:

```python
import tempfile
import os
from faster_whisper import WhisperModel
from core.audit import log

_model = None

def get_model():
    global _model
    if _model is None:
        print("Loading Whisper model (first time only)...")
        _model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _model

def transcribe_audio_file(audio_path: str) -> str:
    model = get_model()
    segments, _ = model.transcribe(audio_path, beam_size=5)
    text = " ".join([seg.text for seg in segments]).strip()
    log(f"Transcribed: '{text[:80]}'", system="VOICE")
    return text

def transcribe_bytes(audio_bytes: bytes, extension: str = "wav") -> str:
    with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return transcribe_audio_file(tmp_path)
    finally:
        os.unlink(tmp_path)
```

---

## PART 8: The Daily Brief Agent (Phase 3)

The Daily Brief runs automatically every morning. It pulls all system statuses, compiles them, and delivers a summary — without you asking.

### Step 8.1 — Create the Brief Agent

Create `C:\Apollo\agents\brief.py`:

```python
"""
Daily Brief Agent — runs on a schedule, no user input required.
Compiles Olympus status, overnight spending, and open Meridian questions
into a single morning summary and delivers it via configured channels.
"""
import schedule
import time
from datetime import date, timedelta
from core.brain import chat
from core.audit import log
from config import BRIEF_DELIVERY_TIME

# Persistent history for the brief agent's own session
_brief_history = []

BRIEF_PROMPT = """Generate today's morning brief. Do the following:
1. Call get_olympus_status to check Apex and current positions.
2. Call get_spending_summary for the current week.
3. Call search_meridian with query "open questions unanswered" to find any pending items.

Then synthesize everything into a clean morning briefing. Format:
- One line on Olympus
- One line on spending
- Any open Meridian items
- Nothing else unless something is urgent or anomalous

Keep it under 100 words. Be direct."""

def run_brief(deliver_fn=None):
    """
    Run the morning brief and deliver it.
    deliver_fn: optional callable that receives the brief text (e.g. send_whatsapp).
    If None, it just logs the brief.
    """
    global _brief_history
    log("Starting daily brief", system="BRIEF")

    response, _brief_history = chat(BRIEF_PROMPT, _brief_history, channel="brief")
    _brief_history = []  # Reset after each brief — no carryover

    log(f"Brief generated: {response[:200]}", system="BRIEF")

    if deliver_fn:
        try:
            deliver_fn(response)
            log("Brief delivered", system="BRIEF")
        except Exception as e:
            log(f"Brief delivery failed: {e}", system="BRIEF")
    else:
        print(f"\n=== APOLLO MORNING BRIEF ===\n{response}\n")

    return response

def start_brief_scheduler(deliver_fn=None):
    """
    Start the daily brief scheduler.
    Call this from main.py in a background thread.
    """
    schedule.every().day.at(BRIEF_DELIVERY_TIME).do(run_brief, deliver_fn=deliver_fn)
    log(f"Brief scheduled for {BRIEF_DELIVERY_TIME} daily", system="BRIEF")

    while True:
        schedule.run_pending()
        time.sleep(60)
```

### Step 8.2 — Wire the Brief into main.py

Add this to `main.py` after `initialize_database()`:

```python
import threading
from agents.brief import start_brief_scheduler

# Start the brief scheduler in a background thread
brief_thread = threading.Thread(
    target=start_brief_scheduler,
    daemon=True
)
brief_thread.start()
```

Add a manual trigger endpoint:

```python
@app.post("/brief")
async def trigger_brief():
    """Manually trigger the morning brief."""
    from agents.brief import run_brief
    brief_text = run_brief()
    return {"brief": brief_text}
```

---

## PART 9: The WhatsApp Bridge (Phase 2)

This lets you message Apollo from your phone without a dedicated app.

### Step 9.1 — Set Up the WhatsApp Bridge

The bridge uses `whatsapp-web.js` — a Node.js library that connects to WhatsApp Web. It runs as a small local server that forwards incoming messages to Apollo's API and sends Apollo's replies back.

In a new folder `C:\Apollo\channels\whatsapp_bridge\`, run:

```
npm init -y
npm install whatsapp-web.js qrcode-terminal express axios
```

Create `C:\Apollo\channels\whatsapp_bridge\index.js`:

```javascript
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const APOLLO_API = 'http://localhost:8001';
const YOUR_NUMBER = 'YOUR_PHONE_NUMBER@c.us';  // e.g. '15551234567@c.us'

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true }
});

client.on('qr', qr => {
    console.log('Scan this QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('WhatsApp bridge ready. Messages from your number will go to Apollo.');
});

client.on('message', async msg => {
    // Only respond to messages from your own number
    if (msg.from !== YOUR_NUMBER) return;

    console.log(`Received: ${msg.body}`);

    try {
        const response = await axios.post(`${APOLLO_API}/chat`, {
            message: msg.body,
            channel: 'whatsapp'
        });
        const reply = response.data.response;
        await msg.reply(reply);
        console.log(`Sent: ${reply.substring(0, 80)}...`);
    } catch (err) {
        await msg.reply('Apollo is unavailable right now.');
        console.error('Apollo API error:', err.message);
    }
});

client.initialize();
```

**Replace `YOUR_PHONE_NUMBER`** with your phone number in international format without `+` (e.g., `15551234567`).

### Step 9.2 — Update the Chat Endpoint for Channel Awareness

Update the `ChatRequest` model in `main.py`:

```python
class ChatRequest(BaseModel):
    message: str
    reset_history: Optional[bool] = False
    channel: Optional[str] = "ui"   # 'ui', 'whatsapp', 'voice', 'brief'
```

Update the chat endpoint:

```python
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global conversation_history
    if request.reset_history:
        conversation_history = []
    response, conversation_history = chat(
        request.message, conversation_history, channel=request.channel
    )
    return ChatResponse(response=response, history_length=len(conversation_history))
```

### Step 9.3 — Start the WhatsApp Bridge

In a new terminal:

```
cd C:\Apollo\channels\whatsapp_bridge
node index.js
```

On first run, a QR code will appear. Scan it with your phone (WhatsApp → Linked Devices → Link a Device). After scanning, the bridge stays connected. To send Apollo a command, message **yourself** on WhatsApp. Apollo will reply in the same thread.

### Step 9.4 — Add the WhatsApp Bridge to the Startup Script

See Part 13 for the updated startup `.bat` file.

---

## PART 10: The API Layer

### Step 10.1 — Create main.py

Create `C:\Apollo\main.py`:

```python
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading
import uvicorn

from core.brain import chat
from core.memory import initialize_database, get_recent_conversations, get_decisions, get_active_patterns, clear_session_rules
from search.indexer import index_meridian_vault, index_decisions
from voice.transcriber import transcribe_bytes
from agents.brief import start_brief_scheduler

# Initialize on startup
initialize_database()
clear_session_rules()  # New session — clear any "just this once" approvals

# Start daily brief scheduler in background
brief_thread = threading.Thread(target=start_brief_scheduler, daemon=True)
brief_thread.start()

app = FastAPI(title="Apollo", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

conversation_history = []

class ChatRequest(BaseModel):
    message: str
    reset_history: Optional[bool] = False
    channel: Optional[str] = "ui"

class ChatResponse(BaseModel):
    response: str
    history_length: int

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global conversation_history
    if request.reset_history:
        conversation_history = []
    response, conversation_history = chat(request.message, conversation_history, channel=request.channel)
    return ChatResponse(response=response, history_length=len(conversation_history))

@app.post("/voice")
async def voice_endpoint(audio: UploadFile = File(...)):
    global conversation_history
    audio_bytes = await audio.read()
    extension = audio.filename.split(".")[-1] if audio.filename else "wav"
    transcribed = transcribe_bytes(audio_bytes, extension)
    if not transcribed:
        raise HTTPException(status_code=400, detail="Could not transcribe audio")
    response, conversation_history = chat(transcribed, conversation_history, channel="voice")
    return {"transcription": transcribed, "response": response}

@app.post("/brief")
async def trigger_brief():
    """Manually trigger the morning brief."""
    from agents.brief import run_brief
    return {"brief": run_brief()}

@app.get("/history")
async def get_history():
    return get_recent_conversations(limit=50)

@app.get("/decisions")
async def get_all_decisions():
    return get_decisions(limit=100)

@app.get("/patterns")
async def get_patterns():
    return get_active_patterns()

@app.post("/reindex")
async def reindex():
    vault_result = index_meridian_vault()
    index_decisions()
    return {"vault": vault_result, "decisions": "indexed"}

@app.get("/health")
async def health():
    return {"status": "Apollo is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
```

### Step 10.2 — Start Apollo's Backend

```
python main.py
```

You should see:
```
Apollo database initialized.
Brief scheduled for 07:00 daily
INFO: Uvicorn running on http://0.0.0.0:8001
```

### Step 10.3 — Test the Backend

```
curl -X POST http://localhost:8001/chat -H "Content-Type: application/json" -d "{\"message\": \"What is Olympus doing today?\"}"
```

If you get a JSON response with Apollo's reply, the backend is working.

---

## PART 11: The Chat UI

### Step 11.1 — Create the Reflex App

Create `C:\Apollo\ui\app.py`:

```python
import reflex as rx
import requests
from typing import List

APOLLO_API = "http://localhost:8001"

class Message(rx.Base):
    role: str
    content: str

class State(rx.State):
    messages: List[Message] = []
    input_text: str = ""
    is_loading: bool = False

    def send_message(self):
        if not self.input_text.strip():
            return
        user_msg = self.input_text.strip()
        self.messages.append(Message(role="user", content=user_msg))
        self.input_text = ""
        self.is_loading = True
        yield
        try:
            response = requests.post(
                f"{APOLLO_API}/chat",
                json={"message": user_msg, "channel": "ui"},
                timeout=30
            )
            data = response.json()
            self.messages.append(Message(role="apollo", content=data["response"]))
        except Exception as e:
            self.messages.append(Message(role="apollo", content=f"Error: {str(e)}"))
        self.is_loading = False

    def clear_chat(self):
        self.messages = []
        requests.post(f"{APOLLO_API}/chat", json={"message": "", "reset_history": True})

def message_bubble(msg: Message) -> rx.Component:
    return rx.box(
        rx.text(msg.content, color="#FFFFFF" if msg.role == "user" else "#E0E0E0",
                font_size="14px", line_height="1.6"),
        background=rx.cond(msg.role == "user", "#1a1a2e", "#16213e"),
        padding="12px 16px",
        border_radius="12px",
        border_left=rx.cond(msg.role == "apollo", "3px solid #e8c97d", "none"),
        max_width="85%",
        align_self=rx.cond(msg.role == "user", "flex-end", "flex-start"),
        margin_bottom="8px",
    )

def index() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text("☀ APOLLO", font_size="20px", font_weight="bold", color="#e8c97d"),
            rx.spacer(),
            rx.button("Clear", on_click=State.clear_chat, size="1",
                      color="#888", background="transparent", cursor="pointer"),
            padding="16px 20px",
            border_bottom="1px solid #1a1a2e",
            width="100%",
        ),
        rx.box(
            rx.foreach(State.messages, message_bubble),
            rx.cond(
                State.is_loading,
                rx.text("Apollo is thinking...", color="#888", font_size="13px", font_style="italic"),
                rx.box()
            ),
            flex="1", overflow_y="auto", padding="20px",
            display="flex", flex_direction="column",
        ),
        rx.hstack(
            rx.input(
                placeholder="Tell Apollo anything...",
                value=State.input_text,
                on_change=State.set_input_text,
                on_key_down=lambda key: State.send_message() if key == "Enter" else None,
                flex="1",
                background="#1a1a2e", border="1px solid #2a2a4e", color="#FFFFFF",
                padding="12px", border_radius="8px",
                _placeholder={"color": "#666"},
            ),
            rx.button("Send", on_click=State.send_message,
                      background="#e8c97d", color="#0a0a1a", font_weight="bold",
                      padding="12px 20px", border_radius="8px", cursor="pointer"),
            padding="16px 20px", border_top="1px solid #1a1a2e", width="100%",
        ),
        display="flex", flex_direction="column", height="100vh",
        background="#0a0a1a", font_family="'Inter', system-ui, sans-serif",
    )

app = rx.App()
app.add_page(index, route="/")
```

### Step 11.2 — Initialize and Run the UI

```
cd ui
reflex init
reflex run
```

Apollo's UI opens at `http://localhost:3000`.

---

## PART 12: The Apollo Mind Vault

### Step 12.1 — Create self_model.md

Create `C:\Apollo\mind_vault\self_model.md`:

```markdown
# Self Model — Apollo's Understanding of [Your Name]

*This file is maintained by Apollo and updated as patterns are detected.*
*Last updated: [DATE]*

---

## Identity

- **Name:** [Your name]
- **Primary Focus:** Trading (Olympus/Apex), Financial tracking (Black Book), Long-term thinking (Meridian)

## Financial Behavior Patterns
*Apollo will populate this over time.*

## Decision-Making Style
*Apollo will populate this over time.*

## Known Mental Models
*Apollo will populate this as you articulate them.*

## Goals (As Stated)
*Apollo will record these as you mention them.*

## Recurring Themes in Journals
*Apollo will identify these over time.*
```

### Step 12.2 — Create core/mind.py

Create `C:\Apollo\core\mind.py`:

```python
from pathlib import Path
from datetime import datetime
from config import APOLLO_MIND_VAULT_PATH
from core.audit import log
import anthropic
from config import ANTHROPIC_API_KEY, FAST_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def get_mind_vault_path() -> Path:
    return Path(APOLLO_MIND_VAULT_PATH)

def write_mental_model(title: str, content: str):
    folder = get_mind_vault_path() / "mental_models"
    folder.mkdir(exist_ok=True)
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    path = folder / f"{safe_title}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n*Recorded: {datetime.now().strftime('%Y-%m-%d')}*\n\n{content}")
    log(f"Wrote mental model: {title}", system="MIND_VAULT")

def log_decision_to_vault(decision: str, reasoning: str, domain: str):
    folder = get_mind_vault_path() / "decisions"
    folder.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = folder / f"{date_str}-{domain}.md"
    entry = f"\n## {datetime.now().strftime('%H:%M')}\n**Decision:** {decision}\n**Reasoning:** {reasoning}\n\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    log(f"Decision logged to Mind Vault: {domain}", system="MIND_VAULT")

def update_self_model(new_insight: str):
    self_model_path = get_mind_vault_path() / "self_model.md"
    with open(self_model_path, "a", encoding="utf-8") as f:
        f.write(f"\n## Insight — {datetime.now().strftime('%Y-%m-%d')}\n{new_insight}\n")
    log(f"Self model updated: {new_insight[:80]}", system="MIND_VAULT")
```

---

## PART 13: The Cross-System Trigger Engine (Phase 4)

This is what makes the systems talk back to each other. Build this only after Phase 1-3 are working.

### Step 13.1 — Create core/triggers.py

Create `C:\Apollo\core\triggers.py`:

```python
"""
Cross-system trigger engine.
Evaluates conditions across Black Book and Olympus, then fires
actions in Meridian or notifies the user via Apollo.

Run on a schedule (every hour or every 15 minutes).
"""
from connectors.black_book import get_spending_summary, get_category_average
from connectors.olympus import get_drawdown_pct
from connectors.meridian import queue_meridian_prompt
from core.audit import log
from datetime import datetime

# --- Trigger Definitions ---
# Each trigger has: a condition function and an action function.
# Add new triggers here as you identify patterns you want Apollo to watch.

DRAWDOWN_THRESHOLD_PCT = 5.0   # Adjust to your Olympus risk tolerance
SPEND_MULTIPLIER_THRESHOLD = 2.0  # Fire if any category is 2x its weekly average

def check_olympus_drawdown():
    """Fire if Apex reports a drawdown above threshold."""
    drawdown = get_drawdown_pct()
    if drawdown is None:
        return
    if drawdown >= DRAWDOWN_THRESHOLD_PCT:
        prompt = (
            f"Olympus had a drawdown of {drawdown:.1f}% today. "
            f"How are you feeling about the strategy, and is anything worth adjusting?"
        )
        queue_meridian_prompt(prompt)
        log(f"Drawdown trigger fired: {drawdown:.1f}%", system="TRIGGERS")

def check_spending_anomalies():
    """Fire if any spending category is significantly above its average."""
    result = get_spending_summary(period="week")
    if not result["success"]:
        return
    for item in result["data"]:
        category = item.get("category")
        weekly_total = float(item.get("total", 0))
        avg_result = get_category_average(category)
        if not avg_result["success"]:
            continue
        avg = avg_result["avg_weekly"]
        if avg > 0 and weekly_total >= avg * SPEND_MULTIPLIER_THRESHOLD:
            prompt = (
                f"Your {category} spending this week (${weekly_total:.0f}) is "
                f"{weekly_total/avg:.1f}x your usual weekly average (${avg:.0f}). "
                f"Anything driving that?"
            )
            queue_meridian_prompt(prompt)
            log(f"Spending anomaly trigger: {category} at {weekly_total/avg:.1f}x average",
                system="TRIGGERS")

def run_all_triggers():
    """Evaluate all triggers. Call this on a schedule."""
    log(f"Evaluating triggers at {datetime.now().strftime('%H:%M')}", system="TRIGGERS")
    check_olympus_drawdown()
    check_spending_anomalies()
    log("Trigger evaluation complete", system="TRIGGERS")

if __name__ == "__main__":
    run_all_triggers()
```

### Step 13.2 — Schedule the Trigger Engine

Add this to `main.py` alongside the brief scheduler:

```python
import schedule
from core.triggers import run_all_triggers

def start_trigger_scheduler():
    schedule.every(1).hours.do(run_all_triggers)
    import time
    while True:
        schedule.run_pending()
        time.sleep(60)

trigger_thread = threading.Thread(target=start_trigger_scheduler, daemon=True)
trigger_thread.start()
```

### Step 13.3 — Add a Trigger Endpoint

```python
@app.post("/triggers/run")
async def run_triggers():
    """Manually run all trigger evaluations."""
    from core.triggers import run_all_triggers
    run_all_triggers()
    return {"status": "Triggers evaluated"}
```

---

## PART 14: Pattern Detection (Phase 4)

### Step 14.1 — Create core/patterns.py

Create `C:\Apollo\core\patterns.py`:

```python
from connectors.black_book import get_spending_summary
from core.memory import save_pattern
from core.audit import log
import anthropic
from config import ANTHROPIC_API_KEY, PRIMARY_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def analyze_spending_patterns():
    summary = get_spending_summary("month")
    if not summary["success"]:
        return
    prompt = f"""
    Analyze this spending data and identify 2-3 clear behavioral patterns.
    Be specific. Each pattern should be actionable.
    Data: {summary['data']}
    Format each as:
    PATTERN: [description]
    CONFIDENCE: [0.0-1.0]
    DATA_POINTS: [number]
    """
    response = client.messages.create(
        model=PRIMARY_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    for line in response.content[0].text.split("\n"):
        if line.startswith("PATTERN:"):
            description = line.replace("PATTERN:", "").strip()
            save_pattern("spending", description, 0.7, 30)
            log(f"Detected spending pattern: {description[:80]}", system="PATTERNS")

def run_pattern_detection():
    log("Starting pattern detection cycle", system="PATTERNS")
    analyze_spending_patterns()
    log("Pattern detection complete", system="PATTERNS")

if __name__ == "__main__":
    run_pattern_detection()
```

---

## PART 15: Phase 5a — The Mirror

Build this only after Phases 1-4 are working smoothly.

### Step 15.1 — The Mirror System Prompt

When the Mirror is active, Apollo uses a deeper system prompt that instructs it to reason in your voice:

```python
MIRROR_SYSTEM_PROMPT = """You are Apollo operating in Mirror Mode.

You have access to years of [Name]'s:
- Financial decisions and their outcomes (Black Book + decision log)
- Journal entries and emotional context (Meridian)
- Trading decisions via Apex in Olympus
- Stated goals, fears, and mental models (Apollo Mind Vault)

In Mirror Mode, your job is not to give generic advice. Your job is to reason as [Name] would reason — using their own stated frameworks, their own past decisions, and their own language.

When asked what they would do, or should do:
1. First retrieve relevant past decisions using search_past_decisions
2. Find relevant journal context using search_meridian
3. Check current financial state with get_account_balances
4. Reason using their own frameworks and past reasoning patterns
5. Answer in their voice: "Based on your own reasoning in [date], you said..."

Always surface the reasoning so they can agree, disagree, or refine it. You are a mirror, not a replacement."""
```

### Step 15.2 — Activate Mirror Mode

Add a `/mirror` endpoint to `main.py`. The user types `/mirror on` to activate it for a session. The brain switches to the Mirror system prompt for that session.

---

## PART 16: Phase 5b — The Hub (Agent Spawning)

Build this only after Phase 5a is working.

### Step 16.1 — Create agents/hub.py

Create `C:\Apollo\agents\hub.py`:

```python
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
            schedule_expression TEXT,         -- e.g. 'every 6 hours', 'daily at 09:00'
            tools_allowed TEXT NOT NULL,      -- JSON array of allowed function names
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
```

### Step 16.2 — Add Hub Endpoints

Add to `main.py`:

```python
from agents.hub import initialize_hub, create_agent, list_agents, retire_agent

initialize_hub()

@app.get("/agents")
async def get_agents():
    return list_agents()

@app.post("/agents")
async def create_new_agent(payload: dict):
    agent_id = create_agent(
        name=payload["name"],
        description=payload["description"],
        system_prompt=payload["system_prompt"],
        schedule_expr=payload.get("schedule", "daily at 09:00"),
        tools_allowed=payload.get("tools", [])
    )
    return {"agent_id": agent_id, "status": "created"}

@app.delete("/agents/{agent_id}")
async def retire_agent_endpoint(agent_id: int):
    retire_agent(agent_id)
    return {"status": "retired"}
```

---

## PART 17: Putting It All Together

### Step 17.1 — The Complete Startup Sequence

**Terminal 1 — Apollo backend:**

```
cd C:\Apollo
venv\Scripts\activate
python main.py
```

**Terminal 2 — Apollo UI:**

```
cd C:\Apollo\ui
reflex run
```

**Terminal 3 — WhatsApp bridge:**

```
cd C:\Apollo\channels\whatsapp_bridge
node index.js
```

Open `http://localhost:3000` — Apollo is live on web.
Message yourself on WhatsApp — Apollo is live on mobile.

### Step 17.2 — Create a Windows Startup Script

Create `C:\Apollo\start_apollo.bat`:

```batch
@echo off
echo Starting Apollo...

:: Start Apollo backend
start "Apollo Backend" cmd /k "cd /d C:\Apollo && venv\Scripts\activate && python main.py"
timeout /t 4

:: Start Apollo UI
start "Apollo UI" cmd /k "cd /d C:\Apollo\ui && reflex run"
timeout /t 3

:: Start WhatsApp bridge
start "Apollo WhatsApp" cmd /k "cd /d C:\Apollo\channels\whatsapp_bridge && node index.js"

echo Apollo is starting.
echo Web UI:    http://localhost:3000
echo API:       http://localhost:8001
echo WhatsApp:  Bridge starting — check the terminal for QR code on first run.
```

### Step 17.3 — Re-index on a Schedule

Every time you add significant content to Meridian, re-index:

```
curl -X POST http://localhost:8001/reindex
```

Or create a Windows Task Scheduler job to run nightly at 2:00am targeting `python C:\Apollo\search\indexer.py`.

---

## PART 18: What Done Looks Like at Each Phase

| Phase                     | You Know It Works When                                                                                     |
|---------------------------|------------------------------------------------------------------------------------------------------------|
| **Phase 1 — Bridge**      | "What's Olympus doing?" returns real data. "Run Meridian" triggers the script.                             |
| **Phase 2 — Recording**   | You say an expense and it appears in Black Book. WhatsApp works as an input channel. Session approvals work.|
| **Phase 3 — Oracle**      | Cross-system questions work. The daily brief runs automatically at 7am.                                    |
| **Phase 4 — Chronicler**  | An Olympus drawdown queues a Meridian reflection. A spending anomaly surfaces before you notice.           |
| **Phase 5a — Mirror**     | You ask "what would I do?" and Apollo reasons in your voice using your actual history.                     |
| **Phase 5b — Hub**        | You describe a background task in plain language and Apollo runs it as a persistent agent.                 |

---

## PART 19: Common Problems and Fixes

| Problem                         | Fix                                                                        |
|---------------------------------|----------------------------------------------------------------------------|
| `ANTHROPIC_API_KEY` not found   | Check `.env` is in `C:\Apollo` and `load_dotenv()` is called in config.py  |
| Neon connection refused         | Verify `BLACK_BOOK_DB_URL` in `.env`. Check that your IP is allowed in Neon.|
| ChromaDB indexing fails         | Verify `MERIDIAN_VAULT_PATH` in `.env` points to the correct folder        |
| WhatsApp bridge: QR not showing | Run `node index.js` in the correct folder; delete `.wwebjs_auth` and retry |
| WhatsApp bridge: not responding | Check Apollo backend is running on port 8001 before starting the bridge    |
| Whisper download fails          | Run `pip install faster-whisper` again with venv active                    |
| `venv` not activating           | Run `venv\Scripts\activate` from `C:\Apollo` directory                     |
| Reflex port conflict            | Kill the process on port 3000 or change port in `reflex.config.py`         |
| Brief not firing                | Check `BRIEF_DELIVERY_TIME` in `.env` matches 24h format (e.g. `07:00`)    |
| Trigger engine not running      | Confirm the trigger thread started — check `apollo_audit.log` for `[TRIGGERS]` entries |

---

*End of Build Plan — Project Apollo, Revision 2*
*Build one part at a time. Test before moving forward.*
*The Bridge (Part 4) is the gate — nothing else works until the connectors do.*
*The Daily Brief (Part 8) and WhatsApp Bridge (Part 9) can be built in parallel with Part 10.*
