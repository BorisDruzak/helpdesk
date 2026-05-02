"""Backend smart views for support ticket work queues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from tickets.statuses import normalize_status


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

_CUSTOM_FILTER_KEYS = {
    "status",
    "status_in",
    "status_not_in",
    "open_only",
    "queue_code",
    "queue_code_in",
    "assignee_id",
    "assignee_id_in",
    "assignee_empty",
    "assigned_to_me",
    "next_action_owner",
    "next_action_owner_in",
    "due_fields",
    "due_before_hours",
    "breached_fields",
    "field_equals",
    "field_in",
    "tags_any",
    "tag",
}
_FIELD_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_SAFE_FIELD_PATH_PREFIXES = (
    "custom_fields.",
    "request_form_data.",
    "request_form_summary.",
    "request_template.",
    "diagnostics.",
)
_SAFE_FIELD_PATHS = {
    "ticket_id",
    "ticket_code",
    "title",
    "status",
    "status_label",
    "requester_status",
    "requester_status_label",
    "public_status",
    "public_status_label",
    "next_action_owner",
    "next_action_due_at",
    "status_reason",
    "queue_id",
    "queue_code",
    "assignee_id",
    "requester_id",
    "requester_display_name",
    "device_id",
    "updated_at",
    "created_at",
    "requires_operator_action",
    "unread_user_messages",
    "support_pending_user_messages",
    "support_unread_user_messages",
    "first_response_due_at",
    "resolution_due_at",
    "first_response_breached_at",
    "resolution_breached_at",
    "ola_ack_due_at",
    "ola_processing_due_at",
    "ola_ack_breached_at",
    "ola_processing_breached_at",
    "priority",
    "priority_class",
    "impact",
    "urgency",
    "importance",
    "tags",
}
_SMART_VIEW_COLUMN_FIELDS = {
    "ticket_id",
    "ticket_code",
    "title",
    "status",
    "status_label",
    "public_status_label",
    "next_action_owner",
    "next_action_due_at",
    "status_reason",
    "queue_id",
    "queue_code",
    "assignee_id",
    "requester_display_name",
    "device_id",
    "updated_at",
    "created_at",
    "unread_user_messages",
    "first_response_due_at",
    "resolution_due_at",
    "ola_ack_due_at",
    "ola_processing_due_at",
    "priority",
    "priority_class",
}
_NEXT_ACTION_OWNERS = {"support", "requester", "internal_team", "vendor", "approver", "system"}
_SORT_DIRECTIONS = {"asc", "desc"}


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


def _listify_validation_value(value: Any, *, field_name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    raise ValueError(f"smart view {field_name} must be list or comma-separated string")


def _validate_status_values(value: Any, *, field_name: str) -> list[str]:
    normalized: list[str] = []
    for raw_status in _listify_validation_value(value, field_name=field_name):
        status, _changed = normalize_status(str(raw_status or "").strip())
        if not status:
            raise ValueError(f"smart view {field_name} contains unsupported status: {raw_status}")
        normalized.append(status)
    return normalized


def _validate_owner_values(value: Any, *, field_name: str) -> list[str]:
    owners = [str(item or "").strip() for item in _listify_validation_value(value, field_name=field_name)]
    invalid = [item for item in owners if item not in _NEXT_ACTION_OWNERS]
    if invalid:
        raise ValueError(f"smart view {field_name} contains unsupported owner: {invalid[0]}")
    return owners


def _validate_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"smart view {field_name} must be boolean")
    return value


def _validate_due_before_hours(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError("smart view due_before_hours must be numeric") from None
    if parsed < 0:
        raise ValueError("smart view due_before_hours must be non-negative")
    return parsed


def _validate_field_path(value: Any, *, field_name: str, allow_custom_prefixes: bool = True) -> str:
    path = str(value or "").strip()
    if not path:
        raise ValueError(f"smart view {field_name} contains empty field path")
    if not _FIELD_PATH_RE.match(path):
        raise ValueError(f"smart view {field_name} contains unsupported field path: {path}")
    if path in _SAFE_FIELD_PATHS:
        return path
    if allow_custom_prefixes and any(path.startswith(prefix) for prefix in _SAFE_FIELD_PATH_PREFIXES):
        return path
    raise ValueError(f"smart view {field_name} contains unsupported field path: {path}")


def _validate_field_path_list(value: Any, *, field_name: str) -> list[str]:
    return [_validate_field_path(item, field_name=field_name) for item in _listify_validation_value(value, field_name=field_name)]


def validate_smart_view_definition(
    *,
    filter_config: dict[str, Any],
    sort: list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    """Validate and normalize a published smart view before it enters the registry."""

    if not isinstance(filter_config, dict):
        raise ValueError("smart view filter must be object")
    unsupported_filter_keys = sorted(set(filter_config) - _CUSTOM_FILTER_KEYS)
    if unsupported_filter_keys:
        raise ValueError(f"smart view filter contains unsupported key: {unsupported_filter_keys[0]}")

    normalized_filter: dict[str, Any] = dict(filter_config)
    for key in ("status", "status_in", "status_not_in"):
        if key in normalized_filter:
            normalized_filter[key] = _validate_status_values(normalized_filter[key], field_name=key)
    for key in ("next_action_owner", "next_action_owner_in"):
        if key in normalized_filter:
            normalized_filter[key] = _validate_owner_values(normalized_filter[key], field_name=key)
    for key in ("open_only", "assignee_empty", "assigned_to_me"):
        if key in normalized_filter:
            normalized_filter[key] = _validate_bool(normalized_filter[key], field_name=key)
    if "due_before_hours" in normalized_filter:
        normalized_filter["due_before_hours"] = _validate_due_before_hours(normalized_filter["due_before_hours"])
    for key in ("due_fields", "breached_fields"):
        if key in normalized_filter:
            normalized_filter[key] = _validate_field_path_list(normalized_filter[key], field_name=key)
    for key in ("field_equals", "field_in"):
        if key in normalized_filter:
            mapping = normalized_filter[key]
            if not isinstance(mapping, dict):
                raise ValueError(f"smart view {key} must be object")
            normalized_filter[key] = {
                _validate_field_path(field, field_name=key): expected
                for field, expected in mapping.items()
            }
    for key in ("queue_code", "queue_code_in", "assignee_id", "assignee_id_in", "tags_any", "tag"):
        if key in normalized_filter:
            normalized_filter[key] = [str(item).strip() for item in _listify_validation_value(normalized_filter[key], field_name=key) if str(item).strip()]

    if sort is not None and not isinstance(sort, list):
        raise ValueError("smart view sort must be list")
    normalized_sort: list[dict[str, str]] = []
    for index, raw_sort in enumerate(sort or []):
        if not isinstance(raw_sort, dict):
            raise ValueError(f"smart view sort[{index}] must be object")
        unsupported_sort_keys = sorted(set(raw_sort) - {"field", "direction"})
        if unsupported_sort_keys:
            raise ValueError(f"smart view sort[{index}] contains unsupported key: {unsupported_sort_keys[0]}")
        field = _validate_field_path(raw_sort.get("field"), field_name=f"sort[{index}].field", allow_custom_prefixes=False)
        direction = str(raw_sort.get("direction") or "asc").strip().lower()
        if direction not in _SORT_DIRECTIONS:
            raise ValueError(f"smart view sort[{index}].direction must be asc or desc")
        normalized_sort.append({"field": field, "direction": direction})

    if columns is not None and not isinstance(columns, list):
        raise ValueError("smart view columns must be list")
    normalized_columns: list[str] = []
    for raw_column in columns or []:
        column = _validate_field_path(raw_column, field_name="columns", allow_custom_prefixes=False)
        if column not in _SMART_VIEW_COLUMN_FIELDS:
            raise ValueError(f"smart view columns contains unsupported field: {column}")
        if column not in normalized_columns:
            normalized_columns.append(column)

    return normalized_filter, normalized_sort, normalized_columns


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
