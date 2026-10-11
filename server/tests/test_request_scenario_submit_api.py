"""Real isolated ticket creation, owner scope, retries and transaction rollback."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering, RequestTemplate, RequesterTicketCreateRequest, Ticket, TicketQueue, TicketSlaPolicy, TicketSlaTarget, TicketQueueOlaTarget, ApprovalPolicy, ClosurePolicy, RoutingPolicy, TicketEvent, TicketApproval, TicketNotification
from app.db.request_scenario_models import RequestStudioSession, RequestStudioScenario, RequestStudioScenarioVersion
from app.repos import TicketFormPacksRepo
from tests.test_request_scenario_session_api import BASE, OWNER, OTHER, seed

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


async def setup(engine, mapped=False):
    definition, version_id = await seed(engine)
    code = definition["scenario_key"]
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        queue = TicketQueue(code=code, name="Scenario test queue", is_active=True)
        session.add(queue)
        await session.flush()
        routing = {"fallback": {"queue_id": queue.id}}
        config = {"routing_policy": routing, "no_sla": True}
        sla_id = None
        if mapped:
            mapped_queue = TicketQueue(code=code + "-mapped", name="Mapped policy queue", is_active=True)
            sla = TicketSlaPolicy(name=code, timezone="UTC", is_active=True)
            session.add_all([mapped_queue, sla])
            await session.flush()
            sla_id = sla.id
            session.add_all([TicketSlaTarget(policy_id=sla.id, priority=priority, first_response_min=30, resolution_min=120) for priority in ("P1", "P2", "P3", "P4")])
            session.add(TicketQueueOlaTarget(queue_id=mapped_queue.id, priority="P2", ack_min=15, processing_min=60))
            session.add(ApprovalPolicy(code=code + "_approval", version="1", title="Test approval", scope_level="request_template", scope_ref=code,
                config_json={"required": True}, is_active=True, published_at=datetime.now(timezone.utc)))
            session.add(ClosurePolicy(code=code + "_closure", version="1", title="Test closure", scope_level="request_template", scope_ref=code,
                config_json={"require_resolution_code": True}, is_active=True, published_at=datetime.now(timezone.utc)))
            routing["rules"] = [{"when": {"field": "custom_fields.request_form_data.affected_scope", "op": "eq", "value": "team"}, "then": {"queue_id": mapped_queue.id}}]
            config = {"routing_policy": routing, "priority_policy": {
                "impact_field": "affected_scope", "urgency_field": "work_continuity", "matrix": {"team": {"work_stopped_no_workaround": "P2"}}},
                "approval_policy": {"required": True}, "closure_policy": {"require_resolution_code": True}}
            definition["blocks"][0]["fields"].extend([
                {"key": "scope", "label": "Affected", "type": "radio", "required": True,
                 "options": [{"value": "team", "label": "Team"}], "process_mapping": {"fact_key": "affected_scope", "roles": ["priority_impact", "routing_field"]}},
                {"key": "continuity", "label": "Continuity", "type": "radio", "required": True,
                 "options": [{"value": "work_stopped_no_workaround", "label": "Cannot work"}], "process_mapping": {"fact_key": "work_continuity", "roles": ["priority_urgency"]}},
            ])
            old = await session.get(RequestStudioScenarioVersion, version_id)
            old.state = "retired"
            scenario = await session.get(RequestStudioScenario, old.scenario_id)
            replacement = RequestStudioScenarioVersion(scenario_id=scenario.id, offering_full_code=scenario.offering_full_code,
                version=2, schema_version=1, definition=definition, content_hash="b" * 64, source_snapshot={}, published_by="test")
            session.add(replacement)
            await session.flush()
            scenario.published_version_id = replacement.id
        await TicketFormPacksRepo(session).upsert_pack(
            pack_key="request_forms", version=code,
            schema_json={"pack_key": "request_forms", "version": code, "forms": [{
                "key": code, "request_template_key": code, "title": "Printer", "ticket_type": "incident",
                "request_kind": "incident", "routing_policy": routing,
                "availability_policy": {"available_without_completed_profile": True, "available_without_agent_binding": True},
                "fields": [{"key": "summary", "type": "text", "label": "Summary", "required": True}],
            }]}, created_by="test",
        )
        await TicketFormPacksRepo(session).set_preferred(pack_key="request_forms", version=code, updated_by="test")
        session.add(RequestTemplate(template_code=code, version="1", public_title="Printer", ticket_type="incident",
                                    sla_policy_id=sla_id, approval_policy_code=code + "_approval" if mapped else None,
                                    closure_policy_code=code + "_closure" if mapped else None, config_json=config, is_active=True, published_at=datetime.now(timezone.utc)))
        service = await session.scalar(select(HelpdeskService).where(HelpdeskService.code == code))
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        service.default_queue_id = queue.id
        offering.default_queue_id, offering.request_template_key = queue.id, code
        await session.commit()
    return definition


async def submit_step(client, definition, mapped=False):
    response = await client.post(BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert response.status == 200, await response.text()
    identifier = (await response.json())["data"]["id"]
    url = BASE + "/" + identifier
    answers = {"summary": "No print", **({"scope": "team", "continuity": "work_stopped_no_workaround"} if mapped else {})}
    response = await client.post(url + "/answer", headers=OWNER, json={"expected_block_id": "questions", "revision": 1, "answers": answers})
    assert response.status == 200, await response.text()
    response = await client.post(url + "/advance", headers=OWNER, json={"expected_block_id": "review", "revision": 2})
    assert response.status == 200, await response.text()
    return identifier, url


@pytest.mark.asyncio
async def test_policy_change_between_preview_and_create_rejects_actual_inactive_queue(test_client_light, test_engine, monkeypatch):
    from web_api import requester_handlers
    from tickets import create_flow

    definition = await setup(test_engine, mapped=True)
    identifier, url = await submit_step(test_client_light, definition, mapped=True)
    models = (Ticket, RequesterTicketCreateRequest, TicketEvent, TicketApproval, TicketNotification)
    async with async_sessionmaker(test_engine)() as session:
        before = [await session.scalar(select(func.count()).select_from(model)) for model in models]
    create = requester_handlers.create_requester_ticket_in_session
    actual_queues = []
    routing = create_flow.TicketRoutingService.apply_routing
    targets = []
    playbooks = AsyncMock(return_value=[])
    monkeypatch.setattr(create_flow, "start_ticket_created_playbooks", playbooks)

    async def record_actual_routing(self, *args, **kwargs):
        queue_id = await routing(self, *args, **kwargs)
        actual_queues.append(queue_id)
        assert queue_id == targets[-1]
        return queue_id

    monkeypatch.setattr(create_flow.TicketRoutingService, "apply_routing", record_actual_routing)

    async def publish_other_route_then_create(request, data, session, **kwargs):
        # This separate transaction commits after submit's successful preview,
        # before canonical create reloads the effective registry policy.
        async with async_sessionmaker(test_engine)() as publisher:
            queue = TicketQueue(code=definition["scenario_key"] + "-inactive", name="Inactive route", is_active=False)
            publisher.add(queue)
            await publisher.flush()
            target = queue.id
            targets.append(target)
            publisher.add(RoutingPolicy(code=definition["scenario_key"] + "_reroute", version="1", title="Changed route",
                scope_level="request_template", scope_ref=definition["scenario_key"],
                config_json={"rules": [], "fallback": {"queue_id": target}, "default_queue_id": target},
                is_active=True, published_at=datetime.now(timezone.utc)))
            await publisher.commit()
        return await create(request, data, session, **kwargs)

    monkeypatch.setattr(requester_handlers, "create_requester_ticket_in_session", publish_other_route_then_create)
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert actual_queues, "The interleaved change must reach actual canonical creation"
    assert response.status == 409 and (await response.json())["error_code"] == "PROCESSING_UNAVAILABLE"
    playbooks.assert_not_awaited()
    async with async_sessionmaker(test_engine)() as session:
        assert [await session.scalar(select(func.count()).select_from(model)) for model in models] == before
        row = await session.get(RequestStudioSession, identifier)
        assert row.state == "active" and row.revision == 3 and row.linked_ticket_id is None


@pytest.mark.asyncio
async def test_real_preview_concurrent_submit_snapshot_and_owner_scope(test_client_light, test_engine):
    definition = await setup(test_engine)
    identifier, url = await submit_step(test_client_light, definition)
    async with async_sessionmaker(test_engine)() as session:
        before = await session.scalar(select(func.count()).select_from(Ticket))
    assert (await test_client_light.post(url + "/submit", headers=OTHER, json={"revision": 3, "confirm": True})).status == 404
    assert (await test_client_light.post(url + "/submit", headers={"Authorization": "Bearer test-ui-auditor-token"}, json={"revision": 3, "confirm": True})).status == 403
    assert (await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True, "device_id": "unowned-test-device"})).status == 403
    response = await test_client_light.post(url + "/ticket-preview", headers=OWNER, json={"revision": 3})
    assert response.status == 200, await response.text()
    preview = (await response.json())["data"]
    assert preview["would_create_ticket"] is False and preview["ok"] is True
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
        assert (await session.get(RequestStudioSession, identifier)).state == "active"
    assert (await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 2, "confirm": True})).status == 409
    assert (await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True, "priority": "P1"})).status == 400
    results = await asyncio.gather(*[
        test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True}) for _ in range(2)
    ])
    for response in results:
        assert response.status == 200, await response.text()
    payloads = [(await response.json())["data"] for response in results]
    assert payloads[0]["linked_ticket_id"] == payloads[1]["linked_ticket_id"]
    ticket_id = payloads[0]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before + 1
        row = await session.get(RequestStudioSession, identifier)
        assert row.state == "ticket_created" and row.revision == 4 and row.linked_ticket_id == ticket_id
        ticket = await session.get(Ticket, ticket_id)
        snapshot = ticket.custom_fields["request_scenario"]
        assert snapshot["session_id"] == identifier and snapshot["version_id"] == row.version_id
        assert snapshot["answers"] == {"summary": "No print"}
        assert ticket.custom_fields["request_form_data"] == {"summary": "No print"}
        assert ticket.custom_fields["service_catalog"]["offering_full_code"] == definition["offering_full_code"]
        assert ticket.custom_fields["request_form_summary"][0]["value"] == "No print"
        assert await session.scalar(select(func.count()).select_from(RequesterTicketCreateRequest).where(RequesterTicketCreateRequest.ticket_id == ticket_id)) == 1


@pytest.mark.asyncio
async def test_failed_session_audit_rolls_back_ticket_ledger_and_allows_retry(test_client_light, test_engine, monkeypatch):
    from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo
    definition = await setup(test_engine)
    identifier, url = await submit_step(test_client_light, definition)
    async with async_sessionmaker(test_engine)() as session:
        before = await session.scalar(select(func.count()).select_from(Ticket))
        ledger_before = await session.scalar(select(func.count()).select_from(RequesterTicketCreateRequest))
    with monkeypatch.context() as failing:
        failing.setattr(RequestScenarioSessionRepo, "_audit", AsyncMock(side_effect=RuntimeError("audit unavailable")))
        response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
        assert response.status == 500, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
        assert await session.scalar(select(func.count()).select_from(RequesterTicketCreateRequest)) == ledger_before
        row = await session.get(RequestStudioSession, identifier)
        assert row.state == "active" and row.revision == 3 and row.linked_ticket_id is None
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["state"] == "ticket_created"


@pytest.mark.asyncio
async def test_mapped_facts_drive_real_priority_routing_sla_ola_and_approval(test_client_light, test_engine, monkeypatch):
    from tickets import ola_service
    from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    definition = await setup(test_engine, mapped=True)
    _, url = await submit_step(test_client_light, definition, mapped=True)
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        queue = await session.scalar(select(TicketQueue).where(TicketQueue.code == definition["scenario_key"] + "-mapped"))
        assert ticket.queue_id == queue.id
        assert ticket.custom_fields["priority_decision"]["effective_priority"] == "P2"
        assert ticket.first_response_due_at is not None and ticket.resolution_due_at is not None
        assert ticket.ola_queue_id == queue.id and ticket.ola_ack_due_at is not None and ticket.ola_processing_due_at is not None
        assert ticket.status == "waiting_on_approval"
        assert (await resolve_effective_ticket_policy(session, ticket, "closure"))["require_resolution_code"] is True
        assert ticket.custom_fields["request_form_data"]["affected_scope"] == "team"
        assert ticket.custom_fields["request_scenario"]["field_roles"]["affected_scope"] == ["priority_impact", "routing_field"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["missing", "inactive"])
async def test_published_scenario_rejects_queue_removed_after_preview(test_client_light, test_engine, unavailable):
    definition = await setup(test_engine, mapped=True)
    identifier, url = await submit_step(test_client_light, definition, mapped=True)
    response = await test_client_light.post(url + "/ticket-preview", headers=OWNER, json={"revision": 3})
    assert response.status == 200 and (await response.json())["data"]["ok"] is True
    async with async_sessionmaker(test_engine)() as session:
        queue = await session.scalar(select(TicketQueue).where(TicketQueue.code == definition["scenario_key"] + "-mapped"))
        if unavailable == "missing":
            await session.delete(queue)
        else:
            queue.is_active = False
        await session.commit()
        before = await session.scalar(select(func.count()).select_from(Ticket))
        creates = await session.scalar(select(func.count()).select_from(RequesterTicketCreateRequest))
    response = await test_client_light.post(url + "/ticket-preview", headers=OWNER, json={"revision": 3})
    assert response.status == 200
    preview = (await response.json())["data"]
    assert preview["ok"] is False and preview["blockers"]
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 409 and (await response.json())["error_code"] == "PROCESSING_UNAVAILABLE"
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
        assert await session.scalar(select(func.count()).select_from(RequesterTicketCreateRequest)) == creates
        row = await session.get(RequestStudioSession, identifier)
        assert row.state == "active" and row.revision == 3 and row.linked_ticket_id is None
