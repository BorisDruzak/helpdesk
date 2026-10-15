"""P2 canonical evaluator/validator safety and deterministic branch contract."""
from copy import deepcopy
from importlib import import_module
import random

import pytest
from pydantic import TypeAdapter

from web_api.dto.request_scenario import Condition, ScenarioAnswerRequest, ScenarioDefinition

pytestmark = pytest.mark.no_db


def _modules():
    return import_module("tickets.request_scenario_validation"), import_module("tickets.request_scenario_runtime")


@pytest.mark.parametrize("schema_version", [1, 2])
@pytest.mark.parametrize("field_type", ["radio", "select"])
@pytest.mark.parametrize("answer,expected", [("mail", "mail_help"), ("vpn", "vpn_help"), ("other", "review")])
def test_choice_answer_selects_the_matching_instruction_or_fallback(schema_version, field_type, answer, expected):
    raw = pilot()
    raw["schema_version"] = schema_version
    raw["entry_points"] = [{"key": "main", "title": "Помощь", "target_block_id": "questions"}]
    page = raw["blocks"][0]
    page["fields"] = [{"key": "issue", "type": field_type, "label": "Что не работает?", "required": True,
                       "options": [{"value": value, "label": value} for value in ("mail", "vpn", "other")]}]
    page["transitions"] = [{"to": "branch"}]
    raw["blocks"] = [page, {"id": "branch", "kind": "decision", "title": "Выбор инструкции", "transitions": [
        {"to": "mail_help", "when": {"op": "eq", "source": "answer", "field": "issue", "value": "mail"}},
        {"to": "vpn_help", "when": {"op": "eq", "source": "answer", "field": "issue", "value": "vpn"}},
        {"to": "review"},
    ]}, *[{"id": block_id, "kind": "instruction", "title": block_id, "content": {"body": "Проверьте подключение"},
           "transitions": [{"to": "review"}]} for block_id in ("mail_help", "vpn_help")], *raw["blocks"][4:6]]
    validator, runtime = _modules()
    assert not validator.validate_scenario(_definition(raw)), validator.validate_scenario(_definition(raw))
    engine = runtime.ScenarioRuntime(_definition(raw))
    initial = engine.initial_state()
    state = engine.advance(initial, _answer(initial, {"issue": answer}))
    assert state.current_block_id == expected
    assert state.answers == {"issue": answer}
    if expected != "review":
        state = engine.advance(state, _answer(state, result="acknowledged"))
        assert state.current_block_id == "review"
    state = engine.advance(state, _answer(state))
    assert state.current_block_id == "submit"  # Actual ticket creation remains a separate durable action.


@pytest.mark.parametrize("group,title", [(None, "Section"), ("details", " ")])
def test_named_section_requires_safe_group_and_human_title(group, title):
    raw = pilot()
    raw["blocks"][0]["fields"][0].update(group=group, group_title=title)
    issues = _modules()[0].validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(issue.code == "invalid_group" for issue in issues)


def test_one_section_cannot_present_conflicting_titles():
    raw = pilot()
    raw["blocks"][0]["fields"][0].update(group="details", group_title="First")
    raw["blocks"][0]["fields"][1].update(group="details", group_title="Second")
    issues = _modules()[0].validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(issue.code == "invalid_group" for issue in issues)


def pilot():
    return {
        "schema_version": 1, "scenario_key": "printer_no_print", "service_code": "workplace",
        "offering_full_code": "workplace.printer_issue", "title": "Не печатает", "entry_block_id": "questions",
        "process_binding": {"request_template_key": "printer"},
        "blocks": [
            {"id": "questions", "kind": "form_page", "title": "Проблема", "fields": [
                {"key": "summary", "type": "textarea", "label": "Что произошло?", "required": True},
                {"key": "impact", "type": "radio", "label": "Кого затронуло?", "required": True,
                 "options": [{"value": "me", "label": "Меня"}, {"value": "team", "label": "Отдел"}],
                 "process_mapping": {"roles": ["priority_impact", "reporting_dimension"], "fact_key": "impact_scope"}},
                {"key": "team_note", "type": "text", "label": "Подробности", "required": True,
                 "visible_when": {"op": "eq", "source": "answer", "field": "impact", "value": "team"}},
            ], "transitions": [{"to": "instruction"}]},
            {"id": "instruction", "kind": "instruction", "title": "Проверьте питание",
             "content": {"body": "Проверьте индикатор питания."}, "transitions": [{"to": "helped"}]},
            {"id": "helped", "kind": "resolution_check", "title": "Помогло?", "transitions": [
                {"to": "done", "when": {"op": "eq", "source": "current_result", "value": "yes"}},
                {"to": "diagnostic", "when": {"op": "eq", "source": "current_result", "value": "no"}},
                {"to": "diagnostic", "when": {"op": "eq", "source": "current_result", "value": "unknown"}},
            ]},
            {"id": "diagnostic", "kind": "diagnostic", "title": "Проверка", "transitions": [{"to": "review"}]},
            {"id": "review", "kind": "review", "title": "Проверьте данные", "transitions": [{"to": "submit"}]},
            {"id": "submit", "kind": "submit_ticket", "title": "Создать обращение"},
            {"id": "done", "kind": "finish", "title": "Решено"},
        ],
    }


