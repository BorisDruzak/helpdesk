from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import RequestTemplate, TicketQueue
from app.repos.knowledge_repo import KnowledgeRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo
from tickets.policy_health_service import PolicyHealthService


pytestmark = pytest.mark.db_cleanup("policies_config")

@pytest.mark.asyncio
async def test_policy_health_includes_service_catalog_objects(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"workplace_{suffix}"
    template_code = f"template_{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Workplace", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="Laptop incident",
                ticket_type="incident",
                config_json={"no_sla": True},
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
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await repo.publish_service(service_code, actor_id="admin-test", actor_role="admin")
        await repo.publish_offering(offering["full_code"], actor_id="admin-test", actor_role="admin")
        dashboard = await PolicyHealthService(session).list_health()

    service_item = next(item for item in dashboard["services"] if item["object_code"] == service_code)
    offering_item = next(item for item in dashboard["offerings"] if item["object_code"] == f"{service_code}.laptop_broken")
    assert service_item["health_status"] in {"ok", "warning"}
    assert offering_item["template_code"] == template_code
    assert offering_item["knowledge_count"] == 0
    assert ("knowledge", "missing_policy") in {
        (issue["policy_kind"], issue["kind"]) for issue in offering_item["issues"]
    }
    assert dashboard["summary"]["services"] >= 1
    assert dashboard["summary"]["offerings"] >= 1


@pytest.mark.asyncio
async def test_policy_health_counts_requester_safe_catalog_knowledge(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    service_code = f"network_{suffix}"
    template_code = f"vpn_{suffix}"
    full_code = f"{service_code}.vpn_issue"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        queue = TicketQueue(code=f"queue_{suffix}", name="Network", is_active=True)
        session.add(queue)
        await session.flush()
        session.add(
            RequestTemplate(
                template_code=template_code,
                version="1",
                public_title="VPN issue",
                ticket_type="incident",
                config_json={"no_sla": True},
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        catalog_repo = ServiceCatalogRepo(session)
        await catalog_repo.upsert_service_draft(
            {
                "code": service_code,
                "public_title": "Network",
                "short_description": "VPN and connectivity",
                "visibility": "public",
                "owner_queue_id": queue.id,
                "default_queue_id": queue.id,
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await catalog_repo.upsert_offering_draft(
            {
                "service_code": service_code,
                "code": "vpn_issue",
                "public_title": "VPN issue",
                "short_description": "VPN does not connect",
                "request_type": "incident",
                "request_template_key": template_code,
                "visibility": "public",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        await catalog_repo.publish_service(service_code, actor_id="admin-test", actor_role="admin")
        await catalog_repo.publish_offering(full_code, actor_id="admin-test", actor_role="admin")

        knowledge_repo = KnowledgeRepo(session)
        await knowledge_repo.upsert_space(
            {
                "code": f"self_service_{suffix}",
                "title": "Self Service",
                "visibility": "requester",
                "lifecycle_status": "active",
            },
            actor_id="admin-test",
        )
        item = await knowledge_repo.create_item_draft(
            {
                "space_code": f"self_service_{suffix}",
                "slug": f"vpn-help-{suffix}",
                "title": "Reconnect VPN",
                "summary": "Requester-safe VPN troubleshooting",
                "visibility": "requester",
                "owner_actor_id": "owner-test",
                "reviewer_actor_id": "reviewer-test",
            },
            actor_id="admin-test",
        )
        version = await knowledge_repo.create_version(
            item["item_id"],
            {"body": "# Steps\nReconnect VPN and retry.", "body_format": "markdown"},
            actor_id="admin-test",
        )
        await knowledge_repo.add_binding(
            item["item_id"],
            {"service_code": service_code, "offering_code": full_code, "request_template_key": template_code},
            actor_id="admin-test",
        )
        await knowledge_repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test")
        dashboard = await PolicyHealthService(session).list_health()

    offering_item = next(item for item in dashboard["offerings"] if item["object_code"] == full_code)
    assert offering_item["knowledge_count"] == 1
    assert ("knowledge", "missing_policy") not in {
        (issue["policy_kind"], issue["kind"]) for issue in offering_item["issues"]
    }
