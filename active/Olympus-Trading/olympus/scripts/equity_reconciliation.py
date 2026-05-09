"""
equity_reconciliation.py — Read-only Alpaca + local DB reconciliation report.

Purpose
-------
The Olympus paper account has drifted ~$10.8K below its $100K starting balance,
but the local trades table only sums to a small realized PnL. This script reads
the live Alpaca paper account and the local SQLite database (both strictly
read-only) and produces a sectioned report that explains where the equity gap
lives — open-position unrealized PnL, realized PnL in the trades table, and
non-trade account activities (fees, dividends, journals).

Strict scope
------------
- Read-only: NO orders, NO position changes, NO DB writes, NO Alpaca calls
  that modify state.
- Does not start, stop, or restart Olympus. Olympus continues to run and
  hold its writer connection to olympus.db while this script reads.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/equity_reconciliation.py
"""

from __future__ import annotations

import sqlite3
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

# Bootstrap: make `olympus/` importable regardless of CWD.
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_OLYMPUS_ROOT))

# PowerShell on Windows defaults stdout to cp1252; force utf-8 so the report
# never crashes on a stray non-ASCII character.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from config.settings import load_settings  # noqa: E402
from core.broker.alpaca import AlpacaClient  # noqa: E402

STARTING_CAPITAL = 100_000.00
RECONCILIATION_TOLERANCE = 50.00  # +/-$50 residual considered fully reconciled
ACTIVITIES_LOOKBACK_DAYS = 90

# Non-FILL activity types that represent CASH FLOWS into/out of the account
# rather than trading-PnL events. The initial JNLC deposit that establishes
# the $100K starting balance is the canonical example. These are reported
# separately so the reconciliation residual is not contaminated by the
# starting deposit itself.
TRANSFER_ACTIVITY_TYPES = {
    "JNLC",   # Journal cash (deposit/withdrawal)
    "JNLS",   # Journal shares
    "CSD",    # Cash deposit
    "CSW",    # Cash withdrawal
    "ACATC",  # ACATS cash transfer in
    "ACATS",  # ACATS securities transfer
    "TRANS",  # Generic transfer
}

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_money(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"${v:,.2f}"


def fmt_signed_money(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    sign = "-" if v < 0 else "+"
    return f"{sign}${abs(v):,.2f}"


def fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:+.2f}%"


def fmt_qty(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):+d}"
    return f"{v:+,.4f}"


def header(title: str, char: str = "=") -> None:
    bar = char * 78
    print()
    print(bar)
    print(f"  {title}")
    print(bar)


def subheader(title: str) -> None:
    print()
    print(f"-- {title} " + "-" * (74 - len(title)))


def kv(label: str, value: Any, width: int = 32) -> None:
    print(f"  {label:<{width}} {value}")


# ---------------------------------------------------------------------------
# Read-only DB connection
# ---------------------------------------------------------------------------

def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    """
    Open the live olympus.db read-only with the WAL writer still active.

    Retries up to 3 times on lock errors with exponential backoff. The
    `?mode=ro` URI guarantees no write attempt; setting query_only as a
    belt-and-suspenders measure.
    """
    uri = f"file:{db_path.as_posix()}?mode=ro"
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            # Confirm the trades table is reachable; this surfaces lock errors
            # immediately rather than later inside the report.
            conn.execute("SELECT 1 FROM trades LIMIT 1").fetchone()
            return conn
        except sqlite3.OperationalError as exc:
            last_err = exc
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"Could not open {db_path} read-only after 3 attempts: {last_err}"
    )


# ---------------------------------------------------------------------------
# Section 1 — Alpaca account snapshot
# ---------------------------------------------------------------------------

