import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from routes import setup_routes


@pytest.fixture
async def web_admin_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin1",
            actor_role="admin",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_bootstrap_exposes_tech_and_observer_features(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/bootstrap")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["workspace"] == "admin"
    assert "tech_panel" in payload["data"]["features"]
    assert payload["data"]["observer"]["quick_endpoint"] == "/api/admin/tech/observer/quick"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_devices_returns_typed_fallback_payload_when_db_is_unavailable(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/devices")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["query"] == ""
    assert payload["data"]["status_filter"] == "all"
    assert payload["data"]["summary"]["visible_count"] == 0
    assert payload["data"]["summary"]["online_count"] == 0
    assert payload["data"]["summary"]["rollout_targets"] == 0
    assert payload["data"]["rollout"] == []
    assert payload["data"]["devices"] == []
    assert payload["data"]["filters"]["status_options"][0] == {
        "value": "all",
        "label": "Все устройства",
    }
