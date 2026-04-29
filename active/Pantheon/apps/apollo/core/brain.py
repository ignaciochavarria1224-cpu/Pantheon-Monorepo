from core.audit import log
from core.memory import log_conversation
from pantheon.api import chat as pantheon_chat
from pantheon.api import reason as pantheon_reason


def chat(user_message: str, conversation_history: list = None, channel: str = "ui") -> tuple[str, list]:
    if conversation_history is None:
        conversation_history = []

    log_conversation("user", user_message, channel=channel)
    log(f"User [{channel}]: {user_message[:100]}", system="PANTHEON")

    response_text, conversation_history = pantheon_chat(
        message=user_message,
        conversation_history=conversation_history,
        channel=channel,
    )

    log_conversation("apollo", response_text, channel=channel)
    return response_text, conversation_history


def _run_with_tools(messages: list) -> str:
    last_user_message = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            last_user_message = message.get("content", "")
            break
    return pantheon_reason(last_user_message, conversation_history=messages, channel="system").response
