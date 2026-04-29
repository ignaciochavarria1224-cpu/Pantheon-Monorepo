from datetime import datetime
from pathlib import Path

from config import AUDIT_LOG_PATH


def _audit_path() -> Path:
    path = Path(AUDIT_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def log(action: str, detail: str = None, system: str = None):
    """Write a permanent record of every action Apollo takes."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_tag = f" [{system}]" if system else ""
    detail_tag = f" - {detail}" if detail else ""
    entry = f"{timestamp}{system_tag} - {action}{detail_tag}\n"
    with _audit_path().open("a", encoding="utf-8") as file_obj:
        file_obj.write(entry)
    print(f"[AUDIT]{system_tag} {action}{detail_tag}")


def get_recent_entries(limit: int = 40) -> list[dict]:
    path = _audit_path()
    if not path.exists():
        return []

    entries: list[dict] = []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    for raw in reversed(lines):
        if not raw.strip():
            continue
        timestamp = raw[:19] if len(raw) >= 19 else ""
        system = ""
        remainder = raw[20:] if len(raw) > 20 else raw
        if remainder.startswith("[") and "]" in remainder:
            system, remainder = remainder[1:].split("]", 1)
            system = system.strip()
            remainder = remainder.strip()
        action, _, detail = remainder.partition(" - ")
        entries.append(
            {
                "timestamp": timestamp,
                "system": system,
                "action": action.strip(),
                "detail": detail.strip(),
                "raw": raw,
            }
        )
    return entries
