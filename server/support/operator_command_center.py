from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from web_api.dto.support import (
    CommandCenterAgentState,
    CommandCenterClosureState,
    CommandCenterDiagnosticsState,
    CommandCenterItem,
    CommandCenterOperationState,
    CommandCenterSection,
    CommandCenterSectionAction,
    CommandCenterSimilarGroup,
    CommandCenterTimerState,
    OperatorCommandCenterFilters,
    OperatorCommandCenterPayload,
    OperatorCommandCenterSummary,
    SupportQueueTicketItem,
)


ACTIVE_STATUSES = {
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
}
TERMINAL_STATUSES = {"resolved", "closed", "canceled"}
HIGH_PRIORITIES = {"p1", "p2", "critical", "high"}
SPIKE_THRESHOLD = 3
_JUNK_DISPLAY_MARKERS = (
    "???",
    "\ufffd",
    "\u00d0",
    "\u00d1",
    "\u0420\u045c",
    "\u0420\u045a",
    "\u0420\u0452",
    "\u0420\u0098",
    "\u0420\u040e",
    "\u0420\u045f",
    "\u0420\u045b",
    "\u0420\u2018",
    "\u0420\u201d",
    "\u0421\u0403",
    "\u0421\u201a",
    "\u0421\u040a",
    "\u0421\u040f",
)


@dataclass(frozen=True)
class SectionSpec:
    title: str
    description: str
    default_severity: str
    action_href: str = "/app/tickets"


@dataclass(frozen=True)
class ApprovalBatchSource:
    pending_count: int = 0
    requested_count: int = 0
    timed_out_count: int = 0
    current_approver: str | None = None
    latest_requested_at: datetime | None = None


@dataclass(frozen=True)
class DiagnosticBatchSource:
    evidence_count: int = 0
    error_evidence_count: int = 0
    warning_evidence_count: int = 0
    latest_evidence_at: datetime | None = None
    open_session_count: int = 0
    failed_session_count: int = 0
    latest_profile_code: str | None = None
    latest_session_status: str | None = None


SECTION_SPECS: dict[str, SectionSpec] = {
    "new_unassigned": SectionSpec(
        "Новые без владельца",
        "Активные тикеты без назначенного исполнителя.",
        "warning",
        "/app/tickets?smart_view=unassigned",
    ),
    "operator_action": SectionSpec(
        "Требует действия оператора",
        "Следующее действие находится на стороне поддержки или уже просрочено.",
        "warning",
        "/app/tickets?smart_view=requires_operator_action",
    ),
    "unread_user_messages": SectionSpec(
        "Новые сообщения пользователя",
        "Пользователь ответил, и сообщение еще требует реакции оператора.",
        "warning",
        "/app/tickets?smart_view=unread_user_messages",
    ),
    "sla_risk": SectionSpec(
        "SLA риск",
        "Срок ответа или решения близок к нарушению либо уже нарушен.",
        "warning",
        "/app/tickets?smart_view=sla_risk",
    ),
    "ola_risk": SectionSpec(
        "OLA риск",
        "Внутренний срок очереди близок к нарушению либо уже нарушен.",
        "warning",
        "/app/tickets?smart_view=ola_risk",
    ),
    "pending_approval": SectionSpec(
        "Ожидает согласования",
        "Тикеты, заблокированные согласованием.",
        "warning",
        "/app/support/approvals?kind=pending_approval",
    ),
    "pending_consent": SectionSpec(
        "Ожидает согласия",
        "Операция или удаленная помощь ожидает согласия пользователя.",
        "warning",
        "/app/support/approvals?kind=pending_consent",
    ),
    "failed_operation": SectionSpec(
        "Ошибки операций",
        "Последняя связанная операция завершилась ошибкой.",
        "warning",
    ),
    "agent_offline_active": SectionSpec(
        "Агент offline",
        "Активный тикет связан с устройством, агент которого недоступен.",
        "warning",
    ),
    "diagnostics_recommended": SectionSpec(
        "Рекомендована диагностика",
        "Политика, статус диагностики или требования к доказательствам требуют диагностического запуска.",
        "info",
    ),
    "closure_blocked": SectionSpec(
        "Блокеры закрытия",
        "Не хватает фактов, доказательств или итогов решения для закрытия.",
        "warning",
    ),
    "similar_tickets_spike": SectionSpec(
        "Похожие обращения / всплеск",
        "За выбранное окно обнаружены группы похожих активных тикетов.",
        "warning",
    ),
}


def parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso_datetime(value: Any) -> str | None:
    parsed = parse_iso_datetime(value)
    return parsed.astimezone(timezone.utc).isoformat() if parsed else None


def _is_active(ticket_data: dict[str, Any], item: SupportQueueTicketItem) -> bool:
    status = str(ticket_data.get("status") or item.status or "").strip()
    return status in ACTIVE_STATUSES and status not in TERMINAL_STATUSES


def _priority_is_high(value: Any) -> bool:
    return str(value or "").strip().lower() in HIGH_PRIORITIES


def _matches_query(ticket_data: dict[str, Any], item: SupportQueueTicketItem, query: str | None) -> bool:
    needle = str(query or "").strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        str(value or "")
        for value in (
            item.ticket_code,
            item.ticket_id,
            item.title,
            item.status,
            item.queue_code,
            item.assignee_id,
            item.assignee_display_name,
            item.requester_display_name,
            ticket_data.get("device_id"),
            ticket_data.get("service_code"),
            ticket_data.get("offering_code"),
            ticket_data.get("reporting_category"),
        )
    ).lower()
    return needle in haystack


def _clean_display_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text or any(marker in text for marker in _JUNK_DISPLAY_MARKERS):
        return fallback
    return text


def _search_href(search_text: str) -> str:
    value = str(search_text or "").strip()
    return "/app/tickets" if not value else f"/app/tickets?search={quote(value)}"


def _timer_state(
    ticket_data: dict[str, Any],
    *,
    due_fields: tuple[str, ...],
    breached_fields: tuple[str, ...],
    risk_minutes: int,
    now: datetime,
) -> CommandCenterTimerState | None:
    breached_at = next((parse_iso_datetime(ticket_data.get(field)) for field in breached_fields if ticket_data.get(field)), None)
    due_at = next((parse_iso_datetime(ticket_data.get(field)) for field in due_fields if ticket_data.get(field)), None)
    if due_at is None and breached_at is None:
        return None
    effective_due = due_at or breached_at
    remaining = int((effective_due - now).total_seconds()) if effective_due else None
    state = "ok"
    if breached_at is not None or (remaining is not None and remaining < 0):
        state = "breached"
    elif remaining is not None and remaining <= max(0, risk_minutes) * 60:
        state = "risk"
    return CommandCenterTimerState(
        state=state,
        due_at=effective_due.isoformat() if effective_due else None,
        remaining_seconds=remaining,
    )


def _operation_state(operation: Any | None) -> CommandCenterOperationState | None:
    if operation is None:
        return None
    status = str(getattr(operation, "status", None) or "").strip() or None
    failed_at = getattr(operation, "finished_at", None) or getattr(operation, "queued_at", None)
    return CommandCenterOperationState(
        id=str(getattr(operation, "operation_id", "") or "") or None,
        status=status,
        tool_name=getattr(operation, "tool_name", None) or getattr(operation, "command_name", None),
        failed_at=iso_datetime(failed_at),
        error_summary=getattr(operation, "error_message", None) or getattr(operation, "error_code", None),
    )


def _agent_state(ticket_data: dict[str, Any], device: Any | None, now: datetime) -> CommandCenterAgentState | None:
    device_id = str(ticket_data.get("device_id") or "").strip()
    if not device_id:
        return None
    last_seen_at = parse_iso_datetime(getattr(device, "last_seen_at", None)) if device is not None else None
    custom_fields = ticket_data.get("custom_fields") if isinstance(ticket_data.get("custom_fields"), dict) else {}
    inventory_context = custom_fields.get("inventory_context") if isinstance(custom_fields, dict) else None
    signals = inventory_context.get("signals") if isinstance(inventory_context, dict) else None
    explicit_offline = bool(signals.get("agent_offline")) if isinstance(signals, dict) else False
    if explicit_offline:
        state = "offline"
    elif last_seen_at is None:
        state = "unknown"
    elif (now - last_seen_at) > timedelta(minutes=5):
        state = "offline"
    else:
        state = "online"
    return CommandCenterAgentState(
        device_id=device_id,
        connection_state=state,
        last_seen_at=last_seen_at.isoformat() if last_seen_at else None,
    )


