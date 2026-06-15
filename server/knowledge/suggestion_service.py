from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.operations_service import KnowledgeOperationsService
from knowledge.search_service import KnowledgeSearchService


_RAW_CONTEXT_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "cookie",
    "session",
)

_RAW_CONTEXT_KEYS = {
    "id",
    "person_id",
    "device_id",
    "asset_id",
    "binding_id",
    "claim_id",
    "account_session_id",
    "requester_account_session_id",
    "service_id",
    "location_id",
    "department_id",
    "audience_group_id",
    "manager_person_id",
    "responsible_person_id",
    "request_template_key",
    "offering_code",
    "service_code",
    "schema",
    "source",
    "email",
    "phone",
}


def _is_raw_context_key(key: str) -> bool:
    normalized = str(key or "").strip().lower()
    if not normalized:
        return False
    if normalized in _RAW_CONTEXT_KEYS or normalized.endswith("_id"):
        return True
    return any(part in normalized for part in _RAW_CONTEXT_KEY_PARTS)


def _append_query_candidate(candidates: list[str], seen: set[str], value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        return
    text = str(value).strip()
    if not text or len(text) > 240:
        return
    normalized = " ".join(text.split())
    marker = normalized.lower()
    if marker and marker not in seen:
        candidates.append(normalized)
        seen.add(marker)


def _collect_safe_context_values(value: Any, *, key: str = "") -> list[str]:
    if _is_raw_context_key(key):
        return []
    if isinstance(value, dict):
        collected: list[str] = []
        for child_key, child_value in value.items():
            collected.extend(_collect_safe_context_values(child_value, key=str(child_key)))
        return collected
    if isinstance(value, list):
        collected = []
        for item in value:
            collected.extend(_collect_safe_context_values(item, key=key))
        return collected
    if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
        return []
    text = str(value).strip()
    return [text] if text else []


def _candidate_queries(context: dict[str, Any]) -> list[str | None]:
    candidates: list[str] = []
    seen: set[str] = set()
    for key in ("query", "title", "description"):
        _append_query_candidate(candidates, seen, context.get(key))
    for key in ("form_payload", "requester_context", "device_metadata"):
        for value in _collect_safe_context_values(context.get(key), key=key):
            _append_query_candidate(candidates, seen, value)
    return candidates or [None]


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
        search_service = KnowledgeSearchService(self.session)
        results: list[dict[str, Any]] = []
        seen_result_ids: set[str] = set()
        surface = str(context.get("surface") or context.get("source_surface") or "suggest")
        for query in _candidate_queries(context):
            query_results = await search_service.search(
                query=query,
                actor_role=actor_role,
                service_code=context.get("service_code"),
                offering_code=context.get("offering_code"),
                request_template_key=context.get("request_template_key"),
                surface=surface,
                limit=max_suggestions,
                effective_audience=effective_audience,
            )
            for item in query_results:
                item_id = str(item.get("item_id") or item.get("slug") or "")
                if item_id and item_id not in seen_result_ids:
                    results.append(item)
                    seen_result_ids.add(item_id)
            if len(results) >= max_suggestions:
                break
        if not results and (context.get("service_code") or context.get("offering_code") or context.get("request_template_key")):
            results = await search_service.search(
                query=None,
                actor_role=actor_role,
                service_code=context.get("service_code"),
                offering_code=context.get("offering_code"),
                request_template_key=context.get("request_template_key"),
                surface=surface,
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
