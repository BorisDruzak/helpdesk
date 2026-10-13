"""Real PostgreSQL source projection, conversion, interchange and pinning."""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.models import HelpdeskServiceOffering, Ticket
from app.db.request_scenario_models import RequestStudioScenarioVersion
from tests.test_request_scenario_publication_api import ready, preview
from tests.test_request_scenario_admin_api import ADMIN, AUDITOR, BASE
from tests.test_request_scenario_session_api import OWNER, BASE as SESSIONS

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]


@pytest.mark.asyncio
async def test_direct_service_creation_is_atomic_idempotent_and_admin_only(test_client_light, test_engine):
    _, existing = await ready(test_engine)
    source = {"schema_version": 2, "scenario_key": "new_" + uuid.uuid4().hex, "service_code": existing["service_code"],
        "title": "New service", "offering_full_code": "", "process_binding": {"request_template_key": ""}, "blocks": [], "entry_points": []}
    assert (await test_client_light.post(BASE + "/services", headers=AUDITOR, json={"definition": source})).status == 403
    created = await test_client_light.post(BASE + "/services", headers=ADMIN, json={"definition": source})
    assert created.status == 200, await created.text()
    value = (await created.json())["data"]
    assert value["draft"]["definition"]["schema_version"] == 2
    assert value["draft"]["definition"]["publish_offering"] is True
    again = await test_client_light.post(BASE + "/services", headers=ADMIN, json={"definition": source})
    assert again.status == 200, await again.text()
    assert (await again.json())["data"]["scenario"]["id"] == value["scenario"]["id"]
    source["title"] = "Concurrent different data"
    assert (await test_client_light.post(BASE + "/services", headers=ADMIN, json={"definition": source})).status == 409


@pytest.mark.asyncio
async def test_v2_map_questions_publish_create_and_keep_v1_session_pinned(test_client_light, test_engine):
    identifier, definition = await ready(test_engine)
    old = await test_client_light.post(SESSIONS, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    assert old.status == 200
    old_session = (await old.json())["data"]
    definition["schema_version"] = 2
    definition["entry_points"] = [{"key": "main", "title": "Printer", "target_block_id": "questions"}]
    definition["blocks"][0]["fields"] = [{"key": "fresh", "type": "radio", "label": "New map question", "required": True,
        "options": [{"value": "department", "label": "Whole department"}], "process_mapping": {
            "effects": [{"value": "department", "facts": {"impact": "department", "urgency": "blocked"}}]}}]
    saved = await test_client_light.put(BASE + "/scenarios/" + identifier + "/draft", headers=ADMIN, json={"definition": definition, "revision": 1})
    assert saved.status == 200, await saved.text()
    body = await preview(test_client_light, identifier, 2)
    published = await test_client_light.post(BASE + "/scenarios/" + identifier + "/publish", headers=ADMIN, json=body)
    assert published.status == 200, await published.text()
    started = await test_client_light.post(SESSIONS, headers=OWNER, json={"offering_full_code": definition["offering_full_code"]})
    value = (await started.json())["data"]
    assert [item["key"] for item in value["block"]["fields"]] == ["fresh"]
    url = SESSIONS + "/" + value["id"]
    answered = await test_client_light.post(url + "/answer", headers=OWNER, json={"expected_block_id": "questions", "revision": 1, "answers": {"fresh": "department"}})
    assert answered.status == 200, await answered.text()
    assert (await test_client_light.post(url + "/advance", headers=OWNER, json={"expected_block_id": "review", "revision": 2})).status == 200
    submitted = await test_client_light.post(url + "/submit", headers=OWNER, json={"revision": 3, "confirm": True})
    assert submitted.status == 200, await submitted.text()
    ticket_id = (await submitted.json())["data"]["linked_ticket_id"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.custom_fields["request_scenario"]["facts"] == {"fresh": "department"}
        assert ticket.custom_fields["request_scenario"]["processing_facts"]["impact"] == "department"
        version = await session.scalar(select(RequestStudioScenarioVersion).where(RequestStudioScenarioVersion.scenario_id == identifier, RequestStudioScenarioVersion.state == "published"))
        assert version.schema_version == 2
    retained = await test_client_light.get(SESSIONS + "/" + old_session["id"], headers=OWNER)
    assert (await retained.json())["data"]["block"]["fields"][0]["key"] == "summary"


@pytest.mark.asyncio
async def test_document_round_trip_has_no_save_or_publish_side_effect(test_client_light, test_engine):
    identifier, _ = await ready(test_engine)
    url = BASE + "/scenarios/" + identifier
    for format in ("json", "yaml"):
        exported = await test_client_light.get(url + "/document?format=" + format, headers=AUDITOR)
        assert exported.status == 200
        document = (await exported.json())["data"]
        checked = await test_client_light.post(BASE + "/documents/validate?scenario_id=" + identifier, headers=ADMIN, json=document)
        assert checked.status == 200, await checked.text()
        assert not (await checked.json())["data"]["diff"]
    invalid = await test_client_light.post(BASE + "/documents/validate?scenario_id=" + identifier, headers=ADMIN, json={"format": "yaml", "content": "a: &x [1]\nb: *x"})
    assert invalid.status == 400
    detail = (await (await test_client_light.get(url, headers=ADMIN)).json())["data"]
    assert detail["draft"]["revision"] == 1


@pytest.mark.asyncio
async def test_conversion_replays_without_overwriting_maps_or_publishing(test_client_light, test_engine):
    _, definition = await ready(test_engine)
    code = definition["service_code"] + ".convert"
    async with async_sessionmaker(test_engine)() as session:
        donor = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == definition["offering_full_code"]))
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=donor.service_id, code="convert", full_code=code,
            name="Convert", public_title="Convert", lifecycle_status="published", visibility="public", request_template_key=donor.request_template_key))
        await session.commit()
    before = await test_client_light.post(BASE + "/convert-forms", headers=ADMIN, json={"offering_full_code": code})
    assert (await before.json())["data"]["items"][0]["status"] == "ready"
    result = await test_client_light.post(BASE + "/convert-forms", headers=ADMIN, json={"offering_full_code": code, "apply": True})
    assert result.status == 200, await result.text()
    item = (await result.json())["data"]["items"][0]
    assert item["status"] == "converted"
    assert item["detail"]["scenario"]["published_version_id"] is None
    repeat = await test_client_light.post(BASE + "/convert-forms", headers=ADMIN, json={"offering_full_code": code, "apply": True})
    repeated = (await repeat.json())["data"]["items"][0]
    assert repeated["status"] == "existing"
    assert repeated["detail"]["draft"]["revision"] == 1
    archived = await test_client_light.post(BASE + "/scenarios/" + item["detail"]["scenario"]["id"] + "/archive", headers=ADMIN, json={"revision": 1})
    assert archived.status == 200, await archived.text()
    again = await test_client_light.post(BASE + "/convert-forms", headers=ADMIN, json={"offering_full_code": code, "apply": True})
    assert again.status == 200, await again.text()
    retained = (await again.json())["data"]["items"][0]
    assert retained["status"] == "existing" and retained["archived"]
    assert retained["detail"]["scenario"]["id"] == item["detail"]["scenario"]["id"]
