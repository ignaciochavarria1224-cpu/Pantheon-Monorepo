"""
Paper trading loop for Olympus Phase 3.
Wires the ranking cycle to the position manager and drives the full trading sequence each cycle.
_run_cycle() never raises under any circumstances.
"""

from __future__ import annotations

import dataclasses
import json
import threading
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

from core.logger import get_logger
from core.models import Direction, LoopState, TradeRecord
from core.scheduler import Scheduler
from core.trading.risk import validate_entry
from core.trading.sizing import calculate_size, calculate_stop_and_target

if TYPE_CHECKING:
    from core.broker.alpaca import AlpacaClient
    from core.data.fetcher import DataFetcher
    from core.ranking.cycle import RankingCycle
    from core.trading.execution import ExecutionEngine
    from core.trading.manager import PositionManager
    from core.universe import UniverseManager

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_ATR_LOOKBACK_BARS = 14
_ATR_FETCH_DAYS = 5
# Minimum number of scored symbols required before entries are attempted.
# Min-max normalisation over fewer symbols produces arbitrary scores.
_MIN_SCORED_TO_TRADE = 10
# Minimum available buying power required to attempt any entry this cycle.
_MIN_POSITION_SIZE = 500.0
# Force EOD liquidation early enough that a scheduler tick cannot miss it.
_MIN_EOD_CLOSE_BUFFER_MINUTES = 10


def _compute_atr(bars: list[dict], period: int = _ATR_LOOKBACK_BARS) -> float:
    """Simple ATR approximation: average of (high − low) for the last `period` bars."""
    recent = bars[-period:] if len(bars) >= period else bars
    if not recent:
        return 0.0
    try:
        ranges = [float(b["high"]) - float(b["low"]) for b in recent]
        return sum(ranges) / len(ranges)
    except Exception:
        return 0.0


