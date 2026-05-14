from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, Ticket, TicketQueue
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo


@pytest.mark.asyncio
async def test_ticket_create_with_service_catalog_stores_explicit_fields_and_snapshot(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    template_code = f"laptop_incident_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Workplace", is_active=True)
        session.add(queue)
        await session.flush()
        forms_repo = TicketFormPacksRepo(session)
        await forms_repo.upsert_pack(
            pack_key="request_forms",
            version=f"test-{suffix}",
            schema_json={
                "pack_key": "request_forms",
                "version": f"test-{suffix}",
                "forms": [
                    {
                        "key": template_code,
                        "request_template_key": template_code,
                        "title": "Laptop incident",
                        "request_kind": "incident",
                        "ticket_type": "incident",
                        "fields": [{"key": "summary", "label": "Summary", "type": "text", "required": False}],
                    }
                ],
            },
            created_by="test",
        )
        await forms_repo.set_preferred(pack_key="request_forms", version=f"test-{suffix}", updated_by="test")
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop incident",
                ticket_type="incident",
                config_json={"default_queue_id": queue.id, "no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Рабочее место",
                "short_description": "Ноутбук и периферия",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "business_criticality": "medium",
                "reporting_category": "end_user_computing",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "laptop_broken",
                "public_title": "Сломался ноутбук",
                "short_description": "Ноутбук не включается",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "workplace_incidents",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="admin-test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="admin-test", actor_role="admin")
        await session.commit()

    resp = await test_client.post(
        "/api/tickets/create",
        headers={"Authorization": "Bearer test-ui-admin-token"},
        json={
            "title": "Сломался ноутбук",
            "description": "Ноутбук не включается",
            "device_id": "device-service-catalog",
            "service_code": service_code,
            "offering_code": "laptop_broken",
            "request_template_key": template_code,
            "form_payload": {"summary": "no boot"},
            "ticket_type": "incident",
            "requester_profile": {"full_name": "Requester"},
        },
    )
    assert resp.status == 200, await resp.text()
    payload = await resp.json()
    ticket_id = payload["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.scalar(select(Ticket).where(Ticket.ticket_id == ticket_id))

    assert ticket is not None
    assert ticket.service_code == service_code
    assert ticket.offering_code == f"{service_code}.laptop_broken"
    assert ticket.request_type == "incident"
    assert ticket.reporting_category == "workplace_incidents"
    snapshot = (ticket.custom_fields or {}).get("service_catalog")
    assert snapshot["service_code"] == service_code
    assert snapshot["offering_full_code"] == f"{service_code}.laptop_broken"
