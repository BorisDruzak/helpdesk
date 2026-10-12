"""Scenario policy references use the existing resolver, never requester input."""
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
from web_api.dto.request_scenario import ProcessBinding

pytestmark = pytest.mark.no_db


def test_typed_binding_only_accepts_existing_processing_policy_kinds():
    value = ProcessBinding.model_validate({"request_template_key": "printer", "policy_refs": {"routing": "printer_route", "sla": "printer_sla"}})
    assert value.policy_refs == {"routing": "printer_route", "sla": "printer_sla"}
    with pytest.raises(ValidationError):
        ProcessBinding.model_validate({"request_template_key": "printer", "policy_refs": {"shell": "execute"}})


@pytest.mark.asyncio
async def test_published_reference_replaces_inherited_config_using_canonical_resolver(monkeypatch):
    from tickets.request_scenario_processing import apply_scenario_policy_refs
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    resolver = AsyncMock(return_value={"config": {"fallback": {"queue_id": 7}}, "policy": {"is_active": True, "published_at": "2026-10-11", "code": "printer_route", "version": "1"}, "sources": [{"code": "printer_route"}]})
    monkeypatch.setattr(HelpdeskPolicyRepo, "resolve_policy_ref", resolver)
    original = {"template_context": {"routing_policy": {"fallback": {"queue_id": 3}}}, "submitted_values": {"summary": "No print"}}
    result = await apply_scenario_policy_refs(None, original, {"routing": "printer_route"})
    assert result["template_context"]["routing_policy"]["fallback"]["queue_id"] == 7
    assert result["template_context"]["policy_refs"]["routing"] == {"code": "printer_route", "version": "1"}
    assert original["template_context"]["routing_policy"]["fallback"]["queue_id"] == 3
    assert result["submitted_values"] == original["submitted_values"]
    resolver.assert_awaited_once_with(kind="routing", code="printer_route", source="request_scenario.policy_refs.routing")


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [{}, {"is_active": True, "published_at": None}])
async def test_missing_or_unpublished_policy_fails_closed(monkeypatch, policy):
    from tickets.request_scenario_processing import apply_scenario_policy_refs
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    monkeypatch.setattr(HelpdeskPolicyRepo, "resolve_policy_ref", AsyncMock(return_value={"config": {"required": False}, "policy": policy}))
    with pytest.raises(ValueError):
        await apply_scenario_policy_refs(None, {"template_context": {}}, {"closure": "missing"})


@pytest.mark.asyncio
async def test_selected_sla_cannot_reference_inactive_legacy_row(monkeypatch):
    from types import SimpleNamespace
    from tickets.request_scenario_processing import apply_scenario_policy_refs
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    monkeypatch.setattr(HelpdeskPolicyRepo, "resolve_policy_ref", AsyncMock(return_value={"config": {"sla_policy_id": 7}, "policy": {"is_active": True, "published_at": "2026-10-11", "version": "1"}}))
    session = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(is_active=False)))
    with pytest.raises(ValueError):
        await apply_scenario_policy_refs(session, {"template_context": {}}, {"sla": "invalid"})
