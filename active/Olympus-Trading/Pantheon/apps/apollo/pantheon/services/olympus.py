from __future__ import annotations

import json
import time
from typing import Any

import requests

from config import OLYMPUS_API_URL


_CACHE: dict[str, Any] = {"snapshot": None, "ts": 0.0}
_CACHE_TTL_S = 15.0
_HTTP_TIMEOUT_S = 5.0


def _empty_snapshot(error: str | None = None) -> dict[str, Any]:
    return {
        "connected": False,
        "error": error or "",
        "db_exists": False,
        "db_path": "",
        "db_updated_at": None,
        "report_path": "",
        "report_updated_at": None,
        "log_updated_at": None,
        "performance": {},
        "latest_cycle": None,
        "recent_trades": [],
        "recent_events": [],
        "report_excerpt": "",
    }


def _get(path: str) -> dict[str, Any]:
    url = OLYMPUS_API_URL.rstrip("/") + path
    r = requests.get(url, timeout=_HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def _decode_cycle(cycle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cycle:
        return None
    out = dict(cycle)
    for raw_key, decoded_key in (("top_longs_json", "top_longs"), ("top_shorts_json", "top_shorts")):
        if raw_key in out:
            try:
                out[decoded_key] = json.loads(out.pop(raw_key) or "[]")
            except Exception:
                out[decoded_key] = []
                out.pop(raw_key, None)
        out.setdefault(decoded_key, [])
    return out


def _build_snapshot() -> dict[str, Any]:
    health = _get("/health")
    summary = _get("/summary")
    cycle_payload = _get("/cycle/latest")
    trades_payload = _get("/trades?limit=8")
    report = _get("/report/latest")

    return {
        "connected": bool(health.get("connected")),
        "db_exists": bool(health.get("db_exists")),
        "db_path": health.get("db_path", ""),
        "db_updated_at": health.get("db_updated_at"),
        "report_path": health.get("report_path", ""),
        "report_updated_at": report.get("updated_at"),
        "log_updated_at": health.get("log_updated_at"),
        "performance": summary.get("performance") or {},
        "latest_cycle": _decode_cycle(cycle_payload.get("cycle")),
        "recent_trades": trades_payload.get("trades") or [],
        "recent_events": summary.get("recent_events") or [],
        "report_excerpt": (report.get("content") or "")[:2500],
    }


def get_snapshot() -> dict[str, Any]:
    now = time.time()
    cached = _CACHE.get("snapshot")
    if cached is not None and (now - _CACHE.get("ts", 0.0)) < _CACHE_TTL_S:
        return cached

    try:
        snapshot = _build_snapshot()
        _CACHE["snapshot"] = snapshot
        _CACHE["ts"] = now
        return snapshot
    except requests.RequestException as exc:
        # Don't cache failures — Olympus may come back online any moment.
        return _empty_snapshot(error=f"Olympus API unreachable at {OLYMPUS_API_URL}: {exc}")
    except Exception as exc:
        return _empty_snapshot(error=str(exc))
