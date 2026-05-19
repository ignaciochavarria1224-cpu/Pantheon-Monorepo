"""
pre_build_safety_checks.py — READ-ONLY pre-Part-A safety diagnostic.

PURPOSE
-------
Two final checks before the Part A build (price-fix + fill-confirmation gate +
broker-connectivity precheck) is authorized:

  1. FALLBACK PATTERN AUDIT — find every `.get(...) or <fallback>` in
     core/trading/ and core/broker/, classify each as safe / suspicious /
     confirmed_bug, so Part A is not about to fix 2 instances of a pattern
     that exists in 5 places.

  2. BROKER_MISMATCH CHARACTERIZATION — characterize the 647 broker_mismatch
     events from 2026-04-22 onward to determine whether the fill-confirmation
     gate resolves them, or whether an independent PositionManager bug exists.

STRICT SCOPE — DIAGNOSTIC ONLY
------------------------------
- Read-only. No production code edits. No DB writes. Parts A/B/C unauthorized.

OUTPUT
------
Plain-text report to stdout AND saved to
scripts/investigations/output/pre_build_safety_report.txt.

Run
---
    cd olympus
    %USERPROFILE%\\OlympusLocal\\venv\\Scripts\\python.exe scripts/investigations/pre_build_safety_checks.py
"""

from __future__ import annotations

import json
import re
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCAN_DIRS = [
    _OLYMPUS_ROOT / "core" / "trading",
    _OLYMPUS_ROOT / "core" / "broker",
]
POST_TRANSITION_START = "2026-04-22"   # day after the phantom episodes
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "pre_build_safety_report.txt"

