# Maridian Build Plan

This document turns the Maridian vision into a practical build roadmap.

It assumes:

- Maridian should live locally inside the Pantheon system
- Pantheon is the true home and control surface
- Obsidian is a mirrored output surface, not the source of truth
- journaling should move out of BlackBook and into Maridian

## Current Documentation State

Maridian already has:

- `maridian_vision.md`
- `maridian_build_plan.md`
- `maridian_storage_paths.md`

That means the remaining work is no longer defining what Maridian is at a high level.
The remaining work is organizing implementation, privacy boundaries, and migration order.

## Phase 0 - Planning And Boundary Lock

Goal:
finish the planning and organization layer before writing new Maridian code.

Required outcomes:

- define what Maridian files are safe to track in Git
- define what personal vault content should remain local/private
- lock the journaling ownership split from BlackBook to Maridian
- lock the first Pantheon Maridian surfaces to build
- keep repo organization ahead of implementation

Exit criteria:

- Maridian has a clear repo/local privacy policy
- Maridian has a clear first implementation sequence
- no one needs to guess whether BlackBook or Maridian owns reflective writing

## Core Build Thesis

Maridian should become the subsystem that converts personal writing into usable memory for Apollo.

The build must protect three things:

1. local ownership
2. clean separation from BlackBook
3. reliable output quality for Apollo consumption

## Target End-State

The end-state is:

- Maridian fully owned by Pantheon
- journal writing done from Pantheon
- cycle execution done from Pantheon
- outputs stored locally inside the repo-owned Maridian system
- outputs mirrored into Obsidian
- Apollo reading processed Maridian insight rather than raw text

## Phase 1 - Lock Ownership And Storage

Goal:
make Pantheon-local Maridian the explicit source of truth.

Required outcomes:

- retire Dropbox as Maridian ownership
- define the Pantheon-local Maridian storage path
- define the Obsidian path against the same canonical vault
- document that Obsidian reads the canonical vault directly
- update repo docs so Maridian is no longer treated as unresolved

Exit criteria:

- Maridian has one clear local home
- Dropbox is no longer treated as canonical
- Obsidian is clearly described as direct access to the canonical vault

## Phase 2 - Move Journal Ownership Into Maridian

Goal:
make Maridian the system where journaling begins.

Required outcomes:

- journaling UI belongs to Maridian
- BlackBook journaling is deprecated or redirected
- journal entries are stored in Maridian-owned storage
- the Maridian tab becomes the normal place to write

Exit criteria:

- new reflective writing starts in Maridian, not BlackBook
- ownership boundaries are clean

## Phase 3 - Build The Pantheon Maridian Control Surface

Goal:
make the Maridian tab a true operating system surface rather than a passive view.

Required surfaces:

- journal composer
- `Run Cycle` button
- cycle status
- cycle history
- latest cards/notes
- questions surface
- index excerpt
- mirror/sync visibility

Exit criteria:

- you can write and run Maridian from Pantheon directly
- the tab is useful without leaving Pantheon

## Phase 4 - Build The Local Processing Pipeline

Goal:
make Maridian's cycle engine operate from Pantheon-local truth.

Required outcomes:

- cycle jobs are triggered from Pantheon
- local files/data are updated by the cycle
- notes/cards/index/questions are regenerated consistently
- Apollo-facing outputs are stored in stable locations

Exit criteria:

- cycle runs update the Maridian brain locally
- outputs are reproducible and inspectable

## Phase 5 - Obsidian Mirror

Goal:
keep Obsidian useful without making it the system owner.

Required outcomes:

- Maridian outputs are mirrored into the Obsidian vault
- mirror direction is Pantheon -> Obsidian
- mirror failures are visible
- reading in Obsidian remains easy

Exit criteria:

- Obsidian reflects the current Maridian brain
- Pantheon remains canonical

## Phase 6 - Apollo Consumption

Goal:
make Apollo meaningfully learn from Maridian outputs.

Required outcomes:

- Apollo can read processed Maridian notes/cards/index/questions
- Apollo uses Maridian to understand patterns and values
- Apollo can reference Maridian-derived insight in a grounded way
- Apollo does not treat BlackBook journals as its main reflective source

Exit criteria:

- Maridian becomes one of Apollo's main "know me" systems

## Phase 7 - BlackBook Journal Separation Complete

Goal:
finish the ownership split cleanly.

Required outcomes:

- BlackBook no longer acts as the primary journal system
- Maridian fully owns reflective writing
- cross-links between BlackBook and Maridian remain possible without ownership confusion

Exit criteria:

- BlackBook is financial
- Maridian is reflective
- Apollo uses both

## Immediate Next Steps

1. Define the Git-vs-local privacy boundary for Maridian vault content.
2. Lock the BlackBook-to-Maridian journal ownership transition in the planning docs.
3. Inventory the current Pantheon Maridian code against the desired control-surface features.
4. Define the first Maridian tab surfaces to build:
   - journal input
   - run-cycle control
   - cycle status
   - latest questions
   - latest notes/cards
   - index excerpt
5. Plan Apollo's first Maridian consumption path from processed outputs.

## Final Position

Maridian should become the local reflective memory engine of Pantheon.

The system wins when:

- journaling starts in Maridian
- cycles run from Pantheon
- outputs stay local
- Obsidian mirrors the results
- Apollo learns how you think from processed memory
