from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRuntimeAudit,
    HelpdeskServiceOffering,
    KnowledgeBinding,
    KnowledgeIndexJob,
    KnowledgeItem,
    KnowledgeNode,
    KnowledgeReviewTask,
    KnowledgeSearchEvent,
    KnowledgeSpace,
    ObserverIntegrityEvent,
)
from knowledge.contracts import actor_visible_visibilities
from knowledge.embedding_service import KnowledgeEmbeddingService
from knowledge.operations_service import KnowledgeOperationsService


REQUESTER_SAFE_VISIBILITIES = {"public", "requester", "agent_requester_safe"}
OPEN_REVIEW_STATUSES = {"open", "assigned", "in_progress"}


def _metric(total: int | float, **extra: Any) -> dict[str, Any]:
    return {"total": total, **extra}


def _metadata(row: Any) -> dict[str, Any]:
    value = getattr(row, "metadata_json", None)
    return value if isinstance(value, dict) else {}


def _is_truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes", "on"}


class KnowledgeOpsSummaryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self, *, actor_role: str = "admin") -> dict[str, Any]:
        allowed = set(actor_visible_visibilities(actor_role))
        quality = await KnowledgeOperationsService(self.session).quality_summary(actor_role=actor_role)
        indexing = await KnowledgeEmbeddingService(self.session).status()
        coverage = await self._coverage(allowed)
        search = await self._search()
        rag = await self._rag()
        observer = await self._observer()
        review = await self._review()
        graph = await self._graph()
        ai = await self._ai(observer)
        status = self._status(indexing=indexing, observer=observer, search=search, quality=quality)

        return {
            "status": status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "coverage": coverage,
            "quality": self._quality(quality),
            "search": search,
            "rag": rag,
            "indexing": {
                "queued": _metric(int(indexing.get("jobs", {}).get("queued", 0))),
                "failed": _metric(int(indexing.get("jobs", {}).get("failed", 0))),
                "stale_embeddings": _metric(int(indexing.get("embeddings", {}).get("stale", 0))),
                "disabled": _metric(int(indexing.get("embeddings", {}).get("disabled", 0))),
                "vector_enabled": bool(indexing.get("vector_enabled")),
                "embedding_model": indexing.get("embedding_model"),
            },
            "ai": ai,
            "graph": graph,
            "review": review,
            "observer": observer,
        }

    async def _count(self, model: Any, *criteria: Any) -> int:
        stmt = select(func.count()).select_from(model)
        for criterion in criteria:
            stmt = stmt.where(criterion)
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def _coverage(self, allowed: set[str]) -> dict[str, Any]:
        published_criteria = (KnowledgeItem.status == "published", KnowledgeItem.visibility.in_(allowed))
        requester_bindings = (
            await self.session.execute(
                select(KnowledgeBinding.service_code, KnowledgeBinding.offering_code)
                .join(KnowledgeItem, KnowledgeItem.item_id == KnowledgeBinding.item_id)
                .where(
                    KnowledgeItem.status == "published",
                    KnowledgeItem.visibility.in_(REQUESTER_SAFE_VISIBILITIES),
                )
            )
        ).all()
        covered_offerings = {(row.service_code, row.offering_code) for row in requester_bindings if row.offering_code}
        offerings = (
            await self.session.execute(
                select(HelpdeskServiceOffering.full_code, HelpdeskServiceOffering.service_id).where(
                    HelpdeskServiceOffering.lifecycle_status == "published"
                )
            )
        ).all()
        services_without_kb = 0
        for offering in offerings:
            if not any(offering.full_code == code or offering.full_code == pair[1] for pair in covered_offerings for code in pair if code):
                services_without_kb += 1
        return {
            "spaces": _metric(await self._count(KnowledgeSpace)),
            "published_articles": _metric(await self._count(KnowledgeItem, *published_criteria, KnowledgeItem.item_type == "article")),
            "requester_safe": _metric(
                await self._count(
                    KnowledgeItem,
                    KnowledgeItem.status == "published",
                    KnowledgeItem.visibility.in_(REQUESTER_SAFE_VISIBILITIES),
                )
            ),
            "support_runbooks": _metric(
                await self._count(
                    KnowledgeItem,
                    KnowledgeItem.status == "published",
                    KnowledgeItem.visibility.in_(allowed),
                    KnowledgeItem.item_type == "runbook",
                )
            ),
            "services_without_kb": _metric(services_without_kb),
        }

    def _quality(self, quality: dict[str, Any]) -> dict[str, Any]:
        items = quality.get("items") if isinstance(quality.get("items"), list) else []
        stale_review = 0
        missing_owner_reviewer = 0
        unsafe_requester_safe = 0
        for item in items:
            issues = set(item.get("issues") or [])
            if "review_overdue" in issues:
                stale_review += 1
            if {"missing_owner", "missing_reviewer"} & issues:
                missing_owner_reviewer += 1
            if str(item.get("visibility")) in REQUESTER_SAFE_VISIBILITIES and any("unsafe" in issue for issue in issues):
                unsafe_requester_safe += 1
        return {
            "average_score": round(float(quality.get("average_quality_score") or 0), 1),
            "low_quality_count": _metric(int(quality.get("low_quality_count") or 0)),
            "stale_review_count": _metric(stale_review),
            "missing_owner_reviewer_count": _metric(missing_owner_reviewer),
            "unsafe_requester_safe_blockers": _metric(unsafe_requester_safe),
        }

    async def _search(self) -> dict[str, Any]:
        rows = (await self.session.execute(select(KnowledgeSearchEvent))).scalars().all()
        zero_result = 0
        fallback_count = 0
        ai_disabled = 0
        vector_usage = 0
        rerank_usage = 0
        query_counts: dict[str, int] = {}
        for row in rows:
            metadata = _metadata(row)
            if int(row.result_count or 0) == 0:
                zero_result += 1
            if metadata.get("fallback_mode") or _is_truthy(metadata.get("fallback")):
                fallback_count += 1
            if _is_truthy(metadata.get("ai_disabled")) or metadata.get("ai_status") == "disabled":
                ai_disabled += 1
            if _is_truthy(metadata.get("vector_used")) or metadata.get("retrieval_mode") == "vector":
                vector_usage += 1
            if _is_truthy(metadata.get("rerank_used")):
                rerank_usage += 1
            query = str(row.query_text_redacted or "").strip()
            if query:
                query_counts[query] = query_counts.get(query, 0) + 1
        top_queries = [{"query": query, "count": count} for query, count in sorted(query_counts.items(), key=lambda item: (-item[1], item[0]))[:5]]
        return {
            "zero_result_searches": _metric(zero_result),
            "top_queries": top_queries,
            "fallback_count": _metric(fallback_count),
            "ai_disabled_count": _metric(ai_disabled),
            "vector_usage_count": _metric(vector_usage),
            "rerank_usage_count": _metric(rerank_usage),
        }

    async def _rag(self) -> dict[str, Any]:
        audit_rows = (
            await self.session.execute(
                select(AgentRuntimeAudit.event_type).where(AgentRuntimeAudit.event_type.like("knowledge.rag.%"))
            )
        ).scalars().all()
        search_rows = (await self.session.execute(select(KnowledgeSearchEvent))).scalars().all()
        no_answer_from_search = sum(1 for row in search_rows if _is_truthy(_metadata(row).get("rag_no_answer")))
        return {
            "answer_count": _metric(sum(1 for event_type in audit_rows if event_type == "knowledge.rag.answer_generated")),
            "no_answer_count": _metric(no_answer_from_search + sum(1 for event_type in audit_rows if event_type == "knowledge.rag.no_answer")),
            "provider_failures": _metric(sum(1 for event_type in audit_rows if "provider" in str(event_type) and "failed" in str(event_type))),
            "citation_validation_failures": _metric(sum(1 for event_type in audit_rows if "citation" in str(event_type) and "failed" in str(event_type))),
        }

    async def _ai(self, observer: dict[str, Any]) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(AgentRuntimeAudit.event_type).where(AgentRuntimeAudit.event_type.like("knowledge.ai.%"))
            )
        ).scalars().all()
        failed = sum(1 for event_type in rows if str(event_type).endswith("failed"))
        ok = sum(1 for event_type in rows if str(event_type).endswith("ok"))
        observer_failed = sum(1 for item in observer["degradations"] if str(item["code"]).startswith("knowledge.ai."))
        return {
            "provider_health": {"status": "degraded" if failed or observer_failed else "ok", "failed_count": failed + observer_failed, "ok_count": ok},
            "model_profile_status": {"active_count": 0, "disabled_count": 0},
            "policy_blocks": _metric(
                await self._count(AgentRuntimeAudit, AgentRuntimeAudit.event_type.in_(("knowledge.rag.policy_blocked", "knowledge.embedding.policy_blocked")))
            ),
        }

    async def _graph(self) -> dict[str, Any]:
        proposed_nodes = await self._count(KnowledgeNode, KnowledgeNode.status == "proposed")
        contradiction_edges = 0
        try:
            from app.db.models import KnowledgeEdge

            contradiction_edges = await self._count(KnowledgeEdge, KnowledgeEdge.relation_type.in_(("contradicts", "duplicates")), KnowledgeEdge.status != "archived")
        except Exception:
            contradiction_edges = 0
        return {
            "orphan_nodes": _metric(await self._count(KnowledgeNode, KnowledgeNode.status != "archived", KnowledgeNode.linked_item_id.is_(None))),
            "pending_proposals": _metric(proposed_nodes),
            "contradiction_duplicate_findings": _metric(contradiction_edges),
        }

    async def _review(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "assigned_open": _metric(
                await self._count(
                    KnowledgeReviewTask,
                    KnowledgeReviewTask.status.in_(OPEN_REVIEW_STATUSES),
                    KnowledgeReviewTask.assigned_to_actor_id.is_not(None),
                )
            ),
            "overdue": _metric(
                await self._count(
                    KnowledgeReviewTask,
                    KnowledgeReviewTask.status.in_(OPEN_REVIEW_STATUSES),
                    KnowledgeReviewTask.due_at.is_not(None),
                    KnowledgeReviewTask.due_at <= now,
                )
            ),
        }

    async def _observer(self) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                select(
                    ObserverIntegrityEvent.event_type,
                    ObserverIntegrityEvent.severity,
                    ObserverIntegrityEvent.source,
                    ObserverIntegrityEvent.status,
                    ObserverIntegrityEvent.actual,
                    func.count(ObserverIntegrityEvent.event_id),
                )
                .where(
                    ObserverIntegrityEvent.status == "active",
                    or_(ObserverIntegrityEvent.source.like("knowledge%"), ObserverIntegrityEvent.event_type.like("knowledge.%")),
                )
                .group_by(
                    ObserverIntegrityEvent.event_type,
                    ObserverIntegrityEvent.severity,
                    ObserverIntegrityEvent.source,
                    ObserverIntegrityEvent.status,
                    ObserverIntegrityEvent.actual,
                )
                .order_by(func.count(ObserverIntegrityEvent.event_id).desc())
            )
        ).all()
        return {
            "degradations": [
                {
                    "code": str(event_type),
                    "severity": str(severity),
                    "source": str(source),
                    "count": int(count),
                    "status": str(status),
                    "message": str(actual or event_type),
                }
                for event_type, severity, source, status, actual, count in rows
            ]
        }

    def _status(self, *, indexing: dict[str, Any], observer: dict[str, Any], search: dict[str, Any], quality: dict[str, Any]) -> str:
        if observer["degradations"]:
            return "degraded"
        if int(indexing.get("jobs", {}).get("failed", 0)) > 0:
            return "degraded"
        if int(search["zero_result_searches"]["total"]) >= 10:
            return "degraded"
        if float(quality.get("average_quality_score") or 100) < 50:
            return "degraded"
        return "ok"
