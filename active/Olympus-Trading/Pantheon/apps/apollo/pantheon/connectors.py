from core.memory import (
    get_active_patterns,
    get_approval_rule,
    get_decisions,
    get_recent_conversations,
    get_recent_traces,
    log_decision,
    set_approval_rule,
)
from pantheon.services import blackbook, maridian, olympus


class PantheonConnectors:
    def recent_memory(self, limit: int = 8) -> list[dict]:
        return get_recent_conversations(limit=limit)

    def recent_traces(self, limit: int = 12) -> list[dict]:
        return get_recent_traces(limit=limit)

    def decisions(self, limit: int = 8) -> list[dict]:
        return get_decisions(limit=limit)

    def patterns(self) -> list[dict]:
        return get_active_patterns()

    def spending_summary(self, period: str) -> dict:
        return {"success": True, "data": blackbook.get_spending_summary(period)}

    def account_balances(self) -> dict:
        return {"success": True, "data": blackbook.get_account_balances()}

    def recent_transactions(self, limit: int = 12) -> dict:
        return {"success": True, "data": blackbook.get_recent_transactions(limit=limit)}

    def blackbook_snapshot(self) -> dict:
        return blackbook.get_snapshot()

    def olympus_snapshot(self) -> dict:
        return olympus.get_snapshot()

    def olympus_status(self) -> dict:
        snapshot = olympus.get_snapshot()
        if not snapshot.get("connected"):
            return {"success": False, "error": "Olympus database/report artifacts are unavailable."}

        performance = snapshot.get("performance") or {}
        cycle = snapshot.get("latest_cycle") or {}
        summary = {
            "daily_pnl": performance.get("avg_pnl", 0),
            "total_pnl": performance.get("total_pnl", 0),
            "open_positions": [],
            "position_count": 0,
            "alerts": [event.get("description") for event in snapshot.get("recent_events", [])[:3]],
            "last_updated": cycle.get("cycle_timestamp") or snapshot.get("report_updated_at"),
            "is_stale": not bool(snapshot.get("db_updated_at")),
            "total_trades": performance.get("total_trades", 0),
        }
        return {"success": True, "summary": summary, "snapshot": snapshot}

    def maridian_snapshot(self) -> dict:
        return maridian.get_snapshot()

    def search_meridian(self, query: str, n_results: int = 5) -> list[dict]:
        from search.retriever import search_meridian

        return search_meridian(query, n_results=n_results)

    def search_decisions(self, query: str, n_results: int = 5) -> list[dict]:
        from search.retriever import search_decisions

        return search_decisions(query, n_results=n_results)

    def write_journal(self, content: str) -> dict:
        from connectors.meridian import append_to_daily_note

        return append_to_daily_note(content)

    def queue_prompt(self, prompt: str) -> dict:
        from connectors.meridian import queue_meridian_prompt

        return queue_meridian_prompt(prompt)

    def run_meridian_cycle(self) -> dict:
        return maridian.run_cycle()

    def record_decision(self, decision: str, reasoning: str | None, domain: str | None) -> None:
        log_decision(decision=decision, reasoning=reasoning, domain=domain or "general")

    def record_expense(self, amount: float, description: str, category: str, account: str, date_str: str | None) -> dict:
        return blackbook.add_expense(amount, description, category, account, date_str)

    def record_income(self, amount: float, description: str, account: str, date_str: str | None) -> dict:
        return blackbook.add_income(amount, description, account, date_str)

    def approval_rule(self, action_type: str) -> dict | None:
        return get_approval_rule(action_type)

    def save_approval_rule(self, action_type: str, scope: str) -> None:
        set_approval_rule(action_type, scope)
