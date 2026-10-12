"""Explicit instruction escape reuses the graph and canonical submit boundary."""
from copy import deepcopy

import pytest

from tests.test_request_scenario_runtime import pilot, _modules, _answer
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def escape_graph():
    raw = pilot()
    raw["blocks"][1]["transitions"].insert(0, {
        "to": "review", "when": {"op": "eq", "source": "current_result", "value": "request_ticket"},
    })
    return raw


def instruction_state(raw):
    module = _modules()[1]
    runtime = module.ScenarioRuntime(ScenarioDefinition.model_validate(raw))
    state = runtime.initial_state()
    state = runtime.advance(state, _answer(state, {"summary": "Printing stopped", "impact": "me"}))
    return module, runtime, state


def test_explicit_escape_reaches_review_without_claiming_instruction_completed():
    module, runtime, state = instruction_state(escape_graph())
    before = deepcopy(state)
    assert runtime.can_request_ticket(state)
    result = runtime.advance(state, _answer(state, result="request_ticket"))
    assert result.current_block_id == "review" and result.state == "active"
    assert result.answers == state.answers
    assert result.results == {"instruction": "request_ticket"}
    assert state == before


@pytest.mark.parametrize("condition", [None, {"op": "neq", "source": "current_result", "value": "acknowledged"}, {"op": "exists", "source": "current_result"}])
def test_fallback_or_non_explicit_condition_cannot_authorize_escape(condition):
    raw = pilot()
    raw["blocks"][1]["transitions"] = [{"to": "review", **({"when": condition} if condition else {})}]
    if condition:
        raw["blocks"][1]["transitions"].append({"to": "helped"})
    else:
        # Keep other pilot blocks reachable through a second question outcome.
        raw["blocks"][0]["transitions"].insert(0, {"to": "helped", "when": {"op": "eq", "source": "answer", "field": "impact", "value": "team"}})
    module, runtime, state = instruction_state(raw)
    assert not runtime.can_request_ticket(state)
    with pytest.raises(module.ScenarioInputError):
        runtime.advance(state, _answer(state, result="request_ticket"))


def test_higher_priority_actual_transition_does_not_authorize_escape():
    raw = escape_graph()
    raw["blocks"][1]["transitions"][0]["priority"] = 2
    raw["blocks"][1]["transitions"].insert(0, {"to": "helped", "priority": 1, "when": {"op": "eq", "source": "answer", "field": "impact", "value": "me"}})
    module, runtime, state = instruction_state(raw)
    assert not runtime.can_request_ticket(state)
    with pytest.raises(module.ScenarioInputError):
        runtime.advance(state, _answer(state, result="request_ticket"))


def test_escape_target_must_be_review_and_projection_contains_only_permission():
    raw = escape_graph()
    raw["blocks"][1]["transitions"][0]["to"] = "submit"
    issues = _modules()[0].validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(issue.code == "invalid_ticket_request_target" for issue in issues)
    _, runtime, state = instruction_state(escape_graph())
    from tickets.request_scenario_session import project_step
    projection = project_step(runtime.definition, state)
    assert projection["block"]["can_request_ticket"] is True
    assert "transitions" not in projection["block"]


def test_readiness_enumerates_escape_as_well_as_acknowledged_instruction():
    from tickets.request_scenario_readiness import submission_variants
    states = submission_variants(ScenarioDefinition.model_validate(escape_graph()))
    assert any(state.results.get("instruction") == "request_ticket" and state.current_block_id == "submit" for state in states)
    assert any(state.results.get("instruction") == "acknowledged" for state in states)


def test_escape_does_not_skip_initial_required_facts():
    module = _modules()[1]
    runtime = module.ScenarioRuntime(ScenarioDefinition.model_validate(escape_graph()))
    initial = runtime.initial_state()
    with pytest.raises(module.ScenarioInputError):
        runtime.advance(initial, _answer(initial, result="request_ticket"))
    with pytest.raises(module.ScenarioInputError):
        runtime.advance(initial, _answer(initial, {"impact": "me"}))
