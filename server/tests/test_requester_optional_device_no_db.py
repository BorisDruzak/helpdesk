from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from web_api.requester_handlers import _resolve_requester_self_device_context, _attach_registry_endpoint_mapping
from domain_ports.endpoint import EndpointDeviceProjection, EndpointDeviceRef, EndpointUnavailable
from domain_ports.registry_contracts import DeviceContextProjection, DeviceRef

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


async def test_explicit_no_device_does_not_select_primary_or_require_device_ownership():
    person = SimpleNamespace(person_id="requester")
    resolver = SimpleNamespace(resolve_person_for_web_user=AsyncMock(return_value=person),
        resolve_primary_device=AsyncMock(), require_owned_device=AsyncMock())
    result = await _resolve_requester_self_device_context(resolver, actor_id="requester",
        supplied_device_id="", state=None, without_device=True)
    assert result[:5] == (person, None, None, "browser_no_device", "no_device")
    resolver.resolve_primary_device.assert_not_awaited()
    resolver.require_owned_device.assert_not_awaited()


@pytest.mark.parametrize("mapping,available", [(False, True), (True, False), (True, True)])
async def test_ticket_endpoint_target_needs_exact_registry_mapping_and_provider(mapping, available):
    reference = "550e8400-e29b-41d4-a716-446655440001"
    ticket = SimpleNamespace(device_id=reference, endpoint_device_ref=None, endpoint_device_snapshot_json=None)
    context = DeviceContextProjection(device=DeviceRef(external_id=reference), display_name="PC",
        asset_type="computer", asset_status="active", source="local_authoritative",
        endpoint_device_ref=reference if mapping else None)
    projection = EndpointDeviceProjection(device=EndpointDeviceRef(external_id=reference),
        display_name="PC", retired=False, last_seen_at=None) if available else EndpointUnavailable()
    ports = SimpleNamespace(registry=SimpleNamespace(device_context=AsyncMock(return_value=context)),
        endpoint=SimpleNamespace(read_device=AsyncMock(return_value=projection)))
    await _attach_registry_endpoint_mapping(ticket, ports)
    if mapping and available:
        assert ticket.endpoint_device_ref == reference
        assert ticket.endpoint_device_snapshot_json["source"] == "endpoint_platform"
    else:
        assert ticket.endpoint_device_ref is None
    if not mapping:
        ports.endpoint.read_device.assert_not_awaited()


async def test_explicit_no_device_and_device_id_are_rejected_together():
    resolver = SimpleNamespace(resolve_person_for_web_user=AsyncMock(), require_owned_device=AsyncMock())
    with pytest.raises(PermissionError):
        await _resolve_requester_self_device_context(resolver, actor_id="requester",
            supplied_device_id="device", state=None, without_device=True)
    resolver.require_owned_device.assert_not_awaited()
