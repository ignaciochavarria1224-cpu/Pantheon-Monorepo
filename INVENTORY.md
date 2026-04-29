# Consolidation Inventory

Generated on 2026-04-29 from the local machine.

## Included Active Projects

This inventory is a historical consolidation snapshot from the first assembly pass on 2026-04-29.

It is useful for tracking where folders originally came from, but it is not the current architecture source of truth.

For current canonical paths, subsystem ownership, and present-day planning status, use:

- `docs/project-plans/repo_status_tracker.md`
- `docs/project-plans/source_of_truth_framework.md`
- `docs/project-plans/source_of_truth_policy.md`

| Folder | Source | Notes | Approx. copied files |
| --- | --- | --- | ---: |
| `active/Apollo` | `C:\Users\ignac\Dropbox\Apollo` | Copied without nested git metadata; runtime auth/session data removed. | 14 |
| `active/BlackBook` | `C:\Users\ignac\Dropbox\BlackBook` | Historical import source only. BlackBook has since been replaced in-place by the canonical local Streamlit version and the older Reflex copy was archived. | 72 |
| `active/deer-flow` | `C:\Users\ignac\Documents\AI PROJECTS\deer-flow` | Existing git repo copied in as plain files. | 1040 |
| `active/Maridian` | `C:\Users\ignac\Dropbox\Maridian` | Historical import source only. Maridian is now planned as Pantheon-local, with the canonical vault path under `active/Pantheon/data/maridian-vault`. | 433 |
| `active/MetaGPT` | `C:\Users\ignac\Documents\AI PROJECTS\MetaGPT` | Existing git repo copied in as plain files. | 1255 |
| `active/oh-my-claudecode` | `C:\Users\ignac\Documents\AI PROJECTS\oh-my-claudecode` | Existing git repo copied in as plain files. | 1422 |
| `active/Olympus-Trading` | `C:\Users\ignac\Documents\AI PROJECTS\Olympus Trading` | Used local AI PROJECTS copy because the Dropbox folder behaved like a placeholder. | 5128 |
| `active/Pantheon` | `C:\Users\ignac\Documents\AI PROJECTS\Pantheon` | Live working copy including local changes present at time of consolidation. | 659 |

## Included Archive Folders

| Folder | Source | Notes | Approx. copied files |
| --- | --- | --- | ---: |
| `archive/Pantheon_Backup_2026-04-18` | `C:\Users\ignac\Dropbox\Pantheon_Backup_2026-04-18` | Backup snapshot copied as-is where local Dropbox content was readable. | 9 |
| `archive/TBD` | `C:\Users\ignac\Dropbox\TBD` | Staging/archive folder copied successfully. | 958 |

## Historical Known Gaps

The following `BlackBook` files were not readable from Dropbox during the original consolidation because Windows returned `The cloud file provider is not running`:

- `.web/reflex (Nacho_Laptop's conflicted copy 2026-04-16).json`
- `.web/reflex.install_frontend_packages (Nacho_Laptop's conflicted copy 2026-04-16).cached`
- `BlackBook/components/sidebar.py`
- `BlackBook/pages/dashboard.py`
- `BlackBook/pages/journal.py`
- `BlackBook/pages/meridian.py`
- `BlackBook/state/app_state.py`
- `BlackBook/state/journal_state.py`

## Excluded On Purpose

- `.git/`
- `node_modules/`
- `dist/`
- `build/`
- `.next/`
- `venv/`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- copied `.env` files
- copied session/auth folders and log folders
