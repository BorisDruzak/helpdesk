from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import or_, select

from app.db.models import Ticket
from domain_ports.container import DomainPortContainer
from domain_ports.knowledge import KnowledgePort, KnowledgeSuggestionRequest


_LEGACY_ATTEMPT_RESULTS = {
    "suggested",
    "viewed",
    "helpful",
    "not_helpful",
    "deflected",
    "skipped",
    "ticket_created_after_view",
}
_LEGACY_ATTEMPT_SURFACES = {"requester_portal", "agent_gui", "support_workspace"}
_LEGACY_VISIBILITY_SCOPES = {"creator_visible", "support_only"}
_LEGACY_AUDIENCE_SCOPES = {"creator", "affected_context", "support"}
_MAX_LEGACY_ATTEMPTS = 20


@dataclass(frozen=True)
class KnowledgeArticleSuggestion:
    """External Knowledge projection; Helpdesk never owns article content."""

    id: str
    title: str
    url: str | None = None
    source_type: str = field(default="external_knowledge", compare=False)
    score: int | None = field(default=None, compare=False)
    match_reasons: list[str] = field(default_factory=list, compare=False)


@dataclass(frozen=True)
class KnowledgeSimilarTicketSuggestion:
    id: str
    number: str | None
    subject: str
    resolution_summary: str | None = None
    source_type: str = field(default="similar_ticket", compare=False)
    score: int | None = field(default=None, compare=False)
    match_reasons: list[str] = field(default_factory=list, compare=False)


@dataclass(frozen=True)
class KnowledgeAiSuggestion:
    text: str | None
    sources: list[str]
    confidence: str = "none"
    source_count: int = 0


@dataclass(frozen=True)
class KnowledgeDiagnostics:
    provider: str = "external_knowledge_port"
    provider_version: str = "v1"
    provider_status: str = "ok"
    external_provider_status: str = "not_configured"
    fallback_reason: str | None = None
    catalog_entry_count: int = 0
    query_tokens: list[str] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    query_signals: list[str] = field(default_factory=list)
    article_matches: dict[str, dict[str, Any]] = field(default_factory=dict)
    similar_ticket_matches: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeSuggestions:
    articles: list[KnowledgeArticleSuggestion]
    similar_tickets: list[KnowledgeSimilarTicketSuggestion]
    ai_summary: KnowledgeAiSuggestion
    diagnostics: KnowledgeDiagnostics = field(default_factory=KnowledgeDiagnostics)


def clean_knowledge_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def project_legacy_knowledge_attempts(raw_attempts: Any) -> list[dict[str, str]]:
    """Project pre-existing attempt JSON without retaining Knowledge identifiers or content."""

    if not isinstance(raw_attempts, list):
        return []
    projected: list[dict[str, str]] = []
    for raw in raw_attempts[:_MAX_LEGACY_ATTEMPTS]:
        if not isinstance(raw, dict):
            continue
        result = raw.get("result")
        surface = raw.get("surface")
        visibility_scope = raw.get("visibility_scope")
        audience_scope = raw.get("audience_scope")
        occurred_at = raw.get("occurred_at")
        if (
            result not in _LEGACY_ATTEMPT_RESULTS
            or surface not in _LEGACY_ATTEMPT_SURFACES
            or visibility_scope not in _LEGACY_VISIBILITY_SCOPES
            or audience_scope not in _LEGACY_AUDIENCE_SCOPES
            or not isinstance(occurred_at, str)
            or not occurred_at
            or len(occurred_at) > 64
        ):
            continue
        projected.append(
            {
                "result": result,
                "surface": surface,
                "visibility_scope": visibility_scope,
                "audience_scope": audience_scope,
                "occurred_at": occurred_at,
            }
        )
    return projected


def _ticket_number(ticket: Ticket) -> str | None:
    return clean_knowledge_text(getattr(ticket, "ticket_code", None)) or clean_knowledge_text(
        getattr(ticket, "ticket_id", None)
    )


def _similar_ticket_suggestion(
    row: Ticket,
    match_metadata: dict[str, tuple[int, list[str]]],
) -> KnowledgeSimilarTicketSuggestion:
    metadata = match_metadata.get(str(row.ticket_id), (60, ["similar_ticket"]))
    return KnowledgeSimilarTicketSuggestion(
        id=str(row.ticket_id),
        number=_ticket_number(row),
        subject=clean_knowledge_text(getattr(row, "title", None)) or "Untitled",
        resolution_summary=clean_knowledge_text(getattr(row, "requester_resolution_summary", None))
        or clean_knowledge_text(getattr(row, "resolution_summary", None)),
        score=metadata[0],
        match_reasons=metadata[1],
    )


