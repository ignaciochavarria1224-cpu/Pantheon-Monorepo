"""
Meridian Control Panel
Run: streamlit run control.py
"""
import json
import subprocess
from pathlib import Path
from datetime import date

import streamlit as st

from db.neon_bridge import push_framework, get_connection

VAULT_ROOT     = Path(__file__).parent
STATE_FILE     = VAULT_ROOT / "vault_state.json"
LOCK_FILE      = VAULT_ROOT / ".evolve.lock"
FRAMEWORKS_DIR = VAULT_ROOT / "Frameworks"
FLAGGED_FILE   = VAULT_ROOT / "Debates" / "flagged.md"
QUESTIONS_DIR  = VAULT_ROOT / "Questions"

st.set_page_config(page_title="Meridian", page_icon="🧠", layout="wide")
st.title("🧠 Meridian — Second Brain Control Panel")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


state = load_state()
is_locked = LOCK_FILE.exists()

# ── STATUS ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Cycle", state.get("cycle_count", 0))
c2.metric("Entries Processed", state.get("total_entries_processed", 0))
c3.metric("Total Notes", state.get("total_notes", 0))
c4.metric("Avg Fitness", state.get("avg_fitness", 0))
c5.metric("Frameworks", state.get("framework_count", 0))

if state.get("stagnation_active"):
    st.warning("⚠ Stagnation active — pressure elevated.")
if is_locked:
    st.info("⏳ Meridian is running...")

st.divider()

# ── CONTROLS ──────────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns(3)
with col_a:
    if is_locked:
        st.button("▶ Run Cycle", disabled=True)
    elif st.button("▶ Run Cycle", type="primary"):
        with st.spinner("Running Meridian cycle..."):
            result = subprocess.run(
                ["python", "evolve.py", "evolve"],
                capture_output=True, text=True, cwd=str(VAULT_ROOT)
            )
        if result.returncode == 0:
            st.success("✓ Done")
        else:
            st.error("✗ Failed")
        st.code((result.stdout + result.stderr)[-3000:])
        st.rerun()
with col_b:
    if st.button("↺ Refresh"):
        st.rerun()
with col_c:
    if is_locked and st.button("🔓 Force Unlock"):
        LOCK_FILE.unlink(missing_ok=True)
        st.rerun()

st.divider()

# ── VAULT STATS ───────────────────────────────────────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    st.subheader("📊 Stage Breakdown")
    stages = state.get("notes_by_stage", {})
    if stages:
        st.bar_chart(stages)
    else:
        st.caption("No notes yet. Run a cycle first.")
with col_r:
    st.subheader("📈 Fitness History")
    history = state.get("fitness_history", [])
    if len(history) > 1:
        st.line_chart(history)
    else:
        st.caption("Run ≥2 cycles to see trend.")

st.divider()

# ── TODAY'S QUESTIONS ─────────────────────────────────────────────────────────
st.subheader("❓ Today's Adaptive Questions")
today_file = QUESTIONS_DIR / f"{date.today()}.md"
if today_file.exists():
    try:
        qs = json.loads(today_file.read_text())
        for i, q in enumerate(qs.get("questions", []), 1):
            st.markdown(f"**Q{i}:** {q.get('question', '')}")
            if q.get("context"):
                st.caption(f"*Why Meridian is asking: {q['context']}*")
    except Exception:
        st.code(today_file.read_text())
else:
    st.info("No questions generated yet today. Run a cycle first.")

st.divider()

# ── FRAMEWORK MARKET ──────────────────────────────────────────────────────────
st.subheader("📋 Framework Market")
markets = sorted(FRAMEWORKS_DIR.glob("market_*.md"), reverse=True)
if markets:
    with st.expander(f"Latest market: {markets[0].name}", expanded=True):
        st.markdown(markets[0].read_text(encoding="utf-8"))

    st.subheader("✍ Write a Framework")
    note_id = st.text_input("Note ID (from market above):")
    col_write, col_push = st.columns(2)
    with col_write:
        if st.button("📝 Write (local only)") and note_id.strip():
            result = subprocess.run(
                ["python", "evolve.py", "write", note_id.strip()],
                capture_output=True, text=True, cwd=str(VAULT_ROOT)
            )
            if result.returncode == 0:
                st.success("✓ Written to Frameworks/")
            else:
                st.error("✗ Failed")
            st.code(result.stdout[-1000:])
    with col_push:
        if st.button("🚀 Write + Push to Black Book") and note_id.strip():
            result = subprocess.run(
                ["python", "evolve.py", "push", note_id.strip()],
                capture_output=True, text=True, cwd=str(VAULT_ROOT)
            )
            if result.returncode == 0:
                st.success("✓ Written + pushed to Neon")
            else:
                st.error("✗ Failed")
            st.code(result.stdout[-1000:])
else:
    st.info("No framework market yet. Run ≥3 cycles to generate eligible notes.")

st.divider()

# ── TOP NOTES ─────────────────────────────────────────────────────────────────
st.subheader("🏆 Top Fitness Notes")
top_notes = state.get("top_fitness_notes", [])
if top_notes:
    for n in top_notes:
        st.markdown(f"**{n.get('title', 'Untitled')}** — `{n.get('id')}` — fitness: `{n.get('fitness', 0)}`")
else:
    st.caption("No scored notes yet.")

st.divider()

# ── FLAGGED FOR REVIEW ────────────────────────────────────────────────────────
st.subheader("🚩 Flagged for Review")
if FLAGGED_FILE.exists():
    content = FLAGGED_FILE.read_text(encoding="utf-8")
    rows = [l for l in content.split("\n") if l.startswith("|") and "Note ID" not in l and "---" not in l]
    if rows:
        st.markdown(content)
        st.caption("These beliefs appear to have reversed. Review and update or move to Archive/.")
    else:
        st.success("Nothing flagged.")
else:
    st.success("Nothing flagged.")

st.divider()

# ── NEON STATUS ───────────────────────────────────────────────────────────────
st.subheader("🔌 Neon Connection")
try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM journal_entries")
    entry_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM meridian_questions")
    q_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM meridian_outputs")
    f_count = cur.fetchone()[0]
    conn.close()
    st.success(
        f"✓ Connected — {entry_count} journal entries | "
        f"{q_count} question sets | {f_count} frameworks"
    )
except Exception as e:
    st.error(f"✗ Neon connection failed: {e}")
    st.caption("Make sure your .env file has the correct NEON_DATABASE_URL.")

if state.get("last_cycle"):
    st.caption(f"Last cycle: {state['last_cycle']}")
