# All Olympus

This repository is the consolidated home for the projects that were previously split across:

- `C:\Users\ignac\Documents\AI PROJECTS`
- `C:\Users\ignac\Dropbox`

The goal of this repo is simple: keep the current source trees in one place, preserve important backup material, and make future organization easier.

## Repository Layout

- `active/` contains the main working copies of the projects you are actively building or referencing.
- `archive/` contains backup, staging, or transitional folders that were worth preserving but should not be treated as the primary working source.
- `INVENTORY.md` documents where each imported folder came from and calls out known gaps from the consolidation.

## Active Projects

- `Apollo`
- `BlackBook`
- `deer-flow`
- `Maridian`
- `MetaGPT`
- `oh-my-claudecode`
- `Olympus-Trading`
- `Pantheon`

## What Was Cleaned Up

- Nested `.git` directories were excluded so this repository behaves as one clean git repo.
- Generated or rebuildable folders such as `node_modules`, `dist`, `build`, `venv`, `.venv`, `.next`, and `__pycache__` were not imported.
- Copied `.env` files, local session/auth folders, and log/state directories were removed from the consolidated repo before commit.

## Important Notes

- `Olympus-Trading` was sourced from the local `AI PROJECTS` copy because the Dropbox version behaved like a placeholder path instead of a normal folder listing.
- `Pantheon` reflects the live local working copy present at the time of consolidation, including local uncommitted work that existed in that folder.
- `BlackBook` has a few missing files because Dropbox Smart Sync did not expose them locally during the import; those missing paths are listed in `INVENTORY.md`.

## Recommended Workflow

1. Treat `active/` as the main place for ongoing work.
2. Use `archive/` only as preserved reference material.
3. Review `INVENTORY.md` before deleting or moving any of the original local folders.
