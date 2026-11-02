"""Resolution classification is optional metadata, including old policies."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_phase1_completion_no_db import completion, resolve
from tickets import workflow_service as workflow
from tickets.closure_policy import build_closure_requirements
from tickets.resolution_policy_service import TicketResolutionPolicyService
from tickets.workflow_profiles import WorkflowTransitionGate, get_workflow_profile
from tickets.workflow_profiles import normalize_workflow_profile
from support.operator_command_center import _closure_state
from web_api.settings_handlers import _build_request_template_items
from tickets.form_process_preview import _closure_preview

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("stored", [None, "old-unlisted-value"])
async def test_old_required_code_policy_does_not_block_code_free_completion(completion, stored):
    policy = completion.ticket.custom_fields["request_template"]["closure_policy"]
    policy["before_resolved"]["require_resolution_code"] = True
    policy["allowed_resolution_codes"] = ["fixed_remote"]
    completion.ticket.resolution_code = stored
    before = deepcopy(completion.ticket.custom_fields)
    requirements = await build_closure_requirements(completion.session, completion.ticket)
    assert not any("code" in requirement["key"] for requirement in requirements)
    await resolve(completion)
    assert completion.ticket.status == "closed"
    assert completion.ticket.resolution_code == stored
    assert completion.ticket.custom_fields["request_template"] == before["request_template"]


async def test_explicit_invalid_classification_still_rejected(completion):
    completion.ticket.custom_fields["request_template"]["closure_policy"]["allowed_resolution_codes"] = ["fixed_remote"]
    with pytest.raises(ValueError, match="allowed_resolution_codes"):
        await resolve(completion, resolution_code="invalid")
    assert completion.ticket.status == "in_progress"


async def test_legacy_transition_code_field_does_not_block_other_gate_requirements(completion, monkeypatch):
    profile = replace(get_workflow_profile("incident"), transition_gates={
        "in_progress": {"resolved": WorkflowTransitionGate(to_status="resolved",
            required_fields=("resolution_code", "requester_resolution_summary"))},
        "resolved": {"closed": WorkflowTransitionGate(to_status="closed", required_fields=("resolution_code",))},
    })
    monkeypatch.setattr(workflow, "load_ticket_workflow_profile", AsyncMock(return_value=profile))
    await resolve(completion)
    assert completion.ticket.status == "closed"
    assert not hasattr(completion.ticket, "resolution_code")


@pytest.mark.parametrize("empty_code", [None, "", "   "])
def test_legacy_quality_enforcement_keeps_root_cause_but_code_optional(empty_code):
    quality = TicketResolutionPolicyService(mode="enforce")
    assert quality.validate("resolved", empty_code, "Cause established", "P1", ["fixed_remote"]) == (True, [])
    ok, errors = quality.validate("resolved", None, None, "P1", ["fixed_remote"])
    assert ok is False and errors == ["root_cause is required for priority P1"]
    ok, errors = quality.validate("resolved", "invalid", "Cause", "P1", ["fixed_remote"])
    assert ok is False and "not in active resolution codes" in errors[0]


def test_advanced_closure_attention_does_not_request_retired_classification():
    assert _closure_state({"status": "in_progress", "requester_resolution_summary": "Service restored"}, None) is None


def test_effective_workflow_metadata_preserves_real_resolution_requirements():
    profile = normalize_workflow_profile({"ticket_type": "legacy", "required_resolve_fields": ["resolution_code", "public_summary", "root_cause"]})
    assert profile.required_resolve_fields == ("public_summary", "root_cause")
    gate = WorkflowTransitionGate(to_status="resolved", required_fields=("resolution_code", "root_cause"))
    assert gate.to_dict()["required_fields"] == ["root_cause"]
    assert gate.required_fields == ("resolution_code", "root_cause")


def test_effective_settings_do_not_advertise_old_code_prerequisite():
    pack = {"forms": [{"key": "legacy", "closure_policy": {"before_resolved": {"require_resolution_code": True}}}]}
    before = deepcopy(pack)
    items = _build_request_template_items(pack)
    assert items[0].closure["requires_resolution_code"] is False
    assert pack == before
    preview = _closure_preview(pack["forms"][0], "P2")
    assert preview["requires_resolution_code"] is False


async def test_missing_public_result_still_blocks_legacy_code_policy(completion):
    completion.ticket.custom_fields["request_template"]["closure_policy"]["require_resolution_code"] = True
    with pytest.raises(ValueError, match="requester_resolution_summary"):
        await resolve(completion, summary=None)
