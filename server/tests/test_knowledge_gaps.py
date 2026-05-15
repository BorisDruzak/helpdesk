from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket
from app.repos.service_catalog_repo import ServiceCatalogRepo
from knowledge.gap_service import KnowledgeGapService


async def _catalog_offering(session) -> None:
    catalog = ServiceCatalogRepo(session)
    await catalog.upsert_service_draft({"code": "network", "name": "Network", "public_title": "Network", "visibility": "public"}, actor_id="admin", actor_role="admin")
    await catalog.publish_service("network", actor_id="admin", actor_role="admin")
    await catalog.upsert_offering_draft(
        {
            "service_code": "network",
            "code": "vpn_issue",
            "name": "VPN issue",
            "public_title": "VPN issue",
            "visibility": "public",
            "request_type": "incident",
            "request_template_key": "vpn_issue",
        },
        actor_id="admin",
        actor_role="admin",
    )
    await catalog.publish_offering("network.vpn_issue", actor_id="admin", actor_role="admin")


@pytest.mark.asyncio
async def test_gap_detection_persists_no_kb_and_high_volume_findings(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _catalog_offering(session)
        for idx in range(3):
            session.add(
                Ticket(
                    ticket_id=f"gap-ticket-{idx}",
                    device_id=f"gap-device-{idx}",
                    title="VPN fails",
                    description="VPN fails",
                    status="new",
                    requester_id=f"requester-{idx}",
                    service_code="network",
                    offering_code="network.vpn_issue",
                    request_type="incident",
                )
            )
        result = await KnowledgeGapService(session).recompute(actor_id="ops-bot")
        await session.commit()

    gap_types = {finding["gap_type"] for finding in result["findings"]}
    assert {"no_requester_article", "no_support_runbook", "high_volume_no_kb"} <= gap_types


@pytest.mark.asyncio
async def test_dismissed_gap_not_recreated_until_evidence_changes_and_create_draft(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _catalog_offering(session)
        service = KnowledgeGapService(session)
        first = await service.recompute(actor_id="ops-bot")
        target = next(row for row in first["findings"] if row["gap_type"] == "no_requester_article")
        await service.dismiss(target["finding_id"], actor_id="admin", reason="Not needed this quarter")
        second = await service.recompute(actor_id="ops-bot")
        draft = await service.create_draft(target["finding_id"], actor_id="support-1", item_type="article")
        await session.commit()

    assert all(row["finding_id"] != target["finding_id"] for row in second["findings"])
    assert draft["item"]["status"] == "draft"
    assert draft["review_task"]["task_type"] == "gap_candidate"
