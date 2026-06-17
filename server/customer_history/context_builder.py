from __future__ import annotations

from typing import Any

from .projection_service import CustomerHistoryProjectionService, ticket_history_person_ids


class CustomerHistoryContextBuilder:
    def __init__(self, session):
        self.session = session

    async def build_ticket_context_pack(
        self,
        ticket_id: str,
        *,
        actor_context: dict[str, Any] | None = None,
        mode: str = "llm_preview",
        limit: int = 20,
    ) -> dict[str, Any]:
        service = CustomerHistoryProjectionService(self.session)
        bounded_limit = max(1, min(int(limit or 20), 100))
        history = await service.history_for_ticket(
            ticket_id,
            actor_context=actor_context,
            limit=bounded_limit,
            role="llm",
        )
        events = list(history.get("events", []))
        sources = set(history.get("sources", []))
        removed_count = int((history.get("redaction_report") or {}).get("removed_count") or 0)
        ticket = await service._ticket(ticket_id)
        if ticket is not None and len(events) < bounded_limit:
            current_ref = history.get("ticket_ref")
            seen = {
                (
                    event.get("ticket_ref"),
                    event.get("source"),
                    event.get("event_type"),
                    event.get("occurred_at"),
                    str(event.get("summary")),
                )
                for event in events
                if isinstance(event, dict)
            }
            for person_id in ticket_history_person_ids(ticket):
                related = await service.history_for_person(
                    person_id,
                    actor_context=actor_context,
                    limit=bounded_limit,
                    role="llm",
                )
                sources.update(related.get("sources", []))
                removed_count += int((related.get("redaction_report") or {}).get("removed_count") or 0)
                for event in related.get("events", []):
                    if event.get("ticket_ref") == current_ref:
                        continue
                    key = (
                        event.get("ticket_ref"),
                        event.get("source"),
                        event.get("event_type"),
                        event.get("occurred_at"),
                        str(event.get("summary")),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    events.append(event)
                    if len(events) >= bounded_limit:
                        break
                if len(events) >= bounded_limit:
                    break
        return {
            "mode": mode,
            "preview_only": True,
            "llm_api_called": False,
            "ticket_ref": history.get("ticket_ref"),
            "events": events[:bounded_limit],
            "redaction_report": {"removed_count": removed_count, "role": "llm"},
            "sources": sorted(sources),
        }

    async def build_person_history(
        self,
        person_id: str,
        *,
        actor_context: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        filter_map = filters or {}
        limit = int(filter_map.get("limit") or 50)
        return await CustomerHistoryProjectionService(self.session).history_for_person(
            person_id,
            actor_context=actor_context,
            limit=limit,
            since=filter_map.get("since"),
            window_days=filter_map.get("window_days"),
        )

    async def build_requester_history(self, actor_context: dict[str, Any]) -> dict[str, Any]:
        person_id = str(actor_context.get("person_id") or "").strip()
        if not person_id:
            return {"events": [], "count": 0, "redaction_report": {"removed_count": 0, "role": "requester"}}
        return await self.build_person_history(person_id, actor_context=actor_context)
