"""
Timed operation scheduler for Olympus.
Runs a callable on a fixed interval, aligned to clean boundaries.
Runs in a background thread. No external dependencies — stdlib only.
"""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Callable, Optional

from core.logger import get_logger

logger = get_logger(__name__)


def _next_boundary_seconds(interval_minutes: int) -> float:
    """
    Return the number of seconds until the next clean interval boundary.
    E.g. for interval=20, boundaries are :00, :20, :40 each hour.
    """
    now = datetime.now(timezone.utc)
    total_seconds_in_day = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6
    interval_seconds = interval_minutes * 60
    elapsed_in_interval = total_seconds_in_day % interval_seconds
    remaining = interval_seconds - elapsed_in_interval
    # Avoid firing immediately if we're exactly on a boundary
    if remaining < 1.0:
        remaining += interval_seconds
    return remaining


class Scheduler:
    """
    Runs a callable on a fixed interval, aligned to clean clock boundaries.

    Usage:
        def my_task():
            ...

        s = Scheduler(my_task, interval_minutes=20)
        s.start()
        # ... later ...
        s.stop()

    The scheduler runs in a background daemon thread.
    Callable failures are logged with full traceback — the scheduler keeps running.
    """

    def __init__(
        self,
        fn: Callable[[], None],
        interval_minutes: int,
        name: str = "scheduler",
    ) -> None:
        self._fn = fn
        self._interval_minutes = interval_minutes
        self._name = name
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._tick_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("[%s] Scheduler already running — ignoring start()", self._name)
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"olympus-{self._name}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "[%s] Scheduler started (interval=%dmin)", self._name, self._interval_minutes
        )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Signal the scheduler to stop and wait for the background thread to exit.
        Returns after at most `timeout` seconds.
        """
        logger.info("[%s] Scheduler stop requested", self._name)
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("[%s] Scheduler thread did not stop within %.1fs", self._name, timeout)
            else:
                logger.info("[%s] Scheduler stopped cleanly", self._name)
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def tick_count(self) -> int:
        """Return how many times the callable has been invoked."""
        return self._tick_count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        # Wait until the next clean boundary before first execution
        wait_secs = _next_boundary_seconds(self._interval_minutes)
        logger.info(
            "[%s] First tick in %.1fs (aligning to %dmin boundary)",
            self._name, wait_secs, self._interval_minutes,
        )

        # Sleep in small increments so stop() is responsive
        self._interruptible_sleep(wait_secs)
        if self._stop_event.is_set():
            return

        # Execute and then repeat every interval_minutes
        interval_secs = self._interval_minutes * 60
        while not self._stop_event.is_set():
            self._execute_once()
            # Sleep for the interval, waking every second to check stop
            self._interruptible_sleep(interval_secs)

    def _execute_once(self) -> None:
        self._tick_count += 1
        tick = self._tick_count
        start_ts = datetime.now(timezone.utc)
        logger.info("[%s] Tick #%d starting at %s", self._name, tick, start_ts.isoformat())

        t0 = time.monotonic()
        try:
            self._fn()
            duration = time.monotonic() - t0
            logger.info(
                "[%s] Tick #%d completed in %.3fs", self._name, tick, duration
            )
        except Exception:
            duration = time.monotonic() - t0
            logger.error(
                "[%s] Tick #%d FAILED after %.3fs:\n%s",
                self._name, tick, duration, traceback.format_exc(),
            )
            # Continue — do not crash the scheduler

    def _interruptible_sleep(self, total_seconds: float) -> None:
        """Sleep for total_seconds, but wake every second to check stop_event."""
        deadline = time.monotonic() + total_seconds
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(1.0, remaining))
