# Olympus — Current Status

> Companion document to olympus_master_plan.md and olympus_build_plan.md.
> Those describe the intended architecture. This describes the current
> reality. Last updated: 2026-05-18.

> **Sourcing rule for this document.** Every claim below is grounded in
> observable evidence: git history, file contents, commit messages, the
> existing `olympus/CLAUDE.md`, `olympus/README.md`, the canonical
> `schema.sql`, or investigation-script outputs. Where the evidence is
> ambiguous or two sources disagree, that is stated explicitly rather
> than resolved.

---

## How to Read This Document

The founding plans (master plan, build plan) were finalized on
**March 25, 2026** as pre-code blueprints. They remain frozen by design.

The git history of this repository begins **April 29, 2026** with a single
"Initial consolidated AI projects import" commit (`7754da5`) that landed the
entire existing Olympus codebase — Phase 1–5 code, the database schema, and
the test suite — in one commit. There is **no granular commit history for the
period March 25 → April 29**; that work is not individually attributable.

All individually attributable history is the two post-import stabilization
batches (22 commits total; 23 commits touch `active/Olympus-Trading/` once
the April 29 import is included):

- **May 9, 2026** — 17 commits
- **May 18, 2026** — 5 commits

This document describes the state of the system as of the most recent push
(`HEAD = 7c0b80f`).

**Methodology.** This document was produced by reading files, git history,
and commit messages only. It did **not** run any tests, execute any scripts,
or exercise the trading loop. Wherever it says "static count," "not
independently verified here," or similar, that phrasing is literal — the
claim rests on file contents, not on an observed run.

---

## Phase Status (at a glance)

"Structural" means the code exists per the build plan. "Operational" means it
has been observed to work end-to-end with verification evidence in the repo.
These two columns diverge deliberately — the divergence is the point of this
table.

| Phase | Structural | Operational | Notes |
|---|---|---|---|
| 1 — Data Foundation | Code present | Not independently verified here | `core/data/`, `core/broker/`, `scheduler.py` present. `tests/phase1/` has 3 files. |
| 2 — Ranking Engine | Code present | Not independently verified here | `core/ranking/` present. `tests/phase2/` has 3 files. |
| 3 — Paper Trading Loop | Code present | In stabilization | Phantom-trade defect found and addressed by the Part A fill-confirmation engine (May 18). |
| 4 — Memory & Storage | Code present | In stabilization | Live schema extended post-import (open_positions, ingestion fingerprinting, order-ID columns). |
| 5 — Apex Intelligence Core | **Disputed** | **Disputed** | CLAUDE.md says "Not started"; README.md says "live". See dedicated subsection. |
| 6 — Pantheon Debate Layer | Not started | Not started | `pantheon_conclusions` table exists in schema; no module. |
| 7 — Controlled Evolution | Not started | Not started | — |
| 8 — App Interface & Live Gate | Not started | Not started | Live trading remains gated by the permanent paper-only guard. |

This document does **not** assert that any phase "passes" or is "complete."
It records what code is present and what verification evidence exists.

---

## Where Each Phase Actually Stands

### Phase 1 — Data Foundation

**What's built.** `core/data/` (fetcher, normalizer, cache), `core/broker/alpaca.py`,
`core/scheduler.py`, `core/universe.py`. Per CLAUDE.md the universe is 185 liquid
US equities and the normalizer emits a guaranteed `list[dict]` bar contract.

**Verification evidence in the repo.** `tests/phase1/` contains `test_alpaca.py`,
`test_data.py`, `test_scheduler.py` — 36 test functions across the three files
(static count). Compiled pytest artifacts (`__pycache__`, pytest 9.0.3,
Python 3.14) indicate the suite has been executed at some point; that is not
current-pass evidence.

**Stabilization work touching this phase.** `core/broker/alpaca.py` was extended
post-import: read-only snapshot helpers for the reconciler and audit scripts
(`5544949`), and a broker healthcheck (`c583cae`).

**Known gaps.** None observed beyond the general note that no test run is
captured with logged output in the repo.

### Phase 2 — Ranking Engine

**What's built.** `core/ranking/` (features, scorer, engine, cycle). Per CLAUDE.md
`RankingEngine.run_cycle()` follows a never-raise contract and long/short
thresholds are normalized_score >= 60 / <= 40.

