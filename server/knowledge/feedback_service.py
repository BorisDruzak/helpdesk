from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeFeedbackEvent, Ticket
from knowledge.contracts import KNOWLEDGE_FEEDBACK_EVENT_TYPES, KnowledgeValidationError


def _new_id() -> str:
    return str(uuid.uuid4())


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _serialize_event(row: KnowledgeFeedbackEvent) -> dict[str, Any]:
    return {
        "event_id": row.event_id,
        "item_id": row.item_id,
        "version_id": row.version_id,
        "chunk_id": row.chunk_id,
        "actor_id": row.actor_id,
        "actor_role": row.actor_role,
        "session_id": row.session_id,
        "ticket_id": row.ticket_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "request_template_key": row.request_template_key,
        "source_surface": row.source_surface,
        "event_type": row.event_type,
        "result": row.result,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata": row.metadata_json or {},
    }


class KnowledgeFeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_event(
        self,
        payload: dict[str, Any],
        *,
        actor_role: str | None,
        actor_id: str | None,
    ) -> dict[str, Any]:
        event_type = str(payload.get("event_type") or "").strip()
        if event_type not in KNOWLEDGE_FEEDBACK_EVENT_TYPES:
            raise KnowledgeValidationError(f"unsupported knowledge feedback event_type: {event_type}")
        ticket_id = _text(payload.get("ticket_id"))
        if ticket_id:
            exists = (await self.session.execute(select(Ticket.ticket_id).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
            if not exists:
                ticket_id = None
        row = KnowledgeFeedbackEvent(
            event_id=str(payload.get("event_id") or _new_id()),
            item_id=_text(payload.get("item_id")),
            version_id=_text(payload.get("version_id")),
            chunk_id=_text(payload.get("chunk_id")),
            actor_id=actor_id,
            actor_role=_text(actor_role),
            session_id=_text(payload.get("session_id")),
            ticket_id=ticket_id,
            service_code=_text(payload.get("service_code")),
            offering_code=_text(payload.get("offering_code")),
            request_template_key=_text(payload.get("request_template_key")),
            source_surface=_text(payload.get("source_surface") or payload.get("surface")) or "api",
            event_type=event_type,
            result=_text(payload.get("result")),
            metadata_json=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
        self.session.add(row)
        await self.session.flush()
        return _serialize_event(row)
