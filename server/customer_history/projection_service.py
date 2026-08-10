from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, desc, or_, select

from app.db.models import Ticket
from domain_ports.container import DomainPortContainer
from domain_ports.registry import RegistryPort
from domain_ports.registry_contracts import PersonRef, RegistryReadActor
from tickets.ticket_context import (
    requester_legacy_scope_clause,
    requester_neutral_scope_clause,
    requester_reference_snapshot_from_record,
)

from .models import CustomerHistoryEvent
from .redaction import redact_event_for_role
from .sources import (
    ChatHistorySource,
    DiagnosticHistorySource,
    KnowledgeHistorySource,
    ObserverHistorySource,
    RegistryHistorySource,
    SlaHistorySource,
    TicketHistorySource,
)


def _actor_role(actor_context: dict[str, Any] | None) -> str:
    role = str((actor_context or {}).get("actor_role") or "").strip().lower()
    if role in {"user", "requester"}:
        return "requester"
    if role == "admin":
        return "admin"
    if role == "llm":
        return "llm"
    return "support"


def _sort_key(event: CustomerHistoryEvent) -> tuple[int, str, str]:
    priority = 0 if event.event_type == "ticket_created" else 1
    return (priority, event.normalized_occurred_at(), event.event_id)


def _ticket_context(ticket: Ticket) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None)
    if not isinstance(custom_fields, dict):
        return {}
    context = custom_fields.get("ticket_context")
    return dict(context) if isinstance(context, dict) else {}


def _context_section(context: dict[str, Any], key: str) -> dict[str, Any]:
    value = context.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _context_person_id(context: dict[str, Any], key: str) -> str | None:
    value = _context_section(context, key).get("person_id")
    return str(value) if value else None


def _legacy_ticket_history_person_ids(ticket: Ticket) -> list[str]:
    """Return historical Registry aliases only from an unambiguously legacy row."""

    context = _ticket_context(ticket)
    ids = [
        getattr(ticket, "requester_person_id", None),
        _context_person_id(context, "creator"),
        _context_person_id(context, "affected"),
    ]
    result: list[str] = []
    for value in ids:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def ticket_history_requester_refs(ticket: Ticket) -> list[str]:
    """Return the opaque history subject(s) valid for a ticket.

    A neutral requester pair owns the row completely.  It is correlated only
    by its exact external reference; malformed neutral data intentionally
    matches neither it nor legacy aliases.  Creator/affected aliases are
    retained solely for rows that contain no neutral fields at all.
    """

    try:
        requester_ref, _snapshot = requester_reference_snapshot_from_record(ticket)
    except (TypeError, ValueError):
        return []
    if requester_ref is not None:
        return [requester_ref.external_id]
    return _legacy_ticket_history_person_ids(ticket)


def _ticket_mentions_requester_ref(ticket: Ticket, requester_ref: str) -> bool:
    return str(requester_ref) in ticket_history_requester_refs(ticket)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _window_start(*, since: Any = None, window_days: int | None = None) -> datetime | None:
    explicit = _parse_datetime(since)
    if explicit is not None:
        return explicit
    if window_days is None:
        return None
    try:
        days = int(window_days)
    except (TypeError, ValueError):
        return None
    if days <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(days=min(days, 3650))


def _filter_events_by_window(events: list[CustomerHistoryEvent], since: datetime | None) -> list[CustomerHistoryEvent]:
    if since is None:
        return events
    filtered: list[CustomerHistoryEvent] = []
    for event in events:
        occurred_at = _parse_datetime(event.occurred_at)
        if occurred_at is None or occurred_at >= since:
            filtered.append(event)
    return filtered


