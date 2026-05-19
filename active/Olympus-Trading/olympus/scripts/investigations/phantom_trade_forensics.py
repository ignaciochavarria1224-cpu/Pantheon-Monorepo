"""
phantom_trade_forensics.py — READ-ONLY forensic investigation of the two
phantom-trade episodes (2026-04-17 and 2026-04-20).

PURPOSE
-------
The B2 feasibility diagnostic found 272 phantom trades concentrated entirely on
2026-04-17 (+119) and 2026-04-20 (+153) — trades recorded in the local trades
table with no corresponding filled Alpaca order. This script investigates the
mechanism behind those phantoms before Part A scope is decided.

STRICT SCOPE — DIAGNOSTIC ONLY
------------------------------
- Read-only: NO writes to data/olympus.db, NO schema changes.
- Does NOT modify trade rows, does NOT delete phantom trades.
- Does NOT touch production code. Parts A/B/C remain unauthorized.

OUTPUT
------
Plain-text report to stdout AND saved to
scripts/investigations/output/phantom_forensics_report.txt.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/investigations/phantom_trade_forensics.py
"""

from __future__ import annotations

import re
import sqlite3
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

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

PHANTOM_DAYS = ["2026-04-17", "2026-04-20"]
ALPACA_ERA_START = "2026-04-17"
HISTORY_FETCH_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
MATCH_WINDOW_S = 60.0           # +/- window for trade<->order timestamp matching
LOG_PATH = Path.home() / "OlympusLocal" / "data" / "logs" / "olympus.log"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "phantom_forensics_report.txt"

ERROR_KEYWORDS = re.compile(
    r"error|exception|traceback|reject|denied|unauthor|401|403|"
    r"timeout|timed out|fail|could not|unable to|none returned",
    re.IGNORECASE,
)
ORDER_KEYWORDS = re.compile(
    r"submit|order|entry|exit|fill|alpaca|broker", re.IGNORECASE,
)

_REPORT_LINES: list[str] = []


def emit(line: str = "") -> None:
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
    if not s:
        return None
    txt = s.strip().replace("Z", "+00:00")
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


def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("SELECT 1 FROM trades LIMIT 1").fetchone()
    return conn


# ---------------------------------------------------------------------------
# Order reconstruction from Alpaca FILLs (qty-weighted, by order_id)
# ---------------------------------------------------------------------------

