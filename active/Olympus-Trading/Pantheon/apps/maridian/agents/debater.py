# agents/debater.py
from pathlib import Path
from datetime import date
from utils.llm import llm_call
from utils.vault import update_frontmatter, VAULT_ROOT
from utils.registry import NoteRegistry

DEBATES_DIR = VAULT_ROOT / "Debates"
FLAGGED_FILE = DEBATES_DIR / "flagged.md"

ADVOCATE_SYS = """You are Ignacio defending a belief he currently holds (2025-2026).
Argue for this position as the person who wrote these journals recently.
Draw on real patterns from your life. 250-350 words. First person. Honest."""

SKEPTIC_SYS = """You are Ignacio in 2022 — younger, less certain, still figuring things out.
Challenge this belief using the uncertainty you had back then.
Not aggressive — genuinely uncertain and questioning. 250-350 words. First person."""

SYNTHESIZER_SYS = """You are Meridian's Synthesizer reviewing how a person's belief has developed.
The same person has argued both sides across time.

Determine:
- Has this belief genuinely evolved (strengthened and clarified over time)?
- Is this still an active unresolved contradiction worth questioning further?
- Has the belief apparently reversed entirely?

Write 2-3 paragraphs of synthesis.

End with EXACTLY one of:
VERDICT: EVOLVED — belief has genuinely strengthened
VERDICT: UNRESOLVED — active contradiction, generate as journal question tomorrow
VERDICT: FLAG — belief appears to have reversed, needs conscious review

Output ONLY synthesis + verdict."""


def debate(registry: NoteRegistry, max_debates: int = 5) -> list:
    print("[DEBATER] Finding belief candidates...")
    eligible = [
        n for n in registry.get_all(exclude_flagged=True)
        if n["frontmatter"].get("maturity", 0) >= 60
        and n["frontmatter"].get("debate_count", 0) < 3
    ]
    eligible.sort(key=lambda n: n["frontmatter"].get("fitness") or 0, reverse=True)
    candidates = eligible[:max_debates]
    print(f"  {len(candidates)} candidates.")

    unresolved = []
    flagged = []

    for note in candidates:
        note_id = note["frontmatter"].get("id", "unknown")
        title = note["frontmatter"].get("title", note_id)
        print(f"  Examining: {title}")

        try:
            body = note["body"][:2500]
            advocate = llm_call("llama3.2", ADVOCATE_SYS,
                                f"Belief to defend:\n{body}", temperature=0.75)
            skeptic = llm_call("llama3.2", SKEPTIC_SYS,
                               f"Belief:\n{body}\n\nCurrent defense:\n{advocate}",
                               temperature=0.75)
            synthesis = llm_call("llama3.2", SYNTHESIZER_SYS,
                                 f"Belief:\n{body}\nNow:\n{advocate}\nThen:\n{skeptic}",
                                 temperature=0.70)

            debate_n = note["frontmatter"].get("debate_count", 0) + 1
            transcript = (
                f"# Examination: {title} (Round {debate_n})\n"
                f"Date: {date.today()}\n\n"
                f"## Current Self\n{advocate}\n\n"
                f"## Earlier Self\n{skeptic}\n\n"
                f"## Synthesis\n{synthesis}\n"
            )
            (DEBATES_DIR / f"{note_id}_debate_{debate_n}.md").write_text(
                transcript, encoding="utf-8"
            )

            is_unresolved = "VERDICT: UNRESOLVED" in synthesis
            is_flagged = "VERDICT: FLAG" in synthesis

            update_frontmatter(note["path"], {
                "debate_count": debate_n,
                "flagged_for_pruning": is_flagged,
            })

            if is_unresolved:
                unresolved.append({
                    "note_id": note_id,
                    "title": title,
                    "synthesis": synthesis,
                    "body": body[:300],
                })
                print(f"    → UNRESOLVED: will become journal question.")
            if is_flagged:
                flagged.append(note_id)
                fitness = note["frontmatter"].get("fitness", 0)
                with open(FLAGGED_FILE, "a", encoding="utf-8") as f:
                    f.write(f"| {note_id} | {title} | {fitness} | {date.today()} | Reversed |\n")
                print(f"    → FLAGGED for review.")

        except Exception as e:
            print(f"  Debate failed for {note_id}: {e}")

    print(f"[DEBATER] Done. {len(unresolved)} unresolved, {len(flagged)} flagged.")
    return unresolved
