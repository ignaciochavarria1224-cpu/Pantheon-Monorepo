# Documentation Policy

This repository treats system READMEs as living technical summaries.

## Required System Summaries

Each major subsystem must maintain a README that explains:

- what the system is for
- what it currently contains
- what it owns
- how it fits into Pantheon
- what is implemented today versus still aspirational

Current required files:

- `apps/apollo/README.md`
- `apps/blackbook/README.md`
- `apps/maridian/README.md`

## Update Rule

When a material change is made to a subsystem, update that subsystem's README in the same commit if the change affects:

- architecture
- folder or module responsibilities
- major runtime dependencies
- major endpoints or interfaces
- data ownership
- subsystem boundaries
- Pantheon or Apollo integration behavior

## Source Of Truth

When plans, README files, and code disagree:

1. code is the operational source of truth
2. README files should be corrected next
3. older plans should be treated as context, not as binding current-state documentation

This policy exists so the repo stays understandable even as the vision evolves.

