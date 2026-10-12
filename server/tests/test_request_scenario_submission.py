"""Trusted scenario facts cannot supply ticket authority or hidden answers."""
import pytest

from web_api.dto.request_scenario import ScenarioDefinition
from tickets.request_scenario_runtime import RuntimeState, ScenarioInputError

pytestmark = pytest.mark.no_db


def definition():
    return ScenarioDefinition.model_validate({
        "scenario_key": "printer", "service_code": "workplace", "offering_full_code": "workplace.printer",
        "title": "Printer", "entry_block_id": "questions", "process_binding": {"request_template_key": "printer"},
        "blocks": [
            {"id": "questions", "kind": "form_page", "title": "Questions", "fields": [
                {"key": "summary", "label": "Problem", "type": "text", "required": True},
                {"key": "urgent", "label": "Urgent", "type": "checkbox", "process_mapping": {
                    "roles": ["priority_urgency", "reporting_dimension"], "fact_key": "is_urgent"}},
                {"key": "hidden", "label": "Hidden", "type": "text", "visible_when": {
                    "source": "answer", "field": "urgent", "op": "eq", "value": True}},
            ], "transitions": [{"to": "submit"}]},
            {"id": "submit", "kind": "submit_ticket", "title": "Submit"},
        ],
    })


def test_submission_maps_only_visited_visible_facts_and_preserves_roles():
    from tickets.request_scenario_submission import build_scenario_submission
    state = RuntimeState("submit", 2, {"summary": "No print", "urgent": False, "hidden": "stale", "queue_id": 9}, ["questions"], {})
    payload, snapshot = build_scenario_submission(definition(), state, session_id="session", version_id="version")
    assert payload["form_payload"] == {"summary": "No print", "is_urgent": False}
    assert payload["offering_full_code"] == "workplace.printer"
    assert not {"priority", "queue_id", "requester_id", "actor_id", "sla_policy_id"} & payload.keys()
    assert snapshot["answers"] == {"summary": "No print", "urgent": False}
    assert snapshot["field_roles"]["is_urgent"] == ["priority_urgency", "reporting_dimension"]
    assert snapshot["session_id"] == "session" and snapshot["version_id"] == "version"
    assert snapshot["summary"][0]["label"] == "Problem"


@pytest.mark.parametrize("current,status", [("questions", "active"), ("submit", "completed_self_service"), ("submit", "canceled")])
def test_submission_requires_active_submit_terminal(current, status):
    from tickets.request_scenario_submission import build_scenario_submission
    with pytest.raises(ScenarioInputError):
        build_scenario_submission(definition(), RuntimeState(current, 1, {}, [], {}, status), session_id="s", version_id="v")


def test_submission_revalidates_required_answers():
    from tickets.request_scenario_submission import build_scenario_submission
    with pytest.raises(ScenarioInputError):
        build_scenario_submission(definition(), RuntimeState("submit", 2, {"urgent": False}, ["questions"], {}), session_id="s", version_id="v")


def test_submit_dto_rejects_client_authority():
    from pydantic import ValidationError
    from web_api.dto.request_scenario_session import SessionSubmit
    assert SessionSubmit.model_validate({"revision": 2, "confirm": True}).confirm
    for extra in ({"actor_id": "other"}, {"priority": "P1"}, {"answers": {"summary": "forged"}}, {"confirm": False}, {"confirm": 1}):
        with pytest.raises(ValidationError):
            SessionSubmit.model_validate({"revision": 2, "confirm": True, **extra})


def test_submit_device_selection_uses_canonical_owned_device_gate():
    from pydantic import ValidationError
    from web_api.dto.request_scenario_session import SessionSubmit
    assert SessionSubmit.model_validate({"revision": 2, "confirm": True, "device_scope": "none"}).device_scope == "none"
    assert SessionSubmit.model_validate({"revision": 2, "confirm": True, "device_id": "device"}).device_id == "device"
    with pytest.raises(ValidationError):
        SessionSubmit.model_validate({"revision": 2, "confirm": True, "device_id": "device", "device_scope": "none"})