def _approval_reason(approval: ApprovalBatchSource | None) -> str | None:
    if approval is None or (approval.pending_count + approval.requested_count + approval.timed_out_count) <= 0:
        return None
    if approval.timed_out_count:
        return f"Согласование просрочено: {approval.timed_out_count}"
    if approval.current_approver:
        return f"Ожидается согласование от {approval.current_approver}"
    return f"Ожидает согласования: {approval.pending_count + approval.requested_count}"


def _diagnostics_state(
    ticket_data: dict[str, Any],
    diagnostics_source: DiagnosticBatchSource | None = None,
) -> CommandCenterDiagnosticsState | None:
    custom_fields = ticket_data.get("custom_fields") if isinstance(ticket_data.get("custom_fields"), dict) else {}
    diagnostics = custom_fields.get("diagnostics") if isinstance(custom_fields, dict) else None
    policy = custom_fields.get("diagnostic_policy") if isinstance(custom_fields, dict) else None
    has_diagnostic_evidence = bool(diagnostics_source and diagnostics_source.evidence_count > 0)
    if diagnostics_source and diagnostics_source.failed_session_count:
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=diagnostics_source.latest_profile_code,
            reason="Диагностическая сессия завершилась ошибкой",
        )
    if diagnostics_source and diagnostics_source.error_evidence_count:
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=diagnostics_source.latest_profile_code,
            reason="Диагностические данные содержат ошибки",
        )
    if diagnostics_source and diagnostics_source.open_session_count and not has_diagnostic_evidence:
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=diagnostics_source.latest_profile_code,
            reason="Есть открытая диагностическая сессия без подтверждающих данных",
        )
    if isinstance(policy, dict) and (policy.get("recommended") or policy.get("profile_code")):
        if has_diagnostic_evidence:
            return None
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=str(policy.get("profile_code") or "").strip() or None,
            reason=str(policy.get("reason") or "Политика рекомендует диагностический запуск"),
        )
    if isinstance(diagnostics, dict) and str(diagnostics.get("status") or "").strip() in {"recommended", "failed"}:
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=str(diagnostics.get("profile_code") or "").strip() or None,
            reason=str(diagnostics.get("reason") or "Диагностический статус требует внимания"),
        )
    if bool(ticket_data.get("evidence_required")) and not str(ticket_data.get("evidence_ref") or "").strip() and not has_diagnostic_evidence:
        return CommandCenterDiagnosticsState(
            recommended=True,
            profile_code=diagnostics_source.latest_profile_code if diagnostics_source else None,
            reason="Для закрытия требуется диагностическое подтверждение",
        )
    return None


def _closure_state(ticket_data: dict[str, Any], passport: Any | None) -> CommandCenterClosureState | None:
    missing: list[str] = []
    status = str(ticket_data.get("status") or "").strip()
    if status not in {"in_progress", "resolved", "waiting_on_user", "waiting_on_internal_team", "waiting_on_vendor"}:
        return None
    if not str(ticket_data.get("resolution_code") or "").strip():
        missing.append("код решения")
    if not str(ticket_data.get("resolution_summary") or "").strip():
        missing.append("описание решения")
    if bool(ticket_data.get("evidence_required")) and not str(ticket_data.get("evidence_ref") or "").strip():
        missing.append("доказательство")
    if passport is not None and str(getattr(passport, "status", "") or "") in {"draft", "needs_review"}:
        missing.append("готовый паспорт решения")
    if not missing:
        return None
    return CommandCenterClosureState(blocked=True, missing_count=len(missing), primary_blocker=missing[0])


