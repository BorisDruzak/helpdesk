import uuid
from datetime import datetime, timezone

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
    Playbook,
    PlaybookRun,
    PlaybookVersion,
    PriorityPolicy,
    ReportingPolicy,
    RequestTemplate,
    RoutingPolicy,
    ServerConfig,
    SlaPolicy,
    SmartView,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketFormPack,
    TicketQueue,
    TicketSlaPolicy,
    TicketSlaTarget,
    TicketType,
    VisibilityPolicy,
)
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX
from tickets.form_catalog import validate_form_pack_schema, validate_form_submission


@pytest.mark.no_db
def test_validate_form_pack_schema_normalizes_on_behalf_policy():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.0",
            "title": "Catalog",
            "forms": [
                {
                    "key": "workplace_help",
                    "request_kind": "workplace_help",
                    "title": "Workplace help",
                    "on_behalf_policy": {
                        "allowed": True,
                        "reason_required": True,
                        "affected_person_required": True,
                        "allowed_scope": "same_department_or_privileged",
                        "no_primary_agent_behavior": "manual_support_review",
                        "support_override_allowed": True,
                    },
                    "fields": [
                        {"key": "summary", "label": "Summary", "type": "text", "required": True},
                    ],
                }
            ],
        }
    )

    policy = pack["forms"][0]["on_behalf_policy"]
    assert policy == {
        "allowed": True,
        "label": "Проблема у другого сотрудника",
        "affected_person_required": True,
        "reason_required": True,
        "allowed_scope": "same_department_or_privileged",
        "diagnostic_target": "affected_person_primary_agent",
        "knowledge_visibility": "creator_only",
        "support_visibility": "creator_and_affected",
        "no_primary_agent_behavior": "manual_support_review",
        "support_override_allowed": True,
    }


@pytest.mark.no_db
def test_validate_form_pack_schema_normalizes_availability_policy():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.0",
            "title": "Catalog",
            "forms": [
                {
                    "key": "emergency_access",
                    "request_kind": "incident",
                    "title": "Emergency access",
                    "availability_policy": {
                        "available_without_completed_profile": True,
                        "available_without_agent_binding": True,
                        "requires_manual_triage": True,
                        "contact_required": True,
                    },
                    "fields": [
                        {"key": "contact_phone", "label": "Contact phone", "type": "phone", "required": True},
                    ],
                },
                {
                    "key": "normal_request",
                    "request_kind": "request",
                    "title": "Normal request",
                    "fields": [
                        {"key": "summary", "label": "Summary", "type": "text", "required": False},
                    ],
                },
            ],
        }
    )

    emergency = next(form for form in pack["forms"] if form["key"] == "emergency_access")
    normal = next(form for form in pack["forms"] if form["key"] == "normal_request")

    assert emergency["availability_policy"] == {
        "available_without_completed_profile": True,
        "available_without_agent_binding": True,
        "requires_manual_triage": True,
        "contact_required": True,
        "allowed_for_anonymous": False,
    }
    assert emergency["available_without_completed_profile"] is True
    assert emergency["available_without_agent_binding"] is True
    assert emergency["requires_manual_triage"] is True
    assert emergency["contact_required"] is True
    assert emergency["allowed_for_anonymous"] is False
    assert normal["availability_policy"] == {
        "available_without_completed_profile": False,
        "available_without_agent_binding": False,
        "requires_manual_triage": False,
        "contact_required": False,
        "allowed_for_anonymous": False,
    }


@pytest.mark.no_db
def test_validate_form_pack_schema_omits_absent_on_behalf_policy():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.0",
            "title": "Catalog",
            "forms": [
                {
                    "key": "workplace_help",
                    "request_kind": "workplace_help",
                    "title": "Workplace help",
                    "fields": [
                        {"key": "summary", "label": "Summary", "type": "text", "required": True},
                    ],
                }
            ],
        }
    )

    assert "on_behalf_policy" not in pack["forms"][0]


