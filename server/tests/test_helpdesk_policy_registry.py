import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ApprovalPolicy,
    ClosurePolicy,
    DiagnosticPolicy,
    HelpdeskPolicyAudit,
    NotificationPolicy,
    OlaPolicy,
    PriorityPolicy,
    RequestTemplate,
    RoutingPolicy,
    SlaPolicy,
    SmartView,
    VisibilityPolicy,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_policy_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        for model in (
            HelpdeskPolicyAudit,
            SmartView,
            RequestTemplate,
            PriorityPolicy,
            SlaPolicy,
            OlaPolicy,
            RoutingPolicy,
            ApprovalPolicy,
            ClosurePolicy,
            DiagnosticPolicy,
            NotificationPolicy,
            VisibilityPolicy,
        ):
            await session.execute(delete(model))
        await session.commit()


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_publishes_versions_and_resolves_inheritance(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="priority",
            code="incident_priority",
            title="Incident priority default",
            scope_level="system",
            config={
                "matrix": {"low_impact": {"low_urgency": "P3"}},
                "manual_override": {"allowed_roles": ["admin"]},
            },
            actor_id="admin1",
            actor_role="admin",
        )
        await repo.publish_policy(
            kind="priority",
            code="incident_priority_incident_override",
            title="Incident priority override",
            scope_level="ticket_type",
            scope_ref="incident",
            config={
                "matrix": {"low_impact": {"low_urgency": "P2"}},
                "manual_override": {"require_reason": True},
            },
            actor_id="admin1",
            actor_role="admin",
        )
        await repo.publish_policy(
            kind="priority",
            code="website_priority_override",
            title="Website priority override",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={"modifiers": [{"condition": {"critical_service": True}, "minimum_priority": "P1"}]},
            actor_id="admin1",
            actor_role="admin",
        )
        effective = await repo.resolve_effective_policy(
            kind="priority",
            ticket_type="incident",
            template_code="website_unavailable",
        )
        await session.commit()

    assert effective["config"]["matrix"]["low_impact"]["low_urgency"] == "P2"
    assert effective["config"]["manual_override"] == {
        "allowed_roles": ["admin"],
        "require_reason": True,
    }
    assert effective["config"]["modifiers"][0]["minimum_priority"] == "P1"
    assert [source["scope_level"] for source in effective["sources"]] == [
        "system",
        "ticket_type",
        "request_template",
    ]


