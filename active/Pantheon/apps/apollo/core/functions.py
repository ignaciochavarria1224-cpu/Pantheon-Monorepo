APOLLO_TOOLS = [
    {
        "name": "add_expense",
        "description": "Record a new expense in Black Book. Use when the user mentions spending money, buying something, or paying for something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "description": {"type": "string"},
                "category": {"type": "string", "description": "Food, Health, Transport, Entertainment, Shopping, Bills, Other"},
                "account": {"type": "string", "description": "checking, savings, credit card, cash"},
                "date": {"type": "string", "description": "YYYY-MM-DD. Omit for today."}
            },
            "required": ["amount", "description", "category", "account"]
        }
    },
    {
        "name": "add_income",
        "description": "Record income in Black Book.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "description": {"type": "string"},
                "account": {"type": "string"},
                "date": {"type": "string"}
            },
            "required": ["amount", "description", "account"]
        }
    },
    {
        "name": "log_journal_entry",
        "description": "Write a journal entry to today's Meridian daily note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "log_decision",
        "description": "Record a decision with reasoning. Use when user says they decided something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string"},
                "reasoning": {"type": "string"},
                "domain": {"type": "string", "description": "finance, trading, personal, career, health, other"}
            },
            "required": ["decision"]
        }
    },
    {
        "name": "get_spending_summary",
        "description": "Get a spending summary from Black Book.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "week, month, or year"}
            },
            "required": ["period"]
        }
    },
    {
        "name": "get_account_balances",
        "description": "Get current account balances from Black Book.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_meridian",
        "description": "Search the Meridian vault for journal entries, notes, or any content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_results": {"type": "integer"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_olympus_status",
        "description": "Get Olympus/Apex trading status including PnL, positions, and alerts.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "trigger_meridian_cycle",
        "description": "Run the Meridian question generation cycle.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_morning_briefing",
        "description": "Get a full morning briefing combining all system statuses.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "search_past_decisions",
        "description": "Search through past decisions for relevant context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "queue_meridian_prompt",
        "description": "Add a reflection prompt to tomorrow's Meridian journal cycle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The question or reflection prompt to add"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "set_approval_rule",
        "description": "Remember that the user has approved an action type. Use when user says 'always allow' or 'just this once'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "description": "The function name being approved"},
                "scope": {"type": "string", "description": "'permanent' for 'always allow', 'session' for 'just this once'"}
            },
            "required": ["action_type", "scope"]
        }
    }
]
