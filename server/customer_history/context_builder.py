from __future__ import annotations

from typing import Any

from domain_ports.registry import RegistryPort
from domain_ports.registry_contracts import RegistryReadActor

from .projection_service import CustomerHistoryProjectionService, ticket_history_person_ids


def _context_event_dedup_key(event: dict[str, Any]) -> tuple[str | None, str, str, str, str, str, str]:
    """Keep opaque Registry event identity through the LLM-safe context dedup.

    ``device_ref`` is intentionally short and can collide; ``event_ref`` is
    the stable opaque Registry digest.  Including both preserves the safe
    device hint while ensuring that two same-time events are not collapsed
    merely because their display-safe device prefixes match.
    """

    refs = event.get("refs")
    safe_refs = refs if isinstance(refs, dict) else {}
    return (
        event.get("ticket_ref"),
        str(event.get("source") or ""),
        str(event.get("event_type") or ""),
        str(event.get("occurred_at") or ""),
        str(event.get("summary") or ""),
        str(safe_refs.get("device_ref") or ""),
        str(safe_refs.get("event_ref") or ""),
    )


class CustomerHistoryContextBuilder:
    def __init__(self, session, *, registry_port: RegistryPort | None = None):
        self.session = session
        self.registry_port = registry_port

    async def build_ticket_context_pack(
        self,
        ticket_id: str,
        *,
        actor_context: dict[str, Any] | None = None,
        mode: str = "llm_preview",
        limit: int = 20,
        registry_actor: RegistryReadActor | None = None,
    ) -> dict[str, Any]:
        service = CustomerHistoryProjectionService(self.session, registry_port=self.registry_port)
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
            seen = {_context_event_dedup_key(event) for event in events if isinstance(event, dict)}
            for person_id in ticket_history_person_ids(ticket):
                related = await service.history_for_person(
                    person_id,
                    actor_context=actor_context,
                    registry_actor=registry_actor,
                    limit=bounded_limit,
                    role="llm",
                )
                sources.update(related.get("sources", []))
                removed_count += int((related.get("redaction_report") or {}).get("removed_count") or 0)
                for event in related.get("events", []):
                    if event.get("ticket_ref") == current_ref:
                        continue
                    key = _context_event_dedup_key(event)
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
        registry_actor: RegistryReadActor | None = None,
    ) -> dict[str, Any]:
        filter_map = filters or {}
        limit = int(filter_map.get("limit") or 50)
        return await CustomerHistoryProjectionService(
            self.session,
            registry_port=self.registry_port,
        ).history_for_person(
            person_id,
            actor_context=actor_context,
            registry_actor=registry_actor,
            limit=limit,
            since=filter_map.get("since"),
            window_days=filter_map.get("window_days"),
        )

    async def build_requester_history(
        self,
        actor_context: dict[str, Any],
        *,
        registry_actor: RegistryReadActor | None = None,
    ) -> dict[str, Any]:
        person_id = str(actor_context.get("person_id") or "").strip()
        if not person_id:
            return {"events": [], "count": 0, "redaction_report": {"removed_count": 0, "role": "requester"}}
        return await self.build_person_history(
            person_id,
            actor_context=actor_context,
            registry_actor=registry_actor,
        )
