from connectors.black_book import (
    add_expense, add_income, get_spending_summary, get_account_balances
)
from connectors.meridian import (
    append_to_daily_note, search_vault, trigger_meridian_cycle, queue_meridian_prompt
)
from connectors.olympus import get_pnl_summary
from search.retriever import search_meridian, search_decisions
from core.memory import log_decision, get_approval_rule, set_approval_rule
from core.audit import log


def execute_function(function_name: str, arguments: dict) -> str:
    log(f"Executing: {function_name}", detail=str(arguments)[:100], system="EXECUTOR")

    if function_name == "add_expense":
        result = add_expense(
            amount=arguments["amount"],
            description=arguments["description"],
            category=arguments["category"],
            account=arguments["account"],
            date_str=arguments.get("date")
        )
        if result["success"]:
            return f"Recorded expense: ${arguments['amount']} for {arguments['description']} ({arguments['category']}) from {arguments['account']}."
        return f"Failed to record expense: {result.get('error')}"

    elif function_name == "add_income":
        result = add_income(
            amount=arguments["amount"],
            description=arguments["description"],
            account=arguments["account"],
            date_str=arguments.get("date")
        )
        return f"Recorded income: ${arguments['amount']} — {arguments['description']}." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "log_journal_entry":
        result = append_to_daily_note(arguments["content"])
        return "Journal entry written." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "log_decision":
        log_decision(
            decision=arguments["decision"],
            reasoning=arguments.get("reasoning"),
            domain=arguments.get("domain", "general")
        )
        content = f"**Decision:** {arguments['decision']}\n**Reasoning:** {arguments.get('reasoning', 'Not provided')}"
        append_to_daily_note(content)
        return f"Decision logged: {arguments['decision']}"

    elif function_name == "get_spending_summary":
        result = get_spending_summary(arguments.get("period", "month"))
        return f"Spending summary: {result['data']}" if result["success"] else f"Could not get summary: {result.get('error')}"

    elif function_name == "get_account_balances":
        result = get_account_balances()
        return f"Account balances: {result['data']}" if result["success"] else f"Could not get balances: {result.get('error')}"

    elif function_name == "search_meridian":
        results = search_meridian(query=arguments["query"], n_results=arguments.get("n_results", 5))
        if not results:
            return f"No results found for: {arguments['query']}"
        return "Found {} relevant notes:\n{}".format(
            len(results),
            "\n".join([f"[{r['source']}]: {r['content'][:200]}..." for r in results])
        )

    elif function_name == "get_olympus_status":
        result = get_pnl_summary()
        if result["success"]:
            s = result["summary"]
            stale = " (WARNING: data is stale)" if s.get("is_stale") else ""
            positions = ", ".join([p.get("symbol", "?") for p in s.get("open_positions", [])]) or "None"
            alerts = "; ".join(s.get("alerts", [])) or "None"
            return (f"Olympus status{stale}:\nDaily PnL: {s['daily_pnl']}\n"
                    f"Total PnL: {s['total_pnl']}\nPositions ({s['position_count']}): {positions}\n"
                    f"Alerts: {alerts}")
        return f"Could not read Olympus: {result.get('error')}"

    elif function_name == "trigger_meridian_cycle":
        result = trigger_meridian_cycle()
        return f"Meridian cycle triggered.\n{result.get('output', '')[:300]}" if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "queue_meridian_prompt":
        result = queue_meridian_prompt(arguments["prompt"])
        return "Prompt queued for tomorrow's Meridian cycle." if result["success"] else f"Failed: {result.get('error')}"

    elif function_name == "get_morning_briefing":
        olympus = execute_function("get_olympus_status", {})
        spending = execute_function("get_spending_summary", {"period": "week"})
        return f"OLYMPUS:\n{olympus}\n\nTHIS WEEK'S SPENDING:\n{spending}"

    elif function_name == "search_past_decisions":
        results = search_decisions(arguments["query"])
        if not results:
            return f"No relevant past decisions for: {arguments['query']}"
        return "Relevant past decisions:\n" + "\n".join([
            f"[{r['timestamp'][:10]}] {r['content'][:200]}..." for r in results
        ])

    elif function_name == "set_approval_rule":
        set_approval_rule(arguments["action_type"], arguments["scope"])
        scope_label = "permanently" if arguments["scope"] == "permanent" else "for this session"
        return f"Got it — I'll skip asking for {arguments['action_type']} {scope_label}."

    return f"Unknown function: {function_name}"
