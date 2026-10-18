"""Portable import creates one new canonical draft with no preview side effects."""
from copy import deepcopy
import json
import uuid
from unittest.mock import AsyncMock

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (ApprovalPolicy, DiagnosticSession, HelpdeskServiceCatalogAudit, HelpdeskServiceOffering,
    RoutingPolicy, SlaPolicy, Ticket, TicketBusinessCalendar, TicketQueue)
from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario, RequestStudioScenarioVersion, RequestStudioSession
from app.repos.request_scenario_repo import RequestScenarioRepo
from tests.test_request_scenario_admin_api import ADMIN, AUDITOR, BASE
from tests.test_request_scenario_publication_api import ready

pytestmark = [pytest.mark.db_cleanup("full"), pytest.mark.light_app]
PREVIEW = BASE + "/services/document-preview"
CREATE = BASE + "/services/from-document"
MODELS = (HelpdeskServiceOffering, HelpdeskServiceCatalogAudit, RequestStudioScenario, RequestStudioDraft,
    RequestStudioScenarioVersion, RequestStudioSession, Ticket, DiagnosticSession, RoutingPolicy, SlaPolicy, TicketQueue, TicketBusinessCalendar)


async def counts(engine):
    async with async_sessionmaker(engine)() as session:
        return [await session.scalar(select(func.count()).select_from(model)) for model in MODELS]


def portable(definition):
    raw = deepcopy(definition)
    for key in ("scenario_key", "service_code", "offering_full_code"):
        raw.pop(key)
    raw["process_binding"].pop("request_template_key")
    # The legacy v1 seed has no catalog entrances. A new v2/v3 service map
    # requires an explicit entrance; normalization must not invent one.
    if not raw.get("entry_points"):
        raw["entry_points"] = [{"key": "main", "title": raw["title"], "target_block_id": raw["entry_block_id"]}]
    return raw


def document(definition, service_code, format="json", **extra):
    return {"service_code": service_code, "format": format,
        "content": json.dumps(definition, ensure_ascii=False) if format == "json" else yaml.safe_dump(definition, allow_unicode=True), **extra}


async def preview(client, value):
    response = await client.post(PREVIEW, headers=ADMIN, json=value)
    assert response.status == 200, await response.text()
    return (await response.json())["data"]


def create_input(value, checked):
    return {**value, "creation_key": checked["creation_key"], "source_hash": checked["source_hash"]}


@pytest.mark.asyncio
async def test_preview_is_admin_only_and_json_yaml_portable_preview_writes_nothing(test_client_light, test_engine, monkeypatch):
    # The shared fixture supplies support for missing credentials. Remove only
    # that compatibility default while exercising the real role decorator.
    from auth import middleware
    original = middleware.extract_auth_context

    async def explicit_auth(request):
        return await original(request) if request.headers.get("Authorization") else None

    monkeypatch.setattr(middleware, "extract_auth_context", explicit_auth)
    _, definition = await ready(test_engine)
    before = await counts(test_engine)
    value = document(portable(definition), definition["service_code"])
    for headers, status in (({}, 401), (AUDITOR, 403), ({"Authorization": "Bearer test-ui-support-token"}, 403), ({"Authorization": "Bearer test-ui-user:document-requester"}, 403)):
        assert (await test_client_light.post(PREVIEW, headers=headers, json=value)).status == status
        assert (await test_client_light.post(CREATE, headers=headers, json={**value, "creation_key": str(uuid.uuid4()), "source_hash": "a" * 64})).status == status
    checked = await preview(test_client_light, value)
    assert checked["issues"] == []
    assert checked["definition"]["scenario_key"] == "scenario_import_" + checked["creation_key"].replace("-", "")
    yaml_value = document(portable(definition), definition["service_code"], "yaml", creation_key=checked["creation_key"])
    yaml_checked = await preview(test_client_light, yaml_value)
    assert yaml_checked == checked
    assert await counts(test_engine) == before


