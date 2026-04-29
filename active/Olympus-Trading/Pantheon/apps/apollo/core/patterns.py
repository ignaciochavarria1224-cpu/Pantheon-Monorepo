from connectors.black_book import get_spending_summary
from core.memory import save_pattern
from core.audit import log
from pantheon.runtime import LocalModelRuntime


def analyze_spending_patterns():
    summary = get_spending_summary("month")
    if not summary["success"]:
        return
    user_prompt = (
        f"Analyze this spending data and identify 2-3 clear behavioral patterns. "
        f"Be specific. Each pattern should be actionable.\n"
        f"Data: {summary['data']}\n"
        f"Format each as:\n"
        f"PATTERN: [description]\n"
        f"CONFIDENCE: [0.0-1.0]\n"
        f"DATA_POINTS: [number]"
    )
    runtime = LocalModelRuntime()
    text = runtime.generate(
        system_prompt="You are a personal finance analyst. Respond only with the requested format.",
        user_prompt=user_prompt,
    )
    if not text:
        return
    for line in text.split("\n"):
        if line.startswith("PATTERN:"):
            description = line.replace("PATTERN:", "").strip()
            save_pattern("spending", description, 0.7, 30)
            log(f"Detected spending pattern: {description[:80]}", system="PATTERNS")


def run_pattern_detection():
    log("Starting pattern detection cycle", system="PATTERNS")
    analyze_spending_patterns()
    log("Pattern detection complete", system="PATTERNS")


if __name__ == "__main__":
    run_pattern_detection()
