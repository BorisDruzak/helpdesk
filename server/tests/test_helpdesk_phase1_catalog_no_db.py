"""Phase-one content executes canonical branches, hidden fields and SLA."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.helpdesk_phase1_catalog import (
    CLOSURE_CODE, CLOSURE_VERSION, build_definitions, build_closure_request,
    fingerprint, require_target,
)
from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
from tickets.request_scenario_submission import build_scenario_submission
from web_api.dto.request_scenario import ScenarioAnswerRequest, ScenarioDefinition

pytestmark = pytest.mark.no_db


def base_definition():
    return json.loads((Path(__file__).parent / "fixtures/phase1_other_base.json").read_text(encoding="utf-8"))


def graph(raw):
    return ScenarioDefinition.model_validate({**raw, "offering_full_code": raw["service_code"] + ".test",
        "process_binding": {**raw["process_binding"], "request_template_key": "general_request"}})


def advance(runtime, state, answers):
    return runtime.advance(state, ScenarioAnswerRequest(expected_block_id=state.current_block_id,
        revision=state.revision, answers=answers))


def test_exact_four_additive_maps_reuse_authoritative_questions_and_sla():
    base = base_definition()
    original = deepcopy(base)
    definitions = build_definitions(base)
    assert base == original
    assert {d["scenario_key"] for d in definitions} == {
        "phase1_password_recovery", "phase1_new_account", "phase1_equipment_replacement", "phase1_business_system"}
    source = {b["id"]: b for b in base["blocks"]}
    for raw in definitions:
        blocks = {b["id"]: b for b in raw["blocks"]}
        assert blocks["q_scope"] == source["q_scope"]
        assert blocks["d_sla"] == source["d_sla"]
        assert blocks["q_urgency"]["fields"] == source["q_urgency"]["fields"]
        assert raw["processing"]["sla_profiles"] == base["processing"]["sla_profiles"]
        assert raw["process_binding"]["policy_refs"] == base["process_binding"]["policy_refs"]
        assert raw["offering_full_code"] == ""
        assert raw["process_binding"]["request_template_key"] == ""
        ScenarioRuntime(graph(raw))


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("scope,continuity,minutes", [
    ("one", "can_work", 300), ("department", "can_work", 300),
    ("one", "degraded", 180), ("department", "degraded", 180),
    ("one", "blocked", 180), ("department", "blocked", 120),
])
def test_every_new_map_executes_preserved_sla_branches(index, scope, continuity, minutes):
    definition = graph(build_definitions(base_definition())[index])
    runtime = ScenarioRuntime(definition)
    state = advance(runtime, runtime.initial_state(), {"subject_kind": "known", "request_details": "Нужна помощь"})
    state = advance(runtime, state, {"impact_scope": scope})
    state = advance(runtime, state, {"work_continuity": continuity})
    assert state.current_block_id == "submit"
    payload, snapshot = build_scenario_submission(definition, state, session_id="test", version_id="test")
    assert snapshot["map_processing"]["sla_profile"]["resolution_minutes"] == minutes
    assert snapshot["map_processing"]["route"]["key"] == "first_line"
    assert snapshot["processing_facts"]["impact"] == ("department" if scope == "department" else "single_user")
    assert snapshot["processing_facts"]["urgency"] == continuity
    assert payload["form_payload"]["request_details"] == "Нужна помощь"


@pytest.mark.parametrize("index", range(4))
def test_conditional_required_subject_and_backtracking_drop_hidden_answer(index):
    definition = graph(build_definitions(base_definition())[index])
    runtime = ScenarioRuntime(definition)
    initial = runtime.initial_state()
    with pytest.raises(ScenarioInputError) as invalid:
        advance(runtime, initial, {"subject_kind": "other", "request_details": "Помогите"})
    assert "subject_other" in invalid.value.errors
    state = advance(runtime, initial, {"subject_kind": "other", "subject_other": "Название системы",
        "request_details": "Помогите"})
    assert state.answers["subject_other"] == "Название системы"
    state = runtime.back(state, "request", expected_revision=state.revision)
    state = advance(runtime, state, {"subject_kind": "known", "subject_other": "Скрытое устаревшее значение",
        "request_details": "Помогите"})
    assert "subject_other" not in state.answers
    state = advance(runtime, state, {"impact_scope": "department"})
    state = advance(runtime, state, {"work_continuity": "blocked"})
    snapshot = build_scenario_submission(definition, state, session_id="test", version_id="test")[1]
    assert "subject_other" not in snapshot["answers"]
    assert "subject_other" not in {field["key"] for field in snapshot["form_schema"]["fields"]}
    state = runtime.back(state, "q_scope", expected_revision=state.revision)
    assert "work_continuity" not in state.answers
    state = advance(runtime, state, {"impact_scope": "one"})
    state = advance(runtime, state, {"work_continuity": "can_work"})
    assert build_scenario_submission(definition, state, session_id="test", version_id="test")[1]["map_processing"]["sla_profile"]["resolution_minutes"] == 300


def test_closure_request_is_exact_version_preserves_other_fields_and_public_result():
    old = {"code": CLOSURE_CODE, "version": "1.0.1", "title": "Обычное закрытие", "scope_level": "system",
        "config": {"require_public_summary": True, "require_resolution_code": True, "evidence": {"keep": True}}}
    original = deepcopy(old)
    request = build_closure_request(old)
    assert old == original
    assert request["requested_version"] == CLOSURE_VERSION == "1.0.2"
    assert request["config"] == {"require_public_summary": True, "require_resolution_code": False,
        "requester_confirmation": {"required": False}, "evidence": {"keep": True}}
    with pytest.raises(ValueError):
        build_closure_request({**old, "code": "unrelated_special_policy"})


def test_guard_rejects_production_and_shared_tests_and_fingerprint_is_content_bound():
    require_target("helpdesk_staging_db")
    require_target("pc_support_test_unique", isolated_test=True)
    for database in ("helpdesk", "postgres", "pc_support_test", "endpoint_platform"):
        with pytest.raises(ValueError):
            require_target(database)
    with pytest.raises(ValueError):
        require_target("pc_support_test", isolated_test=True)
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})
