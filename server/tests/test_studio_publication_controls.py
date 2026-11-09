"""Independent catalogue visibility and configured defaults without DB access."""
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import make_mocked_request
from pydantic import ValidationError

from app.db.models import HelpdeskServiceOffering
from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError
from app.repos.service_catalog_repo import ServiceCatalogRepo, serialize_offering
from web_api import request_scenario_admin_handlers as handlers

pytestmark = pytest.mark.no_db


def test_visibility_input_requires_expected_value_and_forbids_draft_fields():
    from web_api.dto.request_scenario_admin import ScenarioCatalogVisibility
    assert ScenarioCatalogVisibility(visibility="internal", expected_visibility="public").visibility == "internal"
    for value in ({"visibility": "public"}, {"visibility": "public", "expected_visibility": "public", "revision": 3},
                  {"visibility": True, "expected_visibility": "public"}):
        with pytest.raises(ValidationError):
            ScenarioCatalogVisibility.model_validate(value)


@pytest.mark.asyncio
async def test_visibility_only_changes_offering_visibility_and_audit_metadata():
    row = HelpdeskServiceOffering(offering_id="offering", service_id="service", full_code="workplace.printer",
        code="printer", visibility="public", lifecycle_status="published", metadata_json={"private": "preserve"})
    session = SimpleNamespace(scalar=AsyncMock(return_value=row), get=AsyncMock(return_value=SimpleNamespace(code="workplace")), flush=AsyncMock())
    repo = ServiceCatalogRepo(session)
    repo.append_audit = AsyncMock()
    before = serialize_offering(row, service_code="workplace")
    result = await repo.set_offering_visibility("workplace.printer", visibility="internal", expected_visibility="public", actor_id="admin", actor_role="admin")
    assert result["visibility"] == "internal" and result["lifecycle_status"] == "published"
    changed = {key for key in before if result[key] != before[key]}
    assert changed == {"visibility", "updated_at", "updated_by"}
    statement = session.scalar.await_args.args[0]
    assert statement._for_update_arg is not None
    assert statement.get_execution_options()["populate_existing"]
    audit = repo.append_audit.await_args.kwargs
    assert audit["action"] == "visibility_changed" and audit["before"] == before and audit["after"] == result


@pytest.mark.asyncio
async def test_visibility_expected_value_conflict_is_nonmutating():
    from app.repos.service_catalog_repo import CatalogVisibilityConflict
    row = HelpdeskServiceOffering(visibility="restricted")
    session = SimpleNamespace(scalar=AsyncMock(return_value=row), flush=AsyncMock())
    repo = ServiceCatalogRepo(session)
    repo.append_audit = AsyncMock()
    with pytest.raises(CatalogVisibilityConflict):
        await repo.set_offering_visibility("workplace.printer", visibility="public", expected_visibility="internal", actor_id="admin", actor_role="admin")
    assert row.visibility == "restricted"
    session.flush.assert_not_awaited()
    repo.append_audit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("role,status", [(None, 401), ("auditor", 403), ("support", 403), ("requester", 403), ("admin", 200)])