def _base_item(
    ticket_data: dict[str, Any],
    item: SupportQueueTicketItem,
    *,
    reason: str,
    suffix: str,
    sla: CommandCenterTimerState | None,
    ola: CommandCenterTimerState | None,
    operation: CommandCenterOperationState | None,
    agent: CommandCenterAgentState | None,
    diagnostics: CommandCenterDiagnosticsState | None,
    closure: CommandCenterClosureState | None,
) -> CommandCenterItem:
    return CommandCenterItem(
        id=f"{item.ticket_id}:{suffix}",
        ticket_id=item.ticket_id,
        ticket_number=item.ticket_code,
        title=_clean_display_text(item.title, "Без названия"),
        status=item.status,
        priority=item.priority,
        queue=item.queue_code,
        assignee=item.assignee_display_name or item.assignee_id,
        requester_name=_clean_display_text(item.requester_display_name, "Пользователь не указан"),
        service_code=str(ticket_data.get("service_code") or "").strip() or None,
        offering_code=str(ticket_data.get("offering_code") or "").strip() or None,
        created_at=item.created_at,
        updated_at=item.updated_at,
        next_action_owner=item.next_action_owner,
        next_action_due_at=item.next_action_due_at,
        requires_operator_action=item.requires_operator_action,
        unread_user_messages=item.unread_user_messages,
        sla=sla,
        ola=ola,
        operation=operation,
        agent=agent,
        diagnostics=diagnostics,
        closure=closure,
        reason=reason,
        href=f"/app/tickets/{item.ticket_id}",
    )


def _normalize_title(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"\b(?:t|inc|req|ticket)[-_\s]*\d+\b", " ", text)
    text = re.sub(r"\b[0-9a-f]{8,}\b", " ", text)
    text = re.sub(r"[^\w\sа-яё-]+", " ", text, flags=re.IGNORECASE)
    tokens = [token for token in re.split(r"\s+", text) if len(token) > 2]
    return " ".join(tokens[:8])


def _similar_group_key(ticket_data: dict[str, Any], item: SupportQueueTicketItem) -> str | None:
    custom_fields = ticket_data.get("custom_fields") if isinstance(ticket_data.get("custom_fields"), dict) else {}
    template = str(custom_fields.get("request_template_code") or custom_fields.get("request_template_key") or "").strip()
    title = _normalize_title(item.title)
    if template:
        return f"template:{template}"
    service_code = str(ticket_data.get("service_code") or "").strip()
    category = str(ticket_data.get("reporting_category") or ticket_data.get("category_id") or "").strip()
    if service_code and title:
        return f"service:{service_code}|category:{category}|title:{title}"
    if title:
        return f"title:{title}"
    return None


def _build_section(key: str, items: list[CommandCenterItem], count: int, severity: str | None = None) -> CommandCenterSection:
    spec = SECTION_SPECS[key]
    updated_values = [parse_iso_datetime(item.updated_at) for item in items if item.updated_at]
    updated_at = max((value for value in updated_values if value is not None), default=None)
    return CommandCenterSection(
        key=key,
        title=spec.title,
        description=spec.description,
        severity=severity or spec.default_severity,
        count=count,
        updated_at=updated_at.isoformat() if updated_at else None,
        items=items,
        action=CommandCenterSectionAction(label="Открыть в очереди", href=spec.action_href),
    )


