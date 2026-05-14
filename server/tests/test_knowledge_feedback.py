from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.attempts import attach_knowledge_attempts, sanitize_knowledge_attempts


@pytest.mark.asyncio
async def test_knowledge_feedback_records_deflection_without_ticket(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": "it", "title": "IT", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
        item = await repo.create_item_draft(
            {
                "space_code": "it",
                "slug": "vpn-fix",
                "item_type": "article",
                "title": "VPN fix",
                "visibility": "requester",
                "owner_actor_id": "owner",
                "reviewer_actor_id": "reviewer",
            },
            actor_id="support",
        )
        version = await repo.create_version(item["item_id"], {"title": "VPN fix", "body": "Fix VPN", "body_format": "markdown"}, actor_id="support")
        await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin")
        event = await KnowledgeFeedbackService(session).record_event(
            {
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "event_type": "deflected",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "surface": "requester_portal",
                "session_id": "safe-session",
            },
            actor_role="requester",
            actor_id=None,
        )
        await session.commit()

    assert event["event_type"] == "deflected"
    assert event["ticket_id"] is None
    assert event["source_surface"] == "requester_portal"


def test_knowledge_attempts_are_sanitized_for_ticket_custom_fields() -> None:
    attempts = sanitize_knowledge_attempts(
        [
            {
                "item_id": "item-1",
                "version_id": "version-1",
                "result": "not_helpful",
                "device_id": "secret-device",
                "requester_id": "secret-user",
                "custom_fields": {"raw": True},
            },
            {"item_id": "", "result": "viewed"},
            {"item_id": "item-2", "result": "unsupported"},
        ],
        surface="requester_portal",
    )

    assert attempts == [
        {
            "item_id": "item-1",
            "version_id": "version-1",
            "result": "not_helpful",
            "surface": "requester_portal",
            "occurred_at": attempts[0]["occurred_at"],
        },
        {
            "item_id": "item-2",
            "version_id": None,
            "result": "viewed",
            "surface": "requester_portal",
            "occurred_at": attempts[1]["occurred_at"],
        },
    ]
    stored = attach_knowledge_attempts({}, attempts)
    assert stored["knowledge_attempts"] == attempts
    assert "device_id" not in str(stored)
    assert "requester_id" not in str(stored)


@pytest.mark.asyncio
async def test_not_helpful_then_ticket_create_attempt_is_recorded(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = KnowledgeFeedbackService(session)
        event = await service.record_event(
            {
                "item_id": None,
                "version_id": None,
                "event_type": "ticket_created_after_view",
                "ticket_id": "ticket-knowledge-test",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "surface": "requester_portal",
                "metadata": {"knowledge_attempts": [{"item_id": "item-1", "result": "not_helpful"}]},
            },
            actor_role="requester",
            actor_id="requester-test",
        )
        await session.commit()

    assert event["event_type"] == "ticket_created_after_view"
    assert event["metadata"]["knowledge_attempts"][0]["result"] == "not_helpful"
