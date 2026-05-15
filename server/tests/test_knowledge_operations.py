from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeItem, Ticket
from app.repos.knowledge_repo import KnowledgeRepo
from app.repos.service_catalog_repo import ServiceCatalogRepo
from knowledge.contracts import KnowledgePublicationBlockedError
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.operations_service import KnowledgeOperationsService
from knowledge.suggestion_service import KnowledgeSuggestionService


async def _published_item(session, *, slug: str = "vpn-reconnect-basic", visibility: str = "requester") -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": "it-self-service", "title": "IT Self-Service", "visibility": visibility, "lifecycle_status": "active"},
        actor_id="admin-test",
    )
    item = await repo.create_item_draft(
        {
            "space_code": "it-self-service",
            "slug": slug,
            "item_type": "article",
            "title": "VPN reconnect",
            "summary": "Requester-safe VPN steps",
            "visibility": visibility,
            "owner_actor_id": "servicedesk",
            "reviewer_actor_id": "servicedesk",
        },
        actor_id="admin-test",
        actor_role="admin",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": "VPN reconnect", "body_format": "markdown", "body": "## Steps\nReconnect VPN."},
        actor_id="admin-test",
        actor_role="admin",
    )
    await repo.add_binding(
        item["item_id"],
        {"service_code": "network", "offering_code": "network.vpn_issue"},
        actor_id="admin-test",
        actor_role="admin",
    )
    return await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test", actor_role="admin")


@pytest.mark.asyncio
async def test_safe_publication_lint_blocks_requester_content_with_internal_markers(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space(
            {"code": "unsafe", "title": "Unsafe", "visibility": "requester", "lifecycle_status": "active"},
            actor_id="admin-test",
        )
        item = await repo.create_item_draft(
            {
                "space_code": "unsafe",
                "slug": "unsafe-requester-runbook",
                "item_type": "article",
                "title": "Requester article",
                "visibility": "requester",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="admin-test",
            actor_role="admin",
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": "Requester article",
                "body_format": "markdown",
                "body": "Ask L2 to run internal command and inspect queue_id=42 on device_id=abc.",
            },
            actor_id="admin-test",
            actor_role="admin",
        )

        with pytest.raises(KnowledgePublicationBlockedError) as exc:
            await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin-test", actor_role="admin")

    assert {blocker["code"] for blocker in exc.value.blockers} >= {"unsafe_requester_content"}


@pytest.mark.asyncio
async def test_review_queue_quality_score_and_review_action(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _published_item(session)
        row = (await session.execute(select(KnowledgeItem).where(KnowledgeItem.item_id == item["item_id"]))).scalar_one()
        row.review_due_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.flush()

        ops = KnowledgeOperationsService(session)
        review_queue = await ops.review_queue(actor_role="admin")
        quality = await ops.quality_summary(actor_role="admin")
        action = await ops.review_action(item["item_id"], action="mark_needs_review", actor_id="curator", note="VPN procedure changed")
        await session.commit()

    assert any(entry["item_id"] == item["item_id"] and entry["reason"] == "review_overdue" for entry in review_queue["items"])
    scored = next(entry for entry in quality["items"] if entry["item_id"] == item["item_id"])
    assert 0 <= scored["quality_score"] <= 100
    assert "review_overdue" in scored["issues"]
    assert action["item"]["status"] == "needs_review"


@pytest.mark.asyncio
async def test_gap_detection_uses_catalog_ticket_and_feedback_metrics(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        catalog = ServiceCatalogRepo(session)
        await catalog.upsert_service_draft(
            {"code": "network", "name": "Network", "public_title": "Network", "visibility": "public"},
            actor_id="admin-test",
            actor_role="admin",
        )
        await catalog.publish_service("network", actor_id="admin-test", actor_role="admin")
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
            actor_id="admin-test",
            actor_role="admin",
        )
        await catalog.publish_offering("network.vpn_issue", actor_id="admin-test", actor_role="admin")
        session.add(
            Ticket(
                ticket_id="ticket-gap-vpn",
                device_id="device-gap-vpn",
                title="VPN still fails",
                description="VPN failed after reading KB",
                status="new",
                requester_id="requester-gap",
                service_code="network",
                offering_code="network.vpn_issue",
                request_type="incident",
            )
        )
        await KnowledgeFeedbackService(session).record_event(
            {
                "event_type": "ticket_created_after_view",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "surface": "requester_portal",
            },
            actor_role="requester",
            actor_id="requester-gap",
        )
        gaps = await KnowledgeOperationsService(session).detect_gaps(actor_role="admin")
        await session.commit()

    gap = next(entry for entry in gaps["gaps"] if entry["offering_code"] == "network.vpn_issue")
    assert gap["gap_type"] == "missing_requester_safe_knowledge"
    assert gap["ticket_count"] == 1
    assert gap["ticket_created_after_view_count"] == 1


@pytest.mark.asyncio
async def test_rollout_policy_gates_requester_agent_suggestions_but_not_support(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session)
        ops = KnowledgeOperationsService(session)
        await ops.upsert_rollout_policy(
            {
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "surface": "requester_portal",
                "enabled": False,
                "reason": "pilot disabled",
            },
            actor_id="admin-test",
        )
        requester_result = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "surface": "requester_portal"},
            actor_role="requester",
        )
        support_result = await KnowledgeSuggestionService(session).suggest(
            {"service_code": "network", "offering_code": "network.vpn_issue", "surface": "support_workspace"},
            actor_role="support",
        )
        await session.commit()

    assert requester_result["suggestions"] == []
    assert requester_result["rollout"]["enabled"] is False
    assert support_result["suggestions"]
