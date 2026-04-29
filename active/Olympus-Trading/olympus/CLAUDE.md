# CLAUDE.md — Olympus Project Intelligence File

This file is the authoritative context document for all Claude Code sessions working on Olympus.
Read this file completely before taking any action in this codebase.

---

## What Olympus Is

Olympus is a private, single-user trading and market-learning operating system. It is not a public
product. It is a personal command center built around one user, one workflow, and one goal: building
a system that becomes increasingly intelligent and eventually profitable without becoming reckless,
unstable, or impossible to understand.

The system has three named identities:

| Identity | Role |
|----------|------|
| **OLYMPUS** | The body — full platform, interface, and operational loops |
| **APEX** | The brain — memory, interpretation, and judgment layer |
| **PANTHEON** | The council — structured reflection and prioritized improvement |

The governing philosophy of the entire system:
> **Learn broadly. Change selectively. Risk real money slowly.**

---

## The 8-Phase Build Plan

Olympus is built in strict sequential phases. Each phase has a defined output and a gate that must
pass before the next phase begins. Do not build anything that belongs to a later phase.

| # | Phase | Primary Deliverable | Status |
|---|-------|-------------------|--------|
| 1 | **Data Foundation** | Reliable data pipeline + Alpaca connection + scheduler | ✅ Complete |
| 2 | **Ranking Engine** | Automated long/short ranking on defined cycle | ✅ Complete |
| 3 | **Paper Trading Loop** | Autonomous paper entries, management, exits, rotation | ✅ Complete |
| 4 | **Memory & Storage** | Persistent structured storage of all meaningful outputs | ✅ Complete |
| 5 | **Apex Intelligence Core** | Memory interpretation, reporting, pattern surfacing | 🔲 Not started |
| 6 | **Pantheon Debate Layer** | Five-role debate producing single clear conclusions | 🔲 Not started |
| 7 | **Controlled Evolution** | Three-tier conclusion lifecycle; human-gated promotions | 🔲 Not started |
| 8 | **App Interface & Live Gate** | Five-tab Olympus app; live trading mechanism | 🔲 Not started |

**The minimum viable Olympus is Phases 1–4.** That is the earliest point at which the system is
observing, ranking, trading on paper, and remembering — the core learning loop.

---

## Current Project Structure
```
olympus/
├── config/
│   └── settings.py              # Frozen dataclass — all config from .env (Phase 3 fields added)
├── core/
│   ├── logger.py                # get_logger() — all modules use this
│   ├── universe.py              # UniverseManager — 185 liquid US equities
│   ├── models.py                # Shared dataclasses: BarFeatures, RankedSymbol, RankedUniverse,
│   │                            #   Direction, TradeStatus, Position, TradeRecord, LoopState
│   ├── data/
│   │   ├── fetcher.py           # DataFetcher — batch fetch, retry, ET conversion
│   │   ├── normalizer.py        # Pure normalization → guaranteed list[dict] schema
│   │   └── cache.py             # DataCache — parquet on disk, MD5-keyed
│   ├── broker/
│   │   └── alpaca.py            # AlpacaClient — paper-only hard guard + order methods
│   ├── ranking/
│   │   ├── features.py          # compute_features() — zero external deps, stdlib only
│   │   ├── scorer.py            # normalize_scores(), classify_direction()
│   │   ├── engine.py            # RankingEngine.run_cycle() — never raises
│   │   └── cycle.py             # RankingCycle — thread-safe, scheduler-backed
│   ├── trading/
│   │   ├── risk.py              # validate_entry() — 6-gate pure function guard
│   │   ├── sizing.py            # calculate_size(), calculate_stop_and_target() — pure functions
│   │   ├── execution.py         # ExecutionEngine — paper order placement, never raises
│   │   ├── manager.py           # PositionManager — lifecycle, exits, rotations
│   │   └── loop.py              # PaperTradingLoop — full cycle orchestration, never raises
│   ├── memory/
│   │   ├── schema.sql           # Canonical DB schema — 8 tables, 21 indexes, 5 views
│   │   ├── database.py          # Database — SQLite connection, WAL, foreign keys, thread-safe
│   │   ├── ingestion.py         # Ingestion — idempotent JSON → SQLite (trades + rankings)
│   │   ├── writer.py            # MemoryWriter + MemoryAwarePaperTradingLoop subclass
│   │   └── repository.py        # Repository — all read queries for Phase 5+ consumption
│   └── scheduler.py             # Scheduler — background thread, boundary-aligned
├── data/
│   ├── cache/                   # Parquet files for historical bar cache
│   ├── rankings/                # JSON files for completed RankedUniverse cycles
│   ├── trades/                  # JSON trade records — one file per completed trade
│   ├── logs/                    # Rotating log files
│   └── olympus.db               # SQLite database (Phase 4+)
├── tests/
│   ├── phase1/                  # 22 unit tests — all pass
│   ├── phase2/                  # 49 unit tests — all pass
│   ├── phase3/                  # 62 unit tests — all pass
│   └── phase4/                  # 36 unit tests — all pass
├── main.py                      # Gate check entry point — Phases 1, 2, 3 & 4
├── run_live.py                  # Continuous paper-trading runtime — run this to operate Olympus
├── requirements.txt
├── pytest.ini
└── .env.example
```

