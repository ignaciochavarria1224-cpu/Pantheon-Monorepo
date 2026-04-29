# Apollo

Apollo is the user-facing interface layer of the Pantheon system.

If Pantheon is the operating system and intelligence layer, Apollo is the part you actually interact with. It is the voice, chat surface, delivery layer, and request gateway that turns user input into Pantheon reasoning requests and then turns Pantheon results back into something you can read or hear.

## Purpose

Apollo exists to give Pantheon a presence.

Today that presence is primarily:

- a FastAPI backend for chat, voice, briefs, triggers, memory inspection, and agent endpoints
- a Reflex-based web UI with Apollo as the main conversational surface and Pantheon as the internal operations shell
- a WhatsApp bridge
- a voice transcription entrypoint

Apollo is not supposed to be the final home of all intelligence. The current direction of the codebase is that Apollo remains the shell and Pantheon increasingly owns reasoning, orchestration, memory synthesis, approvals, and local model usage behind it.

## What The System Contains

### `main.py`
The main FastAPI application.

It currently exposes:

- `/chat` for normal Apollo conversation flow
- `/reason` for Pantheon-style structured reasoning results
- `/voice` for audio upload and transcription-driven requests
- `/brief` to manually trigger the daily brief
- `/history`, `/decisions`, `/patterns`, `/vault` for inspection endpoints
- `/reindex` to rebuild semantic indexes
- `/triggers/run` to evaluate cross-system triggers
- `/agents` endpoints for lightweight persistent sub-agents

### `core/`
Apollo's legacy backend logic and core runtime utilities.

Important modules:

- `brain.py`
  The compatibility layer that now routes Apollo requests into Pantheon
- `memory.py`
  Local SQLite-backed memory for conversations, decisions, approval rules, patterns, and queued actions
- `mind.py`
  Functions for the Apollo mind-vault style layer and higher-level self-model storage
- `triggers.py`
  Cross-system trigger logic, currently rule-based
- `executor.py` and `functions.py`
  Earlier tool-routing structure that still reflects the original Apollo architecture
- `audit.py`
  Permanent action logging

### `pantheon/`
The beginning of the Pantheon system behind Apollo.

This package now contains:

- `api.py`
  Pantheon entrypoints used by Apollo
- `reasoning.py`
  Current Pantheon request interpretation and orchestration logic
- `runtime.py`
  Provider gateway for Anthropic-first reasoning with Ollama fallback
- `connectors.py`
  Lazy connector bridge into Apollo's surrounding systems
- `models.py`
  Structured Pantheon result model

This folder matters because it represents the transition from "Apollo as the full brain" to "Apollo as the shell over Pantheon."

Pantheon now also exposes structured subsystem endpoints for the Apollo UI so the visible product can render live BlackBook, Maridian, and Olympus state instead of a static preview shell.

### `connectors/`
Direct integration code for:

- BlackBook
- Maridian
- Olympus

These adapters let Apollo and Pantheon read from and write to the surrounding systems. In the future, more of the orchestration around these should live in Pantheon, while the raw integration details remain here or in a shared connector layer.

### `search/`
Semantic indexing and retrieval.

This currently handles:

- indexing Maridian content into Chroma
- indexing decision logs
- semantic retrieval over indexed materials

### `voice/`
Voice input handling via `faster-whisper`.

This is transcription-focused right now. Apollo can receive audio, transcribe it locally, and pass the text through the same chat/reasoning pathway as text input.

### `agents/`
Background or scheduled support processes.

Current components:

- `brief.py`
  The daily brief scheduler and brief generation flow
- `hub.py`
  The early persistent sub-agent registry and execution layer

### `channels/`
Alternative delivery surfaces.

Right now the meaningful channel code is:

- `channels/whatsapp_bridge`
  The WhatsApp bridge that forwards messages into Apollo and returns replies

### `ui/`
Apollo's current Reflex UI.

This is now a two-layer shell:

- `Apollo` remains the main conversational tab
- `Pantheon` is the internal operations shell with subsystem tabs for BlackBook, Maridian, Olympus, and activity

The intention is one primary app, not a set of disconnected daily apps.

## Current State Of Apollo

Apollo is currently in a transitional phase.

It already has:

- a working backend
- local memory
- subsystem connectors
- voice transcription
- a daily brief mechanism
- triggers
- a WhatsApp bridge
- a unified Apollo/Pantheon UI shell
- the first Pantheon operations endpoints
- shared BlackBook-backed financial truth for balances and transaction-aware answers

It does not yet have:

- a completed local-first reasoning stack across all features
- a final digital twin layer
- a fully realized autonomous staff/agent model

So the right way to think about Apollo today is:

Apollo is already operational, but it is still evolving from "all-in-one AI app" into "interface shell for Pantheon."

## Runtime And Dependencies

Apollo currently depends on:

- Python / FastAPI for backend APIs
- Reflex for the web UI
- SQLite for local Apollo memory
- ChromaDB for semantic indexing
- `faster-whisper` for local transcription
- `anthropic` for the current primary reasoning path
- Node.js for the WhatsApp bridge
- BlackBook's Neon-backed database for financial data
- Maridian's vault/code for reflective memory and cycles
- either local Olympus artifacts or a private Olympus API for trading state

Pantheon now prefers Anthropic for open-ended reasoning and can fall back to Ollama when Anthropic is unavailable or when local runtime becomes the primary host later.

Current Pantheon-specific endpoints now also include:

- `/pantheon/doctor` for provider and subsystem health
- `/reason` metadata for provider, grounding, degraded-state, and latency details

## System Boundaries

Apollo owns:

- interface and delivery
- channel routing
- user session entrypoints
- voice/chat ingress
- user-facing response behavior
- the visible Apollo tab and the Pantheon shell that lives inside it

Apollo should not ultimately own:

- deep reasoning policy
- long-term orchestration logic
- cross-system intelligence rules
- local model strategy
- digital twin reasoning

Those responsibilities are moving into Pantheon.

## How Apollo Fits Into Pantheon

In the Pantheon architecture:

- Apollo is the face
- Pantheon is the system behind the face
- BlackBook is the financial source of truth
- Maridian is the reflective/cognitive source of truth
- Olympus is the execution/trading source of truth

That means Apollo should stay understandable and user-centered, while Pantheon becomes increasingly powerful behind it and surfaces subsystem operations through one coherent app shell.

## Documentation Contract

This README is a living system summary, not a marketing file.

Whenever Apollo changes in any material way, this file should be updated in the same commit if the change affects:

- architecture
- runtime dependencies
- public endpoints
- subsystem boundaries
- folder responsibilities
- Pantheon integration behavior

If code and documentation ever disagree, the code is the source of truth until this document is corrected.
