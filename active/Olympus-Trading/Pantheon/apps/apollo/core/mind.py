from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import APOLLO_MIND_VAULT_PATH, FAST_MODEL
from core.audit import log


def get_mind_vault_path() -> Path:
    return Path(APOLLO_MIND_VAULT_PATH)


def _ensure_vault_structure():
    vault = get_mind_vault_path()
    vault.mkdir(parents=True, exist_ok=True)
    for folder_name in ("decisions", "patterns", "mental_models"):
        (vault / folder_name).mkdir(exist_ok=True)

    self_model_path = vault / "self_model.md"
    if not self_model_path.exists():
        self_model_path.write_text(
            (
                "# Self Model - Apollo's Understanding of You\n\n"
                "*This file is maintained by Apollo and updated as patterns are detected.*\n"
                f"*Last updated: {datetime.now().strftime('%Y-%m-%d')}*\n\n"
                "---\n\n"
                "## Identity\n\n"
                "- Primary Focus: Apollo is still learning.\n"
            ),
            encoding="utf-8",
        )


def _preview_markdown(path: Path, limit: int = 220) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8").strip()
    condensed = " ".join(content.split())
    if len(condensed) <= limit:
        return condensed
    return condensed[: limit - 3].rstrip() + "..."


def get_self_model_excerpt(limit: int = 280) -> str:
    _ensure_vault_structure()
    excerpt = _preview_markdown(get_mind_vault_path() / "self_model.md", limit=limit)
    return excerpt or "Self model is waiting for the first Apollo-written insight."


def list_vault_notes(folder_name: str, limit: int = 6) -> list[dict]:
    _ensure_vault_structure()
    folder = get_mind_vault_path() / folder_name
    notes: list[dict] = []
    for path in sorted(folder.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        stat = path.stat()
        notes.append(
            {
                "title": path.stem.replace("-", " ").replace("_", " ").title(),
                "filename": path.name,
                "preview": _preview_markdown(path),
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        )
    return notes


def get_vault_snapshot() -> dict:
    _ensure_vault_structure()
    vault = get_mind_vault_path()
    return {
        "vault_path": str(vault),
        "self_model_excerpt": get_self_model_excerpt(),
        "decisions": list_vault_notes("decisions"),
        "patterns": list_vault_notes("patterns"),
        "mental_models": list_vault_notes("mental_models"),
        "counts": {
            "decisions": len(list((vault / "decisions").glob("*.md"))),
            "patterns": len(list((vault / "patterns").glob("*.md"))),
            "mental_models": len(list((vault / "mental_models").glob("*.md"))),
        },
    }


def write_mental_model(title: str, content: str):
    _ensure_vault_structure()
    folder = get_mind_vault_path() / "mental_models"
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    path = folder / f"{safe_title}.md"
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write(f"# {title}\n\n*Recorded: {datetime.now().strftime('%Y-%m-%d')}*\n\n{content}")
    log(f"Wrote mental model: {title}", system="MIND_VAULT")


def log_decision_to_vault(decision: str, reasoning: str, domain: str):
    _ensure_vault_structure()
    folder = get_mind_vault_path() / "decisions"
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_domain = "".join(c for c in domain if c.isalnum() or c in "-_ ").strip() or "general"
    path = folder / f"{date_str}-{safe_domain}.md"
    entry = (
        f"\n## {datetime.now().strftime('%H:%M')}\n"
        f"**Decision:** {decision}\n"
        f"**Reasoning:** {reasoning}\n\n"
    )
    with open(path, "a", encoding="utf-8") as file_obj:
        file_obj.write(entry)
    log(f"Decision logged to Mind Vault: {safe_domain}", system="MIND_VAULT")


def update_self_model(new_insight: str):
    _ensure_vault_structure()
    self_model_path = get_mind_vault_path() / "self_model.md"
    with open(self_model_path, "a", encoding="utf-8") as file_obj:
        file_obj.write(f"\n## Insight - {datetime.now().strftime('%Y-%m-%d')}\n{new_insight}\n")
    log(f"Self model updated: {new_insight[:80]}", system="MIND_VAULT")
