"""Readiness is a bounded publish gate, independent of policy health."""
from copy import deepcopy
import pytest
from tickets.request_scenario_runtime import RuntimeState
from web_api.dto.request_scenario import ScenarioDefinition
from tests.test_request_scenario_submission import definition

pytestmark = pytest.mark.no_db


def _branch_definition(field, transitions):
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"] = [field]
    raw["blocks"][0]["transitions"] = transitions
    raw["blocks"] = [raw["blocks"][0], *[{"id": key, "kind": "submit_ticket", "title": key} for key in dict.fromkeys(edge["to"] for edge in transitions)]]
    return ScenarioDefinition.model_validate(raw)


def test_readiness_covers_every_multiselect_subset_including_combined_answers():
    from tickets.request_scenario_readiness import submission_variants
    graph = _branch_definition({"key": "choices", "type": "multi_select", "label": "Choices", "options": [{"value": key, "label": key} for key in ("a", "b")], "process_mapping": {"roles": ["routing_field"]}}, [{"to": "submit"}])
    states = submission_variants(graph)
    assert {tuple(state.answers.get("choices", [])) for state in states} == {(), ("a",), ("b",), ("a", "b"), ("b", "a")}


def test_readiness_numeric_graph_conditions_cover_boundary_and_both_intervals():
    from tickets.request_scenario_readiness import submission_variants
    graph = _branch_definition({"key": "amount", "type": "number", "label": "Amount", "required": True, "validation": {"min_value": 2, "max_value": 4}}, [
        {"to": target, "when": {"source": "answer", "field": "amount", "op": op, "value": 3}, "priority": index + 1} for index, (target, op) in enumerate((("low", "lt"), ("equal", "eq"), ("high", "gt")))
    ] + [{"to": "equal"}])
    states = submission_variants(graph)
    assert {state.current_block_id for state in states} == {"low", "equal", "high"}
    assert all(2 <= state.answers["amount"] <= 4 for state in states)


def test_readiness_text_graph_conditions_cover_literal_other_and_missing():
    from tickets.request_scenario_readiness import submission_variants
    graph = _branch_definition({"key": "text", "type": "text", "label": "Text", "validation": {"min_length": 2, "max_length": 4}}, [
        {"to": "special", "when": {"source": "answer", "field": "text", "op": "eq", "value": "VIP"}}, {"to": "other"}])
    states = submission_variants(graph)
    assert {state.current_block_id for state in states} == {"special", "other"}
    assert any("text" not in state.answers for state in states)
    assert any(state.answers.get("text") not in (None, "VIP") for state in states)


@pytest.mark.parametrize("kind", ["text", "number", "select", "radio"])
def test_readiness_distinguishes_explicit_unknown_from_omitted_optional_answer(kind):
    from tickets.request_scenario_readiness import submission_variants
    field = {"key": "text", "type": kind, "label": "Text", "allow_unknown": True}
    if kind in {"select", "radio"}:
        field["options"] = [{"value": "a", "label": "A"}]
    graph = _branch_definition(field, [
        {"to": "unknown", "when": {"source": "answer", "field": "text", "op": "eq", "value": None}, "priority": 1},
        {"to": "known", "when": {"source": "answer", "field": "text", "op": "neq", "value": None}, "priority": 2}, {"to": "omitted"}])
    states = submission_variants(graph)
    assert {state.current_block_id for state in states} == {"unknown", "known", "omitted"}
    assert any(state.current_block_id == "unknown" and state.answers["text"] is None for state in states)
    assert any(state.current_block_id == "omitted" and "text" not in state.answers for state in states)


def test_readiness_ordinary_representatives_obey_constraints_and_url_type():
    from tickets.request_scenario_readiness import submission_variants
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"] = [
        {"key": "amount", "type": "number", "label": "Amount", "required": True, "validation": {"min_value": 30, "max_value": 40}},
        {"key": "text", "type": "text", "label": "Text", "required": True, "validation": {"min_length": 1, "max_length": 2}},
        {"key": "url", "type": "url", "label": "URL", "required": True}]
    assert submission_variants(ScenarioDefinition.model_validate(raw))


def test_readiness_still_rejects_unbounded_numeric_policy_and_large_multiselect():
    from tickets.request_scenario_readiness import submission_variants, ReadinessCoverageError
    graph = _branch_definition({"key": "amount", "type": "number", "label": "Amount"}, [{"to": "submit"}])
    with pytest.raises(ReadinessCoverageError): submission_variants(graph, process_fields={"amount"})
    graph = _branch_definition({"key": "choices", "type": "multi_select", "label": "Choices", "options": [{"value": str(n), "label": str(n)} for n in range(10)], "process_mapping": {"roles": ["routing_field"]}}, [{"to": "submit"}])
    with pytest.raises(ReadinessCoverageError): submission_variants(graph)


