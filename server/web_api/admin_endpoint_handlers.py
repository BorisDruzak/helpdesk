"""Authenticated safe Endpoint Context BFF with canonical Registry overlay."""
from uuid import UUID, uuid4

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from auth.middleware import require_auth
from domain_ports.container import DomainPortContainer
from domain_ports.endpoint import EndpointDeviceRef, EndpointNotFound, EndpointUnavailable
from domain_ports.endpoint_context import (EndpointDeviceFleet, EndpointDeviceContext, EndpointContextCollection,
    EndpointCollectionDetails, EndpointContextHistory, EndpointContextComparison, SafeContextProfile, SAFE_CONTEXT_PROFILES)
from registry.endpoint_device_overlay import read_registry_device_overlays, RegistryDeviceOverlay


class ContextRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profiles: tuple[SafeContextProfile, ...] = Field(default=SAFE_CONTEXT_PROFILES, min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_profiles(self):
        if len(set(self.profiles)) != len(self.profiles):
            raise ValueError("duplicate profiles")
        return self


def _success(data, *, status=200):
    return web.json_response({"status": "success", "data": data}, status=status, headers={"Cache-Control": "no-store"})


def _error(status, code):
    return web.json_response({"status": "error", "error_code": code}, status=status, headers={"Cache-Control": "no-store"})


def _failure(outcome):
    status = 404 if isinstance(outcome, EndpointNotFound) else 503 if isinstance(outcome, EndpointUnavailable) else 502
    return _error(status, outcome.code)


def _device(request):
    # Canonicalize validated UUID only; never search the fleet or infer a local identity.
    return EndpointDeviceRef(external_id=str(UUID(request.match_info["device_id"])))


async def _overlays(devices):
    try:
        async with get_session() as session:
            return await read_registry_device_overlays(session, devices)
    except SQLAlchemyError:
        return {device: RegistryDeviceOverlay(status="unavailable") for device in devices}


@require_auth("admin", "support", "auditor")
async def handle_admin_endpoint_devices(request):
    try:
        if set(request.query) - {"limit", "cursor"}:
            raise ValueError()
        limit = int(request.query.get("limit", "250"))
        cursor = UUID(request.query["cursor"]) if "cursor" in request.query else None
        if not 1 <= limit <= 250:
            raise ValueError()
    except (ValueError, TypeError):
        return _error(400, "invalid_query")
    outcome = await DomainPortContainer.from_config().endpoint.list_device_fleet(limit=limit, cursor=cursor)
    if not isinstance(outcome, EndpointDeviceFleet):
        return _failure(outcome)
    overlays = await _overlays(tuple(item.device.id for item in outcome.items))
    return _success({"items": [{**item.model_dump(mode="json"), "registry": overlays[item.device.id].model_dump(mode="json")}
        for item in outcome.items], "next_cursor": str(outcome.next_cursor) if outcome.next_cursor else None,
        "technical_source": "endpoint", "business_source": "registry"})


@require_auth("admin", "support", "auditor")
async def handle_admin_endpoint_device(request):
    try:
        device = _device(request)
    except (ValueError, KeyError):
        return _error(400, "invalid_device_id")
    outcome = await DomainPortContainer.from_config().endpoint.read_device_context(device)
    if not isinstance(outcome, EndpointDeviceContext):
        return _failure(outcome)
    overlays = await _overlays((outcome.device.id,))
    return _success({**outcome.model_dump(mode="json"), "registry": overlays[outcome.device.id].model_dump(mode="json"),
        "technical_source": "endpoint", "business_source": "registry"})


@require_auth("admin", "support")
async def handle_admin_endpoint_context_refresh(request):
    try:
        device = _device(request)
        refresh = ContextRefreshRequest.model_validate(await request.json())
    except (ValueError, KeyError, ValidationError, TypeError):
        return _error(400, "invalid_refresh_request")
    endpoint = DomainPortContainer.from_config().endpoint
    request_id = uuid4().hex
    results = []
    for profile in refresh.profiles:
        outcome = await endpoint.request_context_collection(device, profile,
            idempotency_key=f"hd-context-{request_id}-{profile}")
        if isinstance(outcome, EndpointContextCollection):
            results.append({"profile": profile, "collection": outcome.model_dump(mode="json"), "error_code": None})
        else:
            results.append({"profile": profile, "collection": None, "error_code": outcome.code})
    succeeded = sum(row["collection"] is not None for row in results)
    return _success({"request_id": request_id, "status": "requested" if succeeded == len(results) else "partial" if succeeded else "failed",
        "results": results}, status=202 if succeeded else 200)


@require_auth("admin", "support", "auditor")
async def handle_admin_endpoint_collection(request):
    try:
        collection = UUID(request.match_info["collection_id"])
    except (ValueError, KeyError):
        return _error(400, "invalid_collection_id")
    outcome = await DomainPortContainer.from_config().endpoint.read_context_collection(collection)
    return _success(outcome.model_dump(mode="json")) if isinstance(outcome, EndpointCollectionDetails) else _failure(outcome)


@require_auth("admin", "support", "auditor")
async def handle_admin_endpoint_history(request):
    try:
        device = _device(request)
        if set(request.query) - {"profile", "limit"}:
            raise ValueError()
        profile = request.query.get("profile", "inventory_v1")
        limit = int(request.query.get("limit", "20"))
        if profile not in {"baseline_v1", "inventory_v1"} or not 1 <= limit <= 100:
            raise ValueError()
    except (ValueError, KeyError):
        return _error(400, "invalid_history_request")
    outcome = await DomainPortContainer.from_config().endpoint.list_context_history(device, profile, limit=limit)
    return _success(outcome.model_dump(mode="json")) if isinstance(outcome, EndpointContextHistory) else _failure(outcome)


@require_auth("admin", "support", "auditor")
async def handle_admin_endpoint_compare(request):
    try:
        device = _device(request)
        if set(request.query) != {"before", "after"}:
            raise ValueError()
        before, after = UUID(request.query["before"]), UUID(request.query["after"])
        if before == after:
            raise ValueError()
    except (ValueError, KeyError):
        return _error(400, "invalid_comparison_request")
    outcome = await DomainPortContainer.from_config().endpoint.compare_context_snapshots(device, before, after)
    return _success(outcome.model_dump(mode="json")) if isinstance(outcome, EndpointContextComparison) else _failure(outcome)
