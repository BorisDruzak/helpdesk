from __future__ import annotations

from datetime import date, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Operation,
    PlaybookRun,
    Ticket,
    TicketActionLog,
    TicketApproval,
    TicketEvent,
    TicketEvidenceItem,
    TicketRelatedObject,
    TicketResolutionPassport,
    TicketWorklog,
)
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.ticket_passport_repo import TicketPassportRepo
from tickets.diagnostic_policy import materialize_diagnostic_operation_evidence
from tickets.evidence_service import TicketEvidenceService
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
from tickets.statuses import get_requester_display_name, get_requester_profile


SECTION_KEYS = {
    "requester": "requester_summary",
    "problem": "problem_summary",
    "affected_object": "affected_object_summary",
    "automated_checks": "automated_checks_summary",
    "operator_checks": "operator_checks_summary",
    "changes_made": "changes_made_summary",
    "approvals": "approvals_summary",
    "evidence": "evidence_summary",
    "user_result": "user_result_summary",
    "internal_result": "internal_result_summary",
    "repeat_guidance": "repeat_guidance",
}

PASSPORT_REQUIREMENT_LABELS = {
    "requester": "Заявитель",
    "problem": "Описание проблемы",
    "affected_object": "Затронутый объект",
    "automated_checks": "Автоматические проверки",
    "operator_checks": "Проверки оператора",
    "changes_made": "Выполненные действия",
    "approvals": "Согласования",
    "evidence": "Доказательство решения",
    "user_result": "Итог для пользователя",
    "internal_result": "Внутренний итог",
    "repeat_guidance": "Инструкция при повторе",
}

PASSPORT_REQUIREMENT_SOURCES = {
    "requester": "ticket.requester_id",
    "problem": "ticket.title",
    "affected_object": "ticket.device_id",
    "automated_checks": "operations",
    "operator_checks": "ticket_worklogs_or_internal_notes",
    "changes_made": "public_support_messages",
    "approvals": "ticket_approvals",
    "evidence": "ticket_evidence_items",
    "user_result": "ticket.requester_resolution_summary",
    "internal_result": "ticket.resolution_summary",
    "repeat_guidance": "passport.repeat_guidance",
}

PASSPORT_ACCEPTED_EVIDENCE_TYPES = {
    "requester": ["ticket_field", "chat_message"],
    "problem": ["ticket_field", "chat_message"],
    "affected_object": ["ticket_field", "asset", "device", "service"],
    "automated_checks": ["diagnostic_result", "operation_log", "playbook_run"],
    "operator_checks": ["worklog", "operation_log", "manual_note"],
    "changes_made": ["worklog", "chat_message", "manual_note"],
    "approvals": ["approval"],
    "evidence": ["diagnostic_result", "screenshot", "video", "file_attachment", "operation_log", "manual_note"],
    "user_result": ["resolution_summary", "requester_confirmation", "chat_message"],
    "internal_result": ["resolution_summary", "worklog", "manual_note"],
    "repeat_guidance": ["resolution_summary", "manual_note"],
}

PASSPORT_RECOMMENDED_ACTIONS = {
    "requester": ["Заполнить профиль заявителя или связать обращение с пользователем."],
    "problem": ["Уточнить описание проблемы в обращении или публичном сообщении."],
    "affected_object": ["Связать обращение с устройством, активом или сервисом."],
    "automated_checks": ["Запустить доступный диагностический плейбук или привязать завершённую операцию."],
    "operator_checks": ["Добавить worklog/internal note или привязать результат проверки."],
    "changes_made": ["Зафиксировать выполненное действие в worklog или сообщении поддержки."],
    "approvals": ["Получить требуемое согласование или привязать существующее решение."],
    "evidence": ["Привязать диагностический результат, скриншот, файл, лог операции или добавить ручное доказательство."],
    "user_result": ["Заполнить публичный итог для заявителя в переходе статуса или паспорте."],
    "internal_result": ["Заполнить внутренний итог, код решения или причину."],
    "repeat_guidance": ["Добавить инструкцию, что делать при повторении проблемы."],
}

