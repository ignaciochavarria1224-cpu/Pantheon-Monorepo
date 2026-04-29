# Olympus

Olympus is the trading execution subsystem in the Pantheon stack.

It owns the market-facing runtime: data intake, universe ranking, entry qualification, paper-trade execution, persistent trade memory, and structured Phase 5 Apex reports. If Apollo is the interface and Pantheon is the broader orchestration layer, Olympus is the subsystem that actually watches markets, simulates trades, and records what happened in a form the rest of the stack can consume.

## Current State

Olympus is currently strongest across Phases 1 through 5:

- Phase 1: data foundation is live
- Phase 2: ranking cycles are live
- Phase 3: paper-trading loop is live
- Phase 4: enriched memory and self-describing trades are live
- Phase 5: persistent Apex reports are live

What is not live yet:

- Pantheon conclusions are not yet being generated in production
- controlled evolution is not yet implemented
- live-money execution is not enabled

## Purpose

Olympus exists to turn market inputs into structured decisions, durable records, and machine-readable intelligence artifacts.

Its current responsibilities are:

- authenticate with Alpaca paper trading
- fetch and normalize intraday market data
- rank a broad equity universe into long and short candidates
- classify market regime quality
- qualify entries with side-aware filters
- run a continuous paper-trading loop with risk controls
- persist ranking cycles, trades, trade features, and system events
- generate structured Apex reports into SQLite
- expose read-only Olympus state through the local API

## What The System Contains

### `main.py`
Startup and validation entrypoint.

Use this to confirm settings, broker connectivity, scheduler behavior, and data flow before running the live loop.

### `run_live.py`
Main operational runtime.

This process:

- loads settings
- initializes the SQLite database
- ingests ranking and trade artifacts
- starts the ranking cycle
- starts the memory-aware paper-trading loop
- writes daily markdown reports
- writes structured Phase 5 Apex reports after market close

It also uses a PID lockfile so two live runtimes do not start accidentally on the same machine.

### `api.py`
Read-only Olympus service API.

This exposes Olympus runtime state without granting execution controls. It is intended to be the safe boundary other Pantheon components or private clients read from.

Current endpoints include:

- `/health`
- `/summary`
- `/trades`
- `/cycle/latest`
- `/report/latest`

### `config/`
Environment-driven runtime configuration.

`config/settings.py` defines credentials, market hours, ranking cadence, cache paths, log paths, trading risk limits, and storage paths.

Important tuning groups include:

- side-specific long and short entry thresholds
- regime classification and mixed-market throttles
- ATR sanity bounds for execution eligibility
- symbol cooldown and suppression controls
- sector concentration limits
- stalled-trade and rotation sensitivity
- runtime storage locations such as `CACHE_DIR`, `LOG_DIR`, `TRADES_DIR`, `RANKINGS_DIR`, and `DB_PATH`

### `core/`
The Olympus engine.

Important areas include:

- `core/broker/`
  broker-facing Alpaca integration
- `core/data/`
  market-data fetch, normalization, and cache behavior
- `core/ranking/`
  feature computation, scoring, and ranking-cycle orchestration
- `core/trading/`
  execution, position management, qualification, sizing, risk logic, regime gating, and the live loop
- `core/memory/`
  SQLite initialization, enrichment, ingestion, repository reads, and live memory writing
- `core/reporting/`
  human-readable daily reporting plus structured Apex report generation

### `scripts/`
Operational utilities and repair tasks.

This includes migration/backfill work such as:

- `scripts/backfill_trade_self_description.py`

### `tests/`
Phase-organized test coverage.

The suite currently includes:

- `phase1`
- `phase2`
- `phase3`
- `phase4`
- `phase5`

Phase 5 tests cover:

- structured Apex report persistence
- idempotent regeneration for the same report window
- repository retrieval APIs for `apex_reports`
- valid empty-window behavior

## Data and Memory Model

Olympus uses SQLite plus local runtime artifacts as its execution memory layer.

Primary SQLite tables include:

- `ranking_cycles`
- `cycle_rankings`
- `trades`
- `trade_features`
- `system_events`
- `apex_reports`
- `pantheon_conclusions`

Important read surfaces include:

- `v_trades_enriched`
- `v_trades_full`
- `v_symbol_performance`
- `v_exit_reason_stats`
- `v_rolling_7day`
- `v_feature_buckets`

### Self-Describing Trades

Every trade is intended to be interpretable without reconstructing context from scattered files.

That means the current schema supports:

- `trades.regime`
- `trades.entry_cycle_id`
- entry-time feature fields such as:
  `rvol_at_entry`, `score_at_entry`, `range_position_at_entry`,
  `vwap_deviation_at_entry`, `atr_at_entry`, `close_at_entry`,
  and `volume_at_entry`

If a runtime database is still on the older schema, use:

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

`content_json` is the canonical machine-readable artifact. Markdown reports remain useful for humans, but the database row is the source of truth for downstream consumers.

The current reporting payload contract includes these top-level sections:

- `meta`
- `performance`
- `risk`
- `ranking`
- `regime`
- `symbols`
- `anomalies`
- `recommendations`

## Current Role In Pantheon

Olympus is currently the trading execution source of truth.

That means the broader stack should rely on Olympus for:

- current paper-trading state
- ranked symbols and directional bias
- recorded trades and trade features
- regime-aware trade context
- runtime health for the market-facing system
- persistent Phase 5 Apex reports for future Pantheon consumption

## Runtime And Dependencies

Olympus currently depends on:

- Python
- Alpaca paper trading credentials
- `alpaca-py`
- `pandas`
- `pyarrow`
- `python-dotenv`
- writable local storage for cache, logs, ranking exports, trade JSON, reports, and SQLite state

Runtime data is intentionally excluded from Git. On a working machine, Olympus will create and use local paths for:

- market-data cache files
- logs
- ranking exports
- JSON trade records
- SQLite runtime state
- generated markdown reports
- generated Apex report summaries

## Quick Start

```bash
cd apps/olympus
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
python run_live.py
```

## Common Commands

```bash
cd apps/olympus
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
- enriched trade memory
- structured Apex report generation
- trading runtime health and diagnostics

Olympus does not own:

- Apollo's user-facing interface
- Pantheon's debate and judge logic
- BlackBook's ledger responsibilities
- human approval for live-money execution

## Documentation Contract

This README is a living operational summary.

Whenever Olympus changes in a material way, this file should be updated in the same change if the update affects:

- runtime entrypoints
- risk or execution behavior
- storage responsibilities
- report generation behavior
- subsystem boundaries
- external dependencies
- how Olympus integrates with Apollo or Pantheon
