import uuid
from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskPolicyAudit, PriorityPolicy, ServerConfig, SlaPolicy, Ticket, TicketFormPack, TicketSlaPolicy, TicketSlaTarget
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX
from tickets.priority_policy import compute_priority_from_facts


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_request_form_packs(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(
            TicketFormPack.__table__.delete().where(TicketFormPack.pack_key == "request_forms")
        )
        await session.execute(
            ServerConfig.__table__.delete().where(
                ServerConfig.key == f"{TICKET_FORM_PREFERRED_KEY_PREFIX}request_forms"
            )
        )
        await session.commit()


async def _clear_priority_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(HelpdeskPolicyAudit.__table__.delete())
        await session.execute(PriorityPolicy.__table__.delete())
        await session.commit()


async def _clear_sla_registry(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(HelpdeskPolicyAudit.__table__.delete())
        await session.execute(SlaPolicy.__table__.delete())
        await session.commit()


def test_compute_priority_from_impact_urgency_and_modifiers():
    result = compute_priority_from_facts(
        impact="department",
        urgency="work_stopped_no_workaround",
        importance="normal",
        modifiers={"critical_service": True, "security": True},
    )

    assert result["computed_priority"] == "P1"
    assert result["effective_priority"] == "P0"
    assert result["legacy_priority"] == "P1"
    assert result["impact"] == 2
    assert result["urgency"] == 3
    assert result["importance"] == 1
    assert result["priority_source"] == "system"
    assert result["applied_modifiers"] == ["critical_service", "security"]
    assert "security" in result["priority_reason"]


@pytest.mark.asyncio
async def test_form_priority_policy_sets_effective_priority_and_sla_target(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        policy = TicketSlaPolicy(name=f"Process SLA {uuid.uuid4().hex[:8]}", is_default=False, is_active=True)
        session.add(policy)
        await session.flush()
        session.add_all(
            [
                TicketSlaTarget(policy_id=policy.id, priority="P0", first_response_min=5, resolution_min=60),
                TicketSlaTarget(policy_id=policy.id, priority="P1", first_response_min=30, resolution_min=240),
                TicketSlaTarget(policy_id=policy.id, priority="P4", first_response_min=480, resolution_min=2400),
            ]
        )
        await session.commit()
        policy_id = policy.id

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
                        "sla_policy_id": policy_id,
                        "priority_policy": {
                            "impact_field": "affected_scope",
                            "urgency_field": "work_continuity",
                            "importance_field": "business_deadline",
                            "modifier_fields": {
                                "critical_service": "critical_service",
                                "public_service": "public_service",
                            },
                        },
                        "fields": [
                            {"key": "url", "label": "URL", "type": "text", "required": True},
                            {"key": "affected_scope", "label": "Кого затронуло", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Можно ли работать", "type": "text", "required": True},
                            {"key": "business_deadline", "label": "Важный срок", "type": "text", "required": False},
                            {"key": "critical_service", "label": "Критичная система", "type": "checkbox", "required": False},
                            {"key": "public_service", "label": "Публичная услуга", "type": "checkbox", "required": False},
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
            "title": "Reports unavailable",
            "description": "Cannot submit required report",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "website_unavailable",
            "form_pack_key": "request_forms",
            "form_payload": {
                "url": "https://reports.example.local",
                "affected_scope": "department",
                "work_continuity": "work_stopped_no_workaround",
                "business_deadline": "deadline_today",
                "critical_service": True,
                "public_service": True,
            },
            "urgency": False,
            "importance": False,
            "urgency_reason": "Legacy request body should not decide process priority",
            "importance_reason": "Legacy request body should not decide process priority",
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    priority_decision = ticket.custom_fields["priority_decision"]
    assert priority_decision["computed_priority"] == "P1"
    assert priority_decision["effective_priority"] == "P0"
    assert priority_decision["priority_source"] == "system"
    assert ticket.custom_fields["priority_class"] == "P0"
    assert ticket.priority == "P1"
    assert ticket.impact == 2
    assert ticket.urgency == 3
    assert ticket.importance == 3
    assert ticket.sla_policy_id == policy_id
    assert ticket.resolution_due_at is not None
    assert ticket.first_response_due_at is not None
    resolution_delta = ticket.resolution_due_at.astimezone(timezone.utc) - ticket.created_at.astimezone(timezone.utc)
    assert 0 < resolution_delta.total_seconds() <= 70 * 60


@pytest.mark.asyncio
async def test_ticket_creation_overlays_priority_policy_from_standalone_registry(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _clear_priority_registry(test_engine)
    form_key = f"registry_priority_{uuid.uuid4().hex[:8]}"

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
                        "title": "Registry priority",
                        "priority_policy": {
                            "impact_field": "affected_scope",
                            "urgency_field": "work_continuity",
                            "importance_field": "business_deadline",
                        },
                        "fields": [
                            {"key": "affected_scope", "label": "Scope", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Continuity", "type": "text", "required": True},
                            {"key": "business_deadline", "label": "Deadline", "type": "text", "required": False},
                            {"key": "critical_service", "label": "Critical", "type": "checkbox", "required": False},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    policy_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "priority",
            "code": f"{form_key}_priority_policy",
            "title": "Registry priority policy",
            "scope_level": "request_template",
            "scope_ref": form_key,
            "config": {"modifier_fields": {"critical_service": "critical_service"}},
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert policy_response.status == 200, await policy_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Low impact but critical service",
            "description": "Registry modifier should raise priority",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {
                "affected_scope": "only_me",
                "work_continuity": "workaround_available",
                "business_deadline": "normal",
                "critical_service": True,
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.custom_fields["priority_decision"]["computed_priority"] == "P3"
    assert ticket.custom_fields["priority_decision"]["effective_priority"] == "P2"
    assert ticket.custom_fields["request_template"]["effective_policy_sources"]["priority"][0]["scope_level"] == "request_template"


@pytest.mark.asyncio
async def test_ticket_creation_uses_standalone_registry_sla_targets(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    await _clear_sla_registry(test_engine)
    form_key = f"registry_sla_{uuid.uuid4().hex[:8]}"

    save_response = await test_client.post(
        "/api/ticket_forms/packs/save",
        json={
            "pack": {
                "pack_key": "request_forms",
                "title": "РљР°С‚Р°Р»РѕРі Р·Р°СЏРІРѕРє",
                "forms": [
                    {
                        "key": form_key,
                        "request_kind": form_key,
                        "ticket_type": "incident",
                        "title": "Registry SLA",
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                            {"key": "impact_scope", "label": "Scope", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Continuity", "type": "text", "required": True},
                        ],
                    }
                ],
            }
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert save_response.status == 200, await save_response.text()

    policy_response = await test_client.post(
        "/api/web/admin/helpdesk-model/policies/publish",
        json={
            "kind": "sla",
            "code": f"{form_key}_sla_policy",
            "title": "Registry SLA policy",
            "scope_level": "request_template",
            "scope_ref": form_key,
            "config": {
                "targets": {
                    "first_response": {"P3": "45m"},
                    "resolution": {"P3": "2h"},
                }
            },
        },
        headers={**_admin_headers(), "Content-Type": "application/json"},
    )
    assert policy_response.status == 200, await policy_response.text()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Standalone SLA target",
            "description": "Registry SLA should set due dates",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": form_key,
            "form_pack_key": "request_forms",
            "form_payload": {
                "summary": "Need help",
                "impact_scope": "only_me",
                "work_continuity": "workaround_available",
            },
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    assert ticket.sla_policy_id is None
    assert ticket.first_response_due_at is not None
    assert ticket.resolution_due_at is not None
    first_response_delta = ticket.first_response_due_at.astimezone(timezone.utc) - ticket.created_at.astimezone(timezone.utc)
    resolution_delta = ticket.resolution_due_at.astimezone(timezone.utc) - ticket.created_at.astimezone(timezone.utc)
    assert 0 < first_response_delta.total_seconds() <= 50 * 60
    assert 0 < resolution_delta.total_seconds() <= 125 * 60
    assert ticket.custom_fields["request_template"]["effective_policy_sources"]["sla"][0]["scope_level"] == "request_template"
