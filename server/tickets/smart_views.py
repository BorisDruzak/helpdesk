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
    SmartView("sla_risk", "Риск по сроку ответа", "Открытые тикеты с близким или нарушенным сроком ответа или решения"),
    SmartView("ola_risk", "Риск внутренней очереди", "Открытые тикеты с близким или нарушенным внутренним сроком очереди"),
    SmartView("unassigned", "Без исполнителя", "Открытые тикеты без назначенного исполнителя"),
    SmartView("stale_waiting", "Зависшие ожидания", "Тикеты, которые долго стоят в ожидании"),
    SmartView("waiting_approval", "Ожидает согласования", "Тикеты на статусе ожидания согласования"),
    SmartView("diagnostics_failed", "Диагностика с ошибкой", "Тикеты с признаком неуспешной диагностики"),
)

_SMART_VIEW_IDS = {view.id for view in DEFAULT_SMART_VIEWS}


def normalize_smart_view_id(raw_value: Any, *, custom_view_ids: set[str] | None = None) -> str:
    value = str(raw_value or "all").strip()
    if value in _SMART_VIEW_IDS:
        return value
    if custom_view_ids and value in custom_view_ids:
        return value
    return "all"


def smart_view_options(custom_views: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    options = [view.to_option() for view in DEFAULT_SMART_VIEWS]
    existing_ids = {option["value"] for option in options}
    for view in custom_views or []:
        code = str(view.get("code") or "").strip()
        if not code or code in existing_ids:
            continue
        options.append({"value": code, "label": str(view.get("title") or code)})
        existing_ids.add(code)
    return options


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


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    raw = str(value).strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def _value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(actual, list):
        expected_values = _as_set(expected)
        return any(str(item).strip() in expected_values for item in actual)
    return str(actual or "").strip() in _as_set(expected)


def _matches_custom_filter(
    ticket_data: dict[str, Any],
    filter_config: dict[str, Any],
    *,
    actor_id: str | None = None,
    now: datetime,
) -> bool:
    status = str(ticket_data.get("status") or "").strip()

    status_in = _as_set(filter_config.get("status_in") or filter_config.get("status"))
    if status_in and status not in status_in:
        return False

    status_not_in = _as_set(filter_config.get("status_not_in"))
    if status_not_in and status in status_not_in:
        return False

    if filter_config.get("open_only") is True and not _is_open(ticket_data):
        return False

    queue_codes = _as_set(filter_config.get("queue_code_in") or filter_config.get("queue_code"))
    if queue_codes and str(ticket_data.get("queue_code") or "").strip() not in queue_codes:
        return False

    assignee_values = _as_set(filter_config.get("assignee_id_in") or filter_config.get("assignee_id"))
    if assignee_values and str(ticket_data.get("assignee_id") or "").strip() not in assignee_values:
        return False

    if filter_config.get("assignee_empty") is True and str(ticket_data.get("assignee_id") or "").strip():
        return False

    if filter_config.get("assigned_to_me") is True and str(ticket_data.get("assignee_id") or "").strip() != str(actor_id or "").strip():
        return False

    owner_values = _as_set(filter_config.get("next_action_owner_in") or filter_config.get("next_action_owner"))
    if owner_values and str(ticket_data.get("next_action_owner") or "").strip() not in owner_values:
        return False

    due_fields = _as_set(filter_config.get("due_fields"))
    due_before_hours = filter_config.get("due_before_hours")
    if due_fields and due_before_hours is not None:
        try:
            risk_before = now + timedelta(hours=float(due_before_hours))
        except (TypeError, ValueError):
            return False
        if not any((due_at := _parse_datetime(_get_path(ticket_data, field))) and due_at <= risk_before for field in due_fields):
            return False

    breached_fields = _as_set(filter_config.get("breached_fields"))
    if breached_fields and not any(bool(_get_path(ticket_data, field)) for field in breached_fields):
        return False

    field_equals = filter_config.get("field_equals")
    if isinstance(field_equals, dict):
        for field, expected in field_equals.items():
            actual = _get_path(ticket_data, str(field))
            if isinstance(expected, list):
                if not _value_matches(actual, expected):
                    return False
            elif actual != expected:
                return False

    field_in = filter_config.get("field_in")
    if isinstance(field_in, dict):
        for field, expected in field_in.items():
            if not _value_matches(_get_path(ticket_data, str(field)), expected):
                return False

    tags = _as_set(filter_config.get("tags_any") or filter_config.get("tag"))
    if tags:
        ticket_tags = _as_set(ticket_data.get("tags"))
        if not ticket_tags.intersection(tags):
            return False

    return True


def matches_smart_view(
    ticket_data: dict[str, Any],
    smart_view_id: str,
    *,
    actor_id: str | None = None,
    now: datetime | None = None,
    custom_views: dict[str, dict[str, Any]] | None = None,
) -> bool:
    custom_views = custom_views or {}
    view_id = normalize_smart_view_id(smart_view_id, custom_view_ids=set(custom_views))
    if view_id == "all":
        return True

    now = now or datetime.now(timezone.utc)
    if view_id not in _SMART_VIEW_IDS:
        view = custom_views.get(view_id) or {}
        filter_config = view.get("filter") or {}
        if not isinstance(filter_config, dict):
            return False
        return _matches_custom_filter(ticket_data, filter_config, actor_id=actor_id, now=now)

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
