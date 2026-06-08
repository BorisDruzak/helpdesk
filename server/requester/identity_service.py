from __future__ import annotations

from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.serializers import ticket_to_dict
from app.db.models import Device, DeviceAccountSession, DeviceRegistrationClaim, DeviceUserBinding, RegistryAsset, RegistryPerson, Ticket
from app.repos.registration_repo import RegistrationRepo
from app.repos.registry_repo import RegistryRepo


class RequesterIdentityResolver:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registration_repo = RegistrationRepo(session)
        self.registry_repo = RegistryRepo(session)

    async def resolve_person_for_web_user(self, actor_id: str) -> RegistryPerson | None:
        login = str(actor_id or "").strip()
        if not login:
            return None
        for provider in ("ui_login", "email", "windows_login", "ad"):
            person = await self.registration_repo.find_person_by_identity(provider, login)
            if person is not None:
                return person
        return None

    async def list_active_bindings(self, person_id: str | None) -> list[DeviceUserBinding]:
        if not person_id:
            return []
        return await self.registration_repo.list_bindings_for_person(person_id, active_only=True)

    async def list_owned_sessions(self, person_id: str | None, binding_ids: list[str]) -> list[DeviceAccountSession]:
        clauses = []
        if person_id:
            clauses.append(DeviceAccountSession.person_id == str(person_id))
        if binding_ids:
            clauses.append(DeviceAccountSession.binding_id.in_(binding_ids))
        if not clauses:
            return []
        result = await self.session.execute(
            select(DeviceAccountSession)
            .where(or_(*clauses))
            .where(DeviceAccountSession.verification_status.in_(["verified", "pending_verification"]))
            .order_by(desc(DeviceAccountSession.created_at))
        )
        return list(result.scalars().all())

    async def list_allowed_devices(self, person_id: str | None) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        for binding in await self.list_active_bindings(person_id):
            device = await self.session.get(Device, binding.device_id)
            asset = await self.registry_repo.get_asset_by_device_id(binding.device_id)
            devices.append(self.serialize_device(binding, device, asset))
        return devices

    def serialize_person(self, person: RegistryPerson | None) -> dict[str, Any] | None:
        if person is None:
            return None
        return {
            "person_id": person.person_id,
            "display_name": person.display_name,
            "full_name": person.full_name,
            "email": person.email,
            "phone": person.phone,
            "department_id": person.department_id,
            "location_id": person.location_id,
            "status": person.status,
        }

    def serialize_device(
        self,
        binding: DeviceUserBinding,
        device: Device | None,
        asset: RegistryAsset | None,
    ) -> dict[str, Any]:
        return {
            "device_id": binding.device_id,
            "binding_id": binding.binding_id,
            "relationship_type": binding.relationship_type,
            "binding_status": binding.status,
            "hostname": getattr(device, "hostname", None) or getattr(asset, "hostname", None),
            "os": getattr(device, "os", None) or ((getattr(asset, "discovery_payload", None) or {}).get("os") if asset else None),
            "agent_version": getattr(device, "agent_version", None)
            or ((getattr(asset, "discovery_payload", None) or {}).get("agent_version") if asset else None),
            "last_seen_at": getattr(getattr(device, "last_seen_at", None), "isoformat", lambda: None)(),
            "online": False,
            "asset_id": getattr(asset, "asset_id", None),
            "asset_name": getattr(asset, "name", None),
        }

    async def get_owned_device_ids(self, person_id: str | None) -> set[str]:
        return {binding.device_id for binding in await self.list_active_bindings(person_id)}

    async def require_owned_device(self, *, actor_id: str, device_id: str) -> tuple[RegistryPerson | None, DeviceUserBinding]:
        person = await self.resolve_person_for_web_user(actor_id)
        if person is None:
            raise PermissionError("requester person not found")
        for binding in await self.list_active_bindings(person.person_id):
            if binding.device_id == str(device_id):
                return person, binding
        raise PermissionError("device is not owned by requester")

    async def list_tickets(self, *, actor_id: str, limit: int = 100) -> list[Ticket]:
        person = await self.resolve_person_for_web_user(actor_id)
        bindings = await self.list_active_bindings(person.person_id if person else None)
        binding_ids = [binding.binding_id for binding in bindings]
        sessions = await self.list_owned_sessions(person.person_id if person else None, binding_ids)
        session_ids = [session.session_id for session in sessions]
        clauses = [Ticket.requester_id == str(actor_id)]
        if person is not None:
            clauses.append(Ticket.requester_person_id == person.person_id)
        if binding_ids:
            clauses.append(Ticket.requester_binding_id.in_(binding_ids))
        if session_ids:
            clauses.append(Ticket.requester_account_session_id.in_(session_ids))
        result = await self.session.execute(
            select(Ticket)
            .where(or_(*clauses))
            .order_by(desc(Ticket.created_at))
            .limit(max(1, min(int(limit or 100), 300)))
        )
        return list(result.scalars().all())

    async def get_ticket(self, *, actor_id: str, ticket_id: str) -> Ticket | None:
        tickets = await self.list_tickets(actor_id=actor_id, limit=300)
        for ticket in tickets:
            if ticket.ticket_id == str(ticket_id):
                return ticket
        return None

    async def count_open_tickets(self, *, actor_id: str) -> int:
        tickets = await self.list_tickets(actor_id=actor_id, limit=300)
        return sum(1 for ticket in tickets if str(getattr(ticket, "status", "") or "") not in {"resolved", "closed", "canceled"})

    async def list_pending_claims(self, person_id: str | None) -> list[dict[str, Any]]:
        if not person_id:
            return []
        result = await self.session.execute(
            select(DeviceRegistrationClaim)
            .where(DeviceRegistrationClaim.person_id == str(person_id))
            .where(DeviceRegistrationClaim.status.in_(["self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "conflict"]))
            .order_by(desc(DeviceRegistrationClaim.submitted_at))
            .limit(50)
        )
        return [
            {
                "claim_id": claim.claim_id,
                "device_id": claim.device_id,
                "status": claim.status,
                "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
            }
            for claim in result.scalars().all()
        ]

    async def build_bootstrap(self, *, actor_id: str) -> dict[str, Any]:
        person = await self.resolve_person_for_web_user(actor_id)
        devices = await self.list_allowed_devices(person.person_id if person else None)
        tickets = await self.list_tickets(actor_id=actor_id, limit=25)
        return {
            "workspace": "requester",
            "profile": self.serialize_person(person),
            "devices": devices,
            "active_bindings": [
                {
                    "binding_id": device["binding_id"],
                    "device_id": device["device_id"],
                    "relationship_type": device["relationship_type"],
                    "status": device["binding_status"],
                }
                for device in devices
            ],
            "pending_registration_claims": await self.list_pending_claims(person.person_id if person else None),
            "open_ticket_count": sum(1 for ticket in tickets if str(getattr(ticket, "status", "") or "") not in {"resolved", "closed", "canceled"}),
            "tickets_requiring_user_action_count": sum(
                1 for ticket in tickets if str(getattr(ticket, "next_action_owner", "") or "") == "requester"
            ),
            "pending_consent_count": 0,
            "recent_tickets": [ticket_to_dict(ticket, visibility="requester") for ticket in tickets[:10]],
            "feature_flags": {
                "requester_ticket_create": True,
                "requester_owned_device_create": True,
                "requester_no_device_create": False,
            },
            "policies": {"device_selection_required": True},
        }
