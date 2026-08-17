"""Server-owned exact mapping from Helpdesk tickets to Endpoint devices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from app.db.models import Ticket
from domain_ports.endpoint import (
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointDisplayName,
    EndpointNotFound,
    EndpointPort,
    EndpointUnavailable,
    OpaqueEndpointRef,
)


class _ImmutableEndpointDeviceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointDeviceSnapshotV1(_ImmutableEndpointDeviceDTO):
    """The only Endpoint device projection retained on a Helpdesk ticket."""

    schema_version: Literal["endpoint_device_snapshot_v1"] = "endpoint_device_snapshot_v1"
    device_ref: OpaqueEndpointRef
    display_name: EndpointDisplayName
    retired: bool
    last_seen_at: AwareDatetime | None
    captured_at: AwareDatetime
    source: Literal["endpoint_platform"] = "endpoint_platform"


class EndpointDeviceReferenceResolution(_ImmutableEndpointDeviceDTO):
    status: Literal["resolved", "unresolved"]
    code: Literal[
        "ENDPOINT_DEVICE_MAPPING_MISSING",
        "ENDPOINT_UNAVAILABLE",
        "ENDPOINT_DEVICE_MAPPING_INVALID",
    ] | None = None
    device_ref: OpaqueEndpointRef | None = None
    persisted: bool = False


class EndpointDeviceReferenceService:
    """Resolve exactly one server-owned candidate without legacy fallback."""

    def __init__(self, endpoint_port: EndpointPort, session_factory: Callable[[], Any]) -> None:
        self._endpoint_port = endpoint_port
        self._session_factory = session_factory

    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution:
        """Read a candidate, call Endpoint outside DB work, then guarded-persist."""

        async with self._session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            if ticket is None:
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
            existing = getattr(ticket, "endpoint_device_ref", None)
            if existing is not None:
                return self._validated_existing(ticket)
            candidate = getattr(ticket, "device_id", None)

        try:
            device = EndpointDeviceRef(external_id=candidate)
        except ValidationError:
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")

        outcome = await self._endpoint_port.read_device(device)
        if isinstance(outcome, EndpointNotFound):
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
        if isinstance(outcome, EndpointUnavailable):
            return self._unresolved("ENDPOINT_UNAVAILABLE")
        if not isinstance(outcome, EndpointDeviceProjection):
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
        if outcome.device.external_id != device.external_id:
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")

        snapshot = EndpointDeviceSnapshotV1(
            device_ref=outcome.device.external_id,
            display_name=outcome.display_name,
            retired=outcome.retired,
            last_seen_at=outcome.last_seen_at,
            captured_at=datetime.now(timezone.utc),
        )

        async with self._session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            if ticket is None:
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
            existing = getattr(ticket, "endpoint_device_ref", None)
            if existing is not None:
                return self._validated_existing(ticket)
            if getattr(ticket, "device_id", None) != device.external_id:
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
            ticket.endpoint_device_ref = device.external_id
            ticket.endpoint_device_snapshot_json = snapshot.model_dump(mode="json")
            await session.flush()
            return EndpointDeviceReferenceResolution(
                status="resolved",
                device_ref=device.external_id,
                persisted=True,
            )

    @staticmethod
    def _validated_existing(ticket: Ticket) -> EndpointDeviceReferenceResolution:
        try:
            ref = EndpointDeviceRef(external_id=getattr(ticket, "endpoint_device_ref", None))
            raw_snapshot = getattr(ticket, "endpoint_device_snapshot_json", None)
            if raw_snapshot is not None:
                snapshot = EndpointDeviceSnapshotV1.model_validate(raw_snapshot)
                if snapshot.device_ref != ref.external_id:
                    raise ValueError("endpoint device snapshot ref does not match ticket ref")
        except (ValidationError, ValueError):
            return EndpointDeviceReferenceService._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
        return EndpointDeviceReferenceResolution(status="resolved", device_ref=ref.external_id)

    @staticmethod
    def _unresolved(
        code: Literal[
            "ENDPOINT_DEVICE_MAPPING_MISSING",
            "ENDPOINT_UNAVAILABLE",
            "ENDPOINT_DEVICE_MAPPING_INVALID",
        ],
    ) -> EndpointDeviceReferenceResolution:
        return EndpointDeviceReferenceResolution(status="unresolved", code=code)
