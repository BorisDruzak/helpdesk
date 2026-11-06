"""Legacy screenshot questions never make an otherwise complete request mandatory."""
from copy import deepcopy

import pytest

from tickets.request_scenario_runtime import RuntimeState, ScenarioInputError, ScenarioRuntime
from tickets.request_scenario_session import project_step
from tickets.request_scenario_submission import build_scenario_submission
from web_api.dto.request_scenario import ScenarioAnswerRequest, ScenarioDefinition

pytestmark = pytest.mark.no_db


def legacy_definition():
    return ScenarioDefinition.model_validate({
        "schema_version": 3, "scenario_key": "legacy", "service_code": "other",
        "offering_full_code": "other.legacy", "title": "Other", "entry_block_id": "request",
        "process_binding": {"request_template_key": "general"},
        "processing": {"defaults": {"route": "first", "sla_profile": "normal"},
            "routes": {"first": {"title": "First", "queue_code": "first"}},
            "sla_profiles": {"normal": {"title": "Normal", "first_response_minutes": 60, "resolution_minutes": 480}}},
        "blocks": [
            {"id": "request", "kind": "form_page", "title": "Problem", "fields": [
                {"key": "details", "type": "textarea", "label": "Describe the problem", "required": True}],
             "transitions": [{"to": "q_evidence"}]},
            {"id": "q_evidence", "kind": "form_page", "title": "Скриншот или фото ошибки", "fields": [
                {"key": "evidence_note", "type": "textarea", "label": "Скриншот подготовлен или почему его невозможно приложить?", "required": True},
                {"key": "evidence_caption", "type": "textarea", "label": "Что видно на снимке или что происходит вместо видимой ошибки?", "required": False}],
             "transitions": [{"to": "submit"}]},
            {"id": "submit", "kind": "submit_ticket", "title": "Submit"},
        ]})


def answer(state, values=None):
    return ScenarioAnswerRequest(revision=state.revision, expected_block_id=state.current_block_id, answers=values or {})


def test_legacy_empty_screenshot_answers_advance_and_final_form_is_optional():
    definition = legacy_definition()
    before = definition.model_dump(mode="json")
    runtime = ScenarioRuntime(definition)
    state = runtime.advance(runtime.initial_state(), answer(runtime.initial_state(), {"details": "No access"}))
    assert state.current_block_id == "q_evidence"
    assert all(not field["required"] for field in project_step(runtime.definition, state)["block"]["fields"])
    preview = runtime.preview_answers(state, answer(state))
    assert preview.answers == {"details": "No access"}
    state = runtime.advance(state, answer(state))
    payload, snapshot = build_scenario_submission(definition, state, session_id="s", version_id="v")
    assert state.current_block_id == "submit"
    assert payload["form_payload"] == {"details": "No access"}
    assert {item["key"]: item["required"] for item in snapshot["form_schema"]["fields"]} == {
        "details": True, "evidence_note": False, "evidence_caption": False}
    assert definition.model_dump(mode="json") == before


def test_legacy_screenshot_answers_and_current_block_are_retained():
    definition = legacy_definition()
    runtime = ScenarioRuntime(definition)
    pinned = RuntimeState("q_evidence", 8, {"details": "No access"}, ["request"], {"_entry_point": {"title": "Entrance"}})
    submitted = runtime.advance(pinned, answer(pinned, {"evidence_note": "Attached", "evidence_caption": "Error"}))
    payload, snapshot = build_scenario_submission(definition, submitted, session_id="s", version_id="old-version")
    assert payload["form_payload"] == {"details": "No access", "evidence_note": "Attached", "evidence_caption": "Error"}
    assert snapshot["version_id"] == "old-version"
    assert snapshot["history"] == ["request", "q_evidence"]
    assert pinned.current_block_id == "q_evidence" and pinned.revision == 8


def test_ordinary_required_question_stays_required():
    runtime = ScenarioRuntime(legacy_definition())
    with pytest.raises(ScenarioInputError, match="invalid"):
        runtime.advance(runtime.initial_state(), answer(runtime.initial_state()))


def test_editor_coordinates_do_not_block_compatibility_and_only_removed_stage_position_is_dropped():
    from tickets.request_scenario_optional_evidence import effective_definition, without_evidence_stage
    raw = legacy_definition().model_dump(mode="json")
    raw["editor_layout"]["positions"] = {"request": {"x": 1, "y": 2}, "q_evidence": {"x": 30, "y": 40}, "submit": {"x": 50, "y": 60}}
    before = deepcopy(raw)
    effective = effective_definition(ScenarioDefinition.model_validate(raw))
    assert effective.blocks[1].fields[0].required is False
    assert effective.editor_layout.model_dump(mode="json") == raw["editor_layout"]
    transformed = without_evidence_stage(raw)
    assert transformed["editor_layout"]["positions"] == {"request": {"x": 1, "y": 2}, "submit": {"x": 50, "y": 60}}
    assert raw == before


