# Olympus

Olympus is the trading execution system in the Pantheon stack.

It owns the market-facing workflow: fetching data, ranking a liquid equity universe, running paper-trading logic, persisting trade memory, and producing artifacts the rest of Pantheon can consume. If Apollo is the interface and Pantheon is the orchestration layer, Olympus is the subsystem that actually watches markets and manages simulated execution behavior.

## Purpose

Olympus exists to turn market inputs into structured trading decisions and durable records.

Its current responsibilities are:

- authenticate with Alpaca paper trading
- fetch and normalize intraday market data
- rank a broad equity universe into long and short candidates
- run an always-on paper-trading loop with risk controls
- persist trade events, rankings, and execution memory into SQLite and JSON artifacts
- generate reports and utilities for inspection and debugging

This means Olympus is not just a script that places paper orders. It is a runtime with its own data layer, ranking logic, execution policy, and memory model.

## What The System Contains

### `main.py`
The phase-gate entrypoint.

This script performs a structured startup validation across settings, logging, Alpaca connectivity, market data access, normalization, cache behavior, and scheduler behavior. It is the quickest way to confirm a fresh machine is wired correctly before running the live loop.

### `api.py`
The read-only Olympus service API.

This exposes Olympus state to the rest of Pantheon without granting execution controls. It is intended to run on the always-on PC so Apollo on other devices can read Olympus through a private network path such as Tailscale.

Current endpoints:

- `/health`
- `/summary`
- `/trades`
- `/cycle/latest`
- `/report/latest`

### `run_live.py`
The continuous paper-trading runtime.

This is the main operational process. It:

- loads settings
- initializes the SQLite database
- ingests existing ranking and trade JSON into durable storage
- starts the ranking cycle
- starts the memory-aware paper-trading loop
- keeps a heartbeat running until shutdown

It also uses a PID lockfile so two live runtimes do not start accidentally on the same machine.

The runtime also persists cycle diagnostics and data-quality events so post-session review can measure whether the execution filters, broker state, and memory writes are behaving cleanly.

### `config/`
Environment-driven configuration.

`config/settings.py` defines Olympus's runtime contract: Alpaca credentials, market hours, ranking cadence, cache paths, log paths, trading risk limits, and storage paths.

Important tuning groups now include:

- side-specific entry thresholds for longs and shorts
- regime classification and mixed-market throttles
- ATR sanity bounds for execution eligibility
- symbol cooldown and suppression controls
- sector concentration limits
- stalled-trade and rotation sensitivity

### `core/`
The trading engine itself.

Important areas include:

- `core/broker/`
  Alpaca integration and broker-facing behavior
- `core/data/`
  market-data fetch, normalization, and cache handling
- `core/ranking/`
  feature computation, scoring, classification, and cycle orchestration
- `core/trading/`
  execution, position management, sizing, risk logic, and the live loop
- `core/trading/regime.py`
  regime classification and market-quality gating
- `core/trading/qualification.py`
  side-aware entry qualification before order placement
- `core/memory/`
  SQLite initialization, ingestion, repository access, and memory writing
- `core/reporting/`
  reporting utilities such as the daily report generator

### `tests/`
Phase-organized test coverage.

The suite is grouped by major system milestones:

- `phase1`
  connectivity, data, and scheduler basics
- `phase2`
  ranking and feature logic
- `phase3`
  trading loop, risk, sizing, and position management
- `phase4`
  memory, schema, ingestion, and repository behavior

### `tools/` and `scripts/`
Operational utilities.

These include local helpers for backtesting, DuckDB inspection, and targeted repair/migration tasks for trade-memory data.

## Current Role In The Pantheon Stack

Olympus is currently the trading execution source of truth.

That means the broader stack should rely on Olympus for:

- current paper-trading state
- ranked symbols and directional bias
- recorded trades and trade features
- runtime health for the market-facing system

