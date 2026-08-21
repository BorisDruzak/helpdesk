"""Server-owned exact mapping from Helpdesk tickets to Endpoint devices."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
import re
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

from app.db.models import Ticket, TicketAdminAudit
from domain_ports.endpoint import (
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointDisplayName,
    EndpointNotFound,
    EndpointPort,
    EndpointUnavailable,
    OpaqueEndpointRef,
)


_LOGGER = logging.getLogger(__name__)


class _ImmutableEndpointDeviceDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointDeviceMappingRequestV1(_ImmutableEndpointDeviceDTO):
    """Strict admin intent for an exact, server-verified Endpoint device mapping."""

    schema_version: Literal["endpoint_device_mapping_request_v1"]
    endpoint_device_ref: OpaqueEndpointRef
    replace: StrictBool
    expected_previous_ref: OpaqueEndpointRef | None
    reason: str | None = Field(default=None, min_length=8, max_length=256, strict=True)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is not None and ("://" in value or re.search(r"[\x00-\x1f\x7f]", value)):
            raise ValueError("mapping replacement reason must be control-character- and URL-free")
        return value

    @model_validator(mode="after")
    def validate_replacement_intent(self) -> "EndpointDeviceMappingRequestV1":
        if self.replace:
            if self.expected_previous_ref is None or self.reason is None:
                raise ValueError("mapping replacement requires expected previous ref and reason")
        elif self.expected_previous_ref is not None or self.reason is not None:
            raise ValueError("initial mapping must not provide replacement fields")
        return self


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
        "ENDPOINT_DEVICE_RETIRED",
    ] | None = None
    device_ref: OpaqueEndpointRef | None = None
    persisted: bool = False


async def record_rejected_endpoint_device_mapping(
    *,
    session_factory: Callable[[], Any],
    ticket_id: str,
    requested_endpoint_device_ref: str | None,
    replace: bool,
    reason_code: str,
    actor_id: str,
    actor_role: str,
    request_correlation: str | None,
) -> None:
    """Persist a best-effort safe audit for a rejected admin mapping attempt."""

    safe_requested_ref = _safe_endpoint_ref(requested_endpoint_device_ref)
    safe_correlation = request_correlation if _safe_correlation(request_correlation) else None
    try:
        async with session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            current_ref = _safe_endpoint_ref(
                getattr(ticket, "endpoint_device_ref", None) if ticket is not None else None
            )
            after_json: dict[str, str | bool | None] = {
                "requested_endpoint_device_ref": safe_requested_ref,
                "replace": replace is True,
                "reason_code": reason_code,
            }
            if safe_correlation is not None:
                after_json["request_correlation"] = safe_correlation
            session.add(
                TicketAdminAudit(
                    entity_type="endpoint_device_mapping",
                    entity_id=ticket_id,
                    action="rejected",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    before_json={"endpoint_device_ref": current_ref},
                    after_json=after_json,
                    trace_id=None,
                )
            )
            await session.flush()
            await session.commit()
    except Exception:
        _LOGGER.warning("endpoint_device_mapping_rejected_audit_failed")


class EndpointDeviceReferenceService:
    """Resolve a verified mapping; never derive one from legacy device metadata."""

    def __init__(self, endpoint_port: EndpointPort, session_factory: Callable[[], Any]) -> None:
        self._endpoint_port = endpoint_port
        self._session_factory = session_factory

    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution:
        """Return a previously verified mapping suitable for readiness checks."""

        async with self._session_factory() as session:
            ticket = await session.get(Ticket, ticket_id)
            if ticket is None:
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
            existing = getattr(ticket, "endpoint_device_ref", None)
            if existing is not None:
                return self._validated_existing(ticket)
        return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")

    async def assign_verified_mapping(
        self,
        *,
        ticket_id: str,
        endpoint_device_ref: str,
        replace: bool = False,
        expected_previous_ref: str | None = None,
        reason: str | None = None,
        actor_id: str = "system",
        actor_role: str = "system",
        request_correlation: str | None = None,
    ) -> EndpointDeviceReferenceResolution:
        """Verify the exact provider id before atomically assigning it to a ticket."""

        try:
            device = EndpointDeviceRef(external_id=endpoint_device_ref)
        except ValidationError:
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=None,
                replace=replace,
                reason_code="ENDPOINT_DEVICE_MAPPING_REQUEST_INVALID",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=None,
            )
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")

        outcome = await self._endpoint_port.read_device(device)
        if isinstance(outcome, EndpointNotFound):
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=device.external_id,
                replace=replace,
                reason_code="ENDPOINT_DEVICE_NOT_FOUND",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=request_correlation,
            )
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
        if isinstance(outcome, EndpointUnavailable):
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=device.external_id,
                replace=replace,
                reason_code="ENDPOINT_UNAVAILABLE",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=request_correlation,
            )
            return self._unresolved("ENDPOINT_UNAVAILABLE")
        if not isinstance(outcome, EndpointDeviceProjection):
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=device.external_id,
                replace=replace,
                reason_code="ENDPOINT_DEVICE_MAPPING_INVALID",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=request_correlation,
            )
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
        if outcome.device.external_id != device.external_id:
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=device.external_id,
                replace=replace,
                reason_code="ENDPOINT_DEVICE_MAPPING_EXACT_ID_MISMATCH",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=request_correlation,
            )
            return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
        if outcome.retired:
            await self._record_rejected(
                ticket_id=ticket_id,
                requested_endpoint_device_ref=device.external_id,
                replace=replace,
                reason_code="ENDPOINT_DEVICE_RETIRED",
                actor_id=actor_id,
                actor_role=actor_role,
                request_correlation=request_correlation,
            )
            return self._unresolved("ENDPOINT_DEVICE_RETIRED")

        snapshot = EndpointDeviceSnapshotV1(
            device_ref=outcome.device.external_id,
            display_name=outcome.display_name,
            retired=outcome.retired,
            last_seen_at=outcome.last_seen_at,
            captured_at=datetime.now(timezone.utc),
        )

        async with self._session_factory() as session:
            ticket = await session.get(Ticket, ticket_id, with_for_update=True)
            if ticket is None:
                await self._record_rejected(
                    ticket_id=ticket_id,
                    requested_endpoint_device_ref=device.external_id,
                    replace=replace,
                    reason_code="ENDPOINT_TICKET_NOT_FOUND",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    request_correlation=request_correlation,
                )
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_MISSING")
            existing = getattr(ticket, "endpoint_device_ref", None)
            if existing == device.external_id:
                return EndpointDeviceReferenceResolution(
                    status="resolved",
                    device_ref=device.external_id,
                    persisted=False,
                )
            if existing is None and replace:
                await self._record_rejected(
                    ticket_id=ticket_id,
                    requested_endpoint_device_ref=device.external_id,
                    replace=replace,
                    reason_code="ENDPOINT_DEVICE_MAPPING_REPLACE_NOT_ALLOWED",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    request_correlation=request_correlation,
                )
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
            if existing is not None and not replace:
                await self._record_rejected(
                    ticket_id=ticket_id,
                    requested_endpoint_device_ref=device.external_id,
                    replace=replace,
                    reason_code="ENDPOINT_DEVICE_MAPPING_REPLACE_REQUIRED",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    request_correlation=request_correlation,
                )
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
            if existing is not None and expected_previous_ref != existing:
                await self._record_rejected(
                    ticket_id=ticket_id,
                    requested_endpoint_device_ref=device.external_id,
                    replace=replace,
                    reason_code="ENDPOINT_DEVICE_MAPPING_PREVIOUS_REF_MISMATCH",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    request_correlation=request_correlation,
                )
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
            if existing is not None and reason is None:
                await self._record_rejected(
                    ticket_id=ticket_id,
                    requested_endpoint_device_ref=device.external_id,
                    replace=replace,
                    reason_code="ENDPOINT_DEVICE_MAPPING_REPLACEMENT_REASON_REQUIRED",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    request_correlation=request_correlation,
                )
                return self._unresolved("ENDPOINT_DEVICE_MAPPING_INVALID")
            ticket.endpoint_device_ref = device.external_id
            ticket.endpoint_device_snapshot_json = snapshot.model_dump(mode="json")
            audit_after = {"endpoint_device_ref": device.external_id}
            if reason is not None:
                audit_after["reason"] = reason
            if _safe_correlation(request_correlation):
                audit_after["request_correlation"] = request_correlation
            session.add(
                TicketAdminAudit(
                    entity_type="endpoint_device_mapping",
                    entity_id=ticket_id,
                    action="replaced" if existing is not None else "created",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    before_json=None
                    if existing is None
                    else {"endpoint_device_ref": existing},
                    after_json=audit_after,
                    trace_id=None,
                )
            )
            await session.flush()
            await session.commit()
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
            if raw_snapshot is None:
                raise ValueError("endpoint device mapping has no verified snapshot")
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
            "ENDPOINT_DEVICE_RETIRED",
        ],
    ) -> EndpointDeviceReferenceResolution:
        return EndpointDeviceReferenceResolution(status="unresolved", code=code)

    async def _record_rejected(self, **kwargs: Any) -> None:
        await record_rejected_endpoint_device_mapping(
            session_factory=self._session_factory,
            **kwargs,
        )


def _safe_endpoint_ref(value: object) -> str | None:
    try:
        return EndpointDeviceRef(external_id=value).external_id
    except ValidationError:
        return None


def _safe_correlation(value: str | None) -> bool:
    return bool(
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value)
    )
