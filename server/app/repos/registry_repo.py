from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    RegistryAsset,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryService,
    RegistryVendor,
    Ticket,
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _display_location(building: str, floor: str | None, room: str | None) -> str:
    parts = [building]
    if floor:
        parts.append(f"{floor} этаж")
    if room:
        parts.append(f"кабинет {room}")
    return ", ".join(parts)


class RegistryRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_asset_by_device_id(self, device_id: str) -> RegistryAsset | None:
        result = await self.session.execute(
            select(RegistryAsset).where(RegistryAsset.device_id == device_id)
        )
        return result.scalar_one_or_none()

    async def get_asset(self, asset_id: str | None) -> RegistryAsset | None:
        if not asset_id:
            return None
        result = await self.session.execute(
            select(RegistryAsset).where(RegistryAsset.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def get_person(self, person_id: str | None) -> RegistryPerson | None:
        if not person_id:
            return None
        result = await self.session.execute(
            select(RegistryPerson).where(RegistryPerson.person_id == person_id)
        )
        return result.scalar_one_or_none()

    async def get_location(self, location_id: str | None) -> RegistryLocation | None:
        if not location_id:
            return None
        result = await self.session.execute(
            select(RegistryLocation).where(RegistryLocation.location_id == location_id)
        )
        return result.scalar_one_or_none()

    async def get_department(self, department_id: str | None) -> RegistryDepartment | None:
        if not department_id:
            return None
        result = await self.session.execute(
            select(RegistryDepartment).where(RegistryDepartment.department_id == department_id)
        )
        return result.scalar_one_or_none()

    async def get_service(self, service_id: str | None) -> RegistryService | None:
        if not service_id:
            return None
        result = await self.session.execute(
            select(RegistryService).where(RegistryService.service_id == service_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_department(
        self,
        *,
        name: str | None,
        source: str = "agent_profile",
        status: str = "pending",
    ) -> RegistryDepartment | None:
        clean_name = _clean(name)
        if not clean_name:
            return None
        result = await self.session.execute(
            select(RegistryDepartment).where(func.lower(RegistryDepartment.name) == clean_name.lower())
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        row = RegistryDepartment(
            department_id=_new_id(),
            code=None,
            name=clean_name,
            source=source,
            status=status,
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_or_create_location(
        self,
        *,
        building: str | None,
        floor: str | None = None,
        room: str | None = None,
        source: str = "agent_profile",
        status: str = "pending",
    ) -> RegistryLocation | None:
        clean_building = _clean(building)
        clean_floor = _clean(floor)
        clean_room = _clean(room)
        if not clean_building and not clean_room:
            return None
        if not clean_building:
            clean_building = "Не указано"
        result = await self.session.execute(
            select(RegistryLocation).where(
                RegistryLocation.building == clean_building,
                RegistryLocation.floor.is_(None) if clean_floor is None else RegistryLocation.floor == clean_floor,
                RegistryLocation.room.is_(None) if clean_room is None else RegistryLocation.room == clean_room,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        row = RegistryLocation(
            location_id=_new_id(),
            building=clean_building,
            floor=clean_floor,
            room=clean_room,
            display_name=_display_location(clean_building, clean_floor, clean_room),
            source=source,
            status=status,
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def upsert_person_from_profile(
        self,
        *,
        profile_key: str,
        display_name: str,
        full_name: str | None,
        phone: str | None,
        email: str | None,
        department_id: str | None,
        location_id: str | None,
        metadata: dict[str, Any],
    ) -> RegistryPerson:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(RegistryPerson).where(
                RegistryPerson.source == "agent_profile",
                RegistryPerson.profile_key == profile_key,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = RegistryPerson(
                person_id=_new_id(),
                display_name=display_name,
                full_name=full_name,
                phone=phone,
                email=email,
                department_id=department_id,
                location_id=location_id,
                source="agent_profile",
                status="self_reported",
                profile_key=profile_key,
                last_seen_at=now,
                metadata_json=metadata,
            )
            self.session.add(row)
        else:
            row.display_name = display_name
            row.full_name = full_name
            row.phone = phone
            row.email = email
            row.department_id = department_id
            row.location_id = location_id
            row.last_seen_at = now
            row.metadata_json = metadata
        await self.session.flush()
        return row

    async def upsert_agent_asset(
        self,
        *,
        device_id: str,
        hostname: str | None,
        os_name: str | None,
        agent_version: str | None,
        metadata: dict[str, Any],
    ) -> RegistryAsset:
        now = datetime.now(timezone.utc)
        row = await self.get_asset_by_device_id(device_id)
        payload = dict(metadata or {})
        if os_name is not None:
            payload["os"] = os_name
        if agent_version is not None:
            payload["agent_version"] = agent_version
        name = hostname or device_id
        if row is None:
            row = RegistryAsset(
                asset_id=_new_id(),
                asset_type="pc",
                name=name,
                hostname=hostname,
                device_id=device_id,
                source="agent",
                status="unverified",
                discovery_payload=payload,
                last_seen_at=now,
            )
            self.session.add(row)
        else:
            row.name = row.name or name
            row.hostname = hostname or row.hostname
            row.discovery_payload = {**(row.discovery_payload or {}), **payload}
            row.last_seen_at = now
        await self.session.flush()
        return row

    async def link_asset_to_person_location(
        self,
        *,
        device_id: str,
        person_id: str | None,
        location_id: str | None,
        department_id: str | None,
    ) -> RegistryAsset | None:
        asset = await self.get_asset_by_device_id(device_id)
        if not asset:
            return None
        if person_id:
            asset.assigned_person_id = person_id
        if location_id:
            asset.location_id = location_id
        if department_id:
            asset.department_id = department_id
        await self.session.flush()
        return asset

    async def list_assets(self, *, limit: int = 200) -> list[RegistryAsset]:
        result = await self.session.execute(
            select(RegistryAsset).order_by(RegistryAsset.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_people(self, *, limit: int = 200) -> list[RegistryPerson]:
        result = await self.session.execute(
            select(RegistryPerson).order_by(RegistryPerson.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def list_locations(self, *, limit: int = 200) -> list[RegistryLocation]:
        result = await self.session.execute(
            select(RegistryLocation).order_by(RegistryLocation.building, RegistryLocation.room).limit(limit)
        )
        return list(result.scalars().all())

    async def list_departments(self) -> list[RegistryDepartment]:
        result = await self.session.execute(
            select(RegistryDepartment).order_by(RegistryDepartment.name)
        )
        return list(result.scalars().all())

    async def list_services(self) -> list[RegistryService]:
        result = await self.session.execute(
            select(RegistryService).order_by(RegistryService.name)
        )
        return list(result.scalars().all())

    async def list_vendors(self) -> list[RegistryVendor]:
        result = await self.session.execute(
            select(RegistryVendor).order_by(RegistryVendor.name)
        )
        return list(result.scalars().all())

    async def count_tickets_by_device_ids(self, device_ids: Iterable[str]) -> dict[str, int]:
        ids = [item for item in device_ids if item]
        if not ids:
            return {}
        result = await self.session.execute(
            select(Ticket.device_id, func.count(Ticket.ticket_id))
            .where(Ticket.device_id.in_(ids))
            .group_by(Ticket.device_id)
        )
        return {str(device_id): int(count) for device_id, count in result.all()}
