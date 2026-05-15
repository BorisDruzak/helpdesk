from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeFeedbackEvent, KnowledgeIngestionJob, KnowledgeItem, KnowledgeReviewComment, KnowledgeReviewTask
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities


def _new_id() -> str:
    return str(uuid.uuid4())


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def serialize_review_task(row: KnowledgeReviewTask, *, item: KnowledgeItem | None = None) -> dict[str, Any]:
    payload = {
        "task_id": row.task_id,
        "item_id": row.item_id,
        "version_id": row.version_id,
        "task_type": row.task_type,
        "severity": row.severity,
        "status": row.status,
        "assigned_to_actor_id": row.assigned_to_actor_id,
        "owner_actor_id": row.owner_actor_id,
        "due_at": _iso(row.due_at),
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "reason": row.reason,
        "suggested_action": row.suggested_action,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "closed_at": _iso(row.closed_at),
        "metadata": row.metadata_json or {},
    }
    if item is not None:
        payload["item"] = serialize_item(item)
    return payload


class KnowledgeReviewTaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self,
        *,
        item_id: str,
        task_type: str,
        severity: str,
        reason: str,
        suggested_action: str | None,
        actor_id: str | None,
        version_id: str | None = None,
        due_at: datetime | None = None,
        source_kind: str | None = None,
        source_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        active_statuses = ("open", "assigned", "in_progress")
        row = (
            await self.session.execute(
                select(KnowledgeReviewTask).where(
                    KnowledgeReviewTask.item_id == item_id,
                    KnowledgeReviewTask.task_type == task_type,
                    KnowledgeReviewTask.source_kind.is_(None) if source_kind is None else KnowledgeReviewTask.source_kind == source_kind,
                    KnowledgeReviewTask.source_ref.is_(None) if source_ref is None else KnowledgeReviewTask.source_ref == source_ref,
                    KnowledgeReviewTask.status.in_(active_statuses),
                )
            )
        ).scalars().first()
        now = datetime.now(timezone.utc)
        if row is None:
            row = KnowledgeReviewTask(
                task_id=_new_id(),
                item_id=item_id,
                version_id=version_id,
                task_type=task_type,
                severity=severity,
                status="open",
                owner_actor_id=actor_id,
                due_at=due_at,
                source_kind=source_kind,
                source_ref=source_ref,
                reason=reason,
                suggested_action=suggested_action,
                created_at=now,
                updated_at=now,
                metadata_json=metadata or {},
            )
            self.session.add(row)
        else:
            row.severity = severity
            row.reason = reason
            row.suggested_action = suggested_action
            row.due_at = due_at or row.due_at
            row.updated_at = now
            row.metadata_json = {**(row.metadata_json or {}), **(metadata or {})}
        await self.session.flush()
        return {"task": serialize_review_task(row), **serialize_review_task(row)}

    async def list_tasks(self, *, actor_role: str, actor_id: str | None = None, status: str | None = None) -> dict[str, Any]:
        allowed = set(actor_visible_visibilities(actor_role))
        query = select(KnowledgeReviewTask, KnowledgeItem).join(KnowledgeItem, KnowledgeItem.item_id == KnowledgeReviewTask.item_id)
        query = query.where(KnowledgeItem.visibility.in_(allowed))
        if actor_role == "support" and actor_id:
            query = query.where(
                (KnowledgeReviewTask.assigned_to_actor_id.is_(None))
                | (KnowledgeReviewTask.assigned_to_actor_id == actor_id)
                | (KnowledgeReviewTask.owner_actor_id == actor_id)
            )
        if status:
            query = query.where(KnowledgeReviewTask.status == status)
        rows = (await self.session.execute(query.order_by(KnowledgeReviewTask.due_at.asc().nulls_last(), KnowledgeReviewTask.created_at.desc()))).all()
        tasks = [serialize_review_task(task, item=item) for task, item in rows]
        return {"tasks": tasks, "count": len(tasks)}

    async def assign_task(self, task_id: str, *, actor_id: str | None, assigned_to_actor_id: str | None) -> dict[str, Any]:
        return await self._transition(task_id, actor_id=actor_id, status="assigned", assigned_to_actor_id=assigned_to_actor_id, note="assigned")

    async def start_task(self, task_id: str, *, actor_id: str | None) -> dict[str, Any]:
        return await self._transition(task_id, actor_id=actor_id, status="in_progress", note="started")

    async def complete_task(self, task_id: str, *, actor_id: str | None, note: str | None = None) -> dict[str, Any]:
        return await self._transition(task_id, actor_id=actor_id, status="done", note=note or "completed", close=True)

    async def dismiss_task(self, task_id: str, *, actor_id: str | None, reason: str | None = None) -> dict[str, Any]:
        return await self._transition(task_id, actor_id=actor_id, status="dismissed", note=reason or "dismissed", close=True)

    async def _transition(
        self,
        task_id: str,
        *,
        actor_id: str | None,
        status: str,
        note: str,
        assigned_to_actor_id: str | None = None,
        close: bool = False,
    ) -> dict[str, Any]:
        row = (await self.session.execute(select(KnowledgeReviewTask).where(KnowledgeReviewTask.task_id == task_id))).scalar_one_or_none()
        if row is None:
            raise ValueError("knowledge review task not found")
        now = datetime.now(timezone.utc)
        row.status = status
        row.updated_at = now
        if assigned_to_actor_id is not None:
            row.assigned_to_actor_id = assigned_to_actor_id
        if close:
            row.closed_at = now
        self.session.add(KnowledgeReviewComment(comment_id=_new_id(), task_id=row.task_id, actor_id=actor_id, body=note, created_at=now))
        await self.session.flush()
        return {"task": serialize_review_task(row)}

    async def generate_tasks(self, *, actor_id: str | None) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        created: list[dict[str, Any]] = []

        items = (await self.session.execute(select(KnowledgeItem))).scalars().all()
        for item in items:
            if item.source_kind == "ticket_passport" and item.status in {"draft", "in_review", "needs_review"}:
                created.append(
                    await self.create_task(
                        item_id=item.item_id,
                        version_id=item.current_version_id,
                        task_type="passport_draft",
                        severity="warning",
                        reason="Passport-derived draft requires curation.",
                        suggested_action="Review source passport and approve, request changes or archive.",
                        actor_id=actor_id,
                        source_kind="ticket_passport",
                        source_ref=item.source_passport_id or item.source_ref or item.item_id,
                    )
                )
            elif item.status in {"draft", "in_review", "needs_review"}:
                created.append(
                    await self.create_task(
                        item_id=item.item_id,
                        version_id=item.current_version_id,
                        task_type="draft_review",
                        severity="info",
                        reason="Draft knowledge item requires review.",
                        suggested_action="Review and decide whether it should be published or archived.",
                        actor_id=actor_id,
                        source_kind="knowledge_item",
                        source_ref=item.item_id,
                    )
                )
            if item.review_due_at and item.review_due_at <= now:
                created.append(
                    await self.create_task(
                        item_id=item.item_id,
                        version_id=item.current_version_id,
                        task_type="scheduled_review",
                        severity="warning",
                        reason="Knowledge review due date has passed.",
                        suggested_action="Review freshness and update review_due_at.",
                        actor_id=actor_id,
                        due_at=item.review_due_at,
                        source_kind="review_due_at",
                        source_ref=item.item_id,
                    )
                )

        jobs = (
            await self.session.execute(select(KnowledgeIngestionJob).where(KnowledgeIngestionJob.status == "review_required", KnowledgeIngestionJob.created_item_id.is_not(None)))
        ).scalars().all()
        for job in jobs:
            created.append(
                await self.create_task(
                    item_id=str(job.created_item_id),
                    version_id=job.created_version_id,
                    task_type="ingestion_review",
                    severity="warning",
                    reason="Ingestion draft requires human review.",
                    suggested_action="Verify extracted content and publish only safe reviewed content.",
                    actor_id=actor_id,
                    source_kind="ingestion_job",
                    source_ref=job.job_id,
                )
            )

        negative_rows = (
            await self.session.execute(
                select(KnowledgeFeedbackEvent.item_id, func.count(KnowledgeFeedbackEvent.event_id))
                .where(KnowledgeFeedbackEvent.item_id.is_not(None), KnowledgeFeedbackEvent.event_type == "not_helpful")
                .group_by(KnowledgeFeedbackEvent.item_id)
            )
        ).all()
        for item_id, count in negative_rows:
            created.append(
                await self.create_task(
                    item_id=str(item_id),
                    task_type="negative_feedback",
                    severity="warning",
                    reason=f"Knowledge item has {int(count)} not-helpful feedback event(s).",
                    suggested_action="Review article usefulness and update or archive.",
                    actor_id=actor_id,
                    source_kind="feedback",
                    source_ref=f"not_helpful:{item_id}",
                    metadata={"not_helpful_count": int(count)},
                )
            )

        tasks = [entry["task"] for entry in created]
        return {"tasks": tasks, "count": len(tasks)}
