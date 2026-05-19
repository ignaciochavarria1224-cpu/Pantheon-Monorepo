"""
fill_reconstruction_feasibility.py — READ-ONLY feasibility diagnostic for
remediation plan Part B2 (broker-truth table).

PURPOSE
-------
Validate B2's core assumption: that Alpaca's FILL ledger can be cleanly
reconstructed into a broker-truth table keyed by order_id, and that those
orders pair into entry/exit trades. If this does not hold, B1 vs B2 must be
reconsidered before any code is authorized.

STRICT SCOPE — DIAGNOSTIC ONLY
------------------------------
- Read-only: NO writes to data/olympus.db, NO schema changes, NO Alpaca calls
  that modify state, NO new tables created.
- Does NOT modify execution.py, manager.py, or any production module.
- Does NOT perform the backfill. Does NOT begin Parts A/B/C.
- Reads the live olympus.db strictly read-only while Olympus keeps running.

OUTPUT
------
Prints a sectioned plain-text report to stdout AND saves the identical report
to scripts/investigations/output/fill_reconstruction_report.txt.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/investigations/fill_reconstruction_feasibility.py
"""

from __future__ import annotations

import random
import sqlite3
import sys
import traceback
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Bootstrap: make `olympus/` importable regardless of CWD.
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from config.settings import load_settings  # noqa: E402
from core.broker.alpaca import AlpacaClient  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALPACA_ERA_START = "2026-04-17"   # Alpaca paper account creation date (UTC)
HISTORY_FETCH_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
SLOW_FILL_THRESHOLD_S = 5.0       # flag orders whose fills span > this
EXPECTED_FILL_COUNT = 3985        # prior-audit figure to confirm against
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "fill_reconstruction_report.txt"

# Report accumulator — every line printed is also captured for the file.
_REPORT_LINES: list[str] = []


def emit(line: str = "") -> None:
    """Print a line to stdout and capture it for the saved report."""
    print(line)
    _REPORT_LINES.append(line)


def section(title: str) -> None:
    emit("")
    emit("=" * 78)
    emit(f"  {title}")
    emit("=" * 78)


def sub(title: str) -> None:
    emit("")
    emit(f"-- {title} " + "-" * max(0, 73 - len(title)))


