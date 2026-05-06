from __future__ import annotations

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from sqlalchemy import or_, select

from app.db.models import Ticket


DEFAULT_KNOWLEDGE_CATALOG_PATH = Path(__file__).with_name("knowledge_catalog.json")


@dataclass(frozen=True)
class KnowledgeArticleSuggestion:
    id: str
    title: str
    url: str | None = None


@dataclass(frozen=True)
class KnowledgeSimilarTicketSuggestion:
    id: str
    number: str | None
    subject: str
    resolution_summary: str | None = None


@dataclass(frozen=True)
class KnowledgeAiSuggestion:
    text: str | None
    sources: list[str]


@dataclass(frozen=True)
class KnowledgeSuggestions:
    articles: list[KnowledgeArticleSuggestion]
    similar_tickets: list[KnowledgeSimilarTicketSuggestion]
    ai_summary: KnowledgeAiSuggestion


@dataclass(frozen=True)
class KnowledgeCatalogEntry:
    id: str
    title: str
    url: str | None
    keywords: tuple[str, ...]


def clean_knowledge_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def article_url(article_ref: str) -> str:
    return f"/app/knowledge/{quote(article_ref, safe='')}"


def _knowledge_text_fragments(value: Any, *, limit: int = 32) -> list[str]:
    if limit <= 0 or value is None:
        return []
    if isinstance(value, dict):
        fragments: list[str] = []
        for key, nested in value.items():
            fragments.extend(_knowledge_text_fragments(key, limit=limit - len(fragments)))
            fragments.extend(_knowledge_text_fragments(nested, limit=limit - len(fragments)))
            if len(fragments) >= limit:
                break
        return fragments[:limit]
    if isinstance(value, (list, tuple, set)):
        fragments = []
        for item in value:
            fragments.extend(_knowledge_text_fragments(item, limit=limit - len(fragments)))
            if len(fragments) >= limit:
                break
        return fragments[:limit]
    text = clean_knowledge_text(value)
    return [text] if text else []


def ticket_knowledge_search_text(ticket: Ticket) -> str:
    fields: list[Any] = [
        getattr(ticket, "title", None),
        getattr(ticket, "description", None),
        getattr(ticket, "requester_resolution_summary", None),
        getattr(ticket, "resolution_summary", None),
        getattr(ticket, "ticket_type", None),
        getattr(ticket, "source", None),
        getattr(ticket, "custom_fields", None),
    ]
    fragments: list[str] = []
    for field in fields:
        fragments.extend(_knowledge_text_fragments(field))
    return " ".join(fragments).casefold()


def _coerce_catalog_entries(raw_entries: Iterable[Any]) -> tuple[KnowledgeCatalogEntry, ...]:
    entries: list[KnowledgeCatalogEntry] = []
    seen_ids: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        article_id = clean_knowledge_text(raw.get("id"))
        title = clean_knowledge_text(raw.get("title"))
        if not article_id or not title or article_id in seen_ids:
            continue
        raw_keywords = raw.get("keywords")
        raw_keyword_items = raw_keywords if isinstance(raw_keywords, list) else []
        keywords = tuple(
            keyword
            for keyword in (clean_knowledge_text(item) for item in raw_keyword_items)
            if keyword
        )
        entries.append(
            KnowledgeCatalogEntry(
                id=article_id,
                title=title,
                url=clean_knowledge_text(raw.get("url")) or article_url(article_id),
                keywords=keywords,
            )
        )
        seen_ids.add(article_id)
    return tuple(entries)


@lru_cache(maxsize=4)
def load_knowledge_catalog(path: str | None = None) -> tuple[KnowledgeCatalogEntry, ...]:
    catalog_path = Path(path) if path else DEFAULT_KNOWLEDGE_CATALOG_PATH
    try:
        raw_entries = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(raw_entries, list):
        return ()
    return _coerce_catalog_entries(raw_entries)


