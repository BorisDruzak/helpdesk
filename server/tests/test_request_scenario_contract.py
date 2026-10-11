"""Guided Studio v2 domain contract; initially RED at the P0 baseline.

The new DTO is additive. Legacy Studio payloads retain their own contract.
"""
from copy import deepcopy
from importlib import import_module

import pytest
from pydantic import ValidationError
from aiohttp.test_utils import make_mocked_request
from unittest.mock import AsyncMock

from auth.context import AuthContext, AuthType

from web_api.dto.request_studio import RequestStudioDraftRequest

pytestmark = pytest.mark.no_db


def _definition():
    return {
        "schema_version": 1,
        "scenario_key": "printer_no_print",
        "service_code": "workplace",
        "offering_full_code": "workplace.printer_issue",
        "title": "Не печатает",
        "entry_block_id": "questions",
        "blocks": [
            {
                "id": "questions", "kind": "form_page", "title": "Проблема",
                "fields": [{
                    "key": "summary", "type": "textarea", "label": "Что происходит?",
                    "required": True,
                    "process_mapping": {"roles": ["display_only", "reporting_dimension"]},
                }],
                "transitions": [{"to": "finish"}],
            },
            {"id": "finish", "kind": "finish", "title": "Решено без обращения"},
        ],
        "process_binding": {"request_template_key": "printer"},
    }


def _dto():
    return import_module("web_api.dto.request_scenario")


def test_scenario_roundtrip_preserves_stable_ids_and_multiple_roles():
    definition = _dto().ScenarioDefinition.model_validate(_definition())
    exported = definition.model_dump(mode="json")
    restored = _dto().ScenarioDefinition.model_validate(exported)
    assert restored.scenario_key == "printer_no_print"
    assert restored.blocks[0].id == "questions"
    assert restored.blocks[0].fields[0].process_mapping.roles == ["display_only", "reporting_dimension"]


@pytest.mark.parametrize("kind", ["shell", "javascript", "endpoint_dispatch"])
def test_scenario_rejects_unknown_executable_blocks(kind):
    raw = deepcopy(_definition())
    raw["blocks"][0]["kind"] = kind
    with pytest.raises(ValidationError):
        _dto().ScenarioDefinition.model_validate(raw)


def test_scenario_rejects_expression_instead_of_typed_condition():
    raw = deepcopy(_definition())
    raw["blocks"][0]["transitions"][0]["when"] = {"op": "eval", "expression": "True"}
    with pytest.raises(ValidationError):
        _dto().ScenarioDefinition.model_validate(raw)


@pytest.mark.parametrize("authority,value", [
    ("actor_id", "another_user"), ("actor_role", "admin"), ("queue_id", 1),
    ("priority", "P1"), ("sla_policy_code", "standard"),
])
def test_session_answer_cannot_supply_authority_or_policy(authority, value):
    dto = _dto().ScenarioAnswerRequest
    raw = {"expected_block_id": "questions", "revision": 1, "answers": {"summary": "Не печатает"}}
    assert dto.model_validate(raw).answers == raw["answers"]
    raw[authority] = value
    with pytest.raises(ValidationError) as caught:
        dto.model_validate(raw)
    assert any(error["type"] == "extra_forbidden" and error["loc"] == (authority,) for error in caught.value.errors())


@pytest.mark.asyncio
@pytest.mark.parametrize("role,status", [(None, 401), ("auditor", 403), ("support", 403)])
async def test_requester_session_read_requires_requester_auth_before_db(role, status, monkeypatch):
    # Real authorization wrapper; only the audit sink is replaced to avoid DB I/O.
    monkeypatch.setattr("auth.middleware._write_web_auth_audit", AsyncMock())
    request = make_mocked_request("GET", "/api/web/requester/request-scenarios/sessions/test-session")
    if role is not None:
        request["auth_context"] = AuthContext(actor_id="test-reader", actor_role=role, auth_type=AuthType.UI_TOKEN)
    handlers = import_module("web_api.request_scenario_handlers")
    response = await handlers.handle_web_requester_scenario_session(request)
    assert response.status == status


def _legacy_payload():
    return {
        "form": {"key": "printer", "request_kind": "printer", "title": "Принтер", "fields": []},
        "offering": {"service_code": "workplace", "code": "printer_issue", "public_title": "Принтер", "request_template_key": "printer"},
    }


def test_legacy_studio_payload_roundtrip_remains_compatible():
    dto = RequestStudioDraftRequest.model_validate(_legacy_payload())
    assert RequestStudioDraftRequest.model_validate(dto.model_dump()) == dto
    assert dto.offering.code == "printer_issue"


def test_new_scenario_is_not_silently_accepted_by_legacy_studio():
    raw = _legacy_payload()
    raw["scenario"] = _definition()
    with pytest.raises(ValidationError):
        RequestStudioDraftRequest.model_validate(raw)
