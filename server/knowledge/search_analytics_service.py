from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import hashlib
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeSearchEvent


def _new_id() -> str:
    return str(uuid.uuid4())


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
SENSITIVE_MARKER_KEY_RE = (
    r"(?:"
    r"device_id|requester_id|person_id|manager_person_id|responsible_person_id|"
    r"account_session_id|requester_account_session_id|session_id|ticket_id|"
    r"queue_id|trace_id|operation_id|request_id|access_code|public_access_code|"
    r"session_token|api_key|password|secret|token|email|phone|"
    r"[\w.-]*(?:token|secret|password|cookie)[\w.-]*"
    r")"
)
MARKER_RE = re.compile(
    rf"\b(?P<key>{SENSITIVE_MARKER_KEY_RE})\s*=\s*(?P<value>\+?\d[\d\s().-]{{6,}}\d|[\w.@:+/-]+)",
    re.IGNORECASE,
)
ALLOWED_SURFACES = {"requester_portal", "agent_gui", "support_workspace", "admin", "api", "search"}


def redact_search_query(query_text: str | None) -> str | None:
    text = str(query_text or "").strip()
    if not text:
        return None
    text = EMAIL_RE.sub("[redacted-email]", text)
    text = MARKER_RE.sub(lambda match: match.group("key").strip() + "=[redacted]", text)
    text = PHONE_RE.sub("[redacted-phone]", text)
    return text[:240]


def hash_search_query(query_text: str | None) -> str:
    normalized = " ".join(str(query_text or "").casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class KnowledgeSearchAnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_search_event(
        self,
        *,
        actor_role: str | None,
        surface: str,
        query_text: str | None,
        result_count: int,
        service_code: str | None = None,
        offering_code: str | None = None,
        session_id: str | None = None,
        clicked_item_id: str | None = None,
        created_ticket_after_search: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_surface = surface if surface in ALLOWED_SURFACES else "search"
        row = KnowledgeSearchEvent(
            event_id=_new_id(),
            actor_role=actor_role,
            session_id=session_id,
            surface=normalized_surface,
            query_text_hash=hash_search_query(query_text),
            query_text_redacted=redact_search_query(query_text),
            service_code=service_code,
            offering_code=offering_code,
            result_count=max(0, int(result_count or 0)),
            clicked_item_id=clicked_item_id,
            created_ticket_after_search=bool(created_ticket_after_search),
            created_at=datetime.now(timezone.utc),
            metadata_json=metadata or {},
        )
        self.session.add(row)
        await self.session.flush()
        return {
            "event_id": row.event_id,
            "actor_role": row.actor_role,
            "surface": row.surface,
            "query_text_hash": row.query_text_hash,
            "query_text_redacted": row.query_text_redacted,
            "service_code": row.service_code,
            "offering_code": row.offering_code,
            "result_count": row.result_count,
            "created_ticket_after_search": row.created_ticket_after_search,
            "created_at": row.created_at.isoformat(),
        }
