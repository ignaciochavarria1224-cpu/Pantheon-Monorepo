"""
Cross-system trigger engine.
Evaluates conditions across Black Book and Olympus, then fires
actions in Meridian or notifies the user via Apollo.

Run on a schedule (every hour or every 15 minutes).
"""
from connectors.black_book import get_spending_summary, get_category_average
from connectors.olympus import get_drawdown_pct
from connectors.meridian import queue_meridian_prompt
from core.audit import log
from datetime import datetime

# --- Trigger Definitions ---
# Each trigger has: a condition function and an action function.
# Add new triggers here as you identify patterns you want Apollo to watch.

DRAWDOWN_THRESHOLD_PCT = 5.0   # Adjust to your Olympus risk tolerance
SPEND_MULTIPLIER_THRESHOLD = 2.0  # Fire if any category is 2x its weekly average

def check_olympus_drawdown():
    """Fire if Apex reports a drawdown above threshold."""
    drawdown = get_drawdown_pct()
    if drawdown is None:
        return
    if drawdown >= DRAWDOWN_THRESHOLD_PCT:
        prompt = (
            f"Olympus had a drawdown of {drawdown:.1f}% today. "
            f"How are you feeling about the strategy, and is anything worth adjusting?"
        )
        queue_meridian_prompt(prompt)
        log(f"Drawdown trigger fired: {drawdown:.1f}%", system="TRIGGERS")

def check_spending_anomalies():
    """Fire if any spending category is significantly above its average."""
    result = get_spending_summary(period="week")
    if not result["success"]:
        return
    for item in result["data"]:
        category = item.get("category")
        weekly_total = float(item.get("total", 0))
        avg_result = get_category_average(category)
        if not avg_result["success"]:
            continue
        avg = avg_result["avg_weekly"]
        if avg > 0 and weekly_total >= avg * SPEND_MULTIPLIER_THRESHOLD:
            prompt = (
                f"Your {category} spending this week (${weekly_total:.0f}) is "
                f"{weekly_total/avg:.1f}x your usual weekly average (${avg:.0f}). "
                f"Anything driving that?"
            )
            queue_meridian_prompt(prompt)
            log(f"Spending anomaly trigger: {category} at {weekly_total/avg:.1f}x average",
                system="TRIGGERS")

def run_all_triggers():
    """Evaluate all triggers. Call this on a schedule."""
    log(f"Evaluating triggers at {datetime.now().strftime('%H:%M')}", system="TRIGGERS")
    check_olympus_drawdown()
    check_spending_anomalies()
    log("Trigger evaluation complete", system="TRIGGERS")

if __name__ == "__main__":
    run_all_triggers()
