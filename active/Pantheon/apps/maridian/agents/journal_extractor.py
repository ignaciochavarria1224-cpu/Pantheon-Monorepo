# agents/journal_extractor.py
"""
Pulls journal entries from Neon, writes them to raw/ as immutable source files.
raw/ is the source of truth — these files are never modified after writing.
"""
import re
from pathlib import Path
from utils.vault import VAULT_ROOT
from db.neon_bridge import pull_new_entries

RAW_DIR = VAULT_ROOT / "raw"


def _slug(text: str, maxlen: int = 20) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower().strip())[:maxlen].strip("_")


def extract(vault_state: dict, max_entries: int = 50) -> list:
    """Pull new entries from Neon and write each as a raw/ markdown file."""
    print("[EXTRACTOR] Pulling new journal entries...")
    RAW_DIR.mkdir(exist_ok=True)

    processed_ids = vault_state.get("processed_entry_ids", [])
    entries = pull_new_entries(processed_ids)

    if not entries:
        print("  No new entries.")
        return []

    print(f"  {len(entries)} new entries found.")
    written, newly_processed = [], []

    for entry in entries[:max_entries]:
        eid    = entry["id"]
        edate  = str(entry["entry_date"])
        tag    = entry.get("tag", "General")
        body   = entry.get("body", "").strip()

        if len(body) < 30:
            newly_processed.append(eid)
            continue

        filename = f"{edate.replace('-', '')}_{eid}_{_slug(tag)}.md"
        path = RAW_DIR / filename
        path.write_text(
            f"---\nid: {eid}\ndate: {edate}\ntag: {tag}\n---\n\n{body}\n",
            encoding="utf-8",
        )
        written.append(path)
        newly_processed.append(eid)

    vault_state["processed_entry_ids"] = processed_ids + newly_processed
    vault_state["total_entries_processed"] = len(vault_state["processed_entry_ids"])
    if entries:
        vault_state["last_entry_date_processed"] = str(entries[-1]["entry_date"])

    print(f"[EXTRACTOR] {len(written)} raw files written to raw/.")
    return written
