from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from auth.rate_limit import reset_rate_limits
from auth.middleware import auth_middleware
from registry import inventory_directory
from web_api.inventory_handlers import search_registration_inventory
import web_api.session_handlers as handlers
from web_api.dto.session import WebRequesterRegisterRequest
from pydantic import ValidationError

pytestmark = pytest.mark.no_db


def valid_payload():
    return {"request_id": str(uuid.uuid4()), "first_name": "Иван", "last_name": "Петров", "department_id": "real", "phone": "1234", "password": "Long-fixture-password-43!", "password_repeat": "Long-fixture-password-43!"}


@pytest.mark.asyncio
async def test_registration_inventory_search_with_real_auth_middleware(monkeypatch):
    monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(handlers.config_module, "WEB_CSRF_SAME_ORIGIN_ENABLED", True)
    monkeypatch.setenv("HELPDESK_INVENTORY_BASE_URL", "https://inventory.example.invalid")
    monkeypatch.setenv("HELPDESK_INVENTORY_REGISTRATION_SEARCH_ENABLED", "true")
    reset_rate_limits()
    employee = {"full_name": "Петров Иван", "department": "Юридический отдел", "has_agent": True}
    monkeypatch.setattr(inventory_directory, "search_registration_people", AsyncMock(
        return_value=inventory_directory.RegistrationPeople(people=[employee])))
    path = "/api/web/session/registration-inventory-search"
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_post(path, search_registration_inventory)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post(path, json={"query": "Петров Ив"})).status == 403
        same_origin = {"Origin": str(client.make_url("/").origin())}
        assert (await client.post(path, json={"query": "Петров"}, headers=same_origin)).status == 400
        response = await client.post(path, json={"query": "Петров Ив"}, headers=same_origin)
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert (await response.json())["data"] == {"people": [employee], "refine": False}


@pytest.mark.parametrize("field", ["actor_role", "person_id", "login", "location_id"])
def test_signup_dto_does_not_accept_privileges_existing_profiles_or_manual_login(field):
    with pytest.raises(ValidationError):
        WebRequesterRegisterRequest.model_validate({**valid_payload(), field: "admin"})


@pytest.mark.asyncio
async def test_signup_routes_remain_feature_flagged(monkeypatch):
    monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", False)
    app = web.Application()
    app.router.add_post("/api/web/session/register-requester", handlers.handle_web_requester_register)
    app.router.add_get("/api/web/session/registration-options", handlers.handle_web_registration_options)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/api/web/session/register-requester", json=valid_payload())).status == 403
        assert (await client.get("/api/web/session/registration-options")).status == 403


@pytest.mark.asyncio
async def test_public_signup_options_do_not_disclose_people_or_locations(monkeypatch):
    from app.repos.registry_repo import RegistryRepo
    from registry.profile_schema_service import RequesterProfileSchemaService, default_profile_schema
    monkeypatch.setattr(handlers.config_module, "WEB_SELF_REGISTRATION_ENABLED", True)
    @asynccontextmanager
    async def sessions():
        yield None
    monkeypatch.setattr(handlers, "get_session", sessions)
    monkeypatch.setattr(RegistryRepo, "list_departments", AsyncMock(return_value=[
        SimpleNamespace(department_id="real", name="Юридический отдел", status="active"),
        SimpleNamespace(department_id="test", name="Synthetic staging", status="archived"),
    ]))
    schema = default_profile_schema()
    hidden = {"key":"private_admin_field", "label":"Hidden administrator field", "type":"text", "custom":True,"visible":False,"editable":False}
    schema.update(updated_by="private-administrator",warnings=["internal-policy-warning"],custom_fields=[hidden])
    schema["fields"].append(hidden)
    monkeypatch.setattr(RequesterProfileSchemaService, "get_schema", AsyncMock(return_value=schema))
    app = web.Application()
    app.router.add_get("/api/web/session/registration-options", handlers.handle_web_registration_options)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/api/web/session/registration-options")
        assert response.status == 200
        data = (await response.json())["data"]
        assert set(data) == {"departments", "profile_schema"}
        assert data["departments"] == [{"value": "real", "label": "Юридический отдел"}]
        assert not {"location_id", "login_identity", "active_device_links"}.intersection(field["key"] for field in data["profile_schema"]["fields"])
        assert response.headers["Cache-Control"] == "no-store"
        public = data["profile_schema"]
        assert set(public) == {"schema_key","version","fields","custom_fields","required_fields"}
        assert public["custom_fields"] == []
        assert "private-administrator" not in str(public) and "internal-policy-warning" not in str(public)
