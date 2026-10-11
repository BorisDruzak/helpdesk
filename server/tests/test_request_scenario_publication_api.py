"""Isolated publication confirmation, source races and additive rollback."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import ApprovalPolicy, RequestTemplate, VisibilityPolicy, RequestStudioPublishToken, Ticket
from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion
from tests.test_request_scenario_submit_api import setup
from tests.test_request_scenario_admin_api import ADMIN, AUDITOR, BASE

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_simulation_matches_actual_creation_with_offering_ticket_type_override(test_client_light, test_engine):
    from app.db.models import HelpdeskServiceOffering, TicketQueue
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from auth.context import AuthContext, AuthType
    from tests.test_request_scenario_submit_api import submit_step, OWNER
    from web_api.dto.request_scenario_admin import SimulationInput
    identifier, definition = await ready(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        offering.ticket_type_code = "service_request"
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == definition["scenario_key"]))
        queue = await session.scalar(select(TicketQueue).where(TicketQueue.code == definition["scenario_key"] + "-mapped"))
        config = dict(template.config_json)
        config["routing_policy"] = {"rules": [{"when": {"field": "ticket_type", "op": "eq", "value": "service_request"}, "then": {"queue_id": queue.id}}], "fallback": config["routing_policy"]["fallback"]}
        template.config_json = config
        await session.commit()
        auth = AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN)
        simulation = await RequestScenarioRepo(session, auth).simulate(identifier, SimulationInput.model_validate({"revision": 1, "steps": [
            {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print", "scope": "team", "continuity": "work_stopped_no_workaround"}},
            {"expected_block_id": "review", "revision": 2}]}))
        expected = simulation["processing"]
        assert expected["routing"]["queue_code"] == definition["scenario_key"] + "-mapped"
        assert expected["sla"]["resolution_min"] == 120
    _, url = await submit_step(test_client_light, definition, mapped=True)
    response = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.ticket_type == "service_request"
        assert ticket.queue_id == expected["routing"]["queue_id"]
        assert ticket.custom_fields["priority_class"] == expected["priority"]["priority_class"]


@pytest.mark.asyncio
async def test_preview_issues_bound_token_without_ticket_writes(test_engine):
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from tickets.request_scenario_publication import ScenarioPublicationService
    from auth.context import AuthContext, AuthType
    identifier, _ = await ready(test_engine)
    async with async_sessionmaker(test_engine)() as session:
        auth = AuthContext(actor_id="admin-test", actor_role="admin", auth_type=AuthType.UI_TOKEN)
        result = await ScenarioPublicationService(RequestScenarioRepo(session, auth)).preview(identifier, 1)
        assert result["readiness"]["can_publish"] is True, result["readiness"]
        assert result["confirmation_token"]
        from web_api.dto.request_scenario_admin import SimulationInput
        before = await session.scalar(select(func.count()).select_from(Ticket))
        simulation = await RequestScenarioRepo(session, auth).simulate(identifier, SimulationInput.model_validate({"revision": 1, "steps": [
            {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "No print", "scope": "team", "continuity": "work_stopped_no_workaround"}},
            {"expected_block_id": "review", "revision": 2}]}))
        assert simulation["current_step"]["kind"] == "submit_ticket"
        assert simulation["processing"]["priority"]["priority_class"] == "P2"
        assert simulation["processing"]["sla"]["resolution_min"] == 120
        assert simulation["processing"]["would_create_ticket"] is False
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
        await session.rollback()


async def ready(engine):
    definition = await setup(engine, mapped=True)
    code = definition["scenario_key"]
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        row = await session.scalar(select(RequestStudioScenario).where(RequestStudioScenario.scenario_key == code))
        session.add(RequestStudioDraft(scenario_id=row.id, definition=definition, revision=1, updated_by="admin-test"))
        approval = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == code + "_approval"))
        approval.config_json = {"required": False}
        session.add(VisibilityPolicy(code=code + "_visibility", version="1", title="Test visibility", config_json={"public_fields": ["ticket_code", "public_status"]}, is_active=True, published_at=datetime.now(timezone.utc)))
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == code))
        template.visibility_policy_code = code + "_visibility"
        await session.commit()
        return row.id, definition


async def preview(client, identifier, revision=1):
    response = await client.post(BASE + "/scenarios/" + identifier + "/publish-preview", headers=ADMIN, json={"revision": revision})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["readiness"]["can_publish"] is True, data
    assert data["confirmation_token"]
    return {"revision": revision, "confirm": True, "confirmation_token": data["confirmation_token"]}


@pytest.mark.asyncio
async def test_atomic_publish_replay_actor_scope_and_rollback_as_new_version(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    url = BASE + "/scenarios/" + identifier
    assert (await test_client_light.post(url + "/publish-preview", headers=AUDITOR, json={"revision": 1})).status == 403
    async with async_sessionmaker(test_engine)() as session:
        before = await session.scalar(select(func.count()).select_from(Ticket))
    body = await preview(test_client_light, identifier)
    assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=dict(body, confirmation_token="invalid"))).status == 400
    assert (await test_client_light.post(url + "/publish", headers=AUDITOR, json=body)).status == 403
    responses = await asyncio.gather(*[test_client_light.post(url + "/publish", headers=ADMIN, json=body) for _ in range(2)])
    assert sorted(response.status for response in responses) == [200, 409]
    response = next(response for response in responses if response.status == 200)
    result = (await response.json())["data"]
    published_id = result["version"]["id"]
    catalog_response = await test_client_light.get(BASE + "/catalog", headers=ADMIN)
    assert catalog_response.status == 200, await catalog_response.text()
    catalog_item = next(item for item in (await catalog_response.json())["data"]["scenarios"] if item["id"] == identifier)
    assert catalog_item["published_version"] == 3
    assert catalog_item["updated_at"]
    async with async_sessionmaker(test_engine)() as session:
        version = await session.get(RequestStudioScenarioVersion, published_id)
        assert version.version == 3 and version.source_snapshot["effective_template"]
        assert (await session.get(RequestStudioScenario, identifier)).published_version_id == published_id
        assert await session.scalar(select(func.count()).select_from(Ticket)) == before
    response = await test_client_light.post(url + "/rollback-draft", headers=ADMIN, json={"revision": 1, "version_id": published_id})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["draft"]["revision"] == 2
    rollback_body = await preview(test_client_light, identifier, 2)
    response = await test_client_light.post(url + "/publish", headers=ADMIN, json=rollback_body)
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["version"]["version"] == 4


@pytest.mark.asyncio
async def test_edit_source_change_expiry_and_audit_failure_leave_versions_unchanged(test_client_light, test_engine, monkeypatch):
    from app.repos.request_scenario_repo import RequestScenarioRepo
    identifier, definition = await ready(test_engine)
    url = BASE + "/scenarios/" + identifier
    body = await preview(test_client_light, identifier)
    async with async_sessionmaker(test_engine)() as session:
        template = await session.scalar(select(RequestTemplate).where(RequestTemplate.template_code == definition["scenario_key"]))
        template.public_title = "Changed after preview"
        await session.commit()
    assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=body)).status == 409
    body = await preview(test_client_light, identifier)
    with monkeypatch.context() as failing:
        failing.setattr(RequestScenarioRepo, "_audit", AsyncMock(side_effect=RuntimeError("audit unavailable")))
        assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=body)).status == 500
    async with async_sessionmaker(test_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.scenario_id == identifier)) == 2
        token = await session.scalar(select(RequestStudioPublishToken).where(RequestStudioPublishToken.scope == "request_scenario.publish").order_by(RequestStudioPublishToken.id.desc()))
        assert token.used_at is None
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()
    assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=body)).status == 409
    body = await preview(test_client_light, identifier)
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": dict(definition, title="Edited")})
    assert response.status == 200
    assert (await test_client_light.post(url + "/publish", headers=ADMIN, json=body)).status == 409


@pytest.mark.asyncio
async def test_health_does_not_hide_graph_or_processing_blockers(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    url = BASE + "/scenarios/" + identifier
    response = await test_client_light.put(url + "/draft", headers=ADMIN, json={"revision": 1, "definition": dict(definition, blocks=[], entry_block_id=None)})
    assert response.status == 200
    response = await test_client_light.post(url + "/publish-preview", headers=ADMIN, json={"revision": 2})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["health"] and data["readiness"]["can_publish"] is False
    assert data["confirmation_token"] is None
