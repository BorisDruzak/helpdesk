"""Isolated PostgreSQL requester ownership, pinning and command acceptance."""
import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceUserBinding, HelpdeskService, HelpdeskServiceOffering, HelpdeskServiceCatalogAudit, RegistryDepartment, RegistryPerson, RegistryPersonIdentity
from app.db.request_scenario_models import RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]
BASE = "/api/web/requester/request-scenarios/sessions"
OWNER = {"Authorization": "Bearer test-ui-user:scenario-owner"}
OTHER = {"Authorization": "Bearer test-ui-user:scenario-other"}


async def seed(engine, guided=False):
    code = "session_" + uuid.uuid4().hex[:8]
    sid, vid = str(uuid.uuid4()), str(uuid.uuid4())
    definition = {
        "scenario_key": code, "service_code": code, "offering_full_code": code + ".printer",
        "title": "Printer", "entry_block_id": "questions",
        "process_binding": {"request_template_key": code},
        "blocks": [
            {"id": "questions", "kind": "form_page", "title": "Question",
             "fields": [{"key": "summary", "type": "text", "label": "Summary", "required": True}],
             "transitions": [{"to": "review"}]},
            {"id": "review", "kind": "review", "title": "Review", "transitions": [{"to": "submit"}]},
            {"id": "submit", "kind": "submit_ticket", "title": "Submit"},
        ],
    }
    if guided:
        page = definition["blocks"][0]
        page["fields"].append({"key": "details", "type": "text", "label": "Details", "required": True,
            "visible_when": {"op": "eq", "source": "answer", "field": "summary", "value": "other"}})
        page["transitions"] = [{"to": "instruction"}]
        definition["blocks"].extend([
            {"id": "instruction", "kind": "instruction", "title": "Check power",
             "content": {"format": "plain", "body": "Check the power cable"}, "transitions": [{"to": "diagnostic"}]},
            {"id": "diagnostic", "kind": "diagnostic", "title": "Diagnostics", "transitions": [{"to": "resolved"}]},
            {"id": "resolved", "kind": "resolution_check", "title": "Resolved?", "transitions": [
                {"to": "finish", "when": {"op": "eq", "source": "current_result", "value": "yes"}}, {"to": "review"}]},
            {"id": "finish", "kind": "finish", "title": "Resolved"},
        ])
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        service = HelpdeskService(service_id=str(uuid.uuid4()), code=code, name="Session test",
                                  public_title="Session test", visibility="public", lifecycle_status="published")
        session.add(service)
        await session.flush()
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=service.service_id,
                    code="printer", full_code=code + ".printer", name="Printer", public_title="Printer",
                    visibility="public", lifecycle_status="published"))
        await session.flush()
        scenario = RequestStudioScenario(id=sid, scenario_key=code, service_code=code,
                    offering_full_code=code + ".printer", title="Printer", enabled=True)
        session.add(scenario)
        await session.flush()
        session.add(RequestStudioScenarioVersion(id=vid, scenario_id=sid, offering_full_code=code + ".printer",
                    version=1, schema_version=1, definition=definition, content_hash="a" * 64,
                    source_snapshot={}, published_by="test"))
        await session.flush()
        scenario.published_version_id = vid
        await session.commit()
    return definition, vid


