# Maridian

Maridian is the reflective and cognitive memory system in the Pantheon stack.

Its job is to read journal material, evolve it into organized knowledge, identify themes and questions, and return your thinking in a more structured and useful form than the original raw entry. It is not a chatbot and not a generic note vault. It is a system for turning raw reflective input into evolving personal intelligence.

## Purpose

Maridian exists because raw journaling by itself is not enough.

Without a system like this, years of journal entries sit in storage and do almost nothing. Maridian pulls those entries into an active cycle that can:

- extract themes
- build a knowledge/wiki layer
- generate adaptive questions
- surface evolving beliefs
- push selected outputs back into the broader operating system

If BlackBook owns financial facts, Maridian owns reflective source material and the distilled patterns that come out of it.

## What The System Contains

### `evolve.py`
The main cycle runner.

This is the operational heart of Maridian. It manages the evolution cycle, including:

- loading state
- locking so cycles do not overlap
- claiming pending jobs from Neon
- extracting or importing new material
- building or updating the knowledge layer
- generating daily questions
- syncing and pushing outputs
- saving cycle state

This is the file that turns Maridian from a pile of scripts into a functioning system.

### `control.py`
The control panel.

This is a Streamlit-based operational interface for:

- viewing current status
- running a cycle manually
- checking today's adaptive questions
- inspecting framework market or output state
- monitoring Neon connectivity

### `agents/`
The modular processing layer.

This folder contains the specialized workers that make Maridian work. The exact behavior has evolved over time, but the current codebase includes agents for:

- journal extraction
- wiki and brain building
- question generation
- framework writing
- fitness scoring
- debate or contradiction surfacing
- pattern reporting
- wikilink harvesting
- growth and crossover logic

The broad idea is that Maridian is not a single monolithic script. It is a pipeline of specialized processors that reshape journal material into increasingly organized forms.

### `db/`
Neon integration and schema.

This layer is responsible for reading from and writing to the shared Postgres/Neon environment. In practical terms, that means Maridian can:

- pull journal entry source data
- push question sets
- push framework-like outputs
- participate in a job/request flow with surrounding systems

### `utils/`
Reusable support code.

This includes helpers for:

- LLM interaction
- registry and state management
- embeddings
- vault operations
- git-related utility behavior

## Current Role In The Pantheon Stack

Maridian is the reflective source of truth.

It is the subsystem Pantheon should reach for when it needs:

- journal-derived context
- long-term themes
- adaptive questions
- reflective follow-up prompts
- evidence of belief or risk-tolerance shifts

Maridian is not the real-time voice interface. That remains Apollo.

Maridian is not the financial source of truth. That remains BlackBook.

Maridian is not the trading execution source of truth. That remains Olympus.

Its job is to own the reflective layer cleanly.

## Current State Of Maridian

The codebase shows two important truths:

1. the long-term vision has been ambitious and multi-stage
2. the actually implemented system today is more grounded than some of the older plans

So the right reading of Maridian is:

- it already has a real cycle runner
- it already has a control panel
- it already has agentized processing modules
- it already integrates with Neon
- it already produces operational outputs for the broader ecosystem

At the same time, some of the larger vision language in older plans has not been fully realized yet, and the code should always be treated as the current truth.

## Runtime And Dependencies

Maridian currently depends on:

- local Python runtime
- Neon/Postgres for shared persistence and source data
- local or nearby LLM helpers depending on environment
- Streamlit for its control panel
- a local file/vault structure for its own processing model

Historically it has also been designed around local model use and local privacy assumptions, which remains aligned with the broader Pantheon direction.

## What Maridian Produces

Today, Maridian primarily produces:

- question sets
- processed reflective structures
- theme or wiki-style knowledge
- framework-like outputs
- pattern and evolution signals

These outputs matter because they feed the larger system:

- BlackBook can display or consume pieces of them
- Apollo can reference them
- Pantheon can reason over them

## Data Ownership

Maridian owns:

- reflective processing logic
- local cognitive and knowledge generation flow
- question generation
- theme extraction and synthesis

In the monorepo, private reflective vault content is intentionally excluded from Git. That means this repo contains Maridian's code and structure, not the full private journal-derived runtime state.

That separation is deliberate and should remain.

## How Maridian Fits Into Pantheon

In the Pantheon architecture:

- Apollo is the interface
- Pantheon is the orchestration and intelligence layer
- Maridian is the reflective memory engine

Pantheon should use Maridian to understand how your thinking evolves over time, not to replace Maridian's domain-specific processing.

In other words:

- Maridian asks: "What themes, beliefs, tensions, and questions are present in the reflective data?"
- Pantheon asks: "How should that affect broader reasoning, coordination, and action?"

## Quick Start

```bash
# 1. Fill in your Neon connection string
# Edit .env -> NEON_DATABASE_URL=postgresql://...

# 2. Initialize Neon tables
python -c "from db.neon_bridge import init_tables; init_tables()"

# 3. Run first cycle
python evolve.py evolve

# 4. Check status
python evolve.py status

# 5. Open control panel
streamlit run control.py
```

## Common Commands

```bash
python evolve.py evolve         # Process a cycle
python evolve.py status         # Print current status
python evolve.py write <id>     # Write framework-like output locally if supported
python evolve.py push <id>      # Push framework-like output if supported
streamlit run control.py        # Open control panel
```

## Documentation Contract

This README is a living system summary.

Whenever Maridian changes in any material way, this file should be updated in the same commit if the change affects:

- the cycle architecture
- agent responsibilities
- output types
- Neon integration
- subsystem boundaries
- the role Maridian plays inside Pantheon

If code and documentation disagree, the code is the source of truth until this file is corrected.