def section_1_account(client: AlpacaClient) -> Optional[dict[str, Any]]:
    header("SECTION 1 — Alpaca account snapshot")
    try:
        acct = client.get_account_snapshot()
    except Exception as exc:
        print(f"  [ERROR] AlpacaClient.get_account_snapshot() failed: {exc}")
        traceback.print_exc()
        return None

    kv("account_number",         acct.get("account_number"))
    kv("status",                 acct.get("status"))
    kv("currency",               acct.get("currency"))
    created = acct.get("created_at")
    if created is not None:
        if isinstance(created, datetime):
            created_utc = created.astimezone(UTC) if created.tzinfo else created.replace(tzinfo=UTC)
            kv("account created (UTC)",  created_utc.isoformat())
            kv("account created (ET)",   created_utc.astimezone(ET).isoformat())
        else:
            kv("account created",        str(created))

    subheader("Equity & cash")
    kv("equity",                 fmt_money(acct.get("equity")))
    kv("last_equity (yest close)", fmt_money(acct.get("last_equity")))
    kv("cash",                   fmt_money(acct.get("cash")))
    kv("buying_power",           fmt_money(acct.get("buying_power")))
    kv("portfolio_value",        fmt_money(acct.get("portfolio_value")))

    subheader("Market values")
    kv("long_market_value",      fmt_money(acct.get("long_market_value")))
    kv("short_market_value",     fmt_money(acct.get("short_market_value")))
    kv("initial_margin",         fmt_money(acct.get("initial_margin")))
    kv("maintenance_margin",     fmt_money(acct.get("maintenance_margin")))
    kv("accrued_fees",           fmt_money(acct.get("accrued_fees")))

    subheader("Derived checks")
    equity = acct.get("equity")
    if equity is not None:
        delta = equity - STARTING_CAPITAL
        pct = (delta / STARTING_CAPITAL) * 100.0
        kv("equity vs $100,000",     f"{fmt_signed_money(delta)}  ({pct:+.2f}%)")

    cash = acct.get("cash")
    lmv = acct.get("long_market_value")
    smv = acct.get("short_market_value")
    if all(v is not None for v in (cash, lmv, smv, equity)):
        components = cash + lmv + smv
        diff = components - equity
        kv("cash + LMV + SMV",       fmt_money(components))
        kv("vs equity (diff)",       fmt_signed_money(diff))

    return acct


# ---------------------------------------------------------------------------
# Section 2 — Open positions
# ---------------------------------------------------------------------------

def section_2_positions(client: AlpacaClient) -> Optional[list[dict[str, Any]]]:
    header("SECTION 2 — Open positions snapshot")
    try:
        positions = client.get_positions_snapshot()
    except Exception as exc:
        print(f"  [ERROR] AlpacaClient.get_positions_snapshot() failed: {exc}")
        traceback.print_exc()
        return None

    if not positions:
        print("  (no open positions)")
        return positions

    print(
        f"  {'Symbol':<8} {'Qty':>10} {'Side':<6} "
        f"{'AvgEntry':>11} {'CurPx':>11} "
        f"{'MktValue':>14} {'CostBasis':>14} "
        f"{'UnrealPL':>14} {'UnrealPL%':>10}"
    )
    print(f"  {'-' * 110}")

    sum_unrealized = 0.0
    sum_long_mv = 0.0
    sum_short_mv = 0.0

    for p in positions:
        qty = p.get("qty") or 0.0
        # Signed qty: negative for short.
        signed_qty = qty if (p.get("side") or "long") == "long" else -abs(qty)
        mv = p.get("market_value") or 0.0
        upl = p.get("unrealized_pl") or 0.0
        sum_unrealized += upl
        if (p.get("side") or "long") == "long":
            sum_long_mv += mv
        else:
            sum_short_mv += mv

        print(
            f"  {p.get('symbol', ''):<8} "
            f"{fmt_qty(signed_qty):>10} "
            f"{(p.get('side') or ''):<6} "
            f"{fmt_money(p.get('avg_entry_price')):>11} "
            f"{fmt_money(p.get('current_price')):>11} "
            f"{fmt_money(mv):>14} "
            f"{fmt_money(p.get('cost_basis')):>14} "
            f"{fmt_signed_money(upl):>14} "
            f"{fmt_pct(p.get('unrealized_plpc')):>10}"
        )

    subheader("Totals")
    kv("open positions count",   len(positions))
    kv("sum unrealized_pl",      fmt_signed_money(sum_unrealized))
    kv("sum market_value (long)",  fmt_money(sum_long_mv))
    kv("sum market_value (short)", fmt_money(sum_short_mv))

    return positions


# ---------------------------------------------------------------------------
# Section 3 — Local trades table
# ---------------------------------------------------------------------------

