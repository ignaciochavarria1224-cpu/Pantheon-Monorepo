from __future__ import annotations

from core.audit import get_recent_entries
from core.memory import get_active_patterns, get_decisions, get_pending_queue, get_recent_conversations
from core.mind import get_vault_snapshot
from pantheon.services import blackbook, maridian, olympus


def get_activity_feed(limit: int = 10) -> dict:
    try:
        conversations = get_recent_conversations(limit=limit)
    except Exception:
        conversations = []
    try:
        decisions = get_decisions(limit=limit)
    except Exception:
        decisions = []
    try:
        patterns = get_active_patterns()[:limit]
    except Exception:
        patterns = []
    try:
        queue = get_pending_queue()[:limit]
    except Exception:
        queue = []
    return {
        "audit": get_recent_entries(limit=limit),
        "conversations": conversations,
        "decisions": decisions,
        "patterns": patterns,
        "queue": queue,
    }


def get_overview() -> dict:
    bb = blackbook.get_snapshot()
    mer = maridian.get_snapshot()
    oly = olympus.get_snapshot()
    activity = get_activity_feed(limit=6)
    vault = get_vault_snapshot()

    latest_signal = "No recent system activity."
    if activity["audit"]:
        top = activity["audit"][0]
        latest_signal = f"{top['system'] or 'SYSTEM'}: {top['action']}"
    elif activity["patterns"]:
        latest_signal = activity["patterns"][0]["description"]

    return {
        "health": {
            "pantheon": "online",
            "blackbook": "online" if bb.get("connected") else "offline",
            "maridian": "online" if mer.get("connected") else "offline",
            "olympus": "online" if oly.get("connected") else "offline",
        },
        "latest_signal": latest_signal,
        "vault": vault,
        "blackbook": {
            "net_worth": bb.get("net_worth"),
            "total_assets": bb.get("total_assets"),
            "total_debt": bb.get("total_debt"),
        },
        "maridian": {
            "cycle_count": mer.get("cycle_count"),
            "locked": mer.get("locked"),
            "question_count": len(mer.get("today_questions", [])),
            "last_cycle": mer.get("last_cycle"),
        },
        "olympus": {
            "total_trades": (oly.get("performance") or {}).get("total_trades", 0),
            "total_pnl": (oly.get("performance") or {}).get("total_pnl", 0),
            "last_trade_at": (oly.get("performance") or {}).get("last_trade_at"),
            "latest_cycle_at": (oly.get("latest_cycle") or {}).get("cycle_timestamp"),
        },
        "activity": activity,
    }
