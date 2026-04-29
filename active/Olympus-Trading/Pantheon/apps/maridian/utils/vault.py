# utils/vault.py
import os
import re
import uuid
from datetime import date
from pathlib import Path
import yaml

_env_vault = os.environ.get("MARIDIAN_VAULT_PATH")
VAULT_ROOT = Path(_env_vault) if _env_vault else Path(__file__).parent.parent

FINAL_FOLDERS = {
    "seed":      VAULT_ROOT / "00-Seeds",
    "sprout":    VAULT_ROOT / "01-Sprouts",
    "tree":      VAULT_ROOT / "02-Trees",
    "framework": VAULT_ROOT / "Frameworks",
    "archive":   VAULT_ROOT / "Archive",
}

STAGING_FOLDERS = {
    "seed":   VAULT_ROOT / "staging" / "00-Seeds",
    "sprout": VAULT_ROOT / "staging" / "01-Sprouts",
    "tree":   VAULT_ROOT / "staging" / "02-Trees",
}

STAGE_THRESHOLDS = {
    "seed":   (0,  20),
    "sprout": (21, 59),
    "tree":   (60, 99),
}

# Canonical domain list — built from Ignacio's journal topics
CANONICAL_DOMAINS = {
    "identity", "ambition", "relationships", "money-mindset",
    "earned-love", "compounding", "failure-processing", "discipline",
    "self-perception", "entrepreneurship", "cultural-identity",
    "friendship", "urgency", "legacy", "creativity", "learning-systems",
    "trust", "consistency", "risk-tolerance", "patience",
    "self-worth", "comparison", "momentum", "solitude",
    "gratitude", "fear", "growth-metaphors", "time-perception",
    "systems-thinking", "game-theory", "compounding-relationships",
    "attention-economics", "identity-debt", "emotional-leverage",
    "signal-vs-noise", "optionality", "asymmetric-returns",
    "network-effects-in-trust", "activation-energy-personal",
    "mean-reversion-in-behavior", "narrative-vs-data",
    "deep-work-vs-shallow-presence", "skin-in-the-game",
    "first-principles-identity", "inversion-thinking",
    "black-swan-in-relationships", "antifragility-personal",
    "family-dynamics",
}


def canonicalize_domain(raw: str) -> str:
    """Convert a raw domain string to canonical kebab-case."""
    slug = re.sub(r'[^a-z0-9]+', '-', raw.lower().strip()).strip('-')
    if slug in CANONICAL_DOMAINS:
        return slug
    # fuzzy match: return best match if distance is small enough
    for canon in CANONICAL_DOMAINS:
        if slug in canon or canon in slug:
            return canon
    return slug


def generate_id(prefix: str = "note") -> str:
    short = uuid.uuid4().hex[:6]
    return f"{prefix}_{short}"


def get_stage(maturity: int) -> str:
    if maturity <= 20:
        return "seed"
    if maturity <= 59:
        return "sprout"
    return "tree"


def default_frontmatter(note_id: str, generation: int = 1, domains: list = None,
                        parent_ids: list = None, source_entry_ids: list = None,
                        entry_date_range: str = "") -> dict:
    return {
        "id": note_id,
        "title": "",
        "maturity": 0,
        "generation": generation,
        "fitness": None,
        "domains": domains or [],
        "parent_ids": (parent_ids or [])[:4],
        "source_entry_ids": source_entry_ids or [],
        "entry_date_range": entry_date_range,
        "last_mutated": str(date.today()),
        "dna_injected": False,
        "dna_injection_count": 0,
        "flagged_for_pruning": False,
        "debate_count": 0,
        "framework_eligible": False,
        "published": False,
        "wikilink_count": 0,
    }


def serialize_frontmatter(fm: dict) -> str:
    return yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)


def write_note(frontmatter: dict, body: str, stage: str,
               filename: str, staging: bool = False) -> Path:
    if staging and stage in STAGING_FOLDERS:
        folder = STAGING_FOLDERS[stage]
    else:
        folder = FINAL_FOLDERS.get(stage, FINAL_FOLDERS["seed"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    content = f"---\n{serialize_frontmatter(frontmatter)}---\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    return path


def read_note(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip() if len(parts) > 2 else ""
        else:
            fm = {}
            body = text.strip()
        return {"path": path, "frontmatter": fm, "body": body}
    except Exception:
        return None


def update_frontmatter(path: Path, updates: dict):
    note = read_note(path)
    if not note:
        return
    fm = note["frontmatter"]
    fm.update(updates)
    write_note(fm, note["body"], get_stage(fm.get("maturity", 0)), path.name, staging=False)


def count_wikilinks(body: str) -> int:
    return len(re.findall(r'\[\[.+?\]\]', body))


def get_all_notes(folders: list = None) -> list:
    if folders is None:
        folders = list(FINAL_FOLDERS.values())
    notes = []
    for folder in folders:
        if folder.exists():
            for f in folder.glob("*.md"):
                if f.name.startswith("index") or f.name.startswith("flagged") or f.name.startswith("lineage"):
                    continue
                n = read_note(f)
                if n:
                    notes.append(n)
    return notes