def section_3_trades(conn: sqlite3.Connection) -> dict[str, Any]:
    header("SECTION 3 — Local trades table summary")

    # Total count + sum of realized_pnl
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(realized_pnl), 0.0) AS total_pnl FROM trades"
    ).fetchone()
    total_count = int(row["n"])
    total_pnl = float(row["total_pnl"])

    # "Today" in ET — trades with entry_time on this ET calendar date.
    now_et = datetime.now(tz=ET)
    today_et = now_et.date().isoformat()
    # entry_time / exit_time are stored as UTC ISO 8601 strings. Convert ET
    # day boundaries to UTC for the WHERE clause.
    et_day_start = datetime.combine(now_et.date(), datetime.min.time(), tzinfo=ET)
    et_day_end = et_day_start + timedelta(days=1)
    utc_day_start = et_day_start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    utc_day_end = et_day_end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    today_open = conn.execute(
        "SELECT COUNT(*) AS n FROM trades WHERE entry_time >= ? AND entry_time < ?",
        (utc_day_start, utc_day_end),
    ).fetchone()
    today_open_count = int(today_open["n"])

    today_closed = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(realized_pnl), 0.0) AS pnl "
        "FROM trades WHERE exit_time >= ? AND exit_time < ?",
        (utc_day_start, utc_day_end),
    ).fetchone()
    today_closed_count = int(today_closed["n"])
    today_closed_pnl = float(today_closed["pnl"])

    # Last 7 calendar days closed (ET-based window, rolling)
    seven_days_ago_et = (now_et - timedelta(days=7)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    last7 = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(realized_pnl), 0.0) AS pnl "
        "FROM trades WHERE exit_time >= ?",
        (seven_days_ago_et,),
    ).fetchone()
    last7_count = int(last7["n"])
    last7_pnl = float(last7["pnl"])

    kv("DB path",                str(conn.execute("PRAGMA database_list").fetchone()["file"]))
    kv("total trades",           f"{total_count:,}")
    kv("sum realized_pnl",       fmt_signed_money(total_pnl))
    kv(f"trades opened today (ET={today_et})", f"{today_open_count:,}")
    kv("trades closed today",    f"{today_closed_count:,}")
    kv("today's realized_pnl",   fmt_signed_money(today_closed_pnl))
    kv("trades closed last 7 d", f"{last7_count:,}")
    kv("last-7d realized_pnl",   fmt_signed_money(last7_pnl))

    return {
        "total_count": total_count,
        "total_pnl": total_pnl,
        "today_open": today_open_count,
        "today_closed": today_closed_count,
        "today_pnl": today_closed_pnl,
        "last7_count": last7_count,
        "last7_pnl": last7_pnl,
    }


# ---------------------------------------------------------------------------
# Section 4 — Reconciliation
# ---------------------------------------------------------------------------

def section_4_reconcile(
    acct: Optional[dict[str, Any]],
    positions: Optional[list[dict[str, Any]]],
    trades: dict[str, Any],
) -> dict[str, Any]:
    header("SECTION 4 — Reconciliation")

    if acct is None or acct.get("equity") is None:
        print("  [ERROR] Cannot reconcile — Alpaca account fetch failed.")
        return {"residual": None, "fits_tolerance": False, "fatal": True}

    A = acct["equity"] - STARTING_CAPITAL  # Actual gap from $100K
    B = trades["total_pnl"]                 # Realized from local DB
    C = (
        sum((p.get("unrealized_pl") or 0.0) for p in (positions or []))
        if positions is not None else None
    )

    kv("A: Alpaca equity - $100,000",     fmt_signed_money(A))
    kv("B: realized PnL (trades table)",  fmt_signed_money(B))
    if C is None:
        kv("C: unrealized PnL (positions)",  "N/A (positions fetch failed)")
    else:
        kv("C: unrealized PnL (positions)",  fmt_signed_money(C))

    if C is None:
        explained = B
    else:
        explained = B + C
    residual = A - explained
    fits = abs(residual) <= RECONCILIATION_TOLERANCE

    subheader("Result")
    kv("explained (B + C)",      fmt_signed_money(explained))
    kv("residual (A - (B+C))",   fmt_signed_money(residual))
    kv(f"within +/-${RECONCILIATION_TOLERANCE:.2f}?", "YES" if fits else "NO")

    if fits:
        print()
        print("  [OK]  Reconciliation SUCCESSFUL - gap fully explained by realized + unrealized PnL.")
    else:
        print()
        print("  [!!]  Residual exceeds tolerance - gap is NOT fully explained by trades + positions.")
        print("        Proceeding to Section 5 to inspect non-trade account activities.")

    return {
        "A": A, "B": B, "C": C,
        "explained": explained,
        "residual": residual,
        "fits_tolerance": fits,
        "fatal": False,
    }


# ---------------------------------------------------------------------------
# Section 5 — Account activities (only if residual exceeds tolerance)
# ---------------------------------------------------------------------------