@pytest.mark.asyncio
@pytest.mark.parametrize("trusted", [False, True])
async def test_policy_simulation_uses_canonical_type_and_taxonomy_only_for_trusted_context(monkeypatch, trusted):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets import policy_health_service as module
    template = {"template_code": "printer", "ticket_type": "incident", "category_id": 1, "service_id": 2, "subcategory_id": 3}
    repo = SimpleNamespace(resolve_effective_request_template=AsyncMock(return_value={"request_template": template}))
    monkeypatch.setattr(module, "HelpdeskPolicyRepo", lambda _: repo)
    monkeypatch.setattr(module, "TicketEventsRepo", lambda _: object())
    monkeypatch.setattr(module, "TicketAdminConfigRepo", lambda _: object())
    monkeypatch.setattr(module, "apply_effective_registry_policies", AsyncMock(side_effect=lambda _, value: value))
    captured = []
    normalized = []
    def priority(**kwargs):
        normalized.append(kwargs["submitted_values"])
        return {"priority_class": "P3", "legacy_priority": "P4"}
    monkeypatch.setattr(module, "compute_priority_from_policy", priority)
    async def inspect(ticket, **_):
        captured.append(ticket)
        raise ValueError("stop after routing input")
    monkeypatch.setattr(module, "TicketRoutingService", lambda *_: SimpleNamespace(resolve_routing_decision=inspect))
    canonical = {"ticket_type": "service_request", "submitted_values": {},
        "template_context": {"key": "printer", "ticket_type": "service_request", "category_id": 11, "service_id": 12, "subcategory_id": 13}}
    with pytest.raises(ValueError, match="stop after routing input"):
        await module.PolicyHealthService(object()).simulate({"template_code": "printer", "request_form_data": {"hidden_policy_fact": True}}, **({"validated_submission": canonical} if trusted else {}))
    ticket = captured[0]
    assert (ticket.ticket_type, ticket.category_id, ticket.service_id, ticket.subcategory_id) == (
        ("service_request", 11, 12, 13) if trusted else ("incident", 1, 2, 3))
    assert normalized == ([{}] if trusted else [{"hidden_policy_fact": True}])