Apollo already includes an Olympus connector, but that connector currently reads exported runtime status rather than directly invoking Olympus code in-process. The code in this folder is the system behind that boundary.
The new read-only API allows Pantheon to read that same truth from another machine without copying the live runtime into Apollo.

## Current State Of Olympus

Olympus is already a real multi-part trading runtime, not just an experiment.

It already has:

- Alpaca paper broker connectivity
- a hardcoded liquid-equity universe
- repeated ranking cycles over recent intraday bars
- a selective "rank, qualify, then trade" execution flow
- side-specific long and short entry thresholds
- lightweight regime gating for trend, mixed, and degraded conditions
- dynamic symbol cooldown and suppression controls
- risk-aware paper-trading flow with flat-by-close enforcement
- SQLite-backed trade memory
- JSON ingestion for trade and ranking artifacts
- cycle diagnostics and daily reporting hooks for qualification and data quality
- tests across the major subsystems

What it does not yet claim is live-money execution. The present code is organized around paper-trading, runtime stability, and structured storage first.

## Profitability Upgrade Highlights

Olympus now layers a moderate profitability-control system on top of the original ranking engine rather than treating every ranked name as equally tradable.

The current execution model is:

1. rank the full universe
2. classify the current regime
3. qualify symbols with side-aware filters
4. enforce exposure, concentration, cooldown, and order-safety checks
5. manage exits with stop, target, rotation, stalled-trade pressure, and mandatory end-of-day liquidation

The most important upgrades in the current build are:

- separate long and short score, RVOL, and position-cap thresholds
- a regime classifier that can allow, constrain, or block entries
- qualification gates using normalized score, RVOL, range position, VWAP deviation, and ATR sanity
- sector concentration checks and dynamic symbol suppression after repeated poor outcomes
- more proactive exits in mixed conditions and less eager rotation in cleaner trend conditions
- persistent cycle diagnostics so reporting can explain what the system accepted, rejected, and why

## Runtime And Dependencies

Olympus currently depends on:

- Python
- Alpaca paper trading credentials
- `alpaca-py`
- `pandas`
- `pyarrow`
- `python-dotenv`
- `pytz`
- writable local storage for cache, logs, trades, rankings, and SQLite state

Runtime data is intentionally excluded from Git. On a working machine, Olympus will create and use local paths under `data/` for:

- market-data cache files
- logs
- ranking exports
- JSON trade records
- `olympus.db`
- generated daily reports and performance logs

When the Olympus API is used, these same local artifacts remain the source of truth; the API only exposes them read-only.

## Quick Start

```bash
# 1. Move into the Olympus app
cd apps/olympus

# 2. Create a local environment and install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Fill in credentials
copy .env.example .env
# then edit .env with Alpaca paper keys

# 4. Run the gate check
python main.py

# 5. Start the live paper runtime
python run_live.py
```

## Common Commands

```bash
cd apps/olympus
python main.py
python run_live.py
pytest
pytest -m "not integration"
python check_db.py
python tools/backtest_runner.py
```

## Data Ownership

Olympus owns:

- market-facing trading logic
- ranking outputs and signal generation
- paper-trade execution records
- trade-memory persistence
- execution qualification and regime gating behavior
- trading runtime health and scheduling behavior
- post-trade diagnostics for data quality and broker-state consistency

Olympus does not own:

- Apollo's user-facing interfaces
- Pantheon's cross-system reasoning policy
- BlackBook's financial ledger
- Maridian's reflective memory and journal processing

That boundary matters because Olympus should stay execution-focused and operationally reliable rather than absorbing unrelated reasoning or interface concerns.

## Documentation Contract

This README is a living system summary.

Whenever Olympus changes in any material way, this file should be updated in the same commit if the change affects:

- runtime entrypoints
- risk or execution behavior
- storage responsibilities
- subsystem boundaries
- external dependencies
- how Olympus integrates with Apollo or Pantheon

If code and documentation disagree, the code is the source of truth until this file is corrected.
