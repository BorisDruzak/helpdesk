from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.registry_repo import RegistryRepo


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True)
class RegistryProfileIngestResult:
    person_id: str
    asset_id: str | None
    location_id: str | None
    department_id: str | None


class RegistryIngestionService:
    """Converts discovered/self-reported agent data into registry records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistryRepo(session)

    async def ingest_agent_handshake(
        self,
        *,
        device_id: str,
        hostname: str | None,
        os_name: str | None,
        agent_version: str | None,
        metadata: dict[str, Any] | None = None,
    ):
        return await self.repo.upsert_agent_asset(
            device_id=device_id,
            hostname=_clean(hostname),
            os_name=_clean(os_name),
            agent_version=_clean(agent_version),
            metadata=metadata or {},
        )

    async def ingest_requester_profile(
        self,
        *,
        device_id: str | None,
        requester_id: str | None,
        display_name: str | None,
        profile: dict[str, Any] | None,
    ) -> RegistryProfileIngestResult:
        profile = profile or {}
        full_name = _clean(profile.get("full_name")) or _clean(display_name) or _clean(requester_id) or "Без имени"
        person_display_name = _clean(display_name) or full_name
        profile_key = _clean(requester_id) or person_display_name

        department = await self.repo.get_or_create_department(
            name=profile.get("department"),
            source="agent_profile",
            status="pending",
        )
        location = await self.repo.get_or_create_location(
            building=profile.get("building"),
            floor=profile.get("floor"),
            room=profile.get("room"),
            source="agent_profile",
            status="pending",
        )
        person = await self.repo.upsert_person_from_profile(
            profile_key=profile_key,
            display_name=person_display_name,
            full_name=full_name,
            phone=_clean(profile.get("phone")),
            email=_clean(profile.get("email")),
            department_id=department.department_id if department else None,
            location_id=location.location_id if location else None,
            metadata={"profile": profile},
        )

        asset = None
        if device_id:
            asset = await self.repo.get_asset_by_device_id(device_id)
            if asset is None:
                asset = await self.repo.upsert_agent_asset(
                    device_id=device_id,
                    hostname=None,
                    os_name=None,
                    agent_version=None,
                    metadata={"source": "profile_upsert"},
                )
            asset = await self.repo.link_asset_to_person_location(
                device_id=device_id,
                person_id=person.person_id,
                location_id=location.location_id if location else None,
                department_id=department.department_id if department else None,
            )
            from inventory.service import DeviceInventoryService

            await DeviceInventoryService(self.session).create_or_update_binding_suggestion_from_profile(
                device_id=device_id,
                requester_id=requester_id,
                display_name=person_display_name,
                profile={**profile, "full_name": full_name},
            )

        return RegistryProfileIngestResult(
            person_id=person.person_id,
            asset_id=asset.asset_id if asset else None,
            location_id=location.location_id if location else None,
            department_id=department.department_id if department else None,
        )


class RegistrySnapshotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistryRepo(session)

    async def build_snapshot(self) -> dict[str, Any]:
        assets = await self.repo.list_assets()
        people = await self.repo.list_people()
        locations = await self.repo.list_locations()
        departments = await self.repo.list_departments()
        services = await self.repo.list_services()
        vendors = await self.repo.list_vendors()

        people_by_id = {person.person_id: person for person in people}
        locations_by_id = {location.location_id: location for location in locations}
        departments_by_id = {department.department_id: department for department in departments}
        ticket_counts = await self.repo.count_tickets_by_device_ids(
            [asset.device_id for asset in assets if asset.device_id]
        )

        data_quality = []
        for asset in assets:
            if asset.asset_type == "pc" and not asset.location_id:
                data_quality.append({
                    "kind": "asset_missing_location",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "ПК без кабинета",
                    "description": asset.name,
                    "details": asset.name,
                })
            if asset.asset_type == "pc" and not asset.assigned_person_id:
                data_quality.append({
                    "kind": "asset_missing_owner",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "ПК без ответственного",
                    "description": asset.name,
                    "details": asset.name,
                })
        for location in locations:
            if location.status == "pending":
                data_quality.append({
                    "kind": "location_pending_confirmation",
                    "severity": "info",
                    "object_type": "location",
                    "object_id": location.location_id,
                    "title": "Локация ждёт подтверждения",
                    "description": location.display_name,
                    "details": location.display_name,
                })

        suggestions = []
        for asset in assets:
            person = people_by_id.get(asset.assigned_person_id or "")
            if asset.hostname and person:
                suggestions.append({
                    "kind": "hostname_person_link",
                    "asset_id": asset.asset_id,
                    "person_id": person.person_id,
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "Связь ПК и пользователя подтверждена профилем агента",
                    "description": f"{asset.hostname} -> {person.display_name}",
                    "details": f"{asset.hostname} -> {person.display_name}",
                    "confidence": 0.95,
                })

        return {
            "summary": {
                "assets_count": len(assets),
                "assets": len(assets),
                "people_count": len(people),
                "people": len(people),
                "locations_count": len(locations),
                "locations": len(locations),
                "departments_count": len(departments),
                "departments": len(departments),
                "services_count": len(services),
                "services": len(services),
                "vendors_count": len(vendors),
                "vendors": len(vendors),
                "data_quality_issue_count": len(data_quality),
                "data_quality_issues": len(data_quality),
                "suggestions_count": len(suggestions),
                "suggestions": len(suggestions),
            },
            "assets": [
                {
                    "id": asset.asset_id,
                    "asset_id": asset.asset_id,
                    "asset_type": asset.asset_type,
                    "name": asset.name,
                    "hostname": asset.hostname,
                    "device_id": asset.device_id,
                    "inventory_number": asset.inventory_number,
                    "serial_number": asset.serial_number,
                    "status": asset.status,
                    "source": asset.source,
                    "location_id": asset.location_id,
                    "location_name": locations_by_id.get(asset.location_id or "").display_name
                    if asset.location_id in locations_by_id
                    else None,
                    "location_display_name": locations_by_id.get(asset.location_id or "").display_name
                    if asset.location_id in locations_by_id
                    else None,
                    "assigned_person_id": asset.assigned_person_id,
                    "owner_name": people_by_id.get(asset.assigned_person_id or "").display_name
                    if asset.assigned_person_id in people_by_id
                    else None,
                    "assigned_person_display_name": people_by_id.get(asset.assigned_person_id or "").display_name
                    if asset.assigned_person_id in people_by_id
                    else None,
                    "department_id": asset.department_id,
                    "department_name": departments_by_id.get(asset.department_id or "").name
                    if asset.department_id in departments_by_id
                    else None,
                    "service_id": asset.service_id,
                    "service_name": None,
                    "vendor_id": asset.vendor_id,
                    "vendor_name": None,
                    "last_seen_at": asset.last_seen_at.isoformat() if asset.last_seen_at else None,
                    "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
                    "ticket_count": ticket_counts.get(asset.device_id or "", 0),
                }
                for asset in assets
            ],
            "people": [
                {
                    "id": person.person_id,
                    "person_id": person.person_id,
                    "display_name": person.display_name,
                    "full_name": person.full_name,
                    "phone": person.phone,
                    "email": person.email,
                    "status": person.status,
                    "source": person.source,
                    "department_id": person.department_id,
                    "department_name": departments_by_id.get(person.department_id or "").name
                    if person.department_id in departments_by_id
                    else None,
                    "location_id": person.location_id,
                    "location_display_name": locations_by_id.get(person.location_id or "").display_name
                    if person.location_id in locations_by_id
                    else None,
                    "location_name": locations_by_id.get(person.location_id or "").display_name
                    if person.location_id in locations_by_id
                    else None,
                    "updated_at": person.updated_at.isoformat() if person.updated_at else None,
                }
                for person in people
            ],
            "locations": [
                {
                    "id": location.location_id,
                    "location_id": location.location_id,
                    "building": location.building,
                    "floor": location.floor,
                    "room": location.room,
                    "display_name": location.display_name,
                    "status": location.status,
                    "source": location.source,
                    "updated_at": location.updated_at.isoformat() if location.updated_at else None,
                }
                for location in locations
            ],
            "departments": [
                {
                    "id": department.department_id,
                    "department_id": department.department_id,
                    "code": department.code,
                    "name": department.name,
                    "status": department.status,
                    "source": department.source,
                    "updated_at": department.updated_at.isoformat() if department.updated_at else None,
                }
                for department in departments
            ],
            "services": [
                {
                    "id": service.service_id,
                    "service_id": service.service_id,
                    "code": service.code,
                    "name": service.name,
                    "owner_queue_id": service.owner_queue_id,
                    "owner_person_id": None,
                    "support_queue": str(service.owner_queue_id) if service.owner_queue_id else None,
                    "vendor_id": service.vendor_id,
                    "source": service.source,
                    "status": service.status,
                    "updated_at": service.updated_at.isoformat() if service.updated_at else None,
                }
                for service in services
            ],
            "vendors": [
                {
                    "id": vendor.vendor_id,
                    "vendor_id": vendor.vendor_id,
                    "code": None,
                    "name": vendor.name,
                    "contact_name": vendor.contact_name,
                    "phone": vendor.contact_phone,
                    "email": vendor.contact_email,
                    "contact_phone": vendor.contact_phone,
                    "contact_email": vendor.contact_email,
                    "source": vendor.source,
                    "status": vendor.status,
                    "updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None,
                }
                for vendor in vendors
            ],
            "data_quality": data_quality,
            "suggestions": suggestions,
        }
