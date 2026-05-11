from types import SimpleNamespace

import pytest

from tickets.form_process_preview import build_form_process_preview


def _form(**overrides):
    form = {
        "key": "website_unavailable",
        "request_kind": "website_unavailable",
        "ticket_type": "incident",
        "title": "Website unavailable",
        "fields": [
            {
                "key": "impact_scope",
                "label": "Impact",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "department", "label": "Department"},
                    {"value": "company", "label": "Company"},
                ],
            },
            {
                "key": "work_continuity",
                "label": "Continuity",
                "type": "select",
                "required": True,
                "options": [{"value": "blocked", "label": "Blocked"}],
            },
            {
                "key": "target_url",
                "label": "URL",
                "type": "text",
                "required": True,
                "help_text": "Enter URL.",
            },
        ],
        "field_roles": {
            "impact_scope": ["priority_impact"],
            "work_continuity": ["priority_urgency"],
            "target_url": ["routing_field", "diagnostic_input"],
        },
        "priority_policy": {
            "impact_field": "impact_scope",
            "urgency_field": "work_continuity",
            "importance_field": "business_importance",
            "modifier_fields": {},
        },
        "routing_policy": {
            "rules": [
                {
                    "code": "website_department_to_networks",
                    "priority_order": 5,
                    "when": {
                        "field": "request_form_data.impact_scope",
                        "op": "eq",
                        "value": "department",
                    },
                    "then": {"queue": "networks"},
                }
            ],
        },
        "sla_policy": {
            "code": "incident_sla_v3",
            "targets": {
                "first_response": {"P1": "15m"},
                "resolution": {"P1": "4h"},
            },
        },
        "ola_policy": {
            "code": "networks_ola_v1",
            "targets": {
                "ack": {"P1": "10m"},
                "processing": {"P1": "2h"},
            },
        },
        "approval_policy": {"required": False},
        "diagnostic_policy": {
            "suggested_playbooks": ["diagnose.website"],
            "auto_run": {"enabled": True, "only_for_priorities": ["P1"]},
            "consent": {"required_for_requester_device": True},
        },
        "closure_policy": {
            "before_resolved": {"require_resolution_code": True, "require_public_summary": True},
            "evidence": {"require_evidence_for_priorities": ["P1"]},
        },
        "visibility_policy": {"public_status_mapping": {"new": "received"}},
        "notification_policy": {"on_ticket_created": {"requester": True, "channels": {"web": True}}},
    }
    form.update(overrides)
    return form


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_form_process_preview_returns_priority_route_sla_and_policies():
    result = await build_form_process_preview(
        raw_form=_form(),
        form_payload={
            "impact_scope": "department",
            "work_continuity": "blocked",
            "target_url": "https://example.test",
        },
        queues=[
            SimpleNamespace(id=17, code="networks", name="Networks"),
            SimpleNamespace(id=1, code="servicedesk_l1", name="Service Desk"),
        ],
        routing_rules=[],
    )

    assert result["ticket_type"] == "incident"
    assert result["request_kind"] == "website_unavailable"
    assert result["priority"]["priority_class"] == "P1"
    assert result["routing"]["source"] == "request_template.routing_policy"
    assert result["routing"]["target_queue_id"] == 17
    assert result["routing"]["target_queue_name"] == "Networks"
    assert result["routing"]["matched_rule"]["code"] == "website_department_to_networks"
    assert result["sla"]["policy_code"] == "incident_sla_v3"
    assert result["sla"]["first_response_min"] == 15
    assert result["sla"]["resolution_min"] == 240
    assert result["ola"]["policy_code"] == "networks_ola_v1"
    assert result["ola"]["ack_min"] == 10
    assert result["ola"]["processing_min"] == 120
    assert result["approval"]["required"] is False
    assert result["diagnostics"]["suggested_playbooks"] == ["diagnose.website"]
    assert result["diagnostics"]["auto_run_enabled"] is True
    assert result["diagnostics"]["consent_required"] is True
    assert result["closure"]["requires_resolution_code"] is True
    assert result["visibility"]["public_status_mapping"]["new"] == "received"
    assert result["notifications"]["events"] == ["on_ticket_created"]
    assert result["validation_report"]["summary"]["can_publish"] is False


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_form_process_preview_uses_global_rule_and_has_no_db_side_effects():
    rule = SimpleNamespace(
        id=44,
        priority_order=10,
        target_queue_id=31,
        condition_json={"field": "request_form_data.target_url", "op": "contains", "value": "intranet"},
    )

    result = await build_form_process_preview(
        raw_form=_form(routing_policy={}),
        form_payload={
            "impact_scope": "company",
            "work_continuity": "blocked",
            "target_url": "https://intranet.example.test",
        },
        queues=[
            SimpleNamespace(id=31, code="apps", name="Apps"),
            SimpleNamespace(id=1, code="servicedesk_l1", name="Service Desk"),
        ],
        routing_rules=[rule],
    )

    assert result["routing"]["source"] == "ticket_routing_rule"
    assert result["routing"]["target_queue_id"] == 31
    assert result["routing"]["matched_rule"]["id"] == 44
    assert result["preview_metadata"]["side_effects"] == []