def _definition(raw=None):
    return ScenarioDefinition.model_validate(raw or pilot())


def _answer(state, answers=None, result=None):
    return ScenarioAnswerRequest(expected_block_id=state.current_block_id, revision=state.revision, answers=answers or {}, current_result=result)


def test_pilot_is_publishable_graph():
    validator, _ = _modules()
    assert validator.validate_scenario(_definition()) == []


@pytest.mark.parametrize("mutation,code", [
    ("entry", "unknown_entry"), ("duplicate_block", "duplicate_block"), ("target", "unknown_target"),
    ("cycle", "cycle"), ("unreachable", "unreachable_block"), ("missing_exit", "missing_fallback"),
    ("terminal_exit", "terminal_outgoing"), ("duplicate_field", "duplicate_field"),
    ("missing_field", "unknown_field"), ("field_cycle", "field_dependency_cycle"),
    ("bad_type", "incompatible_condition"), ("bad_role", "incompatible_role"),
    ("unsafe_fact", "unsafe_fact_key"), ("finish_direct", "unconfirmed_finish"),
    ("bad_capability", "unknown_capability"),
])
def test_invalid_graph_is_rejected_before_runtime(mutation, code):
    raw = pilot()
    page, instruction, check, diagnostic, review, submit, finish = raw["blocks"]
    if mutation == "entry": raw["entry_block_id"] = "absent"
    elif mutation == "duplicate_block": raw["blocks"].append(deepcopy(finish))
    elif mutation == "target": page["transitions"][0]["to"] = "absent"
    elif mutation == "cycle": instruction["transitions"][0]["to"] = page["id"]
    elif mutation == "unreachable": raw["blocks"].append({"id": "orphan", "kind": "submit_ticket", "title": "Orphan"})
    elif mutation == "missing_exit": diagnostic["transitions"] = []
    elif mutation == "terminal_exit": submit["transitions"] = [{"to": "questions"}]
    elif mutation == "duplicate_field": page["fields"].append(deepcopy(page["fields"][0]))
    elif mutation == "missing_field": page["fields"][2]["visible_when"]["field"] = "absent"
    elif mutation == "field_cycle": page["fields"][1]["visible_when"] = {"op": "exists", "source": "answer", "field": "team_note"}
    elif mutation == "bad_type": page["fields"][2]["visible_when"] = {"op": "gt", "source": "answer", "field": "impact", "value": 1}
    elif mutation == "bad_role": page["fields"][0]["process_mapping"] = {"roles": ["priority_impact"]}
    elif mutation == "unsafe_fact": page["fields"][1]["process_mapping"]["fact_key"] = "actor_id"
    elif mutation == "finish_direct": instruction["transitions"][0]["to"] = "done"
    elif mutation == "bad_capability": diagnostic["capability"] = "shell.execute"
    validator, runtime = _modules()
    assert code in {issue.code for issue in validator.validate_scenario(_definition(raw))}
    with pytest.raises(validator.ScenarioValidationError):
        runtime.ScenarioRuntime(_definition(raw))


@pytest.mark.parametrize("op,value,answers,expected", [
    ("eq", True, {"value": 1}, False), ("neq", "x", {}, False),
    ("eq", "team", {"value": "team"}, True), ("gt", 2, {"value": 3}, True),
    ("gt", 2, {"value": "3"}, False), ("in", ["team", "all"], {"value": ["team"]}, True),
])
def test_condition_evaluator_is_typed_and_missing_is_not_inequality(op, value, answers, expected):
    _, runtime = _modules()
    condition = TypeAdapter(Condition).validate_python({"op": op, "source": "answer", "field": "value", "value": value})
    assert runtime.evaluate_condition(condition, answers, None) is expected


def test_instruction_acknowledgment_is_not_self_resolution():
    _, runtime = _modules()
    engine = runtime.ScenarioRuntime(_definition())
    first = engine.initial_state()
    instruction = engine.advance(first, _answer(first, {"summary": "Не печатает", "impact": "me"}))
    assert instruction.current_block_id == "instruction" and instruction.state == "active"
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(instruction, _answer(instruction))
    check = engine.advance(instruction, _answer(instruction, result="acknowledged"))
    assert check.current_block_id == "helped" and check.state == "active"
    done = engine.advance(check, _answer(check, result="yes"))
    assert done.state == "completed_self_service" and done.current_block_id == "done"
    assert first.answers == {} and first.history == []  # caller state is not mutated


