import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from routes import setup_routes
from web_api.session_handlers import _build_session_payload


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


@pytest.fixture
async def web_support_client():
    @web.middleware
    async def auth_context_middleware(request, handler):
        request["auth_context"] = AuthContext(
            actor_id="support1",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.no_db
def test_permission_catalog_has_stable_role_defaults():
    from access_control.catalog import get_permission_catalog, get_role_permission_codes

    catalog = get_permission_catalog()
    codes = {item.code for item in catalog}

    assert "workspace.admin.view" in codes
    assert "workspace.support.view" in codes
    assert "ticket.queue.change" in codes
    assert "ticket.playbook.run" in codes
    assert "admin.access.view" in codes

    admin_permissions = get_role_permission_codes("admin")
    support_permissions = get_role_permission_codes("support")
    auditor_permissions = get_role_permission_codes("auditor")

    assert "admin.access.view" in admin_permissions
    assert "workspace.support.view" in support_permissions
    assert "workspace.admin.view" not in support_permissions
    assert "ticket.status.change" not in auditor_permissions
    assert "observer.trace.view" in auditor_permissions


@pytest.mark.no_db
def test_session_payload_exposes_effective_permissions_and_version():
    payload = _build_session_payload(user_login="support1", actor_role="support", auth_type="ui_token")
    dumped = payload.model_dump()

    assert dumped["default_workspace"] == "support"
    assert dumped["available_workspaces"] == ["support"]
    assert "workspace.support.view" in dumped["permissions"]
    assert "ticket.tool.run" in dumped["permissions"]
    assert "workspace.admin.view" not in dumped["permissions"]
    assert dumped["permissions_version"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_access_catalog_returns_operator_grouped_permissions(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/access/catalog")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["version"]
    assert data["roles"][0]["code"] == "admin"
    assert any(group["code"] == "tickets" for group in data["groups"])
    ticket_group = next(group for group in data["groups"] if group["code"] == "tickets")
    assert any(item["code"] == "ticket.queue.change" for item in ticket_group["permissions"])
    admin_role = next(role for role in data["roles"] if role["code"] == "admin")
    support_role = next(role for role in data["roles"] if role["code"] == "support")
    assert "admin.access.view" in admin_role["permissions"]
    assert "admin.access.view" not in support_role["permissions"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_web_admin_access_effective_can_preview_builtin_role(web_admin_client):
    response = await web_admin_client.get("/api/web/admin/access/effective?actor_id=support1&actor_role=support")

    assert response.status == 200
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["actor_id"] == "support1"
    assert data["actor_role"] == "support"
    assert data["workspaces"] == ["support"]
    assert "ticket.comment.internal" in data["permissions"]
    assert "settings.manage_queues" not in data["permissions"]
    assert data["sources"]["role"] == "support"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_support_cannot_open_admin_access_catalog(web_support_client):
    response = await web_support_client.get("/api/web/admin/access/catalog")

    assert response.status == 403
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error_code"] == "FORBIDDEN"
