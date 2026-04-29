# agents/brain_builder.py
"""
Karpathy Wiki Builder — Meridian's librarian agent.

Reads all raw/ journal entries, classifies themes, builds and maintains
wiki/[Theme].md pages and wiki/INDEX.md.

Key design:
- wiki/.classifications.json caches theme assignments so entries aren't re-classified
- Each wiki page is rebuilt fresh when the cache is updated
- The LLM acts as librarian, not creator — all content traces back to raw entries
"""

import json
from pathlib import Path
from datetime import date
from utils.llm import llm_call
from utils.vault import VAULT_ROOT

RAW_DIR = VAULT_ROOT / "raw"
WIKI_DIR = VAULT_ROOT / "wiki"
CLASSIFICATIONS_FILE = WIKI_DIR / ".classifications.json"

# Minimum entries touching a theme before we build a page for it
MIN_ENTRIES_FOR_PAGE = 2

CLASSIFY_SYSTEM = """\
You are classifying a personal journal entry into themes.
Return ONLY a JSON array of 1-3 theme names. Nothing else — no explanation, no preamble.

Theme names must be short (1-3 words), title-case. Examples:
["Money & Trading", "Faith", "Friendship", "Ambition", "Family", "Identity", "Health",
 "Discipline", "Trust", "Self-Worth", "Entrepreneurship", "Cultural Identity"]

Use existing theme names from the provided list when they fit.
Only create a new theme name if nothing in the list fits well.
"""

WIKI_PAGE_SYSTEM = """\
You are writing a wiki page about one theme from a person's journals.
The person is Ignacio — ~18-19, finance student at FSU, Uruguayan-American from Miami.
He has been journaling since 2022. Early journals: faith, friendship, trust.
Later journals: ambition, trading, entrepreneurship.

Write using EXACTLY this format. No preamble, no extra commentary:

## {theme}

**Core Belief:**
[1-2 sentences. First person ("I know...", "I believe...", "I've learned...").
The single most fundamental thing extracted from these entries.
Specific — not generic. No hedging.]

**How This Evolved:**
[Include ONLY if entries clearly span different years AND show meaningful change.
If not enough data: write exactly "Still forming."
If there IS clear evolution, format as bullet points:
- [Year]: [what shifted in his thinking]]

**In His Own Words:**
> "[exact or near-exact quote — the most striking sentence from the entries]"

**Connected Themes:** [[Theme1]] [[Theme2]]
[Pick 1-3 themes from the connected themes list only. These become Obsidian graph edges.]

Rules:
- Every claim must come directly from the provided journal entries
- Do NOT summarize or editorialize — extract and distill
- The quote must be near-verbatim, not paraphrased
- Keep it concise — 150-250 words total
"""

INDEX_SYSTEM = """\
You are writing the master INDEX for the Meridian wiki — a structured profile of Ignacio,
extracted entirely from his journals.

Ignacio is ~18-19, finance student at FSU, Uruguayan-American from Miami.
He started journaling in 2022. Early: faith, friendship, trust. Later: ambition, trading, entrepreneurship.

Write using EXACTLY this format. No preamble:

# Meridian Index

**Last updated:** {today}
**Entries in wiki:** {total_entries}
**Themes mapped:** {theme_count}

---

## Who Is Ignacio?
[3-4 sentences. Third person. Specific — name actual themes and real tensions from the data.
What drives him? What has changed since 2022? No generic language.]

## Core Themes
[One line per theme. Format: **[[Theme]]** — [one sentence: what this specifically means for him]]

## Active Tensions
[2-3 bullets. Real contradictions visible across the journals. Still unresolved.
Format: • [what pulls against what in his thinking]]

## How He Thinks
[3-4 bullets. Specific patterns in his writing and reasoning you can observe.
Format: • [concrete observation]]

---
*Built by Meridian from {total_entries} raw journal entries.*
"""


