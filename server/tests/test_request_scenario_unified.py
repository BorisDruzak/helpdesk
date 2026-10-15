"""One source for interchange, canonical validation and processing facts."""
import json
import pytest

from web_api.dto.request_scenario import ScenarioDefinition
from tickets.request_scenario_runtime import RuntimeState

pytestmark = pytest.mark.no_db


def source():
    return {"schema_version": 2, "scenario_key": "unified", "service_code": "workplace",
            "offering_full_code": "workplace.printer", "title": "Печать", "entry_block_id": "questions",
            "process_binding": {"request_template_key": "printer"}, "entry_points": [
                {"key": "print", "title": "Не печатает", "target_block_id": "questions"}], "blocks": [
                {"id": "questions", "kind": "form_page", "title": "Вопросы", "fields": [
                    {"key": "affected", "type": "radio", "label": "Кто не может печатать?", "required": True,
                     "options": [{"value": "one", "label": "Только я"}, {"value": "all", "label": "Весь отдел"}],
                     "process_mapping": {"effects": [{"value": "all", "facts": {"impact": "department"}}]}},
                    {"key": "hidden", "type": "text", "label": "Скрытый вопрос", "visible_when": {
                        "source": "answer", "field": "affected", "op": "eq", "value": "one"}}],
                 "transitions": [{"to": "submit", "processing_facts": {"urgency": "blocked"}}]},
                {"id": "submit", "kind": "submit_ticket", "title": "Создать обращение"}]}


def test_json_yaml_round_trip_preserves_one_definition():
    from tickets.request_scenario_document import parse_scenario_document, export_scenario_document
    definition = ScenarioDefinition.model_validate(source())
    for format in ("json", "yaml"):
        parsed = parse_scenario_document(export_scenario_document(definition, format), format)
        assert parsed.model_dump(mode="json") == definition.model_dump(mode="json")


@pytest.mark.parametrize("text,format", [('{"schema_version":1,"schema_version":2}', "json"),
    ('schema_version: 1\nschema_version: 2\n', "yaml"), ('a: &x [1]\nb: *x', "yaml"),
    ('!!python/object/apply:os.system [echo bad]', "yaml"), ('a: .nan', "yaml"),
    ('x: ' + '[' * 50 + '0' + ']' * 50, "yaml"), (json.dumps({"schema_version": 99}), "json")])
def test_invalid_documents_reject_ambiguity_and_unsafe_input(text, format):
    from tickets.request_scenario_document import parse_scenario_document
    with pytest.raises(ValueError):
        parse_scenario_document(text, format)


def test_submission_projects_visible_questions_and_typed_traversed_effects():
    from tickets.request_scenario_submission import build_scenario_submission
    definition = ScenarioDefinition.model_validate(source())
    state = RuntimeState("submit", 2, {"affected": "all", "hidden": "stale"}, ["questions"], {})
    payload, snapshot = build_scenario_submission(definition, state, session_id="s", version_id="v")
    assert payload["form_payload"] == {"affected": "all"}
    assert [field["key"] for field in snapshot["form_schema"]["fields"]] == ["affected"]
    assert snapshot["processing_facts"] == {"impact": "department", "urgency": "blocked"}
    state.answers = {"affected": "one"}
    _, snapshot = build_scenario_submission(definition, state, session_id="s", version_id="v")
    assert snapshot["processing_facts"] == {"urgency": "blocked"}


def test_facts_feed_existing_policy_input_fields_without_deadline_authority():
    from tickets.request_scenario_processing import apply_scenario_processing_facts
    validated = {"submitted_values": {}, "template_context": {"priority_policy": {
        "impact_field": "audience", "urgency_field": "ability", "importance_field": "business"}}}
    result = apply_scenario_processing_facts(validated, {"impact": "department", "urgency": "blocked", "importance": "important"})
    assert result["submitted_values"] == {"audience": "department", "ability": "work_stopped_no_workaround", "business": "high"}
    assert validated["submitted_values"] == {}
    with pytest.raises(ValueError):
        apply_scenario_processing_facts({"template_context": {}}, {"impact": "department"})
    with pytest.raises(ValueError):
        apply_scenario_processing_facts(validated, {"priority": "P1"})


