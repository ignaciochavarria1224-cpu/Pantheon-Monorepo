# agents/fitness_scorer.py
import json
from datetime import datetime
from utils.llm import llm_call
from utils.vault import update_frontmatter, count_wikilinks, get_stage
from utils.embeddings import (load_cache, save_cache, update_cache_for_notes)
from utils.registry import NoteRegistry

SCORER_SYS = """You are Meridian's Fitness Scorer. Score this personal belief note.

Pre-computed (use exactly as given):
- personal_relevance: {relevance} (journal entries contributing, 0-100)
- temporal_span: {span} (years of history contributing, 0-100)

Score these 3 dimensions (0-100 each):
- depth: How fully developed is this belief? Could it stand alone as a conviction?
  (0=fragment, 50=sketch, 100=fully articulated)
- coherence: Does the note hold together internally without contradiction?
  (0=self-contradictory, 100=airtight)
- surprise: How unexpected is this synthesis? Would the person be surprised they believe this?
  (0=obvious, 100=they probably didn't consciously know)

Output ONLY valid JSON. No preamble. No fences:
{{"depth": X, "coherence": X, "surprise": X}}"""


def compute_personal_relevance(source_entry_ids: list) -> float:
    return min(100.0, len(source_entry_ids) * 10)


def compute_temporal_span(entry_date_range: str) -> float:
    if not entry_date_range or " to " not in entry_date_range:
        return 0.0
    try:
        parts = entry_date_range.split(" to ")

        def parse_partial(s):
            s = s.strip()
            if len(s) == 7:
                return datetime.strptime(s, "%Y-%m")
            return datetime.strptime(s[:10], "%Y-%m-%d")

        start = parse_partial(parts[0])
        end = parse_partial(parts[1])
        span_days = (end - start).days
        return min(100.0, span_days / 365 * 100)
    except Exception:
        return 0.0


def score_all(registry: NoteRegistry) -> dict:
    print("[SCORER] Scoring all notes...")
    notes = registry.get_all()
    cache = load_cache()
    cache = update_cache_for_notes(notes, cache)
    save_cache(cache)

    results = {}
    eligible_count = 0

    for note in notes:
        note_id = note["frontmatter"].get("id")
        if not note_id:
            continue

        try:
            fm = note["frontmatter"]
            source_entries = fm.get("source_entry_ids", [])
            date_range = fm.get("entry_date_range", "")
            maturity = fm.get("maturity", 0)
            wikilinks = count_wikilinks(note["body"])
            stage = get_stage(maturity)

            relevance = compute_personal_relevance(source_entries)
            span = compute_temporal_span(date_range)

            raw = llm_call(
                "phi3",
                SCORER_SYS.format(relevance=relevance, span=round(span, 1)),
                f"Note (truncated):\n{note['body'][:1500]}\nStage: {stage}",
                temperature=0.3
            )

            raw_clean = raw.strip().replace("```json", "").replace("```", "").strip()
            try:
                scores = json.loads(raw_clean)
            except json.JSONDecodeError:
                print(f"  [SCORER] Malformed JSON for {note_id}. Skipping.")
                continue

            depth = float(scores.get("depth", 0))
            coherence = float(scores.get("coherence", 0))
            surprise = float(scores.get("surprise", 0))

            fitness = round(
                0.25 * depth + 0.25 * coherence +
                0.20 * relevance + 0.15 * span + 0.15 * surprise,
                1
            )

            framework_eligible = (
                maturity >= 60 and fitness >= 70 and
                wikilinks >= 1 and len(source_entries) >= 3 and
                not fm.get("published", False)
            )
            if framework_eligible:
                eligible_count += 1

            update_frontmatter(note["path"], {
                "fitness": fitness,
                "framework_eligible": framework_eligible,
                "wikilink_count": wikilinks,
            })
            results[note_id] = fitness

        except Exception as e:
            print(f"  Scoring error for {note_id}: {e}")

    print(f"[SCORER] Done. {len(results)} scored. {eligible_count} framework-eligible.")
    return results
