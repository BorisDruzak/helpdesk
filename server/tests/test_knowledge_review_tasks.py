from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeIngestionJob, KnowledgeReviewTask
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.review_task_service import KnowledgeReviewTaskService


pytestmark = pytest.mark.db_cleanup("knowledge")

async def _draft_item(session, *, slug: str, status: str = "draft", source_kind: str = "manual", visibility: str = "support_internal") -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space({"code": "ops", "title": "Ops", "visibility": visibility, "lifecycle_status": "active"}, actor_id="admin")
    item = await repo.create_item_draft(
        {
            "space_code": "ops",
            "slug": slug,
            "item_type": "article",
            "title": slug,
            "summary": "Review candidate",
            "visibility": visibility,
            "owner_actor_id": "servicedesk",
            "reviewer_actor_id": "servicedesk",
            "source_kind": source_kind,
        },
        actor_id="admin",
        actor_role="admin",
    )
    row = await repo.get_item_row(item["item_id"])
    row.status = status
    return item


@pytest.mark.asyncio
async def test_passport_ingestion_stale_and_negative_feedback_generate_review_tasks(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        passport = await _draft_item(session, slug="passport-draft", source_kind="ticket_passport")
        stale = await _draft_item(session, slug="stale-article", status="published", visibility="requester")
        repo = KnowledgeRepo(session)
        stale_row = await repo.get_item_row(stale["item_id"])
        stale_row.review_due_at = datetime.now(timezone.utc) - timedelta(days=1)
        await repo.create_version(stale["item_id"], {"title": "stale", "summary": "safe", "body": "safe body"}, actor_id="admin", actor_role="admin")
        await KnowledgeFeedbackService(session).record_event({"item_id": stale["item_id"], "event_type": "not_helpful"}, actor_role="requester", actor_id="requester")
        space = await repo.get_space_by_code("ops")
        session.add(
            KnowledgeIngestionJob(
                job_id="ingestion-review-job",
                space_id=space.space_id,
                source_kind="text",
                source_name="ingested draft",
                status="review_required",
                created_item_id=passport["item_id"],
            )
        )

        generated = await KnowledgeReviewTaskService(session).generate_tasks(actor_id="ops-bot")
        await session.commit()

    task_types = {task["task_type"] for task in generated["tasks"]}
    assert {"passport_draft", "ingestion_review", "scheduled_review", "negative_feedback"} <= task_types


@pytest.mark.asyncio
async def test_review_task_actions_and_support_visibility(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item = await _draft_item(session, slug="support-runbook", visibility="support_internal")
        service = KnowledgeReviewTaskService(session)
        task = await service.create_task(
            item_id=item["item_id"],
            task_type="draft_review",
            severity="warning",
            reason="Draft needs curation.",
            suggested_action="Review and approve.",
            actor_id="admin",
        )
        await service.assign_task(task["task_id"], actor_id="admin", assigned_to_actor_id="support-1")
        await service.start_task(task["task_id"], actor_id="support-1")
        completed = await service.complete_task(task["task_id"], actor_id="support-1", note="Reviewed")
        visible = await service.list_tasks(actor_role="support", actor_id="support-1")
        await session.commit()

    assert completed["task"]["status"] == "done"
    assert any(row["task_id"] == task["task_id"] for row in visible["tasks"])

    async with session_maker() as session:
        row = (await session.execute(select(KnowledgeReviewTask).where(KnowledgeReviewTask.task_id == task["task_id"]))).scalar_one()
        assert row.closed_at is not None
