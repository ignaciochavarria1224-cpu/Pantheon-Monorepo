from __future__ import annotations

import json
import re
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from config import PANTHEON_PALACE_DIR

from pantheon.services import blackbook, maridian, olympus


ROOMS = ("finance", "trading", "self", "ops")
KINDS = ("concepts", "entities", "syntheses")
META_DIR = Path(PANTHEON_PALACE_DIR) / "_meta"
HEARTBEATS_DIR = Path(PANTHEON_PALACE_DIR) / "ops" / "heartbeats"
CATALOG_PATH = META_DIR / "catalog.json"
STATUS_PATH = META_DIR / "compile_status.json"

_job_lock = threading.Lock()
_job_state: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "mode": "incremental",
    "trigger": "",
    "pages_written": 0,
    "error": "",
    "subsystem_errors": {},
}


def ensure_structure() -> None:
    for room in ROOMS:
        room_root = Path(PANTHEON_PALACE_DIR) / room
        room_root.mkdir(parents=True, exist_ok=True)
        for kind in KINDS:
            (room_root / kind).mkdir(parents=True, exist_ok=True)
    HEARTBEATS_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return clean or "untitled"


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(token) >= 3
    }


def _format_currency(value: float | int | None) -> str:
    return f"${float(value or 0):,.2f}"


def _parse_timestamp(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    try:
        return datetime.fromisoformat(raw).strftime("%B %d, %Y %H:%M")
    except ValueError:
        return raw


def _page_path(room: str, kind: str, slug: str) -> Path:
    return Path(PANTHEON_PALACE_DIR) / room / kind / f"{slug}.md"


def _write_page(
    *,
    room: str,
    kind: str,
    slug: str,
    title: str,
    source_system: str,
    summary: str,
    bullets: list[str],
    references: list[str],
    related: list[str],
) -> dict[str, Any]:
    ensure_structure()
    path = _page_path(room, kind, slug)
    now = datetime.now().isoformat()
    lines = [
        f"# {title}",
        "",
        f"- Source System: {source_system}",
        f"- Room: {room}",
        f"- Kind: {kind}",
        f"- Last Updated: {now}",
        "",
        "## Summary",
        summary,
        "",
        "## Signals",
    ]
    lines.extend(f"- {item}" for item in bullets or ["No strong signals recorded yet."])
    lines.extend(["", "## References"])
    lines.extend(f"- {item}" for item in references or ["No source references captured."])
    lines.extend(["", "## Related"])
    lines.extend(f"- {item}" for item in related or ["No related pages linked yet."])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return {
        "title": title,
        "room": room,
        "kind": kind,
        "slug": slug,
        "path": str(path),
        "source_system": source_system,
        "summary": summary,
        "updated_at": now,
        "references": references,
        "related": related,
    }


def _normalize_merchant(description: str) -> str:
    text = (description or "").strip()
    if not text:
        return "unknown-merchant"
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^A-Za-z0-9 &/-]", "", text)
    return text[:48].strip() or "unknown-merchant"


def _classify_room(query: str) -> str | None:
    lower = query.lower()
    finance_terms = ("spending", "expense", "food", "merchant", "transaction", "money", "budget", "chipotle", "balance")
    trading_terms = ("trade", "setup", "symbol", "olympus", "apex", "chop", "market", "pnl", "ranking")
    self_terms = ("journal", "reflection", "theme", "belief", "question", "maridian", "self")
    ops_terms = ("failure", "doctor", "heartbeat", "health", "system", "when did", "offline", "error")
    if any(term in lower for term in ops_terms):
        return "ops"
    if any(term in lower for term in trading_terms):
        return "trading"
    if any(term in lower for term in finance_terms):
        return "finance"
    if any(term in lower for term in self_terms):
        return "self"
    return None