def search_catalog_articles_for_ticket(
    ticket: Ticket,
    existing_article_ids: set[str] | None = None,
    *,
    catalog: Iterable[KnowledgeCatalogEntry] | None = None,
    limit: int = 3,
) -> list[KnowledgeArticleSuggestion]:
    search_text = ticket_knowledge_search_text(ticket)
    if not search_text:
        return []
    existing_ids = existing_article_ids or set()
    scored: list[tuple[int, int, KnowledgeCatalogEntry]] = []
    for index, entry in enumerate(catalog if catalog is not None else load_knowledge_catalog()):
        if entry.id in existing_ids:
            continue
        score = 0
        for keyword in entry.keywords:
            normalized_keyword = keyword.casefold()
            if normalized_keyword and normalized_keyword in search_text:
                score += 2 if " " in normalized_keyword else 1
        if score > 0:
            scored.append((score, -index, entry))

    scored.sort(reverse=True)
    return [
        KnowledgeArticleSuggestion(id=entry.id, title=entry.title, url=entry.url)
        for _score, _index, entry in scored[:limit]
    ]


def _ticket_knowledge_number(ticket: Ticket) -> str | None:
    return clean_knowledge_text(getattr(ticket, "ticket_code", None)) or clean_knowledge_text(
        getattr(ticket, "ticket_id", None)
    )


async def load_similar_knowledge_tickets(session, ticket: Ticket, limit: int = 3) -> list[KnowledgeSimilarTicketSuggestion]:
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
            if len(similar_rows) >= limit:
                break

    if len(similar_rows) < limit:
        filters = [Ticket.ticket_id != ticket_id, Ticket.status.in_(["resolved", "closed"])]
        category_id = getattr(ticket, "category_id", None)
        service_id = getattr(ticket, "service_id", None)
        if category_id is not None:
            filters.append(Ticket.category_id == category_id)
        elif service_id is not None:
            filters.append(Ticket.service_id == service_id)
        else:
            filters.append(Ticket.title.ilike(f"%{(getattr(ticket, 'title', '') or '')[:24]}%"))
        result = await session.execute(
            select(Ticket)
            .where(*filters)
            .order_by(Ticket.updated_at.desc())
            .limit(limit * 2)
        )
        for row in result.scalars().all():
            if row not in similar_rows:
                similar_rows.append(row)
            if len(similar_rows) >= limit:
                break

    return [
        KnowledgeSimilarTicketSuggestion(
            id=str(row.ticket_id),
            number=_ticket_knowledge_number(row),
            subject=str(getattr(row, "title", "") or "Без темы"),
            resolution_summary=clean_knowledge_text(getattr(row, "requester_resolution_summary", None))
            or clean_knowledge_text(getattr(row, "resolution_summary", None)),
        )
        for row in similar_rows[:limit]
    ]


def knowledge_source_summary(
    articles: list[KnowledgeArticleSuggestion],
    tickets: list[KnowledgeSimilarTicketSuggestion],
) -> KnowledgeAiSuggestion:
    sources: list[str] = []
    for article in articles:
        if article.id not in sources:
            sources.append(article.id)
    for similar_ticket in tickets:
        source = similar_ticket.number or similar_ticket.id
        if source and source not in sources:
            sources.append(source)
    if not sources:
        return KnowledgeAiSuggestion(text=None, sources=[])
    visible_sources = ", ".join(sources[:5])
    extra = len(sources) - 5
    if extra > 0:
        visible_sources = f"{visible_sources} и ещё {extra}"
    return KnowledgeAiSuggestion(
        text=(
            "AI-рекомендация / Бета: найдены связанные источники "
            f"({visible_sources}). Проверьте статьи и похожие тикеты перед применением решения; "
            "действия не запускаются автоматически."
        ),
        sources=sources,
    )


async def build_knowledge_suggestions(
    session,
    ticket: Ticket,
    kb_links: Iterable[Any],
    *,
    catalog_limit_without_manual_links: int = 5,
    similar_limit: int = 3,
) -> KnowledgeSuggestions:
    articles = [
        KnowledgeArticleSuggestion(
            id=str(link.article_ref),
            title=clean_knowledge_text(getattr(link, "title", None)) or str(link.article_ref),
            url=article_url(str(link.article_ref)),
        )
        for link in kb_links
        if clean_knowledge_text(getattr(link, "article_ref", None))
    ]
    existing_article_ids = {article.id for article in articles}
    if not articles and catalog_limit_without_manual_links:
        articles.extend(
            search_catalog_articles_for_ticket(
                ticket,
                existing_article_ids,
                limit=catalog_limit_without_manual_links,
            )
        )
    similar_tickets = await load_similar_knowledge_tickets(session, ticket, limit=similar_limit)
    return KnowledgeSuggestions(
        articles=articles,
        similar_tickets=similar_tickets,
        ai_summary=knowledge_source_summary(articles, similar_tickets),
    )