def section_5_activities(
    client: AlpacaClient,
    lookback_days: int = ACTIVITIES_LOOKBACK_DAYS,
) -> Optional[dict[str, Any]]:
    header(f"SECTION 5 — Account activities (last {lookback_days} days)")
    after = datetime.now(tz=UTC) - timedelta(days=lookback_days)
    print(f"  Fetching activities after {after.isoformat()} UTC ...")

    try:
        rows = client.get_activities(after=after)
    except Exception as exc:
        print(f"  [ERROR] AlpacaClient.get_activities() failed: {exc}")
        traceback.print_exc()
        return None

    print(f"  Total activity rows fetched: {len(rows):,}")

    # Partition: FILL (trade fills) vs everything else.
    non_fill: list[dict[str, Any]] = []
    fill_count = 0
    for r in rows:
        atype = (r.get("activity_type") or "").upper()
        if atype == "FILL":
            fill_count += 1
            continue
        non_fill.append(r)

    print(f"  FILL rows (trades): {fill_count:,}")
    print(f"  Non-FILL rows: {len(non_fill):,}")

    if not non_fill:
        print()
        print("  (No non-FILL activities in the lookback window.)")
        return {
            "non_fill_total": 0.0,
            "transfer_total": 0.0,
            "operating_total": 0.0,
            "rows": [],
        }

    subheader("Non-FILL activities")
    print(
        f"  {'Date':<26} {'Type':<14} {'NetAmount':>14}  {'Class':<10}  Description"
    )
    print(f"  {'-' * 110}")

    total_non_fill = 0.0
    total_transfers = 0.0
    total_operating = 0.0
    for r in sorted(non_fill, key=lambda x: x.get("date") or x.get("transaction_time") or ""):
        when = r.get("date") or r.get("transaction_time") or ""
        atype = (r.get("activity_type") or "").upper()
        # net_amount on non-trade activities; fall back to qty*price if absent.
        net_raw = r.get("net_amount")
        if net_raw is None:
            qty = r.get("qty")
            price = r.get("price")
            try:
                net = float(qty) * float(price) if qty is not None and price is not None else 0.0
            except (TypeError, ValueError):
                net = 0.0
        else:
            try:
                net = float(net_raw)
            except (TypeError, ValueError):
                net = 0.0

        klass = "transfer" if atype in TRANSFER_ACTIVITY_TYPES else "operating"
        total_non_fill += net
        if klass == "transfer":
            total_transfers += net
        else:
            total_operating += net

        desc = r.get("description") or r.get("symbol") or ""
        print(
            f"  {str(when):<26} {str(atype):<14} {fmt_signed_money(net):>14}  {klass:<10}  {desc}"
        )

    subheader("Totals")
    kv("sum of all non-FILL net_amount",   fmt_signed_money(total_non_fill))
    kv("  of which: cash transfers (D_t)", fmt_signed_money(total_transfers))
    kv("  of which: operating  (D_op)",    fmt_signed_money(total_operating))
    print()
    print("  Note: cash transfers (JNLC etc) are the SOURCE of starting capital,")
    print("  not a PnL event. Section 6 reconciliation uses D_op (operating only).")

    return {
        "non_fill_total": total_non_fill,
        "transfer_total": total_transfers,
        "operating_total": total_operating,
        "rows": non_fill,
    }


# ---------------------------------------------------------------------------
# Section 6 — Verdict
# ---------------------------------------------------------------------------

