"""
Phase 2 tests — ranking engine and cycle runner.
Run with: pytest tests/phase2/test_engine.py -v -m "not integration"
All tests here are pure unit tests — network calls are fully mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Add olympus root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models import RankedUniverse, BarFeatures
from core.ranking.engine import RankingEngine
from core.ranking.cycle import RankingCycle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_settings():
    s = MagicMock()
    s.BAR_TIMEFRAME = "5Min"
    s.RANKING_INTERVAL_MINUTES = 20
    return s


def _make_failing_fetcher():
    """DataFetcher that raises on every call."""
    fetcher = MagicMock()
    fetcher.fetch_historical_bars.side_effect = RuntimeError("Simulated API failure")
    return fetcher


def _make_empty_fetcher():
    """DataFetcher that returns an empty DataFrame."""
    import pandas as pd
    fetcher = MagicMock()
    fetcher.fetch_historical_bars.return_value = pd.DataFrame()
    return fetcher


def _make_empty_cache():
    """DataCache that always misses."""
    cache = MagicMock()
    cache.get.return_value = None
    return cache


def _make_mock_universe(symbols=None):
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOGL"]
    universe = MagicMock()
    universe.get_all_symbols.return_value = symbols
    return universe


def _make_engine(fetcher=None, cache=None, universe=None):
    settings = _make_mock_settings()
    fetcher = fetcher or _make_empty_fetcher()
    cache = cache or _make_empty_cache()
    universe = universe or _make_mock_universe()
    return RankingEngine(settings, fetcher, cache, universe)


# ---------------------------------------------------------------------------
# RankingEngine.run_cycle() failure-safety tests
# ---------------------------------------------------------------------------

class TestRankingEngineFailureSafety:

    def test_run_cycle_never_raises_when_fetcher_fails(self):
        """run_cycle() must not raise even when every symbol fetch throws."""
        engine = _make_engine(fetcher=_make_failing_fetcher())
        # Must not raise
        result = engine.run_cycle()
        assert result is not None

    def test_run_cycle_returns_ranked_universe_when_fetcher_fails(self):
        engine = _make_engine(fetcher=_make_failing_fetcher())
        result = engine.run_cycle()
        assert isinstance(result, RankedUniverse)

    def test_run_cycle_returns_empty_longs_and_shorts_when_no_data(self):
        """With no data available, longs and shorts must be empty lists."""
        engine = _make_engine(fetcher=_make_empty_fetcher())
        result = engine.run_cycle()
        assert result.longs == []
        assert result.shorts == []

    def test_run_cycle_returns_valid_ranked_universe_when_no_data(self):
        """All required fields must be present even in the empty case."""
        engine = _make_engine(fetcher=_make_empty_fetcher())
        result = engine.run_cycle()
        assert isinstance(result.cycle_id, str)
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.universe_size, int)
        assert isinstance(result.scored_count, int)
        assert isinstance(result.error_count, int)
        assert isinstance(result.duration_seconds, float)

    def test_run_cycle_never_raises_when_universe_raises(self):
        """Even if get_all_symbols() raises, run_cycle must not propagate it."""
        settings = _make_mock_settings()
        fetcher = _make_empty_fetcher()
        cache = _make_empty_cache()
        universe = MagicMock()
        universe.get_all_symbols.side_effect = RuntimeError("Universe exploded")

        engine = RankingEngine(settings, fetcher, cache, universe)
        result = engine.run_cycle()
        assert isinstance(result, RankedUniverse)

    def test_run_cycle_cycle_id_is_uuid_string(self):
        import uuid
        engine = _make_engine()
        result = engine.run_cycle()
        # Should be parseable as a UUID
        parsed = uuid.UUID(result.cycle_id)
        assert str(parsed) == result.cycle_id

    def test_run_cycle_duration_is_positive(self):
        engine = _make_engine()
        result = engine.run_cycle()
        assert result.duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# cycle_id uniqueness
# ---------------------------------------------------------------------------

class TestCycleIdUniqueness:

    def test_cycle_id_unique_across_two_runs(self):
        engine = _make_engine(fetcher=_make_empty_fetcher())
        result1 = engine.run_cycle()
        result2 = engine.run_cycle()
        assert result1.cycle_id != result2.cycle_id

    def test_cycle_id_unique_across_many_runs(self):
        engine = _make_engine(fetcher=_make_empty_fetcher())
        ids = {engine.run_cycle().cycle_id for _ in range(5)}
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# RankingCycle state tests (no scheduler started)
# ---------------------------------------------------------------------------

class TestRankingCycleState:

    def _make_cycle(self):
        """Create a RankingCycle without calling start()."""
        settings = _make_mock_settings()
        engine = MagicMock()
        # Patch out the rankings dir creation so tests don't touch the filesystem
        with patch("core.ranking.cycle._RANKINGS_DIR") as mock_dir:
            mock_dir.mkdir.return_value = None
            cycle = RankingCycle(engine, settings)
        return cycle

    def test_get_latest_returns_none_before_first_cycle(self):
        settings = _make_mock_settings()
        engine = MagicMock()
        with patch.object(
            Path, "mkdir", return_value=None
        ):
            cycle = RankingCycle(engine, settings)
        assert cycle.get_latest() is None

    def test_get_top_longs_returns_empty_before_first_cycle(self):
        settings = _make_mock_settings()
        engine = MagicMock()
        with patch.object(Path, "mkdir", return_value=None):
            cycle = RankingCycle(engine, settings)
        assert cycle.get_top_longs() == []

    def test_get_top_shorts_returns_empty_before_first_cycle(self):
        settings = _make_mock_settings()
        engine = MagicMock()
        with patch.object(Path, "mkdir", return_value=None):
            cycle = RankingCycle(engine, settings)
        assert cycle.get_top_shorts() == []

    def test_get_top_longs_respects_n_parameter(self, tmp_path):
        """After a cycle, get_top_longs(n) returns at most n items."""
        from core.models import RankedSymbol

        def _make_ranked_symbol(rank, score):
            f = BarFeatures(
                symbol=f"SYM{rank}",
                timestamp=datetime.now(timezone.utc),
                close=100.0, volume=1000.0,
                roc_5=1.0, roc_10=1.0, roc_20=1.0, acceleration=0.0,
                rvol=1.0, vwap_deviation=0.0, range_position=0.5,
                raw_score=score, normalized_score=score,
            )
            return RankedSymbol(
                symbol=f"SYM{rank}", score=score, direction="long",
                rank=rank, features=f, timestamp=datetime.now(timezone.utc),
            )

        universe = RankedUniverse(
            cycle_id="test-id",
            timestamp=datetime.now(timezone.utc),
            longs=[_make_ranked_symbol(i + 1, 90.0 - i) for i in range(15)],
            shorts=[],
            universe_size=15,
            scored_count=15,
            error_count=0,
            duration_seconds=1.0,
        )

        settings = _make_mock_settings()
        engine = MagicMock()
        engine.run_cycle.return_value = universe

        (tmp_path / "rankings").mkdir()
        with patch("core.ranking.cycle._RANKINGS_DIR", tmp_path / "rankings"):
            cycle = RankingCycle(engine, settings)
            cycle._run_cycle()

        assert len(cycle.get_top_longs(n=5)) == 5
        assert len(cycle.get_top_longs(n=15)) == 15
        assert len(cycle.get_top_longs(n=20)) == 15  # only 15 available
