# BlackBook

BlackBook is the financial and operational memory of the Pantheon stack.

It is the system that tracks the concrete facts of day-to-day financial life: transactions, balances, holdings, allocations, reports, journal entries, and advisor history. If Apollo is the interface and Pantheon is the intelligence layer, BlackBook is one of the most important factual sources that they rely on.

## Purpose

BlackBook exists to make your financial life legible and structured.

Its job is not just budgeting. It is the ledger and control system for:

- accounts
- transactions
- spending categories
- investment holdings
- allocation snapshots
- daily reports
- journal entries connected to your broader system
- advisor memory and conversations
- Maridian-facing journal data and outputs

It is the place where facts live. That matters because Pantheon should reason from facts, not guesses, and BlackBook is where many of those facts come from.

## What The System Contains

### `BlackBook/BlackBook.py`
The main Reflex application entrypoint.

BlackBook is structured as a shell app with conditional page rendering rather than as a set of independent mounted routes. The active section is chosen through app state and rendered inside a single layout.

### `BlackBook/pages/`
The visible product surface.

Current sections include:

- `dashboard`
- `transactions`
- `investments`
- `allocation`
- `reports`
- `journal`
- `reconcile`
- `agenda`
- `advisor`
- `meridian`
- `settings`

This means BlackBook is already more than a ledger. It is a personal financial operations app with journaling and second-brain integration built directly into it.

### `BlackBook/state/`
Reflex state logic for the visible app.

This is where most of the page behavior, data loading, filtering, and UI interactions are coordinated.

### `BlackBook/db/queries.py`
The real center of the system.

This file is the data contract between BlackBook and its underlying Neon/Postgres-backed financial data model. It defines and manages:

- settings
- accounts
- transactions
- holdings
- allocation snapshots
- price cache and history
- daily reports
- journal entries
- advisor memory
- advisor conversations
- Maridian brain and questions access

This makes `queries.py` one of the most strategically important files in the whole stack, because it encodes the shape of the structured facts Pantheon and Apollo will later rely on.

It is also now the shared truth path for Apollo/Pantheon financial reads. The current migration direction is to move financial surfaces into the Pantheon shell without duplicating BlackBook logic.

### `assets/`
Shared visual identity and styling, including the main BlackBook stylesheet.

## Current Role In The Pantheon Stack

BlackBook is currently the structured financial source of truth.

Pantheon and Apollo depend on it for things like:

- balances
- spending summaries
- transaction recording
- financial context for advice
- journal entry source material
- advisor memory
- Maridian-linked facts and outputs

It also already acts as a meeting point with Maridian, since BlackBook stores journal entries and reads Maridian outputs and question sets.

The current implementation direction is hybrid:

- BlackBook still owns the financial domain and its standalone app
- Apollo/Pantheon can now render important BlackBook surfaces from shared data-access logic
- deeper admin workflows such as settings and reconciliation can remain in the standalone app until the Pantheon shell catches up

## What BlackBook Already Does Well

BlackBook already has a broad footprint:

- tracks transactions and balances
- stores and renders investment holdings
- computes allocation snapshots
- stores journal entries
- stores advisor conversations and advisor memory
- exposes Maridian-derived themes and questions in-app
- acts as the financial fact layer the broader system can trust

This is why BlackBook should not be absorbed into Apollo or Pantheon. Its job is not to be the intelligence layer. Its job is to own the facts cleanly and reliably.

What *is* being absorbed is the everyday surface area. Pantheon can present BlackBook through its own tabs, but it should still do so by calling BlackBook's underlying truth path rather than rebuilding financial facts in a second connector layer.

## What BlackBook Is Not

BlackBook is not:

- the main orchestration brain
- the voice interface
- the digital twin
- the autonomous system controller

Those jobs belong elsewhere.

BlackBook should stay domain-focused: precise, structured, reliable, and financially grounded.

## Data Ownership

BlackBook owns:

- account facts
- transaction facts
- holdings facts
- allocation and reporting facts
- advisor memory and conversations
- journal entry source rows

BlackBook does not own:

- Maridian's local reflective vault
- Olympus execution logic
- Apollo/Pantheon long-term self-modeling

It may expose data used by those systems, but it should not be forced to become them.

## How BlackBook Fits Into Pantheon

In the broader architecture:

- Apollo is the visible interface
- Pantheon is the orchestration and reasoning layer
- BlackBook is the financial memory and fact system

Pantheon should query BlackBook whenever it needs financial truth. It should not attempt to recreate or mirror BlackBook’s structured logic in prompts.

Balance semantics are now explicit:

- if `current_balance_override` is set, it is treated as the final current balance
- if no override is set, balance is calculated as `starting_balance + ledger transactions`

This boundary is important:

- BlackBook answers "what happened financially?"
- Pantheon answers "what does it mean, and what should happen next?"

## Runtime And Dependencies

BlackBook currently depends on:

- Reflex for the app UI
- PostgreSQL/Neon for storage
- Python-side query logic for all data access

It also includes AI-adjacent surfaces like the advisor page, but the system itself is still fundamentally a structured operations app first.

## Documentation Contract

This README is a living system summary.

Whenever BlackBook changes in any material way, this file should be updated in the same commit if the change affects:

- schema or table responsibilities
- major pages or major state flows
- how BlackBook interacts with Apollo, Pantheon, or Maridian
- the scope of the app
- data ownership boundaries

If this document and the code disagree, the code wins until this file is corrected.
