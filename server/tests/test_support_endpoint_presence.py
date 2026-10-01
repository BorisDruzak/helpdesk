from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from domain_ports.endpoint import EndpointDeviceRef, EndpointUnavailable
from web_api import support_handlers

pytestmark = pytest.mark.no_db

@pytest.mark.asyncio
@pytest.mark.parametrize('online', [True, False])
async def test_endpoint_presence_overrides_legacy_helpdesk_device_state(online):
    from domain_ports.endpoint import EndpointDevicePresenceProjection
    ref = EndpointDeviceRef(external_id='endpoint-1')
    seen = datetime.now(timezone.utc)
    port = SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointDevicePresenceProjection(
        device=ref, display_name='ADMIN-2', online=online, retired=False, last_seen_at=seen)))
    ticket = SimpleNamespace(device_id='registry-1', endpoint_device_ref=ref.external_id)
    legacy = SimpleNamespace(hostname='old-host', os='Windows', agent_version='old-version', last_seen_at=None)
    snapshot = await support_handlers._build_support_device_snapshot(ticket, legacy, endpoint_port=port)
    assert snapshot.hostname == 'ADMIN-2'
    assert snapshot.online is online
    assert snapshot.connection_state == ('online' if online else 'offline')
    assert snapshot.last_seen_at == seen.isoformat()
    assert snapshot.agent_version is None  # The published presence contract has no version.
    port.read_device_presence.assert_awaited_once_with(ref)

@pytest.mark.asyncio
async def test_unavailable_endpoint_is_unknown_without_stale_legacy_fallback():
    port = SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointUnavailable()))
    ticket = SimpleNamespace(device_id='registry-1', endpoint_device_ref='endpoint-1')
    legacy = SimpleNamespace(hostname='ADMIN-2', os='Windows', agent_version='old', last_seen_at=datetime.now(timezone.utc))
    snapshot = await support_handlers._build_support_device_snapshot(ticket, legacy, endpoint_port=port)
    assert snapshot.connection_state == 'unknown'
    assert snapshot.last_seen_at is None
    assert snapshot.agent_version is None

@pytest.mark.asyncio
async def test_presence_for_another_device_cannot_replace_ticket_context():
    from domain_ports.endpoint import EndpointDevicePresenceProjection
    port = SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointDevicePresenceProjection(
        device=EndpointDeviceRef(external_id='another-device'), display_name='wrong-host', online=True, retired=False, last_seen_at=None)))
    snapshot = await support_handlers._build_support_device_snapshot(SimpleNamespace(device_id='registry-1', endpoint_device_ref='endpoint-1'), None, endpoint_port=port)
    assert snapshot.connection_state == 'unknown'
    assert snapshot.hostname is None

@pytest.mark.asyncio
async def test_endpoint_error_is_unknown_and_does_not_break_ticket_read():
    port = SimpleNamespace(read_device_presence=AsyncMock(side_effect=TimeoutError()))
    snapshot = await support_handlers._build_support_device_snapshot(SimpleNamespace(device_id='registry-1', endpoint_device_ref='endpoint-1'), None, endpoint_port=port)
    assert snapshot.connection_state == 'unknown'

@pytest.mark.asyncio
async def test_retired_endpoint_is_not_online():
    from domain_ports.endpoint import EndpointDevicePresenceProjection
    port = SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointDevicePresenceProjection(
        device=EndpointDeviceRef(external_id='endpoint-1'), display_name='ADMIN-2', online=True, retired=True, last_seen_at=None)))
    snapshot = await support_handlers._build_support_device_snapshot(SimpleNamespace(device_id='registry-1', endpoint_device_ref='endpoint-1'), None, endpoint_port=port)
    assert snapshot.connection_state == 'offline'
    assert not snapshot.online

@pytest.mark.asyncio
async def test_ticket_without_endpoint_reference_is_unknown_without_legacy_fallback():
    port = SimpleNamespace(read_device_presence=AsyncMock())
    legacy = SimpleNamespace(hostname='legacy-host', os='Windows', agent_version='3.0', last_seen_at=None)
    snapshot = await support_handlers._build_support_device_snapshot(SimpleNamespace(device_id='legacy-1', endpoint_device_ref=None), legacy, endpoint_port=port, legacy_online=True)
    assert not snapshot.online
    assert snapshot.connection_state == "unknown"
    assert snapshot.agent_version is None
    port.read_device_presence.assert_not_awaited()
