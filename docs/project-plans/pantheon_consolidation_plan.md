# Pantheon Consolidation Plan

This document defines what Pantheon consolidation means, what is already true, what is still split, and how unfinished Phase 7 and Phase 8 work fit directly into the cleanup of Apollo, BlackBook, Maridian, and Olympus.

## Consolidation Thesis

Pantheon is the intended long-term root of the operating system.

Consolidation does **not** mean every subsystem must lose its domain boundaries. It means:

- the repo has one architectural root
- the user-facing surface converges into one active frontend
- subsystem ownership becomes explicit
- standalone legacy copies stop acting like co-equal truths
- Pantheon becomes the place where the system is understood, surfaced, and controlled

## What Is Already Native To Pantheon

These are already Pantheon-native from an architecture point of view:

- `apps/apollo` as the primary user-facing interface direction
- `apps/blackbook` as the intended Pantheon-native financial subsystem location
- `apps/maridian` as the intended Pantheon-native reflective subsystem location
- `apps/olympus` as the Pantheon-facing Olympus surface
- `docs/` and root README as the monorepo-level system framing

## What Is Still Bridged Or Duplicated

These still need explicit cleanup:

- standalone `active/Apollo`
  still exists as a legacy/migration-source/reference copy
- external `Black-Book` Streamlit repo
  is the current canonical BlackBook application while Pantheon BlackBook remains the intended destination
- standalone `active/BlackBook`
  still exists as an older legacy/reference copy
- standalone `active/Maridian`
  still exists alongside Pantheon Maridian and requires an audit
- `active/Olympus-Trading/Pantheon`
  still exists as a duplicate working tree of Pantheon

These are the main structural blockers to saying Pantheon is fully consolidated.

## Subsystem Ownership Under Pantheon

### Apollo

Apollo owns:

- chat and voice ingress
- user-facing response shell
- delivery surfaces
- the main active frontend direction

Apollo should not remain split across two active truths. The Pantheon Apollo app is the canonical target and current truth.

### BlackBook

BlackBook owns:

- financial facts
- transaction and holdings truth
- financial memory and operational finance state

The current application truth lives in the separate `Black-Book` Streamlit repo.

`active/Pantheon/apps/blackbook` should be treated as the Pantheon-native destination, not as the current canonical product truth.

BlackBook should remain a distinct subsystem even after Pantheon-native surfacing is complete. Consolidation does not mean absorbing its domain boundaries into Apollo.

### Maridian

Maridian owns:

- journaling
- cycles
- reflective processing
- Obsidian-brain creation logic

Maridian should remain a distinct subsystem inside Pantheon, even if Apollo and BlackBook consume its outputs later.

### Olympus

Olympus is an `integrated external subsystem`.

It is not fully absorbed into Pantheon runtime ownership today, but it is already part of the live system because:

- Pantheon displays Olympus stats
- Apollo and Pantheon consume Olympus state
- the Pantheon interface is expected to provide increasing insight and eventual control

Olympus therefore belongs in the architecture map directly, even if its execution runtime stays somewhat separate.

## What Pantheon Consolidation Complete Means

Pantheon consolidation should be considered complete only when all of the following are true:

- `active/Pantheon` is the only architectural root in active use
- Apollo has one canonical active implementation
- BlackBook has one canonical active implementation
- Maridian has one canonical active implementation
- duplicate Pantheon working trees are retired or archived
- one active frontend stack remains
- Pantheon-native UI surfaces are the real daily control interface
- standalone legacy copies, where still preserved, are labeled clearly and no longer treated as active truths

## Phase 7 As A Critical Dependency

Pantheon Phase 7 is not optional cleanup-adjacent work. It is one of the main structural dependencies for consolidation.

Phase 7 matters because it is the work that makes Pantheon's Next.js HUD the real operational frontend.

It should be treated as the UI layer that:

- replaces old Reflex surfaces with Pantheon-native pages
- gives BlackBook, Maridian, and Olympus real in-Pantheon visibility
- turns `/pantheon` into the practical daily control surface
- reduces the gap between architectural intent and actual product use

The plan for Phase 7 should explicitly preserve:

- `/pantheon` sub-router structure
- Overview / BlackBook / Maridian / Olympus tab model
- BlackBook subpage parity target
- Maridian panel target
- Olympus panel target
- mobile parity requirement
- full feature parity requirement for rebuilt surfaces

Without Phase 7, source-of-truth cleanup remains weaker because the real user-facing system is still split across generations of UI.

## Phase 8 As A Critical Dependency

Pantheon Phase 8 is also a structural dependency, not a cosmetic follow-up.

Phase 8 is the work that:

- removes Reflex as an active frontend
- collapses the system to one active frontend stack
- cleans stale imports and old boundaries
- prepares legacy BlackBook logic for Pantheon-local service ownership before deleting old app copies

The plan for Phase 8 should explicitly preserve:

- moving Next.js into the final active frontend role
- deprecating `apps/apollo/ui`
- removing old Reflex dependencies
- resolving `from BlackBook` import paths before deleting legacy BlackBook app copies
- sweeping stale references after consolidation
- final desktop and phone verification

Without Phase 8, Apollo and BlackBook cannot be considered structurally settled.

## Temporary Tolerance Rules

Until consolidation is complete, these temporary tolerances are acceptable:

- standalone legacy folders may remain
- Olympus may remain operationally separate while still integrated architecturally
- Maridian may remain classified as `needs audit`
- BlackBook may remain externally canonical while its Pantheon-native migration is still underway

These temporary states are only acceptable if they are:

- documented
- labeled clearly
- linked to a next decision milestone

## Recommended Sequence

1. source-of-truth framework
2. repo status tracker
3. Pantheon consolidation plan
4. explicit Phase 7 and Phase 8 dependency framing
5. BlackBook migration planning
6. Maridian audit
7. missing core subsystem docs
8. duplicate working-tree retirement planning
9. migration sequencing for remaining legacy copies

## Final Position

Pantheon consolidation is not just about moving files.

It is about making the architecture honest:

- one root
- one active frontend
- clear subsystem boundaries
- explicit ownership
- visible control surfaces

Pantheon wins when Apollo becomes the real interface, BlackBook and Maridian remain domain-clean inside it, Olympus remains visible and integrated, and the repo stops behaving like several partially overlapping systems pretending to be one.
