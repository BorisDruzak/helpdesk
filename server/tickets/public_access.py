"""Helpers for requester-facing public ticket access."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from config import SERVER_PUBLIC_BASE_URL


PUBLIC_ACCESS_FIELD = "public_access"
PUBLIC_ACCESS_CODE_LENGTH = 8
PUBLIC_ACCESS_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
PUBLIC_ACCESS_MESSAGE_KIND = "ticket_public_access_code"
FIRST_RESPONSE_STAFF_ROLES = {"support", "admin"}


def generate_public_access_code(length: int = PUBLIC_ACCESS_CODE_LENGTH) -> str:
    return "".join(secrets.choice(PUBLIC_ACCESS_ALPHABET) for _ in range(length))


def hash_public_access_code(code: str) -> str:
    cleaned = (code or "").strip().upper().encode("utf-8")
    return hashlib.sha256(cleaned).hexdigest()


def get_public_access_state(ticket_or_custom_fields: Any) -> Dict[str, Any]:
    if isinstance(ticket_or_custom_fields, dict):
        custom_fields = ticket_or_custom_fields
    else:
        custom_fields = getattr(ticket_or_custom_fields, "custom_fields", None) or {}
    raw = custom_fields.get(PUBLIC_ACCESS_FIELD) if isinstance(custom_fields, dict) else None
    return raw if isinstance(raw, dict) else {}


def set_public_access_code(current_custom_fields: Any, code: str) -> Dict[str, Any]:
    merged = dict(current_custom_fields or {})
    state = dict(get_public_access_state(merged))
    state.update(
        {
            "code_hash": hash_public_access_code(code),
            "code_hint": str(code or "").strip().upper()[-4:],
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    merged[PUBLIC_ACCESS_FIELD] = state
    return merged


def verify_public_access_code(ticket: Any, code: str) -> bool:
    state = get_public_access_state(ticket)
    stored_hash = str(state.get("code_hash") or "").strip()
    return bool(stored_hash) and stored_hash == hash_public_access_code(code)


def build_public_access_url(ticket_id: Optional[str]) -> str:
    base_url = str(SERVER_PUBLIC_BASE_URL or "").rstrip("/")
    encoded_ticket_id = quote(str(ticket_id or "").strip(), safe="")
    if encoded_ticket_id:
        return f"{base_url}/help?ticket_id={encoded_ticket_id}"
    return f"{base_url}/help"


def build_public_access_message(code: str, ticket_id: Optional[str] = None) -> Dict[str, Any]:
    access_code = (code or "").strip().upper()
    access_url = build_public_access_url(ticket_id)
    return {
        "message_id": secrets.token_hex(16),
        "sender_role": "system",
        "from": "system",
        "visibility": "public",
        "text": (
            "Код авторизации для входа в тикет: "
            f"{access_code}\n"
            "Ссылка на веб-страницу тикета: "
            f"{access_url}"
        ),
        "metadata": {
            "kind": PUBLIC_ACCESS_MESSAGE_KIND,
            "public_access_code": access_code,
            "public_access_url": access_url,
        },
    }


def is_public_access_message_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    metadata = payload.get("metadata")
    return isinstance(metadata, dict) and metadata.get("kind") == PUBLIC_ACCESS_MESSAGE_KIND


def is_public_support_reply_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if is_public_access_message_payload(payload):
        return False
    visibility = str(payload.get("visibility") or "public").strip().lower()
    if visibility != "public":
        return False
    sender_role = str(payload.get("sender_role") or payload.get("from_role") or payload.get("from") or "").strip().lower()
    return sender_role in FIRST_RESPONSE_STAFF_ROLES


def make_public_requester_id(ticket_id: str) -> str:
    return f"public:{ticket_id}"


def is_public_unbound_ticket(ticket: Any) -> bool:
    return bool(get_public_access_state(ticket).get("unbound_device"))


def mark_public_ticket_unbound(current_custom_fields: Any, unbound: bool) -> Dict[str, Any]:
    merged = dict(current_custom_fields or {})
    state = dict(get_public_access_state(merged))
    state["unbound_device"] = bool(unbound)
    if not state.get("issued_at"):
        state["issued_at"] = datetime.now(timezone.utc).isoformat()
    merged[PUBLIC_ACCESS_FIELD] = state
    return merged


def public_access_code_hint(ticket: Any) -> Optional[str]:
    hint = get_public_access_state(ticket).get("code_hint")
    cleaned = str(hint or "").strip().upper()
    return cleaned or None
