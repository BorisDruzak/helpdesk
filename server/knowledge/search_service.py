from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeAudienceRule,
    KnowledgeBinding,
    KnowledgeChunk,
    KnowledgeItem,
    KnowledgeItemVersion,
    KnowledgeSpace,
)
from app.repos.knowledge_repo import serialize_item
from knowledge.access_service import KnowledgeAccessService
from knowledge.binding_surfaces import allowed_item_ids_for_binding_surface
from knowledge.contracts import actor_visible_visibilities, sanitize_requester_knowledge_projection
from knowledge.search_analytics_service import KnowledgeSearchAnalyticsService
from knowledge.vector_search_service import KnowledgeVectorSearchService


def _snippet(text: str, query: str, *, max_length: int = 180) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    bounded_length = max(80, min(int(max_length or 180), 1000))
    q = str(query or "").strip().lower()
    if q and q in text.lower():
        index = max(0, text.lower().find(q) - 40)
        return text[index : index + bounded_length]
    return text[:bounded_length]


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
        snippet_length: int = 180,
        vector_enabled: bool = False,
        query_vector: list[float] | None = None,
        vector_weight: float = 1.0,
        effective_audience: Any | None = None,
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
        access_context = await self._audience_access_context(
            rows=[row[0] for row in rows],
            effective_audience=effective_audience,
        )
        service_context = {
            "service_code": service_code,
            "offering_code": offering_code,
            "request_template_key": request_template_key,
        }
        scored: dict[str, tuple[int, dict[str, Any]]] = {}
        for item, version, chunk, binding in rows:
            if not self._item_allowed_by_audience(
                item,
                effective_audience=effective_audience,
                access_context=access_context,
                service_context=service_context,
            ):
                continue
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
            payload["snippet"] = _snippet(chunk.text if chunk is not None else version.body, q, max_length=snippet_length)
            payload["quality_label"] = _quality_label(item.confidence_score)
            payload["freshness_label"] = _freshness_label(item.review_due_at)
            if actor_role in {"requester", "agent", "public"}:
                payload = sanitize_requester_knowledge_projection(payload)
            current = scored.get(item.item_id)
            if current is None or score > current[0]:
                scored[item.item_id] = (score, payload)
        if q:
            segment_rows = await self._search_segment_rows(q, allowed)
            for row in segment_rows:
                item = await self.session.get(KnowledgeItem, row["item_id"])
                version = await self.session.get(KnowledgeItemVersion, row["version_id"])
                if item is None or version is None:
                    continue
                if effective_audience is not None and item.item_id not in access_context["spaces_by_item"]:
                    extra_context = await self._audience_access_context(
                        rows=[item],
                        effective_audience=effective_audience,
                    )
                    access_context["spaces_by_item"].update(extra_context["spaces_by_item"])
                    access_context["rules"].extend(extra_context["rules"])
                if not self._item_allowed_by_audience(
                    item,
                    effective_audience=effective_audience,
                    access_context=access_context,
                    service_context=service_context,
                ):
                    continue
                lower_q = q.lower()
                score = 15
                if lower_q in str(row.get("segment_title") or "").lower():
                    score += 60
                if lower_q in str(row.get("keywords_json") or "").lower():
                    score += 55
                if lower_q in str(row.get("segment_text") or "").lower():
                    score += 20
                try:
                    score += int(float(row.get("boost") or 1) * 10)
                except (TypeError, ValueError):
                    score += 10
                payload = serialize_item(item, current_version=version)
                payload["version_id"] = version.version_id
                payload["snippet"] = _snippet(row.get("segment_text") or version.body, q, max_length=snippet_length)
                payload["quality_label"] = _quality_label(item.confidence_score)
                payload["freshness_label"] = _freshness_label(item.review_due_at)
                if actor_role in {"requester", "agent", "public"}:
                    payload = sanitize_requester_knowledge_projection(payload)
                current = scored.get(item.item_id)
                if current is None or score > current[0]:
                    scored[item.item_id] = (score, payload)
        if vector_enabled and query_vector:
            vector_rows = await KnowledgeVectorSearchService(self.session).search(
                query_vector=query_vector,
                actor_role=actor_role,
                limit=limit,
            )
            for row in vector_rows:
                item = await self.session.get(KnowledgeItem, row["item_id"])
                version = await self.session.get(KnowledgeItemVersion, row["version_id"])
                if item is None or version is None:
                    continue
                if effective_audience is not None and item.item_id not in access_context["spaces_by_item"]:
                    extra_context = await self._audience_access_context(
                        rows=[item],
                        effective_audience=effective_audience,
                    )
                    access_context["spaces_by_item"].update(extra_context["spaces_by_item"])
                    access_context["rules"].extend(extra_context["rules"])
                if not self._item_allowed_by_audience(
                    item,
                    effective_audience=effective_audience,
                    access_context=access_context,
                    service_context=service_context,
                ):
                    continue
                try:
                    score = int(float(row.get("score") or 0) * 100 * max(0.0, float(vector_weight or 1.0)))
                except (TypeError, ValueError):
                    score = 0
                if score <= 0:
                    continue
                payload = serialize_item(item, current_version=version)
                payload["version_id"] = version.version_id
                payload["snippet"] = _snippet(row.get("chunk_text") or version.body, q, max_length=snippet_length)
                payload["quality_label"] = _quality_label(item.confidence_score)
                payload["freshness_label"] = _freshness_label(item.review_due_at)
                payload["retrieval_source"] = "vector"
                payload["vector_score"] = round(float(row.get("score") or 0), 6)
                if row.get("segment_id"):
                    payload["segment_id"] = row["segment_id"]
                if actor_role in {"requester", "agent", "public"}:
                    payload = sanitize_requester_knowledge_projection(payload)
                current = scored.get(item.item_id)
                if current is None or score > current[0]:
                    scored[item.item_id] = (score, payload)
        allowed_surface_item_ids = await allowed_item_ids_for_binding_surface(
            self.session,
            set(scored),
            surface=surface,
        )
        for item_id in list(scored):
            if item_id not in allowed_surface_item_ids:
                scored.pop(item_id, None)
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

    async def _audience_access_context(
        self,
        *,
        rows: list[KnowledgeItem],
        effective_audience: Any | None,
    ) -> dict[str, Any]:
        if effective_audience is None:
            return {"spaces_by_item": {}, "rules": []}
        items = {row.item_id: row for row in rows if row is not None}
        if not items:
            return {"spaces_by_item": {}, "rules": []}
        space_ids = sorted({str(item.space_id) for item in items.values() if item.space_id})
        item_ids = sorted(items)
        spaces = (
            await self.session.execute(
                select(KnowledgeSpace).where(KnowledgeSpace.space_id.in_(space_ids))
            )
        ).scalars().all()
        spaces_by_id = {space.space_id: _space_payload(space) for space in spaces}
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
                .order_by(KnowledgeAudienceRule.priority.asc(), KnowledgeAudienceRule.created_at.asc(), KnowledgeAudienceRule.rule_id.asc())
            )
        ).scalars().all()
        return {
            "spaces_by_item": {
                item_id: spaces_by_id.get(str(item.space_id))
                for item_id, item in items.items()
            },
            "rules": [_rule_payload(rule) for rule in rules],
        }

    def _item_allowed_by_audience(
        self,
        item: KnowledgeItem,
        *,
        effective_audience: Any | None,
        access_context: dict[str, Any],
        service_context: dict[str, Any],
    ) -> bool:
        if effective_audience is None:
            return True
        decision = KnowledgeAccessService.evaluate_item_access(
            item=_item_payload(item),
            space=(access_context.get("spaces_by_item") or {}).get(item.item_id),
            audience=effective_audience,
            rules=list(access_context.get("rules") or []),
            service_context=service_context,
        )
        return decision.allowed

    async def _search_segment_rows(self, query: str, allowed: tuple[str, ...]) -> list[dict[str, Any]]:
        item_visibility_params = {f"item_visibility_{index}": value for index, value in enumerate(allowed)}
        segment_visibility_params = {f"segment_visibility_{index}": value for index, value in enumerate(allowed)}
        item_visibility_sql = ", ".join(f":{key}" for key in item_visibility_params)
        segment_visibility_sql = ", ".join(f":{key}" for key in segment_visibility_params)
        rows = (
            await self.session.execute(
                text(
                    f"""
                    SELECT
                        s.item_id,
                        s.version_id,
                        s.title AS segment_title,
                        s.summary AS segment_summary,
                        s.text AS segment_text,
                        s.keywords_json,
                        s.boost
                    FROM knowledge_article_segments s
                    JOIN knowledge_items i ON i.item_id = s.item_id
                    WHERE i.status = 'published'
                      AND i.current_version_id = s.version_id
                      AND i.visibility IN ({item_visibility_sql})
                      AND s.visibility IN ({segment_visibility_sql})
                      AND s.status = 'active'
                      AND s.full_text_enabled = true
                      AND (
                        lower(COALESCE(s.title, '')) LIKE :like
                        OR lower(COALESCE(s.summary, '')) LIKE :like
                        OR lower(COALESCE(s.text, '')) LIKE :like
                        OR lower(COALESCE(s.keywords_json::text, '')) LIKE :like
                      )
                    """
                ),
                {
                    **item_visibility_params,
                    **segment_visibility_params,
                    "like": f"%{query.lower()}%",
                },
            )
        ).all()
        return [dict(row._mapping) for row in rows]


def _item_payload(row: KnowledgeItem) -> dict[str, Any]:
    return {
        "item_id": row.item_id,
        "space_id": row.space_id,
        "status": row.status,
        "visibility": row.visibility,
        "current_version_id": row.current_version_id,
    }


def _space_payload(row: KnowledgeSpace) -> dict[str, Any]:
    return {
        "space_id": row.space_id,
        "lifecycle_status": row.lifecycle_status,
        "visibility": row.visibility,
    }


def _rule_payload(row: KnowledgeAudienceRule) -> dict[str, Any]:
    return {
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