PASSPORT_FACT_BLOCKING_BY_DEFAULT = {
    "requester",
    "problem",
    "affected_object",
    "evidence",
    "user_result",
    "internal_result",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _join_lines(lines: list[str], fallback: str = "Нет данных") -> str:
    cleaned = [line.strip() for line in lines if line and line.strip()]
    return "\n".join(cleaned) if cleaned else fallback


def _payload_text(payload: dict[str, Any]) -> str:
    for key in ("text", "body", "message", "result_summary", "summary"):
        value = _clean(payload.get(key))
        if value:
            return value
    return ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _usable_evidence(evidence: list[TicketEvidenceItem]) -> list[TicketEvidenceItem]:
    rejected = {"rejected", "archived", "superseded"}
    return [
        item
        for item in evidence
        if str(getattr(item, "verification_status", "") or "unverified").lower() not in rejected
    ]


def _evidence_matches_section(section: str, item: TicketEvidenceItem) -> bool:
    accepted = set(PASSPORT_ACCEPTED_EVIDENCE_TYPES.get(section, []))
    return bool(
        item.required_fact == section
        or item.section_key == section
        or (accepted and item.evidence_type in accepted)
    )


def _candidate_matches_section(section: str, candidate: dict[str, Any]) -> bool:
    accepted = set(PASSPORT_ACCEPTED_EVIDENCE_TYPES.get(section, []))
    return bool(
        candidate.get("required_fact") == section
        or candidate.get("section_key") == section
        or (accepted and candidate.get("evidence_type") in accepted)
    )


def _source_candidate_preview(candidates: list[dict[str, Any]], section: str) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not _candidate_matches_section(section, candidate):
            continue
        candidate_id = str(candidate.get("candidate_id") or f"{candidate.get('source_kind')}:{candidate.get('source_id')}")
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        preview.append(
            {
                "candidate_id": candidate_id,
                "source_kind": candidate.get("source_kind"),
                "source_id": candidate.get("source_id"),
                "source_ref": candidate.get("source_ref"),
                "source_quality": candidate.get("source_quality"),
                "evidence_type": candidate.get("evidence_type"),
                "required_fact": candidate.get("required_fact"),
                "section_key": candidate.get("section_key"),
                "title": candidate.get("title"),
                "summary": candidate.get("summary"),
                "existing_evidence_id": candidate.get("existing_evidence_id"),
            }
        )
        if len(preview) >= 8:
            break
    return preview


def _satisfied_evidence_ids(section: str, evidence: list[TicketEvidenceItem]) -> list[int]:
    ids: list[int] = []
    for item in _usable_evidence(evidence):
        if item.id is not None and _evidence_matches_section(section, item):
            ids.append(item.id)
    return ids


def _is_blocking_required_fact(section: str, reporting_policy: dict[str, Any]) -> bool:
    required_fact_policy = reporting_policy.get("required_facts") if isinstance(reporting_policy, dict) else None
    if isinstance(required_fact_policy, dict):
        item = required_fact_policy.get(section)
        if isinstance(item, dict) and "blocking_for_closure" in item:
            return bool(item.get("blocking_for_closure"))
    return section in PASSPORT_FACT_BLOCKING_BY_DEFAULT


def _reporting_policy_bool(policy: dict[str, Any], section: str, key: str, default: bool) -> bool:
    block = policy.get(section)
    if not isinstance(block, dict):
        return default
    if key not in block:
        return default
    return bool(block.get(key))


def _apply_reporting_policy_to_sections(
    sections: dict[str, str],
    policy: dict[str, Any],
) -> dict[str, str]:
    if not policy:
        return sections
    selected = _string_list(policy.get("required_sections"))
    result = {key: sections.get(key, "") for key in selected if key in SECTION_KEYS} if selected else dict(sections)
    export_visibility = policy.get("export_visibility")
    hidden = set(_string_list(export_visibility.get("hide_sections") if isinstance(export_visibility, dict) else []))
    if hidden:
        result = {key: value for key, value in result.items() if key not in hidden}
    return result


def _reporting_export_preview(policy: dict[str, Any], sections: dict[str, str]) -> dict[str, list[str]]:
    selected = _string_list(policy.get("required_sections")) if policy else []
    export_visibility = policy.get("export_visibility") if isinstance(policy, dict) else None
    hidden = _string_list(export_visibility.get("hide_sections") if isinstance(export_visibility, dict) else [])
    source_sections = selected or [key for key in SECTION_KEYS if key in sections]
    hidden_set = set(hidden)
    return {
        "visible_sections": [key for key in source_sections if key not in hidden_set],
        "hidden_sections": hidden,
    }


def _countable_events(events: list[TicketEvent]) -> list[TicketEvent]:
    return [event for event in events if not str(event.event_type or "").startswith("passport_")]


def _section_has_required_fact(
    section: str,
    *,
    ticket: Ticket,
    sections: dict[str, str],
    evidence: list[TicketEvidenceItem],
    approvals: list[TicketApproval],
    operations: list[Operation],
    worklogs: list[TicketWorklog],
) -> tuple[bool, str | None]:
    evidence_ids = _satisfied_evidence_ids(section, evidence)
    if evidence_ids:
        titles = [item.title for item in _usable_evidence(evidence) if item.id in set(evidence_ids) and item.title]
        return True, _join_lines(titles, fallback=f"evidence:{evidence_ids[0]}")
    if section == "requester":
        value = get_requester_display_name(ticket) or getattr(ticket, "requester_id", None)
        return bool(_clean(value)), _clean(value) or None
    if section == "problem":
        value = _join_lines([getattr(ticket, "title", None), getattr(ticket, "description", None)], fallback="")
        return bool(_clean(value)), _clean(value) or None
    if section == "affected_object":
        value = _join_lines([getattr(ticket, "device_id", None), getattr(ticket, "asset_id", None), getattr(ticket, "service_id", None)], fallback="")
        return bool(_clean(value)), _clean(value) or None
    if section == "automated_checks":
        value = _clean(sections.get(section))
        return bool(operations), value if operations and value else None
    if section == "operator_checks":
        value = _clean(sections.get(section))
        return bool(worklogs), value if worklogs and value else None
    if section == "changes_made":
        value = _clean(sections.get(section))
        return bool(_clean(getattr(ticket, "resolution_summary", None))), value if _clean(getattr(ticket, "resolution_summary", None)) else None
    if section == "approvals":
        value = _clean(sections.get(section))
        return bool(approvals), value if approvals and value else None
    if section == "evidence":
        value = _clean(sections.get(section))
        has_evidence = bool(_clean(getattr(ticket, "evidence_ref", None)))
        return has_evidence, value if has_evidence and value else None
    if section == "user_result":
        value = _clean(getattr(ticket, "requester_resolution_summary", None))
        return bool(value), value or None
    if section == "internal_result":
        value = _join_lines(
            [
                getattr(ticket, "resolution_code", None),
                getattr(ticket, "resolution_summary", None),
                getattr(ticket, "root_cause", None),
            ],
            fallback="",
        )
        return bool(_clean(value)), _clean(value) or None
    value = _clean(sections.get(section))
    return bool(value), value or None


def _build_passport_requirements(
    *,
    ticket: Ticket,
    sections: dict[str, str],
    reporting_policy: dict[str, Any],
    evidence: list[TicketEvidenceItem],
    approvals: list[TicketApproval],
    operations: list[Operation],
    worklogs: list[TicketWorklog],
    source_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    required_sections = _string_list(reporting_policy.get("required_sections")) if isinstance(reporting_policy, dict) else []
    missing_facts: list[dict[str, Any]] = []
    candidates = source_candidates or []
    for section in required_sections:
        if section not in SECTION_KEYS:
            continue
        met, current_value = _section_has_required_fact(
            section,
            ticket=ticket,
            sections=sections,
            evidence=evidence,
            approvals=approvals,
            operations=operations,
            worklogs=worklogs,
        )
        if met:
            continue
        blocking_for_closure = _is_blocking_required_fact(section, reporting_policy)
        candidate_preview = _source_candidate_preview(candidates, section)
        missing_facts.append(
            {
                "required_fact": section,
                "section_key": section,
                "source": PASSPORT_REQUIREMENT_SOURCES.get(section, f"passport.sections.{section}"),
                "current_value": current_value,
                "requester_visible_label": PASSPORT_REQUIREMENT_LABELS.get(section, section),
                "severity": "blocking" if blocking_for_closure else "warning",
                "accepted_evidence_types": PASSPORT_ACCEPTED_EVIDENCE_TYPES.get(section, []),
                "candidate_count": len(candidate_preview),
                "recommended_actions": PASSPORT_RECOMMENDED_ACTIONS.get(section, []),
                "blocking_for_closure": blocking_for_closure,
                "satisfied_by_evidence_ids": _satisfied_evidence_ids(section, evidence),
                "source_candidates": candidate_preview,
            }
        )
    return {
        "required_sections": required_sections,
        "require_official_passport": bool(reporting_policy.get("require_official_passport")) if isinstance(reporting_policy, dict) else False,
        "missing_facts": missing_facts,
        "missing_count": len(missing_facts),
        "blocking_missing_count": sum(1 for item in missing_facts if item.get("severity") == "blocking"),
        "export_preview": _reporting_export_preview(reporting_policy if isinstance(reporting_policy, dict) else {}, sections),
        "knowledge_draft_hints": reporting_policy.get("knowledge_draft_hints", {}) if isinstance(reporting_policy, dict) else {},
    }


class TicketPassportService:
    """Builds deterministic resolution passport drafts from ticket facts."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TicketPassportRepo(session)

    async def get_payload(self, ticket_id: str) -> dict[str, Any]:
        passport = await self.repo.get_latest_passport(ticket_id)
        ticket = await self.session.get(Ticket, ticket_id)
        reporting_policy = {}
        if ticket is not None:
            reporting_policy = await resolve_effective_ticket_policy(
                self.session,
                ticket,
                "reporting",
                snapshot_fields=("reporting_policy", "passport_policy"),
            )
        return await self._build_payload(ticket_id, passport, ticket=ticket, reporting_policy=reporting_policy)

    async def generate(
        self,
        ticket_id: str,
        *,
        actor_id: str | None,
        mode: str = "refresh",
        include_internal_notes: bool = True,
    ) -> dict[str, Any]:
        ticket = await self.session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError("ticket_not_found")

        reporting_policy = await resolve_effective_ticket_policy(
            self.session,
            ticket,
            "reporting",
            snapshot_fields=("reporting_policy", "passport_policy"),
        )
        if isinstance(reporting_policy, dict) and "include_internal_notes" in reporting_policy:
            include_internal_notes = bool(reporting_policy.get("include_internal_notes"))

        events = await self._load_events(ticket_id)
        operations = await self._load_operations(ticket_id, ticket.device_id)
        worklogs = await self._load_worklogs(ticket_id)
        await materialize_diagnostic_operation_evidence(
            self.session,
            ticket=ticket,
            operations=operations,
            created_by=actor_id,
        )
        evidence = await self.repo.list_evidence(ticket_id)
        source_candidates = await TicketEvidenceService(self.session).collect_candidates(ticket_id)
        approvals = await self.repo.list_approvals(ticket_id)
        related_objects = self._related_objects_from_ticket(ticket)

        raw_sections = self._assemble_sections(
            ticket=ticket,
            events=events,
            operations=operations,
            worklogs=worklogs,
            evidence=evidence,
            approvals=approvals,
            include_internal_notes=include_internal_notes,
        )
        passport_requirements = _build_passport_requirements(
            ticket=ticket,
            sections=raw_sections,
            reporting_policy=reporting_policy,
            evidence=evidence,
            approvals=approvals,
            operations=operations,
            worklogs=worklogs,
            source_candidates=source_candidates,
        )
        sections = dict(raw_sections)
        source_payload = {
            "summary_source": "deterministic",
            "mode": mode,
            "include_internal_notes": include_internal_notes,
            "reporting_policy": reporting_policy,
            "report_tags": _string_list(reporting_policy.get("report_tags") if isinstance(reporting_policy, dict) else []),
            "passport_requirements": passport_requirements,
            "source_event_ids": [event.id for event in events if event.id is not None],
            "source_operation_ids": [op.operation_id for op in operations],
            "source_counts": {
                "events": len(_countable_events(events)),
                "operations": len(operations),
                "worklogs": len(worklogs),
                "evidence": len(evidence),
                "approvals": len(approvals),
                "related_objects": len(related_objects),
            },
            "generated_from": {
                "ticket_updated_at": _iso(ticket.updated_at),
                "status": ticket.status,
                "resolution_code": ticket.resolution_code,
            },
        }
        passport = await self.repo.create_passport_version(
            ticket_id=ticket_id,
            generated_by=actor_id,
            sections=sections,
            source_payload=source_payload,
        )
        actions = self._actions_from_events_and_operations(events, operations)
        if _reporting_policy_bool(reporting_policy, "evidence_package", "include_action_log", True):
            await self.repo.replace_generated_actions(ticket_id=ticket_id, passport_id=passport.id, actions=actions)
        if _reporting_policy_bool(reporting_policy, "evidence_package", "include_related_objects", True):
            await self.repo.replace_related_objects(
                ticket_id=ticket_id,
                passport_id=passport.id,
                objects=related_objects,
            )
        await self._record_passport_event(ticket, passport, actor_id)
        return await self._build_payload(ticket_id, passport, ticket=ticket, reporting_policy=reporting_policy)

    def _assemble_sections(
        self,
        *,
        ticket: Ticket,
        events: list[TicketEvent],
        operations: list[Operation],
        worklogs: list[TicketWorklog],
        evidence: list[TicketEvidenceItem],
        approvals: list[TicketApproval],
        include_internal_notes: bool,
    ) -> dict[str, str]:
        requester_profile = get_requester_profile(ticket)
        requester_bits = [get_requester_display_name(ticket) or ticket.requester_id or "Инициатор не указан"]
        for label, key in (("Подразделение", "department"), ("Здание", "building"), ("Кабинет", "room"), ("Телефон", "phone")):
            value = requester_profile.get(key)
            if value:
                requester_bits.append(f"{label}: {value}")

        initial_messages = [
            _payload_text(event.payload)
            for event in events
            if event.event_type == "chat_message" and str(event.payload.get("sender_role") or "").lower() in {"user", "requester", "client", "device", ""}
        ]
        automated_lines = []
        for event in events:
            if event.event_type in {"tool_call_started", "tool_call_result"}:
                tool_name = _clean(event.payload.get("tool_name")) or _clean(event.payload.get("tool"))
                result = _payload_text(event.payload)
                automated_lines.append(_join_lines([tool_name, result], fallback=event.event_type).replace("\n", ": "))
        for operation in operations:
            automated_lines.append(
                _join_lines(
                    [
                        operation.tool_name or operation.command_name or operation.kind,
                        operation.result_summary or operation.error_message or operation.status,
                    ],
                    fallback=operation.operation_id,
                ).replace("\n", ": ")
            )

        operator_lines = []
        change_lines = []
        for event in events:
            if event.event_type != "chat_message":
                continue
            visibility = str(event.payload.get("visibility") or "public").lower()
            sender_role = str(event.payload.get("sender_role") or event.payload.get("from_role") or "").lower()
            text = _payload_text(event.payload)
            if visibility == "internal" and include_internal_notes:
                operator_lines.append(text)
            if sender_role in {"support", "agent", "admin"} and visibility == "public":
                change_lines.append(text)
        for worklog in worklogs:
            operator_lines.append(f"{worklog.spent_minutes} мин: {worklog.note or 'worklog'}")

        approvals_lines = [
            f"{approval.approval_type}: {approval.status}"
            + (f" ({approval.reason})" if approval.reason else "")
            + (f", согласующий: {approval.approver_id}" if approval.approver_id else "")
            for approval in approvals
        ]
        evidence_lines = [
            f"{item.title}: {item.summary or item.source_ref or item.evidence_type}"
            for item in evidence
        ]
        if ticket.evidence_ref:
            evidence_lines.append(ticket.evidence_ref)

        return {
            "requester": _join_lines(requester_bits),
            "problem": _join_lines([ticket.title, ticket.description, *initial_messages]),
            "affected_object": _join_lines([f"Устройство: {ticket.device_id}", f"Актив: {ticket.asset_id}" if ticket.asset_id else ""]),
            "automated_checks": _join_lines(automated_lines, fallback="Автоматические проверки не запускались"),
            "operator_checks": _join_lines(operator_lines, fallback="Операторские проверки не зафиксированы"),
            "changes_made": _join_lines(change_lines, fallback="Изменения не зафиксированы отдельным действием"),
            "approvals": _join_lines(approvals_lines, fallback="Согласования не требовались или не зафиксированы"),
            "evidence": _join_lines(evidence_lines, fallback="Доказательства не приложены"),
            "user_result": ticket.requester_resolution_summary or "Итог для пользователя пока не заполнен",
            "internal_result": _join_lines(
                [ticket.resolution_code or "", ticket.resolution_summary or "", ticket.root_cause or ""],
                fallback="Внутренний технический итог пока не заполнен",
            ),
            "repeat_guidance": "При повторе приложить скриншот, время ошибки и номер устройства/сервиса.",
        }

    def _actions_from_events_and_operations(
        self,
        events: list[TicketEvent],
        operations: list[Operation],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for event in events:
            if event.event_type in {"status_changed", "tool_call_started", "tool_call_result"}:
                title = _clean(event.payload.get("tool_name")) or event.event_type
                actions.append(
                    {
                        "action_type": event.event_type,
                        "actor_id": event.payload.get("actor_id") or event.payload.get("sender_id"),
                        "source_event_id": event.id,
                        "operation_id": event.operation_id,
                        "title": title,
                        "summary": _payload_text(event.payload) or event.event_type,
                        "created_at": event.created_at,
                    }
                )
        for operation in operations:
            actions.append(
                {
                    "action_type": "operation",
                    "actor_id": operation.actor_role,
                    "operation_id": operation.operation_id,
                    "title": operation.tool_name or operation.command_name or operation.kind,
                    "summary": operation.result_summary or operation.error_message or operation.status,
                    "started_at": operation.started_at or operation.queued_at,
                    "finished_at": operation.finished_at,
                    "created_at": operation.queued_at,
                }
            )
        return actions

    def _related_objects_from_ticket(self, ticket: Ticket) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        if ticket.device_id:
            objects.append(
                {
                    "object_type": "device",
                    "object_ref": ticket.device_id,
                    "display_name": ticket.device_id,
                    "relation_type": "affected",
                    "source": "ticket",
                }
            )
        if ticket.asset_id:
            objects.append(
                {
                    "object_type": "asset",
                    "object_ref": ticket.asset_id,
                    "display_name": ticket.asset_id,
                    "relation_type": "affected",
                    "source": "ticket",
                }
            )
        if ticket.service_id:
            objects.append(
                {
                    "object_type": "service",
                    "object_ref": str(ticket.service_id),
                    "display_name": str(ticket.service_id),
                    "relation_type": "affected",
                    "source": "ticket",
                }
            )
        return objects

    async def _build_payload(
        self,
        ticket_id: str,
        passport: TicketResolutionPassport | None,
        *,
        ticket: Ticket | None = None,
        reporting_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = await self.repo.list_evidence(ticket_id)
        actions = await self.repo.list_actions(ticket_id)
        approvals = await self.repo.list_approvals(ticket_id)
        related_objects = await self.repo.list_related_objects(ticket_id)
        current_source_counts: dict[str, int] | None = None
        if passport is not None and ticket is not None:
            current_source_counts = await self._current_source_counts(
                ticket=ticket,
                evidence=evidence,
                approvals=approvals,
                related_objects=related_objects,
            )
        requirements: dict[str, Any] = {}
        if passport is not None:
            source_payload = passport.source_payload or {}
            if isinstance(source_payload, dict):
                requirements = source_payload.get("passport_requirements") or {}
        elif ticket is not None:
            source_candidates = await TicketEvidenceService(self.session).collect_candidates(ticket_id)
            requirements = _build_passport_requirements(
                ticket=ticket,
                sections={},
                reporting_policy=reporting_policy or {},
                evidence=evidence,
                approvals=approvals,
                operations=[],
                worklogs=[],
                source_candidates=source_candidates,
            )
        passport_stale = False
        passport_stale_reasons: list[str] = []
        if passport is not None:
            passport_stale, passport_stale_reasons = self._passport_stale_state(
                passport,
                evidence=evidence,
                current_source_counts=current_source_counts,
            )
        return {
            "ticket_id": ticket_id,
            "passport": self._passport_to_dict(
                passport,
                passport_stale,
                passport_stale_reasons,
                current_source_counts=current_source_counts,
            ) if passport else None,
            "status": "draft" if passport else "missing",
            "requirements": requirements,
            "evidence": [self._evidence_to_dict(item) for item in evidence],
            "actions": [self._action_to_dict(item) for item in actions],
            "approvals": [self._approval_to_dict(item) for item in approvals],
            "related_objects": [self._related_object_to_dict(item) for item in related_objects],
        }

    async def _load_events(self, ticket_id: str) -> list[TicketEvent]:
        result = await self.session.execute(
            select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
        )
        return list(result.scalars().all())

    async def _load_operations(self, ticket_id: str, device_id: str) -> list[Operation]:
        playbook_run_ids = (
            select(PlaybookRun.id)
            .where(
                PlaybookRun.device_id == device_id,
                PlaybookRun.context_json["ticket_id"].astext == ticket_id,
            )
            .subquery()
        )
        result = await self.session.execute(
            select(Operation)
            .where(
                or_(
                    Operation.ticket_id == ticket_id,
                    Operation.playbook_run_id.in_(select(playbook_run_ids.c.id)),
                )
            )
            .order_by(Operation.queued_at.asc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def _load_worklogs(self, ticket_id: str) -> list[TicketWorklog]:
        result = await self.session.execute(
            select(TicketWorklog).where(TicketWorklog.ticket_id == ticket_id).order_by(TicketWorklog.created_at.asc())
        )
        return list(result.scalars().all())

    async def _current_source_counts(
        self,
        *,
        ticket: Ticket,
        evidence: list[TicketEvidenceItem] | None = None,
        approvals: list[TicketApproval] | None = None,
        related_objects: list[TicketRelatedObject] | None = None,
    ) -> dict[str, int]:
        ticket_id = ticket.ticket_id
        events = await self._load_events(ticket_id)
        operations = await self._load_operations(ticket_id, ticket.device_id)
        worklogs = await self._load_worklogs(ticket_id)
        evidence_items = evidence if evidence is not None else await self.repo.list_evidence(ticket_id)
        approval_items = approvals if approvals is not None else await self.repo.list_approvals(ticket_id)
        related_items = related_objects if related_objects is not None else await self.repo.list_related_objects(ticket_id)
        return {
            "events": len(_countable_events(events)),
            "operations": len(operations),
            "worklogs": len(worklogs),
            "evidence": len(evidence_items),
            "approvals": len(approval_items),
            "related_objects": len(related_items),
        }

    async def _record_passport_event(
        self,
        ticket: Ticket,
        passport: TicketResolutionPassport,
        actor_id: str | None,
    ) -> None:
        await TicketEventsRepo(self.session).add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="passport_generated",
            payload={
                "event_id": f"passport-generated-{passport.id}-{uuid.uuid4().hex[:8]}",
                "actor_id": actor_id,
                "passport_id": passport.id,
                "version": passport.version,
            },
            event_id=f"passport-generated-{passport.id}",
        )

    async def get_passport_stale_state(
        self,
        passport: TicketResolutionPassport | None,
        *,
        ticket: Ticket | None,
    ) -> tuple[bool, list[str], dict[str, int]]:
        if passport is None or ticket is None:
            return False, [], {}
        evidence = await self.repo.list_evidence(ticket.ticket_id)
        current_source_counts = await self._current_source_counts(ticket=ticket, evidence=evidence)
        stale, reasons = self._passport_stale_state(
            passport,
            evidence=evidence,
            current_source_counts=current_source_counts,
        )
        return stale, reasons, current_source_counts

    def _passport_stale_state(
        self,
        passport: TicketResolutionPassport | None,
        *,
        evidence: list[TicketEvidenceItem],
        current_source_counts: dict[str, int] | None = None,
    ) -> tuple[bool, list[str]]:
        if passport is None:
            return False, []
        generated_at = passport.generated_at
        reasons: list[str] = []
        if any(item.created_at and item.created_at > generated_at for item in evidence):
            reasons.append("evidence_changed")
        source_payload = passport.source_payload if isinstance(passport.source_payload, dict) else {}
        stored_counts = source_payload.get("source_counts") if isinstance(source_payload, dict) else {}
        if isinstance(stored_counts, dict) and current_source_counts:
            for key, current_count in current_source_counts.items():
                if key == "evidence":
                    continue
                try:
                    stored_count = int(stored_counts.get(key, 0))
                except (TypeError, ValueError):
                    stored_count = 0
                if stored_count != int(current_count):
                    reasons.append(f"{key}_changed")
        return bool(reasons), reasons

    def _passport_to_dict(
        self,
        passport: TicketResolutionPassport,
        stale: bool = False,
        stale_reasons: list[str] | None = None,
        current_source_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        sections = {key: getattr(passport, attr) or "" for key, attr in SECTION_KEYS.items()}
        source_payload = dict(passport.source_payload or {})
        if current_source_counts:
            source_payload["current_source_counts"] = current_source_counts
        if stale_reasons:
            source_payload["stale_reasons"] = stale_reasons
        return {
            "passport_id": passport.id,
            "ticket_id": passport.ticket_id,
            "version": passport.version,
            "status": passport.status,
            "summary_source": passport.summary_source,
            "generated_at": _iso(passport.generated_at),
            "generated_by": passport.generated_by,
            "updated_at": _iso(passport.updated_at),
            "updated_by": passport.updated_by,
            "sections": sections,
            "source_event_ids": passport.source_event_ids or [],
            "source_operation_ids": passport.source_operation_ids or [],
            "source_payload": source_payload,
            "stale": stale,
        }

    def _evidence_to_dict(self, item: TicketEvidenceItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "ticket_id": item.ticket_id,
            "passport_id": item.passport_id,
            "evidence_type": item.evidence_type,
            "source_ref": item.source_ref,
            "source_kind": item.source_kind,
            "source_id": item.source_id,
            "required_fact": item.required_fact,
            "section_key": item.section_key,
            "artifact_id": item.artifact_id,
            "title": item.title,
            "summary": item.summary,
            "visibility": item.visibility,
            "verification_status": item.verification_status,
            "verified_by": item.verified_by,
            "verified_at": _iso(item.verified_at),
            "captured_at": _iso(item.captured_at),
            "public_summary": item.public_summary,
            "internal_summary": item.internal_summary,
            "metadata_json": item.metadata_json or {},
            "export_visibility": item.export_visibility,
            "created_by": item.created_by,
            "created_at": _iso(item.created_at),
        }

    def _action_to_dict(self, item: TicketActionLog) -> dict[str, Any]:
        return {
            "id": item.id,
            "ticket_id": item.ticket_id,
            "passport_id": item.passport_id,
            "action_type": item.action_type,
            "actor_id": item.actor_id,
            "source_event_id": item.source_event_id,
            "operation_id": item.operation_id,
            "title": item.title,
            "summary": item.summary,
            "started_at": _iso(item.started_at),
            "finished_at": _iso(item.finished_at),
            "created_at": _iso(item.created_at),
        }

    def _approval_to_dict(self, item: TicketApproval) -> dict[str, Any]:
        return {
            "id": item.id,
            "ticket_id": item.ticket_id,
            "passport_id": item.passport_id,
            "approval_type": item.approval_type,
            "approver_id": item.approver_id,
            "status": item.status,
            "reason": item.reason,
            "requested_by": item.requested_by,
            "requested_at": _iso(item.requested_at),
            "decided_at": _iso(item.decided_at),
        }

    def _related_object_to_dict(self, item: TicketRelatedObject) -> dict[str, Any]:
        return {
            "id": item.id,
            "ticket_id": item.ticket_id,
            "passport_id": item.passport_id,
            "object_type": item.object_type,
            "object_ref": item.object_ref,
            "display_name": item.display_name,
            "relation_type": item.relation_type,
            "source": item.source,
            "created_at": _iso(item.created_at),
        }
