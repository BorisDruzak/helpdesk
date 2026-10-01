"""Business-only bulk overlay for exact verified Endpoint device identities."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (RegistryEndpointDeviceMapping, RegistryAsset, DeviceUserBinding,
    RegistryPerson, RegistryDepartment, RegistryLocation)


class BusinessDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegistryBindingOverlay(BusinessDTO):
    binding_id: str
    relationship_type: str
    person_id: str
    display_name: str
    department_id: str | None
    department: str | None
    location_id: str | None
    location: str | None


class RegistryDeviceOverlay(BusinessDTO):
    status: Literal["mapped", "unmapped", "unavailable"]
    local_device_id: str | None = None
    asset_id: str | None = None
    asset_name: str | None = None
    inventory_number: str | None = None
    asset_status: str | None = None
    department_id: str | None = None
    department: str | None = None
    location_id: str | None = None
    location: str | None = None
    bindings: tuple[RegistryBindingOverlay, ...] = Field(default=(), max_length=6)
    bindings_truncated: bool = False


async def read_registry_device_overlays(session: AsyncSession, devices: tuple[UUID, ...]) -> dict[UUID, RegistryDeviceOverlay]:
    """Two column-only queries; no hostname/UUID inference and no legacy telemetry."""
    if len(devices) > 250 or len(set(devices)) != len(devices):
        raise ValueError("bounded unique Endpoint identities required")
    result = {device: RegistryDeviceOverlay(status="unmapped") for device in devices}
    if not devices:
        return result
    mapping, asset = RegistryEndpointDeviceMapping, RegistryAsset
    rows = (await session.execute(select(
        mapping.endpoint_device_ref, mapping.device_id, asset.asset_id, asset.name.label("asset_name"),
        asset.inventory_number, asset.status.label("asset_status"), asset.department_id,
        RegistryDepartment.name.label("department"), asset.location_id,
        RegistryLocation.display_name.label("location"),
    ).select_from(mapping).outerjoin(asset, asset.device_id == mapping.device_id)
        .outerjoin(RegistryDepartment, RegistryDepartment.department_id == asset.department_id)
        .outerjoin(RegistryLocation, RegistryLocation.location_id == asset.location_id)
        .where(mapping.endpoint_device_ref.in_(tuple(map(str, devices)))))).mappings().all()
    if not rows:
        return result
    now = datetime.now(timezone.utc)
    binding = DeviceUserBinding
    ranked = select(binding.binding_id,
        func.row_number().over(partition_by=binding.device_id,
            order_by=(case((binding.relationship_type == "primary_user", 0),
                (binding.relationship_type == "responsible", 1), (binding.relationship_type == "owner", 2), else_=3),
                binding.relationship_type, binding.valid_from.desc(), binding.binding_id)).label("position"),
        func.count().over(partition_by=binding.device_id).label("total"),
    ).where(binding.device_id.in_(tuple(row["device_id"] for row in rows)), binding.status == "active",
        binding.valid_from <= now, or_(binding.valid_to.is_(None), binding.valid_to > now)).subquery()
    department, location = aliased(RegistryDepartment), aliased(RegistryLocation)
    bindings = (await session.execute(select(binding.device_id, binding.binding_id, binding.relationship_type,
        RegistryPerson.person_id, RegistryPerson.display_name, RegistryPerson.department_id,
        department.name.label("department"), RegistryPerson.location_id, location.display_name.label("location"), ranked.c.total,
    ).join(ranked, ranked.c.binding_id == binding.binding_id)
        .join(RegistryPerson, RegistryPerson.person_id == binding.person_id)
        .outerjoin(department, department.department_id == RegistryPerson.department_id)
        .outerjoin(location, location.location_id == RegistryPerson.location_id)
        .where(ranked.c.position <= 6).order_by(binding.device_id, ranked.c.position))).mappings().all()
    by_device: dict[str, list[RegistryBindingOverlay]] = {}
    totals: dict[str, int] = {}
    for row in bindings:
        values = dict(row)
        local_id, total = values.pop("device_id"), values.pop("total")
        by_device.setdefault(local_id, []).append(RegistryBindingOverlay(**values))
        totals[local_id] = total
    for row in rows:
        values = dict(row)
        external_id, local_id = UUID(values.pop("endpoint_device_ref")), values.pop("device_id")
        result[external_id] = RegistryDeviceOverlay(status="mapped", local_device_id=local_id,
            bindings=tuple(by_device.get(local_id, ())), bindings_truncated=totals.get(local_id, 0) > 6, **values)
    return result