class PaperTradingLoop:
    """
    The heartbeat of Phase 3.

    On start():
      1. Runs one full cycle immediately (synchronously).
      2. Starts a background Scheduler that fires every RANKING_INTERVAL_MINUTES.

    _run_cycle() implements the full sequence: market-hours check → ranking →
    price updates → exit evaluation → rotation → entry → state update → summary log.
    """

    def __init__(
        self,
        ranking_cycle: "RankingCycle",
        position_manager: "PositionManager",
        execution: "ExecutionEngine",
        fetcher: "DataFetcher",
        settings,
        alpaca_client: "AlpacaClient",
        universe_manager: Optional["UniverseManager"] = None,
    ) -> None:
        self._ranking_cycle = ranking_cycle
        self._position_manager = position_manager
        self._execution = execution
        self._fetcher = fetcher
        self._settings = settings
        self._alpaca = alpaca_client
        self._universe = universe_manager

        self._completed_trades: list[TradeRecord] = []
        self._recent_exit_by_symbol: dict[str, datetime] = {}
        self._trades_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cycle_count = 0
        self._eod_closed_date: Optional[date] = None      # set when EOD close-all fires
        self._report_generated_date: Optional[date] = None  # set when daily report is written
        self._apex_generated_date: Optional[date] = None
        self._weekly_apex_generated_key: Optional[str] = None
        self._last_cycle_diagnostics: dict[str, Any] = {}

        self._state = LoopState(
            is_running=False,
            last_cycle_time=None,
            cycle_count=0,
            open_position_count=0,
            total_trades_completed=0,
            paper_equity=0.0,
            paper_cash=0.0,
            daily_pnl=0.0,
            total_pnl=0.0,
            last_error=None,
        )

        self._scheduler = Scheduler(
            fn=self._run_cycle,
            interval_minutes=settings.RANKING_INTERVAL_MINUTES,
            name="trading-loop",
        )

        logger.info("PaperTradingLoop initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Run one cycle immediately, then start the background scheduler."""
        logger.info("PaperTradingLoop.start() — running initial cycle")
        self._run_cycle()
        self._scheduler.start()
        with self._state_lock:
            self._state = dataclasses.replace(self._state, is_running=True)

    def stop(self) -> None:
        """Stop the background scheduler."""
        logger.info("PaperTradingLoop stopping")
        self._scheduler.stop()
        with self._state_lock:
            self._state = dataclasses.replace(self._state, is_running=False)

    def get_state(self) -> LoopState:
        """Thread-safe read of the current loop state."""
        with self._state_lock:
            return self._state

    def get_completed_trades(self) -> list[TradeRecord]:
        """Return all completed trade records accumulated this session."""
        with self._trades_lock:
            return list(self._completed_trades)

    def get_last_cycle_diagnostics(self) -> dict[str, Any]:
        """Return the most recent cycle diagnostics snapshot."""
        with self._state_lock:
            return dict(self._last_cycle_diagnostics)

    # ------------------------------------------------------------------
    # Cycle — never raises
    # ------------------------------------------------------------------

    def _run_cycle(self) -> None:
        """
        Full paper trading cycle. Called by the scheduler on every tick.
        Must never raise — all exceptions caught at the outer level.
        """
        try:
            self._run_cycle_inner()
        except Exception:
            err = traceback.format_exc()
            logger.error("_run_cycle UNHANDLED exception:\n%s", err)
            with self._state_lock:
                self._state = dataclasses.replace(
                    self._state, last_error=err[:500]
                )

    def _run_cycle_inner(self) -> None:
        diagnostics: dict[str, Any] = {
            "cycle_time": datetime.now(timezone.utc).isoformat(),
            "qualification": {
                "passed": {"long": 0, "short": 0},
                "rejected": {},
            },
            "entries": {"attempted": 0, "filled": 0},
            "exits": {"stops_targets": 0, "rotations": 0},
            "data_quality": {},
            "broker_state": {},
        }

        # ------------------------------------------------------------------
        # Step 1 — Market clock / close-window check
        # ------------------------------------------------------------------
        try:
            clock = self._alpaca.get_clock()
            if not clock["is_open"]:
                logger.debug("Market is closed — skipping trading cycle")
                return
        except Exception as exc:
            logger.error("get_clock() failed: %s", exc)
            return

        # ------------------------------------------------------------------
        # EOD close — trigger when close is within the scheduler-safe buffer.
        # This avoids missing liquidation simply because no scheduler tick lands
        # inside a narrow 3:55–4:00 PM ET wall-clock window.
        # ------------------------------------------------------------------
        clock_ts = clock.get("timestamp")
        now_et = (
            clock_ts.astimezone(_ET)
            if isinstance(clock_ts, datetime)
            else datetime.now(_ET)
        )
        today_et = now_et.date()
        next_close = clock.get("next_close")
        minutes_to_close = None
        if isinstance(next_close, datetime):
            minutes_to_close = (next_close - clock_ts).total_seconds() / 60.0
        close_buffer_min = max(
            int(self._settings.RANKING_INTERVAL_MINUTES),
            _MIN_EOD_CLOSE_BUFFER_MINUTES,
        )

        if minutes_to_close is not None and minutes_to_close <= close_buffer_min:
            if self._eod_closed_date != today_et:
                logger.warning(
                    "EOD close buffer reached (%.1f min to close, buffer=%d) — closing all positions",
                    minutes_to_close,
                    close_buffer_min,
                )
                if self._run_eod_close():
                    self._eod_closed_date = today_et
            return  # skip ranking, exits, rotations, and entries once close-all begins

        eod_done_today = (self._eod_closed_date == today_et)

        # ------------------------------------------------------------------
        # Daily report — fires once per day at 4:05 PM ET (after EOD close)
        # Uses the same time-check pattern as the EOD routine above.
        # ------------------------------------------------------------------
        _report_trigger = now_et.replace(hour=16, minute=5, second=0, microsecond=0)
        if now_et >= _report_trigger and self._report_generated_date != today_et:
            self._generate_daily_report(today_et)
            self._report_generated_date = today_et
        if now_et >= _report_trigger and self._apex_generated_date != today_et:
            weekly_key = f"{today_et.isocalendar().year}-W{today_et.isocalendar().week:02d}"
            include_weekly = today_et.weekday() == 4 and self._weekly_apex_generated_key != weekly_key
            if self._generate_apex_reports(today_et, include_weekly=include_weekly):
                self._apex_generated_date = today_et
                if include_weekly:
                    self._weekly_apex_generated_key = weekly_key

        # ------------------------------------------------------------------
        # Step 2 — Get latest ranking
        # ------------------------------------------------------------------
        ranked = self._ranking_cycle.get_latest()
        if ranked is None:
            logger.warning("No ranking available yet — skipping cycle")
            return

        now_utc = datetime.now(timezone.utc)
        ranking_age_min = (now_utc - ranked.timestamp).total_seconds() / 60.0
        stale_threshold = self._settings.RANKING_INTERVAL_MINUTES * 2
        if ranking_age_min > stale_threshold:
            logger.warning(
                "Ranking is stale (%.1f min old, threshold=%.0f) — skipping cycle",
                ranking_age_min, stale_threshold,
            )
            return

        # ------------------------------------------------------------------
        # Step 3 — Fetch latest bars for open positions + top candidates
        # ------------------------------------------------------------------
        open_positions = self._position_manager.get_open_positions()
        all_longs = list(ranked.longs)
        all_shorts = list(ranked.shorts)

        needed_symbols = list(set(
            [p.symbol for p in open_positions]
            + [rs.symbol for rs in all_longs]
            + [rs.symbol for rs in all_shorts]
        ))

        latest_bars: dict[str, dict] = {}
        if needed_symbols:
            try:
                df = self._fetcher.fetch_latest_bars(needed_symbols)
                if not df.empty:
                    for _, row in df.iterrows():
                        sym = row.get("symbol")
                        if sym:
                            latest_bars[sym] = row.to_dict()
            except Exception as exc:
                logger.error("fetch_latest_bars failed: %s", exc)

        # ------------------------------------------------------------------
        # Step 4 — Update prices for open positions
        # ------------------------------------------------------------------
        self._position_manager.update_prices(latest_bars)

        # ------------------------------------------------------------------
        # Step 5 — Evaluate stop/target exits
        # ------------------------------------------------------------------
        exit_records = self._position_manager.evaluate_exits(latest_bars)
        for record in exit_records:
            self._persist_trade(record)
            self._register_completed_trade(record)
        diagnostics["exits"]["stops_targets"] = len(exit_records)

        # ------------------------------------------------------------------
        # Step 6 — Evaluate rotations and exit dropped positions
        # ------------------------------------------------------------------
        rotation_threshold = int(self._settings.ROTATION_RANK_DROP_THRESHOLD)

        rotation_symbols = self._position_manager.evaluate_rotations(
            ranked, threshold_override=rotation_threshold
        )
        rotation_symbols = list(dict.fromkeys(
            rotation_symbols + self._identify_stalled_positions(
                ranked_universe=ranked,
                open_positions=self._position_manager.get_open_positions(),
                now_utc=now_utc,
                rotation_threshold=rotation_threshold,
            )
        ))
        for symbol in rotation_symbols:
            position = self._position_manager.get_position(symbol)
            if position is None:
                continue  # Already exited (e.g. stop hit in same cycle)

            current_bar = latest_bars.get(symbol)
            exit_price = (
                float(current_bar["close"]) if current_bar else position.current_price
            )

            # Provide current rank/score context for the rotation exit record
            if position.direction == Direction.LONG:
                rank_now = next(
                    (rs.rank for rs in ranked.longs if rs.symbol == symbol), None
                )
                score_now = next(
                    (rs.score for rs in ranked.longs if rs.symbol == symbol), None
                )
            else:
                rank_now = next(
                    (rs.rank for rs in ranked.shorts if rs.symbol == symbol), None
                )
                score_now = next(
                    (rs.score for rs in ranked.shorts if rs.symbol == symbol), None
                )

            record = self._execution.exit_position(
                position, exit_price, "rotation", rank_now, score_now
            )
            if record is not None:
                self._position_manager.remove_position(symbol)
                self._persist_trade(record)
                self._register_completed_trade(record)
            else:
                logger.error("Rotation exit order failed for %s — position remains", symbol)
        diagnostics["exits"]["rotations"] = len(rotation_symbols)

        # ------------------------------------------------------------------
        # Step 7 — Determine entry candidates
        # ------------------------------------------------------------------
        current_open_positions = self._position_manager.get_open_positions()
        open_symbols = {p.symbol for p in current_open_positions}

        if ranked.scored_count < _MIN_SCORED_TO_TRADE:
            # A sparse ranking means min-max normalisation ran over too few
            # symbols — the resulting scores are meaningless.  Skip entries
            # entirely; exits and rotations above still ran normally.
            logger.error(
                "Ranking scored only %d symbols (minimum %d) — "
                "entries skipped this cycle",
                ranked.scored_count, _MIN_SCORED_TO_TRADE,
            )
            entry_candidates: list = []
            raw_candidates: list = []
        else:
            long_candidates = [
                rs for rs in all_longs
                if rs.symbol not in open_symbols and rs.symbol in latest_bars
            ]
            short_candidates = [
                rs for rs in all_shorts
                if rs.symbol not in open_symbols and rs.symbol in latest_bars
            ]
            raw_candidates = long_candidates + short_candidates
            entry_candidates = []

        if eod_done_today and entry_candidates:
            logger.info(
                "EOD close already executed today — skipping %d entry candidate(s)",
                len(entry_candidates),
            )
            entry_candidates = []

        # Fetch account equity once for the whole entry loop — must happen before
        # per_position_budget is computed below.
        try:
            account_info = self._alpaca.get_account()
            current_equity = account_info["equity"]
            current_cash = account_info.get("buying_power", current_equity)
        except Exception as exc:
            logger.error("get_account() failed during entry loop: %s", exc)
            current_equity = self._state.paper_equity or 100_000.0
            current_cash = self._state.paper_cash or 100_000.0

        # Sizing budget is equity-based (NOT buying_power). This caps gross
        # exposure near 1x equity and prevents margin from amplifying single
        # bad signals. entry_candidates is populated below — this placeholder
        # is recomputed after _build_entry_candidates runs.
        num_candidates = max(len(entry_candidates), 1)
        per_position_budget = current_equity / num_candidates

        # ------------------------------------------------------------------
        # Step 8 — Fetch historical bars for ATR, then enter candidates
        # ------------------------------------------------------------------
        candidate_symbols = [rs.symbol for rs in raw_candidates]
        hist_bars: dict[str, list[dict]] = {}

        if candidate_symbols:
            try:
                end_dt = now_utc
                start_dt = end_dt - timedelta(days=_ATR_FETCH_DAYS)
                hist_df = self._fetcher.fetch_historical_bars(
                    candidate_symbols, start=start_dt, end=end_dt
                )
                if not hist_df.empty:
                    for _, row in hist_df.iterrows():
                        sym = row.get("symbol")
                        if sym:
                            hist_bars.setdefault(sym, []).append(row.to_dict())
                    for sym in hist_bars:
                        hist_bars[sym].sort(
                            key=lambda r: str(r.get("timestamp", ""))
                        )
            except Exception as exc:
                logger.error("Historical bars fetch for ATR failed: %s", exc)

        if eod_done_today:
            entry_candidates = []
        elif raw_candidates:
            entry_candidates = self._build_entry_candidates(
                raw_candidates=raw_candidates,
                latest_bars=latest_bars,
                diagnostics=diagnostics,
            )

        # Recompute per-candidate budget now that entry_candidates is final.
        num_candidates = max(len(entry_candidates), 1)
        per_position_budget = current_equity / num_candidates

        # Existing gross exposure counts against the 1x-equity cap so that new
        # entries + already-open positions together cannot exceed equity.
        current_gross_exposure = sum(
            abs(position.size) * (position.current_price or position.entry_price)
            for position in self._position_manager.get_open_positions()
        )
        reserved_capital = 0.0  # capital committed by successful orders this cycle

        for rs in entry_candidates:
            diagnostics["entries"]["attempted"] += 1
            current_open = self._position_manager.get_open_positions()
            if len(current_open) >= self._settings.MAX_OPEN_POSITIONS:
                break

            symbol = rs.symbol
            direction = Direction.LONG if rs.direction == "long" else Direction.SHORT
            side_open_positions = [
                position for position in current_open if position.direction == direction
            ]
            side_limit = (
                int(self._settings.LONG_MAX_OPEN_POSITIONS)
                if direction == Direction.LONG
                else int(self._settings.SHORT_MAX_OPEN_POSITIONS)
            )
            if len(side_open_positions) >= side_limit:
                logger.debug(
                    "Entry skipped — %s %s: side cap reached (%d/%d)",
                    direction.value.upper(), symbol, len(side_open_positions), side_limit,
                )
                continue

            latest_bar = latest_bars.get(symbol)
            if latest_bar is None:
                continue

            entry_price = float(latest_bar["close"])

            # Fix 2 — Price sanity: entry_price must be within ±40% of the last historical close.
            # Catches stale or malformed latest-bar data before an order fires.
            sym_hist = hist_bars.get(symbol, [])
            if sym_hist:
                ref_close = float(sym_hist[-1]["close"])
                price_low  = ref_close * 0.60
                price_high = ref_close * 1.40
                if not (price_low <= entry_price <= price_high):
                    logger.error(
                        "Entry skipped — %s: price sanity failed | "
                        "expected %.2f–%.2f (±40%% of hist close %.2f), got %.2f",
                        symbol, price_low, price_high, ref_close, entry_price,
                    )
                    continue

            # Available capacity = 1x-equity gross-exposure cap minus what we already
            # hold and what we've reserved earlier in this cycle.
            available = current_equity - current_gross_exposure - reserved_capital
            if available < _MIN_POSITION_SIZE:
                logger.warning(
                    "Entry skipped — %s %s: available=%.2f below floor=%.2f "
                    "(gross_exposure=%.2f reserved=%.2f equity=%.2f)",
                    direction.value.upper(), symbol,
                    available, _MIN_POSITION_SIZE,
                    current_gross_exposure, reserved_capital, current_equity,
                )
                continue

            # ATR for stop/target sizing
            atr = _compute_atr(hist_bars.get(symbol, []))

            stop_price, target_price = calculate_stop_and_target(
                entry_price, direction, atr,
                self._settings.ATR_STOP_MULTIPLIER,
                self._settings.ATR_TARGET_MULTIPLIER,
            )

            risk_based_size = calculate_size(
                current_equity, entry_price, stop_price,
                self._settings.MAX_RISK_PER_TRADE_PCT,
            )
            budget_capped_size = int(per_position_budget / entry_price) if entry_price > 0 else 0
            size = min(risk_based_size, budget_capped_size)
            if size < 1 or size * entry_price > available:
                logger.debug(
                    "Entry skipped — %s %s: cost_basis %.2f exceeds available %.2f",
                    direction.value.upper(), symbol, size * entry_price, available,
                )
                continue

            valid, reason = validate_entry(
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                proposed_size=size,
                open_positions=current_open,
                daily_pnl=self._get_daily_pnl(),
                equity=current_equity,
                settings=self._settings,
                side_open_positions=side_open_positions,
                max_positions_for_side=side_limit,
                sector=self._get_symbol_sector(symbol),
                sector_by_symbol=self._build_sector_map(current_open),
                sector_limit=int(self._settings.SECTOR_CONCENTRATION_LIMIT),
            )

            if not valid:
                logger.debug("Entry rejected — %s %s: %s", direction.value.upper(), symbol, reason)
                continue

            # Re-entry cooldown: block same-symbol re-entry within N seconds of
            # the last exit. Catches the intra-cycle case where the exit order
            # fills in microseconds and the opposing entry races a still-settling
            # fill at the broker. The pending-order check below catches the
            # still-pending-order case; the cooldown covers the filled-but-not-
            # settled window.
            cooldown_seconds = int(self._settings.SYMBOL_REENTRY_COOLDOWN_SECONDS)
            with self._trades_lock:
                last_exit = self._recent_exit_by_symbol.get(symbol)
            if last_exit is not None and cooldown_seconds > 0:
                elapsed = (now_utc - last_exit).total_seconds()
                if elapsed < cooldown_seconds:
                    logger.warning(
                        "Entry skipped — %s %s: re-entry cooldown (%.0fs elapsed, %ds required)",
                        direction.value.upper(), symbol, elapsed, cooldown_seconds,
                    )
                    continue

            # Skip if a pending Alpaca order exists for this symbol.
            # The exit order from this cycle (or a previous one) may still be
            # open — submitting the opposing entry immediately would trigger
            # Alpaca's wash-trade rejection.  The order will settle by the next
            # cycle so the entry opportunity is not lost permanently.
            open_orders = self._alpaca.get_open_orders(symbol)
            if open_orders:
                logger.warning(
                    "Entry skipped — %s %s: %d pending Alpaca order(s) (wash trade prevention)",
                    direction.value.upper(), symbol, len(open_orders),
                )
                continue

            position = self._execution.enter_position(
                symbol=symbol,
                direction=direction,
                size=size,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                rank=rs.rank,
                score=rs.score,
            )
            if position is not None:
                position.features = rs.features
                self._position_manager.add_position(position)
                reserved_capital += size * entry_price  # track committed capital this cycle
                diagnostics["entries"]["filled"] += 1

        # ------------------------------------------------------------------
        # Step 9 — Update LoopState from live account
        # ------------------------------------------------------------------
        try:
            acct = self._alpaca.get_account()
            current_equity = acct["equity"]
            current_cash = acct.get("buying_power", current_equity)
        except Exception as exc:
            logger.error("get_account() failed for state update: %s", exc)
            # Retain previous values

        try:
            broker_positions = self._alpaca.get_positions()
            local_positions = {
                p.symbol: {
                    "side": p.direction.value,
                    "qty": int(p.size),
                }
                for p in self._position_manager.get_open_positions()
            }
            broker_position_map = {
                str(p.get("symbol")): {
                    "side": str(p.get("side")),
                    "qty": int(abs(float(p.get("qty", 0.0)))),
                }
                for p in broker_positions
            }
            local_symbols = sorted(local_positions)
            broker_symbols = sorted(broker_position_map)
            shared_symbols = set(local_positions) & set(broker_position_map)
            quantity_or_side_mismatch = any(
                local_positions[symbol] != broker_position_map[symbol]
                for symbol in shared_symbols
            )
            diagnostics["broker_state"] = {
                "local_open_symbols": local_symbols,
                "broker_open_symbols": broker_symbols,
                "local_open_positions": local_positions,
                "broker_open_positions": broker_position_map,
                "mismatch": (
                    local_symbols != broker_symbols
                    or quantity_or_side_mismatch
                ),
            }
        except Exception as exc:
            diagnostics["broker_state"] = {"error": str(exc)}

        with self._state_lock:
            self._cycle_count += 1
            open_count = len(self._position_manager.get_open_positions())
            with self._trades_lock:
                trades_completed = len(self._completed_trades)
            self._last_cycle_diagnostics = diagnostics
            self._state = LoopState(
                is_running=self._state.is_running,
                last_cycle_time=now_utc,
                cycle_count=self._cycle_count,
                open_position_count=open_count,
                total_trades_completed=trades_completed,
                paper_equity=current_equity,
                paper_cash=current_cash,
                daily_pnl=self._get_daily_pnl(),
                total_pnl=self._get_total_pnl(),
                last_error=None,
            )

        # ------------------------------------------------------------------
        # Step 10 — One-line cycle summary
        # ------------------------------------------------------------------
        state = self.get_state()
        logger.info(
            "Cycle #%d | %s | open=%d trades=%d daily_pnl=%.2f total_pnl=%.2f equity=%.2f",
            state.cycle_count,
            now_utc.strftime("%H:%M:%S UTC"),
            state.open_position_count,
            state.total_trades_completed,
            state.daily_pnl,
            state.total_pnl,
            state.paper_equity,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_trade(self, record: TradeRecord) -> None:
        """Write a TradeRecord to data/trades/ as a JSON file. Never raises."""
        try:
            trades_dir: Path = self._settings.TRADES_DIR
            trades_dir.mkdir(parents=True, exist_ok=True)
            filepath = trades_dir / f"trade_{record.trade_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, default=str)
            logger.debug("Trade persisted → %s", filepath.name)
        except Exception as exc:
            logger.error("Failed to persist trade %s: %s", record.trade_id[:8], exc)

    def _register_completed_trade(self, record: TradeRecord) -> None:
        """Add a completed TradeRecord to the session list."""
        with self._trades_lock:
            self._completed_trades.append(record)
            self._recent_exit_by_symbol[record.symbol] = record.exit_time

    def _build_entry_candidates(
        self,
        raw_candidates,
        latest_bars: dict[str, dict],
        diagnostics: dict[str, Any],
    ) -> list:
        per_side_limit = max(int(self._settings.MAX_CANDIDATES_PER_SIDE), 1)
        by_side: dict[str, list] = {"long": [], "short": []}

        for rs in raw_candidates:
            if latest_bars.get(rs.symbol) is None:
                self._increment_rejection(diagnostics, "missing latest bar")
                continue
            by_side[rs.direction].append(rs)
            diagnostics["qualification"]["passed"][rs.direction] += 1

        by_side["long"].sort(key=lambda rs: float(rs.score), reverse=True)
        by_side["short"].sort(key=lambda rs: float(rs.score))

        return by_side["long"][:per_side_limit] + by_side["short"][:per_side_limit]

    def _increment_rejection(self, diagnostics: dict[str, Any], reason: str) -> None:
        rejected = diagnostics["qualification"]["rejected"]
        rejected[reason] = rejected.get(reason, 0) + 1

    def _get_symbol_sector(self, symbol: str) -> Optional[str]:
        if self._universe is None:
            return None
        return self._universe.get_sector_for_symbol(symbol)

    def _build_sector_map(self, positions) -> dict[str, str]:
        sector_map: dict[str, str] = {}
        for position in positions:
            sector = self._get_symbol_sector(position.symbol)
            if sector:
                sector_map[position.symbol] = sector
        return sector_map

    def _identify_stalled_positions(
        self,
        ranked_universe,
        open_positions,
        now_utc: datetime,
        rotation_threshold: int,
    ) -> list[str]:
        long_ranks = {rs.symbol: rs.rank for rs in ranked_universe.longs}
        short_ranks = {rs.symbol: rs.rank for rs in ranked_universe.shorts}
        stalled: list[str] = []
        min_hold_minutes = int(self._settings.STALLED_TRADE_MINUTES)
        progress_floor = float(self._settings.STALLED_TRADE_PROGRESS_FLOOR)
        rank_buffer = int(self._settings.STALLED_TRADE_RANK_BUFFER)

        for position in open_positions:
            hold_minutes = (now_utc - position.entry_time).total_seconds() / 60.0
            if hold_minutes < min_hold_minutes:
                continue
            reward_capacity = abs(position.reward_per_share()) * max(position.size, 1)
            progress = (
                position.unrealized_pnl / reward_capacity
                if reward_capacity > 0 else 0.0
            )
            rank_now = (
                long_ranks.get(position.symbol)
                if position.direction == Direction.LONG
                else short_ranks.get(position.symbol)
            )
            if progress >= progress_floor:
                continue
            if rank_now is None or rank_now > max(1, rotation_threshold - rank_buffer):
                stalled.append(position.symbol)

        return stalled

    def _get_daily_pnl(self) -> float:
        """Sum realized_pnl for all trades closed today (ET date)."""
        today_et = datetime.now(_ET).date()
        with self._trades_lock:
            return sum(
                t.realized_pnl
                for t in self._completed_trades
                if t.exit_time.astimezone(_ET).date() == today_et
            )

    def _get_total_pnl(self) -> float:
        """Sum realized_pnl for all trades closed this session."""
        with self._trades_lock:
            return sum(t.realized_pnl for t in self._completed_trades)

    def _generate_daily_report(self, report_date: date) -> None:
        """
        Generate the daily Markdown report for `report_date`.
        Imported lazily so loop.py has no hard top-level dependency on Phase 4/reporting.
        Never raises — all failures are logged.
        """
        try:
            from core.reporting.daily_report import DailyReportGenerator  # lazy import
            gen = DailyReportGenerator()
            path = gen.generate(report_date)
            if path:
                logger.info("Daily report generated → %s", path)
            else:
                logger.error("Daily report generation returned None for %s", report_date)
        except Exception:
            logger.error(
                "Daily report generation failed for %s:\n%s",
                report_date, traceback.format_exc(),
            )

    def _generate_apex_reports(self, report_date: date, include_weekly: bool = False) -> bool:
        """
        Generate the structured Phase 5 Apex reports for `report_date`.
        Returns True when all requested reports were persisted, False otherwise.
        Never raises.
        """
        try:
            from core.reporting.apex_reports import ApexReportGenerator  # lazy import

            generator = ApexReportGenerator()
            results = generator.generate_daily_suite(
                report_date=report_date,
                include_weekly=include_weekly,
            )
            expected = 4 if include_weekly else 3
            if len(results) == expected:
                logger.info(
                    "Apex reports generated -> %d report(s) for %s",
                    len(results),
                    report_date,
                )
                return True

            logger.error(
                "Apex report generation incomplete for %s: expected=%d actual=%d",
                report_date,
                expected,
                len(results),
            )
            return False
        except Exception:
            logger.error(
                "Apex report generation failed for %s:\n%s",
                report_date,
                traceback.format_exc(),
            )
            return False

    def _run_eod_close(self) -> bool:
        """
        Close every open position at market with reason=eod_close.
        Called once per day when the market is within the scheduler-safe close buffer.
        Never raises — failures are logged and a broker-side fail-safe is attempted.
        Returns True when the liquidation pass completed or a broker fail-safe
        request was accepted, False when Olympus should retry on the next tick.
        """
        positions = self._position_manager.get_open_positions()
        if not positions:
            logger.info("EOD close: no local open positions to close")
        else:
            logger.info("EOD close: closing %d local open position(s) at market", len(positions))
        for position in positions:
            exit_price = position.current_price
            record = self._execution.exit_position(
                position, exit_price, "eod_close",
                rank_at_exit=None, score_at_exit=None,
            )
            if record is not None:
                self._position_manager.remove_position(position.symbol)
                self._persist_trade(record)
                self._register_completed_trade(record)
                logger.info(
                    "EOD close: %s %s | exit=%.2f reason=eod_close pnl=%.2f",
                    position.direction.value.upper(), position.symbol,
                    exit_price, record.realized_pnl,
                )
            else:
                logger.error(
                    "EOD close: exit order failed for %s — position remains open",
                    position.symbol,
                )

        # Broker-level fail-safe:
        # If local exits missed anything, ask Alpaca to cancel open orders and
        # liquidate every remaining position before the closing bell.
        broker_positions = self._alpaca.get_positions()
        broker_orders = self._alpaca.get_open_orders()
        if broker_positions or broker_orders:
            logger.warning(
                "EOD fail-safe engaged: broker still shows %d position(s) and %d open order(s)",
                len(broker_positions),
                len(broker_orders),
            )
            if self._alpaca.close_all_positions(cancel_orders=True):
                # Clear any remaining local state so Olympus does not carry
                # stale open positions into after-hours or the next session.
                for position in self._position_manager.get_open_positions():
                    self._position_manager.remove_position(position.symbol)
                    logger.warning(
                        "EOD fail-safe cleared local position state for %s after broker liquidation request",
                        position.symbol,
                    )
                return True
            else:
                logger.error("EOD fail-safe liquidation request failed — broker positions may remain open")
                return False

        return True
