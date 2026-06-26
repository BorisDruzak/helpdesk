from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any
import uuid


CHAT_MESSAGE_ID_MAX_LENGTH = 120

_CHAT_RETRY_PAYLOAD_FIELDS = (
    "sender_role",
    "sender_display_name",
    "from",
    "text",
    "visibility",
    "attachment_refs",
    "metadata",
    "requester_person_id",
    "requester_binding_id",
    "requester_account_session_id",
    "requester_account_mode",
)


class ChatMessageIdError(ValueError):
    pass


def normalize_chat_message_id(
    raw_message_id: object,
    *,
    generated_factory: Callable[[], str] | None = None,
) -> str:
    """Normalize a client retry key without silently changing non-empty IDs."""

    generate = generated_factory or (lambda: str(uuid.uuid4()))
    if raw_message_id is None:
        return generate()
    message_id = str(raw_message_id).strip()
    if not message_id:
        return generate()
    if len(message_id) > CHAT_MESSAGE_ID_MAX_LENGTH:
        raise ChatMessageIdError(f"message_id must be at most {CHAT_MESSAGE_ID_MAX_LENGTH} characters")
    return message_id


def chat_message_retry_payload_matches(existing_payload: Mapping[str, Any], incoming_payload: Mapping[str, Any]) -> bool:
    return _chat_retry_fingerprint(existing_payload) == _chat_retry_fingerprint(incoming_payload)


def _chat_retry_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {field: _stable_value(payload.get(field)) for field in _CHAT_RETRY_PAYLOAD_FIELDS}


def _stable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _stable_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