@pytest.mark.parametrize("result", ["no", "unknown"])
def test_unavailable_diagnostic_uses_safe_fallback_without_dispatch(result):
    _, runtime = _modules()
    engine = runtime.ScenarioRuntime(_definition())
    state = engine.initial_state()
    state = engine.advance(state, _answer(state, {"summary": "Не печатает", "impact": "me"}))
    state = engine.advance(state, _answer(state, result="acknowledged"))
    state = engine.advance(state, _answer(state, result=result))
    assert state.current_block_id == "review" and state.state == "active"
    assert state.results["diagnostic"] == {"status": "unavailable", "reason": "pre_ticket_contract_unavailable"}
    state = engine.advance(state, _answer(state))
    assert state.current_block_id == "submit" and state.state == "active"
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state))  # ticket creation belongs to the existing durable service


def test_hidden_required_answers_are_pruned_and_back_invalidates_downstream():
    _, runtime = _modules()
    engine = runtime.ScenarioRuntime(_definition())
    state = engine.initial_state()
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state, {"summary": "Не печатает", "impact": "team"}))
    state = engine.advance(state, _answer(state, {"summary": "Не печатает", "impact": "team", "team_note": "Все"}))
    state = engine.advance(state, _answer(state, result="acknowledged"))
    state = engine.advance(state, _answer(state, result="no"))
    back = engine.back(state, "questions", expected_revision=state.revision)
    assert back.results == {} and back.history == []
    edited = engine.advance(back, _answer(back, {"summary": "Не печатает", "impact": "me", "team_note": "stale"}))
    assert "team_note" not in edited.answers
    assert state.answers["team_note"] == "Все" and state.results["helped"] == "no"


def test_runtime_rejects_stale_revision_wrong_block_and_foreign_fields():
    _, runtime = _modules()
    engine = runtime.ScenarioRuntime(_definition())
    state = engine.initial_state()
    with pytest.raises(runtime.ScenarioConflict):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id="review", revision=state.revision))
    with pytest.raises(runtime.ScenarioConflict):
        engine.advance(state, ScenarioAnswerRequest(expected_block_id="questions", revision=state.revision + 1))
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state, {"summary": "x", "impact": "me", "queue_id": 99}))


def test_seeded_dag_fuzz_has_deterministic_bounded_execution():
    validator, runtime = _modules()
    rng = random.Random(147)
    for _ in range(60):
        length = rng.randint(1, 40)
        raw = pilot()
        raw["entry_block_id"] = "page_0"
        raw["blocks"] = [{"id": f"page_{i}", "kind": "form_page", "title": "Вопрос", "fields": [{"key": f"answer_{i}", "type": "text", "label": "Ответ"}], "transitions": [{"to": f"page_{i + 1}" if i + 1 < length else "submit"}]} for i in range(length)]
        raw["blocks"].append({"id": "submit", "kind": "submit_ticket", "title": "Отправить"})
        definition = _definition(raw)
        assert validator.validate_scenario(definition) == []
        left, right = runtime.ScenarioRuntime(definition), runtime.ScenarioRuntime(definition)
        a, b = left.initial_state(), right.initial_state()
        for i in range(length):
            a = left.advance(a, _answer(a, {f"answer_{i}": "x"}))
            b = right.advance(b, _answer(b, {f"answer_{i}": "x"}))
        assert a == b and a.current_block_id == "submit" and len(a.history) == length


def test_overlapping_decision_requires_explicit_unique_priority_and_fallback():
    validator, runtime = _modules()
    raw = pilot()
    raw["blocks"][0]["transitions"] = [{"to": "route"}]
    decision = {"id": "route", "kind": "decision", "title": "Выбор", "transitions": [
        {"to": "instruction", "when": {"op": "exists", "source": "answer", "field": "summary"}},
        {"to": "review", "when": {"op": "eq", "source": "answer", "field": "impact", "value": "me"}},
        {"to": "instruction"},
    ]}
    raw["blocks"].append(decision)
    assert "ambiguous_precedence" in {issue.code for issue in validator.validate_scenario(_definition(raw))}
    decision["transitions"][0]["priority"] = 20
    decision["transitions"][1]["priority"] = 10
    engine = runtime.ScenarioRuntime(_definition(raw))
    start = engine.initial_state()
    state = engine.advance(start, _answer(start, {"summary": "x", "impact": "me"}))
    assert state.current_block_id == "review"
    decision["transitions"].pop()
    assert "missing_fallback" in {issue.code for issue in validator.validate_scenario(_definition(raw))}


