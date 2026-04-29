# Maridian Storage Paths

This document locks the concrete local storage decision for Maridian.

## Canonical Maridian App Path

The Maridian app and control surface should live at:

- `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\apps\maridian`

This is where the Pantheon-facing Maridian UI, cycle controls, and integration logic belong.

## Canonical Maridian Vault Path

The Maridian vault and data source of truth should live at:

- `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\data\maridian-vault`

This is the canonical local home for:

- `raw/`
- `wiki/`
- `Questions/`
- `db/`
- `agents/`
- `utils/`
- `.obsidian/`
- `MERIDIAN.md`
- `README.md`
- `vault_state.json`

## Obsidian Path

Obsidian should open this same canonical vault path directly:

- `C:\Users\ignac\Documents\AI_PROJECTS_MONOREPO\active\Pantheon\data\maridian-vault`

That means Obsidian is not a second source of truth and not a delayed mirror target.
It is a direct reader of the canonical Maridian vault.

## Why This Path Was Chosen

This path is the cleanest long-term option because:

- it keeps Maridian fully local
- it removes Dropbox dependency
- it preserves one canonical source of truth
- it keeps the vault next to Pantheon rather than floating outside the system
- it lets Obsidian graph view operate directly on the live Maridian data
- it minimizes sync risk while protecting the existing 300+ entries and generated files

## Architecture Result

The final structure should be understood like this:

- `active/Pantheon/apps/maridian` = Maridian app, control surface, cycle triggers
- `active/Pantheon/data/maridian-vault` = Maridian canonical data and vault
- Obsidian opens the same vault path directly

## Next Migration Concern

The remaining implementation work is not deciding where Maridian lives.

That decision is now locked.

The next work is:

1. safely migrate the existing Maridian data into the canonical vault path
2. verify nothing is lost from the current 300+ raw entries and supporting files
3. connect the Pantheon Maridian tab to this canonical local vault