def build_operator_command_center_payload(
    entries: list[tuple[dict[str, Any], SupportQueueTicketItem]],
    *,
    operations_by_ticket: dict[str, Any] | None = None,
    devices_by_id: dict[str, Any] | None = None,
    passports_by_ticket: dict[str, Any] | None = None,
    approvals_by_ticket: dict[str, ApprovalBatchSource] | None = None,
    diagnostics_by_ticket: dict[str, DiagnosticBatchSource] | None = None,
    scope: str,
    queue: str | None,
    assignee: str | None,
    query: str | None = None,
    limit_per_section: int,
    window_hours: int,
    sla_risk_minutes: int,
    ola_risk_minutes: int,
    generated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> OperatorCommandCenterPayload:
    now = generated_at or datetime.now(timezone.utc)
    operations_by_ticket = operations_by_ticket or {}
    devices_by_id = devices_by_id or {}
    passports_by_ticket = passports_by_ticket or {}
    approvals_by_ticket = approvals_by_ticket or {}
    diagnostics_by_ticket = diagnostics_by_ticket or {}
    limit = max(1, int(limit_per_section))
    filtered_entries = [
        (ticket_data, item)
        for ticket_data, item in entries
        if _is_active(ticket_data, item)
        and (not queue or str(item.queue_code or "").strip() == queue)
        and (not assignee or str(item.assignee_id or "").strip() == assignee)
        and _matches_query(ticket_data, item, query)
    ]

    section_items: dict[str, list[CommandCenterItem]] = {key: [] for key in SECTION_SPECS}
    section_total_counts: dict[str, int] = {key: 0 for key in SECTION_SPECS}
    section_has_critical: dict[str, bool] = {key: False for key in SECTION_SPECS}
    attention_ids: set[str] = set()

    for ticket_data, item in filtered_entries:
        operation = _operation_state(operations_by_ticket.get(item.ticket_id))
        agent = _agent_state(ticket_data, devices_by_id.get(str(ticket_data.get("device_id") or "")), now)
        approval = approvals_by_ticket.get(item.ticket_id)
        diagnostics = _diagnostics_state(ticket_data, diagnostics_by_ticket.get(item.ticket_id))
        closure = _closure_state(ticket_data, passports_by_ticket.get(item.ticket_id))
        sla = _timer_state(
            ticket_data,
            due_fields=("first_response_due_at", "resolution_due_at"),
            breached_fields=("first_response_breached_at", "resolution_breached_at"),
            risk_minutes=sla_risk_minutes,
            now=now,
        )
        ola = _timer_state(
            ticket_data,
            due_fields=("ola_ack_due_at", "ola_processing_due_at"),
            breached_fields=("ola_ack_breached_at", "ola_processing_breached_at"),
            risk_minutes=ola_risk_minutes,
            now=now,
        )

        high_priority = _priority_is_high(item.priority)
        next_due = parse_iso_datetime(item.next_action_due_at)
        next_overdue = bool(next_due and next_due <= now)
        sla_bad = sla is not None and sla.state in {"risk", "breached"}
        ola_bad = ola is not None and ola.state in {"risk", "breached"}

        def add(key: str, reason: str, suffix: str, critical: bool = False) -> None:
            section_total_counts[key] += 1
            attention_ids.add(item.ticket_id)
            if critical:
                section_has_critical[key] = True
            if len(section_items[key]) < limit:
                section_items[key].append(
                    _base_item(
                        ticket_data,
                        item,
                        reason=reason,
                        suffix=suffix,
                        sla=sla,
                        ola=ola,
                        operation=operation,
                        agent=agent,
                        diagnostics=diagnostics,
                        closure=closure,
                    )
                )

        if not str(item.assignee_id or "").strip():
            add(
                "new_unassigned",
                "Активный тикет еще не назначен исполнителю",
                "new_unassigned",
                critical=high_priority or (sla is not None and sla.state == "breached"),
            )
        if item.requires_operator_action or str(item.next_action_owner or "").strip() in {"support", "operator", "assignee"}:
            add(
                "operator_action",
                "Следующее действие находится на стороне поддержки",
                "operator_action",
                critical=next_overdue,
            )
        if int(item.unread_user_messages or 0) > 0:
            add(
                "unread_user_messages",
                f"Непрочитанных сообщений пользователя: {item.unread_user_messages}",
                "unread_user_messages",
                critical=next_overdue or (sla is not None and sla.state == "breached"),
            )
        if sla_bad:
            add(
                "sla_risk",
                "SLA уже нарушен" if sla and sla.state == "breached" else "SLA скоро будет нарушен",
                "sla_risk",
                critical=sla is not None and sla.state == "breached",
            )
        if ola_bad:
            add(
                "ola_risk",
                "OLA уже нарушен" if ola and ola.state == "breached" else "OLA скоро будет нарушен",
                "ola_risk",
                critical=ola is not None and ola.state == "breached",
            )
        approval_reason = _approval_reason(approval)
        if item.status == "waiting_on_approval" or approval_reason:
            add(
                "pending_approval",
                approval_reason or "Тикет ожидает согласования",
                "pending_approval",
                critical=bool(approval and approval.timed_out_count) or sla_bad or ola_bad,
            )
        if operation is not None and operation.status == "waiting_consent":
            add(
                "pending_consent",
                "Операция ожидает согласия пользователя",
                "pending_consent",
                critical=next_overdue,
            )
        if operation is not None and operation.status in {"failed", "timed_out", "denied"}:
            add(
                "failed_operation",
                operation.error_summary or "Последняя операция завершилась ошибкой",
                "failed_operation",
                critical=high_priority,
            )
        if agent is not None and agent.connection_state in {"offline", "unknown"}:
            needs_agent = diagnostics is not None or operation is not None or item.status in {"in_progress", "assigned"}
            if needs_agent:
                add(
                    "agent_offline_active",
                    "Агент устройства недоступен для активного тикета",
                    "agent_offline_active",
                    critical=high_priority or diagnostics is not None,
                )
        if diagnostics is not None and diagnostics.recommended:
            add(
                "diagnostics_recommended",
                diagnostics.reason or "Рекомендован диагностический запуск",
                "diagnostics_recommended",
                critical=False,
            )
        if closure is not None and closure.blocked:
            add(
                "closure_blocked",
                f"Закрытие заблокировано: {closure.primary_blocker}",
                "closure_blocked",
                critical=sla_bad,
            )

    window_start = now - timedelta(hours=max(1, int(window_hours)))
    groups: dict[str, list[tuple[dict[str, Any], SupportQueueTicketItem]]] = {}
    for ticket_data, item in filtered_entries:
        updated_at = parse_iso_datetime(item.updated_at) or parse_iso_datetime(item.created_at)
        if updated_at is not None and updated_at < window_start:
            continue
        key = _similar_group_key(ticket_data, item)
        if not key:
            continue
        groups.setdefault(key, []).append((ticket_data, item))
    for group_key, group_entries in groups.items():
        if len(group_entries) < SPIKE_THRESHOLD:
            continue
        group_entries = sorted(group_entries, key=lambda pair: pair[1].updated_at or "", reverse=True)
        sample_ids = [pair[1].ticket_id for pair in group_entries[:5]]
        representative_data, representative_item = group_entries[0]
        section_total_counts["similar_tickets_spike"] += 1
        attention_ids.add(group_key)
        if len(section_items["similar_tickets_spike"]) < limit:
            search_text = representative_item.title or _normalize_title(representative_item.title) or group_key
            similar_group = CommandCenterSimilarGroup(
                group_key=group_key,
                count=len(group_entries),
                window_hours=window_hours,
                sample_ticket_ids=sample_ids,
                reason=f"Найдено {len(group_entries)} похожих активных тикета за {window_hours} ч.",
            )
            section_items["similar_tickets_spike"].append(
                _base_item(
                    representative_data,
                    representative_item,
                    reason=similar_group.reason,
                    suffix=f"similar:{group_key}",
                    sla=None,
                    ola=None,
                    operation=None,
                    agent=None,
                    diagnostics=None,
                    closure=None,
                ).model_copy(update={"similar_group": similar_group, "href": _search_href(search_text)})
            )

    sections: list[CommandCenterSection] = []
    for key in SECTION_SPECS:
        severity = "critical" if section_has_critical[key] else SECTION_SPECS[key].default_severity
        sections.append(_build_section(key, section_items[key], section_total_counts[key], severity=severity))

    summary = OperatorCommandCenterSummary(
        total_attention_items=len(attention_ids),
        critical_count=sum(section.count for section in sections if section.severity == "critical"),
        warning_count=sum(section.count for section in sections if section.severity == "warning"),
        info_count=sum(section.count for section in sections if section.severity == "info"),
        new_unassigned_count=section_total_counts["new_unassigned"],
        operator_action_count=section_total_counts["operator_action"],
        unread_user_messages_count=section_total_counts["unread_user_messages"],
        sla_risk_count=section_total_counts["sla_risk"],
        ola_risk_count=section_total_counts["ola_risk"],
        pending_approval_count=section_total_counts["pending_approval"],
        pending_consent_count=section_total_counts["pending_consent"],
        failed_operation_count=section_total_counts["failed_operation"],
        agent_offline_active_count=section_total_counts["agent_offline_active"],
        diagnostics_recommended_count=section_total_counts["diagnostics_recommended"],
        closure_blocked_count=section_total_counts["closure_blocked"],
        similar_spikes_count=section_total_counts["similar_tickets_spike"],
    )
    return OperatorCommandCenterPayload(
        generated_at=now.isoformat(),
        scope=scope,
        filters=OperatorCommandCenterFilters(
            queue=queue,
            assignee=assignee,
            query=query,
            window_hours=window_hours,
            limit_per_section=limit,
        ),
        summary=summary,
        sections=sections,
        metadata=metadata or {},
    )
