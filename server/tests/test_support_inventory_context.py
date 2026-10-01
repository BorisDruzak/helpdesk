from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID
import pytest
from domain_ports.endpoint import EndpointUnavailable, EndpointNotFound
from domain_ports.endpoint_context import EndpointDeviceContext
from registry.endpoint_device_overlay import RegistryDeviceOverlay
from web_api import support_handlers

pytestmark = pytest.mark.no_db
DEVICE = "00000000-0000-0000-0000-000000000001"

@pytest.mark.asyncio
async def test_unmapped_ticket_never_reads_endpoint_or_legacy_telemetry():
    port = SimpleNamespace(read_device_context=AsyncMock())
    result = await support_handlers._build_support_inventory_context(None, SimpleNamespace(endpoint_device_ref=None, device_id=DEVICE), None, endpoint_port=port)
    assert result.status == "unmapped"
    assert result.context is None
    port.read_device_context.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [EndpointUnavailable(), EndpointNotFound(), RuntimeError("provider failed")])
async def test_provider_failure_is_unknown_without_local_fallback(outcome):
    method = AsyncMock(side_effect=outcome) if isinstance(outcome, Exception) else AsyncMock(return_value=outcome)
    result = await support_handlers._build_support_inventory_context(None, SimpleNamespace(endpoint_device_ref=DEVICE, device_id="local-other"), None, endpoint_port=SimpleNamespace(read_device_context=method))
    assert result.status == "unavailable"
    assert result.context is None and result.registry is None
    assert method.await_args.args[0].external_id == DEVICE

@pytest.mark.asyncio
async def test_safe_context_uses_exact_endpoint_id_and_canonical_registry(monkeypatch):
    context = EndpointDeviceContext.model_validate({"device": {"id": DEVICE, "device_identifier": "pc", "display_name": "PC", "retired_at": None, "last_seen_at": None, "online": True}, "profiles": [], "snapshots": []})
    overlay = AsyncMock(return_value={UUID(DEVICE): RegistryDeviceOverlay(status="unmapped")})
    monkeypatch.setattr("registry.endpoint_device_overlay.read_registry_device_overlays", overlay)
    result = await support_handlers._build_support_inventory_context(None, SimpleNamespace(endpoint_device_ref=DEVICE, device_id="local-other"), None, endpoint_port=SimpleNamespace(read_device_context=AsyncMock(return_value=context)))
    assert result.status == "available"
    assert result.context == context and result.registry.status == "unmapped"
    overlay.assert_awaited_once_with(None, (UUID(DEVICE),))
