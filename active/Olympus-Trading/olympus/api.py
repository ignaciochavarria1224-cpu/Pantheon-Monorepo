from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from dotenv import load_dotenv

from config.settings import settings
from core.memory.database import Database
from core.memory.repository import Repository

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="Olympus API", version="1.0.0")
DB_PATH = Path(settings.DB_PATH)
LOG_DIR = Path(settings.LOG_DIR)
_DB = Database(DB_PATH)
_DB.initialize()
_REPO = Repository(_DB)


def _report_path() -> Path:
    return DB_PATH.parent / "reports" / "latest.md"


def _repo() -> Repository:
    return _REPO


@app.get("/health")
async def health():
    report_path = _report_path()
    quality = _REPO.get_trade_quality_summary()
    return {
        "connected": DB_PATH.exists() or report_path.exists(),
        "db_exists": DB_PATH.exists(),
        "db_path": str(DB_PATH),
        "db_updated_at": datetime.fromtimestamp(DB_PATH.stat().st_mtime).isoformat() if DB_PATH.exists() else None,
        "log_updated_at": datetime.fromtimestamp((LOG_DIR / "olympus.log").stat().st_mtime).isoformat()
        if (LOG_DIR / "olympus.log").exists()
        else None,
        "report_exists": report_path.exists(),
        "report_path": str(report_path),
        "latest_clean_trade_at": quality.get("latest_clean_trade_at"),
        "broker_mismatch_events": quality.get("broker_mismatch_events", 0),
        "trade_quality_counts": quality.get("counts", {}),
        "auto_repair_paper_positions": settings.OLYMPUS_AUTO_REPAIR_PAPER_POSITIONS,
        "block_entries_on_broker_mismatch": settings.OLYMPUS_BLOCK_ENTRIES_ON_BROKER_MISMATCH,
        "apex_training_quality_policy": settings.APEX_TRAINING_QUALITY_POLICY,
    }


@app.get("/summary")
async def summary():
    repo = _repo()
    return {
        "performance": repo.get_performance_summary(),
        "recent_events": repo.get_system_events(limit=8),
    }


@app.get("/trades")
async def trades(limit: int = 20):
    repo = _repo()
    return {"trades": repo.get_recent_trades(n=limit)}


@app.get("/cycle/latest")
async def latest_cycle():
    repo = _repo()
    return {"cycle": repo.get_latest_cycle()}


@app.get("/report/latest")
async def latest_report():
    report_path = _report_path()
    if not report_path.exists():
        return {"path": str(report_path), "updated_at": None, "content": ""}
    return {
        "path": str(report_path),
        "updated_at": datetime.fromtimestamp(report_path.stat().st_mtime).isoformat(),
        "content": report_path.read_text(encoding="utf-8"),
    }
