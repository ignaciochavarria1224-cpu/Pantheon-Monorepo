# System Overview

## Roles

- `Pantheon` is the operating system and intelligence layer.
- `Apollo` is the interface, voice, and delivery shell.
- `BlackBook` is the financial and operational source of truth.
- `Maridian` is the reflective and cognitive source material.
- `Olympus` is the market execution and trading memory source of truth.

## Current Repo Mapping

- `apps/apollo`
  Contains the existing Apollo backend, UI, connectors, and the `pantheon/` package that now routes reasoning behind Apollo and powers the internal operations shell.
- `apps/blackbook`
  Contains the BlackBook Reflex app and database/query logic.
- `apps/maridian`
  Contains Maridian code only. Private vault content and derived personal data are intentionally excluded from Git.
- `apps/olympus`
  Contains the Olympus trading engine code, tests, and configuration templates. Live runtime data, logs, and local databases remain excluded from Git.

## Current Direction

The immediate direction is:

1. keep Apollo as the visible product
2. keep Apollo as the main conversational tab while Pantheon becomes the internal shell for BlackBook, Maridian, Olympus, and activity
3. continue moving intelligence responsibilities into Pantheon
4. run the local model stack on the PC
5. use subsystem-owned truth paths so Apollo answers from the same facts those systems use themselves

