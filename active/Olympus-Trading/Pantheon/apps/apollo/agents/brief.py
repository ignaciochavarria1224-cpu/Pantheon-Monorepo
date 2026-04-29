"""
Daily Brief Agent — runs on a schedule, no user input required.
Compiles Olympus status, overnight spending, and open Meridian questions
into a single morning summary and delivers it via configured channels.
"""
import schedule
import time
from datetime import date, timedelta
from core.brain import chat
from core.audit import log
from config import BRIEF_DELIVERY_TIME

# Persistent history for the brief agent's own session
_brief_history = []

BRIEF_PROMPT = """Generate today's morning brief. Do the following:
1. Call get_olympus_status to check Apex and current positions.
2. Call get_spending_summary for the current week.
3. Call search_meridian with query "open questions unanswered" to find any pending items.

Then synthesize everything into a clean morning briefing. Format:
- One line on Olympus
- One line on spending
- Any open Meridian items
- Nothing else unless something is urgent or anomalous

Keep it under 100 words. Be direct."""

def run_brief(deliver_fn=None):
    """
    Run the morning brief and deliver it.
    deliver_fn: optional callable that receives the brief text (e.g. send_whatsapp).
    If None, it just logs the brief.
    """
    global _brief_history
    log("Starting daily brief", system="BRIEF")

    response, _brief_history = chat(BRIEF_PROMPT, _brief_history, channel="brief")
    _brief_history = []  # Reset after each brief — no carryover

    log(f"Brief generated: {response[:200]}", system="BRIEF")

    if deliver_fn:
        try:
            deliver_fn(response)
            log("Brief delivered", system="BRIEF")
        except Exception as e:
            log(f"Brief delivery failed: {e}", system="BRIEF")
    else:
        print(f"\n=== APOLLO MORNING BRIEF ===\n{response}\n")

    return response

def start_brief_scheduler(deliver_fn=None):
    """
    Start the daily brief scheduler.
    Call this from main.py in a background thread.
    """
    schedule.every().day.at(BRIEF_DELIVERY_TIME).do(run_brief, deliver_fn=deliver_fn)
    log(f"Brief scheduled for {BRIEF_DELIVERY_TIME} daily", system="BRIEF")

    while True:
        schedule.run_pending()
        time.sleep(60)
