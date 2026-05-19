# Olympus — Changelog

> Chronological record of work since the master plan was finalized on
> March 25, 2026. Companion to olympus_status.md.

## Format

Entries are grouped by thematic batch, not strictly per-commit. Each entry
gives a date (or date range), a summary, the related commit SHAs, why the
work happened, and what it changed. Most recent work is at the top.

All SHAs were cross-checked against `git log` for the
`active/Olympus-Trading/` path. Line-delta figures (`+N/−M`) are taken from
`git log --stat`. This document does not assert that any test or script
passed — see olympus_status.md for the methodology note.

Two facts shape this changelog and are stated once here:

- The repository's git history begins **April 29, 2026**. The founding plans
  were finalized **March 25, 2026**. The ~5 weeks between have no granular
  commit history (see "Initial Consolidated Import" below).
- 23 commits touch `active/Olympus-Trading/`: 1 import (Apr 29) and 22
  stabilization commits (17 on May 9, 5 on May 18). Two further commits in
  the same push window are repo-wide and non-Olympus (see "Non-Olympus
  Housekeeping").

---

## Pre-Part-A Investigation & Safety Scripts (committed May 18, 2026)

**Commit:** `7c0b80f` (repository `HEAD`)

**Summary.** Added four read-only diagnostic scripts that vetted the codebase
and the runtime database before the Part A fill-confirmation engine was
built.

**Why this work happened.** Before rewriting the execution path, the
phantom-trade defect had to be characterized precisely and the codebase
checked for the same defect pattern elsewhere.

**What changed.** Added `scripts/investigations/fill_reconstruction_feasibility.py`,
`phantom_trade_forensics.py`, `pre_build_safety_checks.py`, and
`reconciler_behavior_analysis.py` (5 files including a `.gitignore` line,
+2,389). `pre_build_safety_checks.py` is explicitly a pre-Part-A safety
audit.

**Chronology note.** `7c0b80f` is the newest commit in the repository, which
is why this entry leads the changelog. However, the scripts' generated output
reports are timestamped 2026-05-17 — the investigation work was performed the
day *before* Part A and informed it. The commit landed after the Part A
commits only because the scripts were committed last. The substantive change
of the May 18 batch is the Part A engine in the next entry.

**Note for future readers.** `scripts/investigations/output/` is gitignored —
these scripts are tracked, their generated `.txt` reports are not.

---

## Part A — Fill Confirmation & Order-ID Linkage (May 18, 2026)

**Commits:** `ae51efc`, `c583cae`, `e0190db`, `c994ef6`

**Summary.** Replaced optimistic trade recording with a broker-confirmed
fill-confirmation engine, and added direct order-to-trade ID linkage.

**Why this work happened.** Investigation (see the entry above and
"Stabilization-Era Audit & Investigation Scripts" below) traced an equity
discrepancy to *phantom trades* — trades written to the local database with
no confirmed Alpaca fill. The mechanism, per
`scripts/investigations/REPORT_v2.md`, was the idiom
`order_info.get("filled_avg_price") or <planned price>` in `execution.py`,
which fabricated a fill price from the planned price whenever the broker had
not reported a fill.

**What changed.**

- `ae51efc` — Added nullable `entry_order_id` / `exit_order_id` columns to the
  `trades` table (`schema.sql` +6, `core/models.py` +6) and the migration
  `scripts/migrations/add_order_ids.py` (+100). The migration is idempotent
  by `PRAGMA table_info` inspection and never modifies row data; historical
  rows keep NULL.
- `c583cae` — Added a broker healthcheck to `core/broker/alpaca.py` (+87/−2)
  and fixed `get_order_by_id` usage.
- `e0190db` — Added the Part A fill-confirmation engine. `execution.py` was
  rewritten (+423/−34): submitted orders are polled via
  `AlpacaClient.get_order` on a fixed backoff schedule; a `TradeRecord` is
  written only on a broker-confirmed fill, always at the broker's
  `filled_avg_price` / `filled_qty` / `filled_at`. Canceled/expired/rejected
  orders and polling timeouts write no `TradeRecord` and emit an
  `order_unfilled` system_event. Supporting settings added to
  `config/settings.py` (+23); loop integration in `core/trading/loop.py`
  (+39).
- `c994ef6` — Wired runtime persistence of the confirmed Alpaca order IDs
  into `core/memory/writer.py` (+38) and the healthcheck precheck into
  `run_live.py` (+9).

**Verification status.** No test file targets the Part A poll loop directly
(`e0190db` added no test). No post-Part-A trading-week audit output is tracked
in the repo.

---

## Stabilization-Era Audit & Investigation Scripts (May 9, 2026)

**Commit:** `a22c1ed`

**Summary.** Added the first body of read-only diagnostic and audit tooling
used to locate and quantify the phantom-trade defect.

**Why this work happened.** An equity discrepancy between the local database
and the Alpaca paper account needed to be explained before any fix was built.

**What changed.** Added `scripts/equity_reconciliation.py`,
`scripts/operational_audit.py`, `scripts/phase4_audit.py`,
`scripts/quick_check.py`, and nine deep-dive scripts under
`scripts/investigations/` plus the tracked report
`scripts/investigations/REPORT_v2.md` (14 files, +3,510). REPORT_v2.md
attributes a $11,344.25 equity gap largely to phantom trades and states
"11 of 20 trading days (55%) show phantom trade patterns."

**Relationship to the May 18 investigation entry.** This is the May 9 half of
a continuous diagnostic thread; the four scripts in `7c0b80f` (top of this
changelog) extended it on May 17–18 ahead of Part A. The two commits are kept
as separate entries to preserve most-recent-first ordering.

---

## Open-Position Persistence Lifecycle (May 9, 2026)

**Commits:** `135fa91`, `396fc9e`, `d1310eb`, `2b5f37e`, `0b2d20e`,
`cd18e42`, `12d6c7b`, `a7ceb36`

**Summary.** Built durable persistence for live, in-flight positions across
the full entry → exit → restart lifecycle.

**Why this work happened.** Before this, in-flight positions lived only in
process memory. A runtime restart lost all knowledge of open positions, so
the system could neither reconcile against the broker nor resume management
of a live trade.

**What changed.**

- `135fa91` — Added the `open_positions` table (PK `position_id`, UNIQUE
  `(symbol, direction)`, FK `entry_cycle_id` ON DELETE SET NULL). The same
  commit also added the `ingestion_source_files` table and the
  `v_trade_quality_flags` view (`schema.sql` +110) — those are covered under
  their own entries below.
- `396fc9e` — Added open-position repository methods
  (`insert_open_position`, `get_open_positions`, `get_open_position_by_id`,
  `delete_open_position_by_id`, `update_open_position_last_seen`) and
  `get_apex_training_trades` / `get_trade_quality_summary`
  (`core/memory/repository.py` +120); added five settings to
  `config/settings.py` (+18), including `OPEN_POSITION_STALE_WARN_HOURS` and
  `OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS`.
- `d1310eb` — Entry-path persistence:
  `MemoryAwarePaperTradingLoop._run_cycle_inner` now detects new positions
  post-cycle and writes them to `open_positions` (`writer.py` +77).
  Persistence failure emits an `open_position_persistence_failed`
  system_event.
- `2b5f37e` — Added `scripts/verify_entry_path_optionB.py` (+159), which
  exercises the entry path against a temp database.
- `0b2d20e` — Added `MemoryWriter.write_trade_and_close_position`
  (`writer.py` +164), wrapping the `trades` INSERT and the `open_positions`
  DELETE in one SQLite transaction. A missing open-position row still inserts
  the trade and emits `orphaned_exit_no_open_row`; transaction failure emits
  `exit_path_transaction_failed`. The commit message notes a follow-up
  refactor to add a public transaction helper to `Database` — not done.
- `cd18e42` — Added `scripts/verify_exit_path.py` (+269), exercising the
  closed-trade path including the orphaned-exit case.
- `12d6c7b` — Added startup reconstruction of open positions from the
  persistent table to `run_live.py` (+170), seeding the in-memory
  `PositionManager` from durable state on restart.
- `a7ceb36` — Added `tests/phase4/test_open_positions_lifecycle.py` (+298, 6
  test functions).

**Verification status.** Two standalone verification scripts and one pytest
file exist for this track. No captured script output is tracked.

---

## BrokerReconciler (May 9, 2026)

**Commits:** `5544949`, `98bdc57`, `cc6e3c0`

**Summary.** Added a module that detects, and optionally repairs, divergence
between local position state and the broker's actual positions/orders.

**Why this work happened.** With positions now persisted, the system needed a
way to detect when local state and broker state had drifted apart — a
prerequisite for trusting the runtime after a restart or an unclean shutdown.

**What changed.**

- `5544949` — Added `core/trading/reconciliation.py` (+186):
  `detect_position_mismatch` (read-only) and `BrokerReconciler.check_and_repair`.
  Repair is gated by `OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS` (default False) and
  refuses to run unless `ALPACA_PAPER=True`. Added read-only broker helpers to
  `core/broker/alpaca.py` (+185), `PositionManager.clear_positions`
  (`manager.py` +9), runtime wiring in `run_live.py` (+20), and tests
  `tests/phase3/test_reconciliation.py` (95 lines) and
  `test_manager.py` (clear_positions coverage). 6 files, +505/−2.
- `98bdc57` — Fixed a runtime startup `TypeError`: `run_live.py` passed
  `broker_reconciler=` to the loop, but the `**kwargs` forwarder relayed it to
  `PaperTradingLoop`, which does not accept the kwarg. Made it an explicit
  optional parameter on `MemoryAwarePaperTradingLoop` (`writer.py` +13/−1).
- `cc6e3c0` — Documented the reconciler's source-of-truth chain (it compares
  broker state against in-memory `PositionManager` state, not `open_positions`
  directly) and propagated the broker-mismatch reason through `writer.py`,
  `loop.py`, and `reconciliation.py` (+29/−10).

