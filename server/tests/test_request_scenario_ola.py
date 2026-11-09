"""OLA settings follow retained visits and use the canonical OLA lifecycle."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.test_request_scenario_terminal_sla import graph, submission
from tickets.request_scenario_runtime import RuntimeState
from tickets.request_scenario_submission import build_scenario_submission
from tickets.request_scenario_validation import validate_scenario
from web_api.dto.request_scenario import ScenarioDefinition, ScenarioDraftDefinition

pytestmark = pytest.mark.no_db


def ola(raw, target="questions", **settings):
    raw["blocks"].append({"id": "ola_" + target, "kind": "ola_attachment", "title": "OLA", "attached_to": target, **settings})


def test_last_visited_ola_then_terminal_override_and_default_inheritance():
    raw = graph()
    raw["process_binding"]["policy_refs"] = {"ola": "default_ola"}
    ola(raw, targets={"ack_minutes": 10, "processing_minutes": 60})
    ola(raw, "submit", policy_ref="final_ola")
    selected = submission(raw)
    assert selected["ola_selection"] == {"kind": "policy", "key": "final_ola", "source": {"kind": "attachment", "block_id": "ola_submit", "attached_to": "submit"}}
    assert selected["policy_refs"]["ola"] == "final_ola"
    raw["blocks"] = [b for b in raw["blocks"] if b["id"] != "ola_submit"]
    selected = submission(raw)
    assert "ola" not in selected["policy_refs"]
    assert selected["ola_selection"]["targets"] == {"ack_minutes": 10, "processing_minutes": 60}
    next(b for b in raw["blocks"] if b["id"] == "submit")["ola_targets"] = {"ack_minutes": 5, "processing_minutes": 30}
    assert submission(raw)["ola_selection"]["source"] == {"kind": "terminal", "block_id": "submit"}


def test_unvisited_settings_and_backtracked_answers_do_not_set_ola():
    raw = graph()
    raw["blocks"][0]["transitions"][0]["to"] = "branch"
    raw["blocks"].append({"id": "branch", "kind": "instruction", "title": "Branch", "content": {"body": "Branch"}, "transitions": [{"to": "submit"}]})
    ola(raw, "branch", targets={"ack_minutes": 5, "processing_minutes": 30})
    definition = ScenarioDefinition.model_validate(raw)
    state = RuntimeState("submit", 3, {"affected": "all"}, ["questions", "branch"], {})
    assert build_scenario_submission(definition, state, session_id="s", version_id="v")[1]["ola_selection"]["source"]["attached_to"] == "branch"
    assert "ola_selection" not in submission(raw, "one")


@pytest.mark.parametrize("targets", [{"ack_minutes": 0, "processing_minutes": 30}, {"ack_minutes": True, "processing_minutes": 30}, {"ack_minutes": 5}, {"ack_minutes": 5, "processing_minutes": -1}])
def test_invalid_durations_are_not_coerced(targets):
    raw = graph(); ola(raw, targets=targets)
    with pytest.raises(ValueError):
        ScenarioDraftDefinition.model_validate(raw)


def test_ola_is_attachment_only_and_legacy_wire_is_unchanged():
    raw = graph(); ola(raw, targets={"ack_minutes": 5, "processing_minutes": 30})
    assert not validate_scenario(ScenarioDefinition.model_validate(raw))
    raw["blocks"][0]["transitions"][0]["to"] = "ola_questions"
    assert "modifier_flow_target" in {i.code for i in validate_scenario(ScenarioDefinition.model_validate(raw))}
    for version in (1, 2, 3):
        legacy = deepcopy(raw); legacy["schema_version"] = version; legacy.pop("execution_semantics")
        with pytest.raises(ValueError, match="schema_version 4"):
            ScenarioDefinition.model_validate(legacy)
    encoded = ScenarioDefinition.model_validate(graph()).model_dump(mode="json")
    assert not any(k.startswith("ola_") for k in encoded["blocks"][1])


def test_policy_and_targets_cannot_be_combined_and_empty_ola_blocks_publication():
    raw = graph(); ola(raw, policy_ref="p", targets={"ack_minutes": 5, "processing_minutes": 30})
    assert any(i.code == "invalid_ola" for i in validate_scenario(ScenarioDraftDefinition.model_validate(raw)))
    raw["blocks"][-1].pop("policy_ref"); raw["blocks"][-1].pop("targets")
    assert any(i.code == "ola_unconfigured" for i in validate_scenario(ScenarioDraftDefinition.model_validate(raw)))


@pytest.mark.asyncio
async def test_explicit_targets_reach_canonical_ola_for_all_priorities_and_stay_pinned():
    from tickets.request_scenario_ola import apply_scenario_ola
    from tickets.ola_service import _targets_from_ola_policy
    from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy
    selected = {"kind": "targets", "targets": {"ack_minutes": 5, "processing_minutes": 30}, "source": {"kind": "terminal", "block_id": "submit"}}
    validated = apply_scenario_ola({"template_context": {"ola_policy_code": "old", "policy_refs": {"ola": {"code": "old"}}}}, selected)
    context = validated["template_context"]
    assert "ola_policy_code" not in context and "ola" not in context["policy_refs"]
    for priority in ("P0", "P1", "P2", "P3", "P4"):
        assert _targets_from_ola_policy(context["ola_policy"], priority) == (5, 30)
    ticket = SimpleNamespace(custom_fields={"request_template": context})
    assert await resolve_effective_ticket_policy(AsyncMock(), ticket, "ola") == context["ola_policy"]


def test_fragment_ola_policy_dependency_is_typed():
    from tickets.request_scenario_fragments import extract_fragment, insert_fragment
    raw = graph(); ola(raw, policy_ref="shared")
    fragment, dependencies = extract_fragment(raw, ["ola_questions"])
    assert {"kind": "ola_policy_ref", "key": "shared", "label": "shared"} in dependencies
    inserted, _ = insert_fragment(graph(), fragment, position={"x": 0, "y": 0}, mappings={"blocks": {"questions": "submit"}, "ola_policy_refs": {"shared": "new_ola"}})
    assert inserted["blocks"][-1]["policy_ref"] == "new_ola"


@pytest.mark.asyncio
async def test_selected_targets_set_real_deadlines_without_changing_queue_or_priority(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from tickets import ola_service
    from tickets.request_scenario_ola import apply_scenario_ola
    selection = {"kind": "targets", "targets": {"ack_minutes": 7, "processing_minutes": 43}, "source": {"kind": "attachment", "block_id": "ola"}}
    context = apply_scenario_ola({"template_context": {}}, selection)["template_context"]
    ticket = SimpleNamespace(ticket_id="ola-unit", queue_id=12, priority="P2", custom_fields={"priority_class": "P2", "request_template": context})
    session = AsyncMock()
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "_add_ola_event", AsyncMock())
    fallback = AsyncMock(side_effect=AssertionError("Scenario targets must win over queue defaults"))
    monkeypatch.setattr(ola_service, "get_ola_targets_for_queue", fallback)
    started = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
    assert await ola_service.start_ola_for_ticket(session, ticket, started_at=started)
    values = session.execute.call_args.args[0].compile().params
    assert values["ola_ack_due_at"] == started + timedelta(minutes=7)
    assert values["ola_processing_due_at"] == started + timedelta(minutes=43)
    assert ticket.queue_id == 12 and ticket.priority == "P2"
    fallback.assert_not_called()


def test_legacy_finish_text_remains_utf8():
    from web_api.dto.request_scenario import Finish
    assert Finish(id="done",title="Готово",kind="finish").message == "Проблема решена без обращения"


def test_disabled_ola_preview_has_no_effective_deadlines(monkeypatch):
    from datetime import datetime, timezone
    from tickets import ola_service
    monkeypatch.setattr(ola_service,"TICKET_OLA_ENABLED",False)
    preview=ola_service.ola_target_preview((7,43),datetime(2026,11,10,tzinfo=timezone.utc))
    assert preview=={"enabled":False,"ack_min":7,"processing_min":43}
    monkeypatch.setattr(ola_service,"TICKET_OLA_ENABLED",True)
    preview=ola_service.ola_target_preview((7,43),datetime(2026,11,10,tzinfo=timezone.utc))
    assert preview["enabled"] and preview["ack_due_preview"]=="2026-11-10T00:07:00+00:00"


@pytest.mark.asyncio
async def test_unavailable_ola_policies_fail_both_attachment_and_terminal_checks(monkeypatch):
    import tickets.request_scenario_processing as processing
    raw=graph(ola_policy_ref="missing_final");ola(raw,policy_ref="missing_attachment")
    monkeypatch.setattr(processing,"apply_scenario_policy_refs",AsyncMock(side_effect=ValueError("unpublished")))
    issues=await processing.scenario_sla_reference_issues(SimpleNamespace(),ScenarioDefinition.model_validate(raw))
    assert {i["path"] for i in issues}=={"blocks.ola_questions.policy_ref","blocks.submit.ola_policy_ref"}


@pytest.mark.asyncio
async def test_manual_ola_survives_registry_overlay_and_real_session_lifecycle(monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession
    import tickets.helpdesk_policy_runtime as runtime
    from tickets.request_scenario_ola import apply_scenario_ola
    value=apply_scenario_ola({"template_context":{}},{"kind":"targets","targets":{"ack_minutes":7,"processing_minutes":43},"source":{"kind":"terminal","block_id":"submit"}})
    policy=deepcopy(value["template_context"]["ola_policy"])
    repo=SimpleNamespace(resolve_effective_request_template=AsyncMock(return_value={"request_template":{"ola_policy_code":"global"},"resolved_policies":{"ola":{"targets":{"ack":{"P2":999},"processing":{"P2":999}}}},"policy_refs":{"ola":{"code":"global"}}}))
    monkeypatch.setattr(runtime,"HelpdeskPolicyRepo",lambda session:repo)
    session=AsyncMock(spec=AsyncSession)
    overlaid=await runtime.apply_effective_registry_policies(session,value)
    assert overlaid["template_context"]["ola_policy"]==policy
    assert "ola_policy_code" not in overlaid["template_context"]
    ticket=SimpleNamespace(custom_fields={"request_template":overlaid["template_context"]})
    assert await runtime.resolve_effective_ticket_policy(session,ticket,"ola")==policy
