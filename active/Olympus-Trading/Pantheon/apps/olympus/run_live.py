"""
run_live.py — Olympus continuous paper-trading runtime.

This is the always-on process that runs Olympus during market hours.
It is NOT the gate-check script (that is main.py).

Usage:
    cd olympus
    python run_live.py

What it does:
    1. Loads settings and initializes the SQLite database
    2. Ingests any existing JSON trade/ranking files into the DB (idempotent)
    3. Wires up all components: AlpacaClient, DataFetcher, RankingEngine,
       RankingCycle, ExecutionEngine, PositionManager, MemoryWriter
    4. Starts MemoryAwarePaperTradingLoop (not plain PaperTradingLoop)
    5. Starts the RankingCycle background scheduler
    6. Runs a lightweight heartbeat on the main thread every 5 minutes
    7. Shuts down cleanly on Ctrl+C

Never-raise contracts are preserved end-to-end:
    - RankingEngine.run_cycle() never raises
    - PaperTradingLoop._run_cycle() never raises
    - MemoryWriter methods never raise
    - This file's outer loop catches any unexpected exception, logs it, and continues
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Bootstrap: ensure the olympus root is on sys.path regardless of CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.logger import get_logger, init_logging

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL_SECONDS = 300   # Log a status line every 5 minutes
_STARTUP_RETRY_SLEEP_SECONDS = 30   # If startup fails, wait before re-raising

# PID lockfile lives next to this script — one file, one process.
_PID_FILE = Path(__file__).resolve().parent / "olympus.pid"


# ---------------------------------------------------------------------------
# Instance guard
# ---------------------------------------------------------------------------

def _acquire_pid_lock() -> None:
    """
    Write our PID to olympus.pid.  If the file already exists and the recorded
    PID is still alive, abort with a clear message.  Stale files (process gone)
    are silently overwritten.
    """
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
        except (ValueError, OSError):
            old_pid = None

        if old_pid is not None:
            try:
                # os.kill(pid, 0) raises if the process does not exist.
                os.kill(old_pid, 0)
                # Process is alive — refuse to start a second instance.
                print(
                    f"[FATAL] Another Olympus instance is already running (PID {old_pid}).\n"
                    f"  Stop it first (Ctrl+C in its terminal), then retry.\n"
                    f"  If the process is gone but the file remains, delete: {_PID_FILE}",
                    file=sys.stderr,
                )
                sys.exit(1)
            except (OSError, ProcessLookupError):
                pass  # Stale file — process is gone, safe to overwrite.

    _PID_FILE.write_text(str(os.getpid()))


def _release_pid_lock() -> None:
    """Remove the PID file on clean shutdown."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> None:
    # ------------------------------------------------------------------
    # Step 0 — Instance guard: refuse to start if already running
    # ------------------------------------------------------------------
    _acquire_pid_lock()

    # ------------------------------------------------------------------
    # Step 1 — Settings
    # ------------------------------------------------------------------
    try:
        from config.settings import settings
    except EnvironmentError as exc:
        # Can't even initialize logging without settings — use print here only
        print(f"[FATAL] Settings failed to load: {exc}")
        print("  → Copy .env.example to .env and fill in your Alpaca paper credentials.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 2 — Logging
    # ------------------------------------------------------------------
    init_logging(log_dir=settings.LOG_DIR, log_level=settings.LOG_LEVEL)
    log = get_logger(__name__)

    log.info("=" * 60)
    log.info("OLYMPUS — Live Paper-Trading Runtime starting")
    log.info("  DB path   : %s", settings.DB_PATH)
    log.info("  Paper mode: %s", settings.ALPACA_PAPER)
    log.info("  Interval  : %d min", settings.RANKING_INTERVAL_MINUTES)
    log.info("  Timezone  : %s", settings.TIMEZONE)
    log.info("=" * 60)

    # ------------------------------------------------------------------
    # Step 3 — Database
    # ------------------------------------------------------------------
    from core.memory.database import Database

    db = Database(settings.DB_PATH)
    db.initialize()
    log.info("Database ready — %s", settings.DB_PATH)

    # ------------------------------------------------------------------
    # Step 4 — Ingest existing JSON files (idempotent, safe on every start)
    # ------------------------------------------------------------------
    from core.memory.ingestion import Ingestion

    _rankings_dir = Path(__file__).resolve().parent / "data" / "rankings"
    _rankings_dir.mkdir(parents=True, exist_ok=True)

    ingestion = Ingestion(db, settings.TRADES_DIR, _rankings_dir)

    trades_result = ingestion.ingest_trades()
    log.info(
        "Startup ingestion — trades: status=%s files=%d rows=%d",
        trades_result.status, trades_result.files_seen, trades_result.rows_written,
    )

    rankings_result = ingestion.ingest_rankings()
    log.info(
        "Startup ingestion — rankings: status=%s files=%d rows=%d",
        rankings_result.status, rankings_result.files_seen, rankings_result.rows_written,
    )

    # ------------------------------------------------------------------
    # Step 5 — Core components
    # ------------------------------------------------------------------
    from core.broker.alpaca import AlpacaClient
    from core.data.cache import DataCache
    from core.data.fetcher import DataFetcher
    from core.memory.repository import Repository
    from core.memory.writer import MemoryAwarePaperTradingLoop, MemoryWriter
    from core.ranking.cycle import RankingCycle
    from core.ranking.engine import RankingEngine
    from core.trading.execution import ExecutionEngine
    from core.trading.manager import PositionManager
    from core.universe import UniverseManager

    alpaca = AlpacaClient()
    fetcher = DataFetcher()
    cache = DataCache(settings.CACHE_DIR)
    universe = UniverseManager()
    writer = MemoryWriter(db)
    repo = Repository(db)

    engine = RankingEngine(settings, fetcher, cache, universe)
    ranking_cycle = RankingCycle(engine, settings)

    execution = ExecutionEngine(alpaca, settings)
    position_manager = PositionManager(execution, settings)

    loop = MemoryAwarePaperTradingLoop(
        memory_writer=writer,
        ranking_cycle=ranking_cycle,
        position_manager=position_manager,
        execution=execution,
        fetcher=fetcher,
        settings=settings,
        alpaca_client=alpaca,
        universe_manager=universe,
    )

    log.info("All components initialized — MemoryAwarePaperTradingLoop ready")

    # ------------------------------------------------------------------
    # Step 6 — Start
    #
    # RankingCycle.start():
    #   - runs one ranking cycle synchronously (so the loop has data immediately)
    #   - then starts the background ranking scheduler
    #
    # MemoryAwarePaperTradingLoop.start():
    #   - runs one trading cycle synchronously
    #   - then starts the background trading scheduler
    #
    # Both schedulers fire on RANKING_INTERVAL_MINUTES boundaries.
    # The main thread then runs a heartbeat loop until Ctrl+C.
    # ------------------------------------------------------------------
    writer.write_event("runtime_start", "Olympus live runtime started")

    log.info("Starting RankingCycle (interval=%dmin) …", settings.RANKING_INTERVAL_MINUTES)
    ranking_cycle.start()

    log.info("Starting MemoryAwarePaperTradingLoop …")
    loop.start()

    log.info("Olympus is running. Press Ctrl+C to stop.")

    # ------------------------------------------------------------------
    # Step 7 — Heartbeat loop (main thread)
    # ------------------------------------------------------------------
    _stop = threading.Event()

    try:
        while not _stop.wait(timeout=_HEARTBEAT_INTERVAL_SECONDS):
            _log_heartbeat(log, alpaca, repo)

    except KeyboardInterrupt:
        log.info("Ctrl+C received — shutting down Olympus …")

    # ------------------------------------------------------------------
    # Step 8 — Clean shutdown
    # ------------------------------------------------------------------
    _stop.set()

    log.info("Stopping trading loop …")
    loop.stop()

    log.info("Stopping ranking cycle …")
    ranking_cycle.stop()

    writer.write_event("runtime_stop", "Olympus live runtime stopped cleanly")

    # Final status snapshot
    try:
        state = loop.get_state()
        log.info(
            "Final state — cycles=%d trades=%d daily_pnl=%.2f total_pnl=%.2f equity=%.2f",
            state.cycle_count,
            state.total_trades_completed,
            state.daily_pnl,
            state.total_pnl,
            state.paper_equity,
        )
    except Exception:
        pass

    db.close()
    _release_pid_lock()
    log.info("Olympus shutdown complete.")


# ---------------------------------------------------------------------------
# Heartbeat helper
# ---------------------------------------------------------------------------


def _log_heartbeat(log, alpaca, repo) -> None:
    """
    Log a compact alive-line. Fetches equity and trade count once.
    Wrapped in broad try/except — a heartbeat failure must not kill the process.
    """
    try:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        equity_str = "n/a"
        try:
            acct = alpaca.get_account()
            equity_str = f"${acct.get('equity', 0):,.2f}"
        except Exception:
            pass

        trade_count_str = "n/a"
        try:
            trade_count_str = str(repo.get_trade_count())
        except Exception:
            pass

        log.info(
            "HEARTBEAT | %s | equity=%s | total_trades_db=%s",
            now_utc, equity_str, trade_count_str,
        )
    except Exception:
        log.warning("Heartbeat failed:\n%s", traceback.format_exc())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit() pass through cleanly (including the instance-guard exit).
    except Exception:
        # Last-resort catch — print to stderr since logging may not be initialized
        print(f"[FATAL] Olympus runtime crashed:\n{traceback.format_exc()}", file=sys.stderr)
        _release_pid_lock()
        sys.exit(1)