**Verification evidence in the repo.** `tests/phase2/` contains `test_engine.py`,
`test_features.py`, `test_scorer.py` — 49 test functions (static count).

**Stabilization work touching this phase.** None directly. Ranking output is
consumed downstream by the trading loop and is one input to the
`v_trade_quality_flags` "stale_ranking" classification.

**Known gaps.** None observed.

### Phase 3 — Paper Trading Loop

**What's built.** `core/trading/` — `risk.py`, `sizing.py`, `execution.py`,
`manager.py`, `loop.py`, plus `qualification.py`, `regime.py`, and the
post-import `reconciliation.py`.

**The defect found during stabilization.** The tracked file
`scripts/investigations/REPORT_v2.md` traces an equity discrepancy of
**$11,344.25** to *phantom trades* — trades recorded in the local database
with no confirmed Alpaca fill — and states "11 of 20 trading days (55%) show
phantom trade patterns." (Both figures are quoted from REPORT_v2.md, which is
tracked in the repo.) The mechanism: per REPORT_v2.md's "Phantom Trade Bug
Locations" section, `execution.py` used the idiom
`order_info.get("filled_avg_price") or <planned price>`, which fabricated a
fill price from the planned price whenever the broker had not reported a
fill. The same finding is recorded with line numbers in the *untracked*
diagnostic output `pre_build_safety_report.txt` (`execution.py:65` entry,
`:116` exit) — that line-level detail is not in the cloned repo.

**What was done about it.** The **Part A fill-confirmation engine** (`e0190db`,
May 18) rewrote `execution.py` (+423/−34). Per the module docstring, an order
is now polled via `AlpacaClient.get_order` on a fixed backoff schedule; a
`TradeRecord` is written **only** on a broker-confirmed fill, and **always** at
the broker's `filled_avg_price` / `filled_qty` / `filled_at`. If the order is
canceled/expired/rejected or polling times out, no `TradeRecord` is written
and an `order_unfilled` system_event is emitted.

**Verification evidence in the repo.** `tests/phase3/` contains 6 files — 82
test functions (static count), including `test_reconciliation.py` (7) and
`test_loop.py` (17). Two standalone verification scripts exist:
`scripts/verify_entry_path_optionB.py` (`2b5f37e`) and
`scripts/verify_exit_path.py` (`cd18e42`). These exercise the entry and exit
paths through `MemoryAwarePaperTradingLoop` against a temp database. The
repo does not contain captured output logs from these scripts.

**Known gaps / stabilization in progress.** Part A landed on May 18 and is
the most recent change to the trading path. No post-Part-A trading-week audit
output is present in the tracked repo. The trading loop's operational status
is therefore "in stabilization."

### Phase 4 — Memory & Storage

**What's built.** `core/memory/` — `schema.sql`, `database.py`, `ingestion.py`,
`writer.py`, `repository.py`, `enrichment.py`. The live schema is 10 tables,
21 indexes, 7 views (see Schema section).

**Stabilization work since the import.** Substantial — see the Stabilization
Track section. In brief: `open_positions` persistence, atomic exit
transaction, ingestion validation and source-file fingerprinting, the
`v_trade_quality_flags` view, and the `entry_order_id`/`exit_order_id`
columns plus their migration.

**Verification evidence in the repo.** `tests/phase4/` contains 5 files — 51
test functions (static count): `test_ingestion.py` (13),
`test_open_positions_lifecycle.py` (6), `test_repository.py` (14),
`test_schema.py` (7), `test_writer.py` (11). `test_schema.py` and
`test_repository.py` were extended (`18012f7`) to cover the landed schema and
repository changes.

**Known gaps.** The exit-path transaction (`0b2d20e`) touches
`Database._lock` directly because `Database` has no public
transaction-context helper; the commit message names a follow-up refactor to
add one. Not done.

### Phase 5 — Apex Intelligence Core (status disputed)

**This subsection documents a contradiction it does not resolve.** Resolving
it is a deliberate decision left to the project owner.

**Claim A — `olympus/CLAUDE.md`.** The phase table marks Phase 5 as
"🔲 Not started." CLAUDE.md elsewhere states "The minimum viable Olympus is
Phases 1–4."

**Claim B — `olympus/README.md`.** States *"Phase 5 is now real in the
codebase,"* *"Olympus is currently strongest across Phases 1 through 5,"* and
that Olympus persists structured Apex report types (`daily_performance`,
`weekly_performance`, `risk_watch`, `ranking_behavior`) into `apex_reports`.