async def load_similar_knowledge_tickets(
    session: Any,
    ticket: Ticket,
    limit: int = 3,
) -> list[KnowledgeSimilarTicketSuggestion]:
    """Keep Helpdesk-owned similar-ticket retrieval independent of Knowledge."""

    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    custom_fields = getattr(ticket, "custom_fields", None)
    raw_similar = custom_fields.get("similar_tickets") if isinstance(custom_fields, dict) else None
    identifiers: list[str] = []
    if isinstance(raw_similar, list):
        for item in raw_similar:
            if isinstance(item, dict):
                value = item.get("ticket_id") or item.get("id") or item.get("ticket_code") or item.get("number")
            else:
                value = item
            text = clean_knowledge_text(value)
            if text and text not in identifiers and text != ticket_id:
                identifiers.append(text)

    similar_rows: list[Ticket] = []
    match_metadata: dict[str, tuple[int, list[str]]] = {}
    if identifiers:
        result = await session.execute(
            select(Ticket).where(
                Ticket.ticket_id != ticket_id,
                or_(Ticket.ticket_id.in_(identifiers), Ticket.ticket_code.in_(identifiers)),
            )
        )
        by_key: dict[str, Ticket] = {}
        for row in result.scalars().all():
            by_key[str(row.ticket_id)] = row
            by_key[str(row.ticket_code)] = row
        for identifier in identifiers:
            row = by_key.get(identifier)
            if row is not None and row not in similar_rows:
                similar_rows.append(row)
                match_metadata[str(row.ticket_id)] = (90, ["linked_ticket"])
            if len(similar_rows) >= limit:
                break

    if len(similar_rows) < limit:
        filters = [Ticket.ticket_id != ticket_id, Ticket.status.in_(["resolved", "closed"])]
        fallback_reasons: list[str] = []
        category_id = getattr(ticket, "category_id", None)
        service_id = getattr(ticket, "service_id", None)
        if category_id is not None:
            filters.append(Ticket.category_id == category_id)
            fallback_reasons.append("same_category")
        elif service_id is not None:
            filters.append(Ticket.service_id == service_id)
            fallback_reasons.append("same_service")
        else:
            filters.append(Ticket.title.ilike(f"%{(getattr(ticket, 'title', '') or '')[:24]}%"))
            fallback_reasons.append("title_similarity")
        result = await session.execute(
            select(Ticket).where(*filters).order_by(Ticket.updated_at.desc()).limit(limit * 2)
        )
        for row in result.scalars().all():
            if row not in similar_rows:
                similar_rows.append(row)
                match_metadata.setdefault(str(row.ticket_id), (70, list(fallback_reasons)))
            if len(similar_rows) >= limit:
                break

    return [_similar_ticket_suggestion(row, match_metadata) for row in similar_rows[:limit]]


async def build_knowledge_suggestions(
    session: Any,
    ticket: Ticket,
    kb_links: Iterable[Any],
    *,
    catalog_limit_without_manual_links: int = 5,
    similar_limit: int = 3,
    knowledge_port: KnowledgePort | None = None,
) -> KnowledgeSuggestions:
    del kb_links, catalog_limit_without_manual_links
    port = knowledge_port or DomainPortContainer.from_config().knowledge
    result = await port.suggest(
        KnowledgeSuggestionRequest(
            query=clean_knowledge_text(getattr(ticket, "title", None)) or "ticket",
            audience_context=("support",),
        )
    )
    articles = [
        KnowledgeArticleSuggestion(id=item.item_ref, title=item.title)
        for item in getattr(result, "items", ())
    ]
    similar_tickets = await load_similar_knowledge_tickets(session, ticket, limit=similar_limit)
    external_status = "available" if getattr(result, "status", None) == "ok" else "not_configured"
    fallback_reason = "similar_tickets_only" if similar_tickets and not articles else None
    if not similar_tickets and not articles:
        fallback_reason = "no_sources_found"
    return KnowledgeSuggestions(
        articles=articles,
        similar_tickets=similar_tickets,
        ai_summary=KnowledgeAiSuggestion(text=None, sources=[], confidence="none", source_count=0),
        diagnostics=KnowledgeDiagnostics(
            provider_status="ok" if external_status == "available" else "degraded",
            external_provider_status=external_status,
            fallback_reason=fallback_reason,
            source_counts={
                "external_knowledge": len(articles),
                "similar_ticket": len(similar_tickets),
            },
            similar_ticket_matches={
                item.id: {
                    "source_type": item.source_type,
                    "score": item.score,
                    "match_reasons": list(item.match_reasons),
                }
                for item in similar_tickets
            },
        ),
    )
