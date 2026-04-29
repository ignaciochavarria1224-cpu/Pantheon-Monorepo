# Maridian Privacy Boundary

This document defines the file-level privacy boundary for Maridian.

It exists because the canonical Maridian vault now lives locally at:

- `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\data\maridian-vault`

That vault contains both:

- system structure that helps the repo stay understandable
- highly personal runtime content that should stay local

This document turns the general Maridian repo policy into a concrete rule set.

## Core Rule

The Maridian vault is local-first by default.

That means:

- files are assumed private unless there is a strong reason to track them
- GitHub is not the home of your raw reflective memory
- Git tracking for Maridian should be selective and intentional

## Canonical Local Vault

The canonical local Maridian vault is:

- `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\data\maridian-vault`

Obsidian reads this same vault directly.

## Track In GitHub

These are good candidates to track in GitHub because they define how Maridian works rather than exposing your private reflective content.

### Code And System Logic

- `control.py`
- `evolve.py`
- `import_chatgpt.py`
- `p2.py`
- `reset_meridian.py`
- `agents/`
- `db/`
- `utils/`

### Documentation And System Structure

- `README.md`
- `MERIDIAN.md`
- `.gitignore`

### Safe Schema-Like State

- `vault_state.json`
  Track only if you are comfortable versioning cycle counts and processing metadata.
  If that feels too runtime-specific later, move it back to local-only.

## Keep Local By Default

These should stay local/private by default and should not be treated as normal GitHub content.

### Highly Personal Reflective Content

- `raw/`
- `wiki/`
- `Questions/`
- generated notes/cards
- summaries and insights derived from personal writing

These are the heart of Maridian's personal-memory layer and should remain local unless you explicitly decide otherwise later.

### Secrets And Machine-Bound Files

- `.env`
- `.claude/`
- machine-specific caches
- embeddings or vector-derived personal artifacts if added later

### Obsidian Local Configuration

- `.obsidian/workspace.json`
- `.obsidian/graph.json`

These are local workspace/view state and should remain local.

## Obsidian Partial Exception

Not every `.obsidian` file is equal.

The default safest rule is:

- keep `.obsidian/` local

If later you want stable shared vault behavior across devices, you can reconsider a few non-sensitive config files selectively.

But for now, do not track `.obsidian` contents by default.

## Practical Folder Classification

Here is the recommended first-pass classification for the current Maridian vault:

- `agents/` -> track
- `db/` -> track
- `utils/` -> track
- `control.py` -> track
- `evolve.py` -> track
- `import_chatgpt.py` -> track
- `p2.py` -> track
- `reset_meridian.py` -> track
- `README.md` -> track
- `MERIDIAN.md` -> track
- `.gitignore` -> track
- `vault_state.json` -> review case-by-case, tentatively local
- `raw/` -> local
- `wiki/` -> local
- `Questions/` -> local
- `.env` -> local
- `.claude/` -> local
- `.obsidian/` -> local

## Founder Rule

If a Maridian file helps explain the system, build the system, or reproduce the system, it is a good candidate for GitHub.

If a Maridian file reveals your private thoughts, processed memory, daily reflective content, or machine-specific usage state, it should stay local.

## Immediate Planning Outcome

This means the next organization pass should treat Maridian as two layers:

1. `system layer`
   code, structure, schemas, docs
2. `memory layer`
   raw journals, generated personal outputs, private reflective state

GitHub should mainly track the system layer.
The local vault should remain the home of the memory layer.

## Final Position

Maridian should absolutely live inside the repo structure.

But that does not mean every file inside the Maridian vault belongs on GitHub.

The system should be versioned.
The private mind should stay local by default.