**On-disk evidence.**

- `core/reporting/` directory exists, containing `apex_reports.py` and
  `daily_report.py`. (CLAUDE.md's "Current Project Structure" section does
  **not** list `core/reporting/` at all.)
- The `apex_reports` table is defined in `schema.sql` (lines 202–214), with
  `idx_apex_reports_generated_at` and `idx_apex_reports_type`.
- `tests/phase5/test_apex_reports.py` exists — 4 test functions (static
  count).
- `scripts/backfill_trade_self_description.py` exists and is referenced by
  README as the repair path for pre-enrichment databases.
- **Neither document is dated or version-stamped.** `CLAUDE.md` and
  `README.md` both lack any date, version field, or "last updated" marker in
  their text. A "the more recent document wins" heuristic therefore cannot be
  applied from the documents' own content; their relative recency would have
  to be established from git history of those two files specifically, which
  this document has not done.

**What this document concludes.** It does not conclude. CLAUDE.md and
README.md make incompatible claims about Phase 5, and both are tracked files
in the same repository. The on-disk evidence shows Phase 5 *reporting code*
exists; it does not by itself establish operational status. This contradiction
is recorded here and in "Open Questions / Known Issues" for the project owner
to resolve.

### Phases 6–8

**Phase 6 — Pantheon Debate Layer.** Not started. The `pantheon_conclusions`
table is defined in `schema.sql` (and README notes it as "schema present, not
yet in active use"), but no debate module exists in `core/`.

**Phase 7 — Controlled Evolution.** Not started.

**Phase 8 — App Interface & Live Gate.** Not started. Live trading remains
disabled — the permanent paper-only guard in `core/broker/alpaca.py` (raises
if `ALPACA_PAPER=False`) is unchanged.

---

## Stabilization Track (work not described by the build plan)

The build plan is a pre-code blueprint. None of the work in this section has
an entry in it. This is post-Phase-4 reliability work, driven by defects
found in the live runtime. It is the most consequential change to the system
since the import. Every commit SHA cited in this section was checked against
`git log`.

### open_positions persistence

**What it is.** A new `open_positions` table (`135fa91`) holding live,
in-flight position state, with repository methods (`396fc9e`) and an
entry-path writer that persists a position the moment it opens (`d1310eb`).

**Why it exists.** Before this, in-flight positions lived only in process
memory. A runtime restart lost all knowledge of open positions, so the system
could not reconcile against the broker or resume management of a live trade.

**Where it lives.** Table in `core/memory/schema.sql`; repository methods
(`insert_open_position`, `get_open_positions`, `get_open_position_by_id`,
`delete_open_position_by_id`, `update_open_position_last_seen`) in
`core/memory/repository.py`; entry-path persistence in
`MemoryAwarePaperTradingLoop._run_cycle_inner` in `core/memory/writer.py`.
Persistence failure emits an `open_position_persistence_failed` system_event
so silent breakage is visible.

### Atomic close + open_positions removal

**What it is.** `MemoryWriter.write_trade_and_close_position` (`0b2d20e`)
wraps the `trades` INSERT and the `open_positions` DELETE in one SQLite
transaction.

**Why it exists.** A closed trade and the removal of its open-position row
must not diverge. If no matching `open_positions` row exists (the entry path
silently failed for that position before this work), the trade still inserts
and an `orphaned_exit_no_open_row` system_event is emitted so the gap is
visible. Transaction failures emit `exit_path_transaction_failed` at error
severity.

**Where it lives.** `core/memory/writer.py`; verified by
`scripts/verify_exit_path.py`.

### Startup reconstruction of open positions

**What it is.** `run_live.py` reconstructs open positions from the persistent
`open_positions` table at startup (`12d6c7b`, +170 lines).

**Why it exists.** It is the consumer side of `open_positions` persistence —
on restart, the in-memory `PositionManager` is seeded from durable state so
the trusted source-of-truth chain (per `reconciliation.py` docstring) is
intact before the reconciler runs.

**Where it lives.** `run_live.py`.

### BrokerReconciler

**What it is.** `core/trading/reconciliation.py` (`5544949`):
`detect_position_mismatch` (read-only) and `BrokerReconciler.check_and_repair`.

**Why it exists.** To detect divergence between local position state and the
broker's actual positions/orders. The repair path is gated by
`OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS` (default False) and refuses to run
unless `ALPACA_PAPER=True`; on misconfiguration it raises explicitly rather
than failing silently. Per the module docstring, the reconciler compares
broker state against the in-memory `PositionManager` state — not against
`open_positions` directly.

**Where it lives.** `core/trading/reconciliation.py`; wired into `run_live.py`
startup; broker read helpers in `core/broker/alpaca.py`;
`PositionManager.clear_positions` (`core/trading/manager.py`) supports the
repair path. Behavior is described in
`scripts/investigations/output/reconciler_behavior_report.txt` (untracked).

### Part A fill-confirmation engine

**What it is.** A rewrite of `core/trading/execution.py` (`e0190db`, +423/−34)
that polls each submitted order to a broker-confirmed fill before writing a
`TradeRecord`.

**Why it exists.** To eliminate phantom trades — see Phase 3 above. The
pre-Part-A `.get("filled_avg_price") or <planned price>` idiom fabricated
fills; REPORT_v2.md attributes a $11,344.25 equity gap largely to this.

**Where it lives.** `core/trading/execution.py`; supporting settings in
`config/settings.py` (e.g. `FILL_CONFIRM_BACKOFF`); loop integration in
`core/trading/loop.py`.

### Broker healthcheck + precheck wiring

**What it is.** A broker healthcheck in `core/broker/alpaca.py` (`c583cae`,
+87) and a precheck wired into the runtime (`c994ef6`).

**Why it exists.** To surface broker-connectivity problems at startup rather
than mid-cycle. `c583cae` also fixed `get_order_by_id` usage.

**Where it lives.** `core/broker/alpaca.py`, `run_live.py`.

### Ingestion validation + source-file fingerprinting

**What it is.** `core/memory/ingestion.py` (`739ef81`, +295) now rejects
malformed JSON payloads before insert (NaN/Infinity numbers, invalid UUIDs,
oversized strings, type-confused ranking items, SQL-injection-shaped strings)
and records per-file fingerprints (size + `mtime_ns`) in the new
`ingestion_source_files` table.

**Why it exists.** The validation guards catch upstream data corruption
before it reaches the database (SQL is already parameterized, so injection
cannot succeed — these guards target corruption, not exploits). The
fingerprints let restarts skip already-ingested files without re-reading
them.

**Where it lives.** `core/memory/ingestion.py`; `ingestion_source_files`
table and `idx_ingestion_source_files_status` in `schema.sql`. Tested in
`tests/phase4/test_ingestion.py`.

### Order-ID columns + migration

**What it is.** Two nullable columns, `trades.entry_order_id` and
`trades.exit_order_id` (`ae51efc`), the migration
`scripts/migrations/add_order_ids.py`, and runtime persistence of the IDs
from confirmed Alpaca orders (`c994ef6`).

**Why it exists.** REPORT_v2.md's schema-linkage analysis found *no direct ID
linkage* between local trades and Alpaca orders, forcing fragile heuristic
matching during reconciliation. These columns give new live trades a direct
order-to-trade link for future reconciliation work (the commit messages call
this "Part B"). Historical rows keep NULL — the migration never modifies row
data and is idempotent by `PRAGMA table_info` inspection.

**Where it lives.** `trades` table in `schema.sql` (lines 116–121);
`core/models.py`; `scripts/migrations/add_order_ids.py`;
persistence in `core/memory/writer.py`.

### Trade-quality flagging

**What it is.** The `v_trade_quality_flags` view (`135fa91`) classifies each
trade as `clean`, `suspect_broker_mismatch`, `suspect_repair_day`,
`suspect_runtime_gap`, or `suspect_stale_ranking`, based on `system_events`
on the trade's entry day and whether `entry_cycle_id` is NULL.

**Why it exists.** To separate trades safe for downstream (Apex) consumption
from trades that occurred under degraded conditions. Repository methods
`get_apex_training_trades` (clean-only) and `get_trade_quality_summary`
consume it (`396fc9e`); the `/health` API endpoint surfaces quality counts
(`cde6807`).

**Where it lives.** `v_trade_quality_flags` in `schema.sql`;
`core/memory/repository.py`; `core/memory/database.py` registers it as a
refreshable view; `api.py`.

---

## Schema (current)

Derived from `core/memory/schema.sql` as of `HEAD`. **10 tables, 21 indexes,
7 views.** All timestamps are UTC ISO 8601 strings. `journal_mode = WAL`,
`foreign_keys = ON`.

**Tables.**

| Table | Purpose | Notable columns / keys |
|---|---|---|
| `ingestion_runs` | One row per ingest job | `run_id` PK; `status` CHECK running/completed/failed |
| `ingestion_source_files` | Per-file ingest fingerprints | PK `(source_type, source_file)`; `file_size`, `mtime_ns` — **added post-import** (`135fa91`) |
| `ranking_cycles` | One row per completed ranking cycle | `cycle_id` PK; `top_longs_json`, `top_shorts_json` |
| `cycle_rankings` | Per-symbol ranks within a cycle | FK `cycle_id` → `ranking_cycles` ON DELETE CASCADE; UNIQUE `(cycle_id, symbol, direction)` |
| `trades` | Every completed paper trade | `trade_id` PK; `entry_cycle_id`/`exit_cycle_id` FK → `ranking_cycles`; `entry_order_id`/`exit_order_id` — **added post-import** (`ae51efc`); UNIQUE `(position_id, entry_time)` |
| `open_positions` | Live in-flight position state | `position_id` PK; UNIQUE `(symbol, direction)`; FK `entry_cycle_id` ON DELETE SET NULL — **added post-import** (`135fa91`) |
| `trade_features` | Feature snapshot at entry | `trade_id` PK, FK → `trades` ON DELETE CASCADE |
| `system_events` | Operational event log | `id` autoincrement; `event_type`, `metadata_json` |
| `apex_reports` | Structured Apex reports | `report_id` PK; `consumed_by_pantheon` flag — Phase 5 surface (see disputed status) |
| `pantheon_conclusions` | Debate / judge outputs | `conclusion_id` PK; `tier` CHECK observation/candidate/promotion — Phase 6, schema only |

**Views.** `v_trades_full`, `v_trades_enriched`, `v_symbol_performance`,
`v_exit_reason_stats`, `v_rolling_7day`, `v_feature_buckets`,
`v_trade_quality_flags` (the last added post-import, `135fa91`).

**Foreign keys of note.** `trades.entry_cycle_id` / `exit_cycle_id` →
`ranking_cycles.cycle_id`; `open_positions.entry_cycle_id` →
`ranking_cycles.cycle_id` ON DELETE SET NULL; `trade_features.trade_id` /
`cycle_rankings.cycle_id` cascade-delete with their parents.

The tracked file `scripts/investigations/REPORT_v2.md`, in its Gap 3
schema-linkage analysis of a runtime database snapshot, reports
`exit_cycle_id` as "NULL count: 1538/1538 (100.0%)" — i.e. NULL for every
trade in that snapshot. This is consistent with CLAUDE.md's note that live FK
wiring of `exit_cycle_id` is a later concern.

---

## Test Coverage

The `tests/` directory is organized by phase. Counts below are **static
counts of `def test_` occurrences** — they describe the test files present,
not a test run. No captured test-run output (logs, a CI record) is tracked
in the repo, so this document does not state that any test passes.

| Directory | Files | `def test_` functions |
|---|---|---|
| `tests/phase1/` | test_alpaca, test_data, test_scheduler | 36 |
| `tests/phase2/` | test_engine, test_features, test_scorer | 49 |
| `tests/phase3/` | test_loop, test_manager, test_qualification, test_reconciliation, test_risk, test_sizing | 82 |
| `tests/phase4/` | test_ingestion, test_open_positions_lifecycle, test_repository, test_schema, test_writer | 51 |
| `tests/phase5/` | test_apex_reports | 4 |
| **Total** | **18 files** | **~222** |

**What the stabilization track added.** `tests/phase3/test_reconciliation.py`
(7) and `test_manager.py` `clear_positions` coverage (`5544949`);
`tests/phase4/test_open_positions_lifecycle.py` (6, `a7ceb36`);
`test_ingestion.py` (`739ef81`); schema/repository test extensions
(`18012f7`).

**What is covered by scripts rather than pytest.** The entry and exit paths
of the memory-aware loop are exercised by `scripts/verify_entry_path_optionB.py`
and `scripts/verify_exit_path.py`. These are standalone scripts, not part of
the pytest suite, and the repo contains no captured output from them.

**What is not covered.** No test file targets the Part A fill-confirmation
poll loop directly (the Part A commit `e0190db` added no test file). Phase 5
has 4 test functions in one file. The investigation/audit scripts have no
tests.

---

## Open Questions / Known Issues

**Phase 5 status is contradicted within the repo.** As detailed above,
`CLAUDE.md` says Phase 5 is "Not started" and `README.md` says it is "live."
Both files are tracked, and neither is dated. This is unresolved and is the
most significant documentation inconsistency observed.

**`CLAUDE.md` contains stale figures.** This is recorded here, not fixed —
correcting CLAUDE.md's body content is a separate decision and is out of
scope for the change that introduces this document. (The Phase 4 change that
adds this document also adds a two-line pointer to the top of CLAUDE.md; that
pointer does not touch any of the claims below.)

- Its test-count claims ("phase1 22, phase2 49, phase3 62, phase4 36") do not
  match the current files (36 / 49 / 82 / 51) and it omits `tests/phase5/`.
- Its schema claim ("8 tables, 21 indexes, 5 views") does not match the
  current `schema.sql` (10 tables, 21 indexes, 7 views).
- Its "Current Project Structure" listing omits the `core/reporting/`
  directory, which exists on disk.

**No `TODO`/`FIXME`/`XXX` markers.** A grep across `olympus/` `.py` and
`.sql` files (excluding `__pycache__`) returned zero matches. This is the
observed state; it is not a guarantee that no incomplete work exists — the
exit-path commit `0b2d20e` names a follow-up `Database` transaction-helper
refactor in its commit message rather than in an in-code marker.

**Investigation outputs are not tracked.** `scripts/investigations/output/`
is gitignored. The four `.txt` diagnostic reports
(`fill_reconstruction_report.txt`, `phantom_forensics_report.txt`,
`pre_build_safety_report.txt`, `reconciler_behavior_report.txt`) exist on the
working machine but are not in the repository. `REPORT_v2.md` *is* tracked.
A future reader cloning the repo will have the investigation *scripts* and
`REPORT_v2.md`, but not the other generated outputs.

**Pre-existing condition — tracked parquet cache (~77 MB).**
`olympus/data/cache/` contains 3,439 tracked `.parquet` files totalling
roughly 77 MB. The `.gitignore` added in `b1b9237` lists `olympus/data/cache/`,
but these files were committed in the April 29 import before that rule
existed, so the ignore rule does not untrack them — they remain in the
repository's history and working tree. This is noted, not addressed; it is
out of scope for this document.

**Pre-existing condition — tracked `.claude/settings.json`.** The files
`.claude/settings.json` and `.claude/settings.local.json` under
`active/Olympus-Trading/` are tracked in the repository. They contain
Claude Code harness configuration. This is noted, not addressed; whether
harness configuration should be tracked per-project is a decision left to the
project owner.

---

## Pre-Phase-5 Gate (informal)

CLAUDE.md states "The minimum viable Olympus is Phases 1–4" and, in its
Phase 4 description, "Must accumulate several weeks of data before Phase 5 is
meaningful." Neither CLAUDE.md nor the founding plans define a precise,
testable gate for moving past Phase 4.

The only formalization of a "one clean trading week" criterion in the repo is
the **anchored per-weekday gap check in `scripts/phase4_audit.py`**
(`section_5_continuity`). That script anchors on the most recent trade
`entry_time`, builds a 7-calendar-day window ending on that anchor, and
reports a "clean week" PASS only if every *weekday* in the window has at
least one trade or ranking cycle. Its in-code comment describes this as
matching "the intent of 'one clean trading week since the FK repair.'"

This document does not elevate that script check into a formal gate. It is a
read-only audit routine, not a documented release criterion. Any decision
about what actually gates Phase 5 belongs to the project owner.

---

## Reference — Commit Anchors

- `7754da5` (Apr 29) — initial consolidated import; all Phase 1–5 code.
- `135fa91`…`a7ceb36` (May 9) — stabilization batch 1: open_positions track,
  BrokerReconciler, ingestion validation, audit/investigation scripts,
  runtime-layout docs, test backfill.
- `ae51efc`…`7c0b80f` (May 18) — stabilization batch 2: order-ID columns +
  migration, broker healthcheck, Part A fill-confirmation engine, order-ID
  persistence, investigation scripts.
- `HEAD = 7c0b80f`.

See `olympus_changelog.md` for the full chronological record.
