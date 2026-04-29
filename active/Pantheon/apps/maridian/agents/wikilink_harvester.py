# agents/wikilink_harvester.py
"""
Finds orphan [[wikilinks]] in the vault — concepts referenced but never developed —
and seeds them as new notes.
"""
import re
from pathlib import Path
from utils.llm import llm_call
from utils.vault import (VAULT_ROOT, generate_id, default_frontmatter,
                          write_note, canonicalize_domain, get_all_notes)
from utils.embeddings import embed_text, is_duplicate, load_cache, save_cache, get_dedup_threshold
from utils.registry import NoteRegistry

SEEDER_SYSTEM = """You are Meridian's Wikilink Harvester. You receive a concept that appeared in a belief note
as a [[wikilink]] — meaning it was referenced but never developed.

Write a 2-3 sentence seed note about this concept.

Rules:
- First person. As Ignacio — direct, honest, no hedging
- This is a seed — early, incomplete, but pointing toward something real
- Do NOT invent personal details
- Output ONLY the seed text. No YAML, no headers."""


def extract_wikilinks(body: str) -> list:
    return re.findall(r'\[\[(.+?)\]\]', body)


def get_existing_titles(registry: NoteRegistry) -> set:
    titles = set()
    for note in registry.get_all():
        t = note["frontmatter"].get("title", "")
        if t:
            titles.add(t.lower().strip())
    return titles


def harvest_orphan_wikilinks(registry: NoteRegistry, top_n: int = 3) -> list:
    print("[WIKILINK HARVESTER] Scanning for orphan concepts...")
    all_notes = registry.get_all()
    existing_titles = get_existing_titles(registry)

    # Count wikilink frequency
    link_counts: dict = {}
    link_sources: dict = {}
    for note in all_notes:
        for link in extract_wikilinks(note["body"]):
            lk = link.lower().strip()
            link_counts[lk] = link_counts.get(lk, 0) + 1
            link_sources.setdefault(lk, []).append(note["frontmatter"].get("domains", []))

    # Find orphans (linked but no note exists)
    orphans = [(lk, cnt) for lk, cnt in link_counts.items()
               if lk not in existing_titles]
    orphans.sort(key=lambda x: x[1], reverse=True)
    orphans = orphans[:top_n]

    if not orphans:
        print("  No orphan wikilinks found.")
        return []

    print(f"  {len(orphans)} orphan concepts to seed: {[o[0] for o in orphans]}")

    cache = load_cache()
    threshold = get_dedup_threshold(registry.count)
    written = []

    for concept, count in orphans:
        try:
            seed_text = llm_call(
                "llama3.2", SEEDER_SYSTEM,
                f"Concept to seed: {concept}\nAppeared {count} time(s) in other notes.",
                temperature=0.8
            )
            seed_text = seed_text.strip()
            if len(seed_text) < 20:
                continue

            emb = embed_text(seed_text)
            if emb is None:
                continue
            if is_duplicate(emb, cache, threshold):
                continue

            # Infer domain from concept name
            domain = canonicalize_domain(concept.split()[0] if concept else "identity")

            note_id = generate_id("wiki")
            fm = {
                **default_frontmatter(note_id, generation=1, domains=[domain]),
                "title": concept[:60],
            }
            path = write_note(fm, seed_text, "seed", f"{note_id}.md", staging=True)
            cache[note_id] = emb
            written.append(path)
            print(f"  Seeded: [[{concept}]]")

        except Exception as e:
            print(f"  Failed to seed '{concept}': {e}")

    save_cache(cache)
    print(f"[WIKILINK HARVESTER] Done. {len(written)} orphan concepts seeded.")
    return written
