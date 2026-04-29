"""
Scoring and normalization for Olympus ranking engine.
Pure functions — no I/O, no side effects.
Takes raw BarFeatures across the full universe and normalizes scores
so they are comparable across symbols.
"""

from __future__ import annotations

from core.models import BarFeatures

_LONG_THRESHOLD = 60.0
_SHORT_THRESHOLD = 40.0
_MAX_CANDIDATES = 20


def normalize_scores(features: list[BarFeatures]) -> list[BarFeatures]:
    """
    Compute normalized_score for each BarFeatures using min-max normalization.

    normalized_score = (raw_score - min_score) / (max_score - min_score) * 100

    If all raw_scores are identical, set all normalized_scores to 50.0.
    Mutates normalized_score in place and returns the same list.
    """
    if not features:
        return features

    raw_scores = [f.raw_score for f in features]
    min_score = min(raw_scores)
    max_score = max(raw_scores)

    if min_score == max_score:
        for f in features:
            f.normalized_score = 50.0
    else:
        score_range = max_score - min_score
        for f in features:
            f.normalized_score = (f.raw_score - min_score) / score_range * 100.0

    return features


def classify_direction(
    features: list[BarFeatures],
) -> tuple[list[BarFeatures], list[BarFeatures]]:
    """
    Split normalized features into long and short candidates.

    Long candidates:  normalized_score >= 60.0
    Short candidates: normalized_score <= 40.0
    Neutral (40 < score < 60): excluded from both lists.

    Returns:
        (longs, shorts)
        - longs: sorted descending by score (strongest first), capped at 20
        - shorts: sorted ascending by score (weakest first), capped at 20
    """
    longs = [f for f in features if f.normalized_score >= _LONG_THRESHOLD]
    shorts = [f for f in features if f.normalized_score <= _SHORT_THRESHOLD]

    longs.sort(key=lambda f: f.normalized_score, reverse=True)
    shorts.sort(key=lambda f: f.normalized_score)  # ascending = weakest score first

    return longs[:_MAX_CANDIDATES], shorts[:_MAX_CANDIDATES]
