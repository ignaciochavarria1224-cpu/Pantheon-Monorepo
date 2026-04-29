"""
Centralized logging setup for Olympus.
All modules must use get_logger(__name__) from this module.
No module should call logging.getLogger directly.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytz

_ET = pytz.timezone("America/New_York")
_initialized = False


class _ETFormatter(logging.Formatter):
    """Formats log timestamps in US/Eastern time."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        import datetime
        utc_dt = datetime.datetime.fromtimestamp(record.created, tz=pytz.utc)
        et_dt = utc_dt.astimezone(_ET)
        if datefmt:
            return et_dt.strftime(datefmt)
        return et_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


_LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s] — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %Z"


def init_logging(log_dir: Path, log_level: str = "INFO") -> None:
    """
    Configure the root logger. Call once at startup from main.py.
    Subsequent calls are no-ops.
    """
    global _initialized
    if _initialized:
        return

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    formatter = _ETFormatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # Rotating file handler
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "olympus.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger. All Olympus modules must use this instead of
    calling logging.getLogger directly.
    """
    return logging.getLogger(name)
