import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import TicketQueue, TicketQueueMember, UiUser
from auth.context import AuthContext, AuthType
from routes import setup_routes
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN
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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


@pytest.mark.asyncio
async def test_web_admin_access_group_crud_grants_effective_permissions(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add_all(
            [
                UiUser(user_login="support-l2", password_hash="secret", actor_role="support", is_active=True),
                TicketQueue(code="network", name="Network", is_triage=False, is_active=True),
            ]
        )
        await session.commit()
        queue = (await session.execute(TicketQueue.__table__.select().where(TicketQueue.code == "network"))).first()
        queue_id = int(queue.id)
        session.add(TicketQueueMember(queue_id=queue_id, actor_id="support-l2", role_in_queue=None))
        await session.commit()

    create_response = await test_client.post(
        "/api/web/admin/access/groups",
        headers=_admin_headers(),
        json={
            "code": "support_l2",
            "name": "Support L2",
            "description": "Second line operators",
            "is_active": True,
        },
    )
    assert create_response.status == 200
    created = (await create_response.json())["data"]
    assert created["code"] == "support_l2"
    group_id = created["group_id"]

    permissions_response = await test_client.put(
        f"/api/web/admin/access/groups/{group_id}/permissions",
        headers=_admin_headers(),
        json={"permissions": ["admin.forms.view", "settings.manage_queues"]},
    )
    assert permissions_response.status == 200
    assert set((await permissions_response.json())["data"]["permissions"]) == {
        "admin.forms.view",
        "settings.manage_queues",
    }

    members_response = await test_client.put(
        f"/api/web/admin/access/groups/{group_id}/members",
        headers=_admin_headers(),
        json={"actor_ids": ["support-l2"]},
    )
    assert members_response.status == 200
    assert (await members_response.json())["data"]["members"] == ["support-l2"]

    queues_response = await test_client.put(
        f"/api/web/admin/access/groups/{group_id}/queues",
        headers=_admin_headers(),
        json={"queues": [{"queue_id": queue_id, "role_in_queue": "lead"}]},
    )
    assert queues_response.status == 200
    queue_grants = (await queues_response.json())["data"]["queue_grants"]
    assert queue_grants == [
        {
            "queue_id": queue_id,
            "queue_code": "network",
            "queue_name": "Network",
            "role_in_queue": "lead",
        }
    ]

    effective_response = await test_client.get(
        "/api/web/admin/access/effective?actor_id=support-l2&actor_role=support",
        headers=_admin_headers(),
    )
    assert effective_response.status == 200
    effective = (await effective_response.json())["data"]
    assert "support_l2" in effective["groups"]
    assert "admin.forms.view" in effective["permissions"]
    assert "settings.manage_queues" in effective["permissions"]
    assert any(queue["queue_code"] == "network" and queue["role_in_queue"] == "lead" for queue in effective["queues"])
    assert effective["sources"]["groups"] == ["support_l2"]

    audit_response = await test_client.get("/api/web/admin/access/audit", headers=_admin_headers())
    assert audit_response.status == 200
    audit = (await audit_response.json())["data"]["items"]
    assert [item["action"] for item in audit[:4]] == [
        "group_queues_updated",
        "group_members_updated",
        "group_permissions_updated",
        "group_created",
    ]


@pytest.mark.asyncio
async def test_support_cannot_mutate_access_groups(test_client):
    response = await test_client.post(
        "/api/web/admin/access/groups",
        headers=_support_headers(),
        json={"code": "support_l2", "name": "Support L2"},
    )

    assert response.status == 403
    payload = await response.json()
    assert payload["error_code"] == "FORBIDDEN"
