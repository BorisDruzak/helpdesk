"""Selected scenario policy reaches readiness, simulator and actual creation."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import RoutingPolicy, SlaPolicy, TicketQueue, Ticket, TicketNotification, Operation, TicketApproval
from tests.test_request_scenario_publication_api import ready, preview
from tests.test_request_scenario_admin_api import ADMIN, BASE
from tests.test_request_scenario_submit_api import submit_step, OWNER
from tests.test_request_scenario_session_api import BASE as SESSION_BASE

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_saved_policy_selection_has_real_creation_parity(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    code = definition["scenario_key"] + "_selected"
    async with async_sessionmaker(test_engine)() as session:
        queue = TicketQueue(code=code, name="Selected scenario queue", is_active=True)
        session.add(queue)
        await session.flush()
        queue_id = queue.id
        session.add(RoutingPolicy(code=code, version="1", title="Selected printing route", config_json={"fallback": {"queue_id": queue_id}}, is_active=True, published_at=datetime.now(timezone.utc)))
        session.add(SlaPolicy(code=code + "_sla", version="1", title="Selected printing SLA", config_json={"targets": {"first_response": {priority: 20 for priority in ("P1", "P2", "P3", "P4")}, "resolution": {priority: 240 for priority in ("P1", "P2", "P3", "P4")}}}, is_active=True, published_at=datetime.now(timezone.utc)))
        await session.commit()
    url = BASE + "/scenarios/" + identifier
    definition["process_binding"]["policy_refs"] = {"routing": "missing"}
    assert (await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": definition})).status == 400
    definition["process_binding"]["policy_refs"] = {"routing": code, "sla": code + "_sla"}
    definition["blocks"][0]["layout"] = "section"
    for field in definition["blocks"][0]["fields"]:
        field.update(group="printer", group_title="Printer details")
    saved = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": definition})
    assert saved.status == 200, await saved.text()
    models = [Ticket, TicketNotification, Operation, TicketApproval]
    async with async_sessionmaker(test_engine)() as session:
        before = [await session.scalar(select(func.count()).select_from(model)) for model in models]
    simulation = await test_client_light.post(url + "/simulate", headers=ADMIN, json={"revision": 2, "steps": [
        {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print", "scope": "team", "continuity": "work_stopped_no_workaround"}},
        {"expected_block_id": "review", "revision": 2},
    ]})
    assert simulation.status == 200, await simulation.text()
    processing = (await simulation.json())["data"]["processing"]
    assert processing["routing"]["queue_id"] == queue_id
    assert processing["sla"]["resolution_min"] == 240
    assert processing["validated_facts"]["affected_scope"] == "team"
    assert processing["priority"]["reason"]
    assert processing["notification"]["would_send"] is False
    assert "recipient_groups" in processing["notification"]
    async with async_sessionmaker(test_engine)() as session:
        assert [await session.scalar(select(func.count()).select_from(model)) for model in models] == before
    body = await preview(test_client_light, identifier, 2)
    published = await test_client_light.post(url + "/publish", headers=ADMIN, json=body)
    assert published.status == 200, await published.text()
    started = await test_client_light.post(SESSION_BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert started.status == 200, await started.text()
    projected = (await started.json())["data"]["block"]
    assert projected["layout"] == "section"
    assert all(field["group_title"] == "Printer details" for field in projected["fields"])
    _, requester_url = await submit_step(test_client_light, definition, mapped=True)
    result = await test_client_light.post(requester_url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert result.status == 200, await result.text()
    ticket_id = (await result.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.queue_id == queue_id
        assert ticket.custom_fields["priority_class"] == processing["priority"]["priority_class"]
        assert ticket.custom_fields["request_template"]["policy_refs"]["routing"]["code"] == code
        assert ticket.custom_fields["request_scenario"]["policy_refs"] == {"routing": code, "sla": code + "_sla"}
        assert ticket.sla_policy_id is None
        assert ticket.custom_fields["request_template"]["sla_policy"]["targets"]["resolution"]["P2"] == 240
        assert ticket.resolution_due_at is not None