**Completeness of this batch.** `git log --grep="reconcil" -i` on the Olympus
path returns five commits. The three above are the BrokerReconciler-module
work (and `git log` on `reconciliation.py` itself confirms only `5544949` and
`cc6e3c0` touch that file). The other two matches — `a22c1ed` and `cde6807` —
are reconciler-*adjacent* (investigation scripts; `/health` surfacing reconciler
settings) and are recorded under their own entries, not here.

**Verification status.** `tests/phase3/test_reconciliation.py` exists (7 test
functions, static count).

---

## Ingestion Validation & Source-File Fingerprinting (May 9, 2026)

**Commits:** `739ef81` (with the `ingestion_source_files` table from `135fa91`)

**Summary.** Added payload validation to the ingestion path and per-file
fingerprinting for fast restarts.

**Why this work happened.** Malformed upstream data could reach the database
unchecked, and restarts re-read already-ingested files.

**What changed.** `core/memory/ingestion.py` (+295) now rejects malformed JSON
payloads before insert — NaN/Infinity numbers, invalid UUIDs, oversized
strings, type-confused ranking items, and SQL-injection-shaped strings (SQL
is already parameterized, so these guards target corruption, not exploits).
Per-file fingerprints (size + `mtime_ns`) are recorded in the
`ingestion_source_files` table (added by `135fa91`) so subsequent runs skip
already-ingested files. Tests added to `tests/phase4/test_ingestion.py`
(+55) cover idempotent skip and the rejection cases.

