from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ContinuousImprovementAction, KnowledgeFeedbackEvent, Ticket
from quality.feedback_service import TicketFeedbackService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_knowledge_article_failed_feedback_creates_kb_improvement_action(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-quality-knowledge",
                title="Mail issue",
                description="Mail does not sync",
                status="resolved",
                requester_id="alice",
                service_code="mail",
                offering_code="mail.mailbox_issue",
                resolved_at=datetime.now(timezone.utc),
                custom_fields={"knowledge_attempts": [{"item_id": "ki-1", "result": "not_helpful"}]},
            )
        )
        await session.flush()
        session.add(
            KnowledgeFeedbackEvent(
                event_id=str(uuid.uuid4()),
                item_id=None,
                version_id=None,
                ticket_id=ticket_id,
                event_type="not_helpful",
                source_surface="requester_portal",
                actor_role="requester",
                service_code="mail",
                offering_code="mail.mailbox_issue",
                created_at=datetime.now(timezone.utc),
            )
        )
        result = await TicketFeedbackService(session).submit_feedback(
            {
                "ticket_id": ticket_id,
                "rating": 2,
                "problem_resolved": False,
                "reason_codes": ["knowledge_article_failed"],
                "source_surface": "requester_portal",
                "metadata": {"knowledge_item_id": "ki-1"},
            },
            actor_id="alice",
            actor_role="requester",
        )
        await session.commit()

        action = await session.get(ContinuousImprovementAction, result["improvement_action_id"])

    assert action is not None
    assert action.action_type in {"update_kb_article", "create_kb_article"}
    assert action.service_code == "mail"
