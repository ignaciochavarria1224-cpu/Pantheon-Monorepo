# Maridian

Maridian is the reflective memory subsystem inside the Pantheon stack.

Its job is to turn raw journal material into structured personal memory that Apollo and Pantheon can use over time.

## Current Architectural Position

Maridian is now organized around two Pantheon-local paths:

- app and control surface:
  `active/Pantheon/apps/maridian`
- canonical vault and data:
  `active/Pantheon/data/maridian-vault`

Obsidian should open the canonical vault directly.

## What Maridian Owns

Maridian owns:

- journaling over time
- cycle execution
- reflective processing
- question generation
- knowledge/wiki outputs
- personal-memory structures Apollo will later consume

Maridian does not own:

- financial facts
- trading execution
- Apollo's voice interface

Those belong to BlackBook, Olympus, and Apollo respectively.

## Current Role

This folder is the Pantheon-side Maridian app shell and control-surface code.

It is where the Maridian tab should eventually become the real place to:

- write journals
- run cycles
- view status
- inspect questions
- inspect notes/cards
- inspect index/wiki outputs

## Transitional Reality

The code in this folder still reflects parts of an older Maridian era, including:

- Neon-era naming
- older shared-table assumptions
- transitional control-panel logic

That does not change the intended architecture.

The current planning source of truth says:

- Pantheon owns the Maridian surface
- the canonical vault is local
- Obsidian reads that same vault
- BlackBook should stop owning reflective journaling over time

## Relationship To The Vault

This folder should be understood together with:

- `active/Pantheon/data/maridian-vault`

The app/control layer lives here.
The reflective content and generated vault state live there.

## Current Priority

The priority is not inventing what Maridian is.

The priority is turning this Pantheon app shell into the real control surface over the canonical vault while preserving:

- local-first privacy
- clean separation from BlackBook
- future Apollo consumption

## Documentation Rule

If Maridian's ownership, vault path, runtime model, or subsystem boundaries change, this README should be updated in the same planning or implementation pass.
