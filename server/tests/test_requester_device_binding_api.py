from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket
from domain_ports.endpoint import EndpointBindingVerified, EndpointDeviceRef, EndpointUnavailable
from registry_adapter.local import LocalRegistryAdapter
from tests.test_requester_workspace_api import _person_for_login, _headers
from tests.conftest import TEST_UI_USER_PREFIX
import web_api.requester_handlers as handlers

pytestmark = [pytest.mark.asyncio, pytest.mark.db_cleanup("web_support")]


async def test_requester_bind_devices_conflict_and_no_device_ticket(test_client_light, test_engine, monkeypatch):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    logins = [f"binding-{uuid4().hex}@example.test" for _ in range(2)]
    device_ref = str(uuid4())
    async with maker() as session:
        for login in logins:
            await _person_for_login(session, login=login)
        await session.commit()
    endpoint = SimpleNamespace(redeem_device_binding=AsyncMock(return_value=EndpointBindingVerified(
        device=EndpointDeviceRef(external_id=device_ref), hostname="API fixture PC", platform="windows")),
        read_device=AsyncMock(return_value=EndpointUnavailable()))
    monkeypatch.setattr(handlers.DomainPortContainer, "from_config", lambda **kw:
        SimpleNamespace(endpoint=endpoint, registry=LocalRegistryAdapter(kw.get("registry_session"))))
    for login, expected in [(logins[0], "active"), (logins[0], "active"), (logins[1], "pending_admin_review")]:
        response = await test_client_light.post("/api/web/requester/devices/link", headers=_headers(TEST_UI_USER_PREFIX + login),
            json={"code": "123-456"})
        payload = await response.json()
        assert response.status == 200, payload
        assert response.headers["Cache-Control"] == "no-store"
        assert payload["data"]["binding_status"] == expected
        assert "123456" not in str(payload) and "123-456" not in str(payload)
        if expected == "active":
            assert any(row["device_id"] == device_ref for row in payload["data"]["devices"])
    # Default forms and explicit no-device intent must remain available even
    # after the account acquires a primary computer.
    ticket_request = {"title": "Mail fixture", "description": "Mail is unavailable", "form_key": "mail_issue",
        "form_payload": {"impact_scope": "single_user", "work_continuity": "workaround_available"},
        "device_scope": "none"}
    response = await test_client_light.post("/api/web/requester/tickets", headers=_headers(TEST_UI_USER_PREFIX + logins[0]),
        json=ticket_request)
    payload = await response.json()
    assert response.status == 200, payload
    async with maker() as session:
        ticket = await session.get(Ticket, payload["data"]["ticket_id"])
        assert ticket.device_id is None and ticket.endpoint_device_ref is None
        assert ticket.requester_person_id is not None
        context = ticket.custom_fields["ticket_context"]
        assert context["diagnostic_target"]["device_id"] is None
