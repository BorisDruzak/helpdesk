"""Safe Context API methods sharing the verified HTTPS transport."""
from collections.abc import Mapping
from urllib.parse import quote, urlencode
from uuid import UUID
from typing import TypeVar

from pydantic import BaseModel, ValidationError

try:
    from domain_ports.endpoint import EndpointInvalidProjection, EndpointFailureOutcome, EndpointDeviceRef, OpaqueEndpointRef
    from domain_ports.endpoint_context import (
        EndpointDeviceFleet, EndpointDeviceContext, EndpointContextCollection,
        EndpointCollectionDetails, EndpointContextHistory, EndpointContextComparison,
        SAFE_CONTEXT_PROFILES, SafeContextProfile, HistoryContextProfile,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"domain_ports", "domain_ports.endpoint", "domain_ports.endpoint_context"}:
        raise
    from server.domain_ports.endpoint import EndpointInvalidProjection, EndpointFailureOutcome, EndpointDeviceRef, OpaqueEndpointRef
    from server.domain_ports.endpoint_context import (
        EndpointDeviceFleet, EndpointDeviceContext, EndpointContextCollection,
        EndpointCollectionDetails, EndpointContextHistory, EndpointContextComparison,
        SAFE_CONTEXT_PROFILES, SafeContextProfile, HistoryContextProfile,
    )

from .wire import (DeviceFleetWireV1, DeviceContextWireV1, ContextCollectionWireV1,
    CollectionDetailsWireV1, ContextHistoryWireV1, ContextComparisonWireV1)

_ContextProjection = TypeVar("_ContextProjection", bound=BaseModel)


class EndpointContextHttpMixin:
    async def _context_projection(self, method: str, path: str, model: type[_ContextProjection],
        *, body: Mapping[str, object] | None = None,
        extra_headers: Mapping[str, str] | None = None) -> _ContextProjection | EndpointFailureOutcome:
        payload = await self._request(method, path, expected_statuses=frozenset({200, 201} if method == "POST" else {200}),
            context_contract=True, body=body, extra_headers=extra_headers)
        if not isinstance(payload, Mapping):
            return payload
        try:
            return model.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            return EndpointInvalidProjection()

    async def list_device_fleet(self, *, limit: int = 250, cursor: UUID | None = None) -> EndpointDeviceFleet | EndpointFailureOutcome:
        if type(limit) is not int or not 1 <= limit <= 250 or (cursor is not None and not isinstance(cursor, UUID)):
            return EndpointInvalidProjection()
        query: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            query["cursor"] = str(cursor)
        result = await self._context_projection("GET", f"/api/v1/devices/context-summary?{urlencode(query)}", DeviceFleetWireV1)
        if isinstance(result, EndpointDeviceFleet):
            if len(result.items) > limit or (cursor is not None and any(i.device.id <= cursor for i in result.items)):
                return EndpointInvalidProjection()
        return result

    async def read_device_context(self, device: EndpointDeviceRef) -> EndpointDeviceContext | EndpointFailureOutcome:
        result = await self._context_projection("GET", f"/api/v1/devices/{quote(device.external_id, safe='')}/context", DeviceContextWireV1)
        if isinstance(result, EndpointDeviceContext) and str(result.device.id) != device.external_id:
            return EndpointInvalidProjection()
        return result

    async def request_context_collection(self, device: EndpointDeviceRef, profile: SafeContextProfile, *, idempotency_key: OpaqueEndpointRef) -> EndpointContextCollection | EndpointFailureOutcome:
        if profile not in SAFE_CONTEXT_PROFILES or not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128 or not idempotency_key.isascii() or idempotency_key != idempotency_key.strip() or not self._valid_header_value(idempotency_key):
            return EndpointInvalidProjection()
        result = await self._context_projection("POST", f"/api/v1/devices/{quote(device.external_id, safe='')}/context/collections", ContextCollectionWireV1,
            body={"profile": profile}, extra_headers={"Idempotency-Key": idempotency_key})
        if isinstance(result, EndpointContextCollection) and (str(result.device_id) != device.external_id or result.profile != profile):
            return EndpointInvalidProjection()
        return result

    async def read_context_collection(self, collection: UUID) -> EndpointCollectionDetails | EndpointFailureOutcome:
        if not isinstance(collection, UUID):
            return EndpointInvalidProjection()
        result = await self._context_projection("GET", f"/api/v1/context/collections/{collection}", CollectionDetailsWireV1)
        if isinstance(result, EndpointCollectionDetails) and result.collection.id != collection:
            return EndpointInvalidProjection()
        return result

    async def list_context_history(self, device: EndpointDeviceRef, profile: HistoryContextProfile, *, limit: int = 20) -> EndpointContextHistory | EndpointFailureOutcome:
        if profile not in {"baseline_v1", "inventory_v1"} or type(limit) is not int or not 1 <= limit <= 100:
            return EndpointInvalidProjection()
        query = urlencode({"profile": profile, "limit": limit})
        result = await self._context_projection("GET", f"/api/v1/devices/{quote(device.external_id, safe='')}/context/snapshots?{query}", ContextHistoryWireV1)
        if isinstance(result, EndpointContextHistory) and (len(result.snapshots) > limit or any(s.profile != profile for s in result.snapshots)):
            return EndpointInvalidProjection()
        return result

    async def compare_context_snapshots(self, device: EndpointDeviceRef, before: UUID, after: UUID) -> EndpointContextComparison | EndpointFailureOutcome:
        if not isinstance(before, UUID) or not isinstance(after, UUID) or before == after:
            return EndpointInvalidProjection()
        query = urlencode({"before_snapshot_id": str(before), "after_snapshot_id": str(after)})
        return await self._context_projection("GET", f"/api/v1/devices/{quote(device.external_id, safe='')}/context/snapshots/compare?{query}", ContextComparisonWireV1)