@pytest.mark.asyncio
async def test_existing_export_creates_distinct_draft_idempotently_without_touching_source(test_client_light, test_engine):
    source_id, definition = await ready(test_engine)
    original = (await (await test_client_light.get(BASE + "/scenarios/" + source_id, headers=ADMIN)).json())["data"]
    foreign = deepcopy(definition)
    foreign["category_id"] = str(uuid.uuid4())
    foreign["entry_points"] = [{"key": "main", "title": "Печать", "target_block_id": "questions", "category_id": str(uuid.uuid4())}]
    value = document(foreign, definition["service_code"], "yaml")
    before = await counts(test_engine)
    checked = await preview(test_client_light, value)
    assert checked["definition"]["category_id"] is None
    assert checked["definition"]["entry_points"][0]["category_id"] is None
    assert checked["issues"] == []
    result = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
    assert result.status == 200, await result.text()
    created = (await result.json())["data"]
    assert created["scenario"]["id"] != source_id
    assert created["scenario"]["published_version_id"] is None and created["scenario"]["enabled"] is False
    assert created["draft"]["revision"] == 1 and created["draft"]["definition"] == checked["definition"]
    after = await counts(test_engine)
    again = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
    assert again.status == 200, await again.text()
    assert (await again.json())["data"]["scenario"]["id"] == created["scenario"]["id"]
    assert await counts(test_engine) == after
    assert after[0] == before[0] + 1 and after[2] == before[2] + 1 and after[3] == before[3] + 1
    assert after[4:] == before[4:]
    async with async_sessionmaker(test_engine)() as session:
        offering = await session.scalar(select(HelpdeskServiceOffering).where(HelpdeskServiceOffering.full_code == created["scenario"]["offering_full_code"]))
        assert offering.lifecycle_status == "draft" and offering.published_at is None
    retained = (await (await test_client_light.get(BASE + "/scenarios/" + source_id, headers=ADMIN)).json())["data"]
    assert retained == original
    immutable = await test_client_light.post(BASE + "/documents/validate?scenario_id=" + source_id, headers=ADMIN,
        json={"format": "json", "content": json.dumps(checked["definition"])})
    assert immutable.status == 409 and (await immutable.json())["error_code"] == "CATALOG_BINDING_IMMUTABLE"
    changed = deepcopy(value)
    changed["content"] = yaml.safe_dump({**foreign, "title": "Changed content"})
    conflict = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(changed, checked))
    assert conflict.status == 409 and (await conflict.json())["error_code"] == "IMPORT_PREVIEW_CHANGED"
    assert await counts(test_engine) == after


@pytest.mark.asyncio
async def test_invalid_graph_queue_calendar_category_and_policy_never_create_rows(test_client_light, test_engine):
    _, definition = await ready(test_engine)
    base = portable(definition)
    base.update(schema_version=3, processing={"sla_profiles": {"standard": {"title": "Standard", "first_response_minutes": 30, "resolution_minutes": 120}},
        "routes": {"support": {"title": "Support", "queue_code": definition["scenario_key"]}}, "defaults": {"route": "support", "sla_profile": "standard"}})
    before = await counts(test_engine)
    for problem, expected_path in (("graph", "blocks.questions.transitions"), ("queue", "processing.routes.support.queue_code"),
        ("calendar", "processing.sla_profiles.standard.calendar_id"), ("category", "category_id"), ("policy", "process_binding.policy_refs")):
        raw, extra = deepcopy(base), {}
        if problem == "graph": raw["blocks"][0]["transitions"][0]["to"] = "missing"
        if problem == "queue": raw["processing"]["routes"]["support"]["queue_code"] = "missing_document_queue"
        if problem == "calendar": raw["processing"]["sla_profiles"]["standard"].update(time_basis="business", calendar_id=987654321)
        if problem == "category": extra["category_id"] = str(uuid.uuid4())
        if problem == "policy": raw["process_binding"]["policy_refs"] = {"priority": "missing_document_policy"}
        value = document(raw, definition["service_code"], **extra)
        checked = await preview(test_client_light, value)
        assert any(issue["path"] == expected_path for issue in checked["issues"]), checked["issues"]
        response = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
        assert response.status == 400, await response.text()
        assert await counts(test_engine) == before


