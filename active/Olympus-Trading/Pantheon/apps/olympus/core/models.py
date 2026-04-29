"""
Shared data models for Phase 2+ output.
All models are standard dataclasses with no external dependencies.
to_dict() methods are provided for JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


@dataclass
class BarFeatures:
    symbol: str
    timestamp: datetime
    close: float
    volume: float
    # momentum
    roc_5: float        # Rate of change over 5 bars
    roc_10: float       # Rate of change over 10 bars
    roc_20: float       # Rate of change over 20 bars
    acceleration: float # roc_5 minus roc_10 — is momentum intensifying?
    # volume
    rvol: float         # Relative volume vs recent average
    # structure
    vwap_deviation: float  # (close - vwap) / vwap — positive means above VWAP
    range_position: float  # Where close sits in recent high/low range — 0.0 to 1.0
    # composite
    raw_score: float    # Pre-normalized composite score
    normalized_score: float  # Final 0–100 score for ranking

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "close": self.close,
            "volume": self.volume,
            "roc_5": self.roc_5,
            "roc_10": self.roc_10,
            "roc_20": self.roc_20,
            "acceleration": self.acceleration,
            "rvol": self.rvol,
            "vwap_deviation": self.vwap_deviation,
            "range_position": self.range_position,
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
        }


@dataclass
class RankedSymbol:
    symbol: str
    score: float              # normalized_score from BarFeatures
    direction: str            # "long" or "short"
    rank: int                 # 1 = strongest in its direction
    features: BarFeatures
    timestamp: datetime       # When this ranking was computed

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score,
            "direction": self.direction,
            "rank": self.rank,
            "features": self.features.to_dict(),
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
        }


@dataclass
class RankedUniverse:
    cycle_id: str             # UUID — unique identifier for this ranking cycle
    timestamp: datetime       # When this cycle completed
    longs: list               # Top long candidates, sorted rank 1 first (list[RankedSymbol])
    shorts: list              # Top short candidates, sorted rank 1 first (list[RankedSymbol])
    universe_size: int        # Total symbols scanned this cycle
    scored_count: int         # Symbols that produced a valid score
    error_count: int          # Symbols that failed scoring (logged, not raised)
    duration_seconds: float   # How long the cycle took to complete

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp is not None else None,
            "longs": [s.to_dict() for s in self.longs],
            "shorts": [s.to_dict() for s in self.shorts],
            "universe_size": self.universe_size,
            "scored_count": self.scored_count,
            "error_count": self.error_count,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Phase 3 — Paper Trading Models
# ---------------------------------------------------------------------------


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass
class Position:
    position_id: str          # UUID4
    symbol: str
    direction: Direction
    entry_price: float
    stop_price: float
    target_price: float
    size: int                 # Shares
    entry_time: datetime
    rank_at_entry: int        # Rank position when entered (1 = top ranked)
    score_at_entry: float     # normalized_score when entered
    current_price: float      # Updated each cycle
    unrealized_pnl: float     # Updated each cycle
    status: TradeStatus       # OPEN while active
    features: Optional["BarFeatures"] = None  # BarFeatures captured at entry time

    def risk_per_share(self) -> float:
        if self.direction == Direction.LONG:
            return self.entry_price - self.stop_price
        return self.stop_price - self.entry_price

    def reward_per_share(self) -> float:
        if self.direction == Direction.LONG:
            return self.target_price - self.entry_price
        return self.entry_price - self.target_price

    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "size": self.size,
            "entry_time": self.entry_time.isoformat() if self.entry_time is not None else None,
            "rank_at_entry": self.rank_at_entry,
            "score_at_entry": self.score_at_entry,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "status": self.status.value,
        }


@dataclass
class TradeRecord:
    trade_id: str             # UUID4
    position_id: str          # Links back to Position
    symbol: str
    direction: str            # "long" or "short"
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    size: int
    entry_time: datetime
    exit_time: datetime
    hold_duration_minutes: float
    realized_pnl: float
    r_multiple: float         # realized_pnl / (risk_per_share * size)
    exit_reason: str          # "stop", "target", "rotation", "manual"
    rank_at_entry: int
    score_at_entry: float
    rank_at_exit: Optional[int]    # Rank at time of exit — None if not available
    score_at_exit: Optional[float]
    status: str               # "closed"
    features: Optional["BarFeatures"] = None  # Carried from Position for DB write

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "size": self.size,
            "entry_time": self.entry_time.isoformat() if self.entry_time is not None else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time is not None else None,
            "hold_duration_minutes": self.hold_duration_minutes,
            "realized_pnl": self.realized_pnl,
            "r_multiple": self.r_multiple,
            "exit_reason": self.exit_reason,
            "rank_at_entry": self.rank_at_entry,
            "score_at_entry": self.score_at_entry,
            "rank_at_exit": self.rank_at_exit,
            "score_at_exit": self.score_at_exit,
            "status": self.status,
        }


@dataclass
class LoopState:
    is_running: bool
    last_cycle_time: Optional[datetime]
    cycle_count: int
    open_position_count: int
    total_trades_completed: int
    paper_equity: float
    paper_cash: float
    daily_pnl: float
    total_pnl: float
    last_error: Optional[str]

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "last_cycle_time": (
                self.last_cycle_time.isoformat() if self.last_cycle_time is not None else None
            ),
            "cycle_count": self.cycle_count,
            "open_position_count": self.open_position_count,
            "total_trades_completed": self.total_trades_completed,
            "paper_equity": self.paper_equity,
            "paper_cash": self.paper_cash,
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "last_error": self.last_error,
        }
