# Pantheon Monorepo

Pantheon is my personal life operating system — a unified voice-first platform centered around Apollo, my own JARVIS-like companion, that intelligently coordinates my money, knowledge, and trading while evolving toward a holographic command center.

This repository is the planning, structure, and coordination home for that system.

The real runtime lives locally on my machine.
GitHub is where the vision, architecture, roadmap, and code history are organized so the system stays understandable across time and devices.

## What Pantheon Is

Pantheon is the system I am building to coordinate the major domains of my life through one intelligent interface.

Its center is Apollo, the companion I speak to.
Around Apollo sit the core subsystems that each own a major domain cleanly:

- `Apollo`
  The voice and intelligent companion — my own JARVIS-like partner that I speak to.
- `BlackBook`
  My personal financial and operational reality — where money, holdings, transactions, and daily logistics live.
- `Maridian`
  My evolving second brain and knowledge vault — where raw thoughts turn into synthesized wisdom and reflection.
- `Olympus`
  My trading system and market intelligence — where positions, performance, and execution decisions happen.

These systems are intentionally separate.

- `BlackBook` owns the money.
- `Maridian` owns the mind.
- `Olympus` owns trading execution and market intelligence.
- `Apollo` is the companion and interface that ties them together.

Inside Olympus, `Apex` exists as the internal brain for that trading system, but it is not treated as a separate Pantheon-wide core subsystem.

## Source Of Truth

Pantheon uses a split source-of-truth model:

- `Local machine`
  The real runtime truth. This is where the live systems, private data, runtime files, and sensitive operational state actually live.
- `GitHub`
  The planning, history, and coordination truth. This is where the vision, architecture, documentation, migration plans, and tracked code live.

If local runtime reality and GitHub ever disagree, local runtime reality wins.

## Current Reality

These things are already real enough to count today:

- the monorepo structure consolidating Apollo, BlackBook, Maridian, and Olympus
- Apollo as a voice/chat interface with reasoning capabilities
- BlackBook as a working financial system
- Maridian as a working knowledge-vault and reflection-cycle system
- Olympus as a working trading-related system

In other words, Pantheon is not only an idea.
The subsystems already exist.
What is still missing is the final unification, the final interface, and the fully coherent command-center experience.

## In Progress

These parts are partially built or actively being organized toward the final system:

- the Pantheon monorepo as the single planning and coordination home
- the Pantheon-local organization of Maridian and its canonical vault
- the migration path from standalone BlackBook into a Pantheon-native financial surface
- the clarification of subsystem ownership and source-of-truth boundaries
- the path toward a single Pantheon interface where Apollo, BlackBook, Maridian, and Olympus feel like one system

This is the stage Pantheon is in right now:

- real subsystems exist
- the planning layer is becoming organized
- the final unified shell is not complete yet

## Near-Term Roadmap

The next major steps are about unification and clarity, not about pretending the final vision already exists.

Near-term, Pantheon needs:

- a cleaner unified Pantheon app surface
- the Maridian tab to become the true journaling and cycle-control surface
- BlackBook to remain financially focused while its Pantheon-native future is planned carefully
- clearer separation between private local runtime data and tracked repo structure
- better alignment between what the docs say and what each subsystem is meant to become

This is the practical stage where the system becomes organized enough that future implementation can happen without confusion.

## The Vision

The realistic end-state of Pantheon is:

- a unified, voice-first desktop and web-accessible life operating system
- a system where I speak naturally to Apollo
- a system where Apollo can coordinate:
  - finances through BlackBook
  - knowledge and reflection through Maridian
  - trading and execution through Olympus
- a system with one beautiful, consistent interface rather than several disconnected tools

In that version, Pantheon becomes the natural command layer for my life.

## The Bigger Dream

The optimistic, far-reaching version of Pantheon goes further.

In the fullest dream version, Pantheon becomes a holographic command center — a personal Iron Man lab where Apollo surrounds me in glowing cyan and gold holograms floating in the air.

In that version:

- I speak casually while the system visibly executes tasks
- information appears around me instead of being trapped in flat screens
- Apollo helps me build, reason, manage, and create in real space
- the system moves toward a more natural, voice-driven way of working

This may be far-fetched.
I still intend to try to make it real.

## Cross-Device Intent

Pantheon is the system I want to be able to reach across devices over time.

The goal is for the Pantheon experience to be accessible from any device in the house or remotely, while the core intelligence and all sensitive data remain fully local and private on my machine.

That means Pantheon can become broadly accessible without giving up the local-first model.

## Why This Repo Exists

This repository exists to:

- bring the systems together
- organize the architecture
- preserve the plans and vision documents
- track progress over time
- make the subsystems understandable across devices
- create one planning and coordination home for the whole Pantheon stack

The repo is not the machine itself.
It is the organized map of the machine I am building.

## Repository Layout

- `active/`
  Working system folders, subsystem code, and current local structure.
- `archive/`
  Historical or legacy copies kept for reference during consolidation.
- `docs/project-plans/`
  Vision documents, build plans, migration plans, and source-of-truth policy docs.
- `INVENTORY.md`
  Historical consolidation inventory from when the repo was first assembled.

## Final Position

Pantheon is my personal operating system for life.

Apollo is the companion at the center.
BlackBook handles money.
Maridian handles mind and reflection.
Olympus handles trading.

The long-term ambition is to reduce screen dependence, move toward a more natural voice-driven way of working, and eventually turn this into a command-center experience that feels closer to JARVIS than to a normal app stack.