def _load_classifications() -> dict:
    if CLASSIFICATIONS_FILE.exists():
        return json.loads(CLASSIFICATIONS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_classifications(data: dict) -> None:
    CLASSIFICATIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_raw_file(path: Path) -> dict:
    """Parse a raw/ markdown file into {id, date, tag, body}."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    fm = {}
    if len(parts) >= 3:
        for line in parts[1].strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        body = parts[2].strip()
    else:
        body = text.strip()
    return {
        "id": fm.get("id", path.stem),
        "date": fm.get("date", ""),
        "tag": fm.get("tag", ""),
        "body": body,
        "path": str(path),
    }


def _classify_entry(entry: dict, known_themes: list) -> list:
    """Ask LLM to classify entry into 1-3 themes. Returns list of theme strings."""
    themes_hint = ""
    if known_themes:
        themes_hint = f"\nExisting themes (reuse if they fit): {json.dumps(known_themes[:20])}"
    try:
        raw = llm_call(
            "llama3.2",
            CLASSIFY_SYSTEM,
            f"Date: {entry['date']}\nTag: {entry['tag']}{themes_hint}\n\nEntry:\n{entry['body'][:600]}",
            temperature=0.2,
        )
        raw = raw.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            themes = json.loads(raw[start:end])
            if isinstance(themes, list):
                return [str(t).strip() for t in themes if t]
    except Exception as e:
        print(f"  [WIKI] Classify failed for {entry['id']}: {e}")
    return ["General"]


def _build_wiki_page(theme: str, entries: list, all_themes: list) -> bool:
    """Build or rebuild a single wiki page for a theme from its raw entries."""
    WIKI_DIR.mkdir(exist_ok=True)
    page_file = WIKI_DIR / f"{theme}.md"

    # Sort by date, use up to 10 entries
    entries_sorted = sorted(entries, key=lambda e: e.get("date", ""))
    snippets = []
    for e in entries_sorted[:10]:
        d = e.get("date", "?")
        tag = e.get("tag", "")
        body = e["body"][:500].strip()
        snippets.append(f"[{d}] [{tag}]\n{body}")
    entries_context = "\n\n---\n\n".join(snippets)

    other_themes = [t for t in all_themes if t != theme]
    prompt = WIKI_PAGE_SYSTEM.format(theme=theme)

    try:
        content = llm_call(
            "llama3.2",
            prompt,
            f"Connected themes available: {', '.join(other_themes[:12])}\n\n"
            f"Entries about '{theme}' ({len(entries)} total):\n\n{entries_context}",
            temperature=0.3,
        )
        frontmatter = (
            f"---\n"
            f"theme: {theme}\n"
            f"entry_count: {len(entries)}\n"
            f"last_updated: {date.today().isoformat()}\n"
            f"---\n\n"
        )
        page_file.write_text(frontmatter + content.strip() + "\n", encoding="utf-8")
        return True
    except Exception as e:
        print(f"  [WIKI] Page build failed for '{theme}': {e}")
        return False


def _build_index(theme_entries: dict, total_entries: int) -> None:
    """Build wiki/INDEX.md — the master profile across all themes."""
    theme_summaries = []
    for theme, entries in sorted(theme_entries.items(), key=lambda x: len(x[1]), reverse=True):
        page = WIKI_DIR / f"{theme}.md"
        if not page.exists():
            continue
        raw = page.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        body = parts[2].strip() if len(parts) > 2 else raw
        theme_summaries.append(f"**{theme}** ({len(entries)} entries):\n{body[:400]}")

    context = "\n\n".join(theme_summaries[:12])
    prompt = INDEX_SYSTEM.format(
        today=date.today().isoformat(),
        total_entries=total_entries,
        theme_count=len(theme_entries),
    )

    try:
        content = llm_call(
            "llama3.2",
            prompt,
            f"Theme summaries:\n\n{context}",
            temperature=0.3,
        )
        frontmatter = (
            f"---\n"
            f"type: index\n"
            f"last_updated: {date.today().isoformat()}\n"
            f"total_entries: {total_entries}\n"
            f"theme_count: {len(theme_entries)}\n"
            f"---\n\n"
        )
        (WIKI_DIR / "INDEX.md").write_text(frontmatter + content.strip() + "\n", encoding="utf-8")
        print("  [WIKI] INDEX.md built.")
    except Exception as e:
        print(f"  [WIKI] INDEX build failed: {e}")


def build_wiki(vault_state: dict) -> dict:
    """
    Main entry point. Returns theme_entries dict (used by question_generator).

    Steps:
    1. Read all raw/ files
    2. Classify any unclassified entries (results cached in wiki/.classifications.json)
    3. Group entries by theme
    4. Build/update wiki pages for qualified themes
    5. Build INDEX.md
    """
    print("[WIKI] Building wiki from raw/ entries...")

    if not RAW_DIR.exists() or not list(RAW_DIR.glob("*.md")):
        print("  [WIKI] No raw entries yet. Skipping.")
        return {}

    WIKI_DIR.mkdir(exist_ok=True)
    classifications = _load_classifications()  # {entry_id: [theme, ...]}

    raw_files = sorted(RAW_DIR.glob("*.md"))
    entries = [_read_raw_file(f) for f in raw_files]

    known_themes = list({t for themes in classifications.values() for t in themes})
    new_classifications = 0

    for entry in entries:
        entry_id = str(entry["id"])
        if entry_id not in classifications:
            themes = _classify_entry(entry, known_themes)
            classifications[entry_id] = themes
            for t in themes:
                if t not in known_themes:
                    known_themes.append(t)
            new_classifications += 1

    if new_classifications > 0:
        _save_classifications(classifications)
        print(f"  [WIKI] Classified {new_classifications} new entries.")

    # Group entries by theme
    theme_entries: dict = {}
    for entry in entries:
        entry_id = str(entry["id"])
        for theme in classifications.get(entry_id, ["General"]):
            theme_entries.setdefault(theme, []).append(entry)

    all_themes = list(theme_entries.keys())
    print(f"  [WIKI] {len(all_themes)} themes across {len(entries)} entries.")

    # Build wiki pages — themes with enough entries
    qualified = {t: e for t, e in theme_entries.items() if len(e) >= MIN_ENTRIES_FOR_PAGE}
    if not qualified and theme_entries:
        qualified = theme_entries  # vault is brand new — build all regardless

    built = []
    for theme, t_entries in sorted(qualified.items(), key=lambda x: len(x[1]), reverse=True):
        ok = _build_wiki_page(theme, t_entries, all_themes)
        if ok:
            built.append(theme)
            print(f"  [WIKI] {theme} ({len(t_entries)} entries)")

    if built:
        built_entries = {t: theme_entries[t] for t in built if t in theme_entries}
        _build_index(built_entries, len(entries))

    vault_state["wiki_last_built"] = date.today().isoformat()
    vault_state["wiki_pages"] = built
    print(f"[WIKI] Done. {len(built)} wiki pages + INDEX built in wiki/.")
    return theme_entries