def parse_ts(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp (handles trailing Z and +00:00)."""
    if not s:
        return None
    txt = s.strip()
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fnum(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Read-only DB connection
# ---------------------------------------------------------------------------

def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("SELECT 1 FROM trades LIMIT 1").fetchone()
    return conn


# ---------------------------------------------------------------------------
# Section 1 — FILL inventory
# ---------------------------------------------------------------------------

def section_1_inventory(fills: list[dict[str, Any]]) -> dict[str, Any]:
    section("SECTION 1 — FILL INVENTORY")

    total = len(fills)
    emit(f"  Total FILL activities fetched : {total:,}")
    emit(f"  Prior-audit expected figure   : {EXPECTED_FILL_COUNT:,}")
    emit(f"  Match prior figure?           : "
         f"{'YES' if total == EXPECTED_FILL_COUNT else 'NO (delta %+d)' % (total - EXPECTED_FILL_COUNT)}")

    side_counts = Counter((f.get("side") or "?").lower() for f in fills)
    sub("By side")
    for s, n in sorted(side_counts.items()):
        emit(f"  {s:<10} {n:,}")

    type_counts = Counter((f.get("type") or "?").lower() for f in fills)
    sub("By fill type")
    for t, n in sorted(type_counts.items()):
        emit(f"  {t:<16} {n:,}")

    # Distinct order_id + null check
    null_order_ids = sum(1 for f in fills if not f.get("order_id"))
    order_ids = [f.get("order_id") for f in fills if f.get("order_id")]
    distinct_orders = len(set(order_ids))
    sub("Order identity")
    emit(f"  Distinct order_id values      : {distinct_orders:,}")
    emit(f"  FILLs with NULL/empty order_id : {null_order_ids:,}")
    if distinct_orders:
        emit(f"  Fills-per-order ratio         : {total / distinct_orders:.3f}  "
             f"(1.0 = no partial fills)")

    # Distribution of fills-per-order
    per_order = Counter()
    fills_by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in fills:
        oid = f.get("order_id")
        if oid:
            fills_by_order[oid].append(f)
    for oid, fl in fills_by_order.items():
        per_order[len(fl)] += 1

    sub("Distribution of fills-per-order")
    buckets = {"1 fill": 0, "2-4 fills": 0, "5+ fills": 0}
    for nfills, norders in per_order.items():
        if nfills == 1:
            buckets["1 fill"] += norders
        elif nfills <= 4:
            buckets["2-4 fills"] += norders
        else:
            buckets["5+ fills"] += norders
    for label, n in buckets.items():
        pct = (100.0 * n / distinct_orders) if distinct_orders else 0.0
        emit(f"  {label:<12} {n:>6,} orders  ({pct:5.1f}%)")
    emit(f"  exact counts: " +
         ", ".join(f"{k}x:{v}" for k, v in sorted(per_order.items())))

    # Date range + daily fill counts
    ts_list = [parse_ts(f.get("transaction_time")) for f in fills]
    ts_list = [t for t in ts_list if t is not None]
    daily = Counter(t.date().isoformat() for t in ts_list)
    sub("Date coverage")
    if ts_list:
        emit(f"  Earliest fill : {min(ts_list).isoformat()}")
        emit(f"  Latest fill   : {max(ts_list).isoformat()}")
        emit(f"  Distinct days : {len(daily)}")
    sub("Daily fill counts")
    emit(f"  {'Date':<14} {'Fills':>8}")
    emit(f"  {'-' * 24}")
    for day in sorted(daily):
        emit(f"  {day:<14} {daily[day]:>8,}")

    return {
        "total": total,
        "distinct_orders": distinct_orders,
        "null_order_ids": null_order_ids,
        "fills_by_order": fills_by_order,
        "daily": daily,
    }


# ---------------------------------------------------------------------------
# Section 2 — Order-level reconstruction
# ---------------------------------------------------------------------------

def section_2_reconstruct(fills_by_order: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    section("SECTION 2 — ORDER-LEVEL RECONSTRUCTION")

    orders: dict[str, dict[str, Any]] = {}
    slow_orders: list[dict[str, Any]] = []
    side_conflict_orders: list[str] = []
    symbol_conflict_orders: list[str] = []

    for oid, fl in fills_by_order.items():
        sides = {(f.get("side") or "?").lower() for f in fl}
        symbols = {(f.get("symbol") or "?") for f in fl}
        ts = sorted(t for t in (parse_ts(f.get("transaction_time")) for f in fl) if t)

        total_qty = sum(fnum(f.get("qty")) for f in fl)
        notional = sum(fnum(f.get("qty")) * fnum(f.get("price")) for f in fl)
        vwap = (notional / total_qty) if total_qty else 0.0

        if len(sides) > 1:
            side_conflict_orders.append(oid)
        if len(symbols) > 1:
            symbol_conflict_orders.append(oid)

        first_ts = ts[0] if ts else None
        last_ts = ts[-1] if ts else None
        span_s = (last_ts - first_ts).total_seconds() if (first_ts and last_ts) else 0.0

        rec = {
            "order_id": oid,
            "symbol": next(iter(symbols)),
            "side": next(iter(sides)),
            "total_qty": total_qty,
            "vwap_price": vwap,
            "n_fills": len(fl),
            "first_ts": first_ts,
            "last_ts": last_ts,
            "span_s": span_s,
        }
        orders[oid] = rec
        if span_s > SLOW_FILL_THRESHOLD_S:
            slow_orders.append(rec)

    emit(f"  Reconstructed orders          : {len(orders):,}")
    emit(f"  Orders with mixed side        : {len(side_conflict_orders):,}")
    emit(f"  Orders with mixed symbol      : {len(symbol_conflict_orders):,}")
    emit(f"  Orders with fills spanning >{SLOW_FILL_THRESHOLD_S:.0f}s : {len(slow_orders):,}")

    if slow_orders:
        sub(f"Slow-fill orders (span > {SLOW_FILL_THRESHOLD_S:.0f}s)")
        emit(f"  {'order_id':<38} {'sym':<7} {'side':<5} {'qty':>9} {'span_s':>9} {'fills':>6}")
        emit(f"  {'-' * 78}")
        for r in sorted(slow_orders, key=lambda x: -x["span_s"]):
            emit(f"  {r['order_id']:<38} {r['symbol']:<7} {r['side']:<5} "
                 f"{r['total_qty']:>9.0f} {r['span_s']:>9.2f} {r['n_fills']:>6}")

    if side_conflict_orders:
        sub("WARNING — order_ids with conflicting sides (breaks B2 assumption)")
        for oid in side_conflict_orders:
            emit(f"  {oid}")

    return {"orders": orders, "slow_orders": slow_orders,
            "side_conflict": side_conflict_orders}


# ---------------------------------------------------------------------------
# Section 3 — Trade-pairing attempt (FIFO)
# ---------------------------------------------------------------------------

def section_3_pairing(orders: dict[str, dict[str, Any]]) -> dict[str, Any]:
    section("SECTION 3 — TRADE-PAIRING ATTEMPT (FIFO)")
    emit("  Method: per symbol, sort orders by first-fill time; FIFO-match each")
    emit("  order against the oldest open order of the OPPOSITE side. A matched")
    emit("  pair = one entry/exit trade. Leftovers = unpaired orders.")

    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in orders.values():
        by_symbol[o["symbol"]].append(o)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    qty_mismatch_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    unpaired: list[dict[str, Any]] = []

    for symbol, olist in by_symbol.items():
        olist.sort(key=lambda x: (x["first_ts"] or datetime.min.replace(tzinfo=timezone.utc)))
        open_legs: deque[dict[str, Any]] = deque()
        for o in olist:
            if open_legs and open_legs[0]["side"] != o["side"]:
                entry = open_legs.popleft()
                pairs.append((entry, o))
                if abs(entry["total_qty"] - o["total_qty"]) > 1e-6:
                    qty_mismatch_pairs.append((entry, o))
            else:
                open_legs.append(o)
        unpaired.extend(open_legs)

    n_orders = len(orders)
    n_paired_orders = len(pairs) * 2
    pair_pct = (100.0 * n_paired_orders / n_orders) if n_orders else 0.0

    emit("")
    emit(f"  Total reconstructed orders    : {n_orders:,}")
    emit(f"  Clean entry/exit pairs        : {len(pairs):,}  "
         f"({n_paired_orders:,} orders, {pair_pct:.1f}% of orders)")
    emit(f"    of which qty-mismatched     : {len(qty_mismatch_pairs):,}")
    emit(f"  Unpaired orders               : {len(unpaired):,}")

    # Breakdown of unpaired
    unpaired_by_side = Counter(o["side"] for o in unpaired)
    sub("Unpaired breakdown by side")
    for s, n in sorted(unpaired_by_side.items()):
        note = "(open entry never closed / orphan)" if s in ("buy", "sell") else ""
        emit(f"  {s:<8} {n:>5}  {note}")

    if unpaired:
        sub("Full unpaired-order dump")
        emit(f"  {'order_id':<38} {'sym':<7} {'side':<5} {'qty':>9} {'first_fill_ts':<28}")
        emit(f"  {'-' * 92}")
        for o in sorted(unpaired, key=lambda x: (x["symbol"],
                        x["first_ts"] or datetime.min.replace(tzinfo=timezone.utc))):
            emit(f"  {o['order_id']:<38} {o['symbol']:<7} {o['side']:<5} "
                 f"{o['total_qty']:>9.0f} "
                 f"{(o['first_ts'].isoformat() if o['first_ts'] else 'N/A'):<28}")

    if qty_mismatch_pairs:
        sub("Qty-mismatched pairs (entry qty != exit qty)")
        emit(f"  {'sym':<7} {'entry_qty':>10} {'exit_qty':>10} {'entry_oid':<38}")
        emit(f"  {'-' * 70}")
        for entry, ex in qty_mismatch_pairs[:50]:
            emit(f"  {entry['symbol']:<7} {entry['total_qty']:>10.0f} "
                 f"{ex['total_qty']:>10.0f} {entry['order_id']:<38}")
        if len(qty_mismatch_pairs) > 50:
            emit(f"  ... and {len(qty_mismatch_pairs) - 50} more")

    return {"pairs": pairs, "unpaired": unpaired,
            "qty_mismatch": qty_mismatch_pairs, "pair_pct": pair_pct}


# ---------------------------------------------------------------------------
# Section 4 — Cross-check against trades table
# ---------------------------------------------------------------------------

def section_4_crosscheck(
    conn: sqlite3.Connection,
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    section("SECTION 4 — CROSS-CHECK AGAINST trades TABLE")

    # trades table rows in the Alpaca era (entry_time >= 2026-04-17)
    era_rows = conn.execute(
        "SELECT trade_id, symbol, direction, size, entry_time, exit_time, status "
        "FROM trades WHERE substr(entry_time,1,10) >= ?",
        (ALPACA_ERA_START,),
    ).fetchall()
    n_era_trades = len(era_rows)
    n_pairs = len(pairs)

    emit(f"  trades rows, Alpaca era (entry >= {ALPACA_ERA_START}) : {n_era_trades:,}")
    emit(f"  reconstructed entry/exit pairs                  : {n_pairs:,}")
    emit(f"  gap (trades - pairs)                            : {n_era_trades - n_pairs:+,}")

    # Gap concentration by date — trades opened per day vs pairs entered per day
    trades_by_day = Counter(r["entry_time"][:10] for r in era_rows)
    pairs_by_day = Counter(
        (e["first_ts"].date().isoformat() if e["first_ts"] else "N/A")
        for e, _ in pairs
    )
    all_days = sorted(set(trades_by_day) | set(pairs_by_day))
    sub("Per-day: trades opened vs pairs entered")
    emit(f"  {'Date':<14} {'trades':>8} {'pairs':>8} {'gap':>8}")
    emit(f"  {'-' * 42}")
    for day in all_days:
        t = trades_by_day.get(day, 0)
        p = pairs_by_day.get(day, 0)
        flag = "  <-- gap" if abs(t - p) >= 10 else ""
        emit(f"  {day:<14} {t:>8,} {p:>8,} {t - p:>+8,}{flag}")

    # April 20 ranking-cycle-failure episode itemization
    sub("2026-04-20 ranking-cycle-failure episode")
    apr20_trades = conn.execute(
        "SELECT COUNT(*) AS n FROM trades WHERE substr(entry_time,1,10) = '2026-04-20'"
    ).fetchone()["n"]
    apr20_trades_exit = conn.execute(
        "SELECT COUNT(*) AS n FROM trades WHERE substr(exit_time,1,10) = '2026-04-20'"
    ).fetchone()["n"]
    apr20_pairs = pairs_by_day.get("2026-04-20", 0)
    emit(f"  trades with entry_time on 2026-04-20 : {apr20_trades}")
    emit(f"  trades with exit_time  on 2026-04-20 : {apr20_trades_exit}")
    emit(f"  reconstructed pairs entered 2026-04-20: {apr20_pairs}")
    emit(f"  fill-side mismatch vs trades          : "
         f"{apr20_trades - apr20_pairs:+d} (trades minus pairs)")
    emit("  Interpretation: a large positive gap here = trades recorded locally")
    emit("  that have no corresponding filled Alpaca order (phantom trades).")

    return {"n_era_trades": n_era_trades, "n_pairs": n_pairs,
            "trades_by_day": trades_by_day, "pairs_by_day": pairs_by_day}


# ---------------------------------------------------------------------------
# Section 5 — Pre-Alpaca cohort
# ---------------------------------------------------------------------------

def section_5_pre_alpaca(
    conn: sqlite3.Connection,
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    section("SECTION 5 — PRE-ALPACA COHORT")

    pre_rows = conn.execute(
        "SELECT COUNT(*) AS n, MIN(entry_time) AS mn, MAX(entry_time) AS mx "
        "FROM trades WHERE substr(entry_time,1,10) < ?",
        (ALPACA_ERA_START,),
    ).fetchone()
    n_pre = pre_rows["n"]

    emit(f"  trades rows with entry_time < {ALPACA_ERA_START} : {n_pre:,}")
    if n_pre:
        emit(f"  pre-Alpaca entry_time range : {pre_rows['mn']}  ->  {pre_rows['mx']}")

    # Confirm no Alpaca fills exist before the account-creation date.
    fill_days = sorted({
        t.date().isoformat()
        for t in (parse_ts(f.get("transaction_time")) for f in fills)
        if t is not None
    })
    earliest_fill_day = fill_days[0] if fill_days else None
    pre_era_fills = [d for d in fill_days if d < ALPACA_ERA_START]

    emit(f"  earliest Alpaca fill day    : {earliest_fill_day}")
    emit(f"  Alpaca fills before {ALPACA_ERA_START} : {len(pre_era_fills)} day(s) "
         f"{'-> CONFIRMED NONE' if not pre_era_fills else '-> UNEXPECTED: ' + str(pre_era_fills)}")
    emit("")
    emit(f"  => {n_pre:,} pre-Alpaca trades are unmatchable by definition and")
    emit(f"     would be QUARANTINED under B2 (no broker truth exists for them).")

    return {"n_pre": n_pre, "pre_era_fills": pre_era_fills}


# ---------------------------------------------------------------------------
# Section 6 — Timing-field spot check
# ---------------------------------------------------------------------------

def section_6_timing(
    conn: sqlite3.Connection,
    orders: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    section("SECTION 6 — TIMING-FIELD SPOT CHECK (20 random Alpaca-era trades)")
    emit("  Compares trades.entry_time against the first-fill timestamp of the")
    emit("  best-matching reconstructed order (symbol + entry-side + nearest qty")
    emit("  + nearest time). A systematic positive delta means entry_time is the")
    emit("  ORDER-SUBMIT time, not the FILL time — a secondary bug, same class.")

    era_rows = conn.execute(
        "SELECT trade_id, symbol, direction, size, entry_time "
        "FROM trades WHERE substr(entry_time,1,10) >= ?",
        (ALPACA_ERA_START,),
    ).fetchall()

    if not era_rows:
        emit("  (no Alpaca-era trades to sample)")
        return {"deltas": []}

    rng = random.Random(42)  # deterministic sample for a reproducible report
    sample = rng.sample(era_rows, min(20, len(era_rows)))

    # Index entry-side orders by symbol for matching.
    orders_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in orders.values():
        orders_by_symbol[o["symbol"]].append(o)

    sub("Per-trade comparison")
    emit(f"  {'symbol':<7} {'dir':<6} {'trades.entry_time':<28} "
         f"{'order first_fill_ts':<28} {'delta_s':>10}")
    emit(f"  {'-' * 88}")

    deltas: list[float] = []
    unmatched = 0
    for r in sample:
        sym = r["symbol"]
        direction = (r["direction"] or "").lower()
        entry_side = "buy" if direction == "long" else "sell"
        et = parse_ts(r["entry_time"])
        candidates = [o for o in orders_by_symbol.get(sym, [])
                      if o["side"] == entry_side and o["first_ts"] is not None]
        if not candidates or et is None:
            unmatched += 1
            emit(f"  {sym:<7} {direction:<6} {r['entry_time']:<28} "
                 f"{'(no matching order)':<28} {'N/A':>10}")
            continue
        best = min(candidates,
                   key=lambda o: abs((o["first_ts"] - et).total_seconds()))
        delta = (best["first_ts"] - et).total_seconds()
        deltas.append(delta)
        emit(f"  {sym:<7} {direction:<6} {r['entry_time']:<28} "
             f"{best['first_ts'].isoformat():<28} {delta:>+10.2f}")

    sub("Delta distribution (order_fill_ts - trades.entry_time, seconds)")
    if deltas:
        srt = sorted(deltas)
        n = len(srt)
        emit(f"  samples matched : {n}   unmatched : {unmatched}")
        emit(f"  min    : {srt[0]:+.2f}")
        emit(f"  median : {srt[n // 2]:+.2f}")
        emit(f"  max    : {srt[-1]:+.2f}")
        emit(f"  mean   : {sum(srt) / n:+.2f}")
        within_2s = sum(1 for d in srt if abs(d) <= 2.0)
        emit(f"  within +/-2s : {within_2s}/{n}")
        if abs(sum(srt) / n) > 5.0:
            emit("  >> SYSTEMATIC OFFSET DETECTED — entry_time likely submit-time,")
            emit("     not fill-time. Flag as secondary bug for the Part A scope.")
        else:
            emit("  >> No large systematic offset — entry_time tracks fill-time")
            emit("     closely enough; not a blocking concern.")
    else:
        emit("  (no deltas computed — all sampled trades unmatched)")

    return {"deltas": deltas, "unmatched": unmatched}


# ---------------------------------------------------------------------------
# Section 7 — Summary verdict
# ---------------------------------------------------------------------------

def section_7_verdict(
    inv: dict[str, Any],
    recon: dict[str, Any],
    pairing: dict[str, Any],
    crosscheck: dict[str, Any],
    pre: dict[str, Any],
    timing: dict[str, Any],
) -> None:
    section("SECTION 7 — SUMMARY VERDICT  (go / no-go for B2)")

    # Check 1 — order_id present on every FILL
    oid_ok = inv["null_order_ids"] == 0
    emit(f"  [1] order_id present & non-null on every FILL : "
         f"{'PASS' if oid_ok else 'FAIL'}  "
         f"({inv['null_order_ids']} null of {inv['total']})")

    # Check 1b — no order with conflicting sides
    side_ok = len(recon["side_conflict"]) == 0
    emit(f"  [1b] no order_id spans conflicting sides       : "
         f"{'PASS' if side_ok else 'FAIL'}  "
         f"({len(recon['side_conflict'])} conflicted)")

    # Check 2 — clean pairing rate
    pct = pairing["pair_pct"]
    if pct > 95.0:
        tier = "B2 TRIVIAL (>95%)"
    elif pct >= 80.0:
        tier = "B2 + MANUAL REVIEW QUEUE (80-95%)"
    else:
        tier = "RECONSIDER APPROACH (<80%)"
    emit(f"  [2] orders pairing cleanly into trades        : "
         f"{pct:.1f}%  ->  {tier}")

    # Check 3 — structural vs scattered gaps
    tbd = crosscheck["trades_by_day"]
    pbd = crosscheck["pairs_by_day"]
    big_gap_days = [d for d in sorted(set(tbd) | set(pbd))
                    if abs(tbd.get(d, 0) - pbd.get(d, 0)) >= 10]
    structural = len(big_gap_days) > 0
    emit(f"  [3] structural gaps (whole days >=10 off)     : "
         f"{'YES — ' + ', '.join(big_gap_days) if structural else 'NO — scattered noise only'}")

    # Check 4 — timing offset
    deltas = timing.get("deltas", [])
    timing_offset = bool(deltas) and abs(sum(deltas) / len(deltas)) > 5.0
    emit(f"  [4] entry_time timing offset (secondary bug)  : "
         f"{'DETECTED' if timing_offset else 'not significant'}")

    emit(f"  [5] pre-Alpaca cohort to quarantine           : "
         f"{pre['n_pre']:,} trades")

    # Overall recommendation
    sub("RECOMMENDATION")
    if not oid_ok or not side_ok:
        emit("  NO-GO: order_id integrity failed. B2's keying assumption is")
        emit("  broken. ESCALATE — B1 vs B2 must be reconsidered.")
    elif pct > 95.0 and not structural:
        emit("  GO: Proceed with B2 as planned. Alpaca's fill ledger reconstructs")
        emit("  cleanly into an order_id-keyed broker-truth table. Pairing is")
        emit("  near-total and gaps are scattered noise, not structural.")
    elif pct >= 80.0:
        emit("  GO WITH MODIFICATIONS: Proceed with B2, but add a manual-review")
        emit("  queue for the unpaired/mismatched minority. Itemize the structural")
        emit("  gap days (esp. 2026-04-20) as a known quarantine set.")
    else:
        emit("  ESCALATE: Clean-pairing rate is below 80%. B2 as specified is not")
        emit("  safe; return to the user before committing to an approach.")

    if timing_offset:
        emit("")
        emit("  NOTE: entry_time timing offset detected — fold this into the")
        emit("  Part A scope as a secondary fix (same failure class as the price")
        emit("  bug: a recorded field that reflects intent, not broker reality).")

    emit("")
    emit("  Scope reminder: this run was DIAGNOSTIC ONLY. No data, schema, or")
    emit("  production module was modified. Parts A/B/C remain unauthorized.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    section("OLYMPUS — FILL RECONSTRUCTION FEASIBILITY DIAGNOSTIC (B2)")
    now = datetime.now(tz=timezone.utc)
    emit(f"  generated (UTC) : {now.isoformat()}")
    emit("  mode            : READ-ONLY DIAGNOSTIC — no writes, no schema changes")

    settings = load_settings()
    db_path = settings.DB_PATH
    emit(f"  database        : {db_path}")
    emit(f"  alpaca paper    : {settings.ALPACA_PAPER}")

    # --- Fetch Alpaca activities (full history) ---
    try:
        client = AlpacaClient()
        rows = client.get_activities(after=HISTORY_FETCH_FROM)
    except Exception as exc:
        emit(f"\n[FATAL] Alpaca activities fetch failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    fills = [r for r in rows if (r.get("activity_type") or "").upper() == "FILL"]

    # --- Open DB read-only ---
    try:
        conn = open_db_readonly(db_path)
    except Exception as exc:
        emit(f"\n[FATAL] DB open failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    try:
        inv = section_1_inventory(fills)
        recon = section_2_reconstruct(inv["fills_by_order"])
        pairing = section_3_pairing(recon["orders"])
        crosscheck = section_4_crosscheck(conn, pairing["pairs"])
        pre = section_5_pre_alpaca(conn, fills)
        timing = section_6_timing(conn, recon["orders"])
        section_7_verdict(inv, recon, pairing, crosscheck, pre, timing)
    finally:
        conn.close()

    _flush_report()
    return 0


def _flush_report() -> None:
    """Write the captured report to the output file."""
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text("\n".join(_REPORT_LINES) + "\n", encoding="utf-8")
        print(f"\n[report saved] {OUTPUT_PATH}")
    except Exception as exc:
        print(f"\n[WARN] could not save report file: {exc}")


if __name__ == "__main__":
    sys.exit(main())