@pytest.mark.no_db
def test_validate_form_pack_schema_rejects_invalid_on_behalf_policy_choice():
    with pytest.raises(ValueError, match="on_behalf_policy.allowed_scope"):
        validate_form_pack_schema(
            {
                "pack_key": "request_forms",
                "version": "1.0.0",
                "title": "Catalog",
                "forms": [
                    {
                        "key": "workplace_help",
                        "request_kind": "workplace_help",
                        "title": "Workplace help",
                        "on_behalf_policy": {
                            "allowed": True,
                            "allowed_scope": "external_company",
                        },
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        )


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_request_form_packs(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            delete(TicketFormPack).where(TicketFormPack.pack_key == "request_forms")
        )
        await session.execute(
            delete(ServerConfig).where(
                ServerConfig.key == f"{TICKET_FORM_PREFERRED_KEY_PREFIX}request_forms"
            )
        )
        await session.commit()


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


async def _ensure_fallback_queue(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(select(TicketQueue).where(TicketQueue.code == "servicedesk_l1"))
        if result.scalar_one_or_none() is None:
            session.add(TicketQueue(code="servicedesk_l1", name="ServiceDesk L1", is_triage=True, is_active=True))
            await session.commit()


async def _ensure_default_sla_policy(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(select(TicketSlaPolicy).where(TicketSlaPolicy.is_default.is_(True)))
        if result.scalar_one_or_none() is not None:
            return
        policy = TicketSlaPolicy(name="Default SLA", is_default=True, is_active=True)
        session.add(policy)
        await session.flush()
        session.add_all(
            [
                TicketSlaTarget(policy_id=policy.id, priority="P0", first_response_min=15, resolution_min=240),
                TicketSlaTarget(policy_id=policy.id, priority="P1", first_response_min=60, resolution_min=1440),
                TicketSlaTarget(policy_id=policy.id, priority="P2", first_response_min=240, resolution_min=4320),
                TicketSlaTarget(policy_id=policy.id, priority="P3", first_response_min=480, resolution_min=7200),
            ]
        )
        await session.commit()


async def _ensure_queue(test_engine, *, code: str, name: str) -> TicketQueue:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        result = await session.execute(select(TicketQueue).where(TicketQueue.code == code))
        queue = result.scalar_one_or_none()
        if queue is None:
            queue = TicketQueue(code=code, name=name, is_triage=False, is_active=True)
            session.add(queue)
            await session.flush()
        else:
            queue.name = name
            queue.is_active = True
        await session.commit()
        return queue


async def _publish_manual_priority_form_pack(test_client) -> None:
    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Manual priority test catalog",
                "forms": [
                    {
                        "key": "manual_priority_form",
                        "request_kind": "manual_priority_form",
                        "ticket_type": "incident",
                        "title": "Manual priority form",
                        "priority_policy": {
                            "impact_field": "affected_scope",
                            "urgency_field": "work_continuity",
                            "importance_field": "business_importance",
                            "matrix": {
                                "single_user": {
                                    "workaround_available": "P3",
                                },
                            },
                            "manual_override": {
                                "allowed_roles": ["admin"],
                                "require_reason": True,
                            },
                        },
                        "fields": [
                            {"key": "affected_scope", "label": "Scope", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Continuity", "type": "text", "required": True},
                            {"key": "business_importance", "label": "Importance", "type": "text", "required": False},
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()


def _manual_priority_create_payload(device_id: str) -> dict:
    return {
        "title": "Manual priority override",
        "description": "Manual priority override should be governed.",
        "device_id": device_id,
        "request_template_key": "manual_priority_form",
        "form_pack_key": "request_forms",
        "form_payload": {
            "affected_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
        "manual_priority": "P1",
    }


def _typed_forms_payload(form_key: str, *, title: str | None = None) -> dict:
    return {
        "title": "Каталог заявок",
        "description": "Typed forms lifecycle test",
        "forms": [
            {
                "key": form_key,
                "request_kind": form_key,
                "title": title or form_key.replace("_", " ").title(),
                "fields": [
                    {
                        "key": "room",
                        "label": "Кабинет",
                        "type": "text",
                        "required": True,
                        "options": [],
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_public_ticket_forms_current_returns_builtin_catalog(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    response = await test_client.get("/public_api/ticket_forms/current")
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    pack = data["pack"]
    assert pack["pack_key"] == "request_forms"
    form_keys = {form["key"] for form in pack.get("forms") or []}
    assert {"profile_completion_help", "agent_binding_help", "breakage", "access", "printer", "site_system"} <= form_keys
    profile_help = next(form for form in pack["forms"] if form["key"] == "profile_completion_help")
    agent_help = next(form for form in pack["forms"] if form["key"] == "agent_binding_help")
    for form in (profile_help, agent_help):
        assert form["availability_policy"] == {
            "available_without_completed_profile": True,
            "available_without_agent_binding": True,
            "requires_manual_triage": True,
            "contact_required": True,
            "allowed_for_anonymous": False,
        }
        assert form["ticket_type"] == "service_request"
    site_form = next(form for form in pack["forms"] if form["key"] == "site_system")
    assert site_form["priority_policy"]["impact_field"] == "impact_scope"
    assert site_form["priority_policy"]["urgency_field"] == "work_continuity"
    assert site_form["priority_policy"]["importance_field"] == "business_importance"
    assert {"impact_scope", "work_continuity", "business_importance"}.issubset(
        {field["key"] for field in site_form["fields"]}
    )
    assert "priority_impact" in site_form["field_roles"]["impact_scope"]


@pytest.mark.asyncio
async def test_admin_can_save_ticket_form_pack_and_switch_current_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "description": "Тестовая публикация каталога",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "description": "Проверка сохранения каталога",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "printer_model", "label": "Модель", "type": "text", "required": False},
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    data = await response.json()
    assert data["status"] == "ok"
    assert data["pack"]["version"] == "1.0.1"

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["status"] == "ok"
    assert current_data["pack"]["version"] == "1.0.1"
    assert current_data["pack"]["forms"][0]["fields"][0]["key"] == "room"
    assert current_data["pack"]["forms"][0]["ticket_type"] == "incident"
    assert "profile_completion_help" not in {form["key"] for form in current_data["pack"]["forms"]}

    public_current_response = await test_client.get("/public_api/ticket_forms/current?pack_key=request_forms")
    assert public_current_response.status == 200, await public_current_response.text()
    public_current_data = await public_current_response.json()
    assert public_current_data["pack"]["title"] == "Каталог обращений"
    public_form_keys = [form["key"] for form in public_current_data["pack"]["forms"]]
    assert public_form_keys[:2] == ["profile_completion_help", "agent_binding_help"]
    assert "printer" in public_form_keys


@pytest.mark.asyncio
async def test_web_admin_forms_save_draft_keeps_current_preferred_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    published = await test_client.post(
        "/api/web/admin/forms/save",
        json=_typed_forms_payload("printer", title="Печать / принтер"),
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert published.status == 200, await published.text()
    published_payload = await published.json()
    assert published_payload["data"]["summary"]["version"] == "1.0.1"

    draft = await test_client.post(
        "/api/web/admin/forms/save-draft",
        json={**_typed_forms_payload("printer_draft", title="Черновой принтер"), "base_version": "1.0.1"},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert draft.status == 200, await draft.text()
    draft_payload = await draft.json()
    assert draft_payload["data"]["status"] == "draft"
    assert draft_payload["data"]["published_version"] is None
    assert draft_payload["data"]["preferred_version"] == "1.0.1"

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["pack"]["version"] == "1.0.1"
    assert current_data["pack"]["forms"][0]["key"] == "printer"


@pytest.mark.asyncio
async def test_web_admin_forms_publish_can_leave_preferred_unchanged(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    initial = await test_client.post(
        "/api/web/admin/forms/save",
        json=_typed_forms_payload("printer", title="Печать / принтер"),
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert initial.status == 200, await initial.text()

    published = await test_client.post(
        "/api/web/admin/forms/publish",
        json={**_typed_forms_payload("access", title="Доступ"), "make_preferred": False},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert published.status == 200, await published.text()
    published_payload = await published.json()
    assert published_payload["data"]["published_version"] == "1.0.2"
    assert published_payload["data"]["preferred_version"] == "1.0.1"
    assert published_payload["data"]["made_preferred"] is False

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["pack"]["version"] == "1.0.1"
    assert current_data["pack"]["forms"][0]["key"] == "printer"


@pytest.mark.asyncio
async def test_web_admin_forms_preferred_switches_published_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    initial = await test_client.post(
        "/api/web/admin/forms/save",
        json=_typed_forms_payload("printer", title="Печать / принтер"),
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert initial.status == 200, await initial.text()

    published = await test_client.post(
        "/api/web/admin/forms/publish",
        json={**_typed_forms_payload("access", title="Доступ"), "make_preferred": False},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert published.status == 200, await published.text()

    preferred = await test_client.patch(
        "/api/web/admin/forms/preferred",
        json={"version": "1.0.2"},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert preferred.status == 200, await preferred.text()
    preferred_payload = await preferred.json()
    assert preferred_payload["data"]["previous_version"] == "1.0.1"
    assert preferred_payload["data"]["preferred_version"] == "1.0.2"

    current_response = await test_client.get(
        "/api/ticket_forms/current?pack_key=request_forms",
        headers=_admin_headers(),
    )
    assert current_response.status == 200, await current_response.text()
    current_data = await current_response.json()
    assert current_data["pack"]["version"] == "1.0.2"
    assert current_data["pack"]["forms"][0]["key"] == "access"


@pytest.mark.asyncio
async def test_web_admin_forms_validate_returns_business_preflight_report(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    response = await test_client.post(
        "/api/web/admin/forms/validate",
        json=_typed_forms_payload("printer", title="Printer"),
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    data = payload["data"]
    warning_codes = {issue["code"] for issue in data["warnings"]}

    assert data["summary"]["errors_count"] == 0
    assert data["summary"]["can_publish"] is True
    assert {
        "REQUIRED_FIELD_HELP_TEXT_MISSING",
        "PUBLIC_TITLE_MISSING",
        "SLA_POLICY_MISSING",
    } <= warning_codes


@pytest.mark.asyncio
async def test_web_admin_forms_validate_accepts_existing_base_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    published = await test_client.post(
        "/api/web/admin/forms/save",
        json=_typed_forms_payload("printer", title="Печать / принтер"),
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert published.status == 200, await published.text()

    response = await test_client.post(
        "/api/web/admin/forms/validate",
        json={**_typed_forms_payload("printer", title="Печать / принтер"), "base_version": "1.0.1"},
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["summary"]["can_publish"] is True


@pytest.mark.asyncio
async def test_web_admin_forms_publish_blocks_missing_business_refs(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    payload = _typed_forms_payload("website_unavailable", title="Website unavailable")
    payload["forms"][0]["default_queue_id"] = 999_999_991

    response = await test_client.post(
        "/api/web/admin/forms/publish",
        json=payload,
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 400, await response.text()
    error = await response.json()
    assert error["error_code"] == "VALIDATION_ERROR"
    assert "ROUTING_QUEUE_NOT_FOUND" in error["error"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        stored = (
            await session.execute(select(TicketFormPack).where(TicketFormPack.pack_key == "request_forms"))
        ).scalars().all()
    assert stored == []


@pytest.mark.asyncio
async def test_admin_save_auto_increments_internal_pack_version(test_client, test_engine):
    await _clear_request_form_packs(test_engine)

    payload = {
        "pack": {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "description": "Автоматический выпуск",
            "forms": [
                {
                    "key": "printer",
                    "request_kind": "printer",
                    "title": "Печать / принтер",
                    "fields": [
                        {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                    ],
                }
            ],
        }
    }

    first = await test_client.post(
        "/api/ticket_forms/packs/save",
        json=payload,
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert first.status == 200, await first.text()
    assert (await first.json())["pack"]["version"] == "1.0.1"

    payload["pack"]["description"] = "Автоматический выпуск 2"
    second = await test_client.post(
        "/api/ticket_forms/packs/save",
        json=payload,
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert second.status == 200, await second.text()
    second_data = await second.json()
    assert second_data["pack"]["version"] == "1.0.2"


@pytest.mark.asyncio
async def test_admin_save_rejects_duplicate_form_key(test_client):
    response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [{"key": "room", "label": "Кабинет", "type": "text", "required": True}],
                    },
                    {
                        "key": "printer",
                        "request_kind": "printer_duplicate",
                        "title": "Дубликат",
                        "fields": [{"key": "room_2", "label": "Кабинет 2", "type": "text", "required": False}],
                    },
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 400, await response.text()
    data = await response.json()
    assert data["error"] == "validation_error"
    assert "duplicate form key" in str(data["details"])


@pytest.mark.asyncio
async def test_create_ticket_accepts_form_payload_and_sets_ticket_type(test_client, test_engine):
    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Paper jam on floor 2",
            "device_id": device_id,
            "user_display_name": "Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "printer_model": "HP LaserJet",
                "printer_number": "PR-17",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.ticket_type == "incident"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_kind"] == "printer"
    assert custom_fields["request_form_key"] == "printer"
    assert custom_fields["request_form_data"]["room"] == "214"
    assert custom_fields["request_form_data"]["printer_model"] == "HP LaserJet"


@pytest.mark.asyncio
async def test_create_ticket_accepts_request_template_key_as_form_alias(test_client, test_engine):
    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Обращение: Печать / принтер",
            "description": "Принтер не печатает",
            "device_id": device_id,
            "user_display_name": "Alice",
            "request_template_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "service_request",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.ticket_type == "incident"
    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_form_key"] == "printer"
    assert custom_fields["request_template"]["key"] == "printer"
    assert custom_fields["request_form_data"]["room"] == "214"


@pytest.mark.asyncio
async def test_create_ticket_preserves_form_schema_and_policy_refs_in_template_context(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    form_key = f"schema_template_{uuid.uuid4().hex[:8]}"
    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Schema templates",
                "forms": [
                    {
                        "key": form_key,
                        "request_template_key": form_key,
                        "request_template_title": "Schema-backed request",
                        "request_kind": form_key,
                        "title": "Schema-backed request",
                        "ticket_type": "incident",
                        "form_schema_id": f"{form_key}_schema",
                        "form_schema_version": 7,
                        "request_template_version": 3,
                        "workflow_profile_id": "incident_default",
                        "priority_policy_code": "incident_priority_policy",
                        "routing_policy_code": "schema_routing",
                        "sla_policy_code": "incident_sla",
                        "closure_policy_code": "incident_closure",
                        "policy_refs": {
                            "form_schema": f"{form_key}_schema@7",
                            "routing": "schema_routing@2",
                        },
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Schema-backed request",
            "description": "Schema metadata smoke",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "request_template_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {"summary": "Metadata should survive"},
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    template = ticket.custom_fields["request_template"]
    assert template["key"] == form_key
    assert template["form_schema_id"] == f"{form_key}_schema"
    assert template["form_schema_version"] == 7
    assert template["request_template_version"] == 3
    assert template["workflow_profile_id"] == "incident_default"
    assert template["priority_policy_code"] == "incident_priority_policy"
    assert template["routing_policy_code"] == "schema_routing"
    assert template["sla_policy_code"] == "incident_sla"
    assert template["closure_policy_code"] == "incident_closure"
    assert template["policy_refs"]["form_schema"] == f"{form_key}_schema@7"


@pytest.mark.asyncio
async def test_create_ticket_accepts_standalone_helpdesk_registry_template(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    template_code = f"registry_template_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        form_schema = await repo.publish_form_schema(
            schema_id=f"{template_code}_form",
            title="Registry-backed form",
            form_key=template_code,
            request_template_code=template_code,
            ticket_type="incident",
            fields=[
                {"key": "summary", "label": "Summary", "type": "text", "required": True},
                {"key": "impact_scope", "label": "Impact", "type": "select", "required": True, "options": [{"value": "single_user", "label": "Single user"}]},
            ],
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_request_template(
            template_code=template_code,
            public_title="Registry-backed request",
            internal_name="Registry-backed request",
            ticket_type="incident",
            form_schema_id=form_schema["schema_id"],
            workflow_profile_id="incident",
            actor_id="test",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Registry standalone create",
            "description": "Create from standalone helpdesk registry template",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "request_template_key": template_code,
            "form_pack_key": "request_forms",
            "form_payload": {"summary": "Registry path works", "impact_scope": "single_user"},
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.ticket_type == "incident"
    assert ticket.custom_fields["request_form_key"] == template_code
    assert ticket.custom_fields["request_template"]["key"] == template_code
    assert ticket.custom_fields["request_template"]["form_schema_id"] == f"{template_code}_form"
    assert ticket.custom_fields["request_form_data"]["summary"] == "Registry path works"


@pytest.mark.asyncio
async def test_public_create_ticket_accepts_standalone_helpdesk_registry_template(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    template_code = f"public_registry_template_{uuid.uuid4().hex[:8]}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        form_schema = await repo.publish_form_schema(
            schema_id=f"{template_code}_form",
            title="Public registry-backed form",
            form_key=template_code,
            request_template_code=template_code,
            ticket_type="request",
            fields=[
                {"key": "question", "label": "Question", "type": "textarea", "required": True},
                {"key": "impact_scope", "label": "Impact", "type": "select", "required": True, "options": [{"value": "single_user", "label": "Single user"}]},
            ],
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_request_template(
            template_code=template_code,
            public_title="Public registry-backed request",
            internal_name="Public registry-backed request",
            ticket_type="request",
            form_schema_id=form_schema["schema_id"],
            workflow_profile_id="request",
            actor_id="test",
            actor_role="admin",
        )
        await session.commit()

    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Public registry standalone create",
            "description": "Create public ticket from standalone registry template",
            "user_display_name": "Public Alice",
            "request_template_key": template_code,
            "form_pack_key": "request_forms",
            "form_payload": {"question": "Registry public path works", "impact_scope": "single_user"},
            "urgency": False,
            "importance": False,
            "urgency_reason": "not urgent",
            "importance_reason": "normal",
        },
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.ticket_type == "request"
    assert ticket.custom_fields["request_form_key"] == template_code
    assert ticket.custom_fields["request_template"]["key"] == template_code
    assert ticket.custom_fields["request_form_data"]["question"] == "Registry public path works"


@pytest.mark.asyncio
async def test_create_ticket_accepts_old_form_key_payload_without_injected_priority_fields(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    form_key = f"legacy_minimal_{uuid.uuid4().hex[:8]}"
    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Legacy minimal forms",
                "forms": [
                    {
                        "key": form_key,
                        "request_kind": form_key,
                        "ticket_type": "incident",
                        "title": "Legacy minimal incident",
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={"Authorization": "Bearer test-ui-admin-token", "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Legacy minimal request",
            "description": "Old client sends only original fields",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {"summary": "Network is unstable"},
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    custom_fields = ticket.custom_fields or {}
    assert custom_fields["request_form_key"] == form_key
    assert custom_fields["request_form_data"] == {"summary": "Network is unstable"}
    assert custom_fields["priority_decision"]["effective_priority"] in {"P0", "P1", "P2", "P3"}


@pytest.mark.asyncio
async def test_create_ticket_preview_returns_effective_template_context(test_client, test_engine):
    await _ensure_fallback_queue(test_engine)
    await _ensure_default_sla_policy(test_engine)

    response = await test_client.post(
        "/api/tickets/create/preview",
        json={
            "request_template_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "impact_scope": "department",
                "work_continuity": "work_stopped_no_workaround",
                "business_importance": "deadline_today",
            },
            "ticket_type": "service_request",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    preview = payload["preview"]

    assert preview["request_template_key"] == "printer"
    assert preview["request_template_title"] == "Печать / принтер"
    assert preview["ticket_type"] == "incident"
    assert preview["priority"]["priority_class"] in {"P0", "P1", "P2", "P3"}
    assert preview["routing"]["target_queue_id"] is not None
    assert preview["routing"]["fallback_applied"] is True
    assert preview["sla"]["first_response_due_at"]
    assert preview["sla"]["resolution_due_at"]
    assert {"key": "room", "label": "Кабинет", "value": "214"} in preview["summary_rows"]


@pytest.mark.asyncio
async def test_create_ticket_manual_priority_override_requires_reason(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _ensure_fallback_queue(test_engine)
    await _publish_manual_priority_form_pack(test_client)

    response = await test_client.post(
        "/api/tickets/create",
        json=_manual_priority_create_payload(str(uuid.uuid4())),
        headers={"Authorization": "Bearer test-ui-admin-token"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["details"]["form_payload"] == "manual_reason is required for manual priority override"


@pytest.mark.asyncio
async def test_create_ticket_manual_priority_override_rejects_requester_role(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _ensure_fallback_queue(test_engine)
    await _publish_manual_priority_form_pack(test_client)
    body = _manual_priority_create_payload(str(uuid.uuid4()))
    body["manual_reason"] = "Requester tries to force priority."

    response = await test_client.post(
        "/api/tickets/create",
        json=body,
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["details"]["form_payload"] == "manual priority override is not allowed for this role"


@pytest.mark.asyncio
async def test_public_create_ticket_manual_priority_override_rejects_requester(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _publish_manual_priority_form_pack(test_client)
    body = _manual_priority_create_payload(str(uuid.uuid4()))
    body.pop("device_id")
    body["user_display_name"] = "Public requester"
    body["manual_reason"] = "Public requester tries to force priority."
    body["urgency"] = False
    body["importance"] = False
    body["urgency_reason"] = "Public create baseline"
    body["importance_reason"] = "Public create baseline"

    response = await test_client.post("/public_api/tickets/create", json=body)

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["details"]["form_payload"] == "manual priority override is not allowed for this role"


@pytest.mark.asyncio
async def test_public_create_ticket_manual_priority_override_rejects_legacy_policy_without_role_list(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Public manual override",
            "description": "Requester must not force priority.",
            "user_display_name": "Public requester",
            "request_template_key": "site_system",
            "form_pack_key": "request_forms",
            "form_payload": {
                "issue_kind": "site_down",
                "system_name": "Stage19",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "manual_priority": "P1",
            "manual_reason": "Requester tries to force priority.",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Public create baseline",
            "importance_reason": "Public create baseline",
        },
    )

    assert response.status == 400, await response.text()
    payload = await response.json()
    assert payload["details"]["form_payload"] == "manual priority override is not allowed for this role"


@pytest.mark.asyncio
async def test_public_create_ticket_allows_false_priority_flags_without_reasons(test_client, test_engine):
    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Public catalog create with false priority flags",
            "description": "Requester submits a normal non-urgent ticket.",
            "user_display_name": "Public requester",
            "request_template_key": "network",
            "form_key": "network",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "606",
                "pc_name": "p6-test-pc",
                "affected_scope": "single",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "urgency": False,
            "importance": False,
        },
    )

    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.ticket_type == "incident"


@pytest.mark.asyncio
async def test_create_ticket_stores_diagnostic_consent(test_client, test_engine):
    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Обращение: Печать / принтер",
            "description": "Принтер не печатает",
            "device_id": device_id,
            "user_display_name": "Alice",
            "request_template_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "diagnostic_consent": {
                "required": True,
                "granted": True,
                "scope": "requester_device",
                "source": "pc_agent_create",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.custom_fields["diagnostic_consent"] == {
        "required": True,
        "granted": True,
        "scope": "requester_device",
        "source": "pc_agent_create",
    }


@pytest.mark.asyncio
async def test_public_create_ticket_stores_diagnostic_consent(test_client, test_engine):
    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Обращение: Печать / принтер",
            "description": "Принтер не печатает",
            "user_display_name": "Public Alice",
            "request_template_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "diagnostic_consent": {
                "required": True,
                "granted": False,
                "scope": "requester_device",
                "source": "public_request_create",
            },
            "urgency": False,
            "importance": False,
            "urgency_reason": "Публичное обращение",
            "importance_reason": "Публичное обращение",
        },
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (
            await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))
        ).scalar_one()

    assert ticket.custom_fields["diagnostic_consent"] == {
        "required": True,
        "granted": False,
        "scope": "requester_device",
        "source": "public_request_create",
    }


@pytest.mark.asyncio
async def test_create_ticket_from_form_starts_configured_playbook(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    playbook_key = f"printer.quick_diag.{uuid.uuid4().hex[:8]}"

    async with session_maker() as session:
        playbook = Playbook(
            key=playbook_key,
            name="Быстрая диагностика принтера",
            domain="diagnostics",
            owner="tests",
            archived=False,
        )
        session.add(playbook)
        await session.flush()
        session.add(
            PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    pack_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "symptom", "label": "Симптом", "type": "text", "required": True},
                        ],
                        "playbook_triggers": [
                            {
                                "event": "ticket_created",
                                "playbook_key": playbook_key,
                                "module_kind": "diagnostic",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert pack_response.status == 200, await pack_response.text()

    device_id = str(uuid.uuid4())
    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Paper jam on floor 2",
            "device_id": device_id,
            "user_display_name": "Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "symptom": "Не печатает",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        run = (
            await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == device_id))
        ).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "playbook_started",
                )
            )
        ).scalar_one()

    assert run.trigger_type == "ticket_created"
    request_form_data = run.context_json["facts_package"]["request_form_data"]
    assert request_form_data["room"] == "214"
    assert request_form_data["symptom"] == "Не печатает"
    assert request_form_data["impact_scope"] == "single_user"
    assert event.payload["playbook_key"] == playbook_key
    assert event.payload["playbook_run_id"] == run.id
    assert event.payload["facts_package"]["request_form_summary"][0] == {
        "key": "room",
        "label": "Кабинет",
        "value": "214",
    }


@pytest.mark.asyncio
async def test_public_create_ticket_from_form_starts_configured_playbook(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    playbook_key = f"public_printer_diag_{uuid.uuid4().hex[:8]}"

    async with session_maker() as session:
        playbook = Playbook(
            key=playbook_key,
            name="Публичная диагностика принтера",
            domain="diagnostics",
            owner="tests",
            archived=False,
        )
        session.add(playbook)
        await session.flush()
        session.add(
            PlaybookVersion(
                playbook_id=playbook.id,
                version="1.0.0",
                manifest_json={},
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    pack_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "fields": [
                            {"key": "room", "label": "Кабинет", "type": "text", "required": True},
                            {"key": "symptom", "label": "Симптом", "type": "text", "required": True},
                        ],
                        "playbook_triggers": [
                            {
                                "event": "ticket_created",
                                "playbook_key": playbook_key,
                                "module_kind": "diagnostic",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert pack_response.status == 200, await pack_response.text()

    response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Printer public issue",
            "description": "Printer does not print",
            "user_display_name": "Public Alice",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "symptom": "Не печатает",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Live/public request",
            "importance_reason": "Live/public request",
        },
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        run = (
            await session.execute(select(PlaybookRun).where(PlaybookRun.device_id == ticket.device_id))
        ).scalar_one()
        event = (
            await session.execute(
                select(TicketEvent).where(
                    TicketEvent.ticket_id == ticket_id,
                    TicketEvent.event_type == "playbook_started",
                )
            )
        ).scalar_one()

    assert run.trigger_type == "ticket_created"
    request_form_data = run.context_json["facts_package"]["request_form_data"]
    assert request_form_data["room"] == "214"
    assert request_form_data["symptom"] == "Не печатает"
    assert request_form_data["impact_scope"] == "single_user"
    assert event.payload["playbook_key"] == playbook_key
    assert event.payload["playbook_run_id"] == run.id


def test_validate_form_pack_schema_rejects_unknown_visible_when_field():
    with pytest.raises(ValueError, match="visible_when.field"):
        validate_form_pack_schema(
            {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Принтер",
                        "fields": [
                            {
                                "key": "room",
                                "label": "Кабинет",
                                "type": "text",
                                "required": True,
                            },
                            {
                                "key": "printer_model",
                                "label": "Модель",
                                "type": "text",
                                "required": False,
                                "visible_when": {"field": "missing_field", "equals": "214"},
                            },
                        ],
                    }
                ],
            },
            require_version=False,
        )


def test_validate_form_submission_applies_visible_when_equals():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "site_system",
                    "request_kind": "site_system",
                    "title": "Сайт и система",
                    "fields": [
                        {
                            "key": "issue_kind",
                            "label": "Тип проблемы",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"value": "site_down", "label": "Сайт недоступен"},
                                {"value": "auth", "label": "Вход"},
                            ],
                        },
                        {
                            "key": "url",
                            "label": "URL",
                            "type": "text",
                            "required": False,
                            "visible_when": {"field": "issue_kind", "equals": "site_down"},
                        },
                    ],
                }
            ],
        },
        require_version=False,
    )

    visible = validate_form_submission(
        pack,
        form_key="site_system",
        raw_values={
            "issue_kind": "site_down",
            "url": "https://helpdesk.local",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )
    hidden = validate_form_submission(
        pack,
        form_key="site_system",
        raw_values={
            "issue_kind": "auth",
            "url": "https://should-not-pass.local",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )

    assert visible["submitted_values"]["url"] == "https://helpdesk.local"
    assert ["issue_kind", "url"] == [item["key"] for item in visible["summary_rows"][:2]]
    assert "impact_scope" in [item["key"] for item in visible["summary_rows"]]
    assert "url" not in hidden["submitted_values"]
    assert [item["key"] for item in hidden["summary_rows"][:1]] == ["issue_kind"]
    assert "impact_scope" in [item["key"] for item in hidden["summary_rows"]]


def test_validate_form_submission_accepts_extended_field_types():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.0",
            "title": "Каталог обращений",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "ticket_type": "incident",
                    "title": "Не открывается сайт",
                    "fields": [
                        {"key": "target_url", "label": "Адрес", "type": "url", "required": True},
                        {"key": "started_at", "label": "Когда началось", "type": "datetime", "required": True},
                        {
                            "key": "symptoms",
                            "label": "Симптомы",
                            "type": "multi_select",
                            "required": True,
                            "options": [
                                {"value": "dns", "label": "DNS"},
                                {"value": "proxy", "label": "Прокси"},
                            ],
                        },
                        {"key": "owner", "label": "Владелец", "type": "user_picker", "required": False},
                        {"key": "contact_email", "label": "Email", "type": "email", "required": False},
                    ],
                }
            ],
        }
    )

    submission = validate_form_submission(
        pack,
        form_key="website_unavailable",
        raw_values={
            "target_url": "https://example.test",
            "started_at": "2026-05-01T09:30",
            "symptoms": ["dns", "proxy"],
            "owner": "ivan.petrov",
            "contact_email": "ivan@example.test",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )

    assert submission["submitted_values"]["symptoms"] == ["dns", "proxy"]
    assert submission["submitted_values"]["target_url"] == "https://example.test"
    summary = {item["key"]: item["value"] for item in submission["summary_rows"]}
    assert summary["symptoms"] == "DNS, Прокси"


def test_validate_form_pack_schema_rejects_file_field_without_draft_upload():
    with pytest.raises(ValueError, match="unsupported type 'file'"):
        validate_form_pack_schema(
            {
                "pack_key": "request_forms",
                "version": "1.0.0",
                "title": "Каталог обращений",
                "forms": [
                    {
                        "key": "file_guard",
                        "request_kind": "file_guard",
                        "title": "Файловое поле",
                        "fields": [
                            {"key": "attachment", "label": "Файл", "type": "file", "required": False},
                        ],
                    }
                ],
            }
        )


def test_validate_form_submission_enforces_dynamic_field_constraints_server_side():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.0",
            "title": "Каталог обращений",
            "forms": [
                {
                    "key": "dynamic_guard",
                    "request_kind": "dynamic_guard",
                    "title": "Проверка динамических правил",
                    "fields": [
                        {
                            "key": "request_type",
                            "label": "Тип",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"value": "hardware", "label": "Оборудование"},
                                {"value": "access", "label": "Доступ"},
                            ],
                        },
                        {"key": "contact_email", "label": "Email", "type": "email", "required": True},
                        {"key": "target_url", "label": "URL", "type": "url", "required": True},
                        {"key": "seats", "label": "Мест", "type": "number", "validation": {"min": 1, "max": 3}},
                        {"key": "code", "label": "Код", "type": "text", "validation": {"min_length": 3, "max_length": 5, "pattern": "^[A-Z]+$"}},
                        {
                            "key": "access_reason",
                            "label": "Причина доступа",
                            "type": "text",
                            "required": True,
                            "visible_when": {"field": "request_type", "equals": "access"},
                        },
                    ],
                }
            ],
        }
    )

    valid = validate_form_submission(
        pack,
        form_key="dynamic_guard",
        raw_values={
            "request_type": "hardware",
            "contact_email": "ivan@example.test",
            "target_url": "https://example.test",
            "seats": "2",
            "code": "ABC",
            "access_reason": "forged hidden value",
        },
    )
    assert valid["submitted_values"]["seats"] == 2
    assert "access_reason" not in valid["submitted_values"]

    with pytest.raises(ValueError) as exc:
        validate_form_submission(
            pack,
            form_key="dynamic_guard",
            raw_values={
                "request_type": "hardware",
                "contact_email": "not-email",
                "target_url": "ftp://example.test",
                "seats": "7",
                "code": "ab",
                "access_reason": "still hidden",
            },
        )

    errors = exc.value.args[0]
    assert {"contact_email", "target_url", "seats", "code"} <= set(errors)
    assert "access_reason" not in errors


def test_validate_form_pack_schema_preserves_request_template_process_context():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "ticket_type": "incident",
                    "title": "Не открывается сайт",
                    "category_id": 10,
                    "service_id": 20,
                    "subcategory_id": 30,
                    "default_queue_id": 40,
                    "sla_policy_id": 50,
                    "suggested_playbook_id": "diagnose.website",
                    "field_roles": {
                        "url": ["routing_field", "diagnostic_input"],
                        "affected_scope": ["priority_field"],
                    },
                    "priority_policy": {
                        "impact_field": "affected_scope",
                        "urgency_field": "work_continuity",
                    },
                    "approval_policy": {"required": False},
                    "closure_policy": {"require_resolution_code": True},
                    "notification_policy": {"on_status_changed": {"requester": True}},
                    "fields": [
                        {"key": "url", "label": "URL", "type": "text", "required": True},
                        {"key": "affected_scope", "label": "Кого затронуло", "type": "text"},
                    ],
                }
            ],
        },
        require_version=False,
    )

    form = pack["forms"][0]
    assert form["ticket_type"] == "incident"
    assert form["category_id"] == 10
    assert form["service_id"] == 20
    assert form["subcategory_id"] == 30
    assert form["default_queue_id"] == 40
    assert form["sla_policy_id"] == 50
    assert form["suggested_playbook_id"] == "diagnose.website"
    assert form["field_roles"]["url"] == ["routing_field", "diagnostic_input"]
    assert form["priority_policy"]["impact_field"] == "affected_scope"
    assert form["closure_policy"]["require_resolution_code"] is True
    assert form["notification_policy"]["on_status_changed"]["requester"] is True


def test_validate_form_pack_schema_accepts_canonical_field_role_enum_and_legacy_roles():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "title": "Website unavailable",
                    "field_roles": {
                        "impact_scope": ["priority_impact"],
                        "work_continuity": ["priority_urgency"],
                        "legacy_priority": ["priority_field"],
                    },
                    "fields": [
                        {"key": "impact_scope", "label": "Impact", "type": "text"},
                        {"key": "work_continuity", "label": "Urgency", "type": "text"},
                        {"key": "legacy_priority", "label": "Legacy priority", "type": "text"},
                    ],
                }
            ],
        },
        require_version=False,
    )

    form = pack["forms"][0]
    assert form["field_roles"]["impact_scope"] == ["priority_impact"]
    assert form["field_roles"]["work_continuity"] == ["priority_urgency"]
    assert form["field_roles"]["legacy_priority"] == ["priority_field"]


def test_validate_form_pack_schema_rejects_unknown_field_role():
    with pytest.raises(ValueError, match="unsupported role"):
        validate_form_pack_schema(
            {
                "pack_key": "request_forms",
                "title": "Request catalog",
                "forms": [
                    {
                        "key": "website_unavailable",
                        "request_kind": "website_unavailable",
                        "title": "Website unavailable",
                        "field_roles": {"impact_scope": ["priority_magic"]},
                        "fields": [
                            {"key": "impact_scope", "label": "Impact", "type": "text"},
                        ],
                    }
                ],
            },
            require_version=False,
        )


def test_validate_form_pack_schema_preserves_preflight_metadata():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "title": "Website unavailable",
                    "field_aliases": {"website_url": "target_url"},
                    "field_migration_note": "target_url renamed to website_url",
                    "route_preview_examples": [{"name": "DNS", "form_payload": {"website_url": "example.test"}}],
                    "process_preview_examples": [{"name": "P1", "form_payload": {"website_url": "example.test"}}],
                    "fields": [
                        {"key": "website_url", "label": "URL", "type": "text", "required": True},
                    ],
                }
            ],
        },
        require_version=False,
    )

    form = pack["forms"][0]
    assert form["field_aliases"] == {"website_url": "target_url"}
    assert form["field_migration_note"] == "target_url renamed to website_url"
    assert form["route_preview_examples"][0]["name"] == "DNS"
    assert form["process_preview_examples"][0]["name"] == "P1"


def test_validate_form_pack_schema_preserves_canonical_policy_refs():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "website_unavailable",
                    "request_kind": "website_unavailable",
                    "title": "Website unavailable",
                    "priority_policy_ref": "incident_priority_v2",
                    "routing_policy_ref": "website_routing_v5",
                    "sla_policy_ref": "incident_sla_v3",
                    "ola_policy_ref": "queue_ola_v1",
                    "approval_policy_ref": "manager_approval_v1",
                    "diagnostic_policy_ref": "website_diagnostics_v2",
                    "closure_policy_ref": "incident_closure_v1",
                    "visibility_policy_ref": "requester_visibility_v1",
                    "notification_policy_ref": "incident_notifications_v1",
                    "reporting_policy_ref": "incident_reporting_v1",
                    "priority_policy": {"impact_field": "legacy_inline"},
                    "fields": [
                        {"key": "url", "label": "URL", "type": "text", "required": True},
                    ],
                }
            ],
        },
        require_version=False,
    )

    form = pack["forms"][0]
    assert form["priority_policy_ref"] == "incident_priority_v2"
    assert form["priority_policy_code"] == "incident_priority_v2"
    assert form["routing_policy_code"] == "website_routing_v5"
    assert form["sla_policy_code"] == "incident_sla_v3"
    assert form["policy_refs"] == {
        "priority": "incident_priority_v2",
        "routing": "website_routing_v5",
        "sla": "incident_sla_v3",
        "ola": "queue_ola_v1",
        "approval": "manager_approval_v1",
        "diagnostic": "website_diagnostics_v2",
        "closure": "incident_closure_v1",
        "visibility": "requester_visibility_v1",
        "notification": "incident_notifications_v1",
        "reporting": "incident_reporting_v1",
    }
    assert form["priority_policy"]["impact_field"] == "legacy_inline"


def test_validate_form_pack_schema_preserves_custom_ticket_type():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Request catalog",
            "forms": [
                {
                    "key": "custom_access",
                    "request_kind": "custom_access",
                    "ticket_type": "custom_access_process",
                    "title": "Custom access",
                    "fields": [
                        {"key": "system", "label": "System", "type": "text", "required": True},
                    ],
                }
            ],
        },
        require_version=False,
    )

    assert pack["forms"][0]["ticket_type"] == "custom_access_process"


@pytest.mark.asyncio
async def test_create_ticket_uses_template_ticket_type_over_request_body(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    category_id = 700_000 + int(uuid.uuid4().hex[:6], 16)
    service_id = category_id + 1
    subcategory_id = category_id + 2
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                TicketCategory(id=category_id, code=f"web-{category_id}", name="Web", level=1),
                TicketCategory(id=service_id, code=f"reports-{service_id}", name="Reports", parent_id=category_id, level=2),
                TicketCategory(
                    id=subcategory_id,
                    code=f"unavailable-{subcategory_id}",
                    name="Website unavailable",
                    parent_id=service_id,
                    level=3,
                ),
            ]
        )
        await session.commit()

    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "Каталог заявок",
                "forms": [
                        {
                            "key": "website_unavailable",
                            "request_kind": "website_unavailable",
                            "ticket_type": "incident",
                            "title": "Не открывается сайт",
                            "category_id": category_id,
                            "service_id": service_id,
                            "subcategory_id": subcategory_id,
                        "suggested_playbook_id": "diagnose.website",
                        "field_roles": {"url": ["routing_field", "diagnostic_input"]},
                        "fields": [
                            {"key": "url", "label": "URL", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Website issue",
            "description": "Cannot open reporting site",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "website_unavailable",
            "form_pack_key": "request_forms",
            "form_payload": {
                "url": "https://reports.example.local",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "consultation",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.ticket_type == "incident"
    assert ticket.category_id == category_id
    assert ticket.service_id == service_id
    assert ticket.subcategory_id == subcategory_id
    assert ticket.custom_fields["request_kind"] == "website_unavailable"
    assert ticket.custom_fields["request_template"]["key"] == "website_unavailable"
    assert ticket.custom_fields["request_template"]["ticket_type"] == "incident"
    assert ticket.custom_fields["request_template"]["suggested_playbook_id"] == "diagnose.website"


@pytest.mark.asyncio
async def test_create_ticket_stores_legacy_form_source_and_computed_snapshot(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    await _clear_request_form_packs(test_engine)
    network_queue = await _ensure_queue(
        test_engine,
        code=f"networks_{uuid.uuid4().hex[:8]}",
        name="Networks",
    )
    form_key = f"website_snapshot_{uuid.uuid4().hex[:8]}"

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
                        "title": "Проблема с сайтом",
                        "priority_policy": {
                            "impact_field": "impact_scope",
                            "urgency_field": "work_continuity",
                            "matrix": {"department": {"blocked": "P1"}},
                        },
                        "routing_policy": {
                            "rules": [
                                {
                                    "code": "website_department_to_networks",
                                    "priority_order": 10,
                                    "when": {
                                        "field": "request_form_data.impact_scope",
                                        "op": "eq",
                                        "value": "department",
                                    },
                                    "then": {"queue_id": network_queue.id},
                                }
                            ]
                        },
                        "fields": [
                            {"key": "impact_scope", "label": "Impact", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Continuity", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    create_response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Website issue",
            "description": "Department cannot open the site",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {
                "impact_scope": "department",
                "work_continuity": "blocked",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    custom_fields = ticket.custom_fields
    assert custom_fields["request_form"] == {
        "source": "legacy_pack",
        "pack_key": "request_forms",
        "pack_version": custom_fields["request_form_version"],
        "form_key": form_key,
        "form_title": "Проблема с сайтом",
        "form_schema_version": custom_fields["request_form_version"],
        "request_template_key": form_key,
    }
    assert custom_fields["resolved_from"] == "legacy_pack"
    computed = custom_fields["request_template"]["computed"]
    assert computed["priority"] == "P1"
    assert computed["queue_id"] == network_queue.id
    assert computed["queue_code"] == network_queue.code
    assert computed["matched_routing_rule"] == "website_department_to_networks"
    assert computed["routing_source"] == "request_template.routing_policy"

    requester_response = await test_client.get(
        f"/api/tickets/{ticket_id}",
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert requester_response.status == 200, await requester_response.text()
    requester_ticket = (await requester_response.json())["ticket"]
    assert "request_template" not in requester_ticket["custom_fields"]

    preview_response = await test_client.post(
        "/api/tickets/create/preview",
        json={
            "device_id": str(uuid.uuid4()),
            "title": "Preview",
            "description": "Preview website issue",
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {
                "impact_scope": "department",
                "work_continuity": "blocked",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert preview_response.status == 200, await preview_response.text()
    preview = (await preview_response.json())["preview"]
    assert preview["request_form"]["source"] == "legacy_pack"
    assert preview["request_form"]["form_key"] == form_key
    assert preview["request_template"]["computed"]["priority"] == "P1"
    assert preview["request_template"]["computed"]["queue_code"] == network_queue.code
    assert preview["request_template"]["computed"]["matched_routing_rule"] == "website_department_to_networks"


@pytest.mark.asyncio
async def test_create_ticket_uses_standalone_registry_source_snapshot(test_client, test_engine):
    await _clear_policy_registry(test_engine)
    await _clear_request_form_packs(test_engine)
    await _ensure_fallback_queue(test_engine)
    template_key = f"standalone_snapshot_{uuid.uuid4().hex[:8]}"
    schema_id = f"{template_key}_schema"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        repo = HelpdeskPolicyRepo(session)
        await repo.publish_form_schema(
            schema_id=schema_id,
            request_template_code=template_key,
            form_key=template_key,
            title="Standalone snapshot",
            ticket_type="incident",
            fields=[
                {"key": "impact_scope", "label": "Impact", "type": "text", "required": True},
                {"key": "work_continuity", "label": "Continuity", "type": "text", "required": True},
            ],
            config={
                "priority_policy": {
                    "impact_field": "impact_scope",
                    "urgency_field": "work_continuity",
                    "matrix": {"department": {"blocked": "P1"}},
                }
            },
            actor_id="admin1",
            actor_role="admin",
            requested_version="2.4.0",
        )
        await repo.publish_request_template(
            template_code=template_key,
            public_title="Standalone snapshot",
            ticket_type="incident",
            form_schema_id=schema_id,
            actor_id="admin1",
            actor_role="admin",
            requested_version="3.1.0",
        )
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Standalone request",
            "description": "Created from standalone registry",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "request_template_key": template_key,
            "form_payload": {
                "impact_scope": "department",
                "work_continuity": "blocked",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    request_form = ticket.custom_fields["request_form"]
    request_template = ticket.custom_fields["request_template"]
    assert request_form["source"] == "standalone_registry"
    assert request_form["pack_key"] == "request_forms"
    assert request_form["form_key"] == template_key
    assert ticket.custom_fields["resolved_template_key"] == template_key
    assert ticket.custom_fields["resolved_template_version"] == "3.1.0"
    assert ticket.custom_fields["resolved_form_schema_id"] == schema_id
    assert ticket.custom_fields["resolved_form_schema_version"] == "2.4.0"
    assert request_template["version"] == "3.1.0"
    assert request_template["form_schema_id"] == schema_id
    assert request_template["form_schema_version"] == "2.4.0"
    assert request_template["computed"]["priority"] == "P1"


def test_validate_form_submission_applies_visible_when_in():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "title": "Каталог заявок",
            "forms": [
                {
                    "key": "hardware",
                    "request_kind": "hardware",
                    "title": "Оборудование",
                    "fields": [
                        {
                            "key": "asset_type",
                            "label": "Тип актива",
                            "type": "select",
                            "required": True,
                            "options": [
                                {"value": "printer", "label": "Принтер"},
                                {"value": "scanner", "label": "Сканер"},
                                {"value": "pc", "label": "ПК"},
                            ],
                        },
                        {
                            "key": "inventory_number",
                            "label": "Инвентарный номер",
                            "type": "text",
                            "required": False,
                            "visible_when": {"field": "asset_type", "in": ["printer", "scanner"]},
                        },
                    ],
                }
            ],
        },
        require_version=False,
    )

    visible = validate_form_submission(
        pack,
        form_key="hardware",
        raw_values={
            "asset_type": "scanner",
            "inventory_number": "INV-17",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )
    hidden = validate_form_submission(
        pack,
        form_key="hardware",
        raw_values={
            "asset_type": "pc",
            "inventory_number": "INV-88",
            "impact_scope": "single_user",
            "work_continuity": "workaround_available",
            "business_importance": "normal",
        },
    )

    assert visible["submitted_values"]["inventory_number"] == "INV-17"
    assert ["asset_type", "inventory_number"] == [item["key"] for item in visible["summary_rows"][:2]]
    assert "impact_scope" in [item["key"] for item in visible["summary_rows"]]
    assert "inventory_number" not in hidden["submitted_values"]
    assert [item["key"] for item in hidden["summary_rows"][:1]] == ["asset_type"]
    assert "impact_scope" in [item["key"] for item in hidden["summary_rows"]]


def test_form_pack_schema_preserves_validation_and_process_mapping_alias():
    pack = validate_form_pack_schema(
        {
            "pack_key": "request_forms",
            "version": "1.0.1",
            "forms": [
                {
                    "key": "website",
                    "title": "Website",
                    "field_roles": {"url": ["routing_field"]},
                    "fields": [
                        {
                            "key": "url",
                            "label": "URL",
                            "type": "url",
                            "required": True,
                            "validation": {"required_message": "Provide URL"},
                            "process_mapping": {
                                "roles": ["diagnostic_input"],
                                "diagnostic_param": "target_url",
                            },
                        }
                    ],
                }
            ],
        }
    )

    form = pack["forms"][0]
    field = form["fields"][0]
    assert form["field_roles"]["url"] == ["routing_field", "diagnostic_input"]
    assert field["validation"]["required_message"] == "Provide URL"
    assert field["process_mapping"] == {
        "roles": ["routing_field", "diagnostic_input"],
        "diagnostic_param": "target_url",
    }

    with pytest.raises(ValueError) as exc:
        validate_form_submission(pack, form_key="website", raw_values={"url": ""})

    assert exc.value.args[0]["url"] == "Provide URL"
