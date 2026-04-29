from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import MARIDIAN_APP_PATH, MERIDIAN_VAULT_PATH


_cycle_lock = threading.Lock()
_cycle_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "last_stdout": "",
    "last_error": "",
}


def _root() -> Path:
    """Code location (apps/maridian inside Pantheon)."""
    return Path(MARIDIAN_APP_PATH)


def _vault() -> Path:
    """Data location (Pantheon/data/maridian-vault)."""
    return Path(MERIDIAN_VAULT_PATH)


def _read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _question_payload() -> dict[str, Any]:
    today_file = _vault() / "Questions" / f"{date.today().isoformat()}.md"
    return _read_json(today_file, {"questions": [], "source_file": str(today_file)})


def _wiki_pages(limit: int = 6) -> list[dict[str, Any]]:
    wiki_dir = _vault() / "wiki"
    if not wiki_dir.exists():
        return []
    pages = []
    for path in sorted(wiki_dir.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name == "INDEX.md":
            continue
        preview = " ".join(path.read_text(encoding="utf-8").split())[:220]
        pages.append(
            {
                "title": path.stem,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "preview": preview,
            }
        )
        if len(pages) >= limit:
            break
    return pages


def get_snapshot() -> dict[str, Any]:
    try:
        vault = _vault()
        state = _read_json(vault / "vault_state.json", {})
        questions = _question_payload()
        index_path = vault / "wiki" / "INDEX.md"
        index_excerpt = ""
        if index_path.exists():
            index_excerpt = " ".join(index_path.read_text(encoding="utf-8").split())[:280]

        return {
            "connected": vault.exists(),
            "locked": _cycle_state["running"],
            "state": state,
            "today_questions": questions.get("questions", []),
            "today_question_file": questions.get("source_file", ""),
            "top_themes": _wiki_pages(),
            "index_excerpt": index_excerpt,
            "last_cycle": state.get("last_cycle"),
            "cycle_count": state.get("cycle_count", 0),
            "entries_processed": state.get("total_entries_processed", 0),
        }
    except Exception as exc:
        return {
            "connected": False,
            "error": str(exc),
            "locked": False,
            "state": {},
            "today_questions": [],
            "today_question_file": "",
            "top_themes": [],
            "index_excerpt": "",
            "last_cycle": None,
            "cycle_count": 0,
            "entries_processed": 0,
        }


def get_cycle_status() -> dict[str, Any]:
    return {
        "running": _cycle_state["running"],
        "started_at": _cycle_state["started_at"],
        "finished_at": _cycle_state["finished_at"],
        "last_result": _cycle_state["last_result"],
        "last_error": _cycle_state["last_error"],
    }


def _ensure_maridian_on_path() -> None:
    root = str(_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _invoke_run_evolve() -> dict[str, Any]:
    """Run the Maridian cycle in-process. Caller already holds _cycle_lock."""
    _ensure_maridian_on_path()
    os.environ.setdefault("MARIDIAN_VAULT_PATH", str(_vault()))
    os.environ.setdefault("MERIDIAN_VAULT_PATH", str(_vault()))

    buf = io.StringIO()
    try:
        # Import lazily so a startup-time import error in any agent doesn't kill Apollo
        from evolve import run_evolve  # type: ignore
        with contextlib.redirect_stdout(buf):
            run_evolve()
        return {"success": True, "stdout": buf.getvalue()[-4000:], "stderr": ""}
    except Exception as exc:
        return {"success": False, "stdout": buf.getvalue()[-4000:], "error": str(exc)}


def run_cycle() -> dict[str, Any]:
    """Synchronous in-process cycle. Returns when the cycle finishes."""
    if not _cycle_lock.acquire(blocking=False):
        return {"success": False, "error": "Maridian cycle already running."}
    _cycle_state["running"] = True
    _cycle_state["started_at"] = datetime.now().isoformat(timespec="seconds")
    _cycle_state["finished_at"] = None
    _cycle_state["last_error"] = ""
    try:
        result = _invoke_run_evolve()
        _cycle_state["last_stdout"] = result.get("stdout", "")
        if result.get("success"):
            _cycle_state["last_result"] = "ok"
        else:
            _cycle_state["last_result"] = "failed"
            _cycle_state["last_error"] = result.get("error", "")
        return result
    finally:
        _cycle_state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _cycle_state["running"] = False
        _cycle_lock.release()


def run_cycle_async() -> dict[str, Any]:
    """Kick off the cycle on a background thread and return immediately."""
    if _cycle_state["running"]:
        return {"success": False, "error": "Maridian cycle already running."}
    threading.Thread(target=run_cycle, daemon=True, name="maridian-cycle").start()
    return {"success": True, "started": True}
