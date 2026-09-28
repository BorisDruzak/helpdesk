from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from endpoint_adapter.http import ExternalEndpointHttpAdapter

pytestmark = [pytest.mark.no_db, pytest.mark.asyncio]


@pytest.mark.parametrize("extra", [False, True])
async def test_binding_adapter_uses_existing_transport_and_bounded_plain_contract(extra):
    device_id = str(uuid4())
    async def redeem(request):
        assert request.path == "/api/v1/device-binding/challenges/redeem"
        assert not request.query
        assert await request.json() == {"purpose": "helpdesk_device_binding", "code": "123456"}
        result = {"status": "verified", "device_id": device_id, "hostname": "Fixture PC", "platform": "windows"}
        if extra:
            result["credential"] = "must-never-be-projected"
        return web.json_response(result)
    app = web.Application()
    app.router.add_post("/api/v1/device-binding/challenges/redeem", redeem)
    async with TestServer(app) as server:
        adapter = ExternalEndpointHttpAdapter(base_url=str(server.make_url("")),
            service_token="test-only", ca_file="", timeout_seconds=1, allow_insecure_test_url=True)
        result = await adapter.redeem_device_binding("123456")
    assert result.status == ("invalid_projection" if extra else "verified")
    if not extra:
        assert result.device.external_id == device_id


async def test_binding_adapter_rejects_non_ascii_code_without_http():
    adapter = ExternalEndpointHttpAdapter(base_url="https://example.invalid", service_token="", ca_file="", timeout_seconds=1)
    result = await adapter.redeem_device_binding("１２３４５６")
    assert result.status == "invalid_projection"
