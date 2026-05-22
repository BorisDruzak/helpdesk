from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DeviceRegistrationClaim,
    DeviceRegistrationEvent,
    DeviceUserBinding,
    RegistryPerson,
    RegistryPersonIdentity,
)


PENDING_CLAIM_STATUSES = {
    "self_reported",
    "pending_user_confirmation",
    "user_confirmed",
    "pending_admin_review",
    "conflict",
}


def new_id() -> str:
    return str(uuid.uuid4())


def normalize_identifier(provider: str, identifier: str | None) -> str:
    text = re.sub(r"\s+", " ", str(identifier or "").strip())
    if not text:
        return ""
    provider_key = str(provider or "").strip().lower()
    if provider_key in {"email", "ui_login", "windows_login", "ad", "agent_profile", "manual"}:
        text = text.lower()
    if "\\" in text:
        left, right = text.split("\\", 1)
        text = f"{left.strip().lower()}\\{right.strip().lower()}"
    return text


class RegistrationRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_primary_binding(self, device_id: str) -> DeviceUserBinding | None:
        result = await self.session.execute(
            select(DeviceUserBinding)
            .where(
                DeviceUserBinding.device_id == str(device_id),
                DeviceUserBinding.status == "active",
                DeviceUserBinding.relationship_type == "primary_user",
            )
            .order_by(desc(DeviceUserBinding.confirmed_at), desc(DeviceUserBinding.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_bindings_for_device(self, device_id: str) -> list[DeviceUserBinding]:
        result = await self.session.execute(
            select(DeviceUserBinding)
            .where(DeviceUserBinding.device_id == str(device_id), DeviceUserBinding.status == "active")
            .order_by(desc(DeviceUserBinding.created_at))
        )
        return list(result.scalars().all())

    async def list_bindings_for_device(self, device_id: str, active_only: bool = False) -> list[DeviceUserBinding]:
        stmt = select(DeviceUserBinding).where(DeviceUserBinding.device_id == str(device_id))
        if active_only:
            stmt = stmt.where(DeviceUserBinding.status == "active")
        result = await self.session.execute(stmt.order_by(desc(DeviceUserBinding.created_at)))
        return list(result.scalars().all())

    async def list_bindings_for_person(self, person_id: str, active_only: bool = True) -> list[DeviceUserBinding]:
        stmt = select(DeviceUserBinding).where(DeviceUserBinding.person_id == str(person_id))
        if active_only:
            stmt = stmt.where(DeviceUserBinding.status == "active")
        result = await self.session.execute(stmt.order_by(desc(DeviceUserBinding.created_at)))
        return list(result.scalars().all())

    async def get_claim(self, claim_id: str) -> DeviceRegistrationClaim | None:
        return await self.session.get(DeviceRegistrationClaim, str(claim_id))

    async def list_claims(
        self,
        *,
        status: str | None = None,
        device_id: str | None = None,
        person_id: str | None = None,
        limit: int = 100,
    ) -> list[DeviceRegistrationClaim]:
        stmt = select(DeviceRegistrationClaim)
        if status:
            stmt = stmt.where(DeviceRegistrationClaim.status == status)
        if device_id:
            stmt = stmt.where(DeviceRegistrationClaim.device_id == str(device_id))
        if person_id:
            stmt = stmt.where(DeviceRegistrationClaim.person_id == str(person_id))
        result = await self.session.execute(
            stmt.order_by(desc(DeviceRegistrationClaim.submitted_at)).limit(max(1, min(int(limit or 100), 500)))
        )
        return list(result.scalars().all())

    async def list_pending_claims(self, *, limit: int = 100) -> list[DeviceRegistrationClaim]:
        result = await self.session.execute(
            select(DeviceRegistrationClaim)
            .where(DeviceRegistrationClaim.status.in_(sorted(PENDING_CLAIM_STATUSES)))
            .order_by(desc(DeviceRegistrationClaim.submitted_at))
            .limit(max(1, min(int(limit or 100), 500)))
        )
        return list(result.scalars().all())

    async def find_pending_claim(
        self,
        *,
        device_id: str,
        person_id: str | None,
        source: str = "agent_profile",
    ) -> DeviceRegistrationClaim | None:
        stmt = select(DeviceRegistrationClaim).where(
            DeviceRegistrationClaim.device_id == str(device_id),
            DeviceRegistrationClaim.source == source,
            DeviceRegistrationClaim.status.in_(sorted(PENDING_CLAIM_STATUSES)),
        )
        if person_id:
            stmt = stmt.where(DeviceRegistrationClaim.person_id == str(person_id))
        result = await self.session.execute(stmt.order_by(desc(DeviceRegistrationClaim.updated_at)).limit(1))
        return result.scalar_one_or_none()

    async def create_claim(self, **fields: Any) -> DeviceRegistrationClaim:
        row = DeviceRegistrationClaim(claim_id=fields.pop("claim_id", new_id()), **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update_claim_status(self, claim_id: str, status: str, **fields: Any) -> DeviceRegistrationClaim:
        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError("registration claim not found")
        claim.status = status
        for key, value in fields.items():
            if hasattr(claim, key):
                setattr(claim, key, value)
        claim.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return claim

    async def create_or_update_person_identity(
        self,
        *,
        person_id: str,
        provider: str,
        identifier: str | None,
        verified: bool = False,
        source: str = "agent_profile",
        metadata: dict[str, Any] | None = None,
    ) -> RegistryPersonIdentity | None:
        clean_identifier = re.sub(r"\s+", " ", str(identifier or "").strip())
        normalized = normalize_identifier(provider, clean_identifier)
        if not normalized:
            return None
        result = await self.session.execute(
            select(RegistryPersonIdentity)
            .where(
                RegistryPersonIdentity.provider == str(provider),
                RegistryPersonIdentity.normalized_identifier == normalized,
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = RegistryPersonIdentity(
                identity_id=new_id(),
                person_id=str(person_id),
                provider=str(provider),
                identifier=clean_identifier,
                normalized_identifier=normalized,
                verified=verified,
                source=source,
                last_seen_at=now,
                metadata_json=metadata or {},
            )
            self.session.add(row)
        else:
            if row.person_id != str(person_id):
                row.last_seen_at = now
                row.metadata_json = {
                    **(row.metadata_json or {}),
                    **(metadata or {}),
                    "collision_person_id": str(person_id),
                }
                await self.session.flush()
                return row
            row.identifier = clean_identifier
            row.verified = bool(row.verified or verified)
            row.source = source or row.source
            row.last_seen_at = now
            row.metadata_json = {**(row.metadata_json or {}), **(metadata or {})}
        await self.session.flush()
        return row

    async def find_person_by_identity(self, provider: str, identifier: str) -> RegistryPerson | None:
        normalized = normalize_identifier(provider, identifier)
        if not normalized:
            return None
        result = await self.session.execute(
            select(RegistryPerson)
            .join(RegistryPersonIdentity, RegistryPersonIdentity.person_id == RegistryPerson.person_id)
            .where(
                RegistryPersonIdentity.provider == str(provider),
                RegistryPersonIdentity.normalized_identifier == normalized,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_binding(self, **fields: Any) -> DeviceUserBinding:
        row = DeviceUserBinding(binding_id=fields.pop("binding_id", new_id()), **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def revoke_binding(self, binding_id: str, *, revoked_by: str | None = None, reason: str | None = None) -> DeviceUserBinding:
        binding = await self.session.get(DeviceUserBinding, str(binding_id))
        if binding is None:
            raise ValueError("registration binding not found")
        now = datetime.now(timezone.utc)
        binding.status = "revoked"
        binding.valid_to = now
        binding.revoked_at = now
        binding.revoked_by = revoked_by
        binding.revoke_reason = reason
        binding.updated_at = now
        await self.session.flush()
        return binding

    async def mark_binding_stale(self, binding_id: str, *, reason: str | None = None) -> DeviceUserBinding:
        binding = await self.session.get(DeviceUserBinding, str(binding_id))
        if binding is None:
            raise ValueError("registration binding not found")
        now = datetime.now(timezone.utc)
        binding.status = "stale"
        binding.valid_to = now
        binding.revoke_reason = reason
        binding.updated_at = now
        await self.session.flush()
        return binding

    async def append_event(
        self,
        *,
        event_type: str,
        device_id: str,
        claim_id: str | None = None,
        binding_id: str | None = None,
        person_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeviceRegistrationEvent:
        row = DeviceRegistrationEvent(
            event_id=new_id(),
            claim_id=claim_id,
            binding_id=binding_id,
            device_id=str(device_id),
            person_id=person_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            event_at=datetime.now(timezone.utc),
            payload=payload or {},
        )
        self.session.add(row)
        await self.session.flush()
        return row
