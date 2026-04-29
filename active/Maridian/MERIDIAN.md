# MERIDIAN.md — Vault Schema

This file describes the Maridian vault structure and thinking model.

Older parts of this document still reflect a Neon/BlackBook sourcing model from an earlier system design.
The current strategic direction is:

- Pantheon-local Maridian ownership
- a canonical local vault
- direct Obsidian access to that canonical vault
- Maridian as the primary journaling home over time

## What Meridian Is

Meridian is a personal wiki built from Ignacio's journals using the Karpathy pattern.
The LLM acts as a librarian — organizing and synthesizing, never inventing.

**The current intended pipeline:**
```
Pantheon Maridian journal input
       ↓
  raw/           ← immutable source files, one per entry, never modified
       ↓
  wiki/           ← LLM-maintained theme pages, rebuilt each cycle
       ↓
  Questions/      ← current adaptive question outputs
  Apollo / Pantheon consumption layers
```

---

## Directory Structure

```
raw/
  YYYYMMDD_[id]_[tag_slug].md    ← one file per journal entry
  (immutable — never modified after writing)

wiki/
  .classifications.json          ← cache: {entry_id: [theme, theme, ...]}
  INDEX.md                       ← master profile (who is Ignacio)
  [Theme Name].md                ← one page per theme (e.g. "Ambition.md")

Questions/
  YYYY-MM-DD.md                  ← daily dynamic questions (JSON)
  history.md                     ← append-only log of all generated questions
```

---

## Who Is Ignacio (LLM Context)

- Age ~18-19, finance student at Florida State University (FSU)
- Uruguayan-American, raised in Miami
- Started journaling in 2022 (via ChatGPT conversations)
- Early journals (2022-2023): faith, friendship, trust, family dynamics
- Later journals (2024-2025): ambition, money, trading, entrepreneurship
- Building: Olympus (trading system), Black Book (personal journal app), Meridian (this)
- Voice: direct, introspective, uses first person freely, sometimes raw/unfiltered

---

## Wiki Page Format

Each `wiki/[Theme].md` follows this structure:

```markdown
---
theme: [Theme Name]
entry_count: [n]
last_updated: YYYY-MM-DD
---

## [Theme Name]

**Core Belief:**
[1-2 sentences, first person, specific to Ignacio's journals]

**How This Evolved:**
[Bullet points by year if clear evolution exists, otherwise: "Still forming."]

**In His Own Words:**
> "[near-verbatim quote from a journal entry]"

**Connected Themes:** [[Theme1]] [[Theme2]]
```

**Rules:**
- Every claim traces back to a `raw/` entry
- Quotes are near-verbatim, not paraphrased
- Connected themes use `[[wikilink]]` syntax — these create Obsidian graph edges
- "Still forming." is the only placeholder allowed

---

## INDEX.md Format

`wiki/INDEX.md` is the master profile. It contains:
- Who Is Ignacio? (3-4 sentences, third person, specific)
- Core Themes (one line per theme with wikilinks)
- Active Tensions (2-3 unresolved contradictions)
- How He Thinks (3-4 observable reasoning patterns)

---

## Historical Shared Tables

| Table | Purpose |
|---|---|
| `journal_entries` | Earlier shared journal-entry source path |
| `meridian_questions` | Earlier shared question-distribution path |
| `meridian_brain` | Earlier shared wiki-sync path |
| `meridian_jobs` | Earlier shared trigger path |
| `meridian_notes` | Legacy table (unused in wiki mode) |

---

## Cycle Phases

**Phase 1 — Extract**
- `agents/journal_extractor.py`
- Pulls new entries from the current source journal path
- Writes each as `raw/YYYYMMDD_[id]_[tag].md`
- Tracks processed IDs in `vault_state.json`

**Phase 2 — Build Wiki**
- `agents/brain_builder.py`
- Classifies each raw entry into themes via LLM
- Caches classifications in `wiki/.classifications.json`
- Builds/updates one `wiki/[Theme].md` per qualified theme
- Builds `wiki/INDEX.md`

**Phase 3 — Questions & Sync**
- `agents/question_generator.py`
- Reads wiki pages, generates dynamic questions
- makes questions available to the surrounding system
- exposes processed outputs for Pantheon and Apollo consumption

---

## vault_state.json Schema

```json
{
  "cycle_count": 0,
  "processed_entry_ids": [],
  "total_entries_processed": 0,
  "last_entry_date_processed": null,
  "last_cycle": null,
  "last_questions_generated": null,
  "wiki_last_built": null,
  "wiki_pages": []
}
```
