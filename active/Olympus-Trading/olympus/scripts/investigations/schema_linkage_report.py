"""
Gap 3: Schema linkage clarity.
Examines database schema and linkage between local trades and Alpaca orders/fills.
"""

import sqlite3
from pathlib import Path
import sys

# Bootstrap
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

from config.settings import load_settings

def main():
    settings = load_settings()

    # Open DB read-only
    db_path = settings.DB_PATH
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    # Get all table names
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t['name'] for t in tables]

    print("=== DATABASE TABLES ===")
    for table in table_names:
        print(f"  {table}")

    print("\n=== TRADES TABLE SCHEMA ===")
    trades_schema = conn.execute("PRAGMA table_info(trades)").fetchall()
    for col in trades_schema:
        print(f"  {col['name']} ({col['type']}) - {'NOT NULL' if col['notnull'] else 'NULL'}")

    print("\n=== TRADE_FEATURES TABLE SCHEMA ===")
    try:
        features_schema = conn.execute("PRAGMA table_info(trade_features)").fetchall()
        for col in features_schema:
            print(f"  {col['name']} ({col['type']}) - {'NOT NULL' if col['notnull'] else 'NULL'}")
    except sqlite3.OperationalError:
        print("  trade_features table does not exist")

    # Check for other related tables
    print("\n=== OTHER POTENTIALLY RELATED TABLES ===")
    related_tables = [t for t in table_names if any(keyword in t.lower() for keyword in ['order', 'fill', 'trade', 'position', 'execution'])]
    for table in related_tables:
        if table not in ['trades', 'trade_features']:
            print(f"\n  {table} schema:")
            try:
                schema = conn.execute(f"PRAGMA table_info({table})").fetchall()
                for col in schema:
                    print(f"    {col['name']} ({col['type']}) - {'NOT NULL' if col['notnull'] else 'NULL'}")
            except sqlite3.OperationalError as e:
                print(f"    Error reading schema: {e}")

    # Analyze trades table for broker linkage columns
    print("\n=== BROKER LINKAGE ANALYSIS ===")
    linkage_keywords = ['order', 'alpaca', 'client', 'broker', 'external', 'fill', 'execution', 'id']
    linkage_columns = []

    for col in trades_schema:
        col_name = col['name'].lower()
        if any(keyword in col_name for keyword in linkage_keywords):
            linkage_columns.append(col['name'])

    if linkage_columns:
        print(f"Potential linkage columns found: {', '.join(linkage_columns)}")

        for col_name in linkage_columns:
            # Get sample values
            try:
                samples = conn.execute(f"SELECT {col_name} FROM trades WHERE {col_name} IS NOT NULL LIMIT 5").fetchall()
                sample_values = [str(row[col_name]) for row in samples]

                # Count NULLs
                null_count = conn.execute(f"SELECT COUNT(*) FROM trades WHERE {col_name} IS NULL").fetchone()[0]
                total_count = conn.execute(f"SELECT COUNT(*) FROM trades").fetchone()[0]

                print(f"\n  Column: {col_name}")
                print(f"    Sample values: {sample_values}")
                print(f"    NULL count: {null_count}/{total_count} ({null_count/total_count*100:.1f}%)")
            except sqlite3.OperationalError as e:
                print(f"    Error analyzing {col_name}: {e}")
    else:
        print("NO potential linkage columns found in trades table")

    # Check for foreign key constraints
    print("\n=== FOREIGN KEY ANALYSIS ===")
    try:
        fks = conn.execute("PRAGMA foreign_key_list(trades)").fetchall()
        if fks:
            print("Foreign keys on trades table:")
            for fk in fks:
                print(f"  {fk['from']} -> {fk['table']}.{fk['to']}")
        else:
            print("No foreign keys found on trades table")
    except sqlite3.OperationalError as e:
        print(f"Error checking foreign keys: {e}")

    # Summary
    print("\n=== LINKAGE METHOD ASSESSMENT ===")
    if linkage_columns:
        direct_linkage = any('id' in col.lower() and ('order' in col.lower() or 'alpaca' in col.lower()) for col in linkage_columns)
        if direct_linkage:
            print("✓ DIRECT ID LINKAGE available - most reliable")
        else:
            print("⚠ HEURISTIC MATCHING required - fragile")
    else:
        print("✗ NO LINKAGE POSSIBLE - catastrophic for reconciliation")

    conn.close()

if __name__ == "__main__":
    main()