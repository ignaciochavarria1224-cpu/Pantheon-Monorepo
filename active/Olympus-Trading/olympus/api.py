from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from fastapi import FastAPI
from dotenv import load_dotenv

from core.memory.database import Database
from core.memory.repository import Repository

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="Olympus API", version="1.0.0")
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "data" / "olympus.db")))
LOG_DIR = Path(os.getenv("LOG_DIR", str(ROOT / "data" / "logs")))
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