def section_6_verdict(
    acct: Optional[dict[str, Any]],
    recon: dict[str, Any],
    activities: Optional[dict[str, Any]],
    fatal_errors: list[str],
) -> None:
    header("SECTION 6 — VERDICT", char="#")

    if recon.get("fatal") or acct is None:
        print()
        print("  Verdict: FAILED — Alpaca API or DB read errors prevented reconciliation.")
        if fatal_errors:
            print()
            print("  Errors encountered:")
            for e in fatal_errors:
                print(f"    - {e}")
        return

    A = recon["A"]
    B = recon["B"]
    C = recon["C"]
    # D = operating non-trade activities only (fees, dividends, interest...).
    # Cash transfers (JNLC etc) are the SOURCE of starting capital and are
    # excluded from the reconciliation math by definition.
    D_op = activities.get("operating_total") if activities else None
    D_transfers = activities.get("transfer_total") if activities else None

    explained_with_d = (B or 0.0) + (C or 0.0) + (D_op or 0.0)
    residual_with_d = A - explained_with_d

    kv("Alpaca equity",                  fmt_money(acct["equity"]))
    kv("Starting capital",               fmt_money(STARTING_CAPITAL))
    kv("Total gap (A)",                  fmt_signed_money(A))
    kv("Realized PnL (B)",               fmt_signed_money(B))
    kv("Unrealized PnL (C)",             fmt_signed_money(C) if C is not None else "N/A")
    kv("Operating activities (D_op)",    fmt_signed_money(D_op) if D_op is not None else "N/A (not fetched)")
    kv("Cash transfers (D_t, info)",     fmt_signed_money(D_transfers) if D_transfers is not None else "N/A")
    kv("Reconciled (B + C + D_op)",      fmt_signed_money(explained_with_d))
    kv("Residual unexplained",           fmt_signed_money(residual_with_d))

    print()
    fits_with_d = activities is not None and abs(residual_with_d) <= RECONCILIATION_TOLERANCE
    if recon["fits_tolerance"]:
        verdict = "FULLY RECONCILED - gap explained by realized + unrealized PnL"
    elif fits_with_d:
        verdict = "RECONCILED VIA ACTIVITIES - fees/dividends/etc account for residual"
    else:
        verdict = (
            f"PARTIAL RECONCILIATION - {fmt_signed_money(residual_with_d)} still unexplained"
        )
    print(f"  Verdict: {verdict}")

    # Diagnostic hint when the residual is large: most likely cause in a paper
    # account is execution slippage between what the trades table assumed
    # (filled_avg_price reported back to Olympus) and the actual fill prices,
    # or trades that never closed (open_at_window_close, then cancelled).
    if not recon["fits_tolerance"] and not fits_with_d:
        print()
        print("  Likely sources of the unexplained residual:")
        print("   - Execution slippage: difference between Olympus's recorded")
        print("     entry/exit prices and Alpaca's actual fill prices")
        print("   - Trades opened in Alpaca but not present in the local trades table")
        print("     (orphan fills from earlier runs, partial fills, or rotation legs)")
        print("   - Compare 'FILL rows (trades)' in Section 5 to 2x the trades count")
        print("     in Section 3 to see if Alpaca recorded fills the local DB missed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    settings = load_settings()
    db_path = settings.DB_PATH

    header("OLYMPUS EQUITY RECONCILIATION REPORT", char="#")
    now_utc = datetime.now(tz=UTC)
    kv("report generated (UTC)", now_utc.isoformat())
    kv("report generated (ET)",  now_utc.astimezone(ET).isoformat())
    kv("database",               str(db_path))
    kv("database mode",          "read-only (?mode=ro, query_only=ON)")
    kv("alpaca paper mode",      str(settings.ALPACA_PAPER))

    fatal_errors: list[str] = []

    # --- Initialize Alpaca client (read-only intent; never sends orders) ---
    try:
        client = AlpacaClient()
    except Exception as exc:
        msg = f"AlpacaClient initialization failed: {exc}"
        print(f"\n[FATAL] {msg}")
        traceback.print_exc()
        fatal_errors.append(msg)
        client = None  # type: ignore[assignment]

    # --- Open DB read-only ---
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = open_db_readonly(db_path)
    except Exception as exc:
        msg = f"DB open failed: {exc}"
        print(f"\n[FATAL] {msg}")
        traceback.print_exc()
        fatal_errors.append(msg)

    # --- Section 1: account ---
    acct = section_1_account(client) if client else None
    if acct is None and client is not None:
        fatal_errors.append("Section 1: Alpaca account fetch failed")

    # --- Section 2: positions ---
    positions = section_2_positions(client) if client else None
    if positions is None and client is not None:
        fatal_errors.append("Section 2: Alpaca positions fetch failed")

    # --- Section 3: trades ---
    if conn is not None:
        try:
            trades = section_3_trades(conn)
        except Exception as exc:
            msg = f"Section 3: DB query failed: {exc}"
            print(f"\n[ERROR] {msg}")
            traceback.print_exc()
            fatal_errors.append(msg)
            trades = {"total_count": 0, "total_pnl": 0.0, "today_open": 0,
                      "today_closed": 0, "today_pnl": 0.0,
                      "last7_count": 0, "last7_pnl": 0.0}
    else:
        trades = {"total_count": 0, "total_pnl": 0.0, "today_open": 0,
                  "today_closed": 0, "today_pnl": 0.0,
                  "last7_count": 0, "last7_pnl": 0.0}

    # --- Section 4: reconciliation ---
    recon = section_4_reconcile(acct, positions, trades)

    # --- Section 5: activities (only if residual > tolerance) ---
    activities: Optional[dict[str, Any]] = None
    if (
        client is not None
        and not recon.get("fatal", False)
        and not recon.get("fits_tolerance", False)
    ):
        activities = section_5_activities(client)
        if activities is None:
            fatal_errors.append("Section 5: account activities fetch failed")
    elif recon.get("fits_tolerance", False):
        header("SECTION 5 — Account activities (skipped)")
        print("  Section 4 reconciled within tolerance — Section 5 not required.")

    # --- Section 6: verdict ---
    section_6_verdict(acct, recon, activities, fatal_errors)

    # --- Cleanup ---
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass

    print()
    return 0 if not fatal_errors and not recon.get("fatal") else 1


if __name__ == "__main__":
    sys.exit(main())
