from pantheon.models import PantheonResult
from pantheon.reasoning import PantheonReasoner
from pantheon.services import blackbook, maridian, olympus
from pantheon.services.shell import get_activity_feed, get_overview

_reasoner = PantheonReasoner()


def reason(message: str, conversation_history: list | None = None, channel: str = "ui") -> PantheonResult:
    return _reasoner.reason(message=message, conversation_history=conversation_history, channel=channel)


def chat(message: str, conversation_history: list | None = None, channel: str = "ui") -> tuple[str, list]:
    history = list(conversation_history or [])
    history.append({"role": "user", "content": message})
    result = reason(message=message, conversation_history=history, channel=channel)
    history.append({"role": "assistant", "content": result.response})
    return result.response, history


def get_overview_snapshot() -> dict:
    return get_overview()


def get_blackbook_snapshot() -> dict:
    return blackbook.get_snapshot()


def get_maridian_snapshot() -> dict:
    return maridian.get_snapshot()


def get_olympus_snapshot() -> dict:
    return olympus.get_snapshot()


def get_activity_snapshot(limit: int = 10) -> dict:
    return get_activity_feed(limit=limit)


def get_doctor_snapshot() -> dict:
    return _reasoner.doctor()
