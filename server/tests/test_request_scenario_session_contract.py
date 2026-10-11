"""Requester projection and strict session inputs without database I/O."""
from importlib import import_module

import pytest
from pydantic import ValidationError

from tickets.request_scenario_runtime import RuntimeState
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def _definition():
    return {
        "scenario_key": "printer", "service_code": "workplace",
        "offering_full_code": "workplace.printer", "title": "Printer",
        "entry_block_id": "questions", "process_binding": {"request_template_key": "printer"},
        "blocks": [
            {"id": "questions", "kind": "form_page", "title": "Questions",
             "fields": [{"key": "summary", "type": "text", "label": "Summary", "required": True}],
             "transitions": [{"to": "finish"}]},
            {"id": "finish", "kind": "finish", "title": "Finished"},
        ],
    }


def test_current_step_hides_graph_process_and_mapping_authority():
    project = import_module("tickets.request_scenario_session").project_step
    definition = ScenarioDefinition.model_validate(_definition())
    state = RuntimeState("questions", answers={"summary": "Printer"})
    result = project(definition, state)
    assert result["block"]["fields"][0]["value"] == "Printer"
    assert result["block"]["fields"][0]["required"] is True
    assert result["back_targets"] == []
    for secret in ("transitions", "process_mapping", "process_binding", "blocks", "visible_when"):
        assert secret not in str(result)


@pytest.mark.parametrize("key", ["actor_id", "version_id", "priority", "expires_at"])
def test_start_cannot_supply_owner_version_policy_or_ttl(key):
    dto = import_module("web_api.dto.request_scenario_session").SessionStart
    with pytest.raises(ValidationError):
        dto.model_validate({"offering_full_code": "workplace.printer", key: "forged"})


def test_back_targets_only_include_visited_interactive_steps():
    project = import_module("tickets.request_scenario_session").project_step
    definition = ScenarioDefinition.model_validate(_definition())
    result = project(definition, RuntimeState("finish", history=["questions"], state="completed_self_service"))
    assert result["back_targets"] == []  # Terminal self-service cannot be reopened.


def test_page_preview_uses_server_conditions_without_advancing_or_persisting():
    from tickets.request_scenario_runtime import ScenarioRuntime
    from web_api.dto.request_scenario import ScenarioAnswerRequest
    raw = _definition()
    raw["blocks"][1] = {"id": "finish", "kind": "submit_ticket", "title": "Submit"}
    raw["blocks"][0]["fields"].append({
        "key": "details", "type": "text", "label": "Details", "required": True,
        "visible_when": {"op": "eq", "source": "answer", "field": "summary", "value": "other"},
    })
    runtime = ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = runtime.initial_state()
    preview = runtime.preview_answers(state, ScenarioAnswerRequest(
        expected_block_id="questions", revision=1, answers={"summary": "other"},
    ))
    projected = import_module("tickets.request_scenario_session").project_step(runtime.definition, preview)
    assert [field["key"] for field in projected["block"]["fields"]] == ["summary", "details"]
    assert state.answers == {} and state.revision == preview.revision == 1


def test_review_projects_only_visited_retained_answers_with_human_labels():
    project = import_module("tickets.request_scenario_session").project_step
    raw = _definition()
    raw["blocks"].append({"id": "review", "kind": "review", "title": "Review"})
    result = project(ScenarioDefinition.model_validate(raw), RuntimeState(
        "review", history=["questions"], answers={"summary": "Printer", "unvisited": "secret"},
    ))
    assert result["block"]["answers"] == [{"key": "summary", "label": "Summary", "type": "text", "value": "Printer", "display_value": "Printer"}]


def test_review_uses_choice_labels_instead_of_machine_keys():
    from tickets.request_scenario_session import project_step
    raw = _definition()
    raw["blocks"][0]["fields"] = [{"key": "summary", "type": "select", "label": "Impact", "options": [{"value": "option_internal", "label": "Только у меня"}]}]
    raw["blocks"].append({"id": "review", "kind": "review", "title": "Review"})
    result = project_step(ScenarioDefinition.model_validate(raw), RuntimeState("review", history=["questions"], answers={"summary": "option_internal"}))
    assert result["block"]["answers"][0]["display_value"] == "Только у меня"
