import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from routes import setup_routes
from web_api import admin_handlers
from web_api.dto.admin import (
    AdminBuildIdentity,
    AdminDeviceUpdateAction,
    AdminDeviceUpdateRecommendation,
    AdminDeviceUpdateRunPayload,
    AdminDeviceUpdateSummary,
    AdminDeviceUpdatesPayload,
    AdminRolloutAssignment,
)


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


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_updates_returns_typed_payload(web_admin_client, monkeypatch):
    async def fake_build_payload(*, device_id: str, state):
        assert device_id == "device-1"
        assert state is None
        return AdminDeviceUpdatesPayload(
            device_id=device_id,
            device_label="WS-01",
            online=True,
            target="windows_amd64",
            current_version="3.1.18",
            release_channel="stable",
            is_release=True,
            summary=AdminDeviceUpdateSummary(
                status="update_available",
                label="Доступно обновление",
                summary="Серверный rollout рекомендует stable/3.1.19.",
            ),
            recommendation=AdminDeviceUpdateRecommendation(
                update_available=True,
                recommendation_source="assigned_rollout",
                recommendation_source_label="Серверный rollout",
                comparison="newer_release_available",
                comparison_label="Назначена более новая release-версия",
                recommended_reason="assigned_rollout_newer",
                recommended_reason_label="Назначенный rollout новее текущей версии.",
                recommended_build=AdminBuildIdentity(
                    target="windows_amd64",
                    channel="stable",
                    version="3.1.19",
                ),
                assigned_rollout=AdminRolloutAssignment(
                    target="windows_amd64",
                    channel="stable",
                    version="3.1.19",
                    updated_at="2026-04-20T12:00:00+05:00",
                    updated_by="admin",
                ),
            ),
            action=AdminDeviceUpdateAction(
                enabled=True,
                label="Запустить обновление",
                reason_required=True,
                endpoint="/api/web/admin/devices/device-1/updates/run",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_build_admin_device_updates_payload", fake_build_payload)

    response = await web_admin_client.get("/api/web/admin/devices/device-1/updates")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["device_id"] == "device-1"
    assert payload["data"]["recommendation"]["recommended_build"]["version"] == "3.1.19"
    assert payload["data"]["action"]["label"] == "Запустить обновление"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_update_run_requires_reason(web_admin_client):
    response = await web_admin_client.post("/api/web/admin/devices/device-1/updates/run", json={})

    assert response.status == 400
    payload = await response.json()

    assert payload["status"] == "error"
    assert payload["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_device_update_run_returns_queued_action_payload(web_admin_client, monkeypatch):
    async def fake_run_update(*, state, auth_context, device_id: str, reason: str, restart_delay_sec: int | None):
        assert state is None
        assert auth_context.actor_role == "admin"
        assert device_id == "device-1"
        assert reason == "canary после smoke"
        assert restart_delay_sec == 5
        return AdminDeviceUpdateRunPayload(
            device_id=device_id,
            operation_id="op-admin-1",
            status="queued",
            message="Операция op-admin-1 поставлена в очередь.",
            build_source="assigned_rollout",
            poll_url="/api/operations/op-admin-1",
            build=AdminBuildIdentity(
                target="windows_amd64",
                channel="stable",
                version="3.1.19",
            ),
        )

    monkeypatch.setattr(admin_handlers, "_run_admin_device_update", fake_run_update)

    response = await web_admin_client.post(
        "/api/web/admin/devices/device-1/updates/run",
        json={"reason": "canary после smoke", "restart_delay_sec": 5},
    )

    assert response.status == 202
    payload = await response.json()

    assert payload["status"] == "success"
    assert payload["data"]["operation_id"] == "op-admin-1"
    assert payload["data"]["build"]["version"] == "3.1.19"