@pytest.mark.asyncio
async def test_generated_schema_replaces_legacy_questions_but_retains_processing(monkeypatch):
    import tickets.request_template_submission as module
    async def pack(*args, **kwargs):
        return {"pack_key": "request_forms", "version": "1", "forms": [{"key": "printer", "title": "Print",
            "ticket_type": "incident", "fields": [{"key": "old_required", "label": "Old", "type": "text", "required": True}],
            "priority_policy": {"impact_field": "scope"}, "default_queue_id": 7}]}
    monkeypatch.setattr(module, "resolve_ticket_form_pack", pack)
    value = await module.resolve_create_form_submission(None, pack_key="request_forms", pack_version=None,
        form_key="printer", request_template_key="printer", raw_values={"new_question": "answer"},
        scenario_schema={"title": "Map", "version": "v2", "fields": [{"key": "new_question", "type": "text", "label": "New", "required": True}]})
    assert value["submitted_values"] == {"new_question": "answer"}
    assert value["template_context"]["default_queue_id"] == 7
    assert value["template_context"]["priority_policy"] == {"impact_field": "scope"}
    assert value["resolved_from"] == "scenario_map"


@pytest.mark.asyncio
async def test_unknown_checkbox_is_not_converted_to_negative_answer(monkeypatch):
    import tickets.request_template_submission as module
    async def pack(*args, **kwargs):
        return {"pack_key": "request_forms", "version": "1", "forms": [{"key": "printer", "title": "Print",
            "ticket_type": "incident", "fields": [], "default_queue_id": 7}]}
    monkeypatch.setattr(module, "resolve_ticket_form_pack", pack)
    value = await module.resolve_create_form_submission(None, pack_key="request_forms", pack_version=None,
        form_key="printer", request_template_key="printer", raw_values={"working": None},
        scenario_schema={"title": "Map", "version": "v2", "fields": [{"key": "working", "type": "checkbox", "label": "Working?", "allow_unknown": True}]})
    assert value["submitted_values"]["working"] is None


def test_conversion_preserves_fields_visibility_and_policy_binding():
    from tickets.request_scenario_conversion import convert_form
    offering = {"full_code": "workplace.printer", "service_code": "workplace", "public_title": "Печать", "request_template_key": "printer"}
    form = {"fields": [{"key": "where", "label": "Где?", "type": "text", "required": True},
        {"key": "detail", "label": "Описание", "type": "textarea", "visible_when": {"field": "where", "equals": "office"},
         "validation": {"max_length": 200}}]}
    result = convert_form(offering, form)
    assert result.schema_version == 2
    assert result.process_binding.request_template_key == "printer"
    fields = result.blocks[0].fields
    assert fields[0].key == "where" and fields[0].required
    assert fields[1].visible_when.value == "office"
    assert fields[1].validation.max_length == 200
    assert result.entry_points[0].title == "Печать"


@pytest.mark.parametrize("form", [{"fields": [{"key": "upload", "label": "File", "type": "file"}]},
    {"fields": [{"key": "name", "label": "Name", "type": "text", "validation": {"pattern": "[a-z]+"}}]},
    {"fields": [], "playbook_triggers": [{"id": "operation"}]},
    {"fields": [{"key": "name", "label": "Name", "type": "text", "default_value": "fixed"}]}])
def test_conversion_reports_unsupported_semantics_instead_of_dropping(form):
    from tickets.request_scenario_conversion import convert_form, ConversionBlocked
    with pytest.raises(ConversionBlocked) as error:
        convert_form({"full_code": "workplace.printer", "service_code": "workplace", "public_title": "Печать", "request_template_key": "printer"}, form)
    assert error.value.issues


def test_persistence_permits_both_pinned_v1_and_unified_v2():
    from app.db.request_scenario_models import RequestStudioScenarioVersion
    constraint = next(item for item in RequestStudioScenarioVersion.__table__.constraints if item.name == "ck_studio_version_schema")
    assert "schema_version IN (1,2,3)" in str(constraint.sqltext)


def test_effects_must_match_supported_answer_values():
    from tickets.request_scenario_validation import validate_scenario
    raw = source()
    raw["blocks"][0]["fields"][0]["process_mapping"]["effects"][0]["value"] = "removed_choice"
    assert any(issue.code == "invalid_processing_effect" for issue in validate_scenario(ScenarioDefinition.model_validate(raw)))


def test_multi_select_contributes_selected_effects_only():
    from tickets.request_scenario_submission import build_scenario_submission
    raw=source()
    raw["blocks"][0]["fields"][0]["type"]="multi_select"
    raw["blocks"][0]["fields"] = raw["blocks"][0]["fields"][:1]
    state=RuntimeState("submit",2,{"affected":["all"]},["questions"],{})
    _, snapshot=build_scenario_submission(ScenarioDefinition.model_validate(raw),state,session_id="s",version_id="v")
    assert snapshot["processing_facts"]["impact"]=="department"
