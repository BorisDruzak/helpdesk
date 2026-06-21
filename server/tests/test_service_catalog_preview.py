from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, Ticket, TicketEvent, TicketQueue
from app.repos.service_catalog_repo import ServiceCatalogRepo
from app.repos.ticket_form_packs_repo import TicketFormPacksRepo


pytestmark = pytest.mark.db_cleanup("tickets")

FORBIDDEN_PREVIEW_KEYS = {
    "queue_id",
    "target_queue_id",
    "assignee_id",
    "policy_refs",
    "raw_policy_json",
    "approval_policy",
    "approver_id",
    "approver_ids",
    "approver_actor_id",
    "registry_service_id",
    "device_id",
    "requester_id",
    "custom_fields",
    "trace_id",
    "operation_id",
    "internal_rule_id",
    "route_rule_id",
    "calendar_id",
}


def _collect_forbidden_keys(payload):
    found: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_PREVIEW_KEYS:
                    found.add(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found


@pytest.mark.asyncio
async def test_requester_service_catalog_preview_is_safe_and_dry_run(test_client, test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    template_code = f"laptop_incident_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Sensitive Internal Workplace", is_active=True)
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
                        "fields": [
                            {"key": "summary", "label": "Summary", "type": "text", "required": True},
                        ],
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
            actor_id="test",
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
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="test", actor_role="admin")
        await session.commit()
        tickets_before = await session.scalar(select(func.count()).select_from(Ticket))
        events_before = await session.scalar(select(func.count()).select_from(TicketEvent))

    response = await test_client.post(
        "/api/service-catalog/preview",
        json={
            "service_code": service_code,
            "offering_code": "laptop_broken",
            "request_template_key": template_code,
            "form_payload": {"summary": "No boot"},
            "description": "No boot",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["ok"] is True
    assert payload["service"]["code"] == service_code
    assert payload["offering"]["full_code"] == f"{service_code}.laptop_broken"
    assert payload["public_status_after_create"]
    assert payload["approval"]["required"] is False
    assert payload["diagnostics"]["consent_required"] is False
    assert "Sensitive Internal Workplace" not in str(payload)
    assert not _collect_forbidden_keys(payload)

    async with session_maker() as session:
        tickets_after = await session.scalar(select(func.count()).select_from(Ticket))
        events_after = await session.scalar(select(func.count()).select_from(TicketEvent))
    assert tickets_after == tickets_before
    assert events_after == events_before


@pytest.mark.asyncio
async def test_requester_service_catalog_preview_returns_safe_validation_error(test_client) -> None:
    response = await test_client.post(
        "/api/service-catalog/preview",
        json={"service_code": "missing", "offering_code": "unknown", "form_payload": {}},
    )

    assert response.status == 400
    payload = await response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "validation_error"
    assert not _collect_forbidden_keys(payload)
