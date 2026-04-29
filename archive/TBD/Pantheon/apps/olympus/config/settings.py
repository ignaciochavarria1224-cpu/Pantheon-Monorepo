"""
Central configuration for Olympus.
All parameters live here. Credentials are loaded from .env — never hardcoded.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the olympus root directory
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in your credentials."
        )
    return val


def _bool_env(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


def _str_env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    return int(val)


def _float_env(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    return float(val)


@dataclass(frozen=True)
class Settings:
    # --- Credentials (from .env) ---
    ALPACA_API_KEY: str
    ALPACA_SECRET_KEY: str
    ALPACA_PAPER: bool

    # --- Data feed ---
    DATA_FEED: str          # "iex" or "sip"

    # --- Market hours (ET) ---
    MARKET_OPEN: str        # "09:30"
    MARKET_CLOSE: str       # "16:00"

    # --- Universe ---
    UNIVERSE_SIZE: int      # target asset count

    # --- Bar settings ---
    BAR_TIMEFRAME: str      # default bar resolution
    HISTORICAL_LOOKBACK_DAYS: int

    # --- Scheduler ---
    RANKING_INTERVAL_MINUTES: int

    # --- Storage ---
    CACHE_DIR: Path

    # --- Logging ---
    LOG_LEVEL: str
    LOG_DIR: Path

    # --- Timezone ---
    TIMEZONE: str

    # --- Phase 3: Paper Trading ---
    MAX_OPEN_POSITIONS: int       # Max concurrent open positions (longs + shorts)
    LONG_MAX_OPEN_POSITIONS: int  # Max concurrent long positions
    SHORT_MAX_OPEN_POSITIONS: int # Max concurrent short positions
    MAX_DAILY_LOSS_PCT: float     # Max daily loss as fraction of equity (e.g. 0.02 = 2%)
    MIN_REWARD_RISK: float        # Minimum reward/risk ratio required to enter
    MAX_RISK_PER_TRADE_PCT: float # Max risk per trade as fraction of equity (e.g. 0.005 = 0.5%)
    ATR_STOP_MULTIPLIER: float    # Stop = entry ± (ATR * multiplier)
    ATR_TARGET_MULTIPLIER: float  # Target = entry ± (ATR * multiplier)
    MIN_ATR_PCT: float            # Reject trades with impractically tight ATR
    MAX_ATR_PCT: float            # Reject trades with excessively noisy ATR
    ROTATION_RANK_DROP_THRESHOLD: int  # Exit if rank drops below this value
    REGIME_TREND_ROTATION_BUFFER: int  # Trend regime allows more rank drift
    REGIME_MIXED_ROTATION_PENALTY: int # Mixed regime exits sooner on rank drift
    LONG_ENTRY_SCORE_THRESHOLD: float  # Minimum score for long qualification
    SHORT_ENTRY_SCORE_THRESHOLD: float # Maximum score for short qualification
    LONG_MIN_RVOL: float          # Minimum relative volume for long qualification
    SHORT_MIN_RVOL: float         # Minimum relative volume for short qualification
    LONG_MIN_RANGE_POSITION: float  # Minimum range position for long qualification
    SHORT_MAX_RANGE_POSITION: float # Maximum range position for short qualification
    LONG_MAX_VWAP_DEVIATION: float  # Maximum abs(vwap deviation) allowed for longs
    SHORT_MAX_VWAP_DEVIATION: float # Maximum abs(vwap deviation) allowed for shorts
    MAX_CANDIDATES_PER_SIDE: int    # Cap final qualified candidates per side each cycle
    REGIME_MIN_SCORED_COUNT: int    # Minimum scored symbols for tradeable regime
    REGIME_MAX_ERROR_COUNT: int     # Maximum tolerated ranking errors for tradeable regime
    REGIME_TOP_N: int               # How many leaders to sample when classifying regime
    REGIME_TREND_STRENGTH_MIN: float  # Strong cross-sectional strength threshold
    REGIME_MIXED_STRENGTH_MIN: float  # Mixed-but-tradeable strength threshold
    REGIME_MIXED_POSITION_SCALE: float # Slot scale applied in mixed regime
    REGIME_MIXED_SCORE_BONUS: float    # Extra score strictness in mixed regime
    SYMBOL_COOLDOWN_TRIGGER_STOPS: int # Stops before temporary cooldown
    SYMBOL_COOLDOWN_MINUTES: int       # Cooldown duration after repeated stops
    SYMBOL_SUPPRESSION_MIN_TRADES: int # Minimum history before suppressing a symbol
    SYMBOL_SUPPRESSION_MAX_STOP_RATE: float # Stop-rate threshold for suppression
    SYMBOL_SUPPRESSION_MAX_PNL: float  # PnL threshold for suppression
    SECTOR_CONCENTRATION_LIMIT: int    # Max simultaneous positions per sector
    STALLED_TRADE_MINUTES: int         # Age before a trade is considered stalled
    STALLED_TRADE_PROGRESS_FLOOR: float # Minimum progress-to-target before time exit
    STALLED_TRADE_RANK_BUFFER: int     # Extra rank grace before time-pressure exit
    TRADES_DIR: Path              # Directory for JSON trade records

    # --- Phase 4: Memory & Storage ---
    DB_PATH: Path                 # Path to olympus.db SQLite database


def load_settings() -> Settings:
    """Load and validate all settings. Raises EnvironmentError on missing credentials."""
    cache_dir = Path(_str_env("CACHE_DIR", str(_ROOT / "data" / "cache")))
    log_dir = Path(_str_env("LOG_DIR", str(_ROOT / "data" / "logs")))
    trades_dir = Path(_str_env("TRADES_DIR", str(_ROOT / "data" / "trades")))
    db_path = Path(_str_env("DB_PATH", str(_ROOT / "data" / "olympus.db")))

    # Ensure directories exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    trades_dir.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        ALPACA_API_KEY=_require_env("ALPACA_API_KEY"),
        ALPACA_SECRET_KEY=_require_env("ALPACA_SECRET_KEY"),
        ALPACA_PAPER=_bool_env("ALPACA_PAPER", True),
        DATA_FEED=_str_env("DATA_FEED", "iex"),
        MARKET_OPEN=_str_env("MARKET_OPEN", "09:30"),
        MARKET_CLOSE=_str_env("MARKET_CLOSE", "16:00"),
        UNIVERSE_SIZE=_int_env("UNIVERSE_SIZE", 200),
        BAR_TIMEFRAME=_str_env("BAR_TIMEFRAME", "5Min"),
        HISTORICAL_LOOKBACK_DAYS=_int_env("HISTORICAL_LOOKBACK_DAYS", 30),
        RANKING_INTERVAL_MINUTES=_int_env("RANKING_INTERVAL_MINUTES", 20),
        CACHE_DIR=cache_dir,
        LOG_LEVEL=_str_env("LOG_LEVEL", "INFO"),
        LOG_DIR=log_dir,
        TIMEZONE="America/New_York",
        # Phase 3 — Paper Trading
        MAX_OPEN_POSITIONS=_int_env("MAX_OPEN_POSITIONS", 20),
        LONG_MAX_OPEN_POSITIONS=_int_env("LONG_MAX_OPEN_POSITIONS", 8),
        SHORT_MAX_OPEN_POSITIONS=_int_env("SHORT_MAX_OPEN_POSITIONS", 12),
        MAX_DAILY_LOSS_PCT=_float_env("MAX_DAILY_LOSS_PCT", 0.02),
        MIN_REWARD_RISK=_float_env("MIN_REWARD_RISK", 1.8),
        MAX_RISK_PER_TRADE_PCT=_float_env("MAX_RISK_PER_TRADE_PCT", 0.005),
        ATR_STOP_MULTIPLIER=_float_env("ATR_STOP_MULTIPLIER", 1.5),
        ATR_TARGET_MULTIPLIER=_float_env("ATR_TARGET_MULTIPLIER", 3.0),
        MIN_ATR_PCT=_float_env("MIN_ATR_PCT", 0.0025),
        MAX_ATR_PCT=_float_env("MAX_ATR_PCT", 0.08),
        ROTATION_RANK_DROP_THRESHOLD=_int_env("ROTATION_RANK_DROP_THRESHOLD", 15),
        REGIME_TREND_ROTATION_BUFFER=_int_env("REGIME_TREND_ROTATION_BUFFER", 4),
        REGIME_MIXED_ROTATION_PENALTY=_int_env("REGIME_MIXED_ROTATION_PENALTY", 4),
        LONG_ENTRY_SCORE_THRESHOLD=_float_env("LONG_ENTRY_SCORE_THRESHOLD", 72.0),
        SHORT_ENTRY_SCORE_THRESHOLD=_float_env("SHORT_ENTRY_SCORE_THRESHOLD", 28.0),
        LONG_MIN_RVOL=_float_env("LONG_MIN_RVOL", 1.15),
        SHORT_MIN_RVOL=_float_env("SHORT_MIN_RVOL", 1.05),
        LONG_MIN_RANGE_POSITION=_float_env("LONG_MIN_RANGE_POSITION", 0.55),
        SHORT_MAX_RANGE_POSITION=_float_env("SHORT_MAX_RANGE_POSITION", 0.45),
        LONG_MAX_VWAP_DEVIATION=_float_env("LONG_MAX_VWAP_DEVIATION", 0.03),
        SHORT_MAX_VWAP_DEVIATION=_float_env("SHORT_MAX_VWAP_DEVIATION", 0.03),
        MAX_CANDIDATES_PER_SIDE=_int_env("MAX_CANDIDATES_PER_SIDE", 8),
        REGIME_MIN_SCORED_COUNT=_int_env("REGIME_MIN_SCORED_COUNT", 160),
        REGIME_MAX_ERROR_COUNT=_int_env("REGIME_MAX_ERROR_COUNT", 12),
        REGIME_TOP_N=_int_env("REGIME_TOP_N", 3),
        REGIME_TREND_STRENGTH_MIN=_float_env("REGIME_TREND_STRENGTH_MIN", 72.0),
        REGIME_MIXED_STRENGTH_MIN=_float_env("REGIME_MIXED_STRENGTH_MIN", 60.0),
        REGIME_MIXED_POSITION_SCALE=_float_env("REGIME_MIXED_POSITION_SCALE", 0.5),
        REGIME_MIXED_SCORE_BONUS=_float_env("REGIME_MIXED_SCORE_BONUS", 4.0),
        SYMBOL_COOLDOWN_TRIGGER_STOPS=_int_env("SYMBOL_COOLDOWN_TRIGGER_STOPS", 2),
        SYMBOL_COOLDOWN_MINUTES=_int_env("SYMBOL_COOLDOWN_MINUTES", 120),
        SYMBOL_SUPPRESSION_MIN_TRADES=_int_env("SYMBOL_SUPPRESSION_MIN_TRADES", 4),
        SYMBOL_SUPPRESSION_MAX_STOP_RATE=_float_env("SYMBOL_SUPPRESSION_MAX_STOP_RATE", 0.75),
        SYMBOL_SUPPRESSION_MAX_PNL=_float_env("SYMBOL_SUPPRESSION_MAX_PNL", -50.0),
        SECTOR_CONCENTRATION_LIMIT=_int_env("SECTOR_CONCENTRATION_LIMIT", 2),
        STALLED_TRADE_MINUTES=_int_env("STALLED_TRADE_MINUTES", 120),
        STALLED_TRADE_PROGRESS_FLOOR=_float_env("STALLED_TRADE_PROGRESS_FLOOR", 0.25),
        STALLED_TRADE_RANK_BUFFER=_int_env("STALLED_TRADE_RANK_BUFFER", 3),
        TRADES_DIR=trades_dir,
        # Phase 4 — Memory & Storage
        DB_PATH=db_path,
    )


# Module-level singleton — imported by all other modules
settings = load_settings()