@pytest.mark.asyncio
async def test_processing_dry_run_uses_returned_canonical_policy_overlay(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets import service_catalog_preview as module
    selection = SimpleNamespace(request_template_key="printer", service={}, offering={})
    resolver = SimpleNamespace(resolve_selection=AsyncMock(return_value=selection),
        apply_to_validated_submission=AsyncMock(return_value={"submitted_values": {"affected_scope": "team"}}))
    canonical = {"submitted_values": {"affected_scope": "team"}, "template_context": {"sla_policy_id": 42}}
    health = SimpleNamespace(simulate=AsyncMock(return_value={"sla": {"resolution_min": 120}}))
    monkeypatch.setattr(module, "ServiceCatalogRuntimeResolver", lambda _: resolver)
    monkeypatch.setattr(module, "resolve_create_form_submission", AsyncMock(return_value={}))
    monkeypatch.setattr(module, "apply_effective_registry_policies", AsyncMock(return_value=canonical))
    monkeypatch.setattr(module, "PolicyHealthService", lambda _: health)
    _, result = await module.simulate_service_catalog_processing(object(), {"offering_full_code": "workplace.printer", "allow_draft_offering": True})
    assert resolver.resolve_selection.call_args.kwargs["actor_role"] == "requester"
    assert result["sla"]["resolution_min"] == 120
    assert health.simulate.call_args.kwargs["validated_submission"] == canonical


def test_isolated_full_cleanup_does_not_retain_used_publication_tokens():
    from tests.conftest import _cleanup_tables_for_profile
    assert "request_studio_publish_tokens" in _cleanup_tables_for_profile("full")


@pytest.mark.asyncio
async def test_publication_freezes_business_calendar_source():
    from types import SimpleNamespace
    from tickets.request_scenario_publication import ScenarioPublicationService
    calls = []
    class Session:
        async def execute(self, statement): calls.append(str(statement))
    await ScenarioPublicationService(SimpleNamespace(session=Session()))._freeze_sources()
    assert "ticket_business_calendars" in calls[0]


@pytest.mark.asyncio
async def test_catalog_promotion_acquires_write_compatible_source_lock():
    from types import SimpleNamespace
    from tickets.request_scenario_publication import ScenarioPublicationService
    calls = []
    class Session:
        async def execute(self, statement): calls.append(str(statement))
    await ScenarioPublicationService(SimpleNamespace(session=Session()))._freeze_sources(write_offering=True)
    assert calls[0].endswith("IN SHARE ROW EXCLUSIVE MODE")


@pytest.mark.asyncio
@pytest.mark.parametrize("service_status,service_visibility,offering_status,offering_visibility", [
    ("draft", "public", "draft", "public"), ("published", "internal", "draft", "public"),
    ("published", "public", "retired", "public"), ("published", "public", "draft", "internal")])
async def test_internal_candidate_preview_cannot_bypass_public_parent_and_visibility(monkeypatch, service_status, service_visibility, offering_status, offering_visibility):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets import service_catalog_preview as module
    selection = SimpleNamespace(service={"lifecycle_status": service_status, "visibility": service_visibility},
        offering={"lifecycle_status": offering_status, "visibility": offering_visibility})
    resolver = SimpleNamespace(resolve_selection=AsyncMock(return_value=selection))
    monkeypatch.setattr(module, "ServiceCatalogRuntimeResolver", lambda _: resolver)
    with pytest.raises(module.ServiceCatalogPreviewError):
        await module.simulate_service_catalog_processing(object(), {}, allow_draft_offering=True)


def test_optional_instruction_checks_both_acknowledgment_outcomes():
    from tickets.request_scenario_readiness import submission_variants
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["transitions"] = [{"to": "instruction"}]
    raw["blocks"].extend([
        {"id": "instruction", "kind": "instruction", "title": "Optional", "acknowledgment_required": False,
         "content": {"format": "plain", "body": "Try this"}, "transitions": [
             {"to": "ack_submit", "when": {"source": "current_result", "op": "eq", "value": "acknowledged"}}, {"to": "submit"}]},
        {"id": "ack_submit", "kind": "submit_ticket", "title": "Acknowledged"},
    ])
    assert {state.current_block_id for state in submission_variants(ScenarioDefinition.model_validate(raw))} == {"submit", "ack_submit"}


def test_priority_importance_and_modifiers_are_actual_process_inputs():
    from tickets.request_scenario_publication import _policy_fields
    assert _policy_fields({"importance_field": "is_important", "modifier_fields": {"vip": "is_vip", "deadline": "deadline_fact"}}) >= {"is_important", "is_vip", "deadline_fact"}


def test_publication_diff_exposes_changed_questions_conditions_and_order():
    from tickets.request_scenario_publication import scenario_diff
    before = definition().model_dump(mode="json")
    after = deepcopy(before)
    after["blocks"][0]["fields"][0]["label"] = "New question"
    after["blocks"][0]["transitions"][0]["to"] = "review"
    changes = scenario_diff(before, after)
    assert any(change["path"].endswith("summary.label") and change["after"] == "New question" for change in changes)
    assert any(change["path"].endswith("transitions") and change["before"] != change["after"] for change in changes)


@pytest.mark.asyncio
async def test_admin_simulator_projects_current_conditions_without_advancing():
    from types import SimpleNamespace
    from app.repos.request_scenario_repo import RequestScenarioRepo
    from web_api.dto.request_scenario_admin import SimulationInput
    repo = RequestScenarioRepo(None, None)
    async def detail(identifier):
        return SimpleNamespace(archived=False), SimpleNamespace(revision=1, definition=definition().model_dump(mode="json"))
    repo.detail = detail
    payload = SimulationInput.model_validate({"revision": 1, "preview": {"expected_block_id": "questions", "revision": 1, "answers": {"urgent": True}}})
    result = await repo.simulate("scenario", payload)
    assert result["state"]["answers"] == {} and result["state"]["revision"] == 1
    assert "hidden" in {field["key"] for field in result["current_step"]["fields"]}


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["routing", "sla", "approval", "closure", "visibility", "selected_sla"])
async def test_policy_health_ok_does_not_hide_processing_blocker(monkeypatch, missing):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tickets import request_scenario_publication as module
    class Health:
        def __init__(self, session=None): pass
        def evaluate(self, **kwargs): return {"templates": [{"health_status": "ok"}]}
        async def simulate(self, payload):
            return {"routing": {"queue_id": None if missing == "routing" and payload["request_form_data"].get("is_urgent") else 1},
                    "sla": {} if missing in {"sla", "selected_sla"} else {"resolution_min": 30},
                    "approval": {"required": missing == "approval", "approvers": []}, "priority": {"priority_class": "P2"}}
    monkeypatch.setattr(module, "PolicyHealthService", Health)
    async def simulate(session, payload, *, scenario_snapshot):
        return None, await Health().simulate({"request_form_data": scenario_snapshot["facts"]})
    monkeypatch.setattr(module, "simulate_service_catalog_processing", simulate)
    source = {"effective_template": {"request_template": {"published_at": "now", "config": {}},
        "resolved_policies": {key: {"configured": True} for key in ("closure", "visibility") if key != missing}},
        "policies": {}, "queues": [], "service": {"lifecycle_status": "published", "visibility": "public"},
        "offering": {"lifecycle_status": "published", "visibility": "public", "request_template_key": "printer"}, "taxonomy": []}
    row = SimpleNamespace(archived=False, category_id=None, offering_full_code="workplace.printer")
    draft = SimpleNamespace(definition=definition().model_dump(mode="json"))
    if missing == "selected_sla":
        from tickets import request_scenario_processing
        monkeypatch.setattr(request_scenario_processing, "apply_scenario_policy_refs", AsyncMock(return_value={"template_context": {"sla_policy": {"targets": []}}}))
        draft.definition["process_binding"]["policy_refs"] = {"sla": "selected"}
        source["effective_template"]["request_template"]["config"] = {"no_sla": True}
    result = await module.ScenarioPublicationService(SimpleNamespace(session=None))._assess(row, draft, source)
    assert result["health"]["health_status"] == "ok" and not result["readiness"]["can_publish"]
    assert any(issue["code"].startswith("sla" if missing == "selected_sla" else missing) for issue in result["readiness"]["issues"])


