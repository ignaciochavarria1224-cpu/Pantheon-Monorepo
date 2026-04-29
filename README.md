# AI Projects Monorepo

This repository is a consolidation of projects from:

- `C:\Users\ignac\Documents\AI PROJECTS`
- `C:\Users\ignac\Dropbox`

The repo was assembled into one clean git root so the original folders remain untouched.

## Layout

- `active/` contains the current working project folders.
- `archive/` contains backup or staging folders that were worth keeping but should not be treated as the primary source of truth.

## Source Selection Notes

- `active/Olympus-Trading` was copied from `AI PROJECTS\Olympus Trading` because the Dropbox path existed as a reparse-point placeholder and did not expose a normal file listing.
- `active/Pantheon` is the live working copy from `AI PROJECTS\Pantheon` and includes local uncommitted work present at consolidation time.
- `active/BlackBook` is only partially complete because several Dropbox Smart Sync files could not be read locally during the copy.

## Safety Notes

- Nested `.git` folders were excluded so this repo behaves as one repository.
- Obvious generated folders like `node_modules`, `dist`, `build`, `venv`, `.venv`, `.next`, and `__pycache__` were excluded from the copy.
- Local secrets and runtime session state such as `.env`, `.states`, auth sessions, and copied log folders were removed from the consolidated repo.

## Next Steps

1. Review `INVENTORY.md`.
2. Check `active/BlackBook` and decide whether to hydrate the missing Dropbox files before the GitHub push.
3. Create or choose a remote GitHub repo and push this repository there.
