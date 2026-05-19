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

import json
import os
import sqlite3
import sys
import threading
import time
import traceback
from datetime import datetime, timezone, timedelta
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

# HTTP API mount (Pantheon reads from this) — disable with OLYMPUS_API_ENABLED=0
_DEFAULT_API_HOST = "127.0.0.1"
_DEFAULT_API_PORT = 8003


# ---------------------------------------------------------------------------
# Instance guard
# ---------------------------------------------------------------------------

def _acquire_pid_lock() -> None:
    """
    Write our PID to olympus.pid.  If the file already exists and the recorded
    PID is still alive, abort with a clear message.  Stale files (process gone)
    are silently overwritten.
    """
    while True:
        try:
            fd = os.open(_PID_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                old_pid = int(_PID_FILE.read_text().strip())
            except (ValueError, OSError):
                old_pid = None

            if old_pid is not None:
                try:
                    # os.kill(pid, 0) raises if the process does not exist.
                    os.kill(old_pid, 0)
                    print(
                        f"[FATAL] Another Olympus instance is already running (PID {old_pid}).\n"
                        f"  Stop it first (Ctrl+C in its terminal), then retry.\n"
                        f"  If the process is gone but the file remains, delete: {_PID_FILE}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                except (OSError, ProcessLookupError):
                    pass

            try:
                _PID_FILE.unlink(missing_ok=True)
            except OSError:
                time.sleep(0.1)
            continue

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        return


def _release_pid_lock() -> None:
    """Remove the PID file on clean shutdown."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _start_api_server(log) -> None:
    """
    Mount api.py FastAPI on a background daemon thread so a single launch
    covers both the trading loop and the HTTP API. Pantheon reads from this.
    Disable with OLYMPUS_API_ENABLED=0.
    """
    if not _bool_env("OLYMPUS_API_ENABLED", default=True):
        log.info("HTTP API disabled (OLYMPUS_API_ENABLED=0)")
        return

    try:
        host = os.getenv("OLYMPUS_API_HOST", _DEFAULT_API_HOST)
        port = int(os.getenv("OLYMPUS_API_PORT", str(_DEFAULT_API_PORT)))
    except ValueError:
        log.warning("Invalid OLYMPUS_API_PORT — falling back to %d", _DEFAULT_API_PORT)
        host, port = _DEFAULT_API_HOST, _DEFAULT_API_PORT

    try:
        import uvicorn
        from api import app
    except Exception as exc:
        log.warning("HTTP API not started — import failed: %s", exc)
        return

    def _run() -> None:
        try:
            config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
            server = uvicorn.Server(config)
            server.run()
        except Exception:
            log.warning("HTTP API thread crashed:\n%s", traceback.format_exc())

    threading.Thread(target=_run, daemon=True, name="olympus-api").start()
    log.info("HTTP API mounted on http://%s:%d", host, port)


def _ensure_safe_broker_start(alpaca, settings, log) -> None:
    """
    Refuse to start against an already-active broker account unless an explicit
    override is set. Olympus does not rebuild local position state on startup,
    so inheriting live broker positions would create drift immediately.
    """
    broker_positions = alpaca.get_positions()
    broker_orders = alpaca.get_open_orders()
    if not broker_positions and not broker_orders:
        return

    if broker_positions:
        pos_summary = ", ".join(
            f"{pos['symbol']} {pos['side']} x{int(abs(pos['qty']))}"
            for pos in broker_positions
        )
        log.error("Startup broker positions detected: %s", pos_summary)
    if broker_orders:
        order_summary = ", ".join(
            f"{order['symbol']} {order['side']} ({order['status']})"
            for order in broker_orders
        )
        log.error("Startup broker open orders detected: %s", order_summary)

    if bool(getattr(settings, "OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS", False)):
        if not bool(getattr(settings, "ALPACA_PAPER", True)):
            raise RuntimeError("Broker auto-repair is forbidden unless ALPACA_PAPER=True")
        log.warning(
            "OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS=1 — repairing paper broker startup state"
        )
        orders_ok = alpaca.cancel_all_orders()
        positions_ok = alpaca.close_all_positions(cancel_orders=True)
        if orders_ok and positions_ok:
            log.warning("Paper broker startup state repair submitted successfully")
            return
        raise RuntimeError("Paper broker startup state repair failed; refusing startup")

    if _bool_env("ALLOW_EXISTING_BROKER_STATE", default=False):
        log.warning(
            "ALLOW_EXISTING_BROKER_STATE=true set — continuing despite pre-existing broker state"
        )
        return

    raise RuntimeError(
        "Broker account already has open positions/orders. Refusing startup because Olympus "
        "cannot safely reconstruct local state yet. Flatten/cancel at the broker or set "
        "ALLOW_EXISTING_BROKER_STATE=true for a deliberate override."
    )


def _parse_iso_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _deserialize_bar_features(raw: str) -> Optional["BarFeatures"]:
    from core.models import BarFeatures

    if not raw:
        return None
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        return BarFeatures(
            symbol=payload.get("symbol", ""),
            timestamp=_parse_iso_datetime(payload["timestamp"]),
            close=float(payload.get("close", 0.0)),
            volume=float(payload.get("volume", 0.0)),
            roc_5=float(payload.get("roc_5", 0.0)),
            roc_10=float(payload.get("roc_10", 0.0)),
            roc_20=float(payload.get("roc_20", 0.0)),
            acceleration=float(payload.get("acceleration", 0.0)),
            rvol=float(payload.get("rvol", 0.0)),
            vwap_deviation=float(payload.get("vwap_deviation", 0.0)),
            range_position=float(payload.get("range_position", 0.0)),
            raw_score=float(payload.get("raw_score", 0.0)),
            normalized_score=float(payload.get("normalized_score", 0.0)),
        )
    except Exception:
        return None


def _build_position_from_open_position_row(row: dict) -> "Position":
    from core.models import Direction, Position, TradeStatus

    entry_time = _parse_iso_datetime(row["entry_time"])
    return Position(
        position_id=row["position_id"],
        symbol=row["symbol"],
        direction=Direction(row["direction"]),
        entry_price=float(row["entry_price"]),
        stop_price=float(row["stop_price"]),
        target_price=float(row["target_price"]),
        size=int(row["size"]),
        entry_time=entry_time,
        rank_at_entry=0,
        score_at_entry=0.0,
        current_price=float(row["entry_price"]),
        unrealized_pnl=0.0,
        status=TradeStatus.OPEN,
        features=_deserialize_bar_features(row.get("features")),
        # Part A: restore the broker entry order ID so a position opened
        # before a restart and closed after still records entry_order_id.
        # NULL-safe: pre-Part-A open_positions rows have broker_order_id NULL,
        # which Position.entry_order_id (Optional[str] = None) accepts.
        entry_order_id=row.get("broker_order_id"),
    )


def _seed_open_positions(repo, position_manager, writer, settings, log) -> None:
    stale_warn = timedelta(hours=int(settings.OPEN_POSITION_STALE_WARN_HOURS))
    stale_skip = timedelta(days=int(settings.OPEN_POSITION_STALE_SKIP_DAYS))
    now_utc = datetime.now(timezone.utc)

    try:
        rows = repo.get_open_positions()
    except sqlite3.OperationalError as exc:
        message = (
            "Startup failed: open_positions table is missing. "
            "Ensure the database has been migrated to include open_positions."
        )
        log.error("%s %s", message, exc)
        writer.write_event(
            "local_state_seed_failure",
            message,
            metadata={
                "error": str(exc),
                "severity": "fatal",
            },
        )
        raise RuntimeError(message) from exc
    except Exception as exc:
        message = "Startup failed while reading open_positions."
        log.error("%s %s", message, exc)
        writer.write_event(
            "local_state_seed_failure",
            message,
            metadata={
                "error": str(exc),
                "severity": "fatal",
            },
        )
        raise

    loaded = 0
    skipped = 0

    for row in rows:
        try:
            position = _build_position_from_open_position_row(row)
        except Exception as exc:
            message = (
                "Failed to reconstruct open position from persistent row: "
                f"position_id={row.get('position_id')} symbol={row.get('symbol')}"
            )
            log.error("%s — %s", message, traceback.format_exc())
            writer.write_event(
                "local_state_seed_failure",
                message,
                symbol=row.get("symbol"),
                metadata={
                    "position_id": row.get("position_id"),
                    "entry_time": row.get("entry_time"),
                    "error": str(exc),
                    "severity": "fatal",
                },
            )
            raise

        age = now_utc - position.entry_time
        if age < stale_warn:
            position_manager.add_position(position)
            loaded += 1
            continue

        if age < stale_skip:
            position_manager.add_position(position)
            loaded += 1
            writer.write_event(
                "stale_open_position_loaded",
                "Loaded stale open position from persistent local state.",
                symbol=position.symbol,
                metadata={
                    "severity": "warning",
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "entry_time": row.get("entry_time"),
                },
            )
            continue

        skipped += 1
        writer.write_event(
            "stale_open_position_skipped",
            "Skipped stale open position that was too old to seed into local state.",
            symbol=position.symbol,
            metadata={
                "severity": "warning",
                "position_id": position.position_id,
                "symbol": position.symbol,
                "entry_time": row.get("entry_time"),
            },
        )

    writer.write_event(
        "local_state_seeded",
        "Local open position state seeded from persistent open_positions.",
        metadata={
            "loaded_positions": loaded,
            "skipped_positions": skipped,
        },
    )
    log.info("Open position seed complete — loaded=%d skipped=%d", loaded, skipped)


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

    _rankings_dir = settings.RANKINGS_DIR
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
    from core.trading.reconciliation import BrokerReconciler
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

    # Part A: pass the memory writer so unconfirmed orders are persisted as
    # 'order_unfilled' system_events (the engine logs only if it is absent).
    execution = ExecutionEngine(alpaca, settings, memory_writer=writer)
    position_manager = PositionManager(execution, settings)
    _seed_open_positions(repo, position_manager, writer, settings, log)
    broker_reconciler = BrokerReconciler(alpaca, settings)
    _ensure_safe_broker_start(alpaca, settings, log)

    loop = MemoryAwarePaperTradingLoop(
        memory_writer=writer,
        broker_reconciler=broker_reconciler,
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

    _start_api_server(log)

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