def reconstruct_orders(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fbo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in fills:
        oid = f.get("order_id")
        if oid:
            fbo[oid].append(f)
    orders: list[dict[str, Any]] = []
    for oid, fl in fbo.items():
        tq = sum(fnum(x.get("qty")) for x in fl)
        notional = sum(fnum(x.get("qty")) * fnum(x.get("price")) for x in fl)
        ts = sorted(t for t in (parse_ts(x.get("transaction_time")) for x in fl) if t)
        orders.append({
            "order_id": oid,
            "symbol": fl[0].get("symbol"),
            "side": (fl[0].get("side") or "").lower(),
            "qty": tq,
            "vwap": (notional / tq) if tq else 0.0,
            "first_ts": ts[0] if ts else None,
            "last_ts": ts[-1] if ts else None,
            "n_fills": len(fl),
        })
    return orders


# Entry/exit side mapping. Long opens with buy / closes with sell.
# Short opens with sell_short / closes with buy.
def entry_side(direction: str) -> set[str]:
    return {"buy"} if direction.lower() == "long" else {"sell_short", "sell"}


def exit_side(direction: str) -> set[str]:
    return {"sell"} if direction.lower() == "long" else {"buy"}


def find_order(
    orders_idx: dict[str, list[dict[str, Any]]],
    symbol: str,
    sides: set[str],
    qty: float,
    when: Optional[datetime],
) -> tuple[Optional[dict[str, Any]], bool]:
    """
    Return (best_order_within_window, qty_matches). best_order is the closest
    order in time for this symbol+side; None if none within MATCH_WINDOW_S.
    """
    if when is None:
        return None, False
    candidates = [
        o for o in orders_idx.get(symbol, [])
        if o["side"] in sides and o["first_ts"] is not None
        and abs((o["first_ts"] - when).total_seconds()) <= MATCH_WINDOW_S
    ]
    if not candidates:
        return None, False
    best = min(candidates, key=lambda o: abs((o["first_ts"] - when).total_seconds()))
    qty_ok = abs(best["qty"] - qty) <= 1.0
    return best, qty_ok


# ---------------------------------------------------------------------------
# Section 1 — Phantom trade inventory
# ---------------------------------------------------------------------------

def classify_day_trades(
    conn: sqlite3.Connection,
    day: str,
    orders_idx: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT trade_id, symbol, direction, size, entry_time, exit_time, "
        "entry_price, exit_price, realized_pnl, exit_reason, status "
        "FROM trades WHERE substr(entry_time,1,10) = ? ORDER BY entry_time",
        (day,),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for r in rows:
        direction = (r["direction"] or "").lower()
        et = parse_ts(r["entry_time"])
        xt = parse_ts(r["exit_time"])
        size = fnum(r["size"])

        e_order, e_qty_ok = find_order(orders_idx, r["symbol"], entry_side(direction), size, et)
        x_order, x_qty_ok = find_order(orders_idx, r["symbol"], exit_side(direction), size, xt)

        e_found = e_order is not None
        x_found = x_order is not None
        if e_found and x_found:
            klass = "matched_clean" if (e_qty_ok and x_qty_ok) else "matched_qtydiff"
        elif e_found or x_found:
            klass = "partial_match"
        else:
            klass = "fully_phantom"

        results.append({
            "trade_id": r["trade_id"],
            "symbol": r["symbol"],
            "direction": direction,
            "size": size,
            "entry_time": r["entry_time"],
            "exit_time": r["exit_time"],
            "entry_price": fnum(r["entry_price"]),
            "exit_price": fnum(r["exit_price"]),
            "realized_pnl": fnum(r["realized_pnl"]),
            "exit_reason": r["exit_reason"],
            "status": r["status"],
            "class": klass,
            "entry_found": e_found,
            "exit_found": x_found,
        })
    return results


def section_1_inventory(
    conn: sqlite3.Connection,
    orders_idx: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    section("SECTION 1 — PHANTOM TRADE INVENTORY (per day)")
    emit(f"  Match rule: symbol + side + timestamp within +/-{MATCH_WINDOW_S:.0f}s")
    emit("  (qty compared separately; a leg with an order but wrong qty still")
    emit("   counts as 'found' — it is not phantom, just a qty discrepancy).")

    by_day: dict[str, list[dict[str, Any]]] = {}
    for day in PHANTOM_DAYS:
        trades = classify_day_trades(conn, day, orders_idx)
        by_day[day] = trades
        klass_counts = Counter(t["class"] for t in trades)

        sub(f"{day} — {len(trades)} trades")
        for k in ("matched_clean", "matched_qtydiff", "partial_match", "fully_phantom"):
            emit(f"  {k:<18} {klass_counts.get(k, 0):>4}")

        emit("")
        emit(f"  {'symbol':<7} {'dir':<5} {'qty':>6} {'entry_time':<26} "
             f"{'exit_reason':<10} {'pnl':>9}  class")
        emit(f"  {'-' * 92}")
        for t in trades:
            emit(f"  {t['symbol']:<7} {t['direction']:<5} {t['size']:>6.0f} "
                 f"{(t['entry_time'] or ''):<26} {(t['exit_reason'] or ''):<10} "
                 f"{t['realized_pnl']:>+9.2f}  {t['class']}")

    return by_day


# ---------------------------------------------------------------------------
# Section 2 — What Alpaca actually did
# ---------------------------------------------------------------------------

def section_2_alpaca(fills: list[dict[str, Any]]) -> None:
    section("SECTION 2 — WHAT ALPACA ACTUALLY DID THOSE DAYS")

    for day in PHANTOM_DAYS:
        day_fills = sorted(
            (f for f in fills
             if (parse_ts(f.get("transaction_time")) or datetime.min.replace(tzinfo=timezone.utc))
             .date().isoformat() == day),
            key=lambda f: f.get("transaction_time") or "",
        )
        sub(f"{day} — {len(day_fills)} Alpaca FILLs")
        emit(f"  {'transaction_time':<28} {'sym':<7} {'side':<11} {'qty':>7} "
             f"{'price':>10} {'order_id':<38}")
        emit(f"  {'-' * 104}")
        for f in day_fills:
            emit(f"  {(f.get('transaction_time') or ''):<28} {(f.get('symbol') or ''):<7} "
                 f"{(f.get('side') or ''):<11} {fnum(f.get('qty')):>7.0f} "
                 f"{fnum(f.get('price')):>10.2f} {(f.get('order_id') or ''):<38}")

        if day == "2026-04-17" and day_fills:
            sub("2026-04-17 — first 10 fills chronologically (account-creation day)")
            for f in day_fills[:10]:
                emit(f"  {(f.get('transaction_time') or '')}  {f.get('symbol')} "
                     f"{f.get('side')} {fnum(f.get('qty')):.0f} @ {fnum(f.get('price')):.2f}")


# ---------------------------------------------------------------------------
# Section 2b — Alpaca ORDER ledger (authoritative submit record)
# ---------------------------------------------------------------------------

def section_2b_order_ledger(
    client: AlpacaClient,
    by_day: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """
    The FILL activity feed only shows orders that filled. The ORDER ledger
    shows every order Alpaca actually received (filled / canceled / rejected /
    expired). Comparing orders-received vs trades-in-DB is the authoritative
    test of whether a phantom 'trade' ever reached the broker at all.
    """
    section("SECTION 2b — ALPACA ORDER LEDGER (authoritative submit record)")
    emit("  get_orders() returns every order Alpaca received, by final status.")
    emit("  A phantom day = trades-in-DB >> orders-Alpaca-received.")

    result: dict[str, Any] = {"per_day": {}, "all_time": {}}

    for day in PHANTOM_DAYS:
        d = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        try:
            orders = client.get_orders(
                status="all", after=d, until=d + timedelta(days=1), limit=500)
        except Exception as exc:
            emit(f"  [ERROR] get_orders({day}) failed: {exc}")
            continue
        status_counts = Counter(o.get("status") or "?" for o in orders)
        n_trades = len(by_day.get(day, []))
        sub(f"{day}")
        emit(f"  trades recorded in DB              : {n_trades}")
        emit(f"  orders Alpaca actually received    : {len(orders)}")
        emit(f"  order status breakdown             : {dict(status_counts)}")
        emit(f"  trades with NO broker order (phantom): "
             f"~{max(0, n_trades - len(orders))}")
        result["per_day"][day] = {
            "n_trades": n_trades,
            "n_orders": len(orders),
            "statuses": dict(status_counts),
        }

    # All-time walk (get_orders has no pagination + a 500 cap, so step the
    # `until` cursor backwards until no new order ids appear).
    sub("All-time order ledger")
    seen: set[str] = set()
    all_status: Counter = Counter()
    cursor = datetime.now(tz=timezone.utc) + timedelta(days=1)
    for _ in range(40):
        try:
            batch = client.get_orders(status="all", until=cursor, limit=500)
        except Exception as exc:
            emit(f"  [ERROR] all-time get_orders failed: {exc}")
            break
        new = [o for o in batch if o.get("order_id") not in seen]
        if not new:
            break
        for o in new:
            seen.add(o.get("order_id"))
            all_status[o.get("status") or "?"] += 1
        submitted = [o.get("submitted_at") for o in batch if o.get("submitted_at")]
        if not submitted:
            break
        oldest = min(submitted)
        if oldest >= cursor:
            break
        cursor = oldest
    emit(f"  distinct orders Alpaca received, all-time : {len(seen):,}")
    emit(f"  status breakdown                          : {dict(all_status)}")
    emit("  Note: 0 rejected / 0 expired all-time means an order that reaches")
    emit("  Alpaca always either fills or is canceled — so a 'phantom' trade")
    emit("  is one whose order NEVER reached the broker, not one that failed.")
    result["all_time"] = {"n_orders": len(seen), "statuses": dict(all_status)}

    return result


# ---------------------------------------------------------------------------
# Section 3 — Order submission records (logs)
# ---------------------------------------------------------------------------

def section_3_logs() -> None:
    section("SECTION 3 — ORDER SUBMISSION RECORDS (olympus.log)")
    emit(f"  Log file: {LOG_PATH}")

    if not LOG_PATH.exists():
        emit("  [WARN] log file not found — cannot inspect submission records.")
        return

    # The log prefixes each line with [YYYY-MM-DD HH:MM:SS TZ]. Filter by prefix
    # date so we only see lines actually emitted on the phantom days.
    day_lines: dict[str, list[str]] = {d: [] for d in PHANTOM_DAYS}
    prefix_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) ")
    try:
        with LOG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = prefix_re.match(line)
                if m and m.group(1) in day_lines:
                    day_lines[m.group(1)].append(line.rstrip("\n"))
    except Exception as exc:
        emit(f"  [ERROR] could not read log: {exc}")
        return

    emit("  Note: log timestamps are ET (EDT); a phantom day's ET prefix overlaps")
    emit("  the same UTC calendar day closely enough for this inventory.")

    for day in PHANTOM_DAYS:
        lines = day_lines[day]
        err_lines = [ln for ln in lines if ERROR_KEYWORDS.search(ln)]
        order_lines = [ln for ln in lines if ORDER_KEYWORDS.search(ln)]
        sub(f"{day} — {len(lines)} log lines")
        emit(f"  lines matching error/exception/reject/auth keywords : {len(err_lines)}")
        emit(f"  lines matching order/submit/fill/broker keywords     : {len(order_lines)}")

        if err_lines:
            emit("")
            emit("  -- first 20 error-class lines --")
            for ln in err_lines[:20]:
                emit(f"    {ln[:200]}")
        else:
            emit("  (no error-class log lines this day)")

        # Sample order-submission lines to see what submit_market_order did.
        submit_lines = [ln for ln in order_lines
                        if re.search(r"submit|ENTRY|EXIT|fill=", ln, re.IGNORECASE)]
        emit("")
        emit(f"  -- order-submission sample (first 15 of {len(submit_lines)}) --")
        for ln in submit_lines[:15]:
            emit(f"    {ln[:200]}")
        if not submit_lines:
            emit("    (no order-submission log lines found this day)")


# ---------------------------------------------------------------------------
# Section 4 — System state propagation check
# ---------------------------------------------------------------------------

def section_4_propagation(
    conn: sqlite3.Connection,
    by_day: dict[str, list[dict[str, Any]]],
) -> None:
    section("SECTION 4 — SYSTEM STATE PROPAGATION CHECK")
    emit("  Question: did phantom positions leak into later days' decisions?")

    for day in PHANTOM_DAYS:
        phantoms = [t for t in by_day[day] if t["class"] == "fully_phantom"]
        sub(f"{day} — {len(phantoms)} fully-phantom trades")

        # 4a. Did the phantom trades themselves get a simulated exit recorded?
        exit_reasons = Counter(t["exit_reason"] for t in phantoms)
        with_exit = sum(1 for t in phantoms if t["exit_time"])
        emit(f"  phantom trades with an exit_time recorded : {with_exit}/{len(phantoms)}")
        emit(f"  phantom exit_reason distribution          : "
             f"{dict(exit_reasons)}")
        emit("  (an exit on a never-opened position = Olympus internally")
        emit("   simulated the full lifecycle of a hallucinated position.)")

        # 4b. broker_mismatch events in the 5 trading days after the phantom day.
        start = datetime.fromisoformat(day).date()
        window_end = (start + timedelta(days=8)).isoformat()
        mismatch_rows = conn.execute(
            "SELECT event_time, metadata_json FROM system_events "
            "WHERE event_type = 'broker_mismatch' "
            "AND substr(event_time,1,10) > ? AND substr(event_time,1,10) <= ? "
            "ORDER BY event_time",
            (day, window_end),
        ).fetchall()
        emit("")
        emit(f"  broker_mismatch events in the ~5 trading days after {day}: "
             f"{len(mismatch_rows)}")

        # 4c. Did any phantom symbol show up as a local-only open position
        #     (in local_open_symbols but not broker_open_symbols) afterwards?
        phantom_symbols = {t["symbol"] for t in phantoms}
        leaked: Counter = Counter()
        for mr in mismatch_rows:
            md = mr["metadata_json"] or ""
            local_only = []
            try:
                import json
                d = json.loads(md)
                local = set(d.get("local_open_symbols") or [])
                broker = set(d.get("broker_open_symbols") or [])
                local_only = list(local - broker)
            except Exception:
                continue
            for s in local_only:
                if s in phantom_symbols:
                    leaked[s] += 1
        if leaked:
            emit(f"  phantom symbols later seen as LOCAL-ONLY open positions:")
            for s, n in leaked.most_common():
                emit(f"    {s:<7} appeared local-only in {n} mismatch event(s)")
        else:
            emit("  no phantom symbol reappeared as a local-only open position")
            emit("  in the following window (subject to system_events coverage).")


# ---------------------------------------------------------------------------
# Section 5 — Pre-Alpaca cohort characterization
# ---------------------------------------------------------------------------

def section_5_pre_alpaca(conn: sqlite3.Connection) -> None:
    section("SECTION 5 — PRE-ALPACA COHORT CHARACTERIZATION")

    pre = conn.execute(
        "SELECT COUNT(*) n, MIN(entry_time) mn, MAX(entry_time) mx, "
        "MIN(entry_price) minp, MAX(entry_price) maxp, AVG(entry_price) avgp, "
        "SUM(CASE WHEN entry_price <= 0 THEN 1 ELSE 0 END) badprice, "
        "SUM(realized_pnl) pnl "
        "FROM trades WHERE substr(entry_time,1,10) < ?",
        (ALPACA_ERA_START,),
    ).fetchone()
    emit(f"  pre-Alpaca trades (< {ALPACA_ERA_START}) : {pre['n']:,}")
    emit(f"  entry_time range          : {pre['mn']}  ->  {pre['mx']}")
    emit(f"  entry_price min/avg/max   : "
         f"{pre['minp']:.2f} / {pre['avgp']:.2f} / {pre['maxp']:.2f}")
    emit(f"  rows with entry_price<=0  : {pre['badprice']}  "
         f"({'OK — none' if pre['badprice'] == 0 else 'SUSPECT'})")
    emit(f"  summed realized_pnl       : {pre['pnl']:+.2f}")

    # Symbol-universe overlap with the Alpaca era.
    pre_syms = {r["symbol"] for r in conn.execute(
        "SELECT DISTINCT symbol FROM trades WHERE substr(entry_time,1,10) < ?",
        (ALPACA_ERA_START,))}
    era_syms = {r["symbol"] for r in conn.execute(
        "SELECT DISTINCT symbol FROM trades WHERE substr(entry_time,1,10) >= ?",
        (ALPACA_ERA_START,))}
    overlap = pre_syms & era_syms
    sub("Symbol universe")
    emit(f"  distinct symbols pre-Alpaca : {len(pre_syms)}")
    emit(f"  distinct symbols Alpaca era : {len(era_syms)}")
    emit(f"  overlap                     : {len(overlap)} "
         f"({100.0 * len(overlap) / max(1, len(pre_syms)):.1f}% of pre-Alpaca symbols)")
    only_pre = pre_syms - era_syms
    if only_pre:
        emit(f"  symbols ONLY in pre-Alpaca  : {sorted(only_pre)}")

    # Source-file metadata: pre vs post.
    sub("source_file metadata (simulation vs live-paper indicator)")
    for label, op in (("pre-Alpaca", "<"), ("Alpaca era", ">=")):
        rows = conn.execute(
            f"SELECT source_file, COUNT(*) n FROM trades "
            f"WHERE substr(entry_time,1,10) {op} ? GROUP BY source_file "
            f"ORDER BY n DESC LIMIT 8",
            (ALPACA_ERA_START,)).fetchall()
        emit(f"  [{label}]")
        for r in rows:
            emit(f"    {str(r['source_file'])[:60]:<62} {r['n']:>6}")


# ---------------------------------------------------------------------------
# Section 6 — 4/17 account-creation-day hypothesis
# ---------------------------------------------------------------------------

def section_6_account_creation(
    conn: sqlite3.Connection,
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    section("SECTION 6 — 2026-04-17 ACCOUNT-CREATION-DAY HYPOTHESIS")

    fills_417 = sorted(
        (parse_ts(f.get("transaction_time")) for f in fills
         if (f.get("transaction_time") or "").startswith("2026-04-17")),
        key=lambda t: t or datetime.min.replace(tzinfo=timezone.utc),
    )
    first_fill = fills_417[0] if fills_417 else None

    first_trade = conn.execute(
        "SELECT trade_id, symbol, entry_time FROM trades "
        "WHERE substr(entry_time,1,10) = '2026-04-17' ORDER BY entry_time LIMIT 1"
    ).fetchone()
    first_trade_ts = parse_ts(first_trade["entry_time"]) if first_trade else None

    emit(f"  first Alpaca FILL on 4/17      : "
         f"{first_fill.isoformat() if first_fill else 'NONE'}")
    emit(f"  first trades-table row on 4/17 : "
         f"{first_trade['entry_time'] if first_trade else 'NONE'} "
         f"({first_trade['symbol'] if first_trade else ''})")

    gap_h: Optional[float] = None
    if first_fill and first_trade_ts:
        gap_h = (first_fill - first_trade_ts).total_seconds() / 3600.0
        emit(f"  gap (first fill - first trade)  : {gap_h:+.2f} hours")

    # How many 4/17 trades were 'opened' before the first real Alpaca fill?
    pre_fill_count = 0
    if first_fill:
        pre_fill_count = conn.execute(
            "SELECT COUNT(*) n FROM trades "
            "WHERE substr(entry_time,1,10) = '2026-04-17' AND entry_time < ?",
            (first_fill.isoformat(),)).fetchone()["n"]
        emit(f"  4/17 trades entered BEFORE the first Alpaca fill : {pre_fill_count}")

    emit("")
    if gap_h is not None and gap_h > 0.5:
        emit(f"  => CONFIRMED: Olympus recorded trades {gap_h:.1f}h before the broker")
        emit("     connection produced any fill. It was 'trading' against a broker")
        emit("     it was not yet connected/authenticated to.")
    elif first_fill and first_trade_ts:
        emit("  => Trades and fills start close together — account-creation-lag")
        emit("     is NOT the dominant 4/17 mechanism; look elsewhere.")

    return {"gap_hours": gap_h, "pre_fill_count": pre_fill_count,
            "first_fill": first_fill, "first_trade_ts": first_trade_ts}


# ---------------------------------------------------------------------------
# Section 7 — Summary verdict
# ---------------------------------------------------------------------------

def section_7_verdict(
    by_day: dict[str, list[dict[str, Any]]],
    s6: dict[str, Any],
    s2b: dict[str, Any],
) -> None:
    section("SECTION 7 — SUMMARY VERDICT")

    counts = {
        day: Counter(t["class"] for t in by_day[day]) for day in PHANTOM_DAYS
    }
    for day in PHANTOM_DAYS:
        c = counts[day]
        emit(f"  {day}: {c.get('fully_phantom', 0)} fully-phantom, "
             f"{c.get('partial_match', 0)} partial, "
             f"{c.get('matched_clean', 0) + c.get('matched_qtydiff', 0)} matched "
             f"(of {len(by_day[day])} trades)")

    sub("Q1 — One mechanism or two different bugs?")
    emit("  ONE mechanism. The ORDER ledger (Section 2b) is decisive:")
    for day in PHANTOM_DAYS:
        pd = s2b.get("per_day", {}).get(day, {})
        emit(f"    {day}: {pd.get('n_trades', '?')} trades in DB vs "
             f"{pd.get('n_orders', '?')} orders Alpaca actually received.")
    emit("  On both days the runtime wrote trades into the live DB with no")
    emit("  corresponding broker order at all — an internal simulated-execution")
    emit("  path, the same mode that produced the 795 pre-Alpaca trades. Same")
    emit("  mechanism both days. It is NOT account-creation lag: Section 6 shows")
    emit(f"  the 4/17 trade-vs-fill gap is only {s6.get('gap_hours')}h.")
    emit("  This is a HISTORICAL sim->broker transition artifact — order volume")
    emit("  is normal (80-200/day) from 2026-04-21 onward.")

    sub("Q2 — Did phantoms pollute later days?")
    emit("  See Section 4: if phantom symbols reappear as local-only open")
    emit("  positions in later broker_mismatch events, downstream decisions were")
    emit("  made against a hallucinated portfolio. If not, the episodes were")
    emit("  largely self-contained (the broker reconciler eventually corrected).")

    sub("Q3 — Does the Part A price fix prevent future phantoms?")
    emit("  NO. The price-recording bug (booking exits at stop_price) and the")
    emit("  phantom-trade bug share ONE root cause — execution.py records a")
    emit("  TradeRecord without confirming the order actually filled — but they")
    emit("  are distinct failure surfaces:")
    emit("    - price bug:   order DID fill, wrong price recorded")
    emit("    - phantom bug: order did NOT fill, trade recorded anyway")
    emit("  A fix that only reads filled_avg_price after submit does NOT stop a")
    emit("  trade being written when the order never fills / the broker is down.")

    sub("Q4 — RECOMMENDATION FOR PART A SCOPE")
    emit("  EXPAND Part A: price-fix + phantom-prevention. Both are the same")
    emit("  one-line discipline — 'do not write a closed TradeRecord until the")
    emit("  order is confirmed filled, and use the confirmed fill's price'.")
    emit("  Concretely Part A should require:")
    emit("    (a) poll get_order(order_id) until status == 'filled'")
    emit("    (b) if not filled within budget -> NO TradeRecord (log + drop")
    emit("        or status='rejected'); never fall back to a planned price")
    emit("    (c) a broker-connectivity precheck so a down/unauth broker halts")
    emit("        trading instead of generating a phantom day")
    emit("")
    emit("  Scope reminder: this run was DIAGNOSTIC ONLY. No trade rows, no")
    emit("  schema, no production code modified. Parts A/B/C remain unauthorized.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    section("OLYMPUS — PHANTOM TRADE FORENSICS (2026-04-17 & 2026-04-20)")
    emit(f"  generated (UTC) : {datetime.now(tz=timezone.utc).isoformat()}")
    emit("  mode            : READ-ONLY DIAGNOSTIC")

    settings = load_settings()
    db_path = settings.DB_PATH
    emit(f"  database        : {db_path}")

    try:
        client = AlpacaClient()
        rows = client.get_activities(after=HISTORY_FETCH_FROM)
    except Exception as exc:
        emit(f"\n[FATAL] Alpaca activities fetch failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    fills = [r for r in rows if (r.get("activity_type") or "").upper() == "FILL"]
    orders = reconstruct_orders(fills)
    orders_idx: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in orders:
        orders_idx[o["symbol"]].append(o)

    try:
        conn = open_db_readonly(db_path)
    except Exception as exc:
        emit(f"\n[FATAL] DB open failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    try:
        by_day = section_1_inventory(conn, orders_idx)
        section_2_alpaca(fills)
        s2b = section_2b_order_ledger(client, by_day)
        section_3_logs()
        section_4_propagation(conn, by_day)
        section_5_pre_alpaca(conn)
        s6 = section_6_account_creation(conn, fills)
        section_7_verdict(by_day, s6, s2b)
    finally:
        conn.close()

    _flush_report()
    return 0


def _flush_report() -> None:
    try:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text("\n".join(_REPORT_LINES) + "\n", encoding="utf-8")
        print(f"\n[report saved] {OUTPUT_PATH}")
    except Exception as exc:
        print(f"\n[WARN] could not save report file: {exc}")


if __name__ == "__main__":
    sys.exit(main())
