"""Requester-facing ticket view models and formatting helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


USER_STATUS_LABELS: dict[str, str] = {
    "new": "Заявка принята",
    "queued": "Заявка принята",
    "triaged": "Заявка принята",
    "assigned": "Назначен специалист",
    "in_progress": "В работе",
    "waiting_user": "Нужен ваш ответ",
    "waiting_on_user": "Нужен ваш ответ",
    "waiting_internal": "Передано профильному специалисту",
    "waiting_vendor": "Ожидаем внешнюю сторону",
    "waiting_on_vendor": "Ожидаем внешнюю сторону",
    "waiting_approval": "Ожидает согласование",
    "waiting_on_approval": "Ожидает согласование",
    "resolved": "Проверьте решение",
    "closed": "Закрыта",
    "canceled": "Отменена",
    "cancelled": "Отменена",
}


@dataclass(frozen=True)
class NextActionViewModel:
    title: str
    description: str
    primary_action_label: str = ""
    secondary_action_label: str = ""
    first_response_text: str = ""
    resolution_text: str = ""
    style: str = "info"


@dataclass(frozen=True)
class TicketHeaderViewModel:
    number_text: str = "#—"
    title: str = "Обращение не выбрано"
    status_label: str = "—"
    status_style: str = "info"
    access_code: str = ""
    public_url: str = ""
    show_resolution_actions: bool = False


@dataclass(frozen=True)
class TimelineItem:
    id: str
    kind: str
    actor_label: str = ""
    time_label: str = ""
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TicketInfoPanelViewModel:
    requester_name: str = "—"
    assignee_name: str = "Пока не назначен"
    room: str = "—"
    phone: str = "—"
    first_response_text: str = "—"
    resolution_text: str = "—"
    first_response_progress: int = 0
    resolution_progress: int = 0
    first_response_remaining_text: str = "Срок будет рассчитан"
    resolution_remaining_text: str = "Срок будет рассчитан"
    sla_status_text: str = "Без нарушения"
    sla_style: str = "success"
    access_code: str = "—"
    public_url: str = ""
    show_device: bool = False
    device_name: str = "—"
    os_text: str = "—"
    agent_status_text: str = "—"
    last_contact_text: str = "—"


def normalize_ticket_status(status: Any) -> str:
    return str(status or "unknown").strip().lower()


def human_ticket_status_label(status: Any) -> str:
    normalized = normalize_ticket_status(status)
    return USER_STATUS_LABELS.get(normalized, "Статус уточняется")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone() if value.tzinfo is not None else value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).astimezone()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return dt.astimezone() if dt.tzinfo is not None else dt
    return None


def format_datetime_local(value: Any, *, now: datetime | None = None) -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return ""
    return dt.strftime("%d.%m.%Y %H:%M")


def format_due_label(value: Any, *, now: datetime | None = None) -> str:
    dt = _parse_datetime(value)
    if dt is None:
        return ""
    local_now = now or datetime.now(dt.tzinfo).astimezone() if dt.tzinfo is not None else datetime.now()
    if local_now.tzinfo is not None and dt.tzinfo is not None:
        local_now = local_now.astimezone(dt.tzinfo)
    if dt.date() == local_now.date():
        return f"Сегодня, до {dt:%H:%M}"
    if (dt.date() - local_now.date()).days == 1:
        return f"Завтра, до {dt:%H:%M}"
    return dt.strftime("%d.%m.%Y %H:%M")


def _time_label(value: Any) -> str:
    dt = _parse_datetime(value)
    return dt.strftime("%H:%M") if dt is not None else ""


def build_next_action_view_model(ticket: dict[str, Any], *, now: datetime | None = None) -> NextActionViewModel:
    status = normalize_ticket_status(ticket.get("status"))
    next_action_owner = str(ticket.get("next_action_owner") or "").strip().lower()
    first_response_done = _parse_datetime(ticket.get("first_response_at")) is not None
    first_response_text = format_due_label(ticket.get("first_response_due_at"), now=now)
    resolution_text = format_due_label(ticket.get("resolution_due_at"), now=now)

    if status == "resolved":
        return NextActionViewModel(
            title="Решение предложено",
            description="Проверьте, устранена ли проблема.",
            primary_action_label="Да, всё работает",
            secondary_action_label="Нет, проблема осталась",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="success",
        )
    if status == "closed":
        return NextActionViewModel(
            title="Обращение закрыто",
            description="Решение подтверждено, обращение завершено.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="success",
        )
    if status in {"canceled", "cancelled"}:
        return NextActionViewModel(
            title="Обращение отменено",
            description="Заявка больше не находится в работе.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="danger",
        )
    if status in {"waiting_user", "waiting_on_user"} or next_action_owner == "requester":
        return NextActionViewModel(
            title="Нужен ваш ответ",
            description="Специалист запросил уточнение. Ответьте в чате ниже.",
            primary_action_label="Ответить",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="warning",
        )
    if status in {"waiting_internal", "waiting_on_internal_team"} or next_action_owner in {"internal_team", "internal"}:
        return NextActionViewModel(
            title="Передано профильному специалисту",
            description="Обращение передано команде, которая отвечает за этот вопрос.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="info",
        )
    if status in {"waiting_vendor", "waiting_on_vendor"} or next_action_owner == "vendor":
        return NextActionViewModel(
            title="Ожидаем внешнюю сторону",
            description="Решение зависит от внешнего сервиса или поставщика. Поддержка следит за статусом.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="info",
        )
    if status in {"waiting_approval", "waiting_on_approval"} or next_action_owner in {"approver", "approval"}:
        return NextActionViewModel(
            title="Ожидает согласование",
            description="Для продолжения нужно согласование. Мы обновим статус, когда оно будет получено.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="warning",
        )
    if first_response_done and next_action_owner in {"", "support"}:
        return NextActionViewModel(
            title="Сейчас на стороне поддержки",
            description="Первый ответ уже получен. Дальше специалист готовит решение или запросит уточнения в чате.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="info",
        )
    if status in {"new", "queued", "triaged"}:
        return NextActionViewModel(
            title="Ожидаем специалиста",
            description="Мы приняли вашу заявку и уже назначаем специалиста. Вы получите первый ответ в установленное время.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="info",
        )
    if status in {"assigned", "in_progress"}:
        return NextActionViewModel(
            title="Сейчас на стороне поддержки",
            description="Специалист проверяет обращение и готовит следующий ответ.",
            first_response_text=first_response_text,
            resolution_text=resolution_text,
            style="info",
        )
    return NextActionViewModel(
        title=human_ticket_status_label(status),
        description="Статус обращения обновлён. Подробности появятся в чате ниже.",
        first_response_text=first_response_text,
        resolution_text=resolution_text,
        style="info",
    )


def _ticket_number_text(ticket: dict[str, Any]) -> str:
    raw = _fallback_dash(
        ticket.get("ticket_code")
        or ticket.get("ticket_number")
        or ticket.get("number")
        or ticket.get("ticket_id")
    )
    if raw == "—":
        return "#—"
    return raw if raw.startswith("#") else f"#{raw}"


def _status_style(status: str) -> str:
    if status in {"closed", "resolved"}:
        return "success"
    if status in {"waiting_user", "waiting_on_user", "waiting_approval", "waiting_on_approval"}:
        return "warning"
    if status in {"canceled", "cancelled"}:
        return "danger"
    return "info"


def build_ticket_header_view_model(ticket: dict[str, Any], *, access_code: str = "") -> TicketHeaderViewModel:
    status = normalize_ticket_status(ticket.get("status"))
    return TicketHeaderViewModel(
        number_text=_ticket_number_text(ticket),
        title=_fallback_dash(ticket.get("title") or ticket.get("subject")),
        status_label=human_ticket_status_label(status),
        status_style=_status_style(status),
        access_code=str(access_code or ticket.get("public_access_code") or ticket.get("access_code") or "").strip(),
        public_url=str(ticket.get("public_access_url") or ticket.get("public_url") or "").strip(),
        show_resolution_actions=status == "resolved",
    )


def _fallback_dash(value: Any) -> str:
    text = str(value or "").strip()
    return text or "—"


def _requester_room_label(profile: dict[str, Any]) -> str:
    building = str(profile.get("building") or profile.get("city") or "").strip()
    room = str(profile.get("room") or profile.get("office") or profile.get("cabinet") or "").strip()
    if building and room:
        return f"{building}, кабинет {room}"
    if room:
        return f"кабинет {room}"
    return building or "—"


def _sla_status_label(raw_status: Any) -> tuple[str, str]:
    status = str(raw_status or "").strip().lower()
    if status in {"breached", "overdue", "expired", "violation"}:
        return "Просрочено", "danger"
    if status in {"risk", "warning", "at_risk"}:
        return "Есть риск", "warning"
    return "Без нарушения", "success"


def _duration_short_label(total_seconds: float) -> str:
    if total_seconds <= 0:
        return "Просрочено"
    minutes = max(1, int(round(total_seconds / 60)))
    if minutes < 60:
        return f"≈ {minutes} мин"
    hours, rest_minutes = divmod(minutes, 60)
    if rest_minutes:
        return f"≈ {hours} ч {rest_minutes} мин"
    return f"≈ {hours} ч"


def _sla_progress_for_due(
    due_value: Any,
    *,
    start_value: Any = None,
    now: datetime | None = None,
) -> tuple[int, str]:
    due_at = _parse_datetime(due_value)
    if due_at is None:
        return 0, "Срок будет рассчитан"
    local_now = now or datetime.now(due_at.tzinfo).astimezone() if due_at.tzinfo is not None else datetime.now()
    if local_now.tzinfo is not None and due_at.tzinfo is not None:
        local_now = local_now.astimezone(due_at.tzinfo)
    remaining_text = _duration_short_label((due_at - local_now).total_seconds())
    start_at = _parse_datetime(start_value)
    if start_at is None:
        return (100 if local_now >= due_at else 0), remaining_text
    if start_at.tzinfo is not None and due_at.tzinfo is not None:
        start_at = start_at.astimezone(due_at.tzinfo)
    total_seconds = (due_at - start_at).total_seconds()
    if total_seconds <= 0:
        return 100, remaining_text
    elapsed_seconds = (local_now - start_at).total_seconds()
    progress = int(round((elapsed_seconds / total_seconds) * 100))
    return max(0, min(100, progress)), remaining_text


def _ticket_device_payload(ticket: dict[str, Any]) -> dict[str, Any]:
    device = ticket.get("device") or ticket.get("device_info") or ticket.get("agent_device")
    return device if isinstance(device, dict) else {}


def build_ticket_info_panel_view_model(
    ticket: dict[str, Any],
    *,
    access_code: str = "",
    now: datetime | None = None,
) -> TicketInfoPanelViewModel:
    profile = ticket.get("requester_profile")
    profile = profile if isinstance(profile, dict) else {}
    device = _ticket_device_payload(ticket)
    requester_name = _fallback_dash(
        profile.get("full_name")
        or profile.get("display_name")
        or ticket.get("requester_display_name")
        or ticket.get("requester_name")
    )
    requester_view = ticket.get("requester_view")
    requester_view = requester_view if isinstance(requester_view, dict) else {}
    public_view = ticket.get("public_view")
    public_view = public_view if isinstance(public_view, dict) else {}
    assignee_name = _first_text(
        requester_view.get("assignee_display_name"),
        requester_view.get("assignee_name"),
        public_view.get("assignee_display_name"),
        public_view.get("assignee_name"),
        ticket.get("assignee_display_name"),
        ticket.get("assignee_name"),
        ticket.get("assignee_id"),
    ) or "Пока не назначен"
    resolution_text = format_due_label(ticket.get("resolution_due_at"), now=now) or "—"
    start_value = ticket.get("created_at") or ticket.get("created") or ticket.get("opened_at")
    first_response_at = ticket.get("first_response_at")
    if _parse_datetime(first_response_at) is not None:
        first_response_text = f"Получен: {_time_label(first_response_at)}"
        first_response_progress = 100
        first_response_remaining_text = "Первый ответ получен"
    else:
        first_response_text = format_due_label(ticket.get("first_response_due_at"), now=now) or "—"
        first_response_progress, first_response_remaining_text = _sla_progress_for_due(
            ticket.get("first_response_due_at"),
            start_value=start_value,
            now=now,
        )
    resolution_progress, resolution_remaining_text = _sla_progress_for_due(
        ticket.get("resolution_due_at"),
        start_value=start_value,
        now=now,
    )
    sla_text, sla_style = _sla_status_label(
        ticket.get("sla_status")
        or ticket.get("deadline_status")
        or ticket.get("timing_status")
    )
    os_parts = [
        str(device.get("os_name") or device.get("operating_system") or "").strip(),
        str(device.get("os_version") or "").strip(),
    ]
    os_text = " ".join(part for part in os_parts if part).strip() or "—"
    agent_online = bool(device.get("agent_online") or device.get("online"))
    has_agent_online = "agent_online" in device or "online" in device
    last_seen = (
        device.get("last_seen_at")
        or device.get("last_contact_at")
        or device.get("agent_last_seen_at")
        or ticket.get("last_seen_at")
    )
    device_name = _fallback_dash(device.get("hostname") or device.get("device_name") or device.get("name"))
    has_device_details = any(
        value and str(value).strip()
        for value in (
            device.get("hostname"),
            device.get("device_name"),
            device.get("name"),
            device.get("os_name"),
            device.get("operating_system"),
            device.get("os_version"),
            last_seen,
        )
    )
    return TicketInfoPanelViewModel(
        requester_name=requester_name,
        assignee_name=assignee_name,
        room=_requester_room_label(profile),
        phone=_fallback_dash(profile.get("phone") or ticket.get("requester_phone")),
        first_response_text=first_response_text,
        resolution_text=resolution_text,
        first_response_progress=first_response_progress,
        resolution_progress=resolution_progress,
        first_response_remaining_text=first_response_remaining_text,
        resolution_remaining_text=resolution_remaining_text,
        sla_status_text=sla_text,
        sla_style=sla_style,
        access_code=_fallback_dash(access_code or ticket.get("public_access_code") or ticket.get("access_code")),
        public_url=str(ticket.get("public_access_url") or ticket.get("public_url") or "").strip(),
        show_device=has_device_details,
        device_name=device_name,
        os_text=os_text,
        agent_status_text=("Онлайн" if agent_online else "Офлайн") if has_agent_online else "—",
        last_contact_text=format_datetime_local(last_seen) or "—",
    )


def _event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or event.get("id") or event.get("operation_id") or "")


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    details = event.get("event_details")
    if isinstance(details, dict):
        merged.update(details)
    payload = event.get("payload")
    if isinstance(payload, dict):
        merged.update(payload)
    return merged


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_diagnostic_checks(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        raw_checks = payload.get("steps")
    if not isinstance(raw_checks, list):
        result = payload.get("result")
        raw_checks = result.get("checks") if isinstance(result, dict) else []
    checks: list[dict[str, str]] = []
    for item in raw_checks or []:
        if not isinstance(item, dict):
            continue
        label = _first_text(item.get("label"), item.get("name"), item.get("key"), item.get("step"))
        status = _first_text(item.get("status"), item.get("result")).lower()
        summary = _first_text(item.get("message"), item.get("summary"), item.get("error"))
        if not summary:
            summary = "OK" if status in {"ok", "success", "passed"} else (status.upper() if status else "")
        checks.append({"label": label, "status": status or "unknown", "summary": summary})
    return checks


def _event_value(event: dict[str, Any], payload: dict[str, Any], *keys: str) -> Any:
    details = event.get("event_details")
    for key in keys:
        if key in payload:
            return payload.get(key)
        if key in event:
            return event.get(key)
        if isinstance(details, dict) and key in details:
            return details.get(key)
    return None


def _status_change_text(status: Any) -> str:
    normalized = normalize_ticket_status(status)
    if normalized in {"", "unknown", "none", "null"}:
        return ""
    if normalized == "assigned":
        return "Назначен специалист поддержки."
    if normalized == "in_progress":
        return "Специалист взял обращение в работу."
    if normalized in {"waiting_user", "waiting_on_user"}:
        return "Специалист ждёт ваш ответ."
    if normalized in {"waiting_internal", "waiting_on_internal_team"}:
        return "Обращение передано профильному специалисту."
    if normalized in {"waiting_vendor", "waiting_on_vendor"}:
        return "Ожидаем ответ внешней стороны."
    if normalized in {"waiting_approval", "waiting_on_approval"}:
        return "Обращение ожидает согласование."
    if normalized == "resolved":
        return "Поддержка предложила решение. Проверьте, устранена ли проблема."
    if normalized == "closed":
        return "Обращение закрыто."
    if normalized in {"canceled", "cancelled"}:
        return "Обращение отменено."
    if normalized in {"new", "queued", "triaged"}:
        return "Заявка принята."
    return "Статус обращения обновлён."


def _format_file_size(value: Any) -> str:
    try:
        size = int(value or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0:
        return ""
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} КБ"
    return f"{size / (1024 * 1024):.1f} МБ".replace(".0 МБ", " МБ")


def _attachment_payload(payload: dict[str, Any]) -> dict[str, str]:
    source = payload.get("attachment") if isinstance(payload.get("attachment"), dict) else payload
    name = _first_text(
        source.get("name"),
        source.get("file_name"),
        source.get("filename"),
        source.get("original_name"),
        "Файл",
    )
    size_label = _first_text(
        source.get("size_label"),
        _format_file_size(source.get("size_bytes") or source.get("size") or source.get("file_size")),
    )
    url = _first_text(source.get("download_url"), source.get("url"), source.get("href"))
    return {"name": name, "size_label": size_label, "url": url}


def map_ticket_event_to_user_timeline_item(event: dict[str, Any]) -> TimelineItem | None:
    event_type = str(event.get("event_type") or event.get("type") or "").strip().lower()
    payload = _event_payload(event)
    event_kind = str(payload.get("event") or event_type).strip().lower()
    time_label = _time_label(event.get("created_at") or event.get("ts") or payload.get("created_at"))

    projection_text = _first_text(event.get("requester_timeline_text"), payload.get("requester_timeline_text"))
    if projection_text:
        projection_payload = event.get("requester_timeline_payload")
        if not isinstance(projection_payload, dict):
            projection_payload = payload.get("requester_timeline_payload")
        return TimelineItem(
            _event_id(event),
            _first_text(event.get("requester_timeline_kind"), payload.get("requester_timeline_kind"), "system_event"),
            _first_text(payload.get("actor_label"), payload.get("sender_display_name"), "Система"),
            time_label,
            projection_text,
            dict(projection_payload) if isinstance(projection_payload, dict) else {},
        )

    hidden_events = {
        "internal_note",
        "worklog_added",
        "message_read",
        "external_notification_delivery",
        "policy_action_dispatched",
        "ticket_updated",
        "ticket_refreshed",
        "presence_updated",
        "ticket_hidden_from_workspace",
        "ticket_unhidden_from_workspace",
        "ticket_archived_from_workspace",
        "ticket_unarchived_from_workspace",
        "sla_paused",
        "sla_resumed",
        "sla_reminder_sent",
        "ola_started",
        "ola_ack_stopped",
        "ola_processing_stopped",
        "ola_paused",
        "ola_resumed",
        "ola_breached",
        "operation_timed_out",
    }
    hidden_prefixes = ("raw_", "debug_", "observer_", "internal_", "tool_log", "protocol_", "auth_")
    if event_kind in hidden_events or event_type in hidden_events:
        return None
    if any(event_kind.startswith(prefix) or event_type.startswith(prefix) for prefix in hidden_prefixes):
        return None
    if event_kind == "ticket_created":
        return TimelineItem(_event_id(event), "system_event", "Система", time_label, "Заявка зарегистрирована.")
    if event_kind in {"routed", "queue_changed"}:
        return TimelineItem(
            _event_id(event),
            "system_event",
            "Система",
            time_label,
            "Заявка передана в первую линию поддержки.",
        )
    if event_kind == "status_changed":
        status_text = _status_change_text(
            _event_value(event, payload, "to_status", "new_status", "status", "ticket_status")
        )
        if not status_text:
            return None
        return TimelineItem(
            _event_id(event),
            "system_event",
            "Система",
            time_label,
            status_text,
        )
    if event_kind in {"assigned", "assignee_changed", "assignment_changed"}:
        return TimelineItem(_event_id(event), "system_event", "Система", time_label, "Назначен специалист поддержки.")
    if event_kind in {"sla_started", "sla_recalculated"}:
        return TimelineItem(_event_id(event), "system_event", "Система", time_label, "Сроки обращения рассчитаны.")
    if event_kind == "sla_first_response_stopped":
        return TimelineItem(_event_id(event), "system_event", "Система", time_label, "Первый ответ получен.")
    if event_kind == "priority_changed":
        return TimelineItem(_event_id(event), "system_event", "Система", time_label, "Приоритет обращения обновлён.")
    if event_kind == "tool_call_started":
        return TimelineItem(
            _event_id(event),
            "system_event",
            "Система",
            time_label,
            "Специалист запустил диагностику.",
        )
    if event_kind == "tool_call_result":
        return TimelineItem(
            _event_id(event),
            "diagnostic_result",
            "Система",
            time_label,
            "Диагностика выполнена",
            {"checks": _normalize_diagnostic_checks(payload)},
        )
    if event_kind in {"attachment_uploaded", "attachment_added", "file_uploaded", "file_attached"}:
        return TimelineItem(
            _event_id(event),
            "attachment",
            _first_text(payload.get("actor_label"), payload.get("sender_name"), "Вы"),
            time_label,
            "Файл приложен",
            _attachment_payload(payload),
        )
    if event_kind == "support_message":
        return TimelineItem(
            _event_id(event),
            "support_message",
            _first_text(payload.get("actor_label"), payload.get("sender_name"), "Специалист поддержки"),
            time_label,
            _first_text(payload.get("text"), payload.get("message")),
            payload,
        )
    if event_kind == "user_message":
        return TimelineItem(
            _event_id(event),
            "user_message",
            "Вы",
            time_label,
            _first_text(payload.get("text"), payload.get("message")),
            payload,
        )
    if event_kind != "system_message_local":
        return None
    user_text = _first_text(event.get("message"), payload.get("message"), payload.get("description"), payload.get("text"))
    if not user_text:
        return None
    return TimelineItem(
        _event_id(event),
        "system_event",
        "Система",
        time_label,
        user_text,
        payload,
    )
