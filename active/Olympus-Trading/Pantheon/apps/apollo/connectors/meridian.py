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
