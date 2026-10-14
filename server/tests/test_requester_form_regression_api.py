"""No-agent authoring and requester ownership on a real isolated database."""
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
import uuid
from datetime import datetime, timezone
from app.db.models import HelpdeskService, HelpdeskServiceOffering, RequestTemplate, Ticket, TicketQueue

from tests.test_request_scenario_admin_api import ADMIN, AUDITOR
from tests.test_request_scenario_session_api import BASE, OWNER, OTHER
from tests.test_request_scenario_submit_api import setup
from tests.test_requester_workspace_api import _person_for_login

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_admin_own_requester_form_without_agent_keeps_foreign_sessions_and_tickets_private(test_client_light, test_engine):
    definition = await setup(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        await _person_for_login(session, login="admin-test")
        await session.commit()
    client = test_client_light
    bootstrap = await client.get("/api/web/requester/bootstrap", headers=ADMIN)
    assert bootstrap.status == 200, await bootstrap.text()
    data = (await bootstrap.json())["data"]
    assert data["devices"] == [] and data["profile_completion"]["complete"]
    assert data["feature_flags"]["requester_no_device_create"]
    assert (await client.get("/api/web/requester/bootstrap", headers=AUDITOR)).status == 403

    foreign = await client.post(BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert foreign.status == 200
    foreign_id = (await foreign.json())["data"]["id"]
    assert (await client.get(BASE + "/" + foreign_id, headers=ADMIN)).status == 404

    started = await client.post(BASE, headers=ADMIN, json={"offering_full_code": definition["offering_full_code"]})
    assert started.status == 200, await started.text()
    own_id = (await started.json())["data"]["id"]
    assert own_id != foreign_id
    url = BASE + "/" + own_id
    assert (await client.get(url, headers=OTHER)).status == 404
    answered = await client.post(url + "/answer", headers=ADMIN,
        json={"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No-agent form check"}})
    assert answered.status == 200, await answered.text()
    assert (await client.post(url + "/advance", headers=ADMIN, json={"expected_block_id": "review", "revision": 2})).status == 200
    preview = await client.post(url + "/ticket-preview", headers=ADMIN, json={"revision": 3, "device_scope": "none"})
    assert preview.status == 200, await preview.text()
    assert (await preview.json())["data"]["ok"]
    submitted = await client.post(url + "/submit", headers=ADMIN, json={"revision": 3, "confirm": True, "device_scope": "none"})
    assert submitted.status == 200, await submitted.text()
    ticket_id = (await submitted.json())["data"]["linked_ticket_id"]
    detail = await client.get("/api/web/requester/tickets/" + ticket_id, headers=ADMIN)
    assert detail.status == 200, await detail.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.device_id is None and ticket.requester_id == "admin-test"
    assert (await client.get("/api/web/requester/tickets/" + ticket_id, headers=OTHER)).status == 404


@pytest.mark.asyncio
async def test_user_help_form_has_only_map_fields_and_can_be_previewed_without_profile_or_agent(test_client_light, test_engine):
    async with async_sessionmaker(test_engine)() as session:
        service = HelpdeskService(service_id=str(uuid.uuid4()), code="requester_setup", name="Setup", public_title="Setup",
                                 lifecycle_status="published", visibility="public")
        session.add(service)
        await session.flush()
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=service.service_id,
            code="agent_binding_help", full_code="requester_setup.agent_binding_help", name="Help", public_title="Help",
            request_template_key="agent_binding_help", lifecycle_status="published", visibility="public"))
        queue = TicketQueue(code="servicedesk_l1", name="Triage", is_triage=True, is_active=True)
        session.add(queue)
        await session.flush()
        session.add(RequestTemplate(template_code="agent_binding_help", version="1", public_title="Help", ticket_type="service_request",
            is_active=True, published_at=datetime.now(timezone.utc), config_json={"priority_policy": {}, "no_sla": True,
                "routing_policy": {"fallback": {"queue_id": queue.id}}}))
        await session.commit()
    client = test_client_light
    response = await client.get("/public_api/ticket_forms/current?pack_key=request_forms")
    assert response.status == 200
    pack = (await response.json())["pack"]
    form = next(item for item in pack["forms"] if item["key"] == "agent_binding_help")
    assert [field["key"] for field in form["fields"]] == ["contact_phone", "agent_problem"]
    preview = await client.post("/api/web/requester/tickets/preview", headers=OTHER, json={
        "form_pack_key": pack["pack_key"], "form_pack_version": pack["version"], "form_key": form["key"],
        "request_template_key": form["key"], "device_scope": "none", "form_payload": {
            "contact_phone": "1234567890", "agent_problem": "Cannot get a binding code"}})
    assert preview.status == 200, await preview.text()
    assert (await preview.json())["data"]["ok"]