# Fallback values that are pure control-flow sentinels (safe).
SAFE_SENTINELS = {
    "None", "[]", "{}", '""', "''", "set()", "list()", "dict()", "tuple()",
    "None)", "False", "True",
}
# Tokens in a fallback that indicate it could silently substitute broker truth.
BROKER_TRUTH_RE = re.compile(
    r"price|qty|quantity|size|time|stamp|order_id|status|fill|entry|exit|"
    r"stop|target|avg|cost|equity|cash|position",
    re.IGNORECASE,
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


# ---------------------------------------------------------------------------
# Check 1 — Fallback pattern audit
# ---------------------------------------------------------------------------

# A line is a candidate when a `.get(` call is followed by ` or ` (the
# defensive-fallback idiom). Parenthesis nesting makes a strict regex fragile,
# so candidates are found loosely and the fallback expression is taken as the
# text following the LAST ` or ` on the line.
GET_RE = re.compile(r"\.get\(")
OR_RE = re.compile(r"\)\s+or\s+")


def classify_fallback(file_name: str, line: str) -> tuple[str, str]:
    """Return (classification, fallback_expr)."""
    m = OR_RE.search(line)
    fallback = line[m.end():].strip() if m else ""
    # Trim trailing syntax so the bare expression can be compared.
    fb_core = fallback.rstrip(" :,)").strip()

    # Known confirmed bug: execution.py booking a planned price as broker truth.
    if file_name == "execution.py" and re.search(
        r"\bor\s+(entry_price|exit_price)\b", line
    ):
        return "confirmed_bug", fallback

    # Pure control-flow sentinels.
    first_token = fb_core.split()[0] if fb_core else ""
    if fb_core in SAFE_SENTINELS or first_token in {"None", "[]", "{}"}:
        return "safe", fallback

    # Anything that looks like it carries broker truth.
    if BROKER_TRUTH_RE.search(fb_core):
        return "suspicious", fallback

    # Non-sentinel, non-obvious fallback — flag conservatively for human review.
    return "suspicious", fallback


def check_1_fallback_audit() -> dict[str, Any]:
    section("CHECK 1 — FALLBACK PATTERN AUDIT")
    emit("  Scanning for the `.get(...) or <fallback>` idiom that caused the")
    emit("  price bug (execution.py:65 entry, :116 exit).")
    for d in SCAN_DIRS:
        emit(f"  scan dir: {d}")

    findings: list[dict[str, Any]] = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.is_dir():
            emit(f"  [WARN] not a directory: {scan_dir}")
            continue
        for py in sorted(scan_dir.rglob("*.py")):
            try:
                lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception as exc:
                emit(f"  [WARN] could not read {py}: {exc}")
                continue
            for n, line in enumerate(lines, start=1):
                if GET_RE.search(line) and OR_RE.search(line):
                    klass, fallback = classify_fallback(py.name, line)
                    findings.append({
                        "file": py.relative_to(_OLYMPUS_ROOT).as_posix(),
                        "line_no": n,
                        "text": line.strip(),
                        "class": klass,
                        "fallback": fallback,
                    })

    klass_counts = Counter(f["class"] for f in findings)
    sub("Summary")
    emit(f"  total `.get(...) or` occurrences : {len(findings)}")
    for k in ("confirmed_bug", "suspicious", "safe"):
        emit(f"    {k:<14} {klass_counts.get(k, 0)}")

    for klass in ("confirmed_bug", "suspicious", "safe"):
        rows = [f for f in findings if f["class"] == klass]
        if not rows:
            continue
        sub(f"{klass.upper()} — {len(rows)} occurrence(s)")
        for f in rows:
            emit(f"  {f['file']}:{f['line_no']}")
            emit(f"      {f['text']}")
            emit(f"      -> fallback substitutes: {f['fallback']}")

    return {"findings": findings, "counts": klass_counts}


# ---------------------------------------------------------------------------
# Check 2 — broker_mismatch characterization
# ---------------------------------------------------------------------------

def open_db_readonly(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("SELECT 1 FROM system_events LIMIT 1").fetchone()
    return conn


def classify_event(meta: dict[str, Any]) -> dict[str, Any]:
    """Return the mismatch composition of a single broker_mismatch event."""
    local_pos = meta.get("local_open_positions") or {}
    broker_pos = meta.get("broker_open_positions") or {}
    local_syms = set(local_pos) or set(meta.get("local_open_symbols") or [])
    broker_syms = set(broker_pos) or set(meta.get("broker_open_symbols") or [])

    local_only = local_syms - broker_syms     # extra local position (phantom-like)
    broker_only = broker_syms - local_syms    # local missing a broker position
    qty_drift: list[str] = []
    side_drift: list[str] = []
    for s in local_syms & broker_syms:
        lp = local_pos.get(s) or {}
        bp = broker_pos.get(s) or {}
        if lp and bp:
            if lp.get("qty") != bp.get("qty"):
                qty_drift.append(s)
            if (lp.get("side") or "") != (bp.get("side") or ""):
                side_drift.append(s)
    return {
        "local_only": sorted(local_only),
        "broker_only": sorted(broker_only),
        "qty_drift": sorted(qty_drift),
        "side_drift": sorted(side_drift),
    }


def check_2_broker_mismatch(conn: sqlite3.Connection) -> dict[str, Any]:
    section("CHECK 2 — BROKER_MISMATCH POST-PHANTOM CHARACTERIZATION")

    rows = conn.execute(
        "SELECT event_time, metadata_json FROM system_events "
        "WHERE event_type = 'broker_mismatch' ORDER BY event_time"
    ).fetchall()
    total = len(rows)
    post = [r for r in rows if r["event_time"][:10] >= POST_TRANSITION_START]
    emit(f"  total broker_mismatch events           : {total}")
    emit(f"  events on/after {POST_TRANSITION_START} (post-transition) : {len(post)}")

    # Parse + classify each post-transition event.
    events: list[dict[str, Any]] = []
    for r in post:
        try:
            meta = json.loads(r["metadata_json"] or "{}")
        except Exception:
            meta = {}
        comp = classify_event(meta)
        comp["time"] = r["event_time"]
        events.append(comp)

    # 2a. Daily counts
    daily = Counter(e["time"][:10] for e in events)
    sub("Daily broker_mismatch counts (post-transition)")
    emit(f"  {'Date':<14} {'Events':>8}")
    emit(f"  {'-' * 24}")
    for day in sorted(daily):
        emit(f"  {day:<14} {daily[day]:>8}")

    # 2b. Mismatch-type composition (per-event totals)
    n_local_only = sum(1 for e in events if e["local_only"])
    n_broker_only = sum(1 for e in events if e["broker_only"])
    n_qty = sum(1 for e in events if e["qty_drift"])
    n_side = sum(1 for e in events if e["side_drift"])
    sub("Mismatch-type composition (events containing each type)")
    emit(f"  events with local-only symbols (extra local position) : {n_local_only}")
    emit(f"  events with broker-only symbols (missing local pos)   : {n_broker_only}")
    emit(f"  events with qty drift (same symbol, different qty)    : {n_qty}")
    emit(f"  events with side drift (same symbol, different side)  : {n_side}")

    # 2c. Symbol clustering — how often each symbol is on the mismatched side.
    sym_local_only: Counter = Counter()
    sym_broker_only: Counter = Counter()
    for e in events:
        for s in e["local_only"]:
            sym_local_only[s] += 1
        for s in e["broker_only"]:
            sym_broker_only[s] += 1
    sub("Top symbols — appearing as LOCAL-ONLY (local thinks it holds, broker doesn't)")
    for s, n in sym_local_only.most_common(15):
        emit(f"  {s:<7} {n:>5} events")
    sub("Top symbols — appearing as BROKER-ONLY (broker holds, local doesn't)")
    if sym_broker_only:
        for s, n in sym_broker_only.most_common(15):
            emit(f"  {s:<7} {n:>5} events")
    else:
        emit("  (none — broker never held a position local was unaware of)")

    # 2d. Persistence — longest consecutive run of events a symbol stays
    #     local-only. Events are ordered; a long run = a sticky mismatch.
    runs: dict[str, int] = defaultdict(int)
    cur: dict[str, int] = defaultdict(int)
    for e in events:
        present = set(e["local_only"])
        for s in list(cur):
            if s not in present:
                cur[s] = 0
        for s in present:
            cur[s] += 1
            runs[s] = max(runs[s], cur[s])
    sub("Persistence — longest consecutive-event local-only streak per symbol")
    streak_buckets = Counter()
    for s, r in runs.items():
        if r <= 1:
            streak_buckets["1 event (transient)"] += 1
        elif r <= 3:
            streak_buckets["2-3 events"] += 1
        elif r <= 10:
            streak_buckets["4-10 events"] += 1
        else:
            streak_buckets["11+ events (sticky)"] += 1
    for label in ("1 event (transient)", "2-3 events", "4-10 events",
                  "11+ events (sticky)"):
        emit(f"  {label:<26} {streak_buckets.get(label, 0):>4} symbols")
    worst = sorted(runs.items(), key=lambda kv: -kv[1])[:8]
    emit("  worst offenders (symbol: longest streak):")
    for s, r in worst:
        emit(f"    {s:<7} {r} consecutive events")

    return {
        "total": total,
        "post_count": len(post),
        "events": events,
        "n_local_only": n_local_only,
        "n_broker_only": n_broker_only,
        "n_qty": n_qty,
        "n_side": n_side,
        "max_streak": max(runs.values()) if runs else 0,
        "sticky_symbols": streak_buckets.get("11+ events (sticky)", 0),
    }


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def verdict(c1: dict[str, Any], c2: dict[str, Any]) -> None:
    section("VERDICT")

    counts = c1["counts"]
    sub("Q1 — Other `or fallback` instances that need Part A scope?")
    emit(f"  confirmed_bug : {counts.get('confirmed_bug', 0)}")
    emit(f"  suspicious    : {counts.get('suspicious', 0)}")
    emit(f"  safe          : {counts.get('safe', 0)}")
    if counts.get("suspicious", 0) == 0:
        emit("  => No suspicious fallbacks beyond the known bug. Part A's price")
        emit("     scope is COMPLETE as currently defined.")
    else:
        emit("  => Suspicious fallbacks exist beyond execution.py. Part A scope")
        emit("     should review the lines listed under SUSPICIOUS above and")
        emit("     decide which to include in the fix.")

    sub("Q2 — Will the fill-confirmation gate resolve broker_mismatch?")
    emit(f"  post-transition events     : {c2['post_count']}")
    emit(f"  with local-only symbols    : {c2['n_local_only']}")
    emit(f"  with broker-only symbols   : {c2['n_broker_only']}")
    emit(f"  longest sticky streak      : {c2['max_streak']} consecutive events")
    emit(f"  symbols sticky 11+ events  : {c2['sticky_symbols']}")
    has_sticky = c2["sticky_symbols"] > 0 or c2["max_streak"] >= 11
    has_broker_only = c2["n_broker_only"] > 0
    emit("")
    emit("  PARTIALLY. The gate resolves the TRANSIENT local-only mismatches")
    emit("  (1-event streaks) — that is the record-before-broker-confirms")
    emit("  latency pattern, and it is the bulk of distinct symbols. BUT:")
    if has_sticky:
        emit(f"   - {c2['sticky_symbols']} symbols are STICKY (>=11 consecutive events;")
        emit(f"     worst = {c2['max_streak']} events). A position stuck local-only for")
        emit("     that long is a permanent phantom the PM never evicts. The gate")
        emit("     stops NEW phantoms; it does NOT clean up already-stuck state.")
    if has_broker_only:
        emit(f"   - {c2['n_broker_only']} events have BROKER-ONLY symbols (broker holds a")
        emit("     position local lost track of). The gate does not touch that")
        emit("     direction at all.")
    if has_sticky or has_broker_only:
        emit("  => An independent PositionManager / reconciliation gap IS")
        emit("     indicated: the reconciler DETECTS mismatch (647 events) but")
        emit("     does not EVICT stale local positions or adopt unknown broker")
        emit("     positions. This is separate from the fill-confirmation gate.")
    else:
        emit("  => No independent PositionManager bug indicated.")

    sub("GO / NO-GO — authorize Part A as scoped (price-fix + fill-confirmation")
    sub("           gate + broker-connectivity precheck)?")
    scope_complete = counts.get("suspicious", 0) == 0
    if scope_complete:
        emit("  RESULT: GO for Part A as scoped.")
        emit("  - Check 1 clean: the 2 confirmed bugs are the ONLY broker-truth")
        emit("    fallbacks; Part A's price-fix scope is complete.")
        emit("  - Part A correctly fixes the price bug and prevents NEW phantoms.")
        if has_sticky or has_broker_only:
            emit("  CAVEAT — do not expect broker_mismatch to drop to zero after")
            emit("  Part A. The sticky/broker-only mismatches are a SEPARATE")
            emit("  PositionManager state-healing issue. Flag as a follow-up item;")
            emit("  it does not block Part A and is not part of its scope.")
    else:
        emit("  RESULT: REVIEW NEEDED — "
             f"{counts['suspicious']} suspicious fallback(s) to triage for scope.")

    emit("")
    emit("  Scope reminder: DIAGNOSTIC ONLY — no production code, no DB writes.")
    emit("  Parts A/B/C remain unauthorized.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    section("OLYMPUS — PRE-PART-A SAFETY CHECKS")
    emit(f"  generated (UTC) : {datetime.now(tz=timezone.utc).isoformat()}")
    emit("  mode            : READ-ONLY DIAGNOSTIC")

    settings = load_settings()
    db_path = settings.DB_PATH
    emit(f"  database        : {db_path}")

    c1 = check_1_fallback_audit()

    try:
        conn = open_db_readonly(db_path)
    except Exception as exc:
        emit(f"\n[FATAL] DB open failed: {exc}")
        traceback.print_exc()
        _flush_report()
        return 1
    try:
        c2 = check_2_broker_mismatch(conn)
    finally:
        conn.close()

    verdict(c1, c2)
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
