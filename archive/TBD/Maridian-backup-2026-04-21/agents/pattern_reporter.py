# agents/pattern_reporter.py
"""
Monthly pattern report. Triggers on cycle_count % 30 == 0.
Analyzes domain distribution, question loops, and evolution events.
"""
from datetime import date
from utils.llm import llm_call
from utils.vault import VAULT_ROOT
from utils.embeddings import load_cache
from utils.registry import NoteRegistry
from db.neon_bridge import push_insight

PATTERNS_DIR = VAULT_ROOT / "Patterns"

REPORTER_SYS = """You are writing Meridian's monthly pattern report for Ignacio.
This is an intelligence briefing, not therapy. Precise, specific, useful.

STRICT OUTPUT TEMPLATE:

# Meridian Pattern Report — {month} {year}

## Frequency Patterns
[Topics appearing in ≥ 20% of notes this period. For each: topic, count, what's notable.]

## Question Loops
[Beliefs or questions appearing repeatedly without resolution. What's the repeating pattern?]

## Growth Signals
[Domains where the notes have grown in depth over time. What changed?]

## Silence Zones
[Active domains with almost no notes. What's conspicuously absent?]

## What Meridian Is Currently Building
[The 2-3 most promising framework candidates and what they need to become complete.]

Rules:
- Every finding must be specific — cite note titles or domains
- No interpretation beyond what the data shows
- 2-3 pages maximum
- Tone: a sharp, honest observer reading your journals"""


def maybe_report(vault_state: dict, registry: NoteRegistry) -> bool:
    cycle = vault_state.get("cycle_count", 0)
    if cycle == 0 or cycle % 30 != 0:
        return False

    print("[PATTERN] Generating monthly pattern report...")
    PATTERNS_DIR.mkdir(exist_ok=True)

    notes = registry.get_all()
    domain_dist = vault_state.get("domain_distribution", {})
    active_domains = vault_state.get("active_domains", [])

    # Build summary for the LLM
    top_domains = sorted(domain_dist.items(), key=lambda x: x[1], reverse=True)[:10]
    silence_zones = [d for d in active_domains if domain_dist.get(d, 0) < 0.02]
    framework_eligible = registry.get_framework_eligible()

    eligible_summaries = [
        f"{n['frontmatter'].get('title', '?')} (fitness: {n['frontmatter'].get('fitness', 0)})"
        for n in framework_eligible[:5]
    ]

    today = date.today()
    report = llm_call(
        "llama3.2", REPORTER_SYS.format(month=today.strftime("%B"), year=today.year),
        f"Domain distribution (top 10): {top_domains}\n"
        f"Silence zones (< 2% coverage): {silence_zones}\n"
        f"Total notes: {len(notes)}\n"
        f"Framework candidates: {eligible_summaries}\n"
        f"Avg fitness: {vault_state.get('avg_fitness', 0)}\n"
        f"Cycles run: {cycle}",
        temperature=0.7
    )

    filename = f"pattern_report_{today.strftime('%Y_%m')}.md"
    (PATTERNS_DIR / filename).write_text(report, encoding="utf-8")

    push_insight("pattern_report", report, str(today))
    vault_state["last_pattern_report"] = str(today)

    print(f"[PATTERN] Report written: {filename} and pushed to Neon.")
    return True
