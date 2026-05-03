import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ApprovalPolicy,
    ClosurePolicy,
    DiagnosticPolicy,
    FormCondition,
    FormField,
    FormSchema,
    HelpdeskPolicyAudit,
    NotificationPolicy,
    OlaPolicy,
    PriorityPolicy,
    ReportingPolicy,
    RequestTemplate,
    RoutingPolicy,
    ServerConfig,
    SlaPolicy,
    SmartView,
    Ticket,
    TicketFormPack,
    TicketType,
    VisibilityPolicy,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX
from tickets.helpdesk_policy_runtime import resolve_effective_ticket_policy


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_policy_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        for model in (
            HelpdeskPolicyAudit,
            FormCondition,
            FormField,
            FormSchema,
            SmartView,
            RequestTemplate,
            TicketType,
            PriorityPolicy,
            SlaPolicy,
            OlaPolicy,
            RoutingPolicy,
            ApprovalPolicy,
            ClosurePolicy,
            DiagnosticPolicy,
            NotificationPolicy,
            VisibilityPolicy,
            ReportingPolicy,
        ):
            await session.execute(delete(model))
        await session.commit()


async def _clear_request_form_packs(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            delete(TicketFormPack).where(TicketFormPack.pack_key == "request_forms")
        )
        await session.execute(
            delete(ServerConfig).where(ServerConfig.key == f"{TICKET_FORM_PREFERRED_KEY_PREFIX}request_forms")
        )
        await session.commit()


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_publishes_ticket_type_versions_and_audit(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        first = await repo.publish_ticket_type(
            code="incident",
            title="Incident",
            default_workflow_profile_id="incident_default",
            default_priority_policy_code="incident_priority",
            default_routing_policy_code="incident_routing",
            default_sla_policy_id=101,
            default_sla_policy_code="incident_sla",
            default_ola_policy_code="incident_ola",
            default_closure_policy_code="incident_closure",
            feature_flags={
                "sla_required": True,
                "ola_required": True,
                "approval_allowed": True,
                "diagnostics_allowed": True,
                "remediation_allowed": False,
                "portal_visible": True,
            },
            actor_id="admin1",
            actor_role="admin",
        )
        second = await repo.publish_ticket_type(
            code="incident",
            title="Incident v2",
            default_workflow_profile_id="incident_default_v2",
            default_priority_policy_code="incident_priority_v2",
            default_routing_policy_code="incident_routing",
            default_sla_policy_id=102,
            default_sla_policy_code="incident_sla_v2",
            default_ola_policy_code="incident_ola",
            default_closure_policy_code="incident_closure",
            feature_flags={"sla_required": True, "portal_visible": True},
            actor_id="admin2",
            actor_role="admin",
        )
        await session.commit()

        rows = list((await session.execute(select(TicketType).where(TicketType.code == "incident"))).scalars().all())
        audits = list(
            (
                await session.execute(
                    select(HelpdeskPolicyAudit)
                    .where(HelpdeskPolicyAudit.entity_type == "ticket_types")
                    .order_by(HelpdeskPolicyAudit.id.asc())
                )
            ).scalars().all()
        )

    assert first["version"] == "1.0.1"
    assert second["version"] == "1.0.2"
    assert second["default_workflow_profile_id"] == "incident_default_v2"
    assert second["default_sla_policy_id"] == 102
    assert second["feature_flags"]["sla_required"] is True
    assert len(rows) == 2
    assert sum(1 for row in rows if row.is_active) == 1
    assert [audit.action for audit in audits] == ["published", "published"]


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_resolves_request_template_defaults_from_ticket_type(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_ticket_type(
            code="incident",
            title="Incident",
            default_workflow_profile_id="incident_default",
            default_priority_policy_code="incident_priority",
            default_routing_policy_code="incident_routing",
            default_sla_policy_id=201,
            default_sla_policy_code="incident_sla",
            default_ola_policy_code="incident_ola",
            default_approval_policy_code="incident_approval",
            default_diagnostic_policy_code="incident_diagnostics",
            default_closure_policy_code="incident_closure",
            default_visibility_policy_code="incident_visibility",
            default_notification_policy_code="incident_notifications",
            actor_id="admin1",
            actor_role="admin",
        )
        template = await repo.publish_request_template(
            template_code="website_unavailable",
            public_title="Website unavailable",
            ticket_type="incident",
            config={"form": {"key": "website_unavailable"}},
            actor_id="admin1",
            actor_role="admin",
        )
        defaults = await repo.resolve_ticket_type_defaults("incident")
        await session.commit()

    assert defaults["code"] == "incident"
    assert template["workflow_profile_id"] == "incident_default"
    assert template["priority_policy_code"] == "incident_priority"
    assert template["routing_policy_code"] == "incident_routing"
    assert template["sla_policy_id"] == 201
    assert template["ola_policy_code"] == "incident_ola"
    assert template["approval_policy_code"] == "incident_approval"
    assert template["diagnostic_policy_code"] == "incident_diagnostics"
    assert template["closure_policy_code"] == "incident_closure"
    assert template["visibility_policy_code"] == "incident_visibility"
    assert template["notification_policy_code"] == "incident_notifications"
    assert template["config"]["ticket_type_defaults"]["code"] == "incident"


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_keeps_legacy_unknown_ticket_type_fallback(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        template = await repo.publish_request_template(
            template_code="legacy_custom",
            public_title="Legacy custom",
            ticket_type="legacy_process",
            workflow_profile_id="legacy_flow",
            actor_id="admin1",
            actor_role="admin",
        )
        defaults = await repo.resolve_ticket_type_defaults("legacy_process")
        await session.commit()

    assert defaults is None
    assert template["ticket_type"] == "legacy_process"
    assert template["workflow_profile_id"] == "legacy_flow"
    assert "ticket_type_defaults" not in template["config"]


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_publishes_form_schema_fields_conditions_and_audit(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        first = await repo.publish_form_schema(
            schema_id="website_unavailable_form",
            title="Website unavailable form",
            form_key="website_unavailable",
            request_template_code="website_unavailable",
            ticket_type="incident",
            fields=[
                {
                    "key": "url",
                    "label": "URL",
                    "type": "url",
                    "required": True,
                    "validation": {"required_message": "URL is required"},
                    "process_mapping": {
                        "roles": ["diagnostic_input", "routing_field"],
                        "diagnostic_param": "target_url",
                    },
                },
                {
                    "key": "affected_scope",
                    "label": "Affected scope",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"value": "only_me", "label": "Only me"},
                        {"value": "department", "label": "Department"},
                    ],
                },
                {
                    "key": "affected_count",
                    "label": "Affected count",
                    "type": "text",
                    "required": True,
                    "visible_when": {"field": "affected_scope", "equals": "department"},
                },
            ],
            actor_id="admin1",
            actor_role="admin",
        )
        second = await repo.publish_form_schema(
            schema_id="website_unavailable_form",
            title="Website unavailable form v2",
            form_key="website_unavailable",
            request_template_code="website_unavailable",
            ticket_type="incident",
            fields=[
                {"key": "url", "label": "URL", "type": "url", "required": True},
            ],
            actor_id="admin2",
            actor_role="admin",
        )
        await session.commit()

        schemas = list(
            (
                await session.execute(
                    select(FormSchema).where(FormSchema.schema_id == "website_unavailable_form")
                )
            ).scalars().all()
        )
        fields = list(
            (
                await session.execute(
                    select(FormField)
                    .where(
                        FormField.schema_id == "website_unavailable_form",
                        FormField.schema_version == "1.0.1",
                    )
                    .order_by(FormField.sort_order.asc())
                )
            ).scalars().all()
        )
        conditions = list(
            (
                await session.execute(
                    select(FormCondition).where(
                        FormCondition.schema_id == "website_unavailable_form",
                        FormCondition.schema_version == "1.0.1",
                    )
                )
            ).scalars().all()
        )

    assert first["version"] == "1.0.1"
    assert second["version"] == "1.0.2"
    assert second["is_active"] is True
    assert sum(1 for row in schemas if row.is_active) == 1
    assert first["fields"][0]["validation"]["required_message"] == "URL is required"
    assert first["fields"][0]["process_mapping"]["roles"] == ["diagnostic_input", "routing_field"]
    assert first["fields"][0]["process_mapping"]["diagnostic_param"] == "target_url"
    assert first["fields"][2]["visibility"]["field"] == "affected_scope"
    assert [field.key for field in fields] == ["url", "affected_scope", "affected_count"]
    assert fields[0].validation_json["required_message"] == "URL is required"
    assert fields[0].process_mapping_json["roles"] == ["diagnostic_input", "routing_field"]
    assert len(conditions) == 1
    assert conditions[0].condition_json == {"field": "affected_scope", "equals": "department"}


@pytest.mark.asyncio
async def test_web_admin_publish_from_form_creates_form_schema_reference(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    form_key = f"schema_{uuid.uuid4().hex[:8]}"
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/request-templates/publish-from-form",
        json={
            "form": {
                "key": form_key,
                "request_kind": form_key,
                "ticket_type": "incident",
                "title": "Website unavailable",
                "field_roles": {"url": ["routing_field"]},
                "fields": [
                    {
                        "key": "url",
                        "label": "URL",
                        "type": "url",
                        "required": True,
                        "validation": {"required_message": "Provide URL"},
                        "process_mapping": {"roles": ["diagnostic_input"], "diagnostic_param": "target_url"},
                    },
                ],
            },
            "publish_policies": False,
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 200, await response.text()
    result = (await response.json())["data"]
    assert result["form_schema"]["schema_id"] == f"{form_key}_form"
    assert result["form_schema"]["fields"][0]["process_mapping"]["roles"] == [
        "routing_field",
        "diagnostic_input",
    ]
    assert result["request_template"]["form_schema_id"] == f"{form_key}_form"
    assert result["request_template"]["config"]["form_schema"]["version"] == "1.0.1"

    create_response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Schema snapshot request",
            "description": "Verify registry template and form schema versions are snapped.",
            "device_id": str(uuid.uuid4()),
            "request_template_key": form_key,
            "form_payload": {"url": "https://snapshot.example.test"},
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    template_snapshot = ticket.custom_fields["request_template"]
    assert template_snapshot["request_template_version"] == "1.0.1"
    assert template_snapshot["form_schema_version"] == "1.0.1"

    registry_response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    assert registry_response.status == 200, await registry_response.text()
    registry = (await registry_response.json())["data"]
    assert registry["summary"]["active_form_schemas_count"] == 1
    assert registry["form_schemas"][0]["schema_id"] == f"{form_key}_form"


@pytest.mark.asyncio
async def test_web_admin_republish_legacy_forms_is_idempotent(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _clear_policy_registry(test_engine)
    first_form_key = f"legacy_{uuid.uuid4().hex[:8]}"
    second_form_key = f"legacy_{uuid.uuid4().hex[:8]}"
    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Legacy request forms",
                "forms": [
                    {
                        "key": first_form_key,
                        "request_kind": first_form_key,
                        "ticket_type": "incident",
                        "title": "Legacy incident",
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    },
                    {
                        "key": second_form_key,
                        "request_kind": second_form_key,
                        "ticket_type": "service_request",
                        "title": "Legacy service request",
                        "priority_policy": {"matrix": {"low_impact": {"low_urgency": "P3"}}},
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    },
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    first_response = await test_client.post(
        "/api/web/admin/helpdesk-model/request-templates/republish-legacy-forms",
        json={"publish_policies": True},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert first_response.status == 200, await first_response.text()
    first_result = (await first_response.json())["data"]
    assert first_result["summary"]["forms_seen_count"] == 2
    assert first_result["summary"]["published_templates_count"] == 2
    assert first_result["summary"]["skipped_unchanged_count"] == 0
    assert {item["template_code"] for item in first_result["items"]} == {first_form_key, second_form_key}

    second_response = await test_client.post(
        "/api/web/admin/helpdesk-model/request-templates/republish-legacy-forms",
        json={"publish_policies": True},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second_response.status == 200, await second_response.text()
    second_result = (await second_response.json())["data"]
    assert second_result["summary"]["published_templates_count"] == 0
    assert second_result["summary"]["skipped_unchanged_count"] == 2
    assert {item["status"] for item in second_result["items"]} == {"skipped_unchanged"}

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        templates = list(
            (
                await session.execute(
                    select(RequestTemplate).where(RequestTemplate.template_code.in_([first_form_key, second_form_key]))
                )
            ).scalars().all()
        )
        schemas = list(
            (
                await session.execute(
                    select(FormSchema).where(FormSchema.request_template_code.in_([first_form_key, second_form_key]))
                )
            ).scalars().all()
        )

    assert len(templates) == 2
    assert len(schemas) == 2
    assert sum(1 for item in templates if item.is_active) == 2
    assert sum(1 for item in schemas if item.is_active) == 2


@pytest.mark.asyncio
async def test_web_admin_registry_reports_template_policy_quality_gaps(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    template_code = f"quality_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_request_template(
            template_code=template_code,
            public_title="Incomplete template",
            ticket_type="incident",
            form_schema_id=f"{template_code}_form",
            actor_id="admin1",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    assert response.status == 200, await response.text()
    registry = (await response.json())["data"]
    assert registry["summary"]["data_quality_issue_count"] >= 5
    template_issues = [
        item
        for item in registry["data_quality"]
        if item["entity_type"] == "request_template" and item["entity_code"] == template_code
    ]
    missing_fields = {item["field"] for item in template_issues}
    assert {"workflow_profile_id", "priority_policy", "routing_policy", "sla_policy", "closure_policy"} <= missing_fields


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
async def test_helpdesk_policy_repo_resolves_request_template_policy_refs_before_inline_config(test_engine):
    await _clear_policy_registry(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="priority",
            code="website_priority_ref",
            title="Website priority ref",
            scope_level="system",
            config={
                "impact_field": "affected_scope",
                "urgency_field": "work_blocked",
                "matrix": {"low_impact": {"low_urgency": "P3"}},
            },
            actor_id="admin1",
            actor_role="admin",
        )
        await repo.publish_request_template(
            template_code="website_unavailable",
            public_title="Не открывается сайт",
            ticket_type="incident",
            priority_policy_code="website_priority_ref",
            config={
                "priority_policy": {
                    "impact_field": "legacy_inline_impact",
                    "urgency_field": "legacy_inline_urgency",
                }
            },
            actor_id="admin1",
            actor_role="admin",
        )

        effective = await repo.resolve_effective_request_template(template_code="website_unavailable")
        await session.commit()

    assert effective["request_template"]["template_code"] == "website_unavailable"
    assert effective["policy_refs"]["priority"]["code"] == "website_priority_ref"
    assert effective["policy_refs"]["priority"]["version"] == "1.0.1"
    assert effective["resolved_policies"]["priority"]["impact_field"] == "affected_scope"
    assert effective["resolved_policies"]["priority"]["urgency_field"] == "work_blocked"
    assert effective["policy_sources"]["priority"][0]["source"] == "request_template.priority_policy_code"
    assert effective["policy_sources"]["priority"][0]["scope_level"] == "policy_ref"


@pytest.mark.asyncio
async def test_ticket_creation_stores_request_template_policy_ref_snapshot(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _clear_policy_registry(test_engine)
    form_key = f"policy_ref_{uuid.uuid4().hex[:8]}"

    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": form_key,
                        "request_kind": form_key,
                        "ticket_type": "incident",
                        "title": "Policy ref form",
                        "priority_policy": {
                            "impact_field": "legacy_inline_impact",
                            "urgency_field": "legacy_inline_urgency",
                        },
                        "fields": [
                            {"key": "impact_scope", "label": "Impact", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Urgency", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        policy = await repo.publish_policy(
            kind="priority",
            code=f"{form_key}_priority_ref",
            title="Priority ref",
            scope_level="system",
            config={
                "impact_field": "impact_scope",
                "urgency_field": "work_continuity",
                "modifiers": {"critical_service": True},
            },
            actor_id="admin1",
            actor_role="admin",
        )
        await repo.publish_request_template(
            template_code=form_key,
            public_title="Policy ref form",
            ticket_type="incident",
            priority_policy_code=policy["code"],
            actor_id="admin1",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Policy ref request",
            "description": "Priority should come from request_template policy ref",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {
                "impact_scope": "only_me",
                "work_continuity": "workaround_available",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    template_snapshot = ticket.custom_fields["request_template"]
    assert ticket.custom_fields["priority_decision"]["effective_priority"] == "P2"
    assert template_snapshot["priority_policy"]["impact_field"] == "impact_scope"
    assert template_snapshot["policy_refs"]["priority"]["code"] == f"{form_key}_priority_ref"
    assert template_snapshot["effective_policy_snapshots"]["priority"]["version"] == "1.0.1"
    assert template_snapshot["effective_policy_snapshots"]["priority"]["source"] == "request_template.priority_policy_code"
    assert template_snapshot["effective_policy_sources"]["priority"][0]["scope_level"] == "policy_ref"

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="priority",
            code=f"{form_key}_priority_ref",
            title="Priority ref v2",
            scope_level="system",
            config={
                "impact_field": "impact_scope_v2",
                "urgency_field": "work_continuity_v2",
            },
            actor_id="admin1",
            actor_role="admin",
        )
        refreshed_ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        active_policy = await resolve_effective_ticket_policy(session, refreshed_ticket, "priority")
        await session.commit()

    assert template_snapshot["effective_policy_snapshots"]["priority"]["version"] == "1.0.1"
    assert active_policy["impact_field"] == "impact_scope_v2"
    assert "modifiers" not in active_policy


@pytest.mark.asyncio
async def test_legacy_ticket_created_before_registry_resolves_ticket_type_policy(test_engine):
    await _clear_policy_registry(test_engine)
    ticket_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=f"device-{ticket_id[:8]}",
                title="Legacy pre-registry ticket",
                description="No request_template snapshot exists yet",
                status="in_progress",
                requester_id="legacy-user",
                ticket_type="incident",
                priority="P3",
                custom_fields={"priority_class": "P2"},
            )
        )
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_policy(
            kind="closure",
            code="incident_closure_default",
            title="Incident closure default",
            scope_level="ticket_type",
            scope_ref="incident",
            config={
                "before_resolved": {"require_resolution_code": True},
                "requester_confirmation": {"required": False},
            },
            actor_id="admin1",
            actor_role="admin",
        )
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        active_policy = await resolve_effective_ticket_policy(session, ticket, "closure")
        await session.commit()

    assert active_policy["before_resolved"]["require_resolution_code"] is True
    assert active_policy["requester_confirmation"]["required"] is False


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
                "sla_policy": {
                    "targets": {
                        "first_response": {"P2": "45m"},
                        "resolution": {"P2": "2h"},
                    },
                },
                "notification_policy": {"on_created": {"requester": True, "queue": True}},
                "reporting_policy": {"report_tags": ["website", "live_acceptance"]},
                "fields": [
                    {"key": "url", "label": "Адрес сайта", "type": "text", "required": True},
                    {
                        "key": "symptoms",
                        "label": "Симптомы",
                        "type": "multi_select",
                        "required": False,
                        "options": [
                            {"value": "dns", "label": "DNS"},
                            {"value": "proxy", "label": "Прокси"},
                        ],
                    },
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
    assert result["request_template"]["sla_policy_code"] == f"{form_key}_sla_policy"
    assert result["request_template"]["diagnostic_policy_code"] == f"{form_key}_diagnostic_policy"
    assert result["request_template"]["notification_policy_code"] == f"{form_key}_notification_policy"
    assert result["request_template"]["reporting_policy_code"] == f"{form_key}_reporting_policy"
    assert result["policies"]["priority"]["config"]["impact_field"] == "impact_scope"
    assert result["policies"]["routing"]["config"]["rules"][0]["then"]["queue_id"] == 40
    assert result["policies"]["sla"]["config"]["targets"]["first_response"]["P2"] == "45m"
    assert result["policies"]["reporting"]["config"]["report_tags"] == ["website", "live_acceptance"]
    symptoms_field = next(field for field in result["form_schema"]["fields"] if field["key"] == "symptoms")
    assert symptoms_field["type"] == "multi_select"
    assert symptoms_field["options"] == [{"value": "dns", "label": "DNS"}, {"value": "proxy", "label": "Прокси"}]

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
    assert audit_count == 8


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
async def test_web_admin_ticket_type_lifecycle_and_registry_payload(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/ticket-types/publish",
        json={
            "code": "access_request",
            "title": "Access request",
            "default_workflow_profile_id": "access_request_flow",
            "default_priority_policy_code": "access_priority",
            "default_routing_policy_code": "access_routing",
            "default_sla_policy_id": 301,
            "default_sla_policy_code": "access_sla",
            "default_approval_policy_code": "service_owner_approval",
            "default_closure_policy_code": "access_closure",
            "feature_flags": {
                "sla_required": True,
                "approval_allowed": True,
                "approval_required_by_default": True,
                "diagnostics_allowed": False,
                "portal_visible": True,
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    first = (await response.json())["data"]["ticket_type"]
    assert first["code"] == "access_request"
    assert first["version"] == "1.0.1"
    assert first["feature_flags"]["approval_required_by_default"] is True

    second_response = await test_client.post(
        "/api/web/admin/helpdesk-model/ticket-types/publish",
        json={
            "code": "access_request",
            "title": "Access request v2",
            "default_workflow_profile_id": "access_request_flow_v2",
            "feature_flags": {"portal_visible": True},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second_response.status == 200, await second_response.text()
    second = (await second_response.json())["data"]["ticket_type"]
    assert second["version"] == "1.0.2"

    registry_response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    assert registry_response.status == 200, await registry_response.text()
    registry = (await registry_response.json())["data"]
    assert registry["summary"]["ticket_types_count"] == 2
    assert registry["summary"]["active_ticket_types_count"] == 1
    assert registry["ticket_types"][0]["code"] == "access_request"
    assert registry["capabilities"]["publish_ticket_type_endpoint"] == "/api/web/admin/helpdesk-model/ticket-types/publish"

    deactivate_response = await test_client.post(
        "/api/web/admin/helpdesk-model/ticket-types/deactivate",
        json={"code": "access_request", "version": second["version"]},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert deactivate_response.status == 200, await deactivate_response.text()
    assert (await deactivate_response.json())["data"]["ticket_type"]["is_active"] is False

    rollback_response = await test_client.post(
        "/api/web/admin/helpdesk-model/ticket-types/rollback",
        json={"code": "access_request", "target_version": first["version"]},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert rollback_response.status == 200, await rollback_response.text()
    rollback = (await rollback_response.json())["data"]["ticket_type"]
    assert rollback["version"] == "1.0.3"
    assert rollback["default_workflow_profile_id"] == "access_request_flow"


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_diffs_deactivates_and_rolls_back_policy_versions(test_engine):
    await _clear_policy_registry(test_engine)
    policy_code = f"closure_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        first = await repo.publish_policy(
            kind="closure",
            code=policy_code,
            title="Closure policy",
            config={"require_resolution_code": True, "auto_close_after_days": 3},
            actor_id="admin1",
            actor_role="admin",
        )
        second = await repo.publish_policy(
            kind="closure",
            code=policy_code,
            title="Closure policy strict",
            config={"require_resolution_code": True, "require_public_summary": True, "auto_close_after_days": 1},
            actor_id="admin1",
            actor_role="admin",
        )

        diff = await repo.diff_policy_versions(
            kind="closure",
            code=policy_code,
            from_version=first["version"],
            to_version=second["version"],
        )
        deactivated = await repo.deactivate_policy(
            kind="closure",
            code=policy_code,
            version=second["version"],
            actor_id="admin2",
            actor_role="admin",
        )
        rollback = await repo.rollback_policy(
            kind="closure",
            code=policy_code,
            target_version=first["version"],
            actor_id="admin3",
            actor_role="admin",
        )
        await session.commit()

        rows = list((await session.execute(select(ClosurePolicy).where(ClosurePolicy.code == policy_code))).scalars().all())
        audits = list(
            (
                await session.execute(
                    select(HelpdeskPolicyAudit)
                    .where(HelpdeskPolicyAudit.entity_code == policy_code)
                    .order_by(HelpdeskPolicyAudit.id.asc())
                )
            ).scalars().all()
        )

    assert diff["from"]["version"] == first["version"]
    assert diff["to"]["version"] == second["version"]
    assert {"path": "config.require_public_summary", "from": None, "to": True} in diff["changes"]
    assert {"path": "config.auto_close_after_days", "from": 3, "to": 1} in diff["changes"]
    assert deactivated["is_active"] is False
    assert rollback["version"] == "1.0.3"
    assert rollback["config"] == first["config"]
    assert rollback["is_active"] is True
    assert len(rows) == 3
    assert sum(1 for row in rows if row.is_active) == 1
    assert [audit.action for audit in audits] == ["published", "published", "deactivated", "rollback_published"]


@pytest.mark.asyncio
async def test_helpdesk_policy_repo_publishes_reporting_policy(test_engine):
    from sqlalchemy import delete

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(delete(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies"))
        await session.execute(delete(ReportingPolicy))
        repo = HelpdeskPolicyRepo(session)

        item = await repo.publish_policy(
            kind="reporting",
            code="website_passport_reporting",
            title="Website passport reporting",
            scope_level="request_template",
            scope_ref="website_unavailable",
            config={
                "required_sections": ["problem", "evidence", "user_result"],
                "evidence_package": {"include_action_log": False, "include_related_objects": False},
                "export_visibility": {"hide_sections": ["internal_result", "operator_checks"]},
                "report_tags": ["critical_service", "diagnostics"],
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await session.commit()

    assert item["kind"] == "reporting"
    assert item["table"] == "reporting_policies"
    assert item["config"]["report_tags"] == ["critical_service", "diagnostics"]

    async with session_maker() as session:
        rows = list((await session.execute(select(ReportingPolicy))).scalars().all())
        audit = list(
            (
                await session.execute(
                    select(HelpdeskPolicyAudit).where(HelpdeskPolicyAudit.entity_type == "reporting_policies")
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1
    assert rows[0].code == "website_passport_reporting"
    assert audit[-1].entity_type == "reporting_policies"


@pytest.mark.asyncio
async def test_web_admin_helpdesk_policy_lifecycle_endpoints(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    policy_code = f"routing_{uuid.uuid4().hex[:8]}"

    first_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "routing",
            "code": policy_code,
            "title": "Routing policy",
            "scope_level": "request_template",
            "scope_ref": "printer",
            "config": {"default_queue": "servicedesk_l1"},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert first_response.status == 200, await first_response.text()
    first = (await first_response.json())["data"]["policy"]

    second_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "routing",
            "code": policy_code,
            "title": "Routing policy v2",
            "scope_level": "request_template",
            "scope_ref": "printer",
            "config": {"default_queue": "networks", "rules": [{"priority_order": 10}]},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second_response.status == 200, await second_response.text()
    second = (await second_response.json())["data"]["policy"]

    diff_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/diff",
        json={"kind": "routing", "code": policy_code, "from_version": first["version"], "to_version": second["version"]},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert diff_response.status == 200, await diff_response.text()
    diff = (await diff_response.json())["data"]
    assert {"path": "config.default_queue", "from": "servicedesk_l1", "to": "networks"} in diff["changes"]

    deactivate_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/deactivate",
        json={"kind": "routing", "code": policy_code, "version": second["version"]},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert deactivate_response.status == 200, await deactivate_response.text()
    deactivated = (await deactivate_response.json())["data"]["policy"]
    assert deactivated["is_active"] is False

    rollback_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/rollback",
        json={"kind": "routing", "code": policy_code, "target_version": first["version"]},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert rollback_response.status == 200, await rollback_response.text()
    rollback = (await rollback_response.json())["data"]["policy"]
    assert rollback["version"] == "1.0.3"
    assert rollback["config"] == first["config"]
    assert rollback["is_active"] is True


@pytest.mark.asyncio
async def test_web_admin_publish_routing_policy_rejects_invalid_targets(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "routing",
            "code": f"routing_invalid_{uuid.uuid4().hex[:8]}",
            "title": "Invalid routing policy",
            "scope_level": "request_template",
            "scope_ref": "printer",
            "config": {
                "default_queue_id": -999,
                "max_auto_reroutes": -1,
                "rules": [
                    {
                        "priority_order": 10,
                        "when": {"field": "request_form_data.room", "op": "eq", "value": "214"},
                        "then": {"queue_id": -999},
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "routing policy" in payload["error"]


@pytest.mark.asyncio
async def test_web_admin_publish_sla_policy_rejects_invalid_targets_and_calendar(test_client, test_engine):
    await _clear_policy_registry(test_engine)

    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "sla",
            "code": "invalid_sla_policy",
            "title": "Invalid SLA",
            "scope_level": "request_template",
            "scope_ref": "incident",
            "config": {
                "targets": {
                    "first_response": {"P1": "-5m"},
                    "resolution": {"P1": "soon"},
                },
                "calendar": {"timezone": "UTC", "weekly_hours_json": "not-an-array"},
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "sla policy" in payload["error"]


@pytest.mark.asyncio
async def test_web_admin_publish_ola_policy_rejects_invalid_targets(test_client, test_engine):
    await _clear_policy_registry(test_engine)

    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "ola",
            "code": "invalid_ola_policy",
            "title": "Invalid OLA",
            "scope_level": "request_template",
            "scope_ref": "incident",
            "config": {"targets": {"ack": {"P1": "-1m"}, "processing": {"P1": "later"}}},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "ola policy" in payload["error"]


@pytest.mark.asyncio
async def test_web_admin_publish_approval_policy_rejects_unknown_approver_source(test_client, test_engine):
    await _clear_policy_registry(test_engine)

    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "approval",
            "code": "invalid_approval_policy",
            "title": "Invalid approval",
            "scope_level": "request_template",
            "scope_ref": "access_request",
            "config": {
                "required": True,
                "approval_mode": "all",
                "approver_source": {"type": "telepathy", "field": "manager_login"},
                "timeout": {"reminder_after": "30m", "escalate_after": "45m", "due_in": "1h"},
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "approval policy" in payload["error"]


@pytest.mark.asyncio
async def test_web_admin_publish_visibility_policy_rejects_invalid_requester_paths(test_client, test_engine):
    await _clear_policy_registry(test_engine)

    response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "visibility",
            "code": "invalid_visibility_policy",
            "title": "Invalid visibility",
            "scope_level": "request_template",
            "scope_ref": "incident",
            "config": {
                "hide_from_requester": ["", ".raw", "ola..runtime"],
                "public_status_mapping": "not-an-object",
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["error_code"] == "VALIDATION_ERROR"
    assert "visibility policy" in payload["error"]


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


@pytest.mark.asyncio
async def test_web_admin_rejects_invalid_smart_view_definition(test_client, test_engine):
    await _clear_policy_registry(test_engine)

    invalid_filter_response = await test_client.post(
        "/api/web/admin/helpdesk-model/smart-views/publish",
        json={
            "code": "invalid_filter_view",
            "title": "Некорректный фильтр",
            "filter": {"status_not_in": ["closed"], "raw_sql": "1=1"},
            "sort": [{"field": "resolution_due_at", "direction": "asc"}],
            "columns": ["ticket_id", "title", "resolution_due_at"],
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert invalid_filter_response.status == 400
    invalid_filter_payload = await invalid_filter_response.json()
    assert invalid_filter_payload["error_code"] == "VALIDATION_ERROR"
    assert "raw_sql" in invalid_filter_payload["error"]

    invalid_sort_response = await test_client.post(
        "/api/web/admin/helpdesk-model/smart-views/publish",
        json={
            "code": "invalid_sort_view",
            "title": "Некорректная сортировка",
            "filter": {"status_not_in": ["closed"]},
            "sort": [{"field": "resolution_due_at", "direction": "sideways"}],
            "columns": ["ticket_id", "title", "resolution_due_at"],
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert invalid_sort_response.status == 400
    invalid_sort_payload = await invalid_sort_response.json()
    assert invalid_sort_payload["error_code"] == "VALIDATION_ERROR"
    assert "direction" in invalid_sort_payload["error"]

    invalid_column_response = await test_client.post(
        "/api/web/admin/helpdesk-model/smart-views/publish",
        json={
            "code": "invalid_column_view",
            "title": "Некорректная колонка",
            "filter": {"status_not_in": ["closed"]},
            "sort": [{"field": "resolution_due_at", "direction": "asc"}],
            "columns": ["ticket_id", "title", "raw_secret"],
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert invalid_column_response.status == 400
    invalid_column_payload = await invalid_column_response.json()
    assert invalid_column_payload["error_code"] == "VALIDATION_ERROR"
    assert "raw_secret" in invalid_column_payload["error"]

    invalid_filter_path_response = await test_client.post(
        "/api/web/admin/helpdesk-model/smart-views/publish",
        json={
            "code": "invalid_filter_path_view",
            "title": "Некорректный путь фильтра",
            "filter": {"field_equals": {"raw_secret": "hidden"}},
            "sort": [{"field": "resolution_due_at", "direction": "asc"}],
            "columns": ["ticket_id", "title", "resolution_due_at"],
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert invalid_filter_path_response.status == 400
    invalid_filter_path_payload = await invalid_filter_path_response.json()
    assert invalid_filter_path_payload["error_code"] == "VALIDATION_ERROR"
    assert "raw_secret" in invalid_filter_path_payload["error"]

    registry_response = await test_client.get(
        "/api/web/admin/helpdesk-model/policies",
        headers=_admin_headers(),
    )
    registry = (await registry_response.json())["data"]
    assert registry["summary"]["active_smart_views_count"] == 0