@pytest.mark.asyncio
async def test_changed_canonical_defaults_require_new_preview_without_creating_anything(test_client_light, test_engine):
    _, definition = await ready(test_engine)
    value = document(portable(definition), definition["service_code"])
    checked = await preview(test_client_light, value)
    async with async_sessionmaker(test_engine)() as session:
        policy = await session.scalar(select(ApprovalPolicy).where(ApprovalPolicy.code == definition["scenario_key"] + "_approval"))
        policy.config_json = {"required": False, "require_comment_on_reject": True}
        await session.commit()
    before = await counts(test_engine)
    current = await preview(test_client_light, {**value, "creation_key": checked["creation_key"]})
    assert current["definition"] == checked["definition"] and current["source_hash"] != checked["source_hash"]
    response = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
    assert response.status == 409 and (await response.json())["error_code"] == "IMPORT_PREVIEW_CHANGED"
    assert await counts(test_engine) == before


@pytest.mark.asyncio
async def test_v3_map_owned_processing_ignores_inert_legacy_refs_but_checks_other_policies(test_client_light, test_engine):
    _, definition = await ready(test_engine)
    inactive_sla = definition["scenario_key"] + "_inactive_legacy_sla"
    async with async_sessionmaker(test_engine)() as session:
        session.add(SlaPolicy(code=inactive_sla, version="1", title="Inactive legacy SLA", is_active=False))
        await session.commit()
    raw = portable(definition)
    refs = {"routing": "missing_document_legacy_route", "sla": inactive_sla}
    raw.update(schema_version=3, process_binding={"policy_refs": refs}, processing={
        "routes": {"support": {"title": "Support", "queue_code": definition["scenario_key"]}},
        "sla_profiles": {"standard": {"title": "Standard", "first_response_minutes": 30, "resolution_minutes": 120}},
        "defaults": {"route": "support", "sla_profile": "standard"}})
    before = await counts(test_engine)
    for kind in ("priority", "approval"):
        invalid = deepcopy(raw)
        invalid["process_binding"]["policy_refs"][kind] = "missing_document_non_map_policy"
        value = document(invalid, definition["service_code"])
        checked = await preview(test_client_light, value)
        assert any(issue["code"] == "policy_reference_unavailable" for issue in checked["issues"])
        response = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
        assert response.status == 400, await response.text()
        assert await counts(test_engine) == before
    value = document(raw, definition["service_code"])
    checked = await preview(test_client_light, value)
    assert checked["issues"] == [] and checked["definition"]["process_binding"]["policy_refs"] == refs
    assert await counts(test_engine) == before
    response = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
    assert response.status == 200, await response.text()
    result = (await response.json())["data"]
    assert result["draft"]["definition"]["process_binding"]["policy_refs"] == refs
    assert result["scenario"]["published_version_id"] is None and result["scenario"]["enabled"] is False
    assert (await counts(test_engine))[4:] == before[4:]


@pytest.mark.asyncio
async def test_late_audit_failure_rolls_back_offering_scenario_and_audit_then_retry_succeeds(test_client_light, test_engine, monkeypatch):
    _, definition = await ready(test_engine)
    value = document(portable(definition), definition["service_code"])
    checked = await preview(test_client_light, value)
    before = await counts(test_engine)
    with monkeypatch.context() as failing:
        failing.setattr(RequestScenarioRepo, "_audit", AsyncMock(side_effect=RuntimeError("late audit failure")))
        result = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
        assert result.status == 500, await result.text()
    assert await counts(test_engine) == before
    result = await test_client_light.post(CREATE, headers=ADMIN, json=create_input(value, checked))
    assert result.status == 200, await result.text()
