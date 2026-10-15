"""V3 interchange stays bounded, strict and compatible with historical maps."""
from copy import deepcopy

import pytest

from web_api.dto.request_scenario import ScenarioDraftDefinition

pytestmark = pytest.mark.no_db


def definition():
    return {
        "schema_version": 3, "scenario_key": "printer", "service_code": "it",
        "offering_full_code": "it.printer", "title": "Печать",
        "process_binding": {"request_template_key": "printer"},
        "processing": {
            "sla_profiles": {"standard": {"title": "Стандартный", "first_response_minutes": 120, "resolution_minutes": 300}},
            "routes": {"support": {"title": "Поддержка", "queue_code": "support"}},
            "defaults": {"route": "support", "sla_profile": "standard"},
        },
        "blocks": [{"id": "q", "kind": "decision", "title": "Условие", "transitions": [
            {"to": "submit", "processing": {"route": "support", "sla_profile": "standard", "approval_required": True}}]},
            {"id": "submit", "kind": "submit_ticket", "title": "Создать"}],
    }


def test_v3_json_yaml_roundtrip_preserves_processing():
    from tickets.request_scenario_document import export_scenario_document, parse_scenario_document
    value = ScenarioDraftDefinition.model_validate(definition())
    for format in ("json", "yaml"):
        restored = parse_scenario_document(export_scenario_document(value, format), format)
        assert restored.model_dump() == value.model_dump()
        assert restored.processing.defaults.route == "support"
        assert restored.blocks[0].transitions[0].processing.approval_required is True


@pytest.mark.parametrize("version", [1, 2])
def test_old_versions_reject_v3_processing_authority(version):
    raw = definition()
    raw["schema_version"] = version
    with pytest.raises(ValueError, match="schema_version 3"):
        ScenarioDraftDefinition.model_validate(raw)
    raw.pop("processing")
    raw["blocks"][0]["transitions"][0].pop("processing")
    assert ScenarioDraftDefinition.model_validate(raw).schema_version == version


@pytest.mark.parametrize("patch", [
    {"first_response_minutes": -1}, {"resolution_minutes": True},
    {"time_basis": "unknown"}, {"calendar_id": 2},
    {"first_response_minutes": 525601}, {"priority": "P1"},
])
def test_invalid_sla_profiles_are_rejected(patch):
    raw = deepcopy(definition())
    raw["processing"]["sla_profiles"]["standard"].update(patch)
    with pytest.raises(ValueError):
        ScenarioDraftDefinition.model_validate(raw)


def test_database_constraint_preserves_all_three_immutable_versions():
    from app.db.request_scenario_models import RequestStudioScenarioVersion
    constraint = next(item for item in RequestStudioScenarioVersion.__table__.constraints if item.name == "ck_studio_version_schema")
    assert "schema_version IN (1,2,3)" in str(constraint.sqltext)


def test_complete_equipment_example_roundtrip_and_all_readiness_routes():
    from pathlib import Path
    from tickets.request_scenario_document import parse_scenario_document, export_scenario_document, document_issues
    from tickets.request_scenario_readiness import submission_variants
    from web_api.dto.request_scenario import ScenarioDefinition
    path = Path(__file__).resolve().parents[2] / "docs/examples/guided-request-v3-equipment.yaml"
    draft = parse_scenario_document(path.read_text(encoding="utf-8"), "yaml")
    assert not document_issues(draft)
    value = ScenarioDefinition.model_validate(draft.model_dump())
    assert len(value.processing.sla_profiles) == 3
    assert len(value.processing.routes) == 3
    assert len(value.blocks[3].transitions[0].when.conditions) == 3
    assert parse_scenario_document(export_scenario_document(value, "yaml"), "yaml").model_dump() == value.model_dump()
    states = submission_variants(value)
    assert any("problem_type" not in state.answers for state in states)
    assert any(state.answers.get("can_continue") is None for state in states)


@pytest.mark.asyncio
async def test_document_reference_validation_reports_missing_queue_before_apply():
    from tickets.request_scenario_document import document_reference_issues
    class Session:
        async def scalars(self, statement):
            return []
    value = ScenarioDraftDefinition.model_validate(definition())
    issues = await document_reference_issues(Session(), value)
    assert issues == [{"code": "processing_queue_unavailable", "path": "processing.routes.support.queue_code",
        "message": "Направление ссылается на отсутствующую или отключённую очередь."}]


def test_unconfigured_v3_draft_can_save_but_cannot_execute():
    from tickets.request_scenario_validation import validate_scenario
    raw = definition()
    raw["processing"] = {"routes": {}, "sla_profiles": {}, "defaults": {"route": "", "sla_profile": ""}}
    value = ScenarioDraftDefinition.model_validate(raw)
    assert any(issue.path.startswith("processing") for issue in validate_scenario(value))


def test_incomplete_profile_and_direction_are_retained_in_draft():
    from tickets.request_scenario_validation import validate_scenario
    raw = definition()
    raw["processing"]["sla_profiles"]["standard"].update(first_response_minutes=0, resolution_minutes=0, time_basis="business")
    raw["processing"]["routes"]["support"]["queue_code"] = ""
    value = ScenarioDraftDefinition.model_validate(raw)
    assert value.processing.sla_profiles["standard"].resolution_minutes == 0
    assert any(issue.path.startswith("processing") for issue in validate_scenario(value))


def test_documented_machine_schema_matches_the_strict_dto():
    import json
    from pathlib import Path
    from scripts.export_request_scenario_schema import scenario_json_schema
    schema = scenario_json_schema()
    path = Path(__file__).resolve().parents[2] / "docs/contracts/request-scenario.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == schema
    assert schema["properties"]["schema_version"]["enum"] == [1, 2, 3]
    assert schema["additionalProperties"] is False
