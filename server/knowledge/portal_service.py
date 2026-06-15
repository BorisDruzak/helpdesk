from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, bindparam, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeAudienceRule, KnowledgeSpace
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.access_service import KnowledgeAccessService
from knowledge.contracts import REQUESTER_SAFE_VISIBILITIES, actor_visible_visibilities


REQUESTER_PORTAL_ROLES = {"public", "requester", "user", "agent"}


def _portal_role(actor_role: str | None) -> str:
    role = str(actor_role or "requester").lower()
    if role in REQUESTER_PORTAL_ROLES:
        return "requester"
    return role


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_value(value: Any) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _new_id() -> str:
    return str(uuid.uuid4())


def _bookmark_key(*, actor_id: str | None, session_id: str | None) -> str:
    actor = _text_value(actor_id)
    session = _text_value(session_id)
    if actor:
        return f"actor:{actor}"
    if session:
        return f"session:{session}"
    return "public:anonymous"


def _safe_space(space: dict[str, Any]) -> dict[str, Any]:
    return {
        "space_id": space.get("space_id"),
        "code": space.get("code"),
        "title": space.get("title"),
        "description": space.get("description"),
        "visibility": space.get("visibility"),
        "lifecycle_status": space.get("lifecycle_status"),
        "allow_rag": bool(space.get("allow_rag")),
        "updated_at": space.get("updated_at"),
    }


def _section_enabled_for_requester_portal(space: Any) -> bool:
    if isinstance(space, dict):
        visibility = str(space.get("visibility") or "")
        lifecycle_status = str(space.get("lifecycle_status") or "active")
        metadata = _dict(space.get("metadata") or space.get("metadata_json"))
    else:
        visibility = str(getattr(space, "visibility", "") or "")
        lifecycle_status = str(getattr(space, "lifecycle_status", "") or "active")
        metadata = _dict(getattr(space, "metadata_json", None))
    return (
        lifecycle_status == "active"
        and visibility in set(REQUESTER_SAFE_VISIBILITIES)
        and metadata.get("show_in_requester_portal") is not False
    )


