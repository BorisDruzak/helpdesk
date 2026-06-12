from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeArticleEditorEvent, KnowledgeVersionDiffCache
from app.repos.knowledge_repo import KnowledgeRepo


def _new_id() -> str:
    return str(uuid.uuid4())


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _body_lines(value: Any) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _line_diff(previous_body: Any, next_body: Any) -> tuple[int, int, int]:
    previous = _body_lines(previous_body)
    current = _body_lines(next_body)
    added = [line for line in current if line not in previous]
    removed = [line for line in previous if line not in current]
    return len(added), len(removed), max(len(added), len(removed))


def serialize_editor_event(row: KnowledgeArticleEditorEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "item_id": row.item_id,
        "version_id": row.version_id,
        "event_type": row.event_type,
        "source_surface": row.source_surface,
        "summary": row.summary,
        "actor_id": row.actor_id,
        "actor_role": row.actor_role,
        "payload": _dict(row.payload_json),
        "created_at": _iso(row.created_at),
    }


def serialize_diff_cache(row: KnowledgeVersionDiffCache) -> dict[str, Any]:
    return {
        "diff_id": row.diff_id,
        "item_id": row.item_id,
        "from_version_id": row.from_version_id,
        "to_version_id": row.to_version_id,
        "added_lines": row.added_lines,
        "removed_lines": row.removed_lines,
        "changed_lines": row.changed_lines,
        "summary": _dict(row.summary_json),
        "content_hash": row.content_hash,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


class KnowledgeEditorHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_event(
        self,
        *,
        item_id: str,
        event_type: str,
        actor_id: str | None,
        actor_role: str | None,
        version_id: str | None = None,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = KnowledgeArticleEditorEvent(
            event_id=_new_id(),
            item_id=item_id,
            version_id=version_id,
            actor_id=actor_id,
            actor_role=actor_role,
            event_type=event_type,
            summary=_text(summary),
            payload_json=_dict(payload),
        )
        self.session.add(row)
        await self.session.flush()
        return serialize_editor_event(row)

    async def record_draft_created(self, item: dict[str, Any], *, actor_id: str | None, actor_role: str | None) -> dict[str, Any]:
        return await self.record_event(
            item_id=str(item["item_id"]),
            event_type="draft_created",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=str(item.get("title") or item.get("slug") or "Draft created"),
            payload={
                "slug": item.get("slug"),
                "visibility": item.get("visibility"),
                "item_type": item.get("item_type") or item.get("type"),
                "status": item.get("status"),
            },
        )

    async def record_version_created(
        self,
        *,
        item_id: str,
        version: dict[str, Any],
        base_version: dict[str, Any] | None,
        actor_id: str | None,
        actor_role: str | None,
        change_summary: str | None,
    ) -> dict[str, Any]:
        version_id = str(version["version_id"])
        added, removed, changed = _line_diff(base_version.get("body") if base_version else "", version.get("body"))
        content_hash = hashlib.sha256(str(version.get("body") or "").encode("utf-8")).hexdigest()
        summary = {
            "change_summary": _text(change_summary) or _text(version.get("change_summary")),
            "from_version_number": base_version.get("version_number") if base_version else None,
            "to_version_number": version.get("version_number"),
            "title": version.get("title"),
        }

        existing = (
            await self.session.execute(
                select(KnowledgeVersionDiffCache).where(KnowledgeVersionDiffCache.to_version_id == version_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = KnowledgeVersionDiffCache(
                diff_id=_new_id(),
                item_id=item_id,
                from_version_id=base_version.get("version_id") if base_version else None,
                to_version_id=version_id,
            )
            self.session.add(existing)
        existing.added_lines = added
        existing.removed_lines = removed
        existing.changed_lines = changed
        existing.summary_json = summary
        existing.content_hash = content_hash
        existing.updated_at = datetime.now(timezone.utc)

        await self.record_event(
            item_id=item_id,
            version_id=version_id,
            event_type="version_created",
            actor_id=actor_id,
            actor_role=actor_role,
            summary=_text(change_summary) or _text(version.get("change_summary")) or "Version created",
            payload={
                "version_number": version.get("version_number"),
                "base_version_id": base_version.get("version_id") if base_version else None,
                "added_lines": added,
                "removed_lines": removed,
            },
        )
        await self.session.flush()
        return serialize_diff_cache(existing)

    async def record_publish(
        self,
        *,
        item_id: str,
        version_id: str | None,
        previous_version_id: str | None,
        actor_id: str | None,
        actor_role: str | None,
        review_note: str | None,
    ) -> dict[str, Any]:
        event_type = "rollback_published" if previous_version_id and version_id and previous_version_id != version_id else "published"
        return await self.record_event(
            item_id=item_id,
            version_id=version_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            summary=_text(review_note) or ("Rollback published" if event_type == "rollback_published" else "Published"),
            payload={"previous_version_id": previous_version_id, "version_id": version_id},
        )

    async def record_review_action(
        self,
        *,
        item_id: str,
        action: str,
        actor_id: str | None,
        actor_role: str | None,
        note: str | None,
    ) -> dict[str, Any]:
        event_type = {
            "submit_review": "review_submitted",
            "request_changes": "changes_requested",
            "approve": "approved",
            "comment": "commented",
            "archive": "archived",
            "retire": "retired",
        }.get(action, "review_action")
        return await self.record_event(
            item_id=item_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            summary=_text(note) or action,
            payload={"action": action},
        )

    async def history(self, item_id_or_slug: str, *, actor_role: str, limit: int = 20) -> dict[str, Any]:
        item = await KnowledgeRepo(self.session).get_item(item_id_or_slug, actor_role=actor_role)
        item_id = str(item["item_id"])
        event_rows = (
            await self.session.execute(
                select(KnowledgeArticleEditorEvent)
                .where(KnowledgeArticleEditorEvent.item_id == item_id)
                .order_by(KnowledgeArticleEditorEvent.created_at.desc(), KnowledgeArticleEditorEvent.event_id.desc())
                .limit(max(1, min(int(limit), 100)))
            )
        ).scalars().all()
        diff_rows = (
            await self.session.execute(
                select(KnowledgeVersionDiffCache)
                .where(KnowledgeVersionDiffCache.item_id == item_id)
                .order_by(KnowledgeVersionDiffCache.created_at.desc(), KnowledgeVersionDiffCache.diff_id.desc())
                .limit(max(1, min(int(limit), 100)))
            )
        ).scalars().all()
        return {
            "events": [serialize_editor_event(row) for row in event_rows],
            "diff_cache": [serialize_diff_cache(row) for row in diff_rows],
        }