def compile_blackbook_pages() -> list[dict[str, Any]]:
    snapshot = blackbook.get_snapshot()
    transactions = blackbook.get_recent_transactions(limit=500)
    balances = snapshot.get("balances", [])
    pages: list[dict[str, Any]] = []

    category_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    merchant_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    weekend_total = 0.0
    weekday_total = 0.0

    for tx in transactions:
        amount = float(tx.get("amount") or 0)
        tx_type = (tx.get("type") or "").lower()
        if tx_type != "expense":
            continue
        category = str(tx.get("category") or "Other").title()
        merchant = _normalize_merchant(str(tx.get("description") or "Unknown"))
        category_totals[category]["total"] += amount
        category_totals[category]["count"] += 1
        merchant_totals[merchant]["total"] += amount
        merchant_totals[merchant]["count"] += 1
        try:
            weekday = datetime.fromisoformat(str(tx.get("date"))).weekday()
            if weekday >= 5:
                weekend_total += amount
            else:
                weekday_total += amount
        except Exception:
            weekday_total += amount

    for category, stats in sorted(category_totals.items(), key=lambda item: item[1]["total"], reverse=True)[:4]:
        slug = _slug(f"{category}-spending")
        summary = (
            f"{category} spending totals {_format_currency(stats['total'])} across {int(stats['count'])} recent expense transactions. "
            f"This page is compiled from BlackBook ledger activity."
        )
        pages.append(
            _write_page(
                room="finance",
                kind="concepts",
                slug=slug,
                title=f"{category} Spending",
                source_system="blackbook",
                summary=summary,
                bullets=[
                    f"Recent total: {_format_currency(stats['total'])}",
                    f"Recent transaction count: {int(stats['count'])}",
                    f"Ledger truth is the default source for Pantheon balance and pattern answers.",
                ],
                references=[f"BlackBook ledger transactions ({int(stats['count'])} rows)"],
                related=["[[finance/syntheses/spending-patterns]]"],
            )
        )

    for merchant, stats in sorted(merchant_totals.items(), key=lambda item: item[1]["count"], reverse=True)[:5]:
        slug = _slug(merchant)
        summary = (
            f"{merchant} appeared {int(stats['count'])} times in recent BlackBook expenses for a total of "
            f"{_format_currency(stats['total'])}."
        )
        pages.append(
            _write_page(
                room="finance",
                kind="entities",
                slug=slug,
                title=merchant,
                source_system="blackbook",
                summary=summary,
                bullets=[
                    f"Visits / charges: {int(stats['count'])}",
                    f"Recent spend: {_format_currency(stats['total'])}",
                ],
                references=[f"BlackBook merchant history for {merchant}"],
                related=["[[finance/syntheses/spending-patterns]]"],
            )
        )

    top_assets = [item["name"] for item in balances if not item.get("is_debt")][:3]
    top_debts = [item["name"] for item in balances if item.get("is_debt")][:3]
    pages.append(
        _write_page(
            room="finance",
            kind="syntheses",
            slug="spending-patterns",
            title="Spending Patterns",
            source_system="blackbook",
            summary=(
                f"Pantheon sees {_format_currency(weekend_total)} of recent weekend spending versus "
                f"{_format_currency(weekday_total)} on weekdays, with categories like "
                f"{', '.join(category_totals.keys()) or 'uncategorized activity'} leading the ledger."
            ),
            bullets=[
                f"Weekend spend: {_format_currency(weekend_total)}",
                f"Weekday spend: {_format_currency(weekday_total)}",
                f"Top asset accounts: {', '.join(top_assets) or 'none'}",
                f"Top debt accounts: {', '.join(top_debts) or 'none'}",
            ],
            references=[
                f"BlackBook balances ({len(balances)} accounts)",
                f"BlackBook transactions ({len(transactions)} rows sampled)",
            ],
            related=[f"[[finance/concepts/{_slug(name)}-spending]]" for name in list(category_totals.keys())[:3]],
        )
    )
    return pages