def _safe_article_summary(item: dict[str, Any]) -> dict[str, Any]:
    current_version = item.get("current_version") if isinstance(item.get("current_version"), dict) else {}
    return {
        "item_id": item.get("item_id"),
        "space_id": item.get("space_id"),
        "slug": item.get("slug"),
        "item_type": item.get("item_type") or item.get("type"),
        "type": item.get("type") or item.get("item_type"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "status": item.get("status"),
        "visibility": item.get("visibility"),
        "version_id": item.get("version_id") or current_version.get("version_id"),
        "tags": _list(item.get("tags")),
        "owner_actor_id": item.get("owner_actor_id"),
        "review_due_at": item.get("review_due_at"),
        "published_at": item.get("published_at") or current_version.get("published_at"),
        "updated_at": item.get("updated_at"),
    }


def _safe_version(version: dict[str, Any]) -> dict[str, Any]:
    return {
        "version_id": version.get("version_id"),
        "item_id": version.get("item_id"),
        "version_number": version.get("version_number"),
        "title": version.get("title"),
        "summary": version.get("summary"),
        "body_format": version.get("body_format"),
        "body": version.get("body"),
        "published_at": version.get("published_at"),
        "created_at": version.get("created_at"),
    }


def _serialize_segment(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    return {
        "segment_id": data.get("segment_id"),
        "item_id": data.get("item_id"),
        "version_id": data.get("version_id"),
        "segment_index": data.get("segment_index"),
        "segment_type": data.get("segment_type"),
        "title": data.get("title"),
        "summary": data.get("summary"),
        "text": data.get("text"),
        "heading_path": data.get("heading_path_json") or [],
        "keywords": data.get("keywords_json") or [],
        "visibility": data.get("visibility"),
        "status": data.get("status"),
    }


class KnowledgePortalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = KnowledgeRepo(session)

    async def home(
        self,
        *,
        actor_role: str = "requester",
        limit: int = 12,
        effective_audience: Any | None = None,
    ) -> dict[str, Any]:
        role = _portal_role(actor_role)
        items = await self.repo.list_items(actor_role=role, include_archived=False)
        items = await self._filter_audience_visible_items(items, effective_audience=effective_audience)
        raw_spaces = [
            space
            for space in await self.repo.list_spaces(actor_role=role)
            if space.get("lifecycle_status") == "active" and _section_enabled_for_requester_portal(space)
        ]
        portal_space_ids = {str(space.get("space_id") or "") for space in raw_spaces}
        items = [item for item in items if str(item.get("space_id") or "") in portal_space_ids]
        spaces = [_safe_space(space) for space in raw_spaces]
        article_summaries = [_safe_article_summary(item) for item in items if item.get("status") == "published"]
        recent = article_summaries[: max(1, min(int(limit or 12), 50))]
        signal_scores = await self._portal_signal_scores([str(article.get("item_id") or "") for article in article_summaries])
        popular = sorted(
            article_summaries,
            key=lambda article: (signal_scores.get(str(article.get("item_id") or ""), 0.0), article.get("updated_at") or ""),
            reverse=True,
        )[:6]
        if not any(signal_scores.values()):
            popular = recent[:6]
        featured = popular[:6]
        return {
            "display_message": "Портал базы знаний загружен",
            "spaces": spaces,
            "featured_articles": featured,
            "recent_articles": recent,
            "popular_articles": popular,
        }

    async def article_detail(
        self,
        slug: str,
        *,
        actor_role: str = "requester",
        effective_audience: Any | None = None,
    ) -> dict[str, Any]:
        role = _portal_role(actor_role)
        item = await self.repo.get_item(slug, actor_role=role)
        await self._ensure_item_space_enabled_for_requester_portal(item)
        version = item.get("current_version")
        if not isinstance(version, dict) or not version.get("body"):
            raise ValueError("knowledge article not found")
        if effective_audience is not None:
            await self._ensure_audience_can_view_item(item, effective_audience=effective_audience)
        safe_article = _safe_article_summary(item)
        safe_version = _safe_version(version)
        return {
            "article": safe_article,
            "version": safe_version,
            "segments": await self._segments(
                item_id=str(safe_article.get("item_id") or ""),
                version_id=str(safe_version.get("version_id") or ""),
                actor_role=role,
            ),
            "related_articles": [],
        }

    async def record_article_view(
        self,
        article: dict[str, Any],
        version: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str = "requester",
        session_id: str | None = None,
    ) -> None:
        item_id = _text_value(article.get("item_id"))
        version_id = _text_value(version.get("version_id"))
        if not item_id or not version_id:
            return
        await self.session.execute(
            text(
                """
                INSERT INTO knowledge_article_views (
                    view_id, item_id, version_id, actor_id, actor_role, session_id,
                    source_surface, metadata_json
                )
                VALUES (
                    :view_id, :item_id, :version_id, :actor_id, :actor_role, :session_id,
                    'requester_portal', '{}'::jsonb
                )
                """
            ),
            {
                "view_id": _new_id(),
                "item_id": item_id,
                "version_id": version_id,
                "actor_id": _text_value(actor_id),
                "actor_role": _text_value(actor_role),
                "session_id": _text_value(session_id),
            },
        )

    async def record_correction_request(
        self,
        article: dict[str, Any],
        version: dict[str, Any],
        *,
        comment: str,
        feedback_event_id: str | None,
        actor_id: str | None,
        actor_role: str = "requester",
        session_id: str | None = None,
    ) -> None:
        item_id = _text_value(article.get("item_id"))
        version_id = _text_value(version.get("version_id"))
        safe_comment = _text_value(comment) or "Requester requested article correction."
        if not item_id or not version_id:
            return
        await self.session.execute(
            text(
                """
                INSERT INTO knowledge_correction_requests (
                    correction_request_id, item_id, version_id, feedback_event_id,
                    actor_id, actor_role, session_id, comment, status, source_surface,
                    metadata_json
                )
                VALUES (
                    :request_id, :item_id, :version_id, :feedback_event_id,
                    :actor_id, :actor_role, :session_id, :comment, 'open',
                    'requester_portal', '{}'::jsonb
                )
                """
            ),
            {
                "request_id": _new_id(),
                "item_id": item_id,
                "version_id": version_id,
                "feedback_event_id": _text_value(feedback_event_id),
                "actor_id": _text_value(actor_id),
                "actor_role": _text_value(actor_role),
                "session_id": _text_value(session_id),
                "comment": safe_comment[:2000],
            },
        )

    async def set_bookmark(
        self,
        article: dict[str, Any],
        version: dict[str, Any],
        *,
        bookmarked: bool,
        actor_id: str | None,
        actor_role: str = "requester",
        session_id: str | None = None,
    ) -> None:
        item_id = _text_value(article.get("item_id"))
        version_id = _text_value(version.get("version_id"))
        if not item_id or not version_id:
            return
        await self.session.execute(
            text(
                """
                INSERT INTO knowledge_user_bookmarks (
                    bookmark_id, bookmark_key, item_id, version_id, actor_id, actor_role,
                    session_id, bookmark_state, source_surface, metadata_json
                )
                VALUES (
                    :bookmark_id, :bookmark_key, :item_id, :version_id, :actor_id, :actor_role,
                    :session_id, :bookmark_state, 'requester_portal', '{}'::jsonb
                )
                ON CONFLICT (bookmark_key, item_id)
                DO UPDATE SET
                    version_id = EXCLUDED.version_id,
                    actor_id = EXCLUDED.actor_id,
                    actor_role = EXCLUDED.actor_role,
                    session_id = EXCLUDED.session_id,
                    bookmark_state = EXCLUDED.bookmark_state,
                    updated_at = now()
                """
            ),
            {
                "bookmark_id": _new_id(),
                "bookmark_key": _bookmark_key(actor_id=actor_id, session_id=session_id),
                "item_id": item_id,
                "version_id": version_id,
                "actor_id": _text_value(actor_id),
                "actor_role": _text_value(actor_role),
                "session_id": _text_value(session_id),
                "bookmark_state": "active" if bookmarked else "removed",
            },
        )

    async def collection(
        self,
        *,
        collection_type: str,
        code: str,
        actor_role: str = "requester",
        effective_audience: Any | None = None,
    ) -> dict[str, Any]:
        role = _portal_role(actor_role)
        normalized_type = str(collection_type or "").strip().lower()
        normalized_code = str(code or "").strip().lower()
        if normalized_type not in {"space", "tag"} or not normalized_code:
            raise ValueError("knowledge collection not found")

        items = await self.repo.list_items(actor_role=role, include_archived=False)
        items = await self._filter_audience_visible_items(items, effective_audience=effective_audience)
        items = await self._filter_requester_portal_items(items)
        if normalized_type == "space":
            spaces = [
                _safe_space(space)
                for space in await self.repo.list_spaces(actor_role=role)
                if space.get("lifecycle_status") == "active" and _section_enabled_for_requester_portal(space)
            ]
            space = next((space for space in spaces if str(space.get("code") or "").lower() == normalized_code), None)
            if space is None:
                raise ValueError("knowledge collection not found")
            articles = [
                _safe_article_summary(item)
                for item in items
                if item.get("status") == "published" and item.get("space_id") == space.get("space_id")
            ]
            return {
                "collection_type": "space",
                "collection_code": space.get("code"),
                "title": space.get("title"),
                "description": space.get("description"),
                "space": space,
                "articles": articles,
            }

        articles = [
            _safe_article_summary(item)
            for item in items
            if item.get("status") == "published" and normalized_code in {str(tag).lower() for tag in _list(item.get("tags"))}
        ]
        return {
            "collection_type": "tag",
            "collection_code": normalized_code,
            "title": normalized_code,
            "description": None,
            "articles": articles,
        }

    async def _filter_audience_visible_items(
        self,
        items: list[dict[str, Any]],
        *,
        effective_audience: Any | None,
    ) -> list[dict[str, Any]]:
        if effective_audience is None or not items:
            return items
        item_ids = sorted({str(item.get("item_id") or "") for item in items if item.get("item_id")})
        space_ids = sorted({str(item.get("space_id") or "") for item in items if item.get("space_id")})
        if not item_ids:
            return []
        spaces = (
            await self.session.execute(select(KnowledgeSpace).where(KnowledgeSpace.space_id.in_(space_ids)))
        ).scalars().all()
        spaces_by_id = {
            space.space_id: {
                "space_id": space.space_id,
                "lifecycle_status": space.lifecycle_status,
                "visibility": space.visibility,
            }
            for space in spaces
        }
        rules = (
            await self.session.execute(
                select(KnowledgeAudienceRule)
                .where(
                    KnowledgeAudienceRule.status == "active",
                    or_(
                        and_(
                            KnowledgeAudienceRule.subject_type == "item",
                            KnowledgeAudienceRule.subject_id.in_(item_ids),
                        ),
                        and_(
                            KnowledgeAudienceRule.subject_type == "space",
                            KnowledgeAudienceRule.subject_id.in_(space_ids),
                        ),
                    ),
                )
                .order_by(
                    KnowledgeAudienceRule.priority.asc(),
                    KnowledgeAudienceRule.created_at.asc(),
                    KnowledgeAudienceRule.rule_id.asc(),
                )
            )
        ).scalars().all()
        return KnowledgeAccessService.filter_authorized_items(
            items=items,
            spaces_by_id=spaces_by_id,
            audience=effective_audience,
            rules=[
                {
                    "rule_id": row.rule_id,
                    "subject_type": row.subject_type,
                    "subject_id": row.subject_id,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "effect": row.effect,
                    "include_children": row.include_children,
                    "priority": row.priority,
                    "status": row.status,
                }
                for row in rules
            ],
        )

    async def _filter_requester_portal_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not items:
            return []
        space_ids = sorted({str(item.get("space_id") or "") for item in items if item.get("space_id")})
        if not space_ids:
            return []
        spaces = (
            await self.session.execute(select(KnowledgeSpace).where(KnowledgeSpace.space_id.in_(space_ids)))
        ).scalars().all()
        portal_space_ids = {space.space_id for space in spaces if _section_enabled_for_requester_portal(space)}
        return [item for item in items if str(item.get("space_id") or "") in portal_space_ids]

    async def _segments(self, *, item_id: str, version_id: str, actor_role: str) -> list[dict[str, Any]]:
        if not item_id or not version_id:
            return []
        allowed = tuple(actor_visible_visibilities(actor_role))
        stmt = (
            text(
                """
                SELECT segment_id, item_id, version_id, segment_index, segment_type, title,
                       summary, text, heading_path_json, keywords_json, visibility, status
                FROM knowledge_article_segments
                WHERE item_id = :item_id
                  AND version_id = :version_id
                  AND status = 'active'
                  AND visibility IN :allowed
                ORDER BY segment_index, created_at, segment_id
                """
            )
            .bindparams(bindparam("allowed", expanding=True))
        )
        rows = (
            await self.session.execute(
                stmt,
                {"item_id": item_id, "version_id": version_id, "allowed": allowed},
            )
        ).all()
        return [_serialize_segment(row) for row in rows]

    async def _ensure_audience_can_view_item(self, item: dict[str, Any], *, effective_audience: Any) -> None:
        item_id = str(item.get("item_id") or "")
        space_id = str(item.get("space_id") or "")
        space = await self.session.get(KnowledgeSpace, space_id) if space_id else None
        rules = (
            await self.session.execute(
                select(KnowledgeAudienceRule)
                .where(
                    KnowledgeAudienceRule.status == "active",
                    or_(
                        and_(
                            KnowledgeAudienceRule.subject_type == "item",
                            KnowledgeAudienceRule.subject_id == item_id,
                        ),
                        and_(
                            KnowledgeAudienceRule.subject_type == "space",
                            KnowledgeAudienceRule.subject_id == space_id,
                        ),
                    ),
                )
                .order_by(
                    KnowledgeAudienceRule.priority.asc(),
                    KnowledgeAudienceRule.created_at.asc(),
                    KnowledgeAudienceRule.rule_id.asc(),
                )
            )
        ).scalars().all()
        current_version = item.get("current_version") if isinstance(item.get("current_version"), dict) else {}
        decision = KnowledgeAccessService.evaluate_item_access(
            item={
                "item_id": item_id,
                "space_id": space_id,
                "status": item.get("status"),
                "visibility": item.get("visibility"),
                "current_version_id": item.get("current_version_id") or current_version.get("version_id"),
            },
            space=(
                {
                    "space_id": space.space_id,
                    "lifecycle_status": space.lifecycle_status,
                    "visibility": space.visibility,
                }
                if space is not None
                else None
            ),
            audience=effective_audience,
            rules=[
                {
                    "rule_id": row.rule_id,
                    "subject_type": row.subject_type,
                    "subject_id": row.subject_id,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "effect": row.effect,
                    "include_children": row.include_children,
                    "priority": row.priority,
                    "status": row.status,
                }
                for row in rules
            ],
        )
        if not decision.allowed:
            raise ValueError("knowledge article not found")

    async def _ensure_item_space_enabled_for_requester_portal(self, item: dict[str, Any]) -> None:
        space_id = str(item.get("space_id") or "")
        space = await self.session.get(KnowledgeSpace, space_id) if space_id else None
        if space is None or not _section_enabled_for_requester_portal(space):
            raise ValueError("knowledge article not found")

    async def _portal_signal_scores(self, item_ids: list[str]) -> dict[str, float]:
        ids = [item_id for item_id in item_ids if item_id]
        if not ids:
            return {}
        scores = {item_id: 0.0 for item_id in ids}
        queries = [
            (
                """
                SELECT item_id, COUNT(*) AS count
                FROM knowledge_article_views
                WHERE item_id IN :item_ids
                GROUP BY item_id
                """,
                1.0,
            ),
            (
                """
                SELECT item_id, COUNT(*) AS count
                FROM knowledge_user_bookmarks
                WHERE item_id IN :item_ids
                  AND bookmark_state = 'active'
                GROUP BY item_id
                """,
                4.0,
            ),
            (
                """
                SELECT item_id, COUNT(*) AS count
                FROM knowledge_feedback_events
                WHERE item_id IN :item_ids
                  AND event_type = 'helpful'
                  AND source_surface = 'requester_portal'
                GROUP BY item_id
                """,
                3.0,
            ),
            (
                """
                SELECT item_id, COUNT(*) AS count
                FROM knowledge_correction_requests
                WHERE item_id IN :item_ids
                  AND status = 'open'
                GROUP BY item_id
                """,
                1.0,
            ),
        ]
        for sql, weight in queries:
            stmt = text(sql).bindparams(bindparam("item_ids", expanding=True))
            rows = (await self.session.execute(stmt, {"item_ids": ids})).all()
            for row in rows:
                data = row._mapping if hasattr(row, "_mapping") else row
                item_id = str(data["item_id"])
                scores[item_id] = scores.get(item_id, 0.0) + float(data["count"] or 0) * weight
        return scores