**Verification status.** `tests/phase4/test_ingestion.py` exists (13 test
functions, static count).

---

## Trade-Quality View & Health Surfacing (May 9, 2026)

**Commits:** `cde6807` (with the `v_trade_quality_flags` view from `135fa91`)

**Summary.** Made trade-quality classification refresh on init and surfaced
quality state through the read-only API.

**Why this work happened.** The `v_trade_quality_flags` view (added by
`135fa91`) classifies each trade as `clean` or one of four `suspect_*`
labels; this state needed to be kept current and observable.

**What changed.** `cde6807` registered `v_trade_quality_flags` in
`_REFRESHABLE_VIEWS` so it is dropped and recreated on `initialize()`,
changed the database lock to an `RLock` to permit reentrant DDL during init,
and added an `execute_ddl()` helper that validates identifiers
(`database.py` +17). `api.py` (+13) `/health` now returns
`latest_clean_trade_at`, `broker_mismatch_events`, `trade_quality_counts`,
and three reconciler-related settings flags, and resolves paths through
`settings.*` instead of `os.getenv`.

---

## Schema & Repository Test Backfill (May 9, 2026)

**Commits:** `18012f7`

**Summary.** Added tests for schema and repository changes that had landed
without coverage.

**What changed.** `tests/phase4/test_schema.py` (+3) now asserts the
`ingestion_source_files` table, the `v_trade_quality_flags` view, and
`idx_ingestion_source_files_status`. `tests/phase4/test_repository.py` (+45)
covers `get_apex_training_trades` (clean-only filtering) and
`get_trade_quality_summary`.