@pytest.mark.asyncio
async def test_web_admin_publish_from_form_creates_template_policies_and_audit(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    form_key = f"website_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
        json={
            "form": {
                "key": form_key,
                "request_kind": form_key,
                "ticket_type": "incident",
                "title": "Не открывается сайт",
                "description": "Пользователь сообщает, что сайт недоступен.",
                "category_id": 10,
                "default_queue_id": 20,
                "sla_policy_id": 30,
                "field_roles": {"url": ["routing_field", "diagnostic_input"]},
                "priority_policy": {
                    "impact_field": "impact_scope",
                    "urgency_field": "work_continuity",
                    "importance_field": "business_importance",
                },
                "routing_policy": {
                    "default_queue_id": 20,
                    "rules": [{"priority_order": 10, "when": {"diagnostic_result": "DNS_FAIL"}, "then": {"queue_id": 40}}],
                },
                "diagnostic_policy": {
                    "suggested_playbooks": ["diagnose.website"],
                    "attach_results": {"to_passport": True, "as_evidence": True},
                },
                "notification_policy": {"on_created": {"requester": True, "queue": True}},
                "fields": [
                    {"key": "url", "label": "Адрес сайта", "type": "text", "required": True},
                    {"key": "impact_scope", "label": "Кого затронуло", "type": "text", "required": True},
                    {"key": "work_continuity", "label": "Можно ли работать", "type": "text", "required": True},
                    {"key": "business_importance", "label": "Важность", "type": "text", "required": False},
                ],
            },
            "publish_policies": True,
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "success"
    result = data["data"]
    assert result["request_template"]["template_code"] == form_key
    assert result["request_template"]["priority_policy_code"] == f"{form_key}_priority_policy"
    assert result["request_template"]["routing_policy_code"] == f"{form_key}_routing_policy"
    assert result["request_template"]["diagnostic_policy_code"] == f"{form_key}_diagnostic_policy"
    assert result["request_template"]["notification_policy_code"] == f"{form_key}_notification_policy"
    assert result["policies"]["priority"]["config"]["impact_field"] == "impact_scope"
    assert result["policies"]["routing"]["config"]["rules"][0]["then"]["queue_id"] == 40

    registry_response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    assert registry_response.status == 200, await registry_response.text()
    registry = (await registry_response.json())["data"]
    assert registry["summary"]["active_request_templates_count"] == 1
    assert registry["summary"]["active_policies_count"] >= 4

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        template = (
            await session.execute(select(RequestTemplate).where(RequestTemplate.template_code == form_key))
        ).scalar_one()
        audit_count = len((await session.execute(select(HelpdeskPolicyAudit))).scalars().all())

    assert template.config_json["form"]["key"] == form_key
    assert audit_count == 5


@pytest.mark.asyncio
async def test_web_admin_publish_policy_creates_version_and_audit(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    policy_code = f"routing_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "routing",
            "code": policy_code,
            "title": "Routing policy",
            "description": "Policy editor smoke",
            "scope_level": "request_template",
            "scope_ref": "printer",
            "config": {
                "default_queue": "servicedesk_l1",
                "rules": [
                    {
                        "priority_order": 10,
                        "when": {"field": "request_form_data.room", "op": "eq", "value": "214"},
                        "then": {"queue": "printers", "priority_boost": 1},
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 200, await response.text()
    result = (await response.json())["data"]
    assert result["policy"]["kind"] == "routing"
    assert result["policy"]["code"] == policy_code
    assert result["policy"]["version"] == "1.0.1"
    assert result["policy"]["scope_level"] == "request_template"
    assert result["policy"]["scope_ref"] == "printer"
    assert result["policy"]["config"]["rules"][0]["then"]["queue"] == "printers"

    second_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "routing",
            "code": policy_code,
            "title": "Routing policy v2",
            "scope_level": "request_template",
            "scope_ref": "printer",
            "config": {"default_queue": "networks"},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second_response.status == 200, await second_response.text()
    second = (await second_response.json())["data"]
    assert second["policy"]["version"] == "1.0.2"

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        rows = list((await session.execute(select(RoutingPolicy).where(RoutingPolicy.code == policy_code))).scalars().all())
        audit_count = len((await session.execute(select(HelpdeskPolicyAudit))).scalars().all())

    assert len(rows) == 2
    assert sum(1 for row in rows if row.is_active) == 1
    assert audit_count == 2


@pytest.mark.asyncio
async def test_web_admin_publishes_sla_ola_and_smart_view_versions(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "sla",
            "code": "incident_sla_policy",
            "title": "Incident answer deadline",
            "scope_level": "ticket_type",
            "scope_ref": "incident",
            "config": {"sla_policy_id": 101, "targets": {"first_response": {"P1": "1h"}}},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    sla = (await response.json())["data"]["policy"]
    assert sla["kind"] == "sla"
    assert sla["table"] == "sla_policies"

    ola_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "ola",
            "code": "incident_ola_policy",
            "title": "Incident internal deadline",
            "scope_level": "ticket_type",
            "scope_ref": "incident",
            "config": {"targets": {"ack": {"P1": "15m"}, "processing": {"P1": "2h"}}},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert ola_response.status == 200, await ola_response.text()
    assert (await ola_response.json())["data"]["policy"]["kind"] == "ola"

    smart_response = await test_client.post(
        "/api/web/admin/helpdesk-model/smart-views/publish",
        json={
            "code": "answer_deadline_risk",
            "title": "Риск по сроку ответа",
            "filter": {"status_not_in": ["closed", "canceled"], "due_before_hours": 2},
            "sort": [{"field": "resolution_due_at", "direction": "asc"}],
            "columns": ["ticket_id", "title", "resolution_due_at"],
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert smart_response.status == 200, await smart_response.text()
    smart_view = (await smart_response.json())["data"]["smart_view"]
    assert smart_view["code"] == "answer_deadline_risk"
    assert smart_view["version"] == "1.0.1"

    registry_response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    registry = (await registry_response.json())["data"]
    assert registry["summary"]["active_policies_count"] == 2
    assert registry["summary"]["active_smart_views_count"] == 1
    assert "sla" in registry["capabilities"]["policy_kinds"]
    assert "ola" in registry["capabilities"]["policy_kinds"]