@pytest.mark.asyncio
async def test_owner_resume_cas_back_replay_expiry_and_version_pin(test_client_light, test_engine, monkeypatch):
    definition, vid = await seed(test_engine)
    catalog = await (await test_client_light.get("/api/service-catalog/current", headers=OWNER)).json()
    service = next(item for item in catalog["services"] if item["service_code"] == definition["service_code"])
    assert service["offerings"][0]["guided_scenario_enabled"] is True
    body = {"offering_full_code": definition["offering_full_code"]}
    response = await test_client_light.post(BASE, headers=OWNER, json=body)
    assert response.status == 200, await response.text()
    started = (await response.json())["data"]
    identifier = started["id"]
    url = BASE + "/" + identifier
    assert started["version_id"] == vid and started["revision"] == 1
    assert (await (await test_client_light.post(BASE, headers=OWNER, json=body)).json())["data"]["id"] == identifier
    for method, suffix, payload in [("get", "", None), ("post", "/answer", {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "forged"}})]:
        assert (await getattr(test_client_light, method)(url + suffix, headers=OTHER, json=payload)).status == 404
    invalid = {"expected_block_id": "questions", "revision": 1, "answers": {}}
    assert (await test_client_light.post(url + "/answer", headers=OWNER, json=invalid)).status == 400
    command = dict(invalid, answers={"summary": "Printer stopped"})
    responses = await asyncio.gather(*[
        test_client_light.post(url + "/answer", headers=OWNER, json=command) for _ in range(2)
    ])
    assert [r.status for r in responses] == [200, 200]
    returned = [await r.json() for r in responses]
    assert all(data["data"]["revision"] == 2 for data in returned)
    assert (await test_client_light.post(url + "/answer", headers=OWNER, json=dict(command, answers={"summary": "different"}))).status == 409
    response = await test_client_light.post(url + "/back", headers=OWNER, json={"target_block_id": "questions", "revision": 2})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["revision"] == 3 and data["block"]["fields"][0]["value"] == "Printer stopped"
    with monkeypatch.context() as patch:
        patch.setattr("app.repos.service_catalog_repo.ServiceCatalogRepo.append_audit", AsyncMock(side_effect=RuntimeError("audit unavailable")))
        response = await test_client_light.post(url + "/answer", headers=OWNER,
            json={"expected_block_id": "questions", "revision": 3, "answers": {"summary": "Must roll back"}})
        assert response.status == 500
    async with async_sessionmaker(test_engine)() as session:
        row = await session.get(RequestStudioSession, identifier)
        assert row.revision == 3 and row.answers == {"summary": "Printer stopped"}
    async with async_sessionmaker(test_engine)() as session:
        await session.execute(update(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.id == vid).values(state="retired"))
        await session.commit()
    assert (await (await test_client_light.get(url, headers=OWNER)).json())["data"]["version_id"] == vid
    async with async_sessionmaker(test_engine)() as session:
        await session.execute(update(RequestStudioSession).where(RequestStudioSession.id == identifier).values(
            created_at=datetime.now(timezone.utc) - timedelta(days=2), expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
        await session.commit()
    assert (await test_client_light.get(url, headers=OWNER)).status == 410


@pytest.mark.asyncio
async def test_conditional_page_instruction_unavailable_diagnostic_and_finish(test_client_light, test_engine):
    definition, _ = await seed(test_engine, guided=True)
    response = await test_client_light.post(BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    url = BASE + "/" + data["id"]
    assert [f["key"] for f in data["block"]["fields"]] == ["summary"]
    answers = {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "other"}}
    response = await test_client_light.post(url + "/step-preview", headers=OWNER, json=answers)
    assert response.status == 200, await response.text()
    assert [f["key"] for f in (await response.json())["data"]["block"]["fields"]] == ["summary", "details"]
    assert "value" not in (await (await test_client_light.get(url, headers=OWNER)).json())["data"]["block"]["fields"][0]
    assert (await test_client_light.post(url + "/answer", headers=OWNER, json=answers)).status == 400
    answers["answers"]["details"] = "Power cable"
    response = await test_client_light.post(url + "/answer", headers=OWNER, json=answers)
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["block"]["kind"] == "instruction"
    advance = {"expected_block_id": "instruction", "revision": 2, "current_result": "acknowledged"}
    response = await test_client_light.post(url + "/advance", headers=OWNER, json=advance)
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["block"]["id"] == "resolved"
    async with async_sessionmaker(test_engine)() as session:
        row = await session.get(RequestStudioSession, data["id"])
        assert row.results["diagnostic"]["status"] == "unavailable"
    response = await test_client_light.post(url + "/advance", headers=OWNER,
        json={"expected_block_id": "resolved", "revision": 3, "current_result": "yes"})
    assert response.status == 200, await response.text()
    assert (await response.json())["data"]["state"] == "completed_self_service"
    for _ in range(2):
        response = await test_client_light.post(url + "/finish", headers=OWNER, json={"revision": 4})
        assert response.status == 200 and (await response.json())["data"]["revision"] == 5


@pytest.mark.asyncio
async def test_picker_sources_are_owned_and_forged_identifiers_are_rejected(test_client_light, test_engine):
    definition, vid = await seed(test_engine)
    # Retire first version and create an additive version, never patch JSON.
    definition["blocks"][0]["fields"] = [
        {"key": "department", "type": "department_picker", "label": "Department", "required": True},
        {"key": "computer", "type": "device_picker", "label": "Computer", "required": True},
    ]
    dept_id, person_id, owned_id, other_id = [str(uuid.uuid4()) for _ in range(4)]
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        old = await session.get(RequestStudioScenarioVersion, vid)
        old.state = "retired"
        scenario = await session.get(RequestStudioScenario, old.scenario_id)
        session.add(RegistryDepartment(department_id=dept_id, name="IT"))
        session.add(RegistryPerson(person_id=person_id, display_name="Picker requester", full_name="Picker requester", status="active"))
        session.add_all([Device(device_id=owned_id, hostname="Owned", protocol_version="ws_ticket_v3", agent_version="test", os="Windows"),
                        Device(device_id=other_id, hostname="Other", protocol_version="ws_ticket_v3", agent_version="test", os="Windows")])
        await session.flush()
        session.add(RegistryPersonIdentity(person_id=person_id, provider="ui_login", identifier="scenario-owner", normalized_identifier="scenario-owner", verified=True))
        session.add(DeviceUserBinding(device_id=owned_id, person_id=person_id, status="active"))
        replacement = RequestStudioScenarioVersion(scenario_id=scenario.id, offering_full_code=scenario.offering_full_code,
            version=2, schema_version=1, definition=definition, content_hash="b" * 64, source_snapshot={}, published_by="test")
        session.add(replacement)
        await session.flush()
        scenario.published_version_id = replacement.id
        await session.commit()
    response = await test_client_light.post(BASE, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    fields = data["block"]["fields"]
    assert {item["value"] for item in fields[0]["options"]} == {dept_id}
    assert fields[1]["options"] == [{"value": owned_id, "label": "Owned"}]
    url = BASE + "/" + data["id"] + "/answer"
    command = {"expected_block_id": "questions", "revision": 1, "answers": {"department": dept_id, "computer": other_id}}
    assert (await test_client_light.post(url, headers=OWNER, json=command)).status == 400
    command["answers"]["computer"] = owned_id
    response = await test_client_light.post(url, headers=OWNER, json=command)
    assert response.status == 200, await response.text()
    assert [item["display_value"] for item in (await response.json())["data"]["block"]["answers"]] == ["IT", "Owned"]
    async with async_sessionmaker(test_engine)() as session:
        events = (await session.scalars(select(HelpdeskServiceCatalogAudit).where(HelpdeskServiceCatalogAudit.object_code == data["id"]).order_by(HelpdeskServiceCatalogAudit.id))).all()
        assert [event.action for event in events] == ["start", "answer"]
        assert all(owned_id not in str(event.after_json) for event in events)
