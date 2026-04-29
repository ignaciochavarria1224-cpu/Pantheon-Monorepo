# utils/embeddings.py
import json
import math
from pathlib import Path

CACHE_FILE = Path(__file__).parent.parent / "vault_embeddings.json"

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list | None:
    try:
        model = _get_model()
        vec = model.encode(text[:512], normalize_embeddings=True)
        return vec.tolist()
    except Exception as e:
        print(f"  [EMB] Embedding failed: {e}")
        return None


def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def is_duplicate(emb: list, cache: dict, threshold: float) -> bool:
    for existing_emb in cache.values():
        if isinstance(existing_emb, list) and cosine_similarity(emb, existing_emb) >= threshold:
            return True
    return False


def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")


def get_dedup_threshold(note_count: int) -> float:
    if note_count < 50:
        return 0.75
    if note_count < 200:
        return 0.85
    return 0.90


def update_cache_for_notes(notes: list, cache: dict) -> dict:
    """Embed any notes not yet in cache."""
    for note in notes:
        nid = note["frontmatter"].get("id")
        if nid and nid not in cache:
            emb = embed_text(note["body"][:512])
            if emb:
                cache[nid] = emb
    return cache
