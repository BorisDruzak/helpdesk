"""Pre-ticket files remain separate from scalar answers and ticket artifacts."""
from types import SimpleNamespace
import uuid

import pytest
from pydantic import ValidationError

from web_api.dto.request_scenario import ScenarioField, InstructionContent, ScenarioAnswerRequest

pytestmark = pytest.mark.no_db


def attachment():
    identifier = str(uuid.uuid4())
    return {"asset_id": identifier, "name": "manual.pdf", "mime_type": "application/pdf",
            "size_bytes": 12, "url": f"/api/web/request-scenario-assets/{identifier}/download"}


def test_author_material_roundtrip_and_bounded_refs():
    ref = attachment()
    field = ScenarioField(key="details", type="textarea", label="Details", help_attachments=[ref])
    assert field.model_dump()["help_attachments"] == [ref]
    assert InstructionContent(body="Read", attachments=[ref]).model_dump()["attachments"] == [ref]
    with pytest.raises(ValidationError):
        ScenarioField(key="details", type="text", label="Details", help_attachments=[ref] * 11)
    with pytest.raises(ValidationError):
        ScenarioAnswerRequest(expected_block_id="page", revision=1, answers={"details": [ref]})


def test_material_ref_cannot_redirect_authenticated_download():
    ref = attachment()
    ref["url"] = "https://evil.invalid/download"
    with pytest.raises(ValidationError):
        InstructionContent(body="Read", attachments=[ref])


def test_copy_provenance_is_explicit_request_metadata_not_scenario_definition():
    from web_api.dto.request_scenario_admin import ServiceScenarioCreate
    identifier = str(uuid.uuid4())
    payload = ServiceScenarioCreate(definition={}, copy_source_id=identifier)
    assert payload.copy_source_id == identifier and payload.definition == {}
    with pytest.raises(ValidationError):
        ServiceScenarioCreate(definition={}, copy_source_id="invalid")


@pytest.mark.asyncio
async def test_malformed_copy_material_is_validated_before_reference_lookup(monkeypatch):
    from unittest.mock import AsyncMock
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from tests.test_request_scenario_contract import _definition
    raw = _definition()
    raw["offering_full_code"] = ""
    raw["process_binding"]["request_template_key"] = ""
    raw["blocks"][0]["fields"][0]["help_attachments"] = [{}]
    session = AsyncMock()
    session.scalar.return_value = None
    repo = RequestScenarioRepo(session, SimpleNamespace(actor_id="admin", actor_role="admin"))
    repo._service_lock = AsyncMock(return_value={"metadata": {"studio_default_template": "printer"}})
    repo.catalog.list_offerings = AsyncMock(return_value=[])
    monkeypatch.setattr("app.repos.helpdesk_policy_repo.HelpdeskPolicyRepo.resolve_effective_request_template",
        AsyncMock(return_value={"request_template": {"published_at": "published", "is_active": True, "ticket_type": "incident"}}))
    lookup = AsyncMock(side_effect=AssertionError("Unvalidated file metadata reached source lookup"))
    monkeypatch.setattr("tickets.request_scenario_assets.copy_material_sources", lookup)
    with pytest.raises(ValidationError):
        await repo.create_service(raw, copy_source_id=str(uuid.uuid4()))
    lookup.assert_not_awaited()


def test_filename_removes_paths_and_header_controls():
    from tickets.request_scenario_assets import safe_asset_name
    assert safe_asset_name("../../folder\\report\r\n.pdf") == "report.pdf"
    assert safe_asset_name(".") == "file"


def test_retained_attachment_fields_exclude_hidden_and_discarded_pages():
    from tickets.request_scenario_assets import retained_attachment_fields
    from web_api.dto.request_scenario import FormPage
    page = FormPage(id="page", kind="form_page", title="Page", fields=[
        {"key": "details", "type": "text", "label": "Details"},
        {"key": "secret", "type": "textarea", "label": "Hidden", "visible_when":
         {"op": "eq", "source": "answer", "field": "details", "value": "show"}},
        {"key": "number", "type": "number", "label": "Number"},
    ])
    other = FormPage(id="other", kind="form_page", title="Other", fields=[{"key": "discarded", "type": "text", "label": "Discarded"}])
    runtime = SimpleNamespace(blocks={"page": page, "other": other})
    state = SimpleNamespace(history=["page"], current_block_id="submit", answers={"details": "hide"})
    assert retained_attachment_fields(runtime, state) == {("page", "details")}


@pytest.mark.asyncio
@pytest.mark.parametrize("handler,role,status", [
    ("handle_scenario_material_upload", "user", 403),
    ("handle_scenario_material_upload", "support", 403),
    ("handle_scenario_answer_upload", "support", 403),
    ("handle_scenario_answer_remove", "auditor", 403),
    ("handle_scenario_asset_download", "support", 403),
    ("handle_scenario_asset_download", None, 401),
])
async def test_asset_auth_rejects_before_database(handler, role, status, monkeypatch):
    from aiohttp.test_utils import make_mocked_request
    from unittest.mock import AsyncMock
    from auth.context import AuthContext, AuthType
    from web_api import request_scenario_asset_handlers as handlers
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())
    request = make_mocked_request("GET", "/api/web/request-scenario-assets/test/download")
    if role:
        request["auth_context"] = AuthContext(actor_id="test", actor_role=role, auth_type=AuthType.UI_TOKEN)
    assert (await getattr(handlers, handler)(request)).status == status
