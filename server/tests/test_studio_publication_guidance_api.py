"""Canonical publication, priority/SLA simulation and ticket creation for v4 inheritance."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, RoutingPolicy, SlaPolicy, Ticket, TicketQueue, TicketSlaPolicy
from app.db.request_scenario_models import RequestStudioDraft
from tests.test_request_scenario_admin_api import ADMIN, BASE
from tests.test_request_scenario_publication_api import ready
from tests.test_request_scenario_submit_api import OWNER, submit_step
from tests.test_request_scenario_v3_processing_api import publish

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


async def weighted(engine, *, refs=False):
    identifier, raw = await ready(engine)
    code = raw["scenario_key"]
    raw.update(schema_version=4, execution_semantics=3, processing={"routes": {}, "sla_profiles": {},
        "defaults": {"route": "", "sla_profile": ""}})
    raw["blocks"].append({"id": "weights", "kind": "sla_attachment", "title": "Влияние и срочность",
        "attached_to": "questions", "processing_facts": {"impact": "department", "urgency": "blocked"}})
    async with async_sessionmaker(engine)() as session:
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == code))
        config = dict(template.config_json)
        config["priority_policy"] = {"impact_field": "affected_scope", "urgency_field": "work_continuity",
            "matrix": {"department": {"work_stopped_no_workaround": "P1"}, "team": {"work_stopped_no_workaround": "P2"}}}
        template.config_json = config
        sla_id = template.sla_policy_id
        if refs:
            queue = TicketQueue(code=code + "-selected", name="Fallback policy queue", is_active=True)
            session.add(queue)
            await session.flush()
            session.add_all([
                RoutingPolicy(code=code + "_selected", version="1", title="Fallback route", config_json={"fallback": {"queue_id": queue.id}},
                    is_active=True, published_at=datetime.now(timezone.utc)),
                SlaPolicy(code=code + "_selected", version="1", title="Fallback SLA", config_json={"targets": {
                    "first_response": {"P1": 11, "P2": 22}, "resolution": {"P1": 111, "P2": 222}}},
                    is_active=True, published_at=datetime.now(timezone.utc)),
            ])
            raw["process_binding"]["policy_refs"] = {"routing": code + "_selected", "sla": code + "_selected"}
            queue_id = queue.id
        else:
            queue_id = await session.scalar(select(TicketQueue.id).where(TicketQueue.code == code + "-mapped"))
        # Seed a native v4 draft; upgrade behavior has its own isolated suite.
        (await session.get(RequestStudioDraft, identifier)).definition = raw
        await session.commit()
    return identifier, raw, queue_id, sla_id


@pytest.mark.asyncio
@pytest.mark.parametrize("refs", [False, True])
async def test_weights_inherit_service_sla_and_route_with_actual_priority_creation_parity(test_client_light, test_engine, refs):
    identifier, raw, queue_id, sla_id = await weighted(test_engine, refs=refs)
    url, preview = await publish(test_client_light, identifier, raw)
    tickets = [item for item in preview["outcomes"] if item["kind"] == "ticket"]
    assert tickets and all(item["map_processing"]["sla_profile"] is None and item["map_processing"]["route"] is None for item in tickets)
    assert all(item["priority"]["priority_class"] == "P1" for item in tickets)
    assert all(item["sla"]["resolution_min"] == (111 if refs else 120) for item in tickets)
    _, requester = await submit_step(test_client_light, raw, mapped=True)
    response = await test_client_light.post(requester + "/ticket-preview", headers=OWNER, json={"revision": 3})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["ok"]
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, (await response.json())["data"]["linked_ticket_id"])
        assert ticket.queue_id == queue_id
        assert ticket.custom_fields["priority_class"] == "P1"
        assert ticket.first_response_due_at and ticket.resolution_due_at
        context = ticket.custom_fields["request_template"]
        assert context["scenario_processing"]["sla_profile"] is None
        if refs:
            assert context["policy_refs"]["sla"]["code"] == raw["process_binding"]["policy_refs"]["sla"]
            assert context["sla_policy"]["targets"]["resolution"]["P1"] == 111
        else:
            assert ticket.sla_policy_id == sla_id


@pytest.mark.asyncio
async def test_missing_inherited_sla_blocks_publication_and_published_terminal(test_client_light, test_engine):
    identifier, raw, _, sla_id = await weighted(test_engine)
    url, _ = await publish(test_client_light, identifier, raw)
    async with async_sessionmaker(test_engine)() as session:
        (await session.get(TicketSlaPolicy, sla_id)).is_active = False
        await session.commit()
        count = await session.scalar(select(func.count()).select_from(Ticket))
    response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert response.status == 200, await response.text()
    assessment = (await response.json())["data"]
    assert not assessment["readiness"]["can_publish"] and not assessment["confirmation_token"]
    assert any(issue["code"] == "sla_unavailable" and issue["path"] == "blocks.submit" for issue in assessment["readiness"]["issues"])
    _, requester = await submit_step(test_client_light, raw, mapped=True)
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 409, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == count


@pytest.mark.asyncio
async def test_unknown_inherited_registry_sla_blocks_only_effective_path(test_client_light, test_engine):
    identifier, raw, _, _ = await weighted(test_engine)
    raw["process_binding"]["policy_refs"] = {"sla": "missing-policy"}
    url = BASE + "/scenarios/" + identifier
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": raw})
    assert response.status == 200, await response.text()
    response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert response.status == 200, await response.text()
    assessment = (await response.json())["data"]
    assert not assessment["readiness"]["can_publish"] and not assessment["confirmation_token"]
    assert any(issue["code"] == "sla_unavailable" and issue["path"] == "blocks.submit" for issue in assessment["readiness"]["issues"])


@pytest.mark.asyncio
async def test_sla_removed_between_preview_and_actual_create_rolls_back(test_client_light, test_engine, monkeypatch):
    from web_api import requester_handlers
    identifier, raw, _, sla_id = await weighted(test_engine)
    await publish(test_client_light, identifier, raw)
    _, requester = await submit_step(test_client_light, raw, mapped=True)
    async with async_sessionmaker(test_engine)() as session:
        count = await session.scalar(select(func.count()).select_from(Ticket))
    create = requester_handlers.create_requester_ticket_in_session
    async def deactivate_then_create(request, data, session, **kwargs):
        async with async_sessionmaker(test_engine)() as publisher:
            (await publisher.get(TicketSlaPolicy, sla_id)).is_active = False
            await publisher.commit()
        return await create(request, data, session, **kwargs)
    monkeypatch.setattr(requester_handlers, "create_requester_ticket_in_session", deactivate_then_create)
    response = await test_client_light.post(requester + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 503, await response.text()
    assert (await response.json())["error_code"] == "TICKET_INITIALIZATION_UNAVAILABLE"
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == count
