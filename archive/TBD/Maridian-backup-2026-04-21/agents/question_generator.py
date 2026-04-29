# agents/question_generator.py
"""
Generate 3 permanent fitness questions + 4 dynamic questions from wiki/ pages.

Question sources (dynamic):
1. Underrepresented themes (low entry count) → gap questions to explore them
2. Themes marked "Still forming" → probe deeper
3. Active high-entry themes → push existing threads further
"""
import json
from pathlib import Path
from datetime import date
from utils.llm import llm_call
from utils.vault import VAULT_ROOT
from db.neon_bridge import push_questions

WIKI_DIR = VAULT_ROOT / "wiki"
QUESTIONS_DIR = VAULT_ROOT / "Questions"
HISTORY_FILE = QUESTIONS_DIR / "history.md"

# These 3 appear permanently at the top — always pushed with every cycle.
FITNESS_QUESTIONS = [
    {"question": "Did I go to the gym today?",         "type": "fitness", "permanent": True},
    {"question": "Did I wake up on time?",             "type": "fitness", "permanent": True},
    {"question": "Did I eat enough and/or good food?", "type": "fitness", "permanent": True},
]

GAP_SYSTEM = """Write one short journal prompt under 12 words. Direct. Conversational.
The prompt explores a theme the writer has touched but not deeply developed.
No "reflect on", "explore", or "delve into". Write like a sharp friend asking a real question.

Format:
QUESTION: [under 12 words]
CONTEXT: [under 10 words: why this gap matters now]"""

THREAD_SYSTEM = """Write one short journal prompt to push a belief further. Under 12 words.
Pick an angle not yet covered in the notes. First person. Blunt and direct.
No therapy-speak, no academic language.

Format:
QUESTION: [under 12 words]
CONTEXT: [under 10 words: what angle to push]"""


def _read_wiki_pages() -> list:
    """Return list of {theme, body, entry_count, last_updated, still_forming} dicts."""
    pages = []
    if not WIKI_DIR.exists():
        return pages
    for f in WIKI_DIR.glob("*.md"):
        if f.name.startswith(".") or f.name == "INDEX.md":
            continue
        raw = f.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        fm = {}
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = parts[2].strip()
        else:
            body = raw.strip()
        pages.append({
            "theme": fm.get("theme", f.stem),
            "entry_count": int(fm.get("entry_count", 0)),
            "last_updated": fm.get("last_updated", ""),
            "body": body,
            "still_forming": "Still forming" in body,
        })
    return pages


def _get_recent_questions(n_days: int = 7) -> list:
    recent = []
    if not QUESTIONS_DIR.exists():
        return recent
    for f in sorted(QUESTIONS_DIR.glob("*.md"), reverse=True)[:n_days]:
        if f.name == "history.md":
            continue
        try:
            content = json.loads(f.read_text())
            recent.extend(q.get("question", "") for q in content.get("questions", []))
        except Exception:
            pass
    return recent


def _parse_q_c(raw: str) -> tuple:
    q_line = next((l for l in raw.split("\n") if l.startswith("QUESTION:")), "")
    c_line = next((l for l in raw.split("\n") if l.startswith("CONTEXT:")), "")
    return q_line.replace("QUESTION:", "").strip(), c_line.replace("CONTEXT:", "").strip()


def _save_and_push(dynamic_questions: list, vault_state: dict, auto_push: bool) -> None:
    today = str(date.today())
    QUESTIONS_DIR.mkdir(exist_ok=True)
    q_file = QUESTIONS_DIR / f"{today}.md"
    q_file.write_text(
        json.dumps({"date": today, "questions": dynamic_questions}, indent=2),
        encoding="utf-8",
    )
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    q_texts = [q.get("question", "")[:60] for q in dynamic_questions]
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"| {today} | " + " | ".join(q_texts) + " |\n")
    if auto_push:
        push_questions(FITNESS_QUESTIONS + dynamic_questions, today)
    vault_state["last_questions_generated"] = today


def generate(vault_state: dict, theme_entries: dict = None, auto_push: bool = True) -> list:
    print("[QUESTIONS] Generating 4 dynamic questions from wiki...")
    pages = _read_wiki_pages()
    recent_qs = _get_recent_questions(7)
    questions = []

    if not pages:
        print("  [QUESTIONS] No wiki pages yet — pushing fitness questions only.")
        _save_and_push([], vault_state, auto_push)
        return []

    # Sort by entry count ascending (least-explored first)
    pages_by_gap = sorted(pages, key=lambda p: p["entry_count"])
    forming = [p for p in pages if p["still_forming"]]
    active = sorted(pages, key=lambda p: p["entry_count"], reverse=True)

    used_themes = set()

    # Source 1: Gap questions — themes with fewest entries (up to 2)
    for page in pages_by_gap:
        if len(questions) >= 2:
            break
        if page["theme"] in used_themes:
            continue
        try:
            raw = llm_call(
                "llama3.2", GAP_SYSTEM,
                f"Theme: {page['theme']}\n"
                f"Only {page['entry_count']} journal entries written about this.\n"
                f"What's been said so far:\n{page['body'][:400]}",
                temperature=0.7,
            )
            q, c = _parse_q_c(raw)
            if q and q not in recent_qs:
                questions.append({"question": q, "context": c,
                                  "source": "gap", "theme": page["theme"], "type": "dynamic"})
                used_themes.add(page["theme"])
        except Exception as e:
            print(f"  Gap question failed ({page['theme']}): {e}")

    # Source 2: Still-forming probes (up to 2)
    for page in forming:
        if len(questions) >= 4:
            break
        if page["theme"] in used_themes:
            continue
        try:
            raw = llm_call(
                "llama3.2", THREAD_SYSTEM,
                f"Theme: {page['theme']} — still forming, not yet resolved.\n"
                f"What's been written:\n{page['body'][:500]}",
                temperature=0.7,
            )
            q, c = _parse_q_c(raw)
            if q and q not in recent_qs:
                questions.append({"question": q, "context": c,
                                  "source": "forming", "theme": page["theme"], "type": "dynamic"})
                used_themes.add(page["theme"])
        except Exception as e:
            print(f"  Forming question failed ({page['theme']}): {e}")

    # Source 3: Thread questions from active themes (fill to 4)
    for page in active:
        if len(questions) >= 4:
            break
        if page["theme"] in used_themes:
            continue
        try:
            raw = llm_call(
                "llama3.2", THREAD_SYSTEM,
                f"Theme: {page['theme']} ({page['entry_count']} entries)\n"
                f"Wiki page:\n{page['body'][:500]}",
                temperature=0.7,
            )
            q, c = _parse_q_c(raw)
            if q and q not in recent_qs:
                questions.append({"question": q, "context": c,
                                  "source": "thread", "theme": page["theme"], "type": "dynamic"})
                used_themes.add(page["theme"])
        except Exception as e:
            print(f"  Thread question failed ({page['theme']}): {e}")

    dynamic_questions = questions[:4]
    _save_and_push(dynamic_questions, vault_state, auto_push)
    print(f"[QUESTIONS] Done. 3 fitness + {len(dynamic_questions)} dynamic questions pushed.")
    return dynamic_questions