def compile_olympus_pages() -> list[dict[str, Any]]:
    snapshot = olympus.get_snapshot()
    performance = snapshot.get("performance") or {}
    trades = snapshot.get("recent_trades") or []
    cycle = snapshot.get("latest_cycle") or {}
    report_excerpt = str(snapshot.get("report_excerpt") or "").strip()
    pages: list[dict[str, Any]] = []

    symbol_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exit_reasons: Counter[str] = Counter()
    for trade in trades:
        symbol_groups[str(trade.get("symbol") or "UNKNOWN")].append(trade)
        exit_reasons[str(trade.get("exit_reason") or "unknown")] += 1

    for symbol, rows in list(symbol_groups.items())[:5]:
        total_pnl = sum(float(row.get("realized_pnl") or 0) for row in rows)
        directions = Counter(str(row.get("direction") or "unknown") for row in rows)
        pages.append(
            _write_page(
                room="trading",
                kind="entities",
                slug=_slug(symbol),
                title=symbol,
                source_system="olympus",
                summary=(
                    f"{symbol} appears {len(rows)} times in recent Olympus trades with a combined realized PnL of "
                    f"{_format_currency(total_pnl)}."
                ),
                bullets=[
                    f"Recent trades: {len(rows)}",
                    f"Realized PnL: {_format_currency(total_pnl)}",
                    f"Direction mix: {', '.join(f'{direction} {count}' for direction, count in directions.items())}",
                ],
                references=[f"Olympus recent trades for {symbol}"],
                related=["[[trading/syntheses/recent-trading-patterns]]"],
            )
        )

    pages.append(
        _write_page(
            room="trading",
            kind="concepts",
            slug="trade-performance",
            title="Trade Performance",
            source_system="olympus",
            summary=(
                f"Olympus reports {performance.get('total_trades', 0)} trades, total PnL "
                f"{_format_currency(performance.get('total_pnl', 0))}, and average R "
                f"{float(performance.get('avg_r_multiple', 0) or 0):.2f}."
            ),
            bullets=[
                f"Total trades: {performance.get('total_trades', 0)}",
                f"Average PnL per trade: {_format_currency(performance.get('avg_pnl', 0))}",
                f"Average R multiple: {float(performance.get('avg_r_multiple', 0) or 0):.2f}",
            ],
            references=["Olympus performance snapshot"],
            related=["[[trading/syntheses/recent-trading-patterns]]"],
        )
    )

    top_exits = ", ".join(f"{reason} ({count})" for reason, count in exit_reasons.most_common(3)) or "no recent exits recorded"
    pages.append(
        _write_page(
            room="trading",
            kind="syntheses",
            slug="recent-trading-patterns",
            title="Recent Trading Patterns",
            source_system="olympus",
            summary=(
                f"Pantheon sees recent trading concentrated around {', '.join(symbol_groups.keys()) or 'no symbols'} "
                f"with the latest ranking cycle at {_parse_timestamp(cycle.get('cycle_timestamp'))}."
            ),
            bullets=[
                f"Common exit reasons: {top_exits}",
                f"Latest scored universe count: {cycle.get('scored_count', 0)}",
                f"Recent report excerpt: {report_excerpt[:180] or 'No report excerpt available.'}",
            ],
            references=[
                "Olympus recent trades",
                "Olympus latest cycle snapshot",
                "Olympus report excerpt",
            ],
            related=[f"[[trading/entities/{_slug(symbol)}]]" for symbol in list(symbol_groups.keys())[:3]],
        )
    )
    return pages


