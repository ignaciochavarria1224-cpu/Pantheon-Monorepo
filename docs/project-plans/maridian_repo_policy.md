# Maridian Repo Policy

This document defines how Maridian should be organized inside the repository before deeper implementation work begins.

It exists to answer three practical questions:

1. what belongs in the repo
2. what should stay local/private
3. what must be planned before code changes begin

## Current Planning State

Maridian already has:

- a repo-level vision document
- a repo-level build plan
- a locked canonical app path
- a locked canonical vault path

That means Maridian is no longer missing its strategic layer.

What remains is implementation planning and careful boundary-setting.

## Canonical Paths

- Maridian app and Pantheon control surface:
  `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\apps\maridian`
- Maridian canonical vault:
  `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\data\maridian-vault`

## What Maridian Must Own

Maridian should own:

- journal writing
- cycle execution
- question generation
- summaries and insights
- generated notes/cards
- wiki/index outputs
- personal-memory structures Apollo will later consume

BlackBook should not remain the owner of reflective journaling.

## Git Boundary

Not every Maridian file should automatically be pushed to GitHub.

### Good candidates to track in Git

- code
- schemas
- prompts and agents
- non-sensitive config templates
- wiki structure rules
- planning docs
- empty/example folders where needed

### Likely local/private by default

- raw personal journal entries
- generated personal notes containing sensitive content
- local `.env`
- embeddings or derived personal vector files
- machine-specific control files if they expose private context

## Recommended Tracking Model

Use a split model:

- repo tracks the Maridian system structure and code
- local vault holds the private personal content unless you explicitly choose otherwise

This keeps the system organized without accidentally publishing personal memory.

## Planning-Only Priorities Before Code Changes

Before implementation starts, the planning layer should stay clear on these items:

1. Maridian owns journaling, not BlackBook
2. Pantheon is the control surface
3. Obsidian reads the same canonical vault
4. Apollo should consume processed Maridian outputs, not raw journals first
5. Git tracking for personal content must be intentional

## First Implementation Milestones

When implementation starts, the first milestones should be:

1. define what vault files remain local/private
2. define what safe subset, if any, is committed to Git
3. remove journal ownership from BlackBook at the planning/interface level
4. wire the Pantheon Maridian tab to the canonical vault
5. add journal entry + run-cycle controls

## Final Position

Maridian is now strategically defined.

The next work is not inventing what Maridian is.
The next work is enforcing clean ownership, privacy boundaries, and execution order so the implementation stays organized.
