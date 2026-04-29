# agents/fossil_manager.py
"""
Creates vault snapshots every 7 cycles. Records state in Fossils/index.md.
"""
import json
import shutil
from pathlib import Path
from datetime import date
from utils.vault import VAULT_ROOT
from utils.registry import NoteRegistry

FOSSILS_DIR = VAULT_ROOT / "Fossils"
FOSSIL_INDEX = FOSSILS_DIR / "index.md"
FOSSIL_TRIGGER = 7  # every N cycles


def maybe_create_fossil(vault_state: dict, registry: NoteRegistry) -> bool:
    cycle = vault_state.get("cycle_count", 0)
    if cycle == 0 or cycle % FOSSIL_TRIGGER != 0:
        return False

    print(f"[FOSSIL] Creating snapshot at cycle {cycle}...")
    snapshot_dir = FOSSILS_DIR / f"cycle_{cycle:04d}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Copy current vault notes to snapshot
    for folder_name in ["00-Seeds", "01-Sprouts", "02-Trees", "Frameworks"]:
        src = VAULT_ROOT / folder_name
        dst = snapshot_dir / folder_name
        if src.exists():
            shutil.copytree(str(src), str(dst), dirs_exist_ok=True)

    # Save state snapshot
    state_snap = snapshot_dir / "vault_state_snapshot.json"
    state_snap.write_text(json.dumps(vault_state, indent=2))

    # Update index
    notes = registry.get_all()
    fitnesses = [n["frontmatter"].get("fitness") or 0 for n in notes
                 if n["frontmatter"].get("fitness") is not None]
    avg_fitness = round(sum(fitnesses) / len(fitnesses), 1) if fitnesses else 0

    top_notes = sorted(notes, key=lambda n: n["frontmatter"].get("fitness") or 0, reverse=True)
    top_note = top_notes[0]["frontmatter"].get("title", "?") if top_notes else "?"

    with open(FOSSIL_INDEX, "a", encoding="utf-8") as f:
        f.write(f"| {cycle} | {date.today()} | {len(notes)} | {avg_fitness} | {top_note} |\n")

    print(f"[FOSSIL] Snapshot saved to {snapshot_dir.name}")
    return True
