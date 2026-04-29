from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    ServerConfig,
    Ticket,
    TicketCategory,
    TicketFormPack,
    TicketQueue,
    TicketSlaPolicy,
    TicketSlaTarget,
)
from app.repos.ticket_form_packs_repo import TICKET_FORM_PREFERRED_KEY_PREFIX


def _admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-ui-admin-token"}


async def _clear_request_form_packs(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await session.execute(TicketFormPack.__table__.delete().where(TicketFormPack.pack_key == "request_forms"))
        await session.execute(
            ServerConfig.__table__.delete().where(
                ServerConfig.key == f"{TICKET_FORM_PREFERRED_KEY_PREFIX}request_forms"
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_request_template_to_observer_trace_detail_route(test_client, test_engine):
    await _clear_request_form_packs(test_engine)
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        category = TicketCategory(code=f"network_{uuid.uuid4().hex[:6]}", name="Network", level=1)
        subcategory = TicketCategory(code=f"web_{uuid.uuid4().hex[:6]}", name="Website unavailable", level=2)
        queue = TicketQueue(code=f"observer_l1_{uuid.uuid4().hex[:6]}", name="Observer ServiceDesk L1", is_active=True)
        policy = TicketSlaPolicy(name=f"Observer SLA {uuid.uuid4().hex[:6]}", is_default=False, is_active=True)
        session.add_all([category, subcategory, queue, policy])
        await session.flush()
        subcategory.parent_id = category.id
        session.add_all(
            [
                TicketSlaTarget(policy_id=policy.id, priority="P0", first_response_min=5, resolution_min=60),
                TicketSlaTarget(policy_id=policy.id, priority="P1", first_response_min=15, resolution_min=240),
                TicketSlaTarget(policy_id=policy.id, priority="P2", first_response_min=120, resolution_min=1440),
                TicketSlaTarget(policy_id=policy.id, priority="P3", first_response_min=480, resolution_min=2400),
            ]
        )
        await session.commit()
        queue_id = queue.id
        policy_id = policy.id
        category_id = category.id
        subcategory_id = subcategory.id

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
                        "subcategory_id": subcategory_id,
                        "default_queue_id": queue_id,
                        "sla_policy_id": policy_id,
                        "suggested_playbook_id": "diagnose.website",
                        "priority_policy": {
                            "impact_field": "impact_scope",
                            "urgency_field": "work_continuity",
                            "importance_field": "business_importance",
                            "modifier_fields": {"critical_service": "critical_service"},
                        },
                        "fields": [
                            {"key": "url", "label": "URL", "type": "text", "required": True},
                            {"key": "impact_scope", "label": "Кого затронуло", "type": "text", "required": True},
                            {"key": "work_continuity", "label": "Можно ли работать", "type": "text", "required": True},
                            {"key": "business_importance", "label": "Важность", "type": "text", "required": False},
                            {"key": "critical_service", "label": "Критичная система", "type": "checkbox", "required": False},
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
            "title": "Reporting site unavailable",
            "description": "Cannot open the required reporting site",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "website_unavailable",
            "form_pack_key": "request_forms",
            "form_payload": {
                "url": "https://reports.example.local",
                "impact_scope": "department",
                "work_continuity": "work_stopped_no_workaround",
                "business_importance": "deadline_today",
                "critical_service": True,
            },
            "urgency": False,
            "importance": False,
        },
        headers={"Authorization": "Bearer test-ui-user:alice"},
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()
        assert ticket.ticket_type == "incident"
        assert ticket.category_id == category_id
        assert ticket.subcategory_id == subcategory_id
        assert ticket.queue_id == queue_id
        assert ticket.sla_policy_id == policy_id
        assert ticket.custom_fields["request_template"]["key"] == "website_unavailable"
        assert ticket.custom_fields["priority_decision"]["effective_priority"] == "P0"
        assert ticket.observer_root_trace_id
        root_trace_id = ticket.observer_root_trace_id

    summary_response = await test_client.get(
        f"/api/tickets/{ticket_id}/observer",
        headers=_admin_headers(),
    )
    assert summary_response.status == 200, await summary_response.text()
    summary_payload = await summary_response.json()
    assert summary_payload["summary"]["ticket_id"] == ticket_id
    assert summary_payload["summary"]["root_trace_id"] == root_trace_id
    assert summary_payload["root_trace"]["root_kind"] == "ticket"

    traces_response = await test_client.get(
        f"/api/web/admin/observer/traces?root_kind=ticket&ticket_id={ticket_id}&limit=5",
        headers=_admin_headers(),
    )
    assert traces_response.status == 200, await traces_response.text()
    traces_payload = await traces_response.json()
    traces = traces_payload["data"]["traces"]
    assert any(item["trace_id"] == root_trace_id for item in traces)

    detail_response = await test_client.get(
        f"/api/web/admin/observer/traces/{root_trace_id}",
        headers=_admin_headers(),
    )
    assert detail_response.status == 200, await detail_response.text()
    detail_payload = await detail_response.json()
    assert detail_payload["data"]["trace"]["trace_id"] == root_trace_id
    assert detail_payload["data"]["trace"]["ticket_id"] == ticket_id
    assert any(span["name"].startswith("ticket.") for span in detail_payload["data"]["spans"])
