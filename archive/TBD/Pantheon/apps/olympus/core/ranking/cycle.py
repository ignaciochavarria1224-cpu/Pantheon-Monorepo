"""
Ranking cycle runner for Olympus.
Wires RankingEngine to the Phase 1 Scheduler.
Provides thread-safe access to the most recent RankedUniverse so that
Phase 3 can read it at any time without triggering a new cycle.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from core.logger import get_logger
from core.models import RankedSymbol, RankedUniverse
from core.scheduler import Scheduler

if TYPE_CHECKING:
    from core.ranking.engine import RankingEngine
    from config.settings import Settings

logger = get_logger(__name__)

_MAX_RANKING_FILES = 100

# Rankings directory relative to the olympus package root
# cycle.py lives at olympus/core/ranking/cycle.py → 3 parents up = olympus/
_OLYMPUS_ROOT = Path(__file__).resolve().parent.parent.parent
_RANKINGS_DIR = _OLYMPUS_ROOT / "data" / "rankings"


class RankingCycle:
    """
    Manages the recurring ranking cycle.

    On start(), runs one cycle immediately (synchronously) so that Phase 3
    always has a valid RankedUniverse available as soon as it starts.
    Subsequent cycles run on the configured RANKING_INTERVAL_MINUTES schedule.

    Thread-safety: get_latest(), get_top_longs(), get_top_shorts() are safe
    to call from any thread.
    """

    def __init__(self, engine, settings) -> None:
        self._engine = engine
        self._settings = settings
        self._latest: Optional[RankedUniverse] = None
        self._lock = threading.Lock()

        _RANKINGS_DIR.mkdir(parents=True, exist_ok=True)

        self._scheduler = Scheduler(
            fn=self._run_cycle,
            interval_minutes=settings.RANKING_INTERVAL_MINUTES,
            name="ranking",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Run one cycle immediately (blocking), then start the scheduler
        for subsequent cycles on the configured interval.
        """
        logger.info("RankingCycle.start() — running initial cycle synchronously")
        self._run_cycle()
        self._scheduler.start()

    def stop(self) -> None:
        """Stop the background scheduler."""
        self._scheduler.stop()

    def get_latest(self) -> Optional[RankedUniverse]:
        """
        Thread-safe read of the most recently completed RankedUniverse.
        Returns None if no cycle has completed yet.
        """
        with self._lock:
            return self._latest

    def get_top_longs(self, n: int = 10) -> list[RankedSymbol]:
        """
        Returns top n long candidates from the latest cycle.
        Returns empty list if no cycle has completed.
        """
        with self._lock:
            if self._latest is None:
                return []
            return self._latest.longs[:n]

    def get_top_shorts(self, n: int = 10) -> list[RankedSymbol]:
        """
        Returns top n short candidates from the latest cycle.
        Returns empty list if no cycle has completed.
        """
        with self._lock:
            if self._latest is None:
                return []
            return self._latest.shorts[:n]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_cycle(self) -> None:
        """Run one ranking cycle, update state, and persist the result."""
        result = self._engine.run_cycle()

        with self._lock:
            self._latest = result

        self._persist(result)

    def _persist(self, universe: RankedUniverse) -> None:
        """Write RankedUniverse to JSON and prune old files."""
        try:
            filename = _RANKINGS_DIR / f"ranking_{universe.cycle_id}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(universe.to_dict(), f, indent=2)
            logger.debug("Persisted ranking cycle %s → %s", universe.cycle_id[:8], filename.name)
            self._prune_old_files()
        except Exception as exc:
            logger.warning("Failed to persist ranking cycle %s: %s", universe.cycle_id[:8], exc)

    def _prune_old_files(self) -> None:
        """Keep only the most recent _MAX_RANKING_FILES ranking JSON files."""
        try:
            files = sorted(
                _RANKINGS_DIR.glob("ranking_*.json"),
                key=lambda p: p.stat().st_mtime,
            )
            excess = len(files) - _MAX_RANKING_FILES
            if excess > 0:
                for f in files[:excess]:
                    f.unlink(missing_ok=True)
                logger.debug("Pruned %d old ranking file(s)", excess)
        except Exception as exc:
            logger.warning("Failed to prune old ranking files: %s", exc)
