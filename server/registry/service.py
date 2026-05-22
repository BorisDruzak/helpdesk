from __future__ import annotations

from dataclasses import dataclass, field
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
    registration: dict[str, Any] = field(default_factory=dict)


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
        from registry.registration_service import RegistrationService

        profile = profile or {}
        full_name = _clean(profile.get("full_name")) or _clean(display_name) or _clean(requester_id) or "Unknown user"
        person_display_name = _clean(display_name) or full_name
        result = await RegistrationService(self.session).submit_agent_profile_claim(
            device_id=device_id or "",
            requester_id=requester_id,
            display_name=person_display_name,
            profile={**profile, "full_name": full_name},
            actor_id=requester_id,
            actor_role="agent",
        )
        registration = result.get("registration") if isinstance(result.get("registration"), dict) else {}
        person_payload = result.get("person") if isinstance(result.get("person"), dict) else {}
        asset_payload = result.get("asset") if isinstance(result.get("asset"), dict) else {}
        person = await self.repo.get_person(person_payload.get("person_id"))
        asset = await self.repo.get_asset(asset_payload.get("asset_id"))
        location = await self.repo.get_location(person.location_id if person else None)
        department = await self.repo.get_department(person.department_id if person else None)

        return RegistryProfileIngestResult(
            person_id=person.person_id if person else "",
            asset_id=asset.asset_id if asset else None,
            location_id=location.location_id if location else None,
            department_id=department.department_id if department else None,
            registration=registration,
        )


