"""P9 outcomes are admin-only simulation; requester runtime never dispatches."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from tests.test_request_scenario_runtime import pilot
from tickets.request_scenario_runtime import ScenarioRuntime
from web_api.dto.request_scenario import ScenarioAnswerRequest, ScenarioDefinition
from web_api.dto.request_scenario_admin import SimulationInput

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize("status", ["unavailable", "denied", "timeout", "capability_absent"])
def test_only_typed_failure_outcomes_can_be_simulated_without_dispatch(status):
    definition = ScenarioDefinition.model_validate(pilot())
    runtime = ScenarioRuntime(definition, diagnostic_outcomes={"diagnostic": status})
    state = runtime.initial_state()
    for block, values, result in [("questions", {"summary": "No print", "impact": "me"}, None),
            ("instruction", {}, "acknowledged"), ("helped", {}, "no")]:
        state = runtime.advance(state, ScenarioAnswerRequest(expected_block_id=block, revision=state.revision, answers=values, current_result=result))
    assert state.current_block_id == "review"
    assert state.results["diagnostic"]["status"] == status
    assert state.results["diagnostic"]["simulated"] is True
    assert state.results["diagnostic"]["operation_created"] is False


def test_requester_cannot_supply_simulated_diagnostic_success_or_consent():
    for raw in ({"diagnostic_outcomes": {"diagnostic": "denied"}}, {"consent": True}, {"current_result": "success"}):
        with pytest.raises(ValidationError):
            ScenarioAnswerRequest.model_validate({"expected_block_id": "diagnostic", "revision": 1, **raw})
    with pytest.raises(ValidationError):
        SimulationInput.model_validate({"revision": 1, "diagnostic_outcomes": {"diagnostic": "success"}})
    assert SimulationInput.model_validate({"revision": 1, "diagnostic_outcomes": {"diagnostic": "timeout"}}).diagnostic_outcomes == {"diagnostic": "timeout"}


def test_unapproved_capability_and_file_fields_are_rejected_before_runtime():
    from tickets.request_scenario_validation import ScenarioValidationError
    definition = pilot()
    definition["blocks"][3]["capability"] = "shell.execute"
    with pytest.raises(ScenarioValidationError):
        ScenarioRuntime(ScenarioDefinition.model_validate(definition))
    definition = deepcopy(pilot())
    definition["blocks"][0]["fields"][0]["type"] = "file"
    with pytest.raises(ValidationError):
        ScenarioDefinition.model_validate(definition)


def test_readiness_covers_all_failure_branches_and_requester_keeps_unavailable():
    from tickets.request_scenario_readiness import submission_variants
    raw = pilot()
    raw["blocks"][3]["transitions"] = [{"to": "submit", "when": {"source": "current_result", "op": "eq", "value": "timeout"}}, {"to": "review"}]
    definition = ScenarioDefinition.model_validate(raw)
    states = submission_variants(definition)
    assert {state.results["diagnostic"]["status"] for state in states if "diagnostic" in state.results} == {"unavailable", "denied", "timeout", "capability_absent"}
    runtime = ScenarioRuntime(definition)
    state = runtime.initial_state()
    for block, values, result in [("questions", {"summary": "No print", "impact": "me"}, None),
            ("instruction", {}, "acknowledged"), ("helped", {}, "no")]:
        state = runtime.advance(state, ScenarioAnswerRequest(expected_block_id=block, revision=state.revision, answers=values, current_result=result))
    assert state.current_block_id == "review"
    assert state.results["diagnostic"] == {"status": "unavailable", "reason": "pre_ticket_contract_unavailable"}


@pytest.mark.asyncio
async def test_imported_file_field_has_explicit_publication_blocker():
    from types import SimpleNamespace
    from tickets.request_scenario_publication import ScenarioPublicationService
    raw = pilot()
    raw["blocks"][0]["fields"][0]["type"] = "file"
    source = {"effective_template": {}, "policies": {}, "queues": [], "taxonomy": [], "service": {}, "offering": {}}
    result = await ScenarioPublicationService(SimpleNamespace(session=None))._assess(
        SimpleNamespace(archived=False, category_id=None), SimpleNamespace(definition=raw), source)
    assert result["readiness"]["can_publish"] is False
    assert "attachments_unsupported" in {issue["code"] for issue in result["readiness"]["issues"]}