@pytest.mark.asyncio
async def test_confirmation_is_bound_to_scope_actor_sources_expiry_and_single_use():
    from datetime import datetime, timedelta, timezone
    from auth.context import AuthContext, AuthType
    from tickets.request_studio_publication import RequestStudioPublicationService, RequestStudioConfirmationError
    class Session:
        def add(self, value): self.row = value
        async def flush(self): pass
        async def execute(self, statement): return self
        def scalar_one_or_none(self): return self.row
    session = Session()
    service = RequestStudioPublicationService(session)
    auth = AuthContext(actor_id="admin", actor_role="admin", auth_type=AuthType.UI_TOKEN)
    token, _ = await service.issue_bound_confirmation_token("a" * 64, scope="request_scenario.publish", auth_context=auth, summary={})
    assert await service.validate_bound_confirmation_token(token, "a" * 64, scope="request_scenario.publish", auth_context=auth) is session.row
    other = AuthContext(actor_id="other", actor_role="admin", auth_type=AuthType.UI_TOKEN)
    for value, digest, scope, actor in [("invalid", "a" * 64, "request_scenario.publish", auth),
            (token, "b" * 64, "request_scenario.publish", auth), (token, "a" * 64, "request_studio.publish", auth),
            (token, "a" * 64, "request_scenario.publish", other)]:
        with pytest.raises(RequestStudioConfirmationError):
            await service.validate_bound_confirmation_token(value, digest, scope=scope, auth_context=actor)
    session.row.used_at = datetime.now(timezone.utc)
    with pytest.raises(RequestStudioConfirmationError) as exc:
        await service.validate_bound_confirmation_token(token, "a" * 64, scope="request_scenario.publish", auth_context=auth)
    assert exc.value.error_code == "CONFIRMATION_TOKEN_USED"
    session.row.used_at = None
    session.row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(RequestStudioConfirmationError) as exc:
        await service.validate_bound_confirmation_token(token, "a" * 64, scope="request_scenario.publish", auth_context=auth)
    assert exc.value.error_code == "CONFIRMATION_TOKEN_EXPIRED"


def test_all_typed_variants_use_canonical_runtime_and_prune_hidden_values():
    from tickets.request_scenario_readiness import submission_variants
    states = submission_variants(definition())
    assert all(isinstance(state, RuntimeState) and state.current_block_id == "submit" for state in states)
    assert {state.answers["urgent"] for state in states} == {True, False}
    assert all("hidden" not in state.answers for state in states if not state.answers["urgent"])


def test_readiness_rejects_unbounded_policy_domain_and_combinatorial_explosion():
    from tickets.request_scenario_readiness import ReadinessCoverageError, submission_variants
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"][0]["process_mapping"] = {"roles": ["routing_field"]}
    with pytest.raises(ReadinessCoverageError):
        submission_variants(ScenarioDefinition.model_validate(raw))
    raw = definition().model_dump(mode="json")
    raw["blocks"][0]["fields"] = [dict(deepcopy(raw["blocks"][0]["fields"][1]), key=f"choice_{n}") for n in range(10)]
    for field in raw["blocks"][0]["fields"]:
        field["process_mapping"]["fact_key"] = field["key"]
    with pytest.raises(ReadinessCoverageError):
        submission_variants(ScenarioDefinition.model_validate(raw))


def test_publish_command_requires_real_confirmation_and_rejects_client_sources():
    from pydantic import ValidationError
    from web_api.dto.request_scenario_admin import ScenarioPublish
    assert ScenarioPublish.model_validate({"revision": 1, "confirmation_token": "token", "confirm": True}).confirm
    for extra in ({"confirm": 1}, {"confirm": False}, {"source_snapshot": {}}, {"actor_id": "other"}):
        with pytest.raises(ValidationError):
            ScenarioPublish.model_validate({"revision": 1, "confirmation_token": "token", "confirm": True, **extra})