---

## Key Architectural Decisions Already Made

**Data format:** The normalizer produces `list[dict]`. Every bar dict is guaranteed to have:
`symbol`, `timestamp` (ET, timezone-aware), `open`, `high`, `low`, `close`, `volume`, `vwap`.
This contract must not change.

**Ranking output:** `RankedUniverse` is the handoff artifact from Phase 2 to Phase 3. Its schema
must not change after Phase 2 without explicit versioning. Phase 3 consumes
`RankingCycle.get_top_longs()` and `get_top_shorts()`.

**Scoring thresholds:** Long candidates require normalized_score >= 60. Short candidates require
normalized_score <= 40. Neutral (40–60) is excluded from trading. Maximum 20 candidates per
direction per cycle.

**Paper-only guard:** `AlpacaClient` raises immediately if `ALPACA_PAPER=False`. Live trading is
not enabled until Phase 8. This guard is permanent and must never be removed or bypassed.

**Failure contracts:**
- `RankingEngine.run_cycle()` — must never raise. Always returns a valid RankedUniverse.
- `Scheduler` — callable failures are logged but do not crash the scheduler.
- All future components that run on a cycle must follow the same never-raise contract.

**Storage:** Phase 1–2 uses only disk cache (parquet) and ranking JSON files. A proper database
does not exist until Phase 4. Do not introduce any database before Phase 4.

**Database timestamps:** All timestamps in `olympus.db` are stored as UTC ISO 8601 strings.
ET conversion is only applied at display/log layers. Every UPDATE statement must explicitly
set `updated_at` — do not rely on DEFAULT for updates.

**Cycle foreign keys:** `trades.entry_cycle_id` and `trades.exit_cycle_id` are NULL for all
trades ingested from Phase 3 JSON files. Live wiring of these FK columns is a Phase 5 concern.

**No ML:** Machine learning does not exist in Olympus until Phase 5 at the earliest, and only
after rule-based Apex interpretation is proven. Do not add any ML library before Phase 5.

---

## What Each Future Phase Will Build

### Phase 3 — Paper Trading Loop
- Paper account integration via Alpaca paper environment
- Entry logic: compare current holdings against top-ranked candidates each cycle
- Position sizing tied to paper portfolio equity
- Exit logic: structure-based stops and profit targets
- Rotation logic: exit dropped positions, enter stronger candidates
- Trade record produced for every entry and exit
- Consumes: `RankingCycle.get_top_longs()` / `get_top_shorts()`
- Produces: structured trade records ready for Phase 4 storage

### Phase 4 — Memory & Storage
- SQLite database — all trade records, ranking cycles, events
- Trade schema: based on 16-column ledger design (trade_id, timestamp_et, symbol, direction,
  entry/stop/target price, size, reason, status, realized_pnl, r_multiple, rejection_reason,
  source, experiment_id, strategy_name)
- Run record capture: every ranking cycle stored with top candidates and changes
- Consistent schema — all records same fields, all queries reliable
- Must accumulate several weeks of data before Phase 5 is meaningful

### Phase 5 — Apex Intelligence Core
- Memory query engine: pull relevant records by time, symbol, outcome
- Pattern summarization: which assets/conditions/hold durations have performed well
- Risk flag generation: repeated losses, bad-outcome clustering
- Report generation: structured weekly/on-demand summaries
- Three output modes: System Mode (Olympus), Analysis Mode (Pantheon), Chat Mode (user)
- Rule-based and pattern-based only — no ML at this stage

