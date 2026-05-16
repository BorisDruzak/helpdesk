from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeBinding, KnowledgeChunk, KnowledgeItem, KnowledgeItemVersion
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities, sanitize_requester_knowledge_projection
from knowledge.search_analytics_service import KnowledgeSearchAnalyticsService


def _snippet(text: str, query: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    q = str(query or "").strip().lower()
    if q and q in text.lower():
        index = max(0, text.lower().find(q) - 40)
        return text[index : index + 180]
    return text[:180]


def _quality_label(confidence_score: Any) -> str | None:
    if confidence_score is None:
        return None
    try:
        score = float(confidence_score)
    except (TypeError, ValueError):
        return None
    if score >= 0.85:
        return "Проверено"
    if score >= 0.6:
        return "Средняя уверенность"
    return "Требует проверки"


def _freshness_label(review_due_at: Any) -> str | None:
    if review_due_at is None:
        return None
    if not hasattr(review_due_at, "astimezone"):
        return None
    due_at = review_due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return "Актуально" if due_at.astimezone(timezone.utc) > datetime.now(timezone.utc) else "Нужно обновить"


class KnowledgeSearchService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        *,
        query: str | None = None,
        actor_role: str = "requester",
        service_code: str | None = None,
        offering_code: str | None = None,
        request_template_key: str | None = None,
        surface: str = "search",
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        allowed = actor_visible_visibilities(actor_role)
        q = str(query or "").strip()
        stmt = (
            select(KnowledgeItem, KnowledgeItemVersion, KnowledgeChunk, KnowledgeBinding)
            .join(KnowledgeItemVersion, KnowledgeItem.current_version_id == KnowledgeItemVersion.version_id)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.version_id == KnowledgeItemVersion.version_id)
            .outerjoin(KnowledgeBinding, KnowledgeBinding.item_id == KnowledgeItem.item_id)
            .where(KnowledgeItem.status == "published", KnowledgeItem.visibility.in_(allowed))
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                (KnowledgeItem.title.ilike(like))
                | (KnowledgeItem.summary.ilike(like))
                | (KnowledgeItem.slug.ilike(like))
                | (KnowledgeChunk.text.ilike(like))
            )
        rows = (await self.session.execute(stmt)).all()
        scored: dict[str, tuple[int, dict[str, Any]]] = {}
        for item, version, chunk, binding in rows:
            score = 0
            if q and q.lower() in str(item.title or "").lower():
                score += 50
            if binding is not None:
                if service_code and binding.service_code == service_code:
                    score += 25
                if offering_code and binding.offering_code == offering_code:
                    score += 35
                if request_template_key and binding.request_template_key == request_template_key:
                    score += 30
            if chunk is not None and q and q.lower() in str(chunk.text or "").lower():
                score += 10
            payload = serialize_item(item, current_version=version)
            payload["version_id"] = version.version_id
            payload["snippet"] = _snippet(chunk.text if chunk is not None else version.body, q)
            payload["quality_label"] = _quality_label(item.confidence_score)
            payload["freshness_label"] = _freshness_label(item.review_due_at)
            if actor_role in {"requester", "agent", "public"}:
                payload = sanitize_requester_knowledge_projection(payload)
            current = scored.get(item.item_id)
            if current is None or score > current[0]:
                scored[item.item_id] = (score, payload)
        ordered = sorted(scored.values(), key=lambda item: (-item[0], str(item[1].get("title") or "")))
        results = [payload for _score, payload in ordered[: max(1, min(limit, 50))]]
        await KnowledgeSearchAnalyticsService(self.session).record_search_event(
            actor_role=actor_role,
            surface=surface,
            session_id=session_id,
            query_text=q,
            service_code=service_code,
            offering_code=offering_code,
            result_count=len(results),
        )
        return results