class CustomerHistoryProjectionService:
    def __init__(self, session, *, registry_port: RegistryPort | None = None):
        self.session = session
        self.registry_port = registry_port or DomainPortContainer.from_config(
            registry_session=session
        ).registry

    async def _ticket(self, ticket_id: str) -> Ticket | None:
        return (
            await self.session.execute(select(Ticket).where(Ticket.ticket_id == str(ticket_id)))
        ).scalar_one_or_none()

    async def _events_for_ticket(
        self,
        ticket: Ticket,
        *,
        limit: int,
        person_id: str | None = None,
    ) -> list[CustomerHistoryEvent]:
        events: list[CustomerHistoryEvent] = []
        for source in (
            TicketHistorySource(self.session),
            KnowledgeHistorySource(self.session),
            DiagnosticHistorySource(self.session),
            ObserverHistorySource(self.session),
            SlaHistorySource(self.session),
            ChatHistorySource(self.session),
        ):
            events.extend(await source.events_for_ticket(ticket, limit=limit, person_id=person_id))
        deduped: dict[str, CustomerHistoryEvent] = {}
        for event in events:
            deduped.setdefault(event.event_id, event)
        return sorted(deduped.values(), key=_sort_key)

    async def _tickets_for_person(self, requester_ref: str, *, limit: int = 100) -> list[Ticket]:
        """Find tickets by exact neutral reference, then legacy person history.

        ``Ticket.requester_id`` deliberately never appears here: it is a
        Helpdesk login/creator field, not a Registry person reference.
        """

        requester_text = str(requester_ref)
        neutral_scope = requester_neutral_scope_clause(Ticket)
        legacy_scope = requester_legacy_scope_clause(Ticket)
        direct_rows = (
            await self.session.execute(
                select(Ticket)
                .where(
                    or_(
                        and_(
                            neutral_scope,
                            Ticket.requester_external_ref == requester_text,
                        ),
                        and_(
                            legacy_scope,
                            Ticket.requester_person_id == requester_text,
                        ),
                    )
                )
                .order_by(desc(Ticket.created_at))
                .limit(max(1, min(int(limit or 100), 300)))
            )
        ).scalars().all()
        by_id: dict[str, Ticket] = {ticket.ticket_id: ticket for ticket in direct_rows}

        scan_limit = max(limit * 3, 300)
        scanned = (
            await self.session.execute(
                select(Ticket)
                .order_by(desc(Ticket.created_at))
                .limit(max(1, min(int(scan_limit), 1000)))
            )
        ).scalars().all()
        for ticket in scanned:
            if (
                ticket.ticket_id not in by_id
                and _ticket_mentions_requester_ref(ticket, requester_text)
            ):
                by_id[ticket.ticket_id] = ticket
            if len(by_id) >= limit:
                break
        return sorted(
            by_id.values(),
            key=lambda ticket: _parse_datetime(getattr(ticket, "created_at", None)) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:limit]

    def _project(
        self,
        events: list[CustomerHistoryEvent],
        *,
        role: str,
        limit: int,
        mode: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        projected: list[dict[str, Any]] = []
        removed = 0
        for event in events:
            data, count = redact_event_for_role(event, role=role, mode=mode)
            removed += count
            if data is not None:
                projected.append(data)
            if len(projected) >= limit:
                break
        return projected, {"removed_count": removed, "role": role}

    async def history_for_ticket(
        self,
        ticket_id: str,
        *,
        actor_context: dict[str, Any] | None = None,
        limit: int = 50,
        role: str | None = None,
        since: Any = None,
        window_days: int | None = None,
    ) -> dict[str, Any]:
        ticket = await self._ticket(ticket_id)
        if ticket is None:
            raise KeyError("ticket not found")
        resolved_role = role or _actor_role(actor_context)
        bounded_limit = max(1, min(int(limit or 50), 200))
        since_at = _window_start(since=since, window_days=window_days)
        events = await self._events_for_ticket(ticket, limit=max(bounded_limit, 50))
        events = _filter_events_by_window(events, since_at)
        projected, report = self._project(events, role=resolved_role, limit=bounded_limit)
        payload: dict[str, Any] = {
            "ticket_ref": getattr(ticket, "ticket_code", None) or ticket.ticket_id,
            "events": projected,
            "count": len(projected),
            "redaction_report": report,
            "sources": sorted({event.source for event in events}),
        }
        if resolved_role in {"support", "admin"}:
            payload["ticket_id"] = ticket.ticket_id
            payload["person_id"] = getattr(ticket, "requester_person_id", None)
        return payload

    async def history_for_person(
        self,
        person_id: str,
        *,
        actor_context: dict[str, Any] | None = None,
        registry_actor: RegistryReadActor | None = None,
        limit: int = 50,
        role: str | None = None,
        since: Any = None,
        window_days: int | None = None,
    ) -> dict[str, Any]:
        role = role or _actor_role(actor_context)
        bounded_limit = max(1, min(int(limit or 50), 200))
        since_at = _window_start(since=since, window_days=window_days)
        requester_ref = str(person_id)
        rows = await self._tickets_for_person(requester_ref, limit=100)
        events: list[CustomerHistoryEvent] = []
        for ticket in rows:
            events.extend(await self._events_for_ticket(ticket, limit=20, person_id=requester_ref))
        registry_result = await RegistryHistorySource(registry_port=self.registry_port).events_for_person(
            PersonRef(external_id=requester_ref),
            actor=registry_actor,
            limit=20,
        )
        events.extend(registry_result.events)
        events = sorted({event.event_id: event for event in events}.values(), key=_sort_key)
        events = _filter_events_by_window(events, since_at)
        projected, report = self._project(events, role=role, limit=bounded_limit)
        payload: dict[str, Any] = {
            "events": projected,
            "count": len(projected),
            "redaction_report": report,
            "sources": sorted({event.source for event in events}),
            "source_states": {"registry": registry_result.source_state},
        }
        if role in {"support", "admin"}:
            payload["person_id"] = requester_ref
        return payload

    async def search_history(
        self,
        query: str,
        *,
        actor_context: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        role = _actor_role(actor_context)
        if role != "admin":
            raise PermissionError("admin role required")
        needle = f"%{str(query or '').strip()}%"
        stmt = select(Ticket).order_by(desc(Ticket.created_at)).limit(max(1, min(int(limit or 50), 100)))
        if str(query or "").strip():
            stmt = stmt.where(or_(Ticket.ticket_code.ilike(needle), Ticket.title.ilike(needle), Ticket.description.ilike(needle)))
        rows = (await self.session.execute(stmt)).scalars().all()
        items = [
            {
                "ticket_id": ticket.ticket_id,
                "ticket_ref": getattr(ticket, "ticket_code", None) or ticket.ticket_id,
                "title": ticket.title,
                "status": ticket.status,
                "person_id": getattr(ticket, "requester_person_id", None),
            }
            for ticket in rows
        ]
        return {"items": items, "count": len(items)}