def compile_maridian_pages() -> list[dict[str, Any]]:
    snapshot = maridian.get_snapshot()
    themes = snapshot.get("top_themes") or []
    questions = snapshot.get("today_questions") or []
    index_excerpt = str(snapshot.get("index_excerpt") or "").strip()
    pages: list[dict[str, Any]] = []

    for theme in themes[:5]:
        title = str(theme.get("title") or "Untitled Theme")
        pages.append(
            _write_page(
                room="self",
                kind="entities",
                slug=_slug(title),
                title=title,
                source_system="maridian",
                summary=(theme.get("preview") or "Pantheon mirrored this reflective theme from Maridian.").strip(),
                bullets=[
                    f"Last updated: {_parse_timestamp(theme.get('updated_at'))}",
                    f"Theme preview: {(theme.get('preview') or '')[:180]}",
                ],
                references=[f"Maridian wiki page: {theme.get('path', title)}"],
                related=["[[self/syntheses/self-model-state]]"],
            )
        )

    question_preview = "; ".join(item.get("question", "") for item in questions[:3]) or "No current adaptive questions."
    pages.append(
        _write_page(
            room="self",
            kind="concepts",
            slug="current-reflection-themes",
            title="Current Reflection Themes",
            source_system="maridian",
            summary=(
                f"Maridian currently surfaces {len(themes)} top themes and {len(questions)} active questions for reflection."
            ),
            bullets=[
                f"Cycle count: {snapshot.get('cycle_count', 0)}",
                f"Last cycle: {_parse_timestamp(snapshot.get('last_cycle'))}",
                f"Question preview: {question_preview}",
            ],
            references=[
                snapshot.get("today_question_file", "Maridian daily questions"),
                "Maridian wiki theme index",
            ],
            related=[f"[[self/entities/{_slug(str(theme.get('title') or 'theme'))}]]" for theme in themes[:3]],
        )
    )
    pages.append(
        _write_page(
            room="self",
            kind="syntheses",
            slug="self-model-state",
            title="Self Model State",
            source_system="maridian",
            summary=index_excerpt[:220] or "Pantheon did not receive a current Maridian index excerpt, so this self-state is sparse.",
            bullets=[
                f"Top themes: {', '.join(str(theme.get('title') or 'untitled') for theme in themes[:4]) or 'none'}",
                f"Adaptive questions today: {len(questions)}",
            ],
            references=["Maridian wiki INDEX", "Maridian question set"],
            related=["[[self/concepts/current-reflection-themes]]"],
        )
    )
    return pages


def compile_ops_pages() -> list[dict[str, Any]]:
    from pantheon.reasoning import PantheonReasoner
    from pantheon.services.shell import get_activity_feed

    activity = get_activity_feed(limit=8)
    doctor = PantheonReasoner().doctor()
    pages: list[dict[str, Any]] = []
    issues = []
    for name, payload in doctor.get("subsystems", {}).items():
        if not payload.get("connected"):
            issues.append(f"{name} offline: {payload.get('reason', 'unknown reason')}")
    pages.append(
        _write_page(
            room="ops",
            kind="syntheses",
            slug="system-health",
            title="System Health",
            source_system="pantheon",
            summary=(
                "Pantheon's operational picture combines doctor results, traces, and audit events into one durable ops memory page."
            ),
            bullets=[
                f"Current provider: {doctor.get('current_provider', 'unknown')}",
                f"Recent traces: {len(doctor.get('recent_traces', []))}",
                f"Recent audit events: {len(activity.get('audit', []))}",
                *(issues or ["No subsystem failures reported in the latest doctor snapshot."]),
            ],
            references=["Pantheon doctor snapshot", "Pantheon audit log", "Pantheon request traces"],
            related=["[[ops/heartbeats]]"],
        )
    )
    return pages


def _load_catalog() -> list[dict[str, Any]]:
    return _load_json(CATALOG_PATH, [])


def _write_catalog(entries: list[dict[str, Any]]) -> None:
    _write_json(CATALOG_PATH, entries)


def get_compile_status() -> dict[str, Any]:
    ensure_structure()
    saved = _load_json(
        STATUS_PATH,
        {
            "status": "idle",
            "last_run_at": None,
            "last_weekly_run_at": None,
            "last_heartbeat_at": None,
            "last_trigger": "",
            "last_mode": "incremental",
            "pages_written": 0,
            "room_counts": {},
            "subsystem_errors": {},
            "error": "",
        },
    )
    with _job_lock:
        live = dict(_job_state)
    saved["current_job"] = live
    return saved


def _save_compile_status(status: dict[str, Any]) -> None:
    _write_json(STATUS_PATH, status)


def _heartbeat_path(timestamp: datetime | None = None) -> Path:
    stamp = (timestamp or datetime.now()).strftime("%Y-%m-%d")
    return HEARTBEATS_DIR / f"{stamp}.md"