async def test_visibility_endpoint_is_admin_only_and_commits(monkeypatch, role, status):
    request = make_mocked_request("POST", "/visibility", match_info={"identifier": "11111111-1111-1111-1111-111111111111"})
    if role:
        request["auth_context"] = SimpleNamespace(actor_role=role, actor_id="actor")
    session = SimpleNamespace(commit=AsyncMock())
    @asynccontextmanager
    async def get_session():
        yield session
    operation = AsyncMock(return_value={"offering": {"visibility": "internal"}})
    monkeypatch.setattr(handlers, "get_session", get_session)
    monkeypatch.setattr(handlers.RequestScenarioRepo, "set_catalog_visibility", operation)
    monkeypatch.setattr(handlers, "_payload", AsyncMock(return_value=SimpleNamespace(visibility="internal", expected_visibility="public")))
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())
    response = await handlers.handle_scenario_catalog_visibility(request)
    assert response.status == status
    if status == 200:
        session.commit.assert_awaited_once()
        assert json.loads(response.body)["data"] == {"offering": {"visibility": "internal"}}
    else:
        operation.assert_not_awaited()
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_visibility_repository_uses_bound_offering_without_draft_write():
    repo = RequestScenarioRepo(None, SimpleNamespace(actor_id="admin", actor_role="admin"))
    repo.detail = AsyncMock(return_value=(SimpleNamespace(service_code="workplace", offering_full_code="workplace.printer", archived=False), object()))
    repo._service_lock = AsyncMock()
    repo.catalog.set_offering_visibility = AsyncMock(return_value={"visibility": "public"})
    result = await repo.set_catalog_visibility("scenario", SimpleNamespace(visibility="public", expected_visibility="internal"))
    assert result == {"offering": {"visibility": "public"}}
    repo.catalog.set_offering_visibility.assert_awaited_once_with("workplace.printer", visibility="public", expected_visibility="internal", actor_id="admin", actor_role="admin")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unified", "partitioned"])
