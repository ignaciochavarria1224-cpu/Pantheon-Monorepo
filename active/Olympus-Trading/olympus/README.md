# Olympus

Olympus is the live market-facing subsystem in this project.

It owns the full paper-trading loop: market data intake, universe ranking, entry qualification, risk-controlled execution, persistent memory, and structured Apex reporting. The current system is no longer just a ranking experiment. It is a multi-phase runtime with durable storage and a growing intelligence layer on top of that storage.

## Current State

Olympus is currently strongest across Phases 1 through 5:

- Phase 1: data foundation is live
- Phase 2: ranking cycles are live
- Phase 3: paper trading loop is live
- Phase 4: enriched memory and trade self-description are live
- Phase 5: persistent Apex reports are now live

What is not live yet:

- Pantheon debate output is not yet operating inside Olympus
- controlled evolution is not yet implemented
- live-money trading is not enabled

## What Olympus Does Today

- authenticates with Alpaca paper trading
- fetches and normalizes intraday market data
- ranks a broad equity universe into long and short candidates
- classifies regime quality using `core/trading/regime.py`
- qualifies entries with side-aware score, RVOL, range-position, VWAP, and ATR checks
- runs a continuous paper-trading loop with stop, target, rotation, stalled-trade, and end-of-day logic
- persists ranking cycles, trades, trade features, and system events into SQLite
- enriches trades with `entry_cycle_id`, `regime`, and entry-time feature context
- generates structured Apex reports into `apex_reports`
- exposes read-only Olympus state through the local API

## Key Entry Points

### `main.py`
Startup and validation entrypoint.

Use this to confirm settings, broker connectivity, scheduler behavior, and data flow on a fresh machine before running the live loop.

### `run_live.py`
Main operational runtime.

This process:

- loads settings
- initializes the SQLite database
- ingests ranking and trade artifacts
- starts the ranking cycle
- starts the memory-aware paper-trading loop
- writes daily markdown reports and Phase 5 Apex reports after market close

### `api.py`
Read-only Olympus service layer.

This exposes operational state without granting execution controls. It is intended for consumption by the broader stack or a private client over a trusted network path.

## Data and Memory Model

Olympus uses SQLite plus local artifacts as its execution memory layer.

### Runtime Source Of Truth

The top-level `olympus/` folder is the canonical Olympus code path for now.
`Pantheon/apps/olympus/` is treated as a stale copy until it is explicitly
synchronized or removed.

Live runtime data is local-first and should not be inferred from repo-local
database files. On this machine the active runtime paths are expected to live
under:

```text
C:\Users\ignac\OlympusLocal\data
```

GitHub/repo files organize code and history; local runtime data is the
operational source of truth.

Primary SQLite tables include:

- `ranking_cycles`
- `cycle_rankings`
- `trades`
- `trade_features`
- `system_events`
- `apex_reports`
- `pantheon_conclusions` (schema present, not yet in active use)

Important read surfaces include:

- `v_trades_enriched`
- `v_trades_full`
- `v_symbol_performance`
- `v_exit_reason_stats`

### Self-Describing Trades

Every trade is intended to be fully interpretable without reconstructing context manually.

That means the live schema now supports:

- `trades.regime`
- `trades.entry_cycle_id`
- entry-time trade features such as `rvol_at_entry`, `score_at_entry`, `range_position_at_entry`, `vwap_deviation_at_entry`, `atr_at_entry`, `close_at_entry`, and `volume_at_entry`

If an older runtime database is still on the pre-enrichment schema, the repair script is:

```bash
python scripts/backfill_trade_self_description.py
```

## Phase 5 Apex Reports

Phase 5 is now real in the codebase.

Olympus can persist these structured report types into `apex_reports`:

- `daily_performance`
- `weekly_performance`
- `risk_watch`
- `ranking_behavior`

Each report stores:

- `report_id`
- `report_type`
- `generated_at`
- `period_start`
- `period_end`
- `content_json`
- `summary_text`
- `consumed_by_pantheon`

`content_json` is the canonical artifact. Markdown reports remain useful for humans, but the database row is the machine-readable source of truth.

## Runtime Paths

Olympus is environment-driven.

By default it uses local paths under `data/`, but the active runtime may point elsewhere if `.env` overrides are set. In practice, this means cache, logs, trade JSON, ranking exports, and even `olympus.db` may live outside the repo on the machine that actually runs Olympus.

The authoritative path contract lives in:

- `config/settings.py`

Important configurable paths include:

- `CACHE_DIR`
- `LOG_DIR`
- `TRADES_DIR`
- `RANKINGS_DIR`
- `DB_PATH`

## Core Modules

### `config/`
Runtime configuration and path/credential loading.

### `core/data/`
Market data fetch, normalization, and cache behavior.

### `core/ranking/`
Feature computation, scoring, and ranking-cycle orchestration.

### `core/trading/`
Qualification, sizing, risk rules, execution, position management, regime logic, and the live loop.

### `core/memory/`
SQLite initialization, ingestion, enrichment, repository reads, and live memory writes.

### `core/reporting/`
Human-readable daily reporting plus structured Phase 5 Apex report generation.

### `scripts/`
Operational migration and repair utilities.

## Tests

The test suite is organized by system phase:

- `tests/phase1`
- `tests/phase2`
- `tests/phase3`
- `tests/phase4`
- `tests/phase5`

The most important Phase 5 guarantees currently covered are:

- structured Apex report persistence
- idempotent report regeneration for the same window
- report retrieval through the repository layer
- valid empty-window behavior

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
python run_live.py
```

## Common Commands

```bash
python main.py
python run_live.py
pytest
python check_db.py
python scripts/backfill_trade_self_description.py
```

## System Boundary

Olympus owns:

- market-facing data flow
- ranking and qualification logic
- paper-trade execution behavior
- trade memory and structured report generation
- runtime health and trading diagnostics

Olympus does not own:

- Apollo or any other UI layer
- Pantheon's debate logic
- human approval for live-money trading

## Documentation Rule

This README is meant to be a living operational summary.

Whenever Olympus changes materially in architecture, runtime behavior, storage shape, or subsystem boundaries, this file should be updated in the same change.
