"""Repository for request-form builder drafts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FormBuilderDraft


class FormDraftsRepo:
    """Stores unpublished form builder drafts separately from published packs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_draft(self, draft_id: str) -> FormBuilderDraft | None:
        result = await self.session.execute(
            select(FormBuilderDraft).where(FormBuilderDraft.id == draft_id)
        )
        return result.scalar_one_or_none()

    async def upsert_draft(
        self,
        *,
        draft_id: str,
        pack_key: str,
        schema_json: dict[str, Any],
        base_version: str | None = None,
        status: str = "draft",
        validation_report_json: dict[str, Any] | None = None,
        actor_id: str | None = None,
    ) -> FormBuilderDraft:
        now = datetime.now(timezone.utc)
        existing = await self.get_draft(draft_id)
        if existing is not None:
            existing.pack_key = pack_key
            existing.base_version = base_version
            existing.status = status
            existing.schema_json = schema_json
            existing.validation_report_json = validation_report_json or {}
            existing.updated_at = now
            existing.updated_by = actor_id
            await self.session.flush()
            return existing

        draft = FormBuilderDraft(
            id=draft_id,
            pack_key=pack_key,
            base_version=base_version,
            status=status,
            schema_json=schema_json,
            validation_report_json=validation_report_json or {},
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(draft)
        await self.session.flush()
        return draft

    async def mark_published(
        self,
        *,
        draft_id: str,
        published_version: str,
        actor_id: str | None = None,
    ) -> FormBuilderDraft | None:
        draft = await self.get_draft(draft_id)
        if draft is None:
            return None
        now = datetime.now(timezone.utc)
        draft.status = "published"
        draft.published_version = published_version
        draft.published_at = now
        draft.updated_at = now
        draft.updated_by = actor_id
        await self.session.flush()
        return draft
