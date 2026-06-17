from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select

from app.db.models import (
    DeviceAccountSession,
    DeviceUserBinding,
    KnowledgeFeedbackEvent,
    Operation,
    ObserverTrace,
    Ticket,
    TicketEvent,
)

from .models import CustomerHistoryEvent, isoformat_utc


def _payload_text(payload: dict[str, Any]) -> str | None:
    for key in ("text", "summary", "result_summary", "message", "status_reason"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


REQUESTER_KB_SCOPES = {"public", "requester", "requester_visible", "creator_visible", "creator"}
REQUESTER_KB_AUDIENCE_SCOPES = {"public", "requester", "requester_visible", "creator_visible", "creator"}


def _ticket_ref(ticket: Ticket) -> str:
    return getattr(ticket, "ticket_code", None) or ticket.ticket_id


def _short_ref(kind: str, value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return f"{kind}:{text[:8]}"


def _base_refs(ticket: Ticket, **extra: Any) -> dict[str, Any]:
    refs = {"ticket_ref": _ticket_ref(ticket)}
    for key, value in extra.items():
        if value:
            refs[key] = value
    return refs


def _ticket_context(ticket: Ticket) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None)
    if not isinstance(custom_fields, dict):
        return {}
    context = custom_fields.get("ticket_context")
    return dict(context) if isinstance(context, dict) else {}


def _context_section(context: dict[str, Any], name: str) -> dict[str, Any]:
    value = context.get(name)
    return dict(value) if isinstance(value, dict) else {}


def _context_person_id(context: dict[str, Any], name: str) -> str | None:
    section = _context_section(context, name)
    value = section.get("person_id")
    return str(value) if value else None


def _context_display_name(context: dict[str, Any], name: str) -> str | None:
    section = _context_section(context, name)
    value = section.get("display_name") or section.get("full_name") or section.get("name")
    return str(value) if value else None


def _relationship_for_person(ticket: Ticket, person_id: str | None) -> str | None:
    if not person_id:
        return None
    context = _ticket_context(ticket)
    creator_id = _context_person_id(context, "creator") or getattr(ticket, "requester_person_id", None)
    affected_id = _context_person_id(context, "affected") or creator_id
    if str(person_id) == str(creator_id) and str(person_id) == str(affected_id):
        return "creator_and_affected"
    if str(person_id) == str(creator_id):
        return "creator"
    if str(person_id) == str(affected_id):
        return "affected"
    return None


def _ticket_context_summary(ticket: Ticket, *, person_id: str | None = None) -> dict[str, Any]:
    context = _ticket_context(ticket)
    if not context:
        return {}
    payload: dict[str, Any] = {
        "created_on_behalf": bool(
            context.get("created_on_behalf")
            or _context_section(context, "on_behalf").get("enabled")
        ),
        "creator_display_name": _context_display_name(context, "creator"),
        "affected_display_name": _context_display_name(context, "affected"),
        "diagnostic_target_status": _context_section(context, "diagnostic_target").get("agent_status")
        or _context_section(context, "target_device").get("agent_status"),
    }
    relationship = _relationship_for_person(ticket, person_id)
    if relationship:
        payload["person_history_relationship"] = relationship
    return {key: value for key, value in payload.items() if value is not None}


def _knowledge_attempt_requester_allowed(item: dict[str, Any]) -> bool:
    visibility_scope = str(item.get("visibility_scope") or "").strip().lower()
    audience_scope = str(item.get("audience_scope") or "").strip().lower()
    if visibility_scope and visibility_scope not in REQUESTER_KB_SCOPES:
        return False
    if audience_scope and audience_scope not in REQUESTER_KB_AUDIENCE_SCOPES:
        return False
    return bool(visibility_scope or audience_scope)


def _event_visibility(event_type: str, payload: dict[str, Any]) -> dict[str, bool]:
    visibility = str(payload.get("visibility") or "").lower()
    if event_type == "chat_message" and visibility in {"internal", "support", "support_only"}:
        return {"requester": False, "support": True, "admin": True, "llm": False}
    if event_type == "ticket_context_resolved":
        return {"requester": False, "support": True, "admin": True, "llm": True}
    if visibility in {"internal", "private"}:
        return {"requester": False, "support": True, "admin": True, "llm": False}
    return {"requester": True, "support": True, "admin": True, "llm": True}


def _group_for_ticket_event(event_type: str) -> str:
    if event_type == "chat_message":
        return "chat"
    if "sla" in event_type or "ola" in event_type:
        return "sla"
    if "tool" in event_type or "diagnostic" in event_type or "playbook" in event_type:
        return "diagnostics"
    return "ticket"


class TicketHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 200,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        custom_fields = getattr(ticket, "custom_fields", None) or {}
        request_form = custom_fields.get("request_form") if isinstance(custom_fields, dict) else None
        ticket_context = custom_fields.get("ticket_context") if isinstance(custom_fields, dict) else None
        ticket_payload = {
            "ticket_code": getattr(ticket, "ticket_code", None),
            "title": getattr(ticket, "title", None),
            "status": getattr(ticket, "status", None),
            "request_form": request_form,
            "ticket_context": ticket_context,
            **_ticket_context_summary(ticket, person_id=person_id),
        }
        events = [
            CustomerHistoryEvent(
                event_id=f"ticket:{ticket.ticket_id}:created",
                source="ticket",
                group="ticket",
                event_type="ticket_created",
                title="Ticket created",
                summary=getattr(ticket, "title", None),
                occurred_at=getattr(ticket, "created_at", None),
                ticket_id=ticket.ticket_id,
                ticket_ref=_ticket_ref(ticket),
                person_id=person_id or getattr(ticket, "requester_person_id", None),
                device_id=getattr(ticket, "device_id", None),
                visibility={"requester": True, "support": True, "admin": True, "llm": True},
                payload=ticket_payload,
                safe_refs=_base_refs(ticket),
            )
        ]
        rows = (
            await self.session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket.ticket_id)
                .order_by(TicketEvent.created_at, TicketEvent.id)
                .limit(max(1, min(int(limit or 200), 500)))
            )
        ).scalars().all()
        for row in rows:
            if str(row.event_type) == "chat_message":
                continue
            payload = dict(getattr(row, "payload", None) or {})
            payload.update(_ticket_context_summary(ticket, person_id=person_id))
            events.append(
                CustomerHistoryEvent(
                    event_id=f"ticket_event:{getattr(row, 'id', None) or getattr(row, 'event_id', None) or len(events)}",
                    source="ticket",
                    group=_group_for_ticket_event(str(row.event_type)),
                    event_type=str(row.event_type),
                    title=str(row.event_type).replace("_", " ").title(),
                    summary=_payload_text(payload),
                    occurred_at=getattr(row, "created_at", None),
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=getattr(row, "device_id", None) or getattr(ticket, "device_id", None),
                    visibility=_event_visibility(str(row.event_type), payload),
                    payload=payload,
                    safe_refs=_base_refs(ticket),
                )
            )
        return events


class KnowledgeHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 100,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent)
                .where(KnowledgeFeedbackEvent.ticket_id == ticket.ticket_id)
                .order_by(KnowledgeFeedbackEvent.created_at, KnowledgeFeedbackEvent.event_id)
                .limit(max(1, min(int(limit or 100), 300)))
            )
        ).scalars().all()
        events: list[CustomerHistoryEvent] = []
        for row in rows:
            payload = dict(row.metadata_json or {})
            payload.update(
                {
                    "event_type": row.event_type,
                    "result": row.result,
                    "source_surface": row.source_surface,
                    "service_code": row.service_code,
                    "offering_code": row.offering_code,
                    "item_id": row.item_id,
                }
            )
            attempts = payload.get("knowledge_attempts")
            requester_visible = False
            if isinstance(attempts, list):
                requester_visible = any(
                    _knowledge_attempt_requester_allowed(item)
                    for item in attempts
                    if isinstance(item, dict)
                )
            else:
                requester_visible = True
            events.append(
                CustomerHistoryEvent(
                    event_id=f"knowledge:{row.event_id}",
                    source="knowledge",
                    group="knowledge",
                    event_type=str(row.event_type),
                    title="Knowledge activity",
                    summary=str(row.result or row.event_type),
                    occurred_at=row.created_at,
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=getattr(ticket, "device_id", None),
                    visibility={"requester": requester_visible, "support": True, "admin": True, "llm": requester_visible},
                    payload=payload,
                    safe_refs=_base_refs(ticket),
                )
            )
        return events


class RegistryHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_person(self, person_id: str, *, limit: int = 100) -> list[CustomerHistoryEvent]:
        events: list[CustomerHistoryEvent] = []
        bindings = (
            await self.session.execute(
                select(DeviceUserBinding)
                .where(DeviceUserBinding.person_id == person_id)
                .order_by(desc(DeviceUserBinding.created_at))
                .limit(max(1, min(int(limit or 100), 300)))
            )
        ).scalars().all()
        for row in bindings:
            events.append(
                CustomerHistoryEvent(
                    event_id=f"registry:binding:{row.binding_id}",
                    source="registry",
                    group="registry",
                    event_type="device_binding",
                    title="Device binding",
                    summary=f"{row.relationship_type}:{row.status}",
                    occurred_at=row.created_at,
                    person_id=person_id,
                    device_id=row.device_id,
                    visibility={"requester": True, "support": True, "admin": True, "llm": True},
                    payload={
                        "relationship_type": row.relationship_type,
                        "status": row.status,
                        "source": row.source,
                        "confirmed_at": isoformat_utc(row.confirmed_at),
                    },
                    safe_refs={
                        key: value
                        for key, value in {"device_ref": _short_ref("device", row.device_id)}.items()
                        if value
                    },
                )
            )
        sessions = (
            await self.session.execute(
                select(DeviceAccountSession)
                .where(DeviceAccountSession.person_id == person_id)
                .order_by(desc(DeviceAccountSession.created_at))
                .limit(max(1, min(int(limit or 100), 300)))
            )
        ).scalars().all()
        for row in sessions:
            events.append(
                CustomerHistoryEvent(
                    event_id=f"registry:session:{row.session_id}",
                    source="registry",
                    group="registry",
                    event_type="account_session",
                    title="Account session",
                    summary=f"{row.account_mode}:{row.verification_status}",
                    occurred_at=row.created_at,
                    person_id=person_id,
                    device_id=row.device_id,
                    visibility={"requester": False, "support": True, "admin": True, "llm": False},
                    payload={
                        "account_mode": row.account_mode,
                        "verification_status": row.verification_status,
                        "warning_code": row.warning_code,
                    },
                )
            )
        return events


class DiagnosticHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 50,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        rows = (
            await self.session.execute(
                select(Operation)
                .where(Operation.ticket_id == ticket.ticket_id)
                .order_by(desc(Operation.queued_at))
                .limit(max(1, min(int(limit or 50), 200)))
            )
        ).scalars().all()
        events: list[CustomerHistoryEvent] = []
        for row in rows:
            events.append(
                CustomerHistoryEvent(
                    event_id=f"operation:{row.operation_id}",
                    source="diagnostics",
                    group="diagnostics",
                    event_type="operation",
                    title=row.tool_name or row.command_name or row.kind,
                    summary=row.result_summary or row.error_message or row.status,
                    occurred_at=row.finished_at or row.queued_at,
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=row.device_id,
                    visibility={"requester": False, "support": True, "admin": True, "llm": True},
                    payload={
                        "kind": row.kind,
                        "status": row.status,
                        "phase": row.phase,
                        "tool_name": row.tool_name,
                        "result_summary": row.result_summary,
                        "error_message": row.error_message,
                    },
                    safe_refs=_base_refs(ticket, operation_ref=_short_ref("operation", row.operation_id)),
                )
            )
        return events


class ObserverHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 50,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        rows = (
            await self.session.execute(
                select(ObserverTrace)
                .where(ObserverTrace.ticket_id == ticket.ticket_id)
                .order_by(desc(ObserverTrace.started_at), desc(ObserverTrace.trace_id))
                .limit(max(1, min(int(limit or 50), 100)))
            )
        ).scalars().all()
        events: list[CustomerHistoryEvent] = []
        for row in rows:
            trace_ref = _short_ref("trace", row.trace_id)
            operation_ref = _short_ref("operation", row.operation_id)
            title = "Observer trace"
            attrs = dict(row.attrs_json or {})
            if attrs.get("title"):
                title = str(attrs["title"])
            events.append(
                CustomerHistoryEvent(
                    event_id=f"observer:{row.trace_id}",
                    source="observer",
                    group="observer",
                    event_type="observer_trace",
                    title=title,
                    summary=f"{row.root_kind or 'trace'}:{row.status}",
                    occurred_at=row.finished_at or row.started_at,
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=row.device_id or getattr(ticket, "device_id", None),
                    visibility={"requester": False, "support": True, "admin": True, "llm": True},
                    payload={
                        "root_kind": row.root_kind,
                        "status": row.status,
                        "span_count": int(row.span_count or 0),
                        "error_count": int(row.error_count or 0),
                        "observer_ref": trace_ref,
                        "operation_ref": operation_ref,
                    },
                    safe_refs=_base_refs(ticket, observer_ref=trace_ref, operation_ref=operation_ref),
                )
            )
        return events


class SlaHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 50,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        events: list[CustomerHistoryEvent] = []
        due_at = getattr(ticket, "resolution_due_at", None)
        if due_at:
            events.append(
                CustomerHistoryEvent(
                    event_id=f"sla:{ticket.ticket_id}:resolution_due",
                    source="sla",
                    group="sla",
                    event_type="resolution_due",
                    title="Resolution SLA",
                    summary="Resolution due time recorded",
                    occurred_at=getattr(ticket, "created_at", None) or datetime.now(timezone.utc),
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=getattr(ticket, "device_id", None),
                    visibility={"requester": True, "support": True, "admin": True, "llm": True},
                    payload={"resolution_due_at": isoformat_utc(due_at)},
                    safe_refs=_base_refs(ticket),
                )
            )
        return events[:limit]


class ChatHistorySource:
    def __init__(self, session):
        self.session = session

    async def events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int = 50,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        rows = (
            await self.session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket.ticket_id, TicketEvent.event_type == "chat_message")
                .order_by(TicketEvent.created_at, TicketEvent.id)
                .limit(max(1, min(int(limit or 50), 200)))
            )
        ).scalars().all()
        events: list[CustomerHistoryEvent] = []
        for row in rows:
            payload = dict(getattr(row, "payload", None) or {})
            events.append(
                CustomerHistoryEvent(
                    event_id=f"chat:{getattr(row, 'id', None) or len(events)}",
                    source="chat",
                    group="chat",
                    event_type="chat_message",
                    title="Chat message",
                    summary=_payload_text(payload),
                    occurred_at=getattr(row, "created_at", None),
                    ticket_id=ticket.ticket_id,
                    ticket_ref=_ticket_ref(ticket),
                    person_id=person_id or getattr(ticket, "requester_person_id", None),
                    device_id=getattr(row, "device_id", None) or getattr(ticket, "device_id", None),
                    visibility=_event_visibility("chat_message", payload),
                    payload=payload,
                    safe_refs=_base_refs(ticket),
                )
            )
        return events