@pytest.mark.parametrize("change", ["label", "condition", "mapping", "bounds", "reference", "entry", "transition", "extra_field"])
def test_similar_stage_with_changed_semantics_is_never_weakened(change):
    raw = legacy_definition().model_dump(mode="json")
    block = raw["blocks"][1]
    field = block["fields"][0]
    if change == "label": field["label"] = "Required business evidence"
    if change == "condition": field["required_when"] = {"source": "answer", "field": "details", "op": "exists"}
    if change == "mapping": field["process_mapping"]["roles"] = ["closure_evidence"]
    if change == "bounds": field["validation"]["min_length"] = 3
    if change == "reference": raw["blocks"][0]["fields"][0]["aliases"] = ["evidence_note"]
    if change == "entry": raw["entry_block_id"] = "q_evidence"
    if change == "transition": block["transitions"][0]["processing"] = {"route": "first"}
    if change == "extra_field": block["fields"].append({"key": "extra", "type": "text", "label": "Extra"})
    from tickets.request_scenario_optional_evidence import effective_definition, without_evidence_stage
    definition = ScenarioDefinition.model_validate(raw)
    assert effective_definition(definition).model_dump(mode="json") == definition.model_dump(mode="json")
    with pytest.raises(ValueError, match="evidence"):
        without_evidence_stage(raw)


def test_new_definition_omits_stage_and_preserves_other_graph_and_processing():
    from tickets.request_scenario_optional_evidence import without_evidence_stage
    raw = legacy_definition().model_dump(mode="json")
    before = deepcopy(raw)
    raw["blocks"][0]["transitions"][0]["processing"] = {"sla_profile": "normal"}
    transformed = without_evidence_stage(raw)
    assert [block["id"] for block in transformed["blocks"]] == ["request", "submit"]
    assert transformed["blocks"][0]["transitions"] == [{**raw["blocks"][0]["transitions"][0], "to": "submit"}]
    assert transformed["processing"] == before["processing"]
    assert transformed["process_binding"] == before["process_binding"]
    runtime = ScenarioRuntime(ScenarioDefinition.model_validate(transformed))
    state = runtime.advance(runtime.initial_state(), answer(runtime.initial_state(), {"details": "No access"}))
    assert state.current_block_id == "submit"
    assert without_evidence_stage(transformed) == transformed


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 2])
async def test_pinned_screenshot_uploads_survive_empty_answers_back_reload_and_claim(count, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets import request_scenario_assets as assets
    rows = [SimpleNamespace(id=f"asset-{index}", block_id="q_evidence", field_key=("evidence_note", "evidence_caption")[index],
        name=f"shot-{index}.png", mime_type="image/png", size_bytes=12, artifact_id=None, removed_at=None,
        storage_path=f"/private/shot-{index}", sha256="a" * 64) for index in range(count)]
    monkeypatch.setattr(assets, "session_assets", AsyncMock(return_value=rows))
    runtime = ScenarioRuntime(legacy_definition())
    pinned = RuntimeState("q_evidence", 8, {"details": "No access"}, ["request"])
    # Asset projection cannot supply a scalar required answer.
    projection = await assets.project_answer_assets(None, "session", runtime, pinned, project_step(runtime.definition, pinned))
    assert sum(len(field["answer_attachments"]) for field in projection["block"]["fields"]) == count
    advanced = runtime.advance(pinned, answer(pinned))
    back = runtime.back(advanced, "q_evidence", expected_revision=advanced.revision)
    await assets.prune_answer_assets(None, "session", runtime, back)
    assert all(row.removed_at is None for row in rows)
    reloaded = ScenarioRuntime(legacy_definition())
    final = reloaded.advance(deepcopy(back), answer(back))
    projected = await assets.project_answer_assets(None, "session", reloaded, final, project_step(reloaded.definition, final))
    assert sum(len(item["answer_attachments"]) for item in projected["block"]["answers"]) == count
    assert final.answers == {"details": "No access"} and final.history == ["request", "q_evidence"]
    ticket = SimpleNamespace(custom_fields={"request_scenario": {"summary": projected["block"]["answers"]}})
    event = SimpleNamespace(payload={"is_initial": True})
    class Session:
        def __init__(self): self.artifacts = []
        def add(self, artifact): self.artifacts.append(artifact)
        async def flush(self): pass
        async def get(self, model, identifier): return ticket
        async def scalar(self, statement): return event
    session = Session()
    row = SimpleNamespace(id="session", **vars(final))
    await assets.claim_answer_assets(session, row, reloaded, 77)
    assert len(session.artifacts) == count
    assert all(artifact.ticket_id == 77 and artifact.kind == "screenshot" for artifact in session.artifacts)
    if count:
        assert len(ticket.custom_fields["request_scenario"]["answer_attachments"]) == count
        assert len(event.payload["attachment_refs"]) == count
        ids = list(event.payload["attachment_refs"])
        await assets.claim_answer_assets(session, row, reloaded, 77)
        assert len(session.artifacts) == count and event.payload["attachment_refs"] == ids
    assert all(asset.removed_at is None for asset in rows)
