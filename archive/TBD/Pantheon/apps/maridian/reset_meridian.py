"""
Reset all Meridian data — wipes local vault and Neon tables.
Run this once before starting fresh with the Karpathy wiki pattern.

Usage: python reset_meridian.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

VAULT_ROOT = Path(__file__).parent

FOLDERS_TO_WIPE = [
    "00-Seeds", "01-Sprouts", "02-Trees", "Frameworks",
    "Archive", "staging", "Brain", "Questions", "Patterns",
    "Debates", "Fossils", "raw", "wiki",
]
FILES_TO_DELETE = [
    "voice_profile.json", "vault_embeddings.json", ".evolve.lock",
]
NEON_TABLES = [
    "meridian_notes", "meridian_questions", "meridian_brain", "meridian_jobs",
]

FRESH_STATE = {
    "cycle_count": 0,
    "processed_entry_ids": [],
    "total_entries_processed": 0,
    "last_entry_date_processed": None,
    "last_cycle": None,
    "last_questions_generated": None,
    "wiki_last_built": None,
    "wiki_pages": [],
}


def reset_local() -> None:
    print("Local vault:")
    for name in FOLDERS_TO_WIPE:
        p = VAULT_ROOT / name
        if p.exists():
            shutil.rmtree(p)
            print(f"  deleted  {name}/")
    for name in FILES_TO_DELETE:
        p = VAULT_ROOT / name
        if p.exists():
            p.unlink()
            print(f"  deleted  {name}")
    state_file = VAULT_ROOT / "vault_state.json"
    state_file.write_text(json.dumps(FRESH_STATE, indent=2))
    print("  reset    vault_state.json")


def reset_neon() -> None:
    print("Neon tables:")
    try:
        from db.neon_bridge import get_connection
        conn = get_connection()
        cur = conn.cursor()
        for table in NEON_TABLES:
            try:
                cur.execute(f"DELETE FROM {table}")
                print(f"  cleared  {table}")
            except Exception as e:
                print(f"  {table}: {e}")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  Neon connection failed: {e}")
        print("  (Run again on a network where port 5432/6543 is open)")


if __name__ == "__main__":
    print("=" * 45)
    print("  MERIDIAN RESET")
    print("=" * 45)
    reset_local()
    print()
    reset_neon()
    print()
    print("Done. Run  python evolve.py  to start fresh.")
    print("=" * 45)