@pytest.mark.parametrize("blank_routes", [False, True])
async def test_create_service_uses_configured_common_queue_only_for_new_services(monkeypatch, mode, blank_routes):
    import config
    from tests.test_request_scenario_v3_processing import definition
    monkeypatch.setattr(config, "TICKET_QUEUE_MODE", mode)
    monkeypatch.setattr(config, "TICKET_TAKE_QUEUE_COMMON_CODE", "actual_common")
    raw = definition().model_dump(mode="json")
    raw.update(offering_full_code="")
    raw["process_binding"]["request_template_key"] = ""
    if blank_routes:
        raw["processing"]["routes"] = {}
        raw["processing"]["defaults"]["route"] = ""
    before = deepcopy(raw)
    common = SimpleNamespace(id=8, code="actual_common", name="Configured common queue", is_active=True)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[None, common]))
    repo = RequestScenarioRepo(session, SimpleNamespace(actor_id="admin", actor_role="admin"))
    repo._service_lock = AsyncMock(return_value={"metadata": {"studio_default_template": "printer"}})
    repo._category = AsyncMock()
    repo.catalog.list_offerings = AsyncMock(return_value=[])
    repo.catalog.upsert_offering_draft = AsyncMock()
    repo.create = AsyncMock(return_value={})
    monkeypatch.setattr("app.repos.helpdesk_policy_repo.HelpdeskPolicyRepo.resolve_effective_request_template", AsyncMock(return_value={"request_template": {"published_at": "now", "is_active": True, "ticket_type": "incident"}}))
    await repo.create_service(raw)
    created = repo.create.await_args.args[0]
    if mode == "unified" and blank_routes:
        assert created.processing.routes["default"].model_dump() == {"queue_code": "actual_common", "title": "Configured common queue"}
        assert created.processing.defaults.route == "default"
    else:
        assert {key: route.model_dump() for key, route in created.processing.routes.items()} == raw["processing"]["routes"]
        assert created.processing.defaults.route == raw["processing"]["defaults"]["route"]
    assert {key: profile.model_dump() for key, profile in created.processing.sla_profiles.items()} == raw["processing"]["sla_profiles"]
    assert created.processing.defaults.sla_profile == raw["processing"]["defaults"]["sla_profile"]
    assert repo.catalog.upsert_offering_draft.await_args.args[0].get("default_queue_id") == (8 if mode == "unified" else None)
    assert raw == before
    from app.db.request_scenario_models import RequestStudioDraft, RequestStudioScenario
    prior = RequestStudioScenario(id="existing", offering_full_code=created.offering_full_code)
    draft = RequestStudioDraft(definition=created.model_dump(mode="json"))
    repo.detail = AsyncMock(return_value=(prior, draft))
    stored_before = deepcopy(draft.definition)
    session.scalar = AsyncMock(side_effect=[prior, common])
    # A retried new-service request must compare with the server's normalized
    # queue default without rewriting an existing definition or creating twice.
    await repo.create_service(raw)
    assert repo.create.await_count == 1
    assert draft.definition == stored_before
    assert repo.catalog.upsert_offering_draft.await_count == 1
    changed = deepcopy(raw)
    changed["processing"]["defaults"]["sla_profile"] = "urgent"
    session.scalar = AsyncMock(side_effect=[prior, common])
    with pytest.raises(ScenarioAdminError, match="REVISION_CONFLICT"):
        await repo.create_service(changed)


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["internal", "restricted"])
async def test_hidden_offering_can_pass_publication_readiness_without_requester_access(monkeypatch, visibility):
    from tickets import request_scenario_publication as module
    from tickets.service_catalog_runtime import ServiceCatalogRuntimeResolver
    from tests.test_request_scenario_submission import definition
    monkeypatch.setattr(module.PolicyHealthService, "evaluate", lambda *_a, **_k: {"templates": [{"health_status": "ok"}]})
    simulate = AsyncMock(return_value=(None, {"routing": {"queue_id": 1}, "sla": {"resolution_min": 30}, "approval": {"required": False}, "priority": {"priority_class": "P2"}}))
    monkeypatch.setattr(module, "simulate_service_catalog_processing", simulate)
    source = {"effective_template": {"request_template": {"published_at": "now", "config": {}},
        "resolved_policies": {"closure": {"configured": True}, "visibility": {"configured": True}}},
        "policies": {}, "queues": [{"id": 1, "is_active": True}], "service": {"lifecycle_status": "published", "visibility": "public"},
        "offering": {"lifecycle_status": "published", "visibility": visibility, "request_template_key": "printer"}, "taxonomy": []}
    before = deepcopy(source)
    row = SimpleNamespace(id="scenario", archived=False, category_id=None, offering_full_code="workplace.printer")
    draft = SimpleNamespace(definition=definition().model_dump(mode="json"))
    result = await module.ScenarioPublicationService(SimpleNamespace(session=None))._assess(row, draft, source)
    assert result["readiness"]["can_publish"], result
    assert simulate.await_args.kwargs["allow_hidden_offering"] is True
    assert source == before
    assert not ServiceCatalogRuntimeResolver(None)._is_visible(source["service"], source["offering"], actor_role="requester")


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["internal", "restricted"])
async def test_catalog_publication_retains_hidden_visibility(visibility):
    row = HelpdeskServiceOffering(full_code="workplace.printer", service_id="parent", visibility=visibility, lifecycle_status="draft")
    session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(code="workplace")), flush=AsyncMock())
    repo = ServiceCatalogRepo(session)
    repo.get_offering_row_by_full_code = AsyncMock(return_value=row)
    repo.append_audit = AsyncMock()
    result = await repo.publish_offering("workplace.printer", actor_id="admin", actor_role="admin")
    assert result["visibility"] == visibility and result["lifecycle_status"] == "published"


@pytest.mark.asyncio
async def test_admin_hidden_preview_preserves_parent_and_lifecycle_gates(monkeypatch):
    from tickets import service_catalog_preview as module
    resolver = SimpleNamespace(resolve_selection=AsyncMock(return_value=SimpleNamespace(service={"lifecycle_status": "published", "visibility": "restricted"}, offering={"lifecycle_status": "published", "visibility": "internal"})))
    monkeypatch.setattr(module, "ServiceCatalogRuntimeResolver", lambda _: resolver)
    with pytest.raises(module.ServiceCatalogPreviewError):
        await module.simulate_service_catalog_processing(None, {}, allow_hidden_offering=True)
    assert resolver.resolve_selection.await_args.kwargs["actor_role"] == "admin"
