from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.operations_service import KnowledgeOperationsService
from knowledge.search_service import KnowledgeSearchService


class KnowledgeSuggestionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def suggest(
        self,
        context: dict[str, Any],
        *,
        actor_role: str,
        effective_audience: Any | None = None,
    ) -> dict[str, Any]:
        rollout = await KnowledgeOperationsService(self.session).rollout_decision(context, actor_role=actor_role)
        if rollout.get("enabled") is False:
            return {"suggestions": [], "known_errors": [], "workarounds": [], "rollout": rollout}
        rollout_max = int(rollout.get("max_suggestions") if rollout.get("max_suggestions") is not None else 5)
        context_limit = int(context.get("limit") if context.get("limit") is not None else 50)
        max_suggestions = max(0, min(rollout_max, context_limit, 50))
        if max_suggestions == 0:
            return {"suggestions": [], "known_errors": [], "workarounds": [], "rollout": rollout}
        query = str(context.get("query") or context.get("title") or context.get("description") or "").strip()
        results = await KnowledgeSearchService(self.session).search(
            query=query,
            actor_role=actor_role,
            service_code=context.get("service_code"),
            offering_code=context.get("offering_code"),
            request_template_key=context.get("request_template_key"),
            surface=str(context.get("surface") or context.get("source_surface") or "suggest"),
            limit=max_suggestions,
            effective_audience=effective_audience,
        )
        if not results and (context.get("service_code") or context.get("offering_code") or context.get("request_template_key")):
            results = await KnowledgeSearchService(self.session).search(
                query=None,
                actor_role=actor_role,
                service_code=context.get("service_code"),
                offering_code=context.get("offering_code"),
                request_template_key=context.get("request_template_key"),
                surface=str(context.get("surface") or context.get("source_surface") or "suggest"),
                limit=max_suggestions,
                effective_audience=effective_audience,
            )
        suggestions: list[dict[str, Any]] = []
        for result in results:
            reason_parts: list[str] = []
            if context.get("service_code"):
                reason_parts.append(f"service={context.get('service_code')}")
            if context.get("offering_code"):
                reason_parts.append(f"offering={context.get('offering_code')}")
            item = dict(result)
            item["reason"] = "Подходит по контексту: " + ", ".join(reason_parts) if reason_parts else "Подходит по тексту обращения"
            item["actions"] = ["view", "mark_helpful", "mark_not_helpful"]
            if not rollout.get("show_quality_badge", True):
                item.pop("quality_label", None)
            if not rollout.get("show_review_freshness", True):
                item.pop("freshness_label", None)
            suggestions.append(item)
        if not rollout.get("show_known_errors", True):
            suggestions = [item for item in suggestions if item.get("type") != "known_error"]
        return {
            "suggestions": suggestions[:max_suggestions],
            "known_errors": [item for item in suggestions if item.get("type") == "known_error"],
            "workarounds": [item for item in suggestions if item.get("type") == "workaround"],
            "rollout": rollout,
        }
