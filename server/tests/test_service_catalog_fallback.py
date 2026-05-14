from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, TicketQueue
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver


FORBIDDEN_SAFE_KEYS = {
    "queue_id",
    "default_queue_id",
    "owner_queue_id",
    "assignee_id",
    "policy_refs",
    "raw_policy_json",
    "approval_policy",
    "approver_id",
    "approver_ids",
    "registry_service_id",
    "device_id",
    "requester_id",
    "custom_fields",
    "trace_id",
    "operation_id",
}


def _collect_forbidden_keys(payload):
    found: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_SAFE_KEYS:
                    found.add(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found


@pytest.mark.asyncio
async def test_current_catalog_includes_safe_fallback_even_when_empty(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()

    assert catalog["fallback"]["service_code"] == "other"
    assert catalog["fallback"]["offering_code"] == "unknown"
    assert catalog["fallback"]["full_code"] == "other.unknown"
    assert any(service["service_code"] == "other" for service in catalog["services"])
    assert not _collect_forbidden_keys(catalog)


@pytest.mark.asyncio
async def test_fallback_seeded_catalog_resolves_as_normal_user_selection(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    template_code = f"general_request_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"triage_{suffix}", name="Internal Triage", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="General request",
                ticket_type="service_request",
                config_json={"default_queue_id": queue.id, "no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        repo = ServiceCatalogRepo(session)
        await repo.upsert_service_draft(
            {
                "code": "other",
                "public_title": "Другое / Не знаю",
                "short_description": "Если вы не знаете, к какой услуге отнести обращение",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
                "business_criticality": "medium",
                "reporting_category": "uncategorized",
            },
            actor_id="test",
            actor_role="admin",
        )
        offering = await repo.upsert_offering_draft(
            {
                "service_code": "other",
                "code": "unknown",
                "public_title": "Не знаю, куда отнести обращение",
                "short_description": "Поддержка уточнит категорию после получения обращения",
                "request_type": "service_request",
                "request_template_key": template_code,
                "visibility": "public",
                "reporting_category": "uncategorized",
            },
            actor_id="test",
            actor_role="admin",
        )
        await repo.publish_service("other", actor_id="test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="test", actor_role="admin")
        await session.commit()

    async with session_maker() as session:
        selection = await ServiceCatalogRuntimeResolver(session).resolve_selection(
            service_code="other",
            offering_code="unknown",
            actor_role="requester",
            require_catalog=True,
        )
        catalog = await ServiceCatalogRuntimeResolver(session).current_catalog_for_requester()

    assert selection.request_template_key == template_code
    assert selection.selected_by == "requester"
    assert catalog["fallback"]["request_template_key"] == template_code


@pytest.mark.asyncio
async def test_invalid_explicit_catalog_selection_does_not_silently_fallback(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async with session_maker() as session:
        with pytest.raises(ServiceCatalogResolutionError) as exc_info:
            await ServiceCatalogRuntimeResolver(session).resolve_selection(
                service_code="missing",
                offering_code="unknown",
                actor_role="requester",
                require_catalog=True,
            )

    assert exc_info.value.details == {"offering_code": "offering not found"}
