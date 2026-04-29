import json
from datetime import datetime
from pathlib import Path
from config import OLYMPUS_STATUS_PATH
from core.audit import log

def read_status() -> dict:
    if not OLYMPUS_STATUS_PATH:
        return {"success": False, "error": "OLYMPUS_STATUS_PATH not configured (legacy Apex drop file)."}
    path = Path(OLYMPUS_STATUS_PATH)
    if not path.exists():
        return {"success": False, "error": "Olympus status file not found. Is Apex running?"}
    age_minutes = (datetime.now().timestamp() - path.stat().st_mtime) / 60
    try:
        with open(path, "r") as f:
            data = json.load(f)
        data["file_age_minutes"] = round(age_minutes, 1)
        data["is_stale"] = age_minutes > 10
        log("Read Olympus status file", system="OLYMPUS")
        return {"success": True, "data": data}
    except json.JSONDecodeError:
        return {"success": False, "error": "Olympus status file is malformed JSON"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_pnl_summary() -> dict:
    result = read_status()
    if not result["success"]:
        return result
    data = result["data"]
    summary = {
        "daily_pnl": data.get("daily_pnl", "N/A"),
        "total_pnl": data.get("total_pnl", "N/A"),
        "open_positions": data.get("positions", []),
        "position_count": len(data.get("positions", [])),
        "alerts": data.get("alerts", []),
        "last_updated": data.get("timestamp", "Unknown"),
        "is_stale": data.get("is_stale", False)
    }
    return {"success": True, "summary": summary}

def get_drawdown_pct() -> float | None:
    """Return current drawdown percentage for trigger evaluation."""
    result = read_status()
    if not result["success"]:
        return None
    return result["data"].get("drawdown_pct", None)
