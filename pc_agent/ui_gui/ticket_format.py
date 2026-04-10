"""Общие функции отображения тикетов (без Qt) — для chat_panel и списка с делегатом."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from . import theme

STATUS_LABELS = {
    "new": "Новый",
    "triaged": "Разобран",
    "in_progress": "В работе",
    "waiting_on_user": "Ждёт пользователя",
    "waiting_on_vendor": "Ждёт подрядчика",
    "resolved": "Решён",
    "closed": "Закрыт",
}


def ticket_status_label(status: Optional[str]) -> str:
    normalized = str(status or "unknown").strip().lower()
    return STATUS_LABELS.get(normalized, normalized or "unknown")


def ticket_status_colors(status: Optional[str]) -> tuple[str, str]:
    normalized = str(status or "unknown").strip().lower()
    return theme.STATUS_COLORS_WARM.get(normalized, theme.STATUS_COLORS_WARM["unknown"])


def normalize_iso_ts(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    if "." in normalized:
        dot_idx = normalized.find(".")
        tz_idx = len(normalized)
        plus_idx = normalized.find("+", dot_idx)
        minus_idx = normalized.find("-", dot_idx)
        if plus_idx != -1:
            tz_idx = min(tz_idx, plus_idx)
        if minus_idx != -1:
            tz_idx = min(tz_idx, minus_idx)
        frac = normalized[dot_idx + 1 : tz_idx]
        if frac.isdigit() and len(frac) > 6:
            normalized = f"{normalized[: dot_idx + 1]}{frac[:6]}{normalized[tz_idx:]}"
    return normalized


def format_ts_short(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).strftime("%d.%m.%Y %H:%M:%S")
    if isinstance(value, str):
        raw = normalize_iso_ts(value)
        if not raw:
            return ""
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            return raw
    return str(value)


def ticket_row_fingerprint(ticket: dict) -> str:
    cc = ticket.get("chat_counters") or {}
    blob = {
        "id": ticket.get("ticket_id"),
        "st": ticket.get("status"),
        "up": ticket.get("updated_at"),
        "ti": ticket.get("title"),
        "um": cc.get("requester_unread_messages"),
        "ut": cc.get("requester_unread_tool_calls"),
    }
    return json.dumps(blob, sort_keys=True, default=str)
