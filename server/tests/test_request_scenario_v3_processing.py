"""Map-owned decisions adapt to canonical services from a retained server route."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_request_scenario_unified import source
from tickets.request_scenario_runtime import RuntimeState
from tickets.request_scenario_submission import build_scenario_submission
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def definition():
    raw = source()
    raw.update(schema_version=3, processing={
        "routes": {"default": {"title": "First line", "queue_code": "first_line"},
                   "printing": {"title": "Printers", "queue_code": "printing"}},
        "sla_profiles": {"standard": {"title": "Standard", "first_response_minutes": 60, "resolution_minutes": 300},
                         "urgent": {"title": "Urgent", "first_response_minutes": 15, "resolution_minutes": 120}},
        "defaults": {"route": "default", "sla_profile": "standard"},
    })
    raw["blocks"][0]["transitions"] = [
        {"to": "submit", "when": {"source": "answer", "field": "affected", "op": "eq", "value": "all"},
         "processing": {"route": "printing", "sla_profile": "urgent", "approval_required": True}},
        {"to": "submit"},
    ]
    return ScenarioDefinition.model_validate(raw)


def snapshot(value="all"):
    return build_scenario_submission(definition(), RuntimeState("submit", 2, {"affected": value}, ["questions"], {}), session_id="s", version_id="v")[1]


def test_selected_branch_owns_sla_route_and_trace():
    selected = snapshot()["map_processing"]
    assert selected["route"]["key"] == "printing"
    assert selected["sla_profile"]["resolution_minutes"] == 120
    assert selected["approval_required"] is True
    assert selected["route"]["source"] == {"kind": "transition", "block_id": "questions", "transition_index": 0}
    assert selected["trace"][0]["assignments"]["route"] == "printing"
    assert selected["condition_trace"][0]["condition_evaluation"]["actual"] == "all"
    assert "form_schema" in snapshot()
    defaults = snapshot("one")["map_processing"]
    assert defaults["route"]["key"] == "default"
    assert defaults["sla_profile"]["resolution_minutes"] == 300
    assert defaults["route"]["source"] == {"kind": "default"}
    assert defaults["condition_trace"][0]["selected"] is False


def test_last_matching_branch_updates_each_assignment_independently():
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["transitions"][0]["to"] = "later"
    raw["blocks"][0]["transitions"][1]["to"] = "later"
    raw["blocks"].insert(1, {"id": "later", "kind": "decision", "title": "Later", "transitions": [
        {"to": "submit", "processing": {"sla_profile": "standard", "approval_required": False}}]})
    graph = ScenarioDefinition.model_validate(raw)
    state = RuntimeState("submit", 2, {"affected": "all"}, ["questions", "later"], {})
    selected = build_scenario_submission(graph, state, session_id="s", version_id="v")[1]["map_processing"]
    assert selected["route"]["key"] == "printing"
    assert selected["sla_profile"]["key"] == "standard"
    assert selected["approval_required"] is False


@pytest.mark.asyncio
async def test_adapter_replaces_inherited_route_and_sla_without_global_policy(monkeypatch):
    from tickets.request_scenario_processing import apply_scenario_map_processing
    selected = snapshot()["map_processing"]
    original = {"template_context": {"sla_policy_id": 9, "sla_policy": {"sla_policy_id": 9},
        "policy_refs": {"sla": {"code": "old"}, "routing": {"code": "old"}},
        "approval_policy": {"required": False, "approver_source": {"type": "requester_manager"}}}}
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=True)))
    result = await apply_scenario_map_processing(session, original, selected)
    context = result["template_context"]
    assert context["routing_policy"] == {"fallback": {"queue_id": 7, "queue_code": "printing"}}
    assert "sla_policy_id" not in context
    assert context["sla_policy"]["targets"]["resolution"] == {priority: 120 for priority in ("P0", "P1", "P2", "P3", "P4")}
    assert context["approval_policy"]["required"] is True
    assert context["approval_policy"]["approver_source"]["type"] == "requester_manager"
    assert not {"sla", "routing"} & context["policy_refs"].keys()
    assert original["template_context"]["sla_policy_id"] == 9


@pytest.mark.asyncio
async def test_adapter_fails_closed_for_disabled_selected_queue():
    from tickets.request_scenario_processing import apply_scenario_map_processing
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=False)))
    with pytest.raises(ValueError):
        await apply_scenario_map_processing(session, {"template_context": {}}, snapshot()["map_processing"])


@pytest.mark.asyncio
async def test_adapter_never_invents_deadlines_for_incomplete_profile():
    from tickets.request_scenario_processing import apply_scenario_map_processing
    selected = snapshot()["map_processing"]
    selected["sla_profile"]["resolution_minutes"] = 0
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=True)))
    with pytest.raises(ValueError):
        await apply_scenario_map_processing(session, {"template_context": {}}, selected)


def test_v3_validation_requires_defaults_and_known_references():
    from tickets.request_scenario_validation import validate_scenario
    raw = definition().model_dump(mode="json")
    raw["processing"]["defaults"]["route"] = "missing"
    raw["blocks"][0]["transitions"][0]["processing"]["sla_profile"] = "missing"
    paths = {issue.path for issue in validate_scenario(ScenarioDefinition.model_validate(raw))}
    assert "processing.defaults.route" in paths
    assert "blocks.questions.transitions.0.processing.sla_profile" in paths
    raw["processing"] = None
    assert "processing" in {issue.path for issue in validate_scenario(ScenarioDefinition.model_validate(raw))}


def test_incomplete_draft_processing_never_executes():
    from tickets.request_scenario_validation import validate_scenario
    raw = definition().model_dump(mode="json")
    raw["processing"]["routes"]["default"]["queue_code"] = ""
    raw["processing"]["sla_profiles"]["standard"]["resolution_minutes"] = 0
    paths = {issue.path for issue in validate_scenario(ScenarioDefinition.model_validate(raw))}
    assert "processing.routes.default.queue_code" in paths
    assert "processing.sla_profiles.standard.resolution_minutes" in paths


@pytest.mark.asyncio
async def test_resolved_approval_keeps_branch_requirement_and_current_approver_source(monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
    from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
    monkeypatch.setattr(HelpdeskPolicyRepo, "resolve_effective_policy", AsyncMock(return_value={"config": {
        "required": False, "approver_source": {"type": "explicit_user", "user_id": "manager"}}}))
    ticket = SimpleNamespace(custom_fields={"request_template": {"key": "printer", "scenario_processing": {
        "approval_required": True}, "approval_policy": {"required": True}}})
    result = await resolve_effective_ticket_policy(AsyncMock(spec=AsyncSession), ticket, "approval")
    assert result["required"] is True
    assert result["approver_source"]["user_id"] == "manager"


def test_publish_validates_unused_routes_and_calendars():
    from tickets.request_scenario_processing import validate_map_processing_references
    graph = definition()
    raw = graph.model_dump(mode="json")
    raw["processing"]["sla_profiles"]["unused"] = {"title": "Unused", "first_response_minutes": 10,
        "resolution_minutes": 20, "time_basis": "business", "calendar_id": 4}
    graph = ScenarioDefinition.model_validate(raw)
    issues = validate_map_processing_references(graph, [{"code": "printing", "is_active": True}], [{
        "id": 4, "is_active": True, "timezone": "UTC", "weekly_hours_json": []}])
    assert {item["path"] for item in issues} == {"processing.routes.default.queue_code", "processing.sla_profiles.unused.calendar_id"}


@pytest.mark.asyncio
async def test_business_profile_uses_canonical_calendar_engine():
    from datetime import datetime, timezone
    from tickets.request_scenario_processing import apply_scenario_map_processing
    from tickets.sla_service import TicketSlaService
    selected = snapshot()["map_processing"]
    selected["sla_profile"].update(time_basis="business", calendar_id=4)
    calendar = SimpleNamespace(is_active=True, timezone="UTC", holidays_json=[], weekly_hours_json=[
        {"day": day, "start": "09:00", "end": "18:00"} for day in range(5)])
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=True)), get=AsyncMock(return_value=calendar))
    result = await apply_scenario_map_processing(session, {"template_context": {}}, selected)
    service = TicketSlaService(session, None)
    config = result["template_context"]["sla_policy"]
    resolved = await service._calendar_for_policy(config)
    assert service._due_at(datetime(2026, 10, 16, 17, tzinfo=timezone.utc), 120, resolved) == datetime(2026, 10, 19, 10, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_published_calendar_schedule_remains_pinned_but_activity_is_rechecked():
    from tickets.request_scenario_processing import apply_scenario_map_processing
    raw = definition().model_dump(mode="json")
    raw["processing"]["sla_profiles"]["urgent"].update(time_basis="business", calendar_id=4)
    graph = ScenarioDefinition.model_validate(raw)
    frozen = {"id": 4, "is_active": True, "timezone": "UTC", "holidays_json": [],
        "weekly_hours_json": [{"day": 0, "start": "09:00", "end": "18:00"}]}
    selected = build_scenario_submission(graph, RuntimeState("submit", 2, {"affected": "all"}, ["questions"], {}),
        session_id="s", version_id="v", source_snapshot={"business_calendars": [frozen]})[1]["map_processing"]
    changed = SimpleNamespace(**{**frozen, "weekly_hours_json": [{"day": 0, "start": "10:00", "end": "12:00"}]})
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=True)), get=AsyncMock(return_value=changed))
    result = await apply_scenario_map_processing(session, {"template_context": {}}, selected)
    assert result["template_context"]["sla_policy"]["calendar"]["weekly_hours_json"] == frozen["weekly_hours_json"]
    changed.is_active = False
    with pytest.raises(ValueError):
        await apply_scenario_map_processing(session, {"template_context": {}}, selected)


def test_omitted_v3_checkbox_does_not_select_negative_processing_branch():
    from tickets.request_scenario_runtime import ScenarioRuntime
    from web_api.dto.request_scenario import ScenarioAnswerRequest
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"] = [{"key": "affected", "label": "Affected?", "type": "checkbox"}]
    raw["blocks"][0]["transitions"][0]["when"]["value"] = False
    graph = ScenarioDefinition.model_validate(raw)
    runtime = ScenarioRuntime(graph)
    state = runtime.advance(runtime.initial_state(), ScenarioAnswerRequest(expected_block_id="questions", revision=1, answers={}))
    assert "affected" not in state.answers
    chosen = build_scenario_submission(graph, state, session_id="s", version_id="v")[1]["map_processing"]
    assert chosen["sla_profile"]["key"] == "standard"
    assert chosen["condition_trace"][0]["condition_evaluation"]["present"] is False
    assert build_scenario_submission(graph, state, session_id="s", version_id="v")[1]["form_schema"]["fields"] == []
    state = runtime.advance(runtime.initial_state(), ScenarioAnswerRequest(expected_block_id="questions", revision=1, answers={"affected": False}))
    assert build_scenario_submission(graph, state, session_id="s", version_id="v")[1]["map_processing"]["sla_profile"]["key"] == "urgent"


def test_required_v3_checkbox_accepts_explicit_no_but_rejects_missing():
    from tickets.request_scenario_runtime import ScenarioRuntime, ScenarioInputError
    from web_api.dto.request_scenario import ScenarioAnswerRequest
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"] = [{"key": "affected", "label": "Affected?", "type": "checkbox", "required": True}]
    raw["blocks"][0]["transitions"][0]["when"]["value"] = False
    graph = ScenarioDefinition.model_validate(raw)
    runtime = ScenarioRuntime(graph)
    with pytest.raises(ScenarioInputError):
        runtime.advance(runtime.initial_state(), ScenarioAnswerRequest(expected_block_id="questions", revision=1, answers={}))
    state = runtime.advance(runtime.initial_state(), ScenarioAnswerRequest(expected_block_id="questions", revision=1, answers={"affected": False}))
    _, submitted = build_scenario_submission(graph, state, session_id="s", version_id="v")
    assert submitted["answers"]["affected"] is False
    assert submitted["form_schema"]["fields"][0]["required"] is False


@pytest.mark.parametrize("start,end", [("0900", "1800"), ("09:00:00.1", "18:00"), ("09:00", "09:00")])
def test_calendar_rejects_times_unsupported_by_canonical_engine(start, end):
    from tickets.request_scenario_processing import validated_scenario_calendar
    with pytest.raises(ValueError):
        validated_scenario_calendar({"is_active": True, "timezone": "UTC", "weekly_hours_json": [{"day": 0, "start": start, "end": end}]})


def test_calendar_orders_slots_and_rejects_overlapping_intervals():
    from tickets.request_scenario_processing import validated_scenario_calendar
    calendar = {"is_active": True, "timezone": "UTC", "weekly_hours_json": [
        {"day": 0, "start": "13:00", "end": "18:00"}, {"day": 0, "start": "09:00", "end": "12:00"}]}
    assert validated_scenario_calendar(calendar)["weekly_hours_json"][0]["start"] == "09:00"
    calendar["weekly_hours_json"][1]["end"] = "14:00"
    with pytest.raises(ValueError):
        validated_scenario_calendar(calendar)


@pytest.mark.asyncio
@pytest.mark.parametrize("identities,expected", [(["manager-login"], ["manager-login"]), ([], []), (["first", "second"], [])])
async def test_requester_manager_uses_trusted_registry_and_rejects_ambiguous_identity(monkeypatch, identities, expected):
    from sqlalchemy.ext.asyncio import AsyncSession
    from tickets.approval_policy import _resolve_approval_source
    from requester.identity_service import RequesterIdentityResolver
    from app.repos.ui_users_repo import UiUsersRepo
    monkeypatch.setattr(UiUsersRepo, "get_by_login", AsyncMock(return_value=SimpleNamespace(user_login="manager-login", actor_role="admin", is_active=True)))
    import access_control.service as access
    monkeypatch.setattr(access, "can", AsyncMock(return_value=True))
    resolver = AsyncMock(return_value=SimpleNamespace(person_id="employee", metadata_json={"manager_person_id": "manager"}))
    monkeypatch.setattr(RequesterIdentityResolver, "resolve_person_for_web_user", resolver)
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = SimpleNamespace(person_id="manager", status="active")
    session.scalars.return_value = SimpleNamespace(all=lambda: identities)
    source, values = await _resolve_approval_source(session, SimpleNamespace(requester_id="trusted-actor", custom_fields={
        "request_form_data": {"manager_id": "forged-manager", "requester_id": "forged-actor"}}), {"type": "requester_manager"})
    assert source == "requester_manager"
    assert values == expected
    resolver.assert_awaited_once_with("trusted-actor")


@pytest.mark.asyncio
@pytest.mark.parametrize("account,permission,queue_allowed", [
    (None, True, True), (SimpleNamespace(user_login="manager-login", actor_role="admin", is_active=False), True, True),
    (SimpleNamespace(user_login="manager-login", actor_role="user", is_active=True), True, True),
    (SimpleNamespace(user_login="manager-login", actor_role="support", is_active=True), False, True),
    (SimpleNamespace(user_login="manager-login", actor_role="support", is_active=True), True, False),
])
async def test_registry_manager_without_canonical_decision_access_is_unavailable(monkeypatch, account, permission, queue_allowed):
    from sqlalchemy.ext.asyncio import AsyncSession
    from tickets.approval_policy import _resolve_approval_source
    from requester.identity_service import RequesterIdentityResolver
    from app.repos.ui_users_repo import UiUsersRepo
    from app.repos.ticket_events_repo import TicketEventsRepo
    import access_control.service as access
    monkeypatch.setattr(RequesterIdentityResolver, "resolve_person_for_web_user", AsyncMock(return_value=SimpleNamespace(metadata_json={"manager_person_id": "manager"})))
    monkeypatch.setattr(UiUsersRepo, "get_by_login", AsyncMock(return_value=account))
    monkeypatch.setattr(access, "can", AsyncMock(return_value=permission))
    monkeypatch.setattr(TicketEventsRepo, "is_actor_in_queue", AsyncMock(return_value=queue_allowed))
    session = AsyncMock(spec=AsyncSession)
    session.get.return_value = SimpleNamespace(person_id="manager", status="active")
    session.scalars.return_value = SimpleNamespace(all=lambda: ["manager-login"])
    _, values = await _resolve_approval_source(session, SimpleNamespace(requester_id="employee", custom_fields={}, queue_id=7, assignee_id=None), {"type": "requester_manager"})
    assert values == []
