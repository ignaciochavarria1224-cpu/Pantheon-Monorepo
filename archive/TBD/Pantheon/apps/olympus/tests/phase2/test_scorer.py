"""
Phase 2 tests — scoring and normalization.
Run with: pytest tests/phase2/test_scorer.py -v -m "not integration"
All tests here are pure unit tests requiring no network or filesystem access.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

# Add olympus root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import BarFeatures
from core.ranking.scorer import normalize_scores, classify_direction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(raw_score: float, symbol: str = "TEST") -> BarFeatures:
    """Create a minimal BarFeatures with a specific raw_score."""
    return BarFeatures(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        close=100.0,
        volume=1000.0,
        roc_5=0.0,
        roc_10=0.0,
        roc_20=raw_score,  # doesn't matter — raw_score is what counts
        acceleration=0.0,
        rvol=1.0,
        vwap_deviation=0.0,
        range_position=0.5,
        raw_score=raw_score,
        normalized_score=0.0,
    )


# ---------------------------------------------------------------------------
# normalize_scores tests
# ---------------------------------------------------------------------------

class TestNormalizeScores:

    def test_min_is_0_max_is_100(self):
        features = [_make_feature(raw) for raw in [-10.0, 0.0, 5.0, 20.0]]
        result = normalize_scores(features)
        scores = [f.normalized_score for f in result]
        assert min(scores) == pytest.approx(0.0, abs=1e-9)
        assert max(scores) == pytest.approx(100.0, abs=1e-9)

    def test_all_50_when_identical_raw_scores(self):
        features = [_make_feature(7.5) for _ in range(5)]
        result = normalize_scores(features)
        for f in result:
            assert f.normalized_score == 50.0

    def test_single_feature_is_50(self):
        features = [_make_feature(3.14)]
        result = normalize_scores(features)
        assert result[0].normalized_score == 50.0

    def test_empty_list_returns_empty(self):
        result = normalize_scores([])
        assert result == []

    def test_normalization_is_monotonic(self):
        """Higher raw_score → higher normalized_score."""
        features = [_make_feature(raw) for raw in [1.0, 2.0, 5.0, 10.0]]
        normalize_scores(features)
        scores = [f.normalized_score for f in features]
        assert scores == sorted(scores)

    def test_intermediate_score_is_correctly_proportioned(self):
        """With raw scores [0, 50, 100] → normalized [0, 50, 100]."""
        features = [_make_feature(raw) for raw in [0.0, 50.0, 100.0]]
        normalize_scores(features)
        assert pytest.approx(features[0].normalized_score, abs=1e-9) == 0.0
        assert pytest.approx(features[1].normalized_score, abs=1e-9) == 50.0
        assert pytest.approx(features[2].normalized_score, abs=1e-9) == 100.0

    def test_only_normalized_score_is_modified(self):
        """normalize_scores must not touch any field other than normalized_score."""
        f = _make_feature(raw_score=5.0)
        original_raw = f.raw_score
        original_roc5 = f.roc_5
        normalize_scores([f])
        assert f.raw_score == original_raw
        assert f.roc_5 == original_roc5


# ---------------------------------------------------------------------------
# classify_direction tests
# ---------------------------------------------------------------------------

class TestClassifyDirection:

    def _normalized_feature(self, score: float, symbol: str = "TEST") -> BarFeatures:
        f = _make_feature(0.0, symbol=symbol)
        f.normalized_score = score
        return f

    def test_long_threshold_is_60(self):
        """Score >= 60 is long."""
        f_below = self._normalized_feature(59.9)
        f_at = self._normalized_feature(60.0)
        f_above = self._normalized_feature(75.0)
        longs, _ = classify_direction([f_below, f_at, f_above])
        symbols = [f.symbol for f in longs]
        assert f_at in longs
        assert f_above in longs
        assert f_below not in longs

    def test_short_threshold_is_40(self):
        """Score <= 40 is short."""
        f_above = self._normalized_feature(40.1)
        f_at = self._normalized_feature(40.0)
        f_below = self._normalized_feature(25.0)
        _, shorts = classify_direction([f_above, f_at, f_below])
        assert f_at in shorts
        assert f_below in shorts
        assert f_above not in shorts

    def test_neutral_excluded_from_both(self):
        """Scores between 40 and 60 (exclusive) appear in neither list."""
        neutrals = [self._normalized_feature(s) for s in [41.0, 50.0, 59.9]]
        longs, shorts = classify_direction(neutrals)
        assert longs == []
        assert shorts == []

    def test_longs_sorted_descending(self):
        """Longs must be ordered strongest-first."""
        features = [self._normalized_feature(s) for s in [65.0, 90.0, 75.0, 80.0]]
        longs, _ = classify_direction(features)
        scores = [f.normalized_score for f in longs]
        assert scores == sorted(scores, reverse=True)

    def test_shorts_sorted_ascending(self):
        """Shorts must be ordered weakest-first (lowest score first)."""
        features = [self._normalized_feature(s) for s in [20.0, 5.0, 35.0, 10.0]]
        _, shorts = classify_direction(features)
        scores = [f.normalized_score for f in shorts]
        assert scores == sorted(scores)

    def test_longs_capped_at_20(self):
        features = [self._normalized_feature(70.0 + i * 0.1, symbol=f"SYM{i}") for i in range(25)]
        longs, _ = classify_direction(features)
        assert len(longs) <= 20

    def test_shorts_capped_at_20(self):
        features = [self._normalized_feature(10.0 + i * 0.1, symbol=f"SYM{i}") for i in range(25)]
        _, shorts = classify_direction(features)
        assert len(shorts) <= 20

    def test_capped_longs_are_highest_scoring(self):
        """When more than 20 longs exist, the top 20 by score are returned."""
        raw_scores = [60.0 + i for i in range(25)]  # 60, 61, ..., 84
        features = [self._normalized_feature(s, symbol=f"SYM{i}") for i, s in enumerate(raw_scores)]
        longs, _ = classify_direction(features)
        assert len(longs) == 20
        min_returned = min(f.normalized_score for f in longs)
        assert min_returned >= 65.0  # bottom 5 (60-64) should be cut

    def test_empty_input_returns_empty_lists(self):
        longs, shorts = classify_direction([])
        assert longs == []
        assert shorts == []
