"""Reconcile only Registry bindings managed by confirmed inventory assignments."""

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Device, DeviceUserBinding, RegistryEndpointDeviceMapping
from app.repos.inventory_binding_authority import (
    INVENTORY_ACTIVE, INVENTORY_ACTOR as ACTOR, INVENTORY_LEASE, INVENTORY_SOURCE as SOURCE, active_binding_condition,
)
from app.repos.registration_repo import RegistrationRepo
from domain_ports.endpoint import EndpointDeviceProjection, EndpointDeviceRef, EndpointNotFound
from registry.endpoint_possession_service import EndpointMappingUnavailable, ensure_verified_endpoint_mapping
from registry.registration_service import RegistrationService

MAX_SNAPSHOT_AGE = INVENTORY_LEASE


def fresh_inventory_observation(observed_at, *, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    return observed_at is not None and now - MAX_SNAPSHOT_AGE <= observed_at <= now + timedelta(seconds=30)


async def inventory_ticket_targets(session, person_id: str, profile) -> dict[str, str]:
    """Expose a local ID only when an exact mapping and existing ownership agree."""
    references = {str(item.endpoint_device_id): str(item.assignment_id) for item in profile.assignments
                  if item.endpoint_binding_state == "confirmed"}
    if not references:
        return {}
    mapping = RegistryEndpointDeviceMapping
    result = await session.execute(select(mapping.endpoint_device_ref, mapping.device_id)
        .join(Device, Device.device_id == mapping.device_id)
        .join(DeviceUserBinding, DeviceUserBinding.device_id == mapping.device_id)
        .where(mapping.endpoint_device_ref.in_(references), Device.deleted_at.is_(None),
               DeviceUserBinding.person_id == person_id, active_binding_condition()))
    return {references[endpoint_id]: device_id for endpoint_id, device_id in result}


def _assignment_evidence(link, assignment) -> dict[str, str]:
    return {
        "approval_id": link.approval_id,
        "inventory_person_id": link.inventory_person_id,
        "inventory_asset_id": str(assignment.inventory_asset_id),
        "assignment_id": str(assignment.assignment_id),
        "endpoint_binding_id": str(assignment.endpoint_binding_id),
        "endpoint_device_ref": str(assignment.endpoint_device_id),
    }


class InventoryDeviceBindingService:
    def __init__(self, session, endpoint):
        self.session = session
        self.endpoint = endpoint
        self.repo = RegistrationRepo(session)
        self.registration = RegistrationService(session)

    async def _managed(self, person_id: str) -> list[DeviceUserBinding]:
        return list(await self.session.scalars(select(DeviceUserBinding).where(
            DeviceUserBinding.person_id == person_id, DeviceUserBinding.source == SOURCE,
            DeviceUserBinding.status == INVENTORY_ACTIVE,
        ).order_by(DeviceUserBinding.device_id, DeviceUserBinding.binding_id)))

    async def _revoke(self, row: DeviceUserBinding, reason: str) -> None:
        row = await self.session.get(DeviceUserBinding, row.binding_id, with_for_update=True, populate_existing=True)
        if row is None or row.status != INVENTORY_ACTIVE or row.source != SOURCE:
            return
        await self.registration.retire_inventory_binding(row, reason)

    async def _lock_devices(self, ids: set[str]) -> None:
        if ids:
            await self.session.execute(select(Device.device_id).where(Device.device_id.in_(ids))
                .order_by(Device.device_id).with_for_update())

    async def revoke_all(self, person_id: str, reason: str) -> None:
        rows = await self._managed(person_id)
        await self._lock_devices({row.device_id for row in rows})
        for row in rows:
            await self._revoke(row, reason)

    async def _endpoint_projections(self, assignments) -> dict:
        gate = asyncio.Semaphore(4)
        results = {}

        async def read(assignment):
            async with gate:
                reference = EndpointDeviceRef(external_id=str(assignment.endpoint_device_id))
                try:
                    projection = await self.endpoint.read_device(reference)
                except Exception:
                    logger.warning("[inventory_bindings] Endpoint device check unavailable")
                    return
                if isinstance(projection, EndpointNotFound) or (
                    isinstance(projection, EndpointDeviceProjection) and projection.device == reference
                ):
                    results[reference.external_id] = projection

        try:
            async with asyncio.timeout(8):
                await asyncio.gather(*(read(assignment) for assignment in assignments))
        except TimeoutError:
            pass
        return results

    async def reconcile(self, link, profile) -> dict[str, dict]:
        """The caller serializes the link and verifies its active account."""
        now = datetime.now(timezone.utc)
        if (str(profile.inventory_person_id) != link.inventory_person_id
                or not fresh_inventory_observation(profile.observed_at, now=now)
                or (fresh_inventory_observation(link.observed_at, now=now) and profile.observed_at < link.observed_at)):
            return {}
        desired = {}
        for assignment in profile.assignments:
            if assignment.endpoint_binding_state == "confirmed":
                role = "primary_user" if assignment.role == "primary" else "shared_user"
                desired[str(assignment.assignment_id)] = (assignment, role, _assignment_evidence(link, assignment))

        projections = await self._endpoint_projections(item[0] for item in desired.values())
        managed_rows = await self._managed(link.person_id)
        refs = set(projections)
        mapping = RegistryEndpointDeviceMapping
        mapped = dict((await self.session.execute(select(mapping.endpoint_device_ref, mapping.device_id)
            .where(mapping.endpoint_device_ref.in_(refs)))).all()) if refs else {}
        await self._lock_devices({row.device_id for row in managed_rows} | {mapped.get(ref, ref) for ref in refs})
        managed = {}
        for row in await self._managed(link.person_id):
            evidence = row.metadata_json or {}
            assignment_id = evidence.get("assignment_id")
            target = desired.get(assignment_id)
            if target is None or (row.relationship_type, evidence) != (target[1], target[2]):
                await self._revoke(row, "inventory_assignment_changed")
            else:
                managed[assignment_id] = row

        blocked = list(await self.session.scalars(select(DeviceUserBinding.metadata_json).where(
            DeviceUserBinding.person_id == link.person_id, DeviceUserBinding.source == SOURCE,
            DeviceUserBinding.status.in_(("revoked", "transferred", "stale")),
            DeviceUserBinding.revoked_by.is_distinct_from(ACTOR),
        )))
        result = {}
        policy = await self.registration._registration_policy()
        verified_until = min(now, profile.observed_at) + INVENTORY_LEASE
        for key, (assignment, role, evidence) in sorted(desired.items(), key=lambda entry: entry[1][2]["endpoint_device_ref"]):
            current = managed.get(key)
            if any(all((item or {}).get(field) == value for field, value in evidence.items()) for item in blocked):
                if current is not None:
                    await self._revoke(current, "inventory_operator_revoked")
                result[key] = {"state": "conflict"}
                continue
            if role == "shared_user" and not policy.get("allow_shared_devices", True):
                if current is not None:
                    await self._revoke(current, "inventory_shared_policy_disabled")
                result[key] = {"state": "conflict"}
                continue
            reference = str(assignment.endpoint_device_id)
            projection = projections.get(reference)
            if projection is None:
                if current is not None and (current.inventory_verified_until is None or current.inventory_verified_until <= now):
                    await self._revoke(current, "endpoint_confirmation_expired")
                result[key] = {"state": "unavailable"}
                continue
            if isinstance(projection, EndpointNotFound) or projection.retired:
                if current is not None:
                    await self._revoke(current, "endpoint_device_retired")
                result[key] = {"state": "conflict"}
                continue

            try:
                mapping = await ensure_verified_endpoint_mapping(
                    self.session, reference, now=now,
                    hostname=projection.display_name, platform="unknown",
                )
            except EndpointMappingUnavailable:
                if current is not None:
                    await self._revoke(current, "endpoint_mapping_conflict")
                result[key] = {"state": "conflict"}
                continue
            device = await self.session.get(Device, mapping.device_id, with_for_update=True, populate_existing=True)
            if device is None or device.deleted_at is not None:
                if current is not None:
                    await self._revoke(current, "endpoint_mapping_inactive")
                result[key] = {"state": "conflict"}
                continue
            if current is not None and current.device_id != device.device_id:
                await self._revoke(current, "endpoint_mapping_changed")
                current = None

            rows = await self.repo.list_bindings_for_device(
                device.device_id, active_only=True, include_expired_inventory=True,
            )
            asset = await self.registration.registry_repo.get_asset_by_device_id(device.device_id)
            foreign_owner = any(
                row.relationship_type in {"primary_user", "owner"} and row.person_id != link.person_id
                for row in rows
            )
            asset_conflict = asset and (
                asset.status in {"archived", "retired", "deleted"}
                or (role == "primary_user" and asset.assigned_person_id not in (None, link.person_id))
            )
            if (role == "primary_user" and foreign_owner) or asset_conflict:
                if current is not None:
                    await self._revoke(current, "inventory_owner_conflict")
                result[key] = {"state": "conflict"}
                continue
            existing = next((row for row in rows if row.person_id == link.person_id), None)
            if existing is not None:
                if current is not None and current.binding_id == existing.binding_id:
                    current.inventory_verified_until = verified_until
                result[key] = {"state": "bound", "device_id": existing.device_id}
                continue
            if await self.registration.detect_conflicts(device.device_id, link.person_id, role):
                result[key] = {"state": "conflict"}
                continue

            try:
                async with self.session.begin_nested():
                    asset = asset or await self.registration._ensure_asset_for_device(device)
                    row = await self.repo.create_binding(
                        device_id=device.device_id, asset_id=asset.asset_id, person_id=link.person_id,
                        relationship_type=role, status=INVENTORY_ACTIVE, source=SOURCE, valid_from=now,
                        confirmed_at=now, inventory_verified_until=verified_until, metadata_json=evidence,
                    )
                    await self.repo.append_event(
                        event_type="inventory_binding_activated", device_id=device.device_id,
                        person_id=link.person_id, binding_id=row.binding_id, actor_id=ACTOR,
                        actor_role="service", payload=evidence,
                    )
            except IntegrityError:
                result[key] = {"state": "conflict"}
                continue
            result[key] = {"state": "bound", "device_id": device.device_id}
        return result
