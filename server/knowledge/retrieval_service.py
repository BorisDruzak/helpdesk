from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeItem, KnowledgeItemVersion
from app.repos.knowledge_repo import serialize_item
from knowledge.contracts import actor_visible_visibilities, sanitize_requester_knowledge_projection
from knowledge.search_analytics_service import KnowledgeSearchAnalyticsService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from knowledge.vector_search_service import KnowledgeVectorSearchService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _snippet(text_value: Any, query: str, *, max_length: int) -> str:
    text_text = str(text_value or "").strip()
    if not text_text:
        return ""
    bounded = max(80, min(int(max_length or 180), 1000))
    lower_query = str(query or "").strip().lower()
    lower_text = text_text.lower()
    if lower_query and lower_query in lower_text:
        start = max(0, lower_text.find(lower_query) - 40)
        return text_text[start : start + bounded]
    return text_text[:bounded]


class KnowledgeRetrievalService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def retrieve(
        self,
        *,
        query: str | None,
        actor_role: str,
        service_code: str | None = None,
        offering_code: str | None = None,
        request_template_key: str | None = None,
        surface: str = "retrieve",
        session_id: str | None = None,
        limit: int | None = None,
        query_vector: list[float] | None = None,
    ) -> dict[str, Any]:
        settings = await KnowledgeSearchSettingsService(self.session).get_settings()
        effective_mode = str(settings.get("effective_mode") or "keyword_only")
        max_results = max(1, min(int(limit or settings.get("max_results") or 10), int(settings.get("max_results") or 10), 50))
        snippet_length = int(settings.get("snippet_length") or 180)
        query_text = str(query or "").strip()
        allowed = tuple(actor_visible_visibilities(actor_role))
        candidates: dict[str, dict[str, Any]] = {}

        if bool(settings.get("keyword_enabled", True)):
            await self._merge_keyword_candidates(
                candidates,
                query=query_text,
                allowed=allowed,
                actor_role=actor_role,
                service_code=service_code,
                offering_code=offering_code,
                request_template_key=request_template_key,
                snippet_length=snippet_length,
            )

        if bool(settings.get("full_text_enabled", False)) or effective_mode in {"hybrid_no_ai", "hybrid_vector", "hybrid_vector_rerank"}:
            await self._merge_segment_candidates(
                candidates,
                query=query_text,
                allowed=allowed,
                actor_role=actor_role,
                snippet_length=snippet_length,
            )

        vector_used = False
        vector_fallback = None
        if bool(settings.get("vector_enabled", False)):
            if query_vector:
                vector_rows = await KnowledgeVectorSearchService(self.session).search(
                    query_vector=query_vector,
                    actor_role=actor_role,
                    limit=max_results,
                )
                vector_used = bool(vector_rows)
                await self._merge_vector_candidates(
                    candidates,
                    rows=vector_rows,
                    actor_role=actor_role,
                    query=query_text,
                    snippet_length=snippet_length,
                    vector_weight=float(settings.get("vector_weight") or 1.0),
                )
            else:
                vector_fallback = "query_vector_missing"

        ordered = sorted(candidates.values(), key=lambda item: (-float(item["score"]), str(item["item"].get("title") or "")))
        results = ordered[:max_results]
        if actor_role in {"requester", "agent", "public"}:
            for result in results:
                result.pop("score_parts", None)
        await KnowledgeSearchAnalyticsService(self.session).record_search_event(
            actor_role=actor_role,
            surface=surface,
            session_id=session_id,
            query_text=query_text,
            service_code=service_code,
            offering_code=offering_code,
            result_count=len(results),
        )
        await self._record_observer_event(
            "knowledge.retrieval.zero_results" if not results else "knowledge.retrieval.executed",
            actor_role=actor_role,
            details={
                "surface": surface,
                "effective_mode": effective_mode,
                "result_count": len(results),
                "vector_used": vector_used,
                "fallback_mode": vector_fallback,
            },
        )
        return {
            "results": results,
            "search_mode": settings.get("search_mode"),
            "effective_mode": effective_mode,
            "fallback_mode": vector_fallback,
            "ai_used": bool(settings.get("ai_enabled")) and vector_used,
            "settings": {
                "keyword_enabled": bool(settings.get("keyword_enabled", True)),
                "full_text_enabled": bool(settings.get("full_text_enabled", False)),
                "vector_enabled": bool(settings.get("vector_enabled", False)),
                "rerank_enabled": bool(settings.get("rerank_enabled", False)),
            },
        }

    async def _merge_keyword_candidates(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        query: str,
        allowed: tuple[str, ...],
        actor_role: str,
        service_code: str | None,
        offering_code: str | None,
        request_template_key: str | None,
        snippet_length: int,
    ) -> None:
        if not query:
            return
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        i.item_id,
                        v.version_id,
                        c.chunk_id,
                        NULL::text AS segment_id,
                        i.title,
                        i.summary,
                        i.slug,
                        i.confidence_score,
                        i.review_due_at,
                        c.text AS chunk_text,
                        b.service_code,
                        b.offering_code,
                        b.request_template_key
                    FROM knowledge_items i
                    JOIN knowledge_item_versions v ON v.version_id = i.current_version_id
                    LEFT JOIN knowledge_chunks c ON c.version_id = v.version_id
                    LEFT JOIN knowledge_bindings b ON b.item_id = i.item_id
                    WHERE i.status = 'published'
                      AND i.visibility = ANY(:allowed)
                      AND (
                        lower(COALESCE(i.title, '')) LIKE :like
                        OR lower(COALESCE(i.summary, '')) LIKE :like
                        OR lower(COALESCE(i.slug, '')) LIKE :like
                        OR lower(COALESCE(c.text, '')) LIKE :like
                      )
                    LIMIT 250
                    """
                ),
                {"allowed": list(allowed), "like": f"%{query.lower()}%"},
            )
        ).mappings().all()
        lower_query = query.lower()
        for row in rows:
            parts: dict[str, float] = {}
            if lower_query in str(row.get("title") or "").lower():
                parts["keyword_title"] = 50.0
            if lower_query in str(row.get("summary") or "").lower():
                parts["keyword_summary"] = 25.0
            if lower_query in str(row.get("slug") or "").lower():
                parts["keyword_slug"] = 20.0
            if lower_query in str(row.get("chunk_text") or "").lower():
                parts["keyword_chunk"] = 15.0
            self._apply_binding_parts(parts, row, service_code=service_code, offering_code=offering_code, request_template_key=request_template_key)
            await self._upsert_candidate(candidates, row=row, actor_role=actor_role, query=query, snippet_length=snippet_length, parts=parts, source="keyword")

    async def _merge_segment_candidates(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        query: str,
        allowed: tuple[str, ...],
        actor_role: str,
        snippet_length: int,
    ) -> None:
        if not query:
            return
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        i.item_id,
                        s.version_id,
                        NULL::text AS chunk_id,
                        s.segment_id,
                        i.title,
                        i.summary,
                        i.slug,
                        i.confidence_score,
                        i.review_due_at,
                        s.title AS segment_title,
                        s.summary AS segment_summary,
                        s.text AS chunk_text,
                        s.keywords_json,
                        s.boost
                    FROM knowledge_article_segments s
                    JOIN knowledge_items i ON i.item_id = s.item_id
                    WHERE i.status = 'published'
                      AND i.current_version_id = s.version_id
                      AND i.visibility = ANY(:allowed)
                      AND s.visibility = ANY(:allowed)
                      AND s.status = 'active'
                      AND s.full_text_enabled = true
                      AND (
                        lower(COALESCE(s.title, '')) LIKE :like
                        OR lower(COALESCE(s.summary, '')) LIKE :like
                        OR lower(COALESCE(s.text, '')) LIKE :like
                        OR lower(COALESCE(s.keywords_json::text, '')) LIKE :like
                      )
                    LIMIT 250
                    """
                ),
                {"allowed": list(allowed), "like": f"%{query.lower()}%"},
            )
        ).mappings().all()
        lower_query = query.lower()
        for row in rows:
            parts: dict[str, float] = {"manual_segment": 10.0}
            if lower_query in str(row.get("segment_title") or "").lower():
                parts["segment_title"] = 60.0
            if lower_query in str(row.get("keywords_json") or "").lower():
                parts["segment_keywords"] = 55.0
            if lower_query in str(row.get("chunk_text") or "").lower():
                parts["segment_text"] = 20.0
            try:
                parts["segment_boost"] = float(row.get("boost") or 1) * 10
            except (TypeError, ValueError):
                parts["segment_boost"] = 10.0
            await self._upsert_candidate(candidates, row=row, actor_role=actor_role, query=query, snippet_length=snippet_length, parts=parts, source="segment")

    async def _merge_vector_candidates(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        rows: list[dict[str, Any]],
        actor_role: str,
        query: str,
        snippet_length: int,
        vector_weight: float,
    ) -> None:
        for row in rows:
            item = await self.session.get(KnowledgeItem, row["item_id"])
            version = await self.session.get(KnowledgeItemVersion, row["version_id"])
            if item is None or version is None:
                continue
            mapped = {
                "item_id": item.item_id,
                "version_id": version.version_id,
                "chunk_id": row.get("chunk_id"),
                "segment_id": row.get("segment_id"),
                "title": item.title,
                "summary": item.summary,
                "slug": item.slug,
                "confidence_score": item.confidence_score,
                "review_due_at": item.review_due_at,
                "chunk_text": row.get("chunk_text"),
            }
            parts = {"vector": float(row.get("score") or 0) * 100 * max(0.0, vector_weight)}
            await self._upsert_candidate(candidates, row=mapped, actor_role=actor_role, query=query, snippet_length=snippet_length, parts=parts, source="vector")

    def _apply_binding_parts(
        self,
        parts: dict[str, float],
        row: Any,
        *,
        service_code: str | None,
        offering_code: str | None,
        request_template_key: str | None,
    ) -> None:
        if service_code and row.get("service_code") == service_code:
            parts["binding_service"] = 25.0
        if offering_code and row.get("offering_code") == offering_code:
            parts["binding_offering"] = 35.0
        if request_template_key and row.get("request_template_key") == request_template_key:
            parts["binding_template"] = 30.0

    async def _upsert_candidate(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        row: Any,
        actor_role: str,
        query: str,
        snippet_length: int,
        parts: dict[str, float],
        source: str,
    ) -> None:
        if not parts:
            return
        item = await self.session.get(KnowledgeItem, row["item_id"])
        version = await self.session.get(KnowledgeItemVersion, row["version_id"])
        if item is None or version is None:
            return
        item_payload = serialize_item(item, current_version=version)
        if actor_role in {"requester", "agent", "public"}:
            item_payload = sanitize_requester_knowledge_projection(item_payload)
        candidate = candidates.get(item.item_id)
        if candidate is None:
            candidate = {
                "item": item_payload,
                "version": {"version_id": version.version_id, "title": version.title},
                "chunk_id": row.get("chunk_id"),
                "segment_id": row.get("segment_id"),
                "snippet": _snippet(row.get("chunk_text") or version.body, query, max_length=snippet_length),
                "score": 0.0,
                "score_parts": {},
                "source_mode": [],
                "fallback_mode": None,
                "citations": [],
            }
            candidates[item.item_id] = candidate
        for key, value in parts.items():
            candidate["score_parts"][key] = max(float(candidate["score_parts"].get(key) or 0), float(value))
        candidate["score"] = round(sum(float(value) for value in candidate["score_parts"].values()), 6)
        if source not in candidate["source_mode"]:
            candidate["source_mode"].append(source)
        citation_ref = row.get("chunk_id") or row.get("segment_id")
        if citation_ref and not any((citation.get("chunk_id") or citation.get("segment_id")) == citation_ref for citation in candidate["citations"]):
            candidate["citations"].append(
                {
                    "item_id": item.item_id,
                    "version_id": version.version_id,
                    "chunk_id": row.get("chunk_id"),
                    "segment_id": row.get("segment_id"),
                    "title": item.title,
                    "snippet": _snippet(row.get("chunk_text") or version.body, query, max_length=snippet_length),
                }
            )
    async def _record_observer_event(self, event_type: str, *, actor_role: str, details: dict[str, Any]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO agent_runtime_audit (
                    device_id, event_type, severity, source, actor_role,
                    details_json, created_at
                )
                VALUES (
                    'server', :event_type, 'info', 'knowledge_retrieval',
                    :actor_role, CAST(:details_json AS jsonb), :created_at
                )
                """
            ),
            {
                "event_type": event_type,
                "actor_role": actor_role,
                "details_json": _json(details),
                "created_at": _now(),
            },
        )