---

## Runtime-Layout Hardening & Artifact Cleanup (May 9, 2026)

**Commits:** `b1b9237`, `2de769a`

**Summary.** Documented the canonical runtime data location, hardened the
launcher, and stopped tracking stale runtime artifacts.

**Why this work happened.** Repo-local data files (a stale `olympus.db`) were
being mistaken for canonical runtime data, and the launcher used a hardcoded
absolute path.

**What changed.**

- `b1b9237` — Added a "Runtime Source Of Truth" section to `olympus/README.md`
  (+17) pointing operators at `C:\Users\ignac\OlympusLocal\data` as the
  canonical live-data path; replaced a hardcoded path in `launch_olympus.bat`
  with `%~dp0olympus` and made it refuse to start when the Python executable
  or `run_live.py` is missing; added a parent `.gitignore` (+16) for runtime
  artifacts; archived the May-7 stabilization audit to
  `docs/audits/2026-05-07-stabilization-audit.md` (+561). 4 files, +616/−1.
- `2de769a` — Removed the stale tracked `data/olympus.db` (an 18.96 MB
  repo-local SQLite copy that the runtime never wrote to) and a leftover
  `olympus.pid`; removed two orphaned journal files from disk.

---

## Initial Consolidated Import (April 29, 2026)

**Commit:** `7754da5`

**Summary.** The entire existing Olympus codebase was imported into this
repository in a single commit, "Initial consolidated AI projects import."

**The March 25 → April 29 gap.** The founding plans (master plan, build plan)
were finalized **March 25, 2026** as pre-code blueprints. This repository's
git history begins **April 29, 2026** with this import. Whatever Phase 1–5
code, schema, and tests were written in the intervening ~5 weeks arrived here
as one commit; there is **no granular, per-commit history for that period**.
This changelog does not attempt to reconstruct it.

**What the import contained (as observed at `HEAD`).** Phase 1–4 code per the
build plan, plus Phase 5 reporting code (`core/reporting/`), the canonical
`core/memory/schema.sql`, and the `tests/phase1`–`phase5` suites. The import
also brought unrelated projects (Pantheon/Apollo and others) into the
monorepo.

**Note.** The status of Phase 5 is contradicted between `CLAUDE.md` and
`README.md`; see olympus_status.md. This changelog does not resolve it.

---

## Non-Olympus Housekeeping (April 29, 2026)

**Commits:** `362b5d7`, `69087e0`

These two commits fall in the same push window but do not touch
`active/Olympus-Trading/`. `362b5d7` rewrote the repo README for the
consolidated layout; `69087e0` added a missing package marker for an
archived "maridian" utils package. They are recorded here only so the
chronology has no gap; they are not Olympus work.

---

## March 25, 2026 — Master Plan Finalized

Reference point. The founding documents — `olympus_master_plan.md`
(v1.0, "Blueprint Finalized") and `olympus_build_plan.md` — were finalized on
this date as pre-code blueprints. They predate this repository's git history
and remain frozen by design. All work above postdates them.
