# agents/grower.py
import json
import random
from pathlib import Path
from datetime import date
from utils.llm import llm_call
from utils.vault import (generate_id, default_frontmatter, write_note,
                          get_stage, VAULT_ROOT, canonicalize_domain)
from utils.embeddings import (load_cache, save_cache, embed_text, cosine_similarity)
from utils.registry import NoteRegistry
from agents.dna_injector import inject

LINEAGE_FILE = VAULT_ROOT / "Fossils" / "lineage.md"
VOICE_PROFILE_FILE = VAULT_ROOT / "voice_profile.json"

GROWER_SYSTEM = """You are Meridian's Grower. You receive two notes from different periods of the same person's life.
Produce a child note that represents the evolution between them.

Voice directive: {voice_summary}
Write as Ignacio at full potential — the version who lived through both of these perspectives
and knows what he actually believes now. First person. Certain. Direct. No hedging.

Rules:
- Synthesize both into one evolved position
- Acknowledge the earlier perspective without dismissing it — show how it changed
- Minimum 600 words
- Invent at least 4 [[wikilink]] concepts this synthesis suggests (things to develop further)
- Sound like a person writing in their journal, not a philosopher
- Output ONLY the Markdown body. No YAML."""


def get_voice_summary() -> str:
    if VOICE_PROFILE_FILE.exists():
        profile = json.loads(VOICE_PROFILE_FILE.read_text())
        if profile.get("built"):
            phrases = profile.get("characteristic_phrases", [])[:5]
            concepts = profile.get("recurring_concepts", [])[:5]
            return f"Use phrases like: {phrases}. Recurring themes: {concepts}. First person, direct."
    return "First person. Direct. Honest. No hedging."


def get_entry_date(note: dict) -> str:
    date_range = note["frontmatter"].get("entry_date_range", "")
    if " to " in date_range:
        return date_range.split(" to ")[0]
    return date_range or ""


def select_cross_temporal_pairs(registry: NoteRegistry, cache: dict, n: int = 10) -> list:
    eligible = [n for n in registry.get_all(exclude_flagged=True)
                if (n["frontmatter"].get("fitness") or 0) >= 40
                and n["frontmatter"].get("maturity", 0) < 95
                and n["frontmatter"].get("id") in cache]

    if len(eligible) < 2:
        return []

    def growth_score(note):
        f = note["frontmatter"].get("fitness") or 0
        m = note["frontmatter"].get("maturity", 0)
        return f * (1 - m / 100)

    eligible.sort(key=growth_score, reverse=True)
    top = eligible[:min(40, len(eligible))]

    pairs = []
    used = set()

    for i, a in enumerate(top):
        a_id = a["frontmatter"].get("id", "")
        if a_id in used or len(pairs) >= n:
            break

        for b in top[i + 1:]:
            b_id = b["frontmatter"].get("id", "")
            if b_id in used:
                continue

            a_domains = {canonicalize_domain(d) for d in a["frontmatter"].get("domains", [])}
            b_domains = {canonicalize_domain(d) for d in b["frontmatter"].get("domains", [])}
            if len(a_domains & b_domains) >= 2:
                continue

            a_emb, b_emb = cache.get(a_id), cache.get(b_id)
            if a_emb and b_emb:
                sim = cosine_similarity(a_emb, b_emb)
                if not (0.25 <= sim <= 0.72):
                    continue

            a_date = get_entry_date(a)
            b_date = get_entry_date(b)
            cross_temporal = a_date[:4] != b_date[:4] if (a_date and b_date) else False

            pairs.append((a, b, cross_temporal))
            used.add(a_id)
            used.add(b_id)
            break

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def grow(vault_state: dict, registry: NoteRegistry, n_pairs: int = 10) -> list:
    print(f"[GROWER] Selecting parent pairs...")
    cache = load_cache()
    pairs = select_cross_temporal_pairs(registry, cache, n_pairs)
    print(f"  {len(pairs)} pairs selected ({sum(1 for _, _, ct in pairs if ct)} cross-temporal).")

    if not pairs:
        print("  Not enough eligible notes yet. Skipping grow phase.")
        return []

    voice_summary = get_voice_summary()
    force_dna = vault_state.get("stagnation_active", False)
    written = []

    for i, (parent_a, parent_b, is_cross_temporal) in enumerate(pairs):
        print(f"  Growing pair {i + 1}/{len(pairs)} (cross-temporal: {is_cross_temporal})...")
        try:
            a_date = get_entry_date(parent_a)
            b_date = get_entry_date(parent_b)
            if a_date > b_date:
                parent_a, parent_b = parent_b, parent_a
                a_date, b_date = b_date, a_date

            body = llm_call(
                "llama3.2",
                GROWER_SYSTEM.format(voice_summary=voice_summary),
                f"Earlier note ({a_date}):\n{parent_a['body'][:2500]}\n\n"
                f"Later note ({b_date}):\n{parent_b['body'][:2500]}",
                temperature=0.85
            )

            a_domains = parent_a["frontmatter"].get("domains", [])
            b_domains = parent_b["frontmatter"].get("domains", [])
            combined = list({canonicalize_domain(d) for d in a_domains + b_domains})

            inj_count = 0
            mutation, injected = inject(body, combined, force=force_dna, injection_count=0)
            if mutation:
                body += f"\n\n---\n*[Expanded through: {injected}]*\n\n{mutation}"
                combined.append(canonicalize_domain(injected))
                inj_count = 1

            a_mat = parent_a["frontmatter"].get("maturity", 0)
            b_mat = parent_b["frontmatter"].get("maturity", 0)
            child_maturity = min(99, max(a_mat, b_mat) + 10)

            a_entries = parent_a["frontmatter"].get("source_entry_ids", [])
            b_entries = parent_b["frontmatter"].get("source_entry_ids", [])
            merged_entries = list(set(a_entries + b_entries))

            all_dates = [d for d in [a_date, b_date] if d]
            date_range = (f"{min(all_dates)} to {max(all_dates)}"
                          if len(all_dates) >= 2 else (all_dates[0] if all_dates else ""))

            child_id = generate_id("child")
            child_fm = {
                **default_frontmatter(
                    child_id,
                    generation=max(
                        parent_a["frontmatter"].get("generation", 1),
                        parent_b["frontmatter"].get("generation", 1)
                    ) + 1,
                    domains=combined,
                    parent_ids=[parent_a["frontmatter"].get("id", ""),
                                parent_b["frontmatter"].get("id", "")],
                    source_entry_ids=merged_entries,
                    entry_date_range=date_range
                ),
                "title": body.split("\n")[0].replace("#", "").strip()[:60],
                "maturity": child_maturity,
                "dna_injected": bool(mutation),
                "dna_injection_count": inj_count,
            }

            stage = get_stage(child_maturity)
            path = write_note(child_fm, body, stage, f"{child_id}.md", staging=True)
            emb = embed_text(body[:1000])
            if emb:
                cache[child_id] = emb
            written.append(path)

        except Exception as e:
            print(f"  Pair {i + 1} failed: {e}")

    save_cache(cache)
    print(f"[GROWER] Done. {len(written)} children written.")
    return written
