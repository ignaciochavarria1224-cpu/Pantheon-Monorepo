# Source Of Truth Framework

This document defines how source-of-truth decisions are made across the repository.

## Root Rule

- `active/Pantheon` is the intended long-term root of the operating system.
- New architecture, status tracking, and consolidation planning should assume Pantheon is the parent system unless a specific subsystem is explicitly classified otherwise.

## Canonical Decision Rule

Source-of-truth decisions are determined primarily by the **most recent meaningful active work**.

Meaningful active work includes:

- feature development
- UI rebuilding
- backend/runtime evolution
- connector changes
- state/model changes
- architecture changes

Meaningful active work does **not** include:

- generated frontend artifacts
- copied runtime data
- stale duplicate working trees
- incomplete repo exports
- archived backups

When recency alone is not enough, use these tie-breakers in order:

1. architecture fit with the intended Pantheon-native design
2. completeness of the implementation
3. clarity of data ownership

## Required Classification Labels

Every major system or duplicate path must be labeled with one of the following:

- `canonical`
- `legacy`
- `reference`
- `migration source`
- `duplicate working tree`
- `needs audit`
- `integrated external subsystem`
- `reference / future integration`

## What Each Label Means

### `canonical`

The official source of truth for active development and architectural decisions.

### `legacy`

An older implementation that should not receive new product work unless explicitly reactivated.

### `reference`

Useful for comparison, historical context, or code borrowing, but not the active truth.

### `migration source`

A folder that still contains useful logic or runtime pieces that need to be intentionally migrated into the canonical system.

### `duplicate working tree`

Another copy of the same repo or subsystem that should not remain a co-equal source of truth.

### `needs audit`

A subsystem split that has not earned a final ruling yet. This label is temporary and must always include:

- the audit criterion
- the current structural risk
- the next decision milestone

### `integrated external subsystem`

A system that still runs somewhat independently but is already consumed by Pantheon and Apollo as part of the live architecture.

### `reference / future integration`

A repo that is strategically important but not yet integrated into the active system.

## Current Default Decisions

- `Pantheon`
  `active/Pantheon` is the canonical root.
- `Apollo`
  `active/Pantheon/apps/apollo` is canonical.
  `active/Apollo` is `legacy / migration source / reference`.
- `BlackBook`
  the separate `Black-Book` Streamlit repo is the current canonical application truth.
  `active/Pantheon/apps/blackbook` is the Pantheon migration target.
  `active/BlackBook` is a `legacy / reference` copy.
- `Olympus`
  treat Olympus as an `integrated external subsystem`.
  Its runtime may remain operationally distinct while Pantheon consumes and displays its state.
- `MetaGPT`, `deer-flow`, and `oh-my-claudecode`
  classify as `reference / future integration`.

## Audit Rule For Split Systems

If a subsystem is split and not yet resolved, the audit must answer:

- where the most recent meaningful work is landing
- which copy best matches the intended Pantheon architecture
- whether standalone-only files are real source logic or residue
- what threshold permits a final canonical ruling

No unresolved split should stay unlabeled.
