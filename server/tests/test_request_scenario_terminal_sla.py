"""Terminal SLA is optional v4 authority, applied after the retained route."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_request_scenario_v3_processing import definition
from tickets.request_scenario_runtime import RuntimeState
from tickets.request_scenario_submission import build_scenario_submission
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition

pytestmark = pytest.mark.no_db


def graph(**terminal):
    raw = definition().model_dump(mode="json")
    raw.update(schema_version=4, execution_semantics=3)
    next(block for block in raw["blocks"] if block["id"] == "submit").update(terminal)
    return raw


def submission(raw, value="all"):
    return build_scenario_submission(ScenarioDefinition.model_validate(raw),
        RuntimeState("submit", 2, {"affected": value}, ["questions"], {}), session_id="s", version_id="v")[1]


def test_terminal_profile_wins_after_actual_branch_and_preserves_route():
    snapshot = submission(graph(sla_profile="standard"))
    assert snapshot["map_processing"]["route"]["key"] == "printing"
    assert snapshot["map_processing"]["sla_profile"]["key"] == "standard"
    assert snapshot["map_processing"]["sla_profile"]["source"] == {"kind": "terminal", "block_id": "submit"}
    assert snapshot["map_processing"]["sla_profile"]["first_response_minutes"] == 60


def test_terminal_omission_preserves_inherited_actual_branch_and_wire_format():
    raw = graph()
    value = ScenarioDefinition.model_validate(raw)
    submit = next(block for block in value.model_dump(mode="json")["blocks"] if block["id"] == "submit")
    assert "sla_profile" not in submit and "policy_ref" not in submit
    assert submission(raw)["map_processing"]["sla_profile"]["key"] == "urgent"
    assert submission(raw, "one")["map_processing"]["sla_profile"]["key"] == "standard"


@pytest.mark.parametrize("terminal_profile,expected", [(None, "urgent"), ("standard", "standard")])
def test_last_visited_sla_block_wins_then_terminal_override_wins(terminal_profile, expected):
    raw = graph(**({"sla_profile": terminal_profile} if terminal_profile else {}))
    raw["blocks"][0]["transitions"] = [{"to": "first_sla"}]
    raw["blocks"].extend([
        {"id": "first_sla", "kind": "sla", "title": "First", "sla_profile": "standard", "transitions": [{"to": "last_sla"}]},
        {"id": "last_sla", "kind": "sla", "title": "Last", "sla_profile": "urgent", "transitions": [{"to": "submit"}]},
    ])
    state = RuntimeState("submit", 4, {"affected": "one"}, ["questions", "first_sla", "last_sla"], {})
    snapshot = build_scenario_submission(ScenarioDefinition.model_validate(raw), state, session_id="s", version_id="v")[1]
    assert snapshot["map_processing"]["sla_profile"]["key"] == expected
    assert snapshot["map_processing"]["sla_profile"]["source"] == {"kind": "terminal" if terminal_profile else "block", "block_id": "submit" if terminal_profile else "last_sla"}


def test_edge_sla_after_block_wins_and_unvisited_route_contributes_nothing():
    raw = graph()
    raw["blocks"][0]["transitions"][0].update(to="sla_block")
    raw["blocks"].append({"id": "sla_block", "kind": "sla", "title": "SLA", "sla_profile": "urgent", "transitions": [{"to": "submit", "processing": {"sla_profile": "standard"}}]})
    state = RuntimeState("submit", 3, {"affected": "all"}, ["questions", "sla_block"], {})
    selected = build_scenario_submission(ScenarioDefinition.model_validate(raw), state, session_id="s", version_id="v")[1]["map_processing"]
    assert selected["sla_profile"]["key"] == "standard"
    assert selected["sla_profile"]["source"]["kind"] == "transition"
    inherited = submission(raw, "one")["map_processing"]
    assert inherited["sla_profile"]["key"] == "standard"
    assert inherited["route"]["key"] == "default"


@pytest.mark.parametrize("version", [1, 2, 3])
def test_terminal_override_cannot_be_added_to_legacy_schema(version):
    raw = graph(sla_profile="standard")
    raw.update(schema_version=version)
    raw.pop("execution_semantics")
    with pytest.raises(ValueError, match="schema_version 4"):
        ScenarioDefinition.model_validate(raw)


@pytest.mark.parametrize("selection,processing", [
    ({"sla_profile": "absent"}, True),
    ({"sla_profile": "standard", "policy_ref": "policy"}, True),
    ({"policy_ref": "policy"}, True),
    ({"sla_profile": "standard"}, False),
])
def test_terminal_invalid_source_or_reference_is_rejected(selection, processing):
    raw = graph(**selection)
    if not processing:
        raw["processing"] = None
        for block in raw["blocks"]:
            for edge in block.get("transitions", []):
                edge.pop("processing", None)
    issues = validate_scenario(ScenarioDefinition.model_validate(raw))
    assert any(issue.path.startswith("blocks.submit") for issue in issues)


def test_terminal_policy_wins_over_visited_sla_block_without_processing():
    raw = graph(policy_ref="final_policy")
    raw.update(processing=None)
    raw["process_binding"]["policy_refs"] = {"sla": "default_policy"}
    raw["blocks"][0]["transitions"] = [{"to": "set_sla"}]
    raw["blocks"].insert(1, {"id": "set_sla", "kind": "sla", "title": "SLA", "policy_ref": "route_policy", "transitions": [{"to": "submit"}]})
    state = RuntimeState("submit", 3, {"affected": "one"}, ["questions", "set_sla"], {})
    snapshot = build_scenario_submission(ScenarioDefinition.model_validate(raw), state, session_id="s", version_id="v")[1]
    assert snapshot["policy_refs"]["sla"] == "final_policy"
    assert snapshot["sla_selection"] == {"kind": "policy", "key": "final_policy", "source": {"kind": "terminal", "block_id": "submit"}}


def test_fragment_terminal_profile_requires_mapping_and_remaps_reference():
    from tickets.request_scenario_fragments import extract_fragment, insert_fragment, FragmentDependencyError
    raw = graph(sla_profile="urgent")
    fragment, dependencies = extract_fragment(raw, ["submit"])
    assert {"kind": "sla_profile", "key": "urgent", "label": "urgent"} in dependencies
    with pytest.raises(FragmentDependencyError):
        insert_fragment(raw, fragment, position={"x": 0, "y": 0}, mappings={})
    target, ids = insert_fragment(raw, fragment, position={"x": 0, "y": 0}, mappings={"sla_profiles": {"urgent": "standard"}})
    assert next(block for block in target["blocks"] if block["id"] == ids[0])["sla_profile"] == "standard"


@pytest.mark.asyncio
async def test_terminal_policy_import_checks_publication_availability(monkeypatch):
    from tickets.request_scenario_document import document_reference_issues
    import tickets.request_scenario_processing as processing
    raw = graph(policy_ref="missing")
    raw["processing"] = None
    for block in raw["blocks"]:
        for edge in block.get("transitions", []):
            edge.pop("processing", None)
    monkeypatch.setattr(processing, "apply_scenario_policy_refs", AsyncMock(side_effect=ValueError("unavailable")))
    issues = await document_reference_issues(SimpleNamespace(), ScenarioDefinition.model_validate(raw))
    assert any(issue["path"] == "blocks.submit.policy_ref" and issue["code"] == "policy_reference_unavailable" for issue in issues)


@pytest.mark.asyncio
async def test_actual_simulation_retains_final_policy_source_and_actual_durations(monkeypatch):
    import tickets.service_catalog_preview as preview
    import tickets.request_scenario_processing as processing
    selection = SimpleNamespace(request_template_key="printer", service=None, offering=None)
    resolver = SimpleNamespace(resolve_selection=AsyncMock(return_value=selection),
        apply_to_validated_submission=AsyncMock(return_value={"template_context": {}}))
    monkeypatch.setattr(preview, "ServiceCatalogRuntimeResolver", lambda session: resolver)
    monkeypatch.setattr(preview, "resolve_create_form_submission", AsyncMock(return_value={"template_context": {}}))
    monkeypatch.setattr(preview, "apply_effective_registry_policies", AsyncMock(return_value={"template_context": {}}))
    monkeypatch.setattr(processing, "apply_scenario_policy_refs", AsyncMock(return_value={"template_context": {}}))
    monkeypatch.setattr(preview, "PolicyHealthService", lambda session: SimpleNamespace(simulate=AsyncMock(return_value={
        "sla": {"first_response_min": 17, "resolution_min": 83, "time_basis": "business"}})))
    terminal_selection = {"kind": "policy", "key": "published", "source": {"kind": "terminal", "block_id": "submit"}}
    snapshot = {"facts": {}, "field_roles": {}, "summary": [], "policy_refs": {"sla": "published"}, "sla_selection": terminal_selection}
    _, result = await preview.simulate_service_catalog_processing(SimpleNamespace(), {"request_template_key": "printer", "sla_selection": "forged"}, scenario_snapshot=snapshot)
    assert result["sla"]["selection"] == terminal_selection
    assert result["sla"]["source"] == terminal_selection["source"]
    assert result["sla"]["resolution_min"] == 83 and result["sla"]["time_basis"] == "business"


@pytest.mark.asyncio
async def test_terminal_profile_flows_to_canonical_create_context_after_backtracking():
    from tickets.request_scenario_runtime import ScenarioRuntime
    from tickets.request_scenario_processing import apply_scenario_map_processing
    from web_api.dto.request_scenario import ScenarioAnswerRequest
    engine = ScenarioRuntime(ScenarioDefinition.model_validate(graph(sla_profile="standard")))
    state = engine.initial_state()
    state = engine.advance(state, ScenarioAnswerRequest(expected_block_id="questions", revision=state.revision, answers={"affected": "all"}))
    back = engine.back(state, "questions", expected_revision=state.revision)
    state = engine.advance(back, ScenarioAnswerRequest(expected_block_id="questions", revision=back.revision, answers={"affected": "one"}))
    snapshot = build_scenario_submission(engine.definition, state, session_id="s", version_id="v")[1]
    session = SimpleNamespace(scalar=AsyncMock(return_value=SimpleNamespace(id=7, code="first_line", is_active=True)))
    context = (await apply_scenario_map_processing(session, {"template_context": {}}, snapshot["map_processing"]))["template_context"]
    assert context["routing_policy"]["fallback"]["queue_code"] == "first_line"
    assert context["sla_policy"]["targets"]["resolution"]["P2"] == 300
    assert context["scenario_processing"]["sla_profile"]["source"] == {"kind": "terminal", "block_id": "submit"}


def test_finish_cannot_acquire_ticket_sla_authority():
    raw = graph()
    raw["blocks"][1].update(kind="finish", sla_profile="standard")
    with pytest.raises(ValueError):
        ScenarioDefinition.model_validate(raw)


@pytest.mark.parametrize("format", ["json", "yaml"])
def test_terminal_override_survives_document_roundtrip(format):
    from tickets.request_scenario_document import export_scenario_document, parse_scenario_document
    value = ScenarioDefinition.model_validate(graph(sla_profile="standard"))
    restored = parse_scenario_document(export_scenario_document(value, format), format)
    assert next(block for block in restored.blocks if block.id == "submit").sla_profile == "standard"


@pytest.mark.asyncio
async def test_binding_rejects_unpublished_terminal_policy_on_save(monkeypatch):
    from app.repos.request_scenario_repo import RequestScenarioRepo
    import tickets.request_scenario_processing as processing
    raw = graph(policy_ref="missing")
    raw["processing"] = None
    for block in raw["blocks"]:
        for edge in block.get("transitions", []):
            edge.pop("processing", None)
    repo = RequestScenarioRepo.__new__(RequestScenarioRepo)
    repo.catalog = SimpleNamespace(get_offering_by_full_code=AsyncMock(return_value={"service_code": raw["service_code"], "request_template_key": raw["process_binding"]["request_template_key"]}))
    repo.session = SimpleNamespace(scalar=AsyncMock(return_value="template"))
    repo._category = AsyncMock()
    monkeypatch.setattr(processing, "apply_scenario_policy_refs", AsyncMock(side_effect=lambda session, validated, refs: (_ for _ in ()).throw(ValueError("unavailable")) if refs else validated))
    with pytest.raises(ValueError):
        await repo._binding(ScenarioDefinition.model_validate(raw))
