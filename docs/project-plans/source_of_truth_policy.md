# Source Of Truth Policy

This document defines how source of truth should be understood across the monorepo.

It is written as a founder note with policy rules because the systems in this repo do not all live in the same way.

Some parts of the system are meant to be versioned, shared, and tracked through GitHub.
Other parts are meant to stay local because they are live runtime state, private memory, or machine-bound operational truth.

This policy exists so those boundaries stay clear.

## Core Principle

There are two different truths in this ecosystem:

1. `local truth`
2. `GitHub truth`

They are not the same thing and should not be treated as the same thing.

## Local Truth

Local truth is always the real truth.

That means the local machine is the canonical home for:

- live systems
- runtime state
- operational files
- real app data
- private personal memory
- machine-bound execution environments

If a conflict appears between local runtime reality and what GitHub shows, local reality wins.

## GitHub Truth

GitHub is not the runtime source of truth.

GitHub exists to provide:

- planning
- architecture
- vision documents
- build plans
- migration plans
- repo organization
- code history
- coordination across devices
- visibility into where each system stands

GitHub should be treated as the coordination and history layer, not as the owner of live runtime truth.

## Monorepo Rule

This policy applies to the whole monorepo, including:

- Pantheon
- Apollo
- BlackBook
- Maridian
- Olympus
- supporting integration repos and planning docs

## What GitHub Should Track

By default, GitHub should track:

- source code
- architecture and planning documents
- prompts, agents, and reusable system logic
- schemas
- non-sensitive configuration templates
- migration plans
- documentation
- selected code and structure needed to understand and reproduce the systems

The default intent is:

- track everything that helps organize, understand, and rebuild the systems
- do not track secrets or very personal data

## What Should Stay Local

The following should stay local by default and should not be treated as normal GitHub content:

- raw journal entries
- generated Maridian notes/cards
- local databases
- `.env` files
- Obsidian workspace/config files
- AI conversation history
- exported reports
- logs

These are excluded because they are either:

- sensitive
- personal
- runtime-specific
- machine-specific
- too volatile to be a good coordination artifact

## Runtime Interpretation

The intended operating rule is simple:

- local is always the real truth
- GitHub is coordination and history

This means even when code is tracked in GitHub, the actual live system still lives locally unless explicitly stated otherwise.

## Cross-Device Rule

GitHub helps keep the systems visible and organized across devices.

But another device should not automatically be treated as canonical just because the repo is available there.

The rules are:

- GitHub is the shared coordination layer across devices
- local runtime on the active machine is the real execution truth
- another device is a viewer, planner, or secondary work surface unless intentionally promoted
- the Pantheon app is the main system intended to become meaningfully cross-device over time

## Pantheon-Specific Note

Pantheon is the system most likely to become the cross-device interface.

That does not change this policy.

It means:

- Pantheon may become accessible across devices
- but the real underlying system state is still expected to live locally first
- GitHub still remains planning/history/coordination rather than runtime truth

## Privacy Rule

If a file contains secrets, highly personal memory, private runtime state, or sensitive generated outputs, it should stay local unless there is a deliberate choice to publish or version it.

The default should be caution, not convenience.

## Founder Position

The repo exists to bring everything together, organize it, track it, and make the systems understandable across time and devices.

The local machine exists to actually run the systems.

That is the model.

GitHub is where the systems are described, planned, versioned, and coordinated.
Local files are where the systems are actually alive.
