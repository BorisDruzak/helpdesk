from __future__ import annotations

from datetime import date, datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Operation,
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
        has_evidence = bool(evidence) or bool(_clean(getattr(ticket, "evidence_ref", None)))
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
) -> dict[str, Any]:
    required_sections = _string_list(reporting_policy.get("required_sections")) if isinstance(reporting_policy, dict) else []
    missing_facts: list[dict[str, Any]] = []
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
        missing_facts.append(
            {
                "required_fact": section,
                "source": PASSPORT_REQUIREMENT_SOURCES.get(section, f"passport.sections.{section}"),
                "current_value": current_value,
                "requester_visible_label": PASSPORT_REQUIREMENT_LABELS.get(section, section),
                "severity": "blocking",
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
        )
        sections = _apply_reporting_policy_to_sections(raw_sections, reporting_policy)
        source_payload = {
            "summary_source": "deterministic",
            "mode": mode,
            "include_internal_notes": include_internal_notes,
            "reporting_policy": reporting_policy,
            "report_tags": _string_list(reporting_policy.get("report_tags") if isinstance(reporting_policy, dict) else []),
            "passport_requirements": passport_requirements,
            "source_event_ids": [event.id for event in events if event.id is not None],
            "source_operation_ids": [op.operation_id for op in operations],
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
        requirements: dict[str, Any] = {}
        if passport is not None:
            source_payload = passport.source_payload or {}
            if isinstance(source_payload, dict):
                requirements = source_payload.get("passport_requirements") or {}
        elif ticket is not None:
            requirements = _build_passport_requirements(
                ticket=ticket,
                sections={},
                reporting_policy=reporting_policy or {},
                evidence=evidence,
                approvals=approvals,
                operations=[],
                worklogs=[],
            )
        return {
            "ticket_id": ticket_id,
            "passport": self._passport_to_dict(passport) if passport else None,
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
        result = await self.session.execute(
            select(Operation)
            .where(Operation.ticket_id == ticket_id)
            .order_by(Operation.queued_at.asc())
            .limit(50)
        )
        operations = list(result.scalars().all())
        if operations:
            return operations
        result = await self.session.execute(
            select(Operation)
            .where(Operation.device_id == device_id)
            .order_by(Operation.queued_at.desc())
            .limit(10)
        )
        return list(reversed(result.scalars().all()))

    async def _load_worklogs(self, ticket_id: str) -> list[TicketWorklog]:
        result = await self.session.execute(
            select(TicketWorklog).where(TicketWorklog.ticket_id == ticket_id).order_by(TicketWorklog.created_at.asc())
        )
        return list(result.scalars().all())

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

    def _passport_to_dict(self, passport: TicketResolutionPassport) -> dict[str, Any]:
        sections = {key: getattr(passport, attr) or "" for key, attr in SECTION_KEYS.items()}
        source_payload = passport.source_payload or {}
        reporting_policy = source_payload.get("reporting_policy") if isinstance(source_payload, dict) else {}
        if isinstance(reporting_policy, dict) and reporting_policy:
            sections = _apply_reporting_policy_to_sections(sections, reporting_policy)
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
            "stale": False,
        }

    def _evidence_to_dict(self, item: TicketEvidenceItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "ticket_id": item.ticket_id,
            "passport_id": item.passport_id,
            "evidence_type": item.evidence_type,
            "source_ref": item.source_ref,
            "title": item.title,
            "summary": item.summary,
            "visibility": item.visibility,
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
