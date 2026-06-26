"""Requester-facing projection for ticket timeline events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from tickets.public_access import is_public_access_message_payload


RequesterTimelineKind = Literal[
    "system_event",
    "diagnostic_result",
    "attachment",
    "user_message",
    "support_message",
]


@dataclass(frozen=True)
class RequesterTimelineProjection:
    text: str
    kind: RequesterTimelineKind
    payload: dict[str, Any]
    icon: str | None = None
    style: str | None = None


STATUS_TEXT: dict[str, str] = {
    "new": "Обращение принято.",
    "queued": "Обращение принято.",
    "assigned": "Назначен специалист поддержки.",
    "in_progress": "Специалист взял обращение в работу.",
    "waiting_on_user": "Специалист ждёт ваш ответ.",
    "waiting_user": "Специалист ждёт ваш ответ.",
    "waiting_on_internal_team": "Обращение передано профильному специалисту.",
    "waiting_internal": "Обращение передано профильному специалисту.",
    "waiting_on_vendor": "Ожидаем ответ внешней стороны.",
    "waiting_vendor": "Ожидаем ответ внешней стороны.",
    "waiting_on_approval": "Обращение ожидает согласование.",
    "waiting_approval": "Обращение ожидает согласование.",
    "scheduled": "Обращение запланировано.",
    "resolved": "Поддержка предложила решение. Проверьте, устранена ли проблема.",
    "closed": "Обращение закрыто.",
    "canceled": "Обращение отменено.",
    "cancelled": "Обращение отменено.",
}

SYSTEM_EVENT_TEXT: dict[str, str] = {
    "ticket_created": "Обращение зарегистрировано.",
    "queue_changed": "Обращение передано в профильную группу поддержки.",
    "routing_applied": "Обращение направлено в подходящую группу поддержки.",
    "priority_changed": "Приоритет обращения обновлён.",
    "priority_overridden": "Приоритет обращения обновлён.",
    "classification_changed": "Категория обращения уточнена.",
    "requester_profile_changed": "Контактные данные по обращению обновлены.",
    "device_changed": "Устройство по обращению обновлено.",
    "sla_started": "Сроки обращения рассчитаны.",
    "sla_warning": "Есть риск нарушения срока. Поддержка получила уведомление.",
    "sla_breached": "Срок нарушен. Обращение требует внимания поддержки.",
    "sla_first_response_stopped": "Первый ответ получен.",
    "sla_resolution_stopped": "Срок решения остановлен.",
    "tool_call_started": "Специалист запустил диагностику.",
    "diagnostic_result_classified": "Результат диагностики обработан.",
    "playbook_started": "Запущена диагностика по обращению.",
    "approval_approved": "Согласование получено.",
    "approval_rejected": "Согласование отклонено.",
    "approval_escalated": "Согласование передано ответственному специалисту.",
    "approval_timed_out": "Срок согласования истёк.",
    "passport_generated": "Подготовлены материалы по решению.",
}

REQUESTER_FLAGGED_EVENT_TEXT: dict[str, str] = {
    "approval_reminder_due": "Ожидается согласование.",
    "passport_evidence_added": "Материалы по решению обновлены.",
    "passport_evidence_linked": "Материалы по решению обновлены.",
    "passport_evidence_verified": "Материалы по решению проверены.",
    "passport_evidence_rejected": "Материалы по решению требуют уточнения.",
    "passport_evidence_archived": "Материалы по решению обновлены.",
    "passport_evidence_superseded": "Материалы по решению обновлены.",
    "passport_evidence_unverified": "Материалы по решению требуют проверки.",
    "operation_retried": "Диагностика запущена повторно.",
    "operation_retry_consent_requested": "Для повторной диагностики требуется подтверждение.",
}

HIDDEN_EVENT_TYPES = {
    "ticket_updated",
    "ticket_refreshed",
    "internal_note",
    "worklog_added",
    "message_read",
    "external_notification_delivery",
    "policy_action_dispatched",
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

HIDDEN_PREFIXES = (
    "raw_",
    "debug_",
    "observer_",
    "internal_",
    "tool_log",
    "protocol_",
    "auth_",
)

SUPPORT_ROLES = {"support", "admin", "staff", "operator"}
USER_ROLES = {"user", "requester", "agent", "device", "client"}
STATUS_FIELDS = ("new_status", "status", "to_status", "new_value", "value")


def build_requester_timeline_projection(
    event: object | dict[str, Any],
    ticket: object | None = None,
) -> RequesterTimelineProjection | None:
    """Build a safe Russian requester-facing projection for a ticket event."""

    payload = _payload(event)
    event_type = _event_type(event, payload)
    if not event_type:
        return None
    if _is_hidden_event_type(event_type):
        return None

    if event_type == "chat_message":
        return _project_chat_message(event, payload)
    if event_type == "status_changed":
        return _project_status_changed(event, payload)
    if event_type == "assignee_changed":
        return _project_assignee_changed(event, payload)
    if event_type == "tool_call_result":
        return _project_tool_call_result(event, payload)
    if event_type in {"attachment_uploaded", "attachment_added"}:
        return _project_attachment_event(event, payload)
    if event_type in SYSTEM_EVENT_TEXT:
        return RequesterTimelineProjection(SYSTEM_EVENT_TEXT[event_type], "system_event", _safe_event_payload(event_type, event, payload))
    if event_type in REQUESTER_FLAGGED_EVENT_TEXT and _requester_visible_flag(payload):
        return RequesterTimelineProjection(REQUESTER_FLAGGED_EVENT_TEXT[event_type], "system_event", _safe_event_payload(event_type, event, payload))
    return None


def is_requester_visible_timeline_event(event_type: str, payload: Mapping[str, Any] | None) -> bool:
    event = {"event_type": event_type, "payload": dict(payload or {})}
    return build_requester_timeline_projection(event) is not None


def projection_to_fields(projection: RequesterTimelineProjection | None) -> dict[str, Any]:
    if projection is None:
        return {
            "requester_timeline_text": None,
            "requester_timeline_kind": None,
            "requester_timeline_payload": None,
            "requester_timeline_icon": None,
            "requester_timeline_style": None,
        }
    return {
        "requester_timeline_text": projection.text,
        "requester_timeline_kind": projection.kind,
        "requester_timeline_payload": projection.payload,
        "requester_timeline_icon": projection.icon,
        "requester_timeline_style": projection.style,
    }


def _project_chat_message(event: object | dict[str, Any], payload: Mapping[str, Any]) -> RequesterTimelineProjection | None:
    raw_visibility = _field(event, payload, "visibility")
    visibility = _clean(raw_visibility).lower() if raw_visibility is not None else "public"
    if visibility != "public":
        return None

    if is_public_access_message_payload(payload):
        return RequesterTimelineProjection(
            "Код доступа к обращению сформирован.",
            "system_event",
            {"message_kind": "ticket_access_notice"},
        )

    attachments = _safe_attachments(payload.get("attachments") or payload.get("attachment_refs") or [])
    text = _clean(_field(event, payload, "text", "message", "body"))
    role = _clean(_field(event, payload, "sender_role", "from_role", "from", "role")).lower()
    safe_payload: dict[str, Any] = {}
    if attachments:
        safe_payload["attachments"] = attachments

    if attachments and not text:
        return RequesterTimelineProjection("Добавлено вложение.", "attachment", safe_payload)
    if role in SUPPORT_ROLES:
        return RequesterTimelineProjection(text or "Сообщение поддержки.", "support_message", safe_payload)
    if role == "system":
        return RequesterTimelineProjection(text or "Системное сообщение.", "system_event", safe_payload)
    if role in USER_ROLES or not role:
        return RequesterTimelineProjection(text or "Сообщение пользователя.", "user_message", safe_payload)
    return None


def _project_status_changed(event: object | dict[str, Any], payload: Mapping[str, Any]) -> RequesterTimelineProjection:
    status = _normalize_key(_field(event, payload, *STATUS_FIELDS))
    text = STATUS_TEXT.get(status, "Статус обращения обновлён.")
    safe_payload = {"status": status} if status in STATUS_TEXT else {}
    return RequesterTimelineProjection(text, "system_event", safe_payload)


def _project_assignee_changed(event: object | dict[str, Any], payload: Mapping[str, Any]) -> RequesterTimelineProjection:
    assignee = _clean(
        _field(
            event,
            payload,
            "new_assignee_display_name",
            "assignee_display_name",
            "new_assignee_name",
            "assignee_name",
            "new_assignee",
            "new_value",
        )
    )
    if assignee and assignee.lower() not in {"none", "null", "unassigned", "unknown"}:
        return RequesterTimelineProjection(
            f"Назначен исполнитель: {assignee}.",
            "system_event",
            {"assignee_display_name": assignee},
        )
    return RequesterTimelineProjection(
        "Обращение вернулось в очередь поддержки.",
        "system_event",
        {},
    )


def _project_tool_call_result(event: object | dict[str, Any], payload: Mapping[str, Any]) -> RequesterTimelineProjection:
    checks = _compact_diagnostic_checks(payload)
    safe_payload = {"checks": checks} if checks else {}
    return RequesterTimelineProjection("Выполнена диагностика", "diagnostic_result", safe_payload)


def _project_attachment_event(event: object | dict[str, Any], payload: Mapping[str, Any]) -> RequesterTimelineProjection:
    attachments = _safe_attachments(payload.get("attachments") or [payload])
    return RequesterTimelineProjection(
        "Добавлено вложение.",
        "attachment",
        {"attachments": attachments} if attachments else {},
    )


def _safe_event_payload(event_type: str, event: object | dict[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    if event_type in {"queue_changed", "routing_applied"}:
        queue_name = _clean(_field(event, payload, "queue_name", "new_queue_name", "target_queue_name"))
        return {"queue_name": queue_name} if queue_name else {}
    if event_type in {"priority_changed", "priority_overridden"}:
        priority_label = _clean(_field(event, payload, "priority_label", "new_priority_label"))
        return {"priority_label": priority_label} if priority_label else {}
    return {}


def _payload(event: object | dict[str, Any]) -> Mapping[str, Any]:
    if isinstance(event, Mapping):
        raw = event.get("payload")
        return raw if isinstance(raw, Mapping) else event
    raw = getattr(event, "payload", None)
    return raw if isinstance(raw, Mapping) else {}


def _event_type(event: object | dict[str, Any], payload: Mapping[str, Any]) -> str:
    raw = None
    if isinstance(event, Mapping):
        raw = event.get("event_type") or event.get("type")
    else:
        raw = getattr(event, "event_type", None) or getattr(event, "type", None)
    event_type = _normalize_key(raw)
    payload_type = _normalize_key(payload.get("event_type") or payload.get("type") or payload.get("event"))
    if event_type in {"", "ticket_event"} and payload_type:
        return payload_type
    if event_type in {"ticket_updated", "ticket_refreshed"} and payload_type in _known_projectable_event_types():
        return payload_type
    return event_type


def _field(event: object | dict[str, Any], payload: Mapping[str, Any], *names: str) -> Any:
    event_details = payload.get("event_details")
    if not isinstance(event_details, Mapping):
        event_details = payload.get("details") if isinstance(payload.get("details"), Mapping) else None
    top_level_details = None
    if isinstance(event, Mapping):
        top_level_details = event.get("event_details")

    sources: list[Mapping[str, Any]] = [payload]
    if isinstance(event_details, Mapping):
        sources.append(event_details)
    if isinstance(top_level_details, Mapping):
        sources.append(top_level_details)
    if isinstance(event, Mapping):
        sources.append(event)

    for source in sources:
        for name in names:
            if name in source and source.get(name) is not None:
                return source.get(name)
    return None


def _compact_diagnostic_checks(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    candidates: list[Any] = []
    for source in _diagnostic_sources(payload):
        for key in ("checks", "steps", "diagnostics", "observations"):
            value = source.get(key) if isinstance(source, Mapping) else None
            if isinstance(value, list):
                candidates = value
                break
        if candidates:
            break

    checks: list[dict[str, str]] = []
    for item in candidates[:10]:
        check = _compact_diagnostic_check(item)
        if check:
            checks.append(check)
    return checks


def _diagnostic_sources(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = [payload]
    for key in ("result", "diagnostic", "diagnostics"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            sources.append(value)
    return sources


def _compact_diagnostic_check(item: Any) -> dict[str, str] | None:
    if not isinstance(item, Mapping):
        label = _clean(item)
        return {"label": label, "status": "info", "summary": ""} if label else None

    label = _clean(item.get("label") or item.get("title") or item.get("name") or item.get("check") or item.get("key"))
    if not label:
        return None
    status = _normalize_check_status(item)
    summary = _clean(item.get("summary") or item.get("message") or item.get("text") or item.get("description"))
    compact = {"label": label, "status": status}
    if summary:
        compact["summary"] = summary
    return compact


def _normalize_check_status(item: Mapping[str, Any]) -> str:
    if item.get("ok") is True or item.get("success") is True or item.get("passed") is True:
        return "ok"
    if item.get("ok") is False or item.get("success") is False or item.get("passed") is False:
        return "failed"
    status = _normalize_key(item.get("status") or item.get("state") or item.get("result"))
    if status in {"ok", "pass", "passed", "success", "successful", "healthy"}:
        return "ok"
    if status in {"fail", "failed", "error", "critical", "unhealthy"}:
        return "failed"
    if status in {"warning", "warn", "degraded"}:
        return "warning"
    return "info"


def _safe_attachments(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else [value]
    attachments: list[dict[str, Any]] = []
    for item in items[:10]:
        if isinstance(item, Mapping):
            name = _clean(item.get("name") or item.get("filename") or item.get("file_name") or item.get("title"))
            size_label = _clean(item.get("size_label") or item.get("human_size"))
            safe: dict[str, Any] = {}
            if name:
                safe["name"] = name
            if size_label:
                safe["size_label"] = size_label
            if _safe_url(item.get("url")):
                safe["url"] = _clean(item.get("url"))
            if safe:
                attachments.append(safe)
        else:
            name = _clean(item)
            if name:
                attachments.append({"name": name})
    return attachments


def _safe_url(value: Any) -> bool:
    url = _clean(value)
    if not url:
        return False
    lowered = url.lower()
    if "token=" in lowered or "access_code=" in lowered or "secret" in lowered:
        return False
    return lowered.startswith(("/api/", "/attachments/", "http://", "https://"))


def _requester_visible_flag(payload: Mapping[str, Any]) -> bool:
    value = payload.get("requester_visible")
    if value is True:
        return True
    visibility = _clean(payload.get("visibility") or payload.get("export_visibility")).lower()
    return visibility == "public"


def _is_hidden_event_type(event_type: str) -> bool:
    if event_type in HIDDEN_EVENT_TYPES:
        return True
    return any(event_type.startswith(prefix) for prefix in HIDDEN_PREFIXES)


def _known_projectable_event_types() -> set[str]:
    return {
        "chat_message",
        "status_changed",
        "assignee_changed",
        "tool_call_result",
        "attachment_uploaded",
        "attachment_added",
        *SYSTEM_EVENT_TEXT.keys(),
        *REQUESTER_FLAGGED_EVENT_TEXT.keys(),
    }


def _normalize_key(value: Any) -> str:
    return _clean(value).strip().lower().replace("-", "_").replace(" ", "_")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return " ".join(text.split())


__all__ = [
    "RequesterTimelineKind",
    "RequesterTimelineProjection",
    "build_requester_timeline_projection",
    "is_requester_visible_timeline_event",
    "projection_to_fields",
]
