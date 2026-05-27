"""Accessibility metadata helpers for the local agent GUI.

The UIA layer is a product test surface. Keep identifiers stable, ASCII, and
free from tokens or other secrets.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


SECRET_KEY_RE = re.compile(r"(authorization|cookie|session[_-]?token|token)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(
    r"\b(authorization|cookie|session[_-]?token|token)\b\s*[:=]\s*[^;\s]+",
    re.IGNORECASE,
)


def redact_accessible_text(value: object) -> str:
    text = str(value or "")
    if not text:
        return ""
    return SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text)


def set_uia_metadata(widget: Any, object_name: str | None = None, name: str | None = None, description: str | None = None) -> None:
    if widget is None:
        return
    if object_name and hasattr(widget, "setObjectName"):
        widget.setObjectName(object_name)
    if hasattr(widget, "setAccessibleName"):
        accessible_name = redact_accessible_text(name or object_name or "")
        accessible_description = redact_accessible_text(description or "")
        if accessible_description and accessible_description not in accessible_name:
            accessible_name = f"{accessible_name}; {accessible_description}" if accessible_name else accessible_description
        widget.setAccessibleName(accessible_name)
    if description is not None and hasattr(widget, "setAccessibleDescription"):
        widget.setAccessibleDescription(redact_accessible_text(description))


def _safe_kv(key: str, value: object) -> str | None:
    if SECRET_KEY_RE.search(key):
        return None
    text = redact_accessible_text(value).strip()
    if not text:
        return None
    return f"{key}={text}"


def _join(parts: Iterable[str | None]) -> str:
    return "; ".join(part for part in parts if part)


def normalize_connection_state(bridge_connected: bool, server_state: str | None) -> str:
    state = str(server_state or "disconnected").strip().lower()
    if not bridge_connected:
        return "disconnected"
    if state in {"connected", "connecting", "disconnected", "error"}:
        return state
    if state in {"authorizing", "starting"}:
        return "connecting"
    if state in {"rejected", "auth_required"}:
        return "error"
    return "disconnected"


def connection_description(*, bridge_connected: bool, server_state: str | None, detail: str | None = None) -> str:
    normalized = normalize_connection_state(bridge_connected, server_state)
    return _join(
        [
            _safe_kv("id", "agent.connection.state"),
            _safe_kv("connection_state", normalized),
            _safe_kv("server_state", str(server_state or "disconnected").strip().lower() or "disconnected"),
            _safe_kv("bridge_connected", str(bool(bridge_connected)).lower()),
            _safe_kv("detail", detail),
        ]
    )


def account_description(session: Mapping[str, Any] | None) -> str:
    if not session:
        return "id=agent.account.summary; account_exists=false; account_mode=none"
    display_name = session.get("display_name") or session.get("full_name") or session.get("login") or ""
    parts = [
        _safe_kv("id", "agent.account.summary"),
        _safe_kv("account_exists", "true"),
        _safe_kv("account_mode", session.get("account_mode")),
        _safe_kv("display_name", display_name),
        _safe_kv("full_name", session.get("full_name")),
        _safe_kv("login", session.get("login")),
        _safe_kv("email", session.get("email")),
        _safe_kv("person_id", session.get("person_id") or session.get("account_id")),
        _safe_kv("binding_id", session.get("binding_id")),
    ]
    return _join(parts)


def ticket_card_id(ticket: Mapping[str, Any]) -> str:
    code = str(ticket.get("ticket_code") or "").strip()
    if not code:
        ticket_id = str(ticket.get("ticket_id") or "").strip()
        code = ticket_id[:8] if ticket_id else "unknown"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", code).strip("-") or "unknown"
    return f"agent.ticket.card.{safe}"


def ticket_description(ticket: Mapping[str, Any], *, prefix_id: str = "agent.ticket") -> str:
    title = str(ticket.get("title") or "").replace("\n", " ").strip()
    parts = [
        _safe_kv("id", prefix_id),
        _safe_kv("ticket_id", ticket.get("ticket_id")),
        _safe_kv("ticket_code", ticket.get("ticket_code")),
        _safe_kv("status", ticket.get("status")),
        _safe_kv("title", title),
    ]
    return _join(parts)


def ticket_list_description(tickets: Iterable[Mapping[str, Any]], *, active_ticket_id: object | None = None, limit: int = 30) -> str:
    rows = list(tickets)
    active = str(active_ticket_id or "").strip()
    parts = [
        _safe_kv("id", "agent.tickets.list"),
        _safe_kv("ticket_count", len(rows)),
        _safe_kv("active_ticket_id", active),
    ]
    for ticket in rows[: max(0, limit)]:
        card_id = ticket_card_id(ticket)
        parts.append(_safe_kv(card_id, ticket_description(ticket, prefix_id=card_id)))
    if len(rows) > limit:
        parts.append(_safe_kv("truncated", len(rows) - limit))
    return _join(parts)