def write_heartbeat(compiled_entries: list[dict[str, Any]], trigger: str = "manual") -> dict[str, Any]:
    from pantheon.reasoning import PantheonReasoner
    from pantheon.services.shell import get_activity_feed

    doctor = PantheonReasoner().doctor()
    activity = get_activity_feed(limit=10)
    bb = blackbook.get_snapshot()
    mer = maridian.get_snapshot()
    oly = olympus.get_snapshot()

    failures = []
    recoveries = []
    for name, payload in doctor.get("subsystems", {}).items():
        if payload.get("connected"):
            recoveries.append(f"{name} healthy")
        else:
            failures.append(f"{name} issue: {payload.get('reason', 'unknown')}")

    lines = [
        f"# Pantheon Heartbeat - {datetime.now().strftime('%B %d, %Y')}",
        "",
        (
            f"{datetime.now().strftime('%B %d, %Y')}. I refreshed {len(compiled_entries)} compiled pages across finance, "
            f"trading, self, and ops after a {trigger} compile pass."
        ),
        "",
        "## Narrative",
        (
            f"I handled {len(activity.get('traces', []))} recent traced requests, saw {len(activity.get('audit', []))} recent audit events, "
            f"and my current reasoning provider is {doctor.get('current_provider', 'unknown')}."
        ),
        (
            f"BlackBook reports net worth {_format_currency(bb.get('net_worth', 0))}. "
            f"Maridian is {'locked' if mer.get('locked') else 'idle'} at cycle {mer.get('cycle_count', 0)}. "
            f"Olympus reports {_format_currency((oly.get('performance') or {}).get('total_pnl', 0))} total PnL."
        ),
        "",
        "## Signals",
    ]
    for bullet in failures or ["No subsystem failures reported in the latest pass."]:
        lines.append(f"- {bullet}")
    for bullet in recoveries[:4]:
        lines.append(f"- Recovery / healthy signal: {bullet}")
    lines.append(f"- New compiled pages this pass: {len(compiled_entries)}")
    lines.append(
        "- Notable activity: "
        + (
            activity["audit"][0]["action"] if activity.get("audit") else "No recent audit actions."
        )
    )

    path = _heartbeat_path()
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return {
        "title": f"Heartbeat {_parse_timestamp(datetime.now().isoformat())}",
        "path": str(path),
        "updated_at": datetime.now().isoformat(),
        "excerpt": " ".join(lines[3:8])[:420],
    }


def get_latest_heartbeat() -> dict[str, Any]:
    ensure_structure()
    files = sorted(HEARTBEATS_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not files:
        return {
            "title": "No heartbeat yet",
            "path": "",
            "updated_at": None,
            "content": "",
            "excerpt": "Pantheon has not written a heartbeat yet.",
        }
    path = files[0]
    content = path.read_text(encoding="utf-8")
    return {
        "title": path.stem,
        "path": str(path),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        "content": content,
        "excerpt": " ".join(content.split())[:420],
    }


def get_heartbeat_history(limit: int = 12) -> list[dict[str, Any]]:
    ensure_structure()
    items = []
    for path in sorted(HEARTBEATS_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        content = path.read_text(encoding="utf-8")
        items.append(
            {
                "title": path.stem,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "excerpt": " ".join(content.split())[:320],
            }
        )
    return items


def get_rooms_summary() -> dict[str, Any]:
    catalog = _load_catalog()
    room_map: dict[str, dict[str, Any]] = {
        room: {"room": room, "count": 0, "latest_updated_at": None, "latest_pages": []} for room in ROOMS
    }
    for entry in catalog:
        room = entry.get("room")
        if room not in room_map:
            continue
        room_map[room]["count"] += 1
        latest = room_map[room]["latest_updated_at"]
        if not latest or str(entry.get("updated_at", "")) > str(latest):
            room_map[room]["latest_updated_at"] = entry.get("updated_at")
        room_map[room]["latest_pages"].append(entry)

    for room in room_map.values():
        room["latest_pages"] = sorted(
            room["latest_pages"],
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )[:4]
    return {
        "rooms": list(room_map.values()),
        "latest_heartbeat": get_latest_heartbeat(),
    }


def get_room_snapshot(room: str) -> dict[str, Any]:
    room = room.lower()
    catalog = [entry for entry in _load_catalog() if entry.get("room") == room]
    return {
        "room": room,
        "pages": sorted(catalog, key=lambda item: item.get("updated_at") or "", reverse=True),
        "heartbeats": get_heartbeat_history(limit=8) if room == "ops" else [],
    }


def search_compiled_memory(query: str, room: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    room = room or _classify_room(query)
    query_tokens = _tokenize(query)
    catalog = _load_catalog()
    candidates = []
    for entry in catalog:
        if room and entry.get("room") != room:
            continue
        haystack = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("summary", "")),
                " ".join(entry.get("references", []) or []),
                " ".join(entry.get("related", []) or []),
            ]
        )
        tokens = _tokenize(haystack)
        overlap = len(query_tokens & tokens)
        if overlap == 0:
            continue
        score = overlap * 10
        if entry.get("kind") == "syntheses":
            score += 3
        if room and entry.get("room") == room:
            score += 2
        candidate = dict(entry)
        candidate["score"] = score
        candidates.append(candidate)

    if room == "ops" or any(token in query.lower() for token in ("when did", "failure", "offline", "error", "doctor", "heartbeat")):
        for item in get_heartbeat_history(limit=8):
            text = " ".join([item.get("title", ""), item.get("excerpt", "")])
            overlap = len(query_tokens & _tokenize(text))
            if overlap == 0:
                continue
            candidates.append(
                {
                    "title": item["title"],
                    "room": "ops",
                    "kind": "heartbeat",
                    "path": item["path"],
                    "summary": item["excerpt"],
                    "updated_at": item["updated_at"],
                    "source_system": "pantheon",
                    "score": overlap * 11,
                }
            )

    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)[:limit]


