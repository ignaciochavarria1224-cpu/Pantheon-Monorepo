"""
Meridian — Main Evolution Entrypoint (Karpathy Wiki Pattern)

Three-phase pipeline:
  Phase 1: Extract   — pull journal entries from Neon, write to raw/ as immutable files
  Phase 2: Build Wiki — classify entries by theme, build/update wiki/ pages
  Phase 3: Questions  — generate 4 dynamic + 3 fitness questions, push to Neon

Usage:
  python evolve.py evolve    # Full cycle
  python evolve.py status    # Print vault stats
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime

VAULT_ROOT = Path(__file__).parent
STATE_FILE = VAULT_ROOT / "vault_state.json"
STATE_TMP  = VAULT_ROOT / "vault_state.tmp"
LOCK_FILE  = VAULT_ROOT / ".evolve.lock"
WIKI_DIR   = VAULT_ROOT / "wiki"


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def acquire_lock():
    if LOCK_FILE.exists():
        raise RuntimeError("Meridian already running. Delete .evolve.lock to reset.")
    LOCK_FILE.write_text(str(time.time()))


def release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def _get_neon_conn():
    """Return a Neon psycopg2 connection if NEON_DATABASE_URL is set, else None."""
    try:
        import os, psycopg2
        url = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not url:
            from dotenv import load_dotenv
            load_dotenv(VAULT_ROOT / ".env")
            url = os.environ.get("NEON_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if url:
            return psycopg2.connect(url, connect_timeout=10)
    except Exception:
        pass
    return None


def claim_pending_job():
    """Mark oldest pending job as 'running'. Returns job id or None."""
    conn = _get_neon_conn()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE meridian_jobs SET status='running', started_at=%s "
            "WHERE id = (SELECT id FROM meridian_jobs WHERE status='pending' ORDER BY id LIMIT 1) "
            "RETURNING id",
            (datetime.now().isoformat(),)
        )
        row = cur.fetchone()
        conn.commit()
        cur.close(); conn.close()
        return row[0] if row else None
    except Exception:
        return None


def complete_job(job_id, result="ok"):
    """Mark a job as completed."""
    if job_id is None:
        return
    conn = _get_neon_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE meridian_jobs SET status='completed', completed_at=%s, result=%s WHERE id=%s",
            (datetime.now().isoformat(), result, job_id)
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception:
        pass


def run_evolve():
    print("=" * 55)
    print("  MERIDIAN — Evolution Cycle (Wiki Mode)")
    print("=" * 55)
    state = load_state()
    acquire_lock()
    start = time.time()
    job_id = claim_pending_job()
    if job_id:
        print(f"  [Neon] Picked up job #{job_id} from Black Book.")

    try:
        from agents.journal_extractor import extract
        from agents.brain_builder import build_wiki
        from agents.question_generator import generate as generate_questions
        from utils.git_ops import git_commit
        from db.neon_bridge import push_brain_themes

        # ── Phase 1: Extract ────────────────────────────────────
        print("\n-- Phase 1: Extract --")
        extract(state)

        # ── Phase 2: Build Wiki ──────────────────────────────────
        print("\n-- Phase 2: Build Wiki --")
        theme_entries = build_wiki(state)

        # ── Phase 3: Questions & Sync ────────────────────────────
        print("\n-- Phase 3: Questions & Sync --")
        generate_questions(state, theme_entries=theme_entries)

        # Push wiki pages to Neon so Black Book can display them
        wiki_themes = []
        if WIKI_DIR.exists():
            for f in sorted(WIKI_DIR.glob("*.md")):
                if not f.name.startswith(".") and f.name != "INDEX.md":
                    wiki_themes.append({
                        "theme": f.stem,
                        "body": f.read_text(encoding="utf-8"),
                    })
        wiki_index = ""
        index_f = WIKI_DIR / "INDEX.md"
        if index_f.exists():
            wiki_index = index_f.read_text(encoding="utf-8")

        state["cycle_count"] = state.get("cycle_count", 0) + 1
        state["last_cycle"] = datetime.now().isoformat()
        state["total_entries_processed"] = len(state.get("processed_entry_ids", []))

        push_brain_themes(wiki_themes, wiki_index, state["cycle_count"])

        # Two-phase state save (safe on Windows)
        STATE_TMP.write_text(json.dumps(state, indent=2))
        success = git_commit(state["cycle_count"], len(state.get("wiki_pages", [])))
        if success:
            STATE_TMP.replace(STATE_FILE)
        else:
            STATE_TMP.unlink(missing_ok=True)
            print("  [!] Git failed. Previous state preserved.")

        elapsed = round(time.time() - start, 1)
        complete_job(job_id, result=f"cycle_{state['cycle_count']}_ok")
        print(f"\n[DONE] Cycle {state['cycle_count']} complete in {elapsed}s")
        print(f"  Entries processed: {state.get('total_entries_processed', 0)}")
        print(f"  Wiki pages: {len(state.get('wiki_pages', []))}")
        print(f"  Questions pushed to Neon.")

    except Exception as e:
        complete_job(job_id, result=f"failed: {e}")
        print(f"\n[FAIL] CYCLE FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        release_lock()


def run_status():
    state = load_state()
    print("\nMeridian Status")
    print(f"  Cycle:              {state.get('cycle_count', 0)}")
    print(f"  Entries processed:  {state.get('total_entries_processed', 0)}")
    print(f"  Wiki pages:         {len(state.get('wiki_pages', []))}")
    print(f"  Wiki themes:        {', '.join(state.get('wiki_pages', [])) or 'none'}")
    print(f"  Wiki last built:    {state.get('wiki_last_built', 'Never')}")
    print(f"  Questions last gen: {state.get('last_questions_generated', 'Never')}")
    print(f"  Last cycle:         {state.get('last_cycle', 'Never')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "evolve":
        run_evolve()
    elif cmd == "status":
        run_status()
    else:
        print(__doc__)
