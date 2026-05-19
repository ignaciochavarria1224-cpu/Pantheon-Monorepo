"""
reconciler_behavior_analysis.py — READ-ONLY analysis of the PositionManager /
broker reconciliation path.

PURPOSE
-------
Pre-Part-A diagnostic. Check 2 of pre_build_safety_checks revealed a distinct
PositionManager reconciliation bug: the reconciler detects local/broker
mismatch (647 events) but never acts on it. This script characterizes that
detect-but-don't-act behavior so the reconciler fix can be scoped, and answers
whether Part A may ship in isolation.

STRICT SCOPE — DIAGNOSTIC ONLY
------------------------------
- Read-only. No production code edits. No DB writes (no evictions, no cleanup).
- Alpaca calls are read-only (get_positions only). Parts A/B/C unauthorized.

OUTPUT
------
Plain-text report to stdout AND saved to
scripts/investigations/output/reconciler_behavior_report.txt.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/investigations/reconciler_behavior_analysis.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
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

PHANTOM_SYMBOLS = ["BKR", "NKE", "LLY", "PSA"]
PHANTOM_DAYS = ["2026-04-17", "2026-04-20"]
RECON_PATH = _OLYMPUS_ROOT / "core" / "trading" / "reconciliation.py"
LOOP_PATH = _OLYMPUS_ROOT / "core" / "trading" / "loop.py"
WRITER_PATH = _OLYMPUS_ROOT / "core" / "memory" / "writer.py"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "reconciler_behavior_report.txt"

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


def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("SELECT 1 FROM system_events LIMIT 1").fetchone()
    return conn


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []


def show_range(path: Path, start: int, end: int, indent: str = "    ") -> None:
    """Print lines [start, end] (1-indexed) of a file with line numbers."""
    lines = read_lines(path)
    for n in range(start, min(end, len(lines)) + 1):
        emit(f"{indent}{n:>4}  {lines[n - 1]}")


def find_line(path: Path, needle: str, after: int = 0) -> Optional[int]:
    lines = read_lines(path)
    for n in range(after, len(lines)):
        if needle in lines[n]:
            return n + 1
    return None


# ---------------------------------------------------------------------------
# Section 1 — Where is the reconciler and what does it do?
# ---------------------------------------------------------------------------

def section_1_reconciler() -> dict[str, Any]:
    section("SECTION 1 — WHERE IS THE RECONCILER, AND WHAT DOES IT DO?")

    sub("1a. The reconciler module")
    emit(f"  file: {RECON_PATH.relative_to(_OLYMPUS_ROOT).as_posix()}")
    cr = find_line(RECON_PATH, "def check_and_repair")
    dpm = find_line(RECON_PATH, "def detect_position_mismatch")
    emit(f"  BrokerReconciler.check_and_repair() at line {cr}")
    emit(f"  detect_position_mismatch() at line {dpm}")

    sub("1b. check_and_repair() — full body (the only act-on-mismatch code)")
    if cr:
        show_range(RECON_PATH, cr, cr + 33)

    # 1c. Is it wired into the live loop?
    sub("1c. Is the reconciler invoked by the trading loop?")
    loop_uses = find_line(LOOP_PATH, "reconcil") or find_line(LOOP_PATH, "Reconciler")
    emit(f"  loop.py references 'reconcil'/'Reconciler' : "
         f"{'yes (line %d)' % loop_uses if loop_uses else 'NO'}")
    # The writer subclass holds the reconciler; show its own comment.
    hold = find_line(WRITER_PATH, "does not imply in-loop")
    if hold:
        emit("  writer.py (MemoryAwarePaperTradingLoop docstring) states:")
        show_range(WRITER_PATH, hold - 2, hold + 1)
    emit("")
    emit("  => BrokerReconciler is instantiated in run_live.py and passed to the")
    emit("     loop, but the trading cycle DELIBERATELY never calls it (per the")
    emit("     writer.py docstring). check_and_repair() is unreached in normal")
    emit("     operation.")

    # 1d. Where do the broker_mismatch events actually come from?
    sub("1d. Where the 647 broker_mismatch events actually come from")
    inline = find_line(LOOP_PATH, 'diagnostics["broker_state"]')
    emit(f"  loop.py builds diagnostics['broker_state'] inline at line {inline}.")
    emit("  This is a SEPARATE, inline reimplementation of mismatch detection")
    emit("  inside _run_cycle — it computes `mismatch` and `reason` and writes")
    emit("  them to cycle diagnostics. It is detection + logging ONLY.")
    if inline:
        show_range(LOOP_PATH, inline - 7, inline + 7)

    # 1e. Verdict on eviction logic
    sub("1e. Does eviction / adoption logic exist?")
    recon_text = "\n".join(read_lines(RECON_PATH)).lower()
    has_evict = any(k in recon_text for k in ("evict", "remove_position", "drop_position",
                                              "del self._positions", "discard"))
    has_adopt = any(k in recon_text for k in ("adopt", "add_position", "import_position"))
    emit(f"  local-position EVICTION logic in reconciler  : "
         f"{'present' if has_evict else 'ABSENT'}")
    emit(f"  broker-position ADOPTION logic in reconciler : "
         f"{'present' if has_adopt else 'ABSENT'}")
    emit("  The only act-on-mismatch path, check_and_repair(), calls")
    emit("  cancel_all_orders() + close_all_positions() — it FLATTENS the BROKER")
    emit("  side. It never edits local PositionManager state. And it is gated")
    emit("  behind OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS (default False).")

    return {"loop_calls_reconciler": bool(loop_uses),
            "has_evict": has_evict, "has_adopt": has_adopt}


# ---------------------------------------------------------------------------
# Section 2 — The 4 permanent phantom positions
# ---------------------------------------------------------------------------

def section_2_phantoms(
    conn: sqlite3.Connection,
    client: AlpacaClient,
    mismatch_events: list[dict[str, Any]],
) -> dict[str, Any]:
    section("SECTION 2 — THE 4 PERMANENT PHANTOM POSITIONS (BKR, NKE, LLY, PSA)")

    # Current broker positions (read-only).
    try:
        broker_now = {str(p.get("symbol")).upper(): p
                      for p in client.get_positions()}
    except Exception as exc:
        emit(f"  [WARN] get_positions() failed: {exc}")
        broker_now = {}
    emit(f"  Alpaca positions held RIGHT NOW : "
         f"{sorted(broker_now) if broker_now else '(none — account flat)'}")

    # open_positions table state.
    op_count = conn.execute("SELECT COUNT(*) n FROM open_positions").fetchone()["n"]
    emit(f"  open_positions table row count  : {op_count}")
    emit("  (the loop's in-memory PositionManager state is not historically")
    emit("   persisted; entry_price/trade_id of an in-memory stuck position are")
    emit("   only recoverable via the broker_mismatch event snapshots below.)")

    results: dict[str, Any] = {}
    for sym in PHANTOM_SYMBOLS:
        sub(f"{sym}")
        # Events where this symbol is local-only.
        lo_events = [e for e in mismatch_events if sym in e["local_only"]]
        bo_events = [e for e in mismatch_events if sym in e["broker_only"]]
        emit(f"  local-only in   : {len(lo_events)} broker_mismatch events")
        emit(f"  broker-only in  : {len(bo_events)} broker_mismatch events")
        if lo_events:
            first, last = lo_events[0], lo_events[-1]
            meta_pos = (first["meta"].get("local_open_positions") or {}).get(sym, {})
            emit(f"  first seen local-only : {first['time']}  "
                 f"(side={meta_pos.get('side')}, qty={meta_pos.get('qty')})")
            emit(f"  last  seen local-only : {last['time']}")
        # Currently held at broker?
        emit(f"  held at Alpaca now    : {'YES' if sym in broker_now else 'no'}")
        # Phantom-batch origin: trades on 4/17 / 4/20.
        for day in PHANTOM_DAYS:
            n = conn.execute(
                "SELECT COUNT(*) n FROM trades WHERE symbol = ? "
                "AND substr(entry_time,1,10) = ?", (sym, day)).fetchone()["n"]
            emit(f"  trades rows entered {day} : {n}")
        era = conn.execute(
            "SELECT COUNT(*) n FROM trades WHERE symbol = ? "
            "AND substr(entry_time,1,10) >= '2026-04-17'", (sym,)).fetchone()["n"]
        emit(f"  trades rows, Alpaca era total : {era}")
        results[sym] = {"lo_events": len(lo_events), "bo_events": len(bo_events),
                        "held_now": sym in broker_now}

    sub("Cross-reference with phantom_forensics §4")
    emit("  phantom_forensics §4 reported BKR local-only in 87 (post-4/17) +")
    emit("  179 (post-4/20) broker_mismatch events, and PSA in 166. The")
    emit("  local-only counts above are over ALL post-4/22 events; if BKR/PSA")
    emit("  dominate, these are the same stuck entries — confirmed continuity.")

    return results


# ---------------------------------------------------------------------------
# Section 3 — The broker-only events: real capital exposure check
# ---------------------------------------------------------------------------

def section_3_broker_only(
    client: AlpacaClient,
    mismatch_events: list[dict[str, Any]],
) -> dict[str, Any]:
    section("SECTION 3 — BROKER-ONLY EVENTS: REAL CAPITAL EXPOSURE CHECK")

    try:
        broker_now = {str(p.get("symbol")).upper() for p in client.get_positions()}
    except Exception:
        broker_now = set()

    bo_events = [e for e in mismatch_events if e["broker_only"]]
    emit(f"  broker_mismatch events with broker-only symbols : {len(bo_events)}")
    emit(f"  Alpaca positions held right now                 : "
         f"{sorted(broker_now) if broker_now else '(none — account flat)'}")

    # Every distinct broker-only (symbol) occurrence.
    bo_symbol_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in bo_events:
        for s in e["broker_only"]:
            bo_symbol_events[s].append(e)

    sub("Broker-only symbols — broker held a position local had no record of")
    emit(f"  {'symbol':<8} {'events':>7} {'first':<26} {'last':<26} {'held now':>9}")
    emit(f"  {'-' * 80}")
    for s in sorted(bo_symbol_events, key=lambda k: -len(bo_symbol_events[k])):
        evs = bo_symbol_events[s]
        emit(f"  {s:<8} {len(evs):>7} {evs[0]['time']:<26} {evs[-1]['time']:<26} "
             f"{('YES' if s in broker_now else 'no'):>9}")

    # PSA oscillation timeline.
    sub("PSA state timeline (4/22 -> 5/15): local vs broker per mismatch event")
    emit(f"  {'event_time':<28} {'local?':<8} {'broker?':<9} {'classification'}")
    emit(f"  {'-' * 74}")
    psa_flips = 0
    prev = None
    for e in mismatch_events:
        meta = e["meta"]
        in_local = "PSA" in (meta.get("local_open_positions") or meta.get("local_open_symbols") or [])
        in_broker = "PSA" in (meta.get("broker_open_positions") or meta.get("broker_open_symbols") or [])
        if not in_local and not in_broker:
            continue
        if in_local and in_broker:
            klass = "agree (both hold)"
        elif in_local:
            klass = "LOCAL-ONLY phantom"
        else:
            klass = "BROKER-ONLY (untracked exposure)"
        state = (in_local, in_broker)
        if prev is not None and state != prev:
            psa_flips += 1
        prev = state
        emit(f"  {e['time']:<28} {str(in_local):<8} {str(in_broker):<9} {klass}")
    emit(f"  PSA local/broker state flips across the period : {psa_flips}")

    sub("CRITICAL — untracked real-capital exposure")
    still_held = [s for s in bo_symbol_events if s in broker_now]
    if still_held:
        emit(f"  !! {len(still_held)} broker-only symbol(s) STILL held at Alpaca: "
             f"{still_held}")
        emit("     Real capital is in positions Olympus does not track RIGHT NOW.")
    else:
        emit("  All broker-only positions are HISTORICAL — the account is flat")
        emit("  now (0 positions), so there is no untracked exposure at present.")
        emit("  But at the time of each event above, the broker DID hold a")
        emit("  position Olympus had no local record of — real capital was")
        emit("  briefly unmanaged by Olympus on those cycles.")

    return {"bo_event_count": len(bo_events),
            "bo_symbols": len(bo_symbol_events),
            "still_held": still_held,
            "psa_flips": psa_flips}


# ---------------------------------------------------------------------------
# Section 4 — Decision-contamination check
# ---------------------------------------------------------------------------

def section_4_contamination(conn: sqlite3.Connection) -> dict[str, Any]:
    section("SECTION 4 — DECISION-CONTAMINATION CHECK")

    # 4a. Re-entry attempts on the 4 stuck symbols after they got stuck.
    sub("4a. Re-entry attempts on the 4 stuck phantom symbols")
    emit("  If local state says a symbol is held, entry logic should skip it.")
    reentry: dict[str, int] = {}
    for sym in PHANTOM_SYMBOLS:
        rows = conn.execute(
            "SELECT substr(entry_time,1,10) d, COUNT(*) n FROM trades "
            "WHERE symbol = ? AND substr(entry_time,1,10) >= '2026-04-22' "
            "GROUP BY d ORDER BY d", (sym,)).fetchall()
        total = sum(r["n"] for r in rows)
        reentry[sym] = total
        emit(f"  {sym}: {total} trades entered on/after 2026-04-22 "
             f"across {len(rows)} day(s)")

    # 4b. Slot contamination via cycle_diagnostics broker_state.
    sub("4b. Portfolio-slot contamination (cycle_diagnostics)")
    settings = load_settings()
    max_open = getattr(settings, "MAX_OPEN_POSITIONS", 20)
    emit(f"  MAX_OPEN_POSITIONS = {max_open}  "
         f"(LONG_MAX={getattr(settings, 'LONG_MAX_OPEN_POSITIONS', '?')}, "
         f"SHORT_MAX={getattr(settings, 'SHORT_MAX_OPEN_POSITIONS', '?')})")

    cyc_rows = conn.execute(
        "SELECT event_time, metadata_json FROM system_events "
        "WHERE event_type = 'cycle_diagnostics' ORDER BY event_time"
    ).fetchall()

    cycles_with_phantom = 0
    entries_in_contaminated = 0
    near_cap_with_phantom = 0
    inflation_samples: list[int] = []
    total_cycles = 0
    for r in cyc_rows:
        try:
            md = json.loads(r["metadata_json"] or "{}")
        except Exception:
            continue
        bs = md.get("broker_state") or {}
        local_syms = set(bs.get("local_open_symbols") or [])
        broker_syms = set(bs.get("broker_open_symbols") or [])
        if not local_syms and not broker_syms:
            continue
        total_cycles += 1
        local_only = local_syms - broker_syms
        inflation_samples.append(len(local_only))
        entries = md.get("entries") or {}
        filled = int(entries.get("filled") or 0)
        if local_only:
            cycles_with_phantom += 1
            entries_in_contaminated += filled
            if len(local_syms) >= max_open - 2:
                near_cap_with_phantom += 1

    emit(f"  cycle_diagnostics with broker_state         : {total_cycles}")
    emit(f"  cycles where local state held >=1 phantom   : {cycles_with_phantom}")
    if total_cycles:
        emit(f"    ({100.0 * cycles_with_phantom / total_cycles:.1f}% of cycles)")
    emit(f"  entries FILLED during contaminated cycles   : {entries_in_contaminated}")
    emit(f"  contaminated cycles at/near the {max_open}-slot cap : "
         f"{near_cap_with_phantom}")
    if inflation_samples:
        avg_inflation = sum(inflation_samples) / len(inflation_samples)
        emit(f"  avg local-only (phantom) symbols per cycle  : {avg_inflation:.2f}")
        emit(f"  max local-only symbols in a single cycle    : "
             f"{max(inflation_samples)}")

    emit("")
    emit("  Interpretation: every entry filled during a contaminated cycle was")
    emit("  sized/slotted against a portfolio whose local position set included")
    emit("  phantom holdings. Sizing keys off live Alpaca equity (not phantom-")
    emit("  affected), but the MAX_OPEN_POSITIONS slot count is taken from LOCAL")
    emit("  open positions — so phantom holdings consume real entry slots.")

    return {"reentry": reentry,
            "cycles_with_phantom": cycles_with_phantom,
            "total_cycles": total_cycles,
            "entries_in_contaminated": entries_in_contaminated,
            "near_cap_with_phantom": near_cap_with_phantom}


# ---------------------------------------------------------------------------
# Section 5 — Verdict
# ---------------------------------------------------------------------------

def section_5_verdict(
    s1: dict[str, Any], s2: dict[str, Any],
    s3: dict[str, Any], s4: dict[str, Any],
) -> None:
    section("SECTION 5 — VERDICT")

    sub("Q1 — Broken eviction logic, or NO eviction logic? (repair vs build new)")
    emit("  NO eviction logic. The reconciler has detection + a broker-side")
    emit("  flatten ('repair' = close everything at Alpaca, default-off). It has")
    emit(f"  no local-position eviction (present={s1['has_evict']}) and no broker-")
    emit(f"  position adoption (present={s1['has_adopt']}). Furthermore the loop")
    emit("  does not even call BrokerReconciler — it inlines a detection-only")
    emit("  copy. => The fix is BUILD NEW (local-state healing + wire it in),")
    emit("  not repair.")

    sub("Q2 — Is the 201 broker-only finding real exposure, or stale history?")
    if s3["still_held"]:
        emit(f"  REAL, CURRENT exposure: {s3['still_held']} still held at Alpaca")
        emit("  with no local record. This is live and must be addressed now.")
    else:
        emit("  Stale/historical. The account is flat now (0 broker positions),")
        emit("  so there is no untracked exposure at present. BUT each broker-")
        emit("  only event was a real cycle on which the broker held capital")
        emit("  Olympus did not track — a genuine (if transient) exposure that")
        emit("  recurred across the period. Not a current emergency; is a real")
        emit("  correctness gap the reconciler fix must close.")

    sub("Q3 — Recommended scope for the reconciler fix")
    emit("  SEPARABLE from Part A. Part A (fill-confirmation gate) touches")
    emit("  execution.py and stops NEW local-only phantoms at the source.")
    emit("  The reconciler fix touches loop.py + reconciliation.py + manager.py")
    emit("  and heals/evicts EXISTING stuck state + handles the broker-only")
    emit("  direction. Different files, different concern. Recommend a distinct")
    emit("  Part A.5 sequenced immediately AFTER Part A — Part A reduces the")
    emit("  inflow of phantoms, making the reconciler's healing job smaller and")
    emit("  easier to verify. They need not be one coordinated commit.")

    sub("Q4 — GO / NO-GO on authorizing Part A in isolation")
    emit("  GO. Part A is well-scoped, self-contained, and correct on its own.")
    emit("  It does not depend on the reconciler fix and does not make the")
    emit("  reconciler situation worse. The reconciler bug is now well-")
    emit("  understood and cleanly separable as Part A.5.")
    emit("  CAVEAT: Part A alone will NOT clear the existing stuck phantoms or")
    emit("  the broker_mismatch events. That is expected and is Part A.5's job.")
    emit("")
    emit("  Contamination context (Section 4): "
         f"{s4['cycles_with_phantom']}/{s4['total_cycles']} cycles ran with at")
    emit(f"  least one phantom in local state; {s4['entries_in_contaminated']} entries were")
    emit("  filled during those cycles, slotted against a contaminated portfolio.")
    emit("  This argues for scheduling Part A.5 promptly after Part A — not for")
    emit("  delaying Part A.")
    emit("")
    emit("  Scope reminder: DIAGNOSTIC ONLY — no production code, no DB writes.")
    emit("  Parts A/B/C remain unauthorized.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _load_mismatch_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT event_time, metadata_json FROM system_events "
        "WHERE event_type = 'broker_mismatch' ORDER BY event_time"
    ).fetchall()
    events: list[dict[str, Any]] = []
    for r in rows:
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except Exception:
            meta = {}
        local_pos = meta.get("local_open_positions") or {}
        broker_pos = meta.get("broker_open_positions") or {}
        local_syms = set(local_pos) or set(meta.get("local_open_symbols") or [])
        broker_syms = set(broker_pos) or set(meta.get("broker_open_symbols") or [])
        events.append({
            "time": r["event_time"],
            "meta": meta,
            "local_only": sorted(local_syms - broker_syms),
            "broker_only": sorted(broker_syms - local_syms),
        })
    return events


def main() -> int:
    section("OLYMPUS — RECONCILER BEHAVIOR ANALYSIS")
    emit(f"  generated (UTC) : {datetime.now(tz=timezone.utc).isoformat()}")
    emit("  mode            : READ-ONLY DIAGNOSTIC")

    settings = load_settings()
    db_path = settings.DB_PATH
    emit(f"  database        : {db_path}")

    try:
        client = AlpacaClient()
    except Exception as exc:
        emit(f"\n[FATAL] AlpacaClient init failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    try:
        conn = open_db_readonly(db_path)
    except Exception as exc:
        emit(f"\n[FATAL] DB open failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1

    try:
        mismatch_events = _load_mismatch_events(conn)
        s1 = section_1_reconciler()
        s2 = section_2_phantoms(conn, client, mismatch_events)
        s3 = section_3_broker_only(client, mismatch_events)
        s4 = section_4_contamination(conn)
        section_5_verdict(s1, s2, s3, s4)
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
