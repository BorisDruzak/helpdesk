"""V4 map omissions inherit canonical service policy, proved per retained path."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_request_scenario_terminal_sla import graph, submission
from tickets.request_scenario_processing import apply_scenario_map_processing
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def inherited_graph():
    raw = graph()
    raw["processing"]["defaults"] = {"route": "", "sla_profile": ""}
    raw["processing"]["sla_profiles"] = {}
    raw["blocks"][0]["transitions"] = [{"to": "submit"}]
    raw["blocks"].append({"id": "weights", "kind": "sla_attachment", "title": "Влияние",
        "attached_to": "questions", "processing_facts": {"impact": "department", "urgency": "blocked"}})
    return raw


def test_v4_weights_only_uses_service_policy_without_inventing_map_defaults():
    raw = inherited_graph()
    assert not validate_scenario(ScenarioDefinition.model_validate(raw))
    snapshot = submission(raw)
    assert snapshot["processing_facts"] == {"impact": "department", "urgency": "blocked"}
    assert snapshot["map_processing"]["route"] is None
    assert snapshot["map_processing"]["sla_profile"] is None
    assert raw["processing"]["defaults"] == {"route": "", "sla_profile": ""}


def test_explicit_paths_and_terminal_profiles_do_not_require_map_defaults():
    raw = graph()
    raw["processing"]["defaults"] = {"route": "", "sla_profile": ""}
    raw["blocks"][0]["transitions"][1]["processing"] = {"route": "default", "sla_profile": "standard"}
    assert not validate_scenario(ScenarioDefinition.model_validate(raw))
    assert submission(raw, "all")["map_processing"]["sla_profile"]["key"] == "urgent"
    assert submission(raw, "one")["map_processing"]["sla_profile"]["key"] == "standard"
    next(block for block in raw["blocks"] if block["id"] == "submit")["sla_profile"] = "standard"
    assert submission(raw, "all")["map_processing"]["sla_profile"]["source"]["kind"] == "terminal"


@pytest.mark.parametrize("version", [3, 4])
def test_nonempty_unknown_default_stays_strict(version):
    raw = graph()
    raw["schema_version"] = version
    if version == 3:
        raw.pop("execution_semantics")
    raw["processing"]["defaults"]["route"] = "absent"
    assert any(issue.path == "processing.defaults.route" for issue in validate_scenario(ScenarioDefinition.model_validate(raw)))


def test_v3_empty_defaults_retain_old_validation():
    raw = graph()
    raw.update(schema_version=3)
    raw.pop("execution_semantics")
    raw["processing"]["defaults"] = {"route": "", "sla_profile": ""}
    assert len([issue for issue in validate_scenario(ScenarioDefinition.model_validate(raw)) if issue.code == "processing_default_missing"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("selected_kind", [None, "route", "sla_profile"])
async def test_adapter_preserves_independently_inherited_policies_and_sources(selected_kind):
    original = {"template_context": {"routing_policy": {"fallback": {"queue_id": 9}},
        "sla_policy": {"legacy_sla_policy_id": 12}, "sla_policy_id": 12,
        "policy_refs": {"routing": {"code": "canonical-route"}, "sla": {"code": "canonical-sla"}},
        "effective_policy_sources": {"sla": ["service"], "routing": ["service"]}}}
    selection = submission(graph())["map_processing"]
    for kind in ("route", "sla_profile"):
        if kind != selected_kind:
            selection[kind] = None
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="printing", is_active=True)))
    context = (await apply_scenario_map_processing(session, original, selection))["template_context"]
    for kind, key in (("routing", "route"), ("sla", "sla_profile")):
        if key != selected_kind:
            assert context[kind + "_policy"] == original["template_context"][kind + "_policy"]
            assert context["policy_refs"][kind] == original["template_context"]["policy_refs"][kind]
            assert context["effective_policy_sources"][kind] == ["service"]
        else:
            assert kind not in context["policy_refs"]
    if selected_kind != "sla_profile":
        assert context["sla_policy_id"] == 12
    if selected_kind != "route":
        session.scalar.assert_not_called()


def assessment_source():
    return {"effective_template": {"request_template": {"published_at": "now", "config": {}},
        "resolved_policies": {"closure": {"configured": True}, "visibility": {"configured": True}}},
        "policies": {}, "queues": [{"id": 1, "code": "first_line", "is_active": True}, {"id": 2, "code": "printing", "is_active": True}],
        "business_calendars": [], "service": {"lifecycle_status": "published", "visibility": "public"},
        "offering": {"lifecycle_status": "published", "visibility": "public", "request_template_key": "printer"}, "taxonomy": []}


async def assess(monkeypatch, raw, *, missing=None, traversal_error=None, processing_error=None):
    from tickets import request_scenario_publication as module
    monkeypatch.setattr(module, "PolicyHealthService", lambda: SimpleNamespace(evaluate=lambda **kw: {"templates": [{"health_status": "ok"}]}))
    async def simulate(session, payload, *, scenario_snapshot):
        if processing_error:
            raise processing_error
        return None, {"routing": {"queue_id": None if missing == "route" else 1},
            "sla": {} if missing == "sla" else {"first_response_min": 0 if missing == "first_response" else 10, "resolution_min": 30},
            "approval": {}, "priority": {}, "map_processing": scenario_snapshot["map_processing"]}
    monkeypatch.setattr(module, "simulate_service_catalog_processing", simulate)
    if traversal_error:
        monkeypatch.setattr(module, "submission_variants", lambda *a, **kw: (_ for _ in ()).throw(traversal_error))
    row = SimpleNamespace(id="scenario", archived=False, category_id=None, offering_full_code="workplace.printer")
    return await module.ScenarioPublicationService(SimpleNamespace(session=None))._assess(row, SimpleNamespace(definition=raw), assessment_source())


@pytest.mark.asyncio
async def test_publication_accepts_weights_when_canonical_outcomes_are_proven(monkeypatch):
    result = await assess(monkeypatch, inherited_graph())
    assert result["readiness"]["can_publish"], result["readiness"]
    assert result["readiness"]["variants_checked"] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("missing,code,word", [("route", "routing_unavailable", "очеред"), ("sla", "sla_unavailable", "SLA"), ("first_response", "sla_unavailable", "SLA")])
async def test_uncovered_policy_explains_actual_terminal_and_path(monkeypatch, missing, code, word):
    raw = inherited_graph()
    result = await assess(monkeypatch, raw, missing=missing)
    issues = result["readiness"]["issues"]
    assert not result["readiness"]["can_publish"]
    issue = next(issue for issue in issues if issue["code"] == code)
    assert issue["path"] == "blocks.submit"
    assert word in issue["message"]
    assert all(next(block for block in raw["blocks"] if block["id"] == identifier)["title"] in issue["message"] for identifier in ("questions", "submit"))
    assert not any(issue["code"] == "processing_default_missing" for issue in issues)


@pytest.mark.asyncio
async def test_issue_labels_distinguish_two_paths_to_the_same_terminal(monkeypatch):
    raw = inherited_graph()
    raw["blocks"][0]["title"] = "Кого затронула проблема"
    next(block for block in raw["blocks"] if block["id"] == "submit")["title"] = "Передать в поддержку"
    raw["blocks"][0]["transitions"] = [
        {"to": "branch_department", "when": {"source": "answer", "field": "affected", "op": "eq", "value": "all"}},
        {"to": "branch_person"},
    ]
    raw["blocks"].extend([
        {"id": "branch_department", "kind": "decision", "title": "Весь отдел", "transitions": [{"to": "submit"}]},
        {"id": "branch_person", "kind": "decision", "title": "Один сотрудник", "transitions": [{"to": "submit"}]},
    ])
    result = await assess(monkeypatch, raw, missing="sla")
    issues = [issue for issue in result["readiness"]["issues"] if issue["code"] == "sla_unavailable"]
    assert len(issues) == 2 and all(issue["path"] == "blocks.submit" for issue in issues)
    assert any("Кого затронула проблема → Весь отдел → Передать в поддержку" in issue["message"] for issue in issues)
    assert any("Кого затронула проблема → Один сотрудник → Передать в поддержку" in issue["message"] for issue in issues)
    assert all("branch_" not in issue["message"] and "«Передать в поддержку»" in issue["message"] for issue in issues)


@pytest.mark.asyncio
@pytest.mark.parametrize("coverage_error", [True, False])
async def test_aborted_traversal_does_not_claim_submission_unreachable(monkeypatch, coverage_error):
    from tickets.request_scenario_readiness import ReadinessCoverageError
    raw = inherited_graph()
    if not coverage_error:
        raw["blocks"][0]["transitions"] = []
    result = await assess(monkeypatch, raw, traversal_error=ReadinessCoverageError("Лимит проверки") if coverage_error else None)
    assert result["readiness"]["variants_checked"] == 0
    assert "submission_unreachable" not in {issue["code"] for issue in result["readiness"]["issues"]}


def test_fallback_registry_refs_are_only_used_for_inherited_map_kind():
    raw = inherited_graph()
    raw["process_binding"]["policy_refs"] = {"routing": "canonical", "sla": "canonical"}
    assert submission(raw)["policy_refs"] == {"routing": "canonical", "sla": "canonical"}
    next(block for block in raw["blocks"] if block["id"] == "submit")["route"] = "printing"
    assert submission(raw)["policy_refs"] == {"sla": "canonical"}


@pytest.mark.asyncio
@pytest.mark.parametrize("selected_kind", [None, "route", "sla_profile"])
async def test_canonical_recomposition_only_pins_explicit_map_kind(monkeypatch, selected_kind):
    from tickets import helpdesk_policy_runtime as runtime
    selected = {"route": None, "sla_profile": None}
    if selected_kind:
        selected[selected_kind] = {"key": "map"}
    inherited = {"routing_policy": {"fallback": {"queue_id": 1}}, "sla_policy": {"targets": {"resolution": {"P2": 30}}}}
    canonical = {"routing": {"fallback": {"queue_id": 2}}, "sla": {"targets": {"resolution": {"P2": 60}}}}
    repo = SimpleNamespace(resolve_effective_request_template=AsyncMock(return_value={"request_template": {}, "resolved_policies": canonical}))
    monkeypatch.setattr(runtime, "HelpdeskPolicyRepo", lambda _: repo)
    result = await runtime.apply_effective_registry_policies(SimpleNamespace(), {"template_context": {**deepcopy(inherited), "scenario_processing": selected}})
    context = result["template_context"]
    for kind, key in (("routing", "route"), ("sla", "sla_profile")):
        assert context[kind + "_policy"] == (inherited[kind + "_policy"] if key == selected_kind else canonical[kind])


@pytest.mark.asyncio
async def test_actual_create_cannot_continue_without_inherited_sla_deadlines(monkeypatch):
    from tickets import create_flow
    ticket = SimpleNamespace(ticket_id="t", device_id=None, queue_id=1,
        custom_fields={"request_template": {"scenario_processing": {"route": None, "sla_profile": None}}},
        first_response_due_at=None, resolution_due_at=None)
    repo = SimpleNamespace(get_ticket=AsyncMock(return_value=ticket))
    monkeypatch.setattr(create_flow, "TicketRoutingService", lambda *args: SimpleNamespace(apply_routing=AsyncMock()))
    monkeypatch.setattr(create_flow, "TicketSlaService", lambda *args: SimpleNamespace(start_sla=AsyncMock()))
    monkeypatch.setattr("tickets.service_catalog_preview.lock_active_scenario_queue", AsyncMock(return_value=True))
    downstream = AsyncMock(side_effect=AssertionError("Uncovered SLA reached downstream work"))
    monkeypatch.setattr(create_flow, "start_ola_for_ticket", downstream)
    with pytest.raises(create_flow.TicketInitializationError) as error:
        await create_flow.apply_create_side_effects(SimpleNamespace(), repo, ticket, require_active_queue=True)
    assert error.value.stage == "sla"
    downstream.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,code", [("sla", "sla_unavailable"), ("routing", "routing_unavailable")])
async def test_invalid_inherited_registry_reference_explains_policy_kind(monkeypatch, kind, code):
    from tickets.service_catalog_preview import ServiceCatalogPreviewError
    result = await assess(monkeypatch, inherited_graph(), processing_error=ServiceCatalogPreviewError({"form_payload": {"policy_refs." + kind: "unavailable"}}))
    assert any(issue["code"] == code and issue["path"] == "blocks.submit" for issue in result["readiness"]["issues"])