@pytest.mark.parametrize("value", [True, "3", 11])
def test_runtime_numeric_answers_require_actual_numbers_and_apply_bounds(value):
    _, runtime = _modules()
    raw = pilot()
    raw["blocks"][0]["fields"].append({"key": "count", "type": "number", "label": "Количество", "required": True, "validation": {"min_value": 1, "max_value": 10}})
    engine = runtime.ScenarioRuntime(_definition(raw))
    state = engine.initial_state()
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state, {"summary": "x", "impact": "me", "count": value}))


def test_long_field_dependency_chain_does_not_use_python_recursion():
    validator, _ = _modules()
    raw = pilot()
    raw["entry_block_id"] = "page_0"
    raw["blocks"] = []
    for page in range(12):
        fields = []
        for offset in range(100):
            index = page * 100 + offset
            item = {"key": f"f_{index}", "type": "text", "label": "Ответ"}
            if index:
                item["required_when"] = {"op": "exists", "source": "answer", "field": f"f_{index - 1}"}
            fields.append(item)
        raw["blocks"].append({"id": f"page_{page}", "kind": "form_page", "title": "Вопросы", "fields": fields, "transitions": [{"to": f"page_{page + 1}" if page < 11 else "submit"}]})
    raw["blocks"].append({"id": "submit", "kind": "submit_ticket", "title": "Отправить"})
    # Reverse declarations so a recursive checker would recurse through the entire chain.
    raw["blocks"].reverse()
    for block in raw["blocks"]:
        if "fields" in block:
            block["fields"].reverse()
    assert validator.validate_scenario(_definition(raw)) == []


def test_multi_select_disjoint_expected_sets_can_overlap_on_actual_answer():
    validator, _ = _modules()
    raw = pilot()
    field = raw["blocks"][0]["fields"][1]
    field["type"] = "multi_select"
    field["process_mapping"] = {"roles": ["reporting_dimension"]}
    raw["blocks"][0]["fields"][2].pop("visible_when")
    raw["blocks"][0]["transitions"] = [
        {"to": "instruction", "when": {"op": "in", "source": "answer", "field": "impact", "value": ["me"]}},
        {"to": "review", "when": {"op": "in", "source": "answer", "field": "impact", "value": ["team"]}},
        {"to": "instruction"},
    ]
    assert "ambiguous_precedence" in {issue.code for issue in validator.validate_scenario(_definition(raw))}


def test_oversized_integer_cannot_overflow_evaluator_or_enter_answers():
    validator, runtime = _modules()
    huge = 10 ** 1000
    condition = TypeAdapter(Condition).validate_python({"op": "gt", "source": "answer", "field": "value", "value": 1})
    assert runtime.evaluate_condition(condition, {"value": huge}) is False
    raw = pilot()
    raw["blocks"][0]["fields"].append({"key": "count", "type": "number", "label": "Количество"})
    engine = runtime.ScenarioRuntime(_definition(raw))
    state = engine.initial_state()
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state, {"summary": "x", "impact": "me", "count": huge}))
    raw["blocks"][0]["transitions"] = [
        {"to": "instruction", "when": {"op": "gt", "source": "answer", "field": "count", "value": huge}},
        {"to": "instruction"},
    ]
    assert "incompatible_condition" in {issue.code for issue in validator.validate_scenario(_definition(raw))}


def test_answer_dependent_branch_cannot_prove_resolution_coverage():
    validator, runtime = _modules()
    raw = pilot()
    raw["blocks"][2]["transitions"] = [
        {"to": "done", "priority": 1, "when": {"op": "eq", "source": "current_result", "value": "yes"}},
        {"to": "diagnostic", "priority": 2, "when": {"op": "not", "condition": {"op": "exists", "source": "answer", "field": "summary"}}},
    ]
    assert "missing_fallback" in {issue.code for issue in validator.validate_scenario(_definition(raw))}
    with pytest.raises(validator.ScenarioValidationError):
        runtime.ScenarioRuntime(_definition(raw))


@pytest.mark.parametrize("value", [1e100, 1e308])
def test_large_finite_float_cannot_be_normalized_into_unsafe_integer(value):
    _, runtime = _modules()
    raw = pilot()
    raw["blocks"][0]["fields"].append({"key": "count", "type": "number", "label": "Количество"})
    engine = runtime.ScenarioRuntime(_definition(raw))
    state = engine.initial_state()
    with pytest.raises(runtime.ScenarioInputError):
        engine.advance(state, _answer(state, {"summary": "x", "impact": "me", "count": value}))
