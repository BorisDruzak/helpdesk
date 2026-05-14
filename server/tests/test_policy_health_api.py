from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ApprovalPolicy,
    ClosurePolicy,
    DiagnosticPolicy,
    OlaPolicy,
    PriorityPolicy,
    RequestTemplate,
    RoutingPolicy,
    SlaPolicy,
    Ticket,
    TicketQueue,
    VisibilityPolicy,
)


@pytest.mark.asyncio
async def test_policy_health_api_rbac_and_schema(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    template_code = f"printer_repair_{suffix}"
    routing_code = f"printer_route_{suffix}"
    sla_code = f"standard_sla_{suffix}"
    visibility_code = f"safe_visibility_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Printer repair",
                ticket_type="incident",
                routing_policy_code=routing_code,
                sla_policy_code=sla_code,
                visibility_policy_code=visibility_code,
                config_json={"default_queue_code": "support"},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        session.add(RoutingPolicy(code=routing_code, version="1", title="Printer route", config_json={"rules": []}, is_active=True))
        session.add(SlaPolicy(code=sla_code, version="1", title="Standard SLA", config_json={}, is_active=True))
        session.add(VisibilityPolicy(code=visibility_code, version="1", title="Safe visibility", config_json={"public_fields": ["ticket_code"]}, is_active=True))
        await session.commit()

    admin_resp = await test_client.get(
        "/api/web/admin/helpdesk/policy-health",
        headers={"Authorization": "Bearer test-ui-admin-token"},
    )
    assert admin_resp.status == 200
    admin_payload = await admin_resp.json()
    assert admin_payload["status"] == "ok"
    item = next(template for template in admin_payload["templates"] if template["template_code"] == template_code)
    assert "routing" in item["checks"]

    auditor_resp = await test_client.get(
        f"/api/web/admin/helpdesk/policy-health/{template_code}",
        headers={"Authorization": "Bearer test-ui-auditor-token"},
    )
    assert auditor_resp.status == 200
    detail = await auditor_resp.json()
    assert detail["template_code"] == template_code

    support_resp = await test_client.get(
        "/api/web/admin/helpdesk/policy-health",
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert support_resp.status == 403


@pytest.mark.asyncio
async def test_policy_health_simulate_is_dry_run(test_client, test_engine) -> None:
    template_code = f"printer_repair_dry_run_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Printer repair",
                ticket_type="incident",
                config_json={"default_queue_code": "support", "no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        before = await session.scalar(select(func.count()).select_from(Ticket))

    resp = await test_client.post(
        "/api/web/admin/helpdesk/policy-health/simulate",
        headers={"Authorization": "Bearer test-ui-admin-token"},
        json={"template_code": template_code, "request_form_data": {"summary": "Paper jam"}},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["would_create_ticket"] is False
    assert payload["template_code"] == template_code

    async with session_maker() as session:
        after = await session.scalar(select(func.count()).select_from(Ticket))
    assert after == before


@pytest.mark.asyncio
async def test_policy_health_simulate_uses_runtime_resolvers(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    template_code = f"runtime_sim_{suffix}"
    queue_code = f"runtime_queue_{suffix}"
    routing_code = f"runtime_routing_{suffix}"
    priority_code = f"runtime_priority_{suffix}"
    sla_code = f"runtime_sla_{suffix}"
    ola_code = f"runtime_ola_{suffix}"
    approval_code = f"runtime_approval_{suffix}"
    closure_code = f"runtime_closure_{suffix}"
    visibility_code = f"runtime_visibility_{suffix}"
    diagnostic_code = f"runtime_diagnostic_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(TicketQueue(code=queue_code, name="Sensitive Internal Department", is_active=True))
        session.add(
            PriorityPolicy(
                code=priority_code,
                version="1",
                title="Runtime priority",
                config_json={
                    "impact_field": "impact",
                    "urgency_field": "urgency",
                    "matrix": {"department": {"blocked": "P1"}},
                },
                is_active=True,
            )
        )
        session.add(
            RoutingPolicy(
                code=routing_code,
                version="1",
                title="Runtime routing",
                config_json={
                    "rules": [
                        {
                            "when": {"field": "request_form_data.issue_type", "op": "eq", "value": "printer"},
                            "then": {"queue_code": queue_code, "assignee_strategy": "least_loaded"},
                        }
                    ]
                },
                is_active=True,
            )
        )
        session.add(
            SlaPolicy(
                code=sla_code,
                version="1",
                title="Runtime SLA",
                config_json={"targets": {"first_response": {"P1": "30m"}, "resolution": {"P1": "4h"}}},
                is_active=True,
            )
        )
        session.add(
            OlaPolicy(
                code=ola_code,
                version="1",
                title="Runtime OLA",
                config_json={"targets": {"ack": {"P1": "10m"}, "processing": {"P1": "2h"}}},
                is_active=True,
            )
        )
        session.add(
            ApprovalPolicy(
                code=approval_code,
                version="1",
                title="Runtime approval",
                config_json={
                    "required": True,
                    "approval_mode": "any_one",
                    "approver_source": {"type": "form_field", "field": "approver"},
                },
                is_active=True,
            )
        )
        session.add(
            ClosurePolicy(
                code=closure_code,
                version="1",
                title="Runtime closure",
                config_json={"before_resolved": {"require_public_summary": True}},
                is_active=True,
            )
        )
        session.add(
            VisibilityPolicy(
                code=visibility_code,
                version="1",
                title="Runtime visibility",
                config_json={
                    "public_status_mapping": {"queued": {"status": "accepted", "label": "Принято"}},
                    "hide_from_requester": ["root_cause"],
                },
                is_active=True,
            )
        )
        session.add(
            DiagnosticPolicy(
                code=diagnostic_code,
                version="1",
                title="Runtime diagnostic",
                config_json={"suggested_playbooks": [{"playbook_key": "printer.basic"}], "auto_run": {"enabled": True}},
                is_active=True,
            )
        )
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Runtime simulation",
                ticket_type="incident",
                priority_policy_code=priority_code,
                routing_policy_code=routing_code,
                sla_policy_code=sla_code,
                ola_policy_code=ola_code,
                approval_policy_code=approval_code,
                closure_policy_code=closure_code,
                visibility_policy_code=visibility_code,
                diagnostic_policy_code=diagnostic_code,
                config_json={},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        before = await session.scalar(select(func.count()).select_from(Ticket))

    resp = await test_client.post(
        "/api/web/admin/helpdesk/policy-health/simulate",
        headers={"Authorization": "Bearer test-ui-admin-token"},
        json={
            "template_code": template_code,
            "request_form_data": {
                "issue_type": "printer",
                "impact": "department",
                "urgency": "blocked",
                "approver": "manager-1",
            },
            "requester_context": {"requester_id": "user:sim"},
            "device_metadata": {"device_id": "device-sim"},
        },
    )
    assert resp.status == 200, await resp.text()
    payload = await resp.json()

    assert payload["would_create_ticket"] is False
    assert payload["routing"]["queue_code"] == queue_code
    assert payload["routing"]["source"] == "request_template.routing_policy"
    assert payload["priority"]["priority_class"] == "P1"
    assert payload["priority"]["legacy_priority"] == "P2"
    assert payload["sla"]["policy_code"] == sla_code
    assert payload["sla"]["first_response_min"] == 30
    assert payload["sla"]["resolution_min"] == 240
    assert payload["ola"]["policy_code"] == ola_code
    assert payload["ola"]["ack_min"] == 10
    assert payload["ola"]["processing_min"] == 120
    assert payload["approval"]["required"] is True
    assert payload["approval"]["approvers"] == ["manager-1"]
    assert payload["closure"]["requires_public_summary"] is True
    assert payload["visibility"]["public_status_label"] == "Принято"
    assert payload["diagnostic"]["suggested_playbooks"] == ["printer.basic"]

    async with session_maker() as session:
        after = await session.scalar(select(func.count()).select_from(Ticket))
    assert after == before
