# Pantheon

Pantheon is the system behind Apollo.

This repository is the private monorepo for the personal operating system stack:

- `apps/apollo` - the interface layer and current Pantheon runtime seed
- `apps/blackbook` - finance, ledger, and operational memory
- `apps/maridian` - second-brain and reflective processing system
- `apps/olympus` - market data, ranking, paper-trading execution, and trade memory

## Structure

```text
Pantheon/
  apps/
    apollo/
    blackbook/
    maridian/
    olympus/
  docs/
  README.md
  .gitignore
```

## Safety Rules

This repo is set up to keep code and architecture in Git, while keeping secrets and private runtime data out.

Excluded from version control:

- `.env` files and secrets
- local databases and indexes
- Apollo logs and runtime data
- Olympus logs, caches, paper-trade JSON, and SQLite runtime state
- Maridian private journal/vault content
- build artifacts, caches, `node_modules`, and generated web folders

## Current Architecture

- `Apollo` is the user-facing app, voice, and chat surface.
- `Pantheon` currently lives inside `apps/apollo/pantheon` as the hidden reasoning layer and internal operations shell behind Apollo.
- `BlackBook` and `Maridian` remain separate subsystems that Pantheon reads from and coordinates.
- `Olympus` is the trading execution source of truth, including market data fetch, ranking cycles, paper-trading logic, and persistent trade memory.

See [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) for the high-level model.

## Documentation Rule

Each major system in this repository should maintain its own living README:

- `apps/apollo/README.md`
- `apps/blackbook/README.md`
- `apps/maridian/README.md`
- `apps/olympus/README.md`

These files are not optional polish. They are operational summaries of purpose, boundaries, and current state.

Whenever a system changes in a material way, its README should be updated in the same commit if the change affects architecture, responsibilities, interfaces, runtime, or subsystem boundaries.

