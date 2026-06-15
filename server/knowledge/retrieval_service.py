from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.contracts import AIModelProfile, AIProviderConfig
from ai.openrouter_client import OpenRouterClient
from app.db.models import KnowledgeAudienceRule, KnowledgeItem, KnowledgeItemVersion, KnowledgeSpace
from app.repos.knowledge_repo import serialize_item
from knowledge.access_service import KnowledgeAccessService
from knowledge.binding_surfaces import allowed_item_ids_for_binding_surface
from knowledge.contracts import actor_visible_visibilities, sanitize_requester_knowledge_projection
from knowledge.rag_policy import EXPLAIN_RAG_POLICY_ROLES, evaluate_rag_eligibility, safe_rag_trace_item
from knowledge.search_analytics_service import KnowledgeSearchAnalyticsService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from knowledge.vector_search_service import KnowledgeVectorSearchService


Transport = Callable[..., Awaitable[dict[str, Any]]]


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
    def __init__(self, session: AsyncSession, *, transport: Transport | None = None):
        self.session = session
        self.transport = transport

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
        effective_audience: Any | None = None,
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

        await self._filter_candidates_by_audience(
            candidates,
            effective_audience=effective_audience,
            service_context={
                "service_code": service_code,
                "offering_code": offering_code,
                "request_template_key": request_template_key,
            },
        )
        await self._filter_candidates_by_binding_surface(candidates, surface=surface)
        rag_policy_trace = await self._filter_candidates_by_rag_policy(candidates, actor_role=actor_role)
        ordered = sorted(candidates.values(), key=lambda item: (-float(item["score"]), str(item["item"].get("title") or "")))
        results = ordered[:max_results]
        rerank_used = False
        if bool(settings.get("rerank_enabled", False)) and len(results) > 1:
            reranked, rerank_fallback, rerank_used = await self._maybe_rerank(
                results,
                query=query_text,
                actor_role=actor_role,
                existing_fallback=vector_fallback,
            )
            results = reranked
            vector_fallback = rerank_fallback
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
                "rerank_used": rerank_used,
                "fallback_mode": vector_fallback,
                "rag_policy_excluded_count": rag_policy_trace["excluded_count"],
            },
        )
        payload = {
            "results": results,
            "search_mode": settings.get("search_mode"),
            "effective_mode": effective_mode,
            "fallback_mode": vector_fallback,
            "ai_used": bool(settings.get("ai_enabled")) and (vector_used or rerank_used),
            "settings": {
                "keyword_enabled": bool(settings.get("keyword_enabled", True)),
                "full_text_enabled": bool(settings.get("full_text_enabled", False)),
                "vector_enabled": bool(settings.get("vector_enabled", False)),
                "rerank_enabled": bool(settings.get("rerank_enabled", False)),
            },
        }
        if str(actor_role or "").lower() in EXPLAIN_RAG_POLICY_ROLES:
            payload["rag_policy"] = rag_policy_trace
        return payload

    async def _maybe_rerank(
        self,
        results: list[dict[str, Any]],
        *,
        query: str,
        actor_role: str,
        existing_fallback: str | None,
    ) -> tuple[list[dict[str, Any]], str | None, bool]:
        if not query:
            return results, existing_fallback or "rerank_query_missing", False
        profile = await self._get_ai_profile("rerank")
        provider = await self._get_provider(profile["provider_id"]) if profile else None
        if not profile or not provider or not await self._ai_task_allowed("rerank"):
            await self._record_observer_event(
                "knowledge.retrieval.rerank_failed_fallback",
                actor_role=actor_role,
                details={"reason": "rerank_not_configured", "result_count": len(results)},
            )
            return results, existing_fallback or "rerank_not_configured", False
        api_key = _resolve_secret_ref(provider.get("api_key_secret_ref"))
        if not api_key or self.transport is None:
            await self._record_observer_event(
                "knowledge.retrieval.rerank_failed_fallback",
                actor_role=actor_role,
                details={"reason": "rerank_provider_unavailable", "result_count": len(results)},
            )
            return results, existing_fallback or "rerank_provider_unavailable", False
        documents = [f"{item['item'].get('title') or ''}\n{item.get('snippet') or ''}".strip() for item in results]
        try:
            client = OpenRouterClient(
                AIProviderConfig(
                    provider_id=str(provider["provider_id"]),
                    code=str(provider["code"]),
                    base_url=str(provider.get("base_url") or "https://openrouter.ai/api/v1"),
                    api_key=api_key,
                ),
                transport=self.transport,
            )
            rerank_result = await client.rerank(
                AIModelProfile(
                    profile_id=str(profile["profile_id"]),
                    provider_id=str(profile["provider_id"]),
                    task_type="rerank",
                    model_name=str(profile["model_name"]),
                    timeout_ms=int(profile.get("timeout_ms") or 30_000),
                ),
                query=query,
                documents=documents,
            )
        except Exception:
            await self._record_observer_event(
                "knowledge.retrieval.rerank_failed_fallback",
                actor_role=actor_role,
                details={"reason": "rerank_request_failed", "result_count": len(results)},
            )
            return results, existing_fallback or "rerank_request_failed", False

        by_index: dict[int, float] = {}
        for item in rerank_result.results:
            try:
                index = int(item.get("index"))
                score = float(item.get("relevance_score", item.get("score", 0)))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(results):
                by_index[index] = score
        if not by_index:
            return results, existing_fallback or "rerank_empty_response", False

        reranked: list[dict[str, Any]] = []
        for index, item in enumerate(results):
            updated = dict(item)
            score_parts = dict(updated.get("score_parts") or {})
            if index in by_index:
                score_parts["rerank"] = by_index[index] * 100
                updated["source_mode"] = [*updated.get("source_mode", []), "rerank"] if "rerank" not in updated.get("source_mode", []) else updated.get("source_mode", [])
                updated["score_parts"] = score_parts
                updated["score"] = round(sum(float(value) for value in score_parts.values()), 6)
            reranked.append(updated)
        reranked.sort(key=lambda item: (-float((item.get("score_parts") or {}).get("rerank") or -1), -float(item.get("score") or 0)))
        await self._record_observer_event(
            "knowledge.retrieval.rerank_used",
            actor_role=actor_role,
            details={"result_count": len(reranked), "model_profile_id": profile["profile_id"]},
        )
        return reranked, existing_fallback, True

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

    async def _filter_candidates_by_audience(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        effective_audience: Any | None,
        service_context: dict[str, Any],
    ) -> None:
        if effective_audience is None or not candidates:
            return
        rows = (
            await self.session.execute(
                select(KnowledgeItem).where(KnowledgeItem.item_id.in_(sorted(candidates)))
            )
        ).scalars().all()
        access_context = await self._audience_access_context(
            rows=rows,
            effective_audience=effective_audience,
        )
        allowed_ids: set[str] = set()
        for item in rows:
            if self._item_allowed_by_audience(
                item,
                effective_audience=effective_audience,
                access_context=access_context,
                service_context=service_context,
            ):
                allowed_ids.add(item.item_id)
        for item_id in list(candidates):
            if item_id not in allowed_ids:
                candidates.pop(item_id, None)

    async def _filter_candidates_by_binding_surface(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        surface: str,
    ) -> None:
        if not candidates:
            return
        allowed_ids = await allowed_item_ids_for_binding_surface(
            self.session,
            set(candidates),
            surface=surface,
        )
        for item_id in list(candidates):
            if item_id not in allowed_ids:
                candidates.pop(item_id, None)

    async def _filter_candidates_by_rag_policy(
        self,
        candidates: dict[str, dict[str, Any]],
        *,
        actor_role: str,
    ) -> dict[str, Any]:
        trace = {
            "included_count": 0,
            "excluded_count": 0,
            "included": [],
            "excluded": [],
        }
        if not candidates:
            return trace
        rows = (
            await self.session.execute(
                select(KnowledgeItem, KnowledgeSpace)
                .join(KnowledgeSpace, KnowledgeSpace.space_id == KnowledgeItem.space_id)
                .where(KnowledgeItem.item_id.in_(sorted(candidates)))
            )
        ).all()
        item_space_by_id = {item.item_id: (item, space) for item, space in rows}
        for item_id in list(candidates):
            item_space = item_space_by_id.get(item_id)
            if item_space is None:
                candidates.pop(item_id, None)
                trace["excluded_count"] += 1
                trace["excluded"].append(
                    {
                        "item_id": item_id,
                        "included": False,
                        "reason_code": "knowledge_item_not_found",
                        "policy": "inherit",
                    }
                )
                continue
            item, space = item_space
            decision = evaluate_rag_eligibility(item, space, actor_role=actor_role)
            if decision.allowed:
                trace["included_count"] += 1
                trace["included"].append(safe_rag_trace_item(item, decision, included=True))
            else:
                candidates.pop(item_id, None)
                trace["excluded_count"] += 1
                trace["excluded"].append(safe_rag_trace_item(item, decision, included=False))
        return trace

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

    async def _get_ai_profile(self, task_type: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT *
                    FROM ai_model_profiles
                    WHERE task_type = :task_type
                      AND enabled = true
                    ORDER BY is_default DESC, created_at DESC, profile_id DESC
                    LIMIT 1
                    """
                ),
                {"task_type": task_type},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _get_provider(self, provider_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT *
                    FROM ai_providers
                    WHERE provider_id = :provider_id
                      AND enabled = true
                      AND provider_type = 'openrouter'
                    """
                ),
                {"provider_id": provider_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _ai_task_allowed(self, task_type: str) -> bool:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT policy_id
                    FROM ai_policy_profiles
                    WHERE enabled = true
                      AND ai_allowed = true
                      AND (:task_type <> 'rerank' OR rerank_allowed = true)
                      AND (task_type IS NULL OR task_type = :task_type)
                    ORDER BY updated_at DESC, policy_id DESC
                    LIMIT 1
                    """
                ),
                {"task_type": task_type},
            )
        ).first()
        return row is not None


def _resolve_secret_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if value.startswith("env:"):
        return os.getenv(value[4:])
    return None


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