class RegistrySnapshotService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RegistryRepo(session)

    async def build_snapshot(self) -> dict[str, Any]:
        from registry.registration_service import RegistrationService

        registration_service = RegistrationService(self.session)
        assets = await self.repo.list_assets()
        people = await self.repo.list_people()
        locations = await self.repo.list_locations()
        departments = await self.repo.list_departments()
        services = await self.repo.list_services()
        vendors = await self.repo.list_vendors()
        claims = await registration_service.repo.list_claims(limit=300)
        bindings = []
        for asset in assets:
            if asset.device_id:
                bindings.extend(await registration_service.repo.list_active_bindings_for_device(asset.device_id))

        people_by_id = {person.person_id: person for person in people}
        locations_by_id = {location.location_id: location for location in locations}
        departments_by_id = {department.department_id: department for department in departments}
        active_by_device = {binding.device_id: binding for binding in bindings if binding.status == "active"}
        pending_by_device: dict[str, list[Any]] = {}
        for claim in claims:
            if claim.status in {"self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review", "conflict"}:
                pending_by_device.setdefault(claim.device_id, []).append(claim)
        ticket_counts = await self.repo.count_tickets_by_device_ids([asset.device_id for asset in assets if asset.device_id])

        data_quality = []
        for asset in assets:
            active_binding = active_by_device.get(asset.device_id or "")
            pending_claims = pending_by_device.get(asset.device_id or "", [])
            if asset.asset_type == "pc" and not asset.location_id:
                data_quality.append({
                    "kind": "asset_missing_location",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "PC without location",
                    "description": asset.name,
                    "details": asset.name,
                })
            if asset.asset_type == "pc" and not active_binding:
                data_quality.append({
                    "kind": "asset_missing_confirmed_user",
                    "severity": "warning",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "PC without confirmed user",
                    "description": asset.name,
                    "details": asset.name,
                })
            if any(claim.status in {"pending_user_confirmation", "self_reported", "user_confirmed", "pending_admin_review"} for claim in pending_claims):
                data_quality.append({
                    "kind": "registration_pending_confirmation",
                    "severity": "info",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "Registration pending",
                    "description": asset.name,
                    "details": asset.name,
                })
            conflict = next((claim for claim in pending_claims if claim.status == "conflict"), None)
            if conflict:
                data_quality.append({
                    "kind": "registration_conflict",
                    "severity": "error",
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "Registration conflict",
                    "description": conflict.conflict_reason or asset.name,
                    "details": conflict.conflict_reason or asset.name,
                })
        for binding in bindings:
            if binding.status == "stale":
                data_quality.append({
                    "kind": "binding_stale",
                    "severity": "warning",
                    "object_type": "binding",
                    "object_id": binding.binding_id,
                    "title": "Registration binding is stale",
                    "description": binding.device_id,
                    "details": binding.device_id,
                })
        for location in locations:
            if location.status == "pending":
                data_quality.append({
                    "kind": "location_pending_confirmation",
                    "severity": "info",
                    "object_type": "location",
                    "object_id": location.location_id,
                    "title": "Location pending confirmation",
                    "description": location.display_name,
                    "details": location.display_name,
                })

        suggestions = []
        for asset in assets:
            active_binding = active_by_device.get(asset.device_id or "")
            person = people_by_id.get(active_binding.person_id if active_binding else asset.assigned_person_id or "")
            if asset.hostname and person:
                suggestions.append({
                    "kind": "hostname_person_link",
                    "asset_id": asset.asset_id,
                    "person_id": person.person_id,
                    "object_type": "asset",
                    "object_id": asset.asset_id,
                    "title": "PC and user link exists",
                    "description": f"{asset.hostname} -> {person.display_name}",
                    "details": f"{asset.hostname} -> {person.display_name}",
                    "confidence": 0.95,
                })

        def claim_payload(claim: Any) -> dict[str, Any]:
            person = people_by_id.get(claim.person_id or "")
            return {
                "claim_id": claim.claim_id,
                "device_id": claim.device_id,
                "asset_id": claim.asset_id,
                "person_id": claim.person_id,
                "person_name": person.display_name if person else None,
                "status": claim.status,
                "claim_type": claim.claim_type,
                "relationship_type": claim.relationship_type,
                "confidence": float(claim.confidence) if claim.confidence is not None else None,
                "submitted_at": claim.submitted_at.isoformat() if claim.submitted_at else None,
                "conflict_reason": claim.conflict_reason,
                "profile_snapshot": claim.profile_snapshot or {},
            }

        def binding_payload(binding: Any) -> dict[str, Any]:
            person = people_by_id.get(binding.person_id or "")
            return {
                "binding_id": binding.binding_id,
                "device_id": binding.device_id,
                "asset_id": binding.asset_id,
                "person_id": binding.person_id,
                "person_name": person.display_name if person else None,
                "relationship_type": binding.relationship_type,
                "status": binding.status,
                "confirmed_at": binding.confirmed_at.isoformat() if binding.confirmed_at else None,
                "confirmed_by_admin": binding.confirmed_by_admin,
            }

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
                "registrations_pending": sum(1 for claim in claims if claim.status in {"self_reported", "pending_user_confirmation", "user_confirmed", "pending_admin_review"}),
                "registrations_conflicts": sum(1 for claim in claims if claim.status == "conflict"),
                "unregistered_devices": sum(1 for asset in assets if asset.asset_type == "pc" and not active_by_device.get(asset.device_id or "")),
                "active_bindings": sum(1 for binding in bindings if binding.status == "active"),
                "stale_bindings": sum(1 for binding in bindings if binding.status == "stale"),
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
                    "registration_status": "admin_confirmed"
                    if active_by_device.get(asset.device_id or "")
                    else ("conflict" if any(claim.status == "conflict" for claim in pending_by_device.get(asset.device_id or "", [])) else ("pending" if pending_by_device.get(asset.device_id or "") else "unregistered")),
                    "active_binding_id": active_by_device.get(asset.device_id or "").binding_id
                    if active_by_device.get(asset.device_id or "")
                    else None,
                    "active_person_id": active_by_device.get(asset.device_id or "").person_id
                    if active_by_device.get(asset.device_id or "")
                    else None,
                    "active_person_name": people_by_id.get(active_by_device.get(asset.device_id or "").person_id).display_name
                    if active_by_device.get(asset.device_id or "") and active_by_device.get(asset.device_id or "").person_id in people_by_id
                    else None,
                    "pending_claim_count": len(pending_by_device.get(asset.device_id or "", [])),
                    "last_claim_at": max(
                        (claim.submitted_at for claim in pending_by_device.get(asset.device_id or "", []) if claim.submitted_at),
                        default=None,
                    ).isoformat()
                    if pending_by_device.get(asset.device_id or "")
                    else None,
                    "current_os_user": None,
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
            "registration_claims": [claim_payload(claim) for claim in claims],
            "active_bindings": [binding_payload(binding) for binding in bindings],
            "data_quality": data_quality,
            "suggestions": suggestions,
        }
