"""
Export all Neon PostgreSQL tables to CSV files for backup.
Run from: apps/apollo/  (so config.py loads correctly)
Usage: python scripts/export_neon_to_csv.py [output_dir]
"""

import csv
import os
import sys
from pathlib import Path

# Allow running from apps/apollo/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
import psycopg2.extras

DB_URL = os.getenv("BLACK_BOOK_DB_URL") or os.getenv("DATABASE_URL")
if not DB_URL:
    # Try loading from .env manually
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("BLACK_BOOK_DB_URL=") or line.startswith("DATABASE_URL="):
                DB_URL = line.split("=", 1)[1].strip()
                break

if not DB_URL:
    root_env = Path(__file__).resolve().parents[3] / ".env"
    if root_env.exists():
        for line in root_env.read_text().splitlines():
            if line.startswith("BLACK_BOOK_DB_URL=") or line.startswith("DATABASE_URL="):
                DB_URL = line.split("=", 1)[1].strip()
                break

if not DB_URL:
    print("ERROR: No DATABASE_URL or BLACK_BOOK_DB_URL found in environment or .env files.")
    sys.exit(1)

TABLES = [
    "accounts",
    "transactions",
    "holdings",
    "price_cache",
    "price_history",
    "settings",
    "journal_entries",
    "allocation_snapshots",
    "daily_reports",
    "advisor_memory",
    "advisor_conversations",
    "meridian_notes",
    "meridian_jobs",
]

output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\Ignac\Dropbox\Pantheon_Backup_2026-04-18\neon_export"
)
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Connecting to Neon...")
conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

total_rows = 0
for table in TABLES:
    try:
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        if not rows:
            print(f"  {table}: 0 rows (empty or missing)")
            # Write header-only CSV
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position")
            cols = [r["column_name"] for r in cur.fetchall()]
            out_file = output_dir / f"{table}.csv"
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=cols)
                writer.writeheader()
            continue

        out_file = output_dir / f"{table}.csv"
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"  {table}: {len(rows)} rows -> {out_file.name}")
        total_rows += len(rows)
    except Exception as e:
        print(f"  {table}: SKIPPED - {e}")

cur.close()
conn.close()

print(f"\nDone. {total_rows} total rows exported to {output_dir}")
