"""Backend smart views for support ticket work queues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


TERMINAL_STATUSES = {"resolved", "closed", "canceled"}
WAITING_STATUSES = {
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
}


@dataclass(frozen=True)
class SmartView:
    id: str
    title: str
    description: str

    def to_option(self) -> dict[str, str]:
        return {"value": self.id, "label": self.title}


DEFAULT_SMART_VIEWS: tuple[SmartView, ...] = (
    SmartView("all", "Все", "Все доступные тикеты"),
    SmartView("my_action", "Нужен мой ответ", "Тикеты, где следующий шаг за поддержкой"),
    SmartView("requester_reply", "Ответил пользователь", "Тикеты с непрочитанными сообщениями пользователя"),
    SmartView("sla_risk", "SLA риск", "Открытые тикеты с близким или нарушенным SLA"),
    SmartView("ola_risk", "OLA риск", "Открытые тикеты с близким или нарушенным OLA"),
    SmartView("unassigned", "Без исполнителя", "Открытые тикеты без назначенного исполнителя"),
    SmartView("stale_waiting", "Зависшие ожидания", "Тикеты, которые долго стоят в ожидании"),
    SmartView("waiting_approval", "Ожидает согласования", "Тикеты на статусе ожидания согласования"),
    SmartView("diagnostics_failed", "Диагностика с ошибкой", "Тикеты с признаком неуспешной диагностики"),
)

_SMART_VIEW_IDS = {view.id for view in DEFAULT_SMART_VIEWS}


def normalize_smart_view_id(raw_value: Any) -> str:
    value = str(raw_value or "all").strip()
    return value if value in _SMART_VIEW_IDS else "all"


def smart_view_options() -> list[dict[str, str]]:
    return [view.to_option() for view in DEFAULT_SMART_VIEWS]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_open(ticket_data: dict[str, Any]) -> bool:
    return str(ticket_data.get("status") or "").strip() not in TERMINAL_STATUSES


def _due_at_or_breached(ticket_data: dict[str, Any], *, due_keys: tuple[str, ...], breach_keys: tuple[str, ...], now: datetime) -> bool:
    if any(ticket_data.get(key) for key in breach_keys):
        return True
    risk_before = now + timedelta(hours=2)
    for key in due_keys:
        due_at = _parse_datetime(ticket_data.get(key))
        if due_at and due_at <= risk_before:
            return True
    return False


def _diagnostics_failed(ticket_data: dict[str, Any]) -> bool:
    custom_fields = ticket_data.get("custom_fields") or {}
    if not isinstance(custom_fields, dict):
        custom_fields = {}
    diagnostics = custom_fields.get("diagnostics") or custom_fields.get("diagnostic_policy") or {}
    if isinstance(diagnostics, dict):
        status = str(diagnostics.get("status") or diagnostics.get("last_status") or "").strip().lower()
        result = str(diagnostics.get("result") or diagnostics.get("last_result") or "").strip().lower()
        if status in {"failed", "error"} or result in {"failed", "error"}:
            return True
    tags = ticket_data.get("tags") or []
    return isinstance(tags, list) and any(str(tag).strip() == "diagnostics_failed" for tag in tags)


def matches_smart_view(
    ticket_data: dict[str, Any],
    smart_view_id: str,
    *,
    actor_id: str | None = None,
    now: datetime | None = None,
) -> bool:
    view_id = normalize_smart_view_id(smart_view_id)
    if view_id == "all":
        return True

    now = now or datetime.now(timezone.utc)
    status = str(ticket_data.get("status") or "").strip()
    if view_id == "my_action":
        owner = str(ticket_data.get("next_action_owner") or "").strip()
        return _is_open(ticket_data) and owner in {"support", "internal_team", "approver", "system"}
    if view_id == "requester_reply":
        return _is_open(ticket_data) and int(ticket_data.get("support_pending_user_messages") or ticket_data.get("support_unread_user_messages") or 0) > 0
    if view_id == "sla_risk":
        return _is_open(ticket_data) and _due_at_or_breached(
            ticket_data,
            due_keys=("first_response_due_at", "resolution_due_at"),
            breach_keys=("first_response_breached_at", "resolution_breached_at"),
            now=now,
        )
    if view_id == "ola_risk":
        return _is_open(ticket_data) and _due_at_or_breached(
            ticket_data,
            due_keys=("ola_ack_due_at", "ola_processing_due_at"),
            breach_keys=("ola_ack_breached_at", "ola_processing_breached_at"),
            now=now,
        )
    if view_id == "unassigned":
        return _is_open(ticket_data) and not str(ticket_data.get("assignee_id") or "").strip()
    if view_id == "stale_waiting":
        updated_at = _parse_datetime(ticket_data.get("updated_at"))
        return status in WAITING_STATUSES and bool(updated_at and updated_at <= now - timedelta(days=3))
    if view_id == "waiting_approval":
        return status == "waiting_on_approval"
    if view_id == "diagnostics_failed":
        return _is_open(ticket_data) and _diagnostics_failed(ticket_data)
    return True