### Phase 6 — Pantheon Debate Layer
- Five roles: Researcher, Critic, Risk Manager, Optimizer, Judge
- Receives curated Apex report as input
- Sequenced debate flow — each role sees prior role outputs
- Judge collapses debate into one clear conclusion + one next action
- Every Pantheon conclusion stored back into Apex memory
- LLM client: use `claude-sonnet-4-6` model

### Phase 7 — Controlled Evolution
- Three-tier lifecycle: Observation → Candidate → Promotion
- Candidate testing queue: backtest/replay before promotion consideration
- Promotion requires explicit human approval before any system change
- Change log: every modification traceable to a Pantheon conclusion
- Rollback capability: any promoted change can be reversed

### Phase 8 — App Interface & Live Gate
- Five tabs: Dashboard, Apex, Trading, Pantheon, System
- Dashboard: portfolio overview, PnL, top opportunities, system heartbeat
- Apex tab: conversational interface connected to Apex intelligence core
- Trading tab: paper and live positions, entries/exits, PnL per position
- Pantheon tab: role contributions, debate flow, Judge conclusion per cycle
- System tab: settings, API keys, logs, run history
- Live trading gate: explicitly activated, human confirmation required at every step
- **Paper trading remains fully autonomous. Live trading remains permanently human-gated.**

---

## Hard Rules — Apply to Every Phase

1. **Never raise from a cycle.** Any component that runs on a scheduler must catch all exceptions,
   log them, and return a valid (possibly empty) result. The loop must never die.

2. **Paper guard is permanent.** `AlpacaClient` must never be instantiated in live mode before
   Phase 8. The guard in `core/broker/alpaca.py` must not be removed or weakened.

3. **No phase-jumping.** Do not build any component that belongs to a later phase. If you identify
   something that belongs to Phase 5 while building Phase 3, note it and stop. Build what the
   current phase requires and nothing else.

4. **Every module uses `get_logger(__name__)`.** No bare `print()` in production code paths.
   No direct `logging.getLogger()` calls. Import from `core.logger`.

5. **All credentials from `.env` only.** No hardcoded API keys anywhere. Ever.

6. **Modify Phase 1 or 2 files only when necessary.** If a change to an earlier phase file is
   required, note it explicitly — what changed, why, and confirm tests still pass.

7. **The `RankedUniverse` schema is frozen.** Phase 3 depends on it. Do not change field names,
   types, or structure without explicit versioning.

8. **No ML before Phase 5.** Do not add sklearn, torch, tensorflow, or any ML library before the
   rule-based interpretation layer in Phase 5 is proven.

9. **No database before Phase 4.** Do not introduce SQLite, Postgres, or any structured DB before
   Phase 4. Use the existing cache and JSON files for anything Phases 1–3 need to persist.

10. **No UI before Phase 8.** Do not build any web framework, dashboard, or frontend before the
    entire machine behind it is real and running.

---

## Running the Project
```bash
# Install dependencies
pip install -r requirements.txt

# Set up credentials
cp .env.example .env
# Fill in ALPACA_API_KEY and ALPACA_SECRET_KEY from your Alpaca paper account

# Run gate checks — verifies all phases initialized correctly (run once to confirm setup)
cd olympus
python main.py

# Run the live paper-trading runtime — this is the always-on process
cd olympus
python run_live.py

# Run unit tests (no credentials needed)
python -m pytest tests/ -v -m "not integration"

# Run integration tests (requires credentials + market data availability)
python -m pytest tests/ -v
```

**Entrypoint distinction:**
- `main.py` — gate-check script. Initializes everything, runs one cycle of each phase, prints pass/fail summary, then exits. Run this to confirm your setup is correct.
- `run_live.py` — continuous runtime. Stays alive, fires trading cycles on schedule, writes all results to `olympus.db`. This is the process that actually accumulates data.

---

## The Full Operational Loop (When Complete)

1. Market observed across 185-symbol universe
2. Ranking engine produces long/short lists every 20 minutes
3. Paper trading acts on ranked candidates fully autonomously
4. Results stored in persistent memory (Apex)
5. Apex interprets outputs — patterns, risk flags, reports
6. Pantheon debates Apex findings through five roles
7. Judge collapses debate into one conclusion + one action
8. Conclusion stored back into Apex memory
9. Controlled evolution evaluates conclusion tier
10. Promotions require human approval before any system change
11. Live trading permanently human-gated

> *The system becomes intelligent through accumulation, not through rushing.*
