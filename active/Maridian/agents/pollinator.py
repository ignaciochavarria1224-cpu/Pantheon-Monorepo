# agents/pollinator.py
"""
Finds semantically related note pairs and produces hybrid notes that neither contained alone.
In Meridian: forces two beliefs from different contexts to speak to each other.
"""
import re
from pathlib import Path
from utils.llm import llm_call
from utils.vault import (generate_id, default_frontmatter, write_note,
                          get_stage, canonicalize_domain, VAULT_ROOT)
from utils.embeddings import (load_cache, save_cache, embed_text,
                               cosine_similarity, get_dedup_threshold, is_duplicate)
from utils.registry import NoteRegistry

POLLINATOR_SYSTEM = """You are Meridian's Pollinator. You receive two related belief notes.
Force them to speak to each other and produce a hybrid note that neither contained alone.

Output format (EXACT — do not deviate):
LINKS_NOTE_A: [[concept1]], [[concept2]], [[concept3]]
LINKS_NOTE_B: [[concept1]], [[concept2]], [[concept3]]
HYBRID_NOTE:
[First-person Markdown body, 400-800 words. Voice: Ignacio at full potential. Direct. Certain.]"""


def extract_links_and_hybrid(raw: str) -> tuple:
    links_a, links_b, hybrid = [], [], ""
    lines = raw.split("\n")
    hybrid_lines = []
    in_hybrid = False
    for line in lines:
        if line.startswith("LINKS_NOTE_A:"):
            links_a = re.findall(r'\[\[(.+?)\]\]', line)
        elif line.startswith("LINKS_NOTE_B:"):
            links_b = re.findall(r'\[\[(.+?)\]\]', line)
        elif line.startswith("HYBRID_NOTE:"):
            in_hybrid = True
        elif in_hybrid:
            hybrid_lines.append(line)
    hybrid = "\n".join(hybrid_lines).strip()
    return links_a, links_b, hybrid


def select_pollination_pairs(registry: NoteRegistry, cache: dict, n: int = 5) -> list:
    eligible = [note for note in registry.get_all(exclude_flagged=True)
                if (note["frontmatter"].get("fitness") or 0) >= 35
                and note["frontmatter"].get("id") in cache]

    if len(eligible) < 2:
        return []

    pairs = []
    used = set()

    for i, a in enumerate(eligible):
        a_id = a["frontmatter"].get("id", "")
        if a_id in used or len(pairs) >= n:
            break
        for b in eligible[i + 1:]:
            b_id = b["frontmatter"].get("id", "")
            if b_id in used:
                continue

            a_emb, b_emb = cache.get(a_id), cache.get(b_id)
            if not a_emb or not b_emb:
                continue
            sim = cosine_similarity(a_emb, b_emb)

            # Sweet spot: related but distinct
            if not (0.35 <= sim <= 0.68):
                continue

            # Prefer different domains
            a_doms = {canonicalize_domain(d) for d in a["frontmatter"].get("domains", [])}
            b_doms = {canonicalize_domain(d) for d in b["frontmatter"].get("domains", [])}
            if len(a_doms & b_doms) >= 2:
                continue

            pairs.append((a, b))
            used.add(a_id)
            used.add(b_id)
            break

    return pairs


def pollinate(registry: NoteRegistry, n: int = 5) -> list:
    print("[POLLINATOR] Finding belief pairs to cross-pollinate...")
    cache = load_cache()
    pairs = select_pollination_pairs(registry, cache, n)
    print(f"  {len(pairs)} pairs found.")

    if not pairs:
        return []

    threshold = get_dedup_threshold(registry.count)
    written = []

    for i, (note_a, note_b) in enumerate(pairs):
        print(f"  Pollinating pair {i + 1}/{len(pairs)}...")
        try:
            raw = llm_call(
                "llama3.2", POLLINATOR_SYSTEM,
                f"Note A:\n{note_a['body'][:2000]}\n\nNote B:\n{note_b['body'][:2000]}",
                temperature=0.85
            )

            links_a, links_b, hybrid = extract_links_and_hybrid(raw)
            if len(hybrid) < 100:
                print(f"  Pair {i + 1}: hybrid too short, skipping.")
                continue

            emb = embed_text(hybrid[:512])
            if emb is None or is_duplicate(emb, cache, threshold):
                continue

            # Merge domains
            a_doms = [canonicalize_domain(d) for d in note_a["frontmatter"].get("domains", [])]
            b_doms = [canonicalize_domain(d) for d in note_b["frontmatter"].get("domains", [])]
            combined = list(set(a_doms + b_doms))

            # Merge source entries and date ranges
            a_entries = note_a["frontmatter"].get("source_entry_ids", [])
            b_entries = note_b["frontmatter"].get("source_entry_ids", [])
            merged_entries = list(set(a_entries + b_entries))

            maturity = max(
                note_a["frontmatter"].get("maturity", 0),
                note_b["frontmatter"].get("maturity", 0)
            ) + 5

            hybrid_id = generate_id("pollen")
            fm = {
                **default_frontmatter(
                    hybrid_id,
                    generation=max(
                        note_a["frontmatter"].get("generation", 1),
                        note_b["frontmatter"].get("generation", 1)
                    ) + 1,
                    domains=combined,
                    parent_ids=[note_a["frontmatter"].get("id", ""),
                                note_b["frontmatter"].get("id", "")],
                    source_entry_ids=merged_entries,
                ),
                "title": hybrid.split("\n")[0].replace("#", "").strip()[:60],
                "maturity": min(99, maturity),
            }

            stage = get_stage(fm["maturity"])
            path = write_note(fm, hybrid, stage, f"{hybrid_id}.md", staging=True)
            cache[hybrid_id] = emb
            written.append(path)

        except Exception as e:
            print(f"  Pair {i + 1} failed: {e}")

    save_cache(cache)
    print(f"[POLLINATOR] Done. {len(written)} hybrids written.")
    return written
