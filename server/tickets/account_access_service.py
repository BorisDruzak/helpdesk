from __future__ import annotations

from typing import Any

from sqlalchemy import and_, false, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ticket
from app.repos.registration_repo import RegistrationRepo
from tickets.ticket_context import (
    requester_legacy_scope_clause,
    requester_neutral_scope_clause,
    requester_reference_snapshot_from_record,
)


class TicketBindingAccessService:
    """Authorize agent ticket actions with the active Registry device binding."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.registration = RegistrationRepo(session)

    async def resolve_agent_binding(self, *, device_id: str) -> dict[str, Any]:
        binding = await self.registration.get_active_primary_binding(device_id)
        if binding is None:
            return {"valid": False, "error_code": "ACTIVE_DEVICE_BINDING_REQUIRED"}
        return {
            "valid": True,
            "binding": {
                "device_id": binding.device_id,
                "binding_id": binding.binding_id,
                "person_id": binding.person_id,
                "asset_id": binding.asset_id,
                "relationship_type": binding.relationship_type,
            },
        }

    async def can_create_ticket(self, *, device_id: str, binding: dict[str, Any]) -> bool:
        return str(binding.get("device_id") or "") == str(device_id)

    async def can_view_ticket(self, *, ticket: Ticket, binding: dict[str, Any]) -> bool:
        return self._ticket_allowed(ticket, binding)

    async def can_send_message(self, *, ticket: Ticket, binding: dict[str, Any]) -> bool:
        return self._ticket_allowed(ticket, binding)

    def _ticket_allowed(self, ticket: Ticket, binding: dict[str, Any]) -> bool:
        if str(getattr(ticket, "device_id", "") or "") != str(binding.get("device_id") or ""):
            return False
        try:
            requester_ref, _requester_snapshot = requester_reference_snapshot_from_record(ticket)
        except (TypeError, ValueError):
            return False
        binding_id = str(binding.get("binding_id") or "")
        person_id = str(binding.get("person_id") or "")
        if requester_ref is not None:
            return bool(person_id and requester_ref.external_id == person_id)
        return bool(
            (binding_id and getattr(ticket, "requester_binding_id", None) == binding_id)
            or (person_id and getattr(ticket, "requester_person_id", None) == person_id)
        )

    def apply_ticket_list_filter(self, stmt, *, binding: dict[str, Any]):
        binding_id = str(binding.get("binding_id") or "")
        person_id = str(binding.get("person_id") or "")
        if not person_id:
            return stmt.where(false())
        neutral_scope = requester_neutral_scope_clause(Ticket)
        legacy_scope = requester_legacy_scope_clause(Ticket)
        clauses = [
            and_(neutral_scope, Ticket.requester_external_ref == person_id),
            and_(legacy_scope, Ticket.requester_person_id == person_id),
        ]
        if binding_id:
            clauses.append(and_(legacy_scope, Ticket.requester_binding_id == binding_id))
        return stmt.where(or_(*clauses))