def _set_job_state(**updates) -> None:
    with _job_lock:
        _job_state.update(updates)


def _run_compile_worker(weekly: bool = False, trigger: str = "manual") -> None:
    ensure_structure()
    started_at = datetime.now().isoformat()
    _set_job_state(
        status="running",
        started_at=started_at,
        completed_at=None,
        mode="weekly" if weekly else "incremental",
        trigger=trigger,
        pages_written=0,
        error="",
        subsystem_errors={},
    )
    previous_catalog = _load_catalog()
    previous_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in previous_catalog:
        previous_by_system[str(entry.get("source_system") or "")].append(entry)

    compiled_entries: list[dict[str, Any]] = []
    subsystem_errors: dict[str, str] = {}
    for system_name, compiler in (
        ("blackbook", compile_blackbook_pages),
        ("olympus", compile_olympus_pages),
        ("maridian", compile_maridian_pages),
        ("pantheon", compile_ops_pages),
    ):
        try:
            compiled_entries.extend(compiler())
        except Exception as exc:
            subsystem_errors[system_name] = str(exc)
            compiled_entries.extend(previous_by_system.get(system_name, []))

    heartbeat = write_heartbeat(compiled_entries, trigger=trigger)
    _write_catalog(compiled_entries)
    room_counts = Counter(entry.get("room", "unknown") for entry in compiled_entries)
    status = {
        "status": "completed" if not subsystem_errors else "completed_with_errors",
        "last_run_at": datetime.now().isoformat(),
        "last_weekly_run_at": datetime.now().isoformat() if weekly else get_compile_status().get("last_weekly_run_at"),
        "last_heartbeat_at": heartbeat.get("updated_at"),
        "last_trigger": trigger,
        "last_mode": "weekly" if weekly else "incremental",
        "pages_written": len(compiled_entries),
        "room_counts": dict(room_counts),
        "subsystem_errors": subsystem_errors,
        "error": "",
    }
    _save_compile_status(status)
    _set_job_state(
        status=status["status"],
        completed_at=datetime.now().isoformat(),
        pages_written=len(compiled_entries),
        error="",
        subsystem_errors=subsystem_errors,
    )


def start_compile(weekly: bool = False, trigger: str = "manual") -> dict[str, Any]:
    current = get_compile_status().get("current_job", {})
    if current.get("status") == "running":
        return {"success": False, "error": "Pantheon compile is already running.", "status": current}
    _set_job_state(
        status="running",
        started_at=datetime.now().isoformat(),
        completed_at=None,
        mode="weekly" if weekly else "incremental",
        trigger=trigger,
        pages_written=0,
        error="",
        subsystem_errors={},
    )
    thread = threading.Thread(target=_run_compile_worker, kwargs={"weekly": weekly, "trigger": trigger}, daemon=True)
    thread.start()
    return {"success": True, "status": "started", "job": get_compile_status().get("current_job", {})}
