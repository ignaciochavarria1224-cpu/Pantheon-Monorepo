"""
Phase 1 tests — Scheduler.
Run with: pytest tests/phase1/test_scheduler.py -v
All tests are unit tests — no network required.
"""

from __future__ import annotations

import sys
import time
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestScheduler:

    def test_scheduler_starts_and_stops(self):
        from core.scheduler import Scheduler
        calls = []

        def fn():
            calls.append(1)

        sched = Scheduler(fn, interval_minutes=1, name="test-start-stop")
        sched.start()
        assert sched.is_running()
        sched.stop(timeout=3.0)
        assert not sched.is_running()

    def test_scheduler_callable_is_invoked(self):
        """Verify the callable can be invoked via tick_count tracking."""
        from core.scheduler import Scheduler
        calls = []

        def fn():
            calls.append(time.monotonic())

        sched = Scheduler(fn, interval_minutes=1, name="test-invoke")
        sched.start()

        # Directly trigger the internal _execute_once for test speed
        sched._execute_once()
        sched._execute_once()
        sched._execute_once()

        sched.stop(timeout=2.0)
        assert sched.tick_count() >= 3

    def test_scheduler_continues_after_callable_failure(self):
        """Scheduler must not crash if the callable raises."""
        from core.scheduler import Scheduler

        call_count = [0]
        raise_on = {1}  # raise on first call only

        def fn():
            call_count[0] += 1
            if call_count[0] in raise_on:
                raise RuntimeError("Intentional test failure")

        sched = Scheduler(fn, interval_minutes=1, name="test-failure")
        sched.start()

        sched._execute_once()  # will raise internally, should be caught
        sched._execute_once()  # should succeed

        sched.stop(timeout=2.0)
        assert call_count[0] == 2  # both calls happened

    def test_scheduler_is_not_running_after_stop(self):
        from core.scheduler import Scheduler
        sched = Scheduler(lambda: None, interval_minutes=1, name="test-stopped")
        sched.start()
        sched.stop(timeout=3.0)
        assert not sched.is_running()

    def test_scheduler_runs_in_background_thread(self):
        from core.scheduler import Scheduler

        sched = Scheduler(lambda: None, interval_minutes=1, name="test-thread")
        sched.start()
        # The background thread should be named "olympus-test-thread"
        assert sched._thread is not None
        assert "olympus-test-thread" in sched._thread.name
        sched.stop(timeout=2.0)

    def test_scheduler_double_start_is_noop(self):
        from core.scheduler import Scheduler
        sched = Scheduler(lambda: None, interval_minutes=1, name="test-double-start")
        sched.start()
        thread_before = sched._thread
        sched.start()  # should be a no-op
        thread_after = sched._thread
        assert thread_before is thread_after
        sched.stop(timeout=2.0)

    def test_next_boundary_seconds_is_positive(self):
        from core.scheduler import _next_boundary_seconds
        for interval in [1, 5, 10, 20, 30, 60]:
            wait = _next_boundary_seconds(interval)
            assert wait > 0, f"Expected positive wait for interval={interval}"
            assert wait <= interval * 60, f"Wait too long for interval={interval}"
