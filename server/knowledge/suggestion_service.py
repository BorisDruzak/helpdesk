from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.operations_service import KnowledgeOperationsService
from knowledge.search_service import KnowledgeSearchService


class KnowledgeSuggestionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def suggest(self, context: dict[str, Any], *, actor_role: str) -> dict[str, Any]:
        rollout = await KnowledgeOperationsService(self.session).rollout_decision(context, actor_role=actor_role)
        if rollout.get("enabled") is False:
            return {"suggestions": [], "known_errors": [], "workarounds": [], "rollout": rollout}
        max_suggestions = max(1, min(int(rollout.get("max_suggestions") or 5), int(context.get("limit") or 50), 50))
        query = str(context.get("query") or context.get("title") or context.get("description") or "").strip()
        results = await KnowledgeSearchService(self.session).search(
            query=query,
            actor_role=actor_role,
            service_code=context.get("service_code"),
            offering_code=context.get("offering_code"),
            request_template_key=context.get("request_template_key"),
            limit=max_suggestions,
        )
        if not results and (context.get("service_code") or context.get("offering_code") or context.get("request_template_key")):
            results = await KnowledgeSearchService(self.session).search(
                query=None,
                actor_role=actor_role,
                service_code=context.get("service_code"),
                offering_code=context.get("offering_code"),
                request_template_key=context.get("request_template_key"),
                limit=max_suggestions,
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
            suggestions.append(item)
        return {
            "suggestions": suggestions[:max_suggestions],
            "known_errors": [item for item in suggestions if item.get("type") == "known_error"] if rollout.get("show_known_errors", True) else [],
            "workarounds": [item for item in suggestions if item.get("type") == "workaround"],
            "rollout": rollout,
        }
