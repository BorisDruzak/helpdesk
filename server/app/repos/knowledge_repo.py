from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeBinding,
    KnowledgeChunk,
    KnowledgeItem,
    KnowledgeItemVersion,
    KnowledgeSpace,
)
from knowledge.contracts import (
    KNOWLEDGE_BODY_FORMATS,
    KNOWLEDGE_ITEM_STATUSES,
    KNOWLEDGE_ITEM_TYPES,
    KNOWLEDGE_VISIBILITIES,
    KnowledgeValidationError,
    normalize_knowledge_slug,
)


def _new_id() -> str:
    return str(uuid.uuid4())


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _dict(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _validate_choice(value: str, choices: tuple[str, ...], field_name: str) -> str:
    if value not in choices:
        raise KnowledgeValidationError(f"unsupported {field_name}: {value}")
    return value


def _chunk_text(body: str) -> list[tuple[str | None, str]]:
    chunks: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for raw_line in str(body or "").splitlines():
        line = raw_line.strip()
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading_match:
            if current_lines:
                chunks.append((current_heading, "\n".join(current_lines).strip()))
                current_lines = []
            current_heading = heading_match.group(1).strip()
            continue
        if line:
            current_lines.append(line)
    if current_lines:
        chunks.append((current_heading, "\n".join(current_lines).strip()))
    if not chunks and body.strip():
        chunks.append((None, body.strip()))
    return chunks


def serialize_space(row: KnowledgeSpace) -> dict[str, Any]:
    return {
        "space_id": row.space_id,
        "code": row.code,
        "title": row.title,
        "description": row.description,
        "visibility": row.visibility,
        "lifecycle_status": row.lifecycle_status,
        "owner_actor_id": row.owner_actor_id,
        "default_reviewer_actor_id": row.default_reviewer_actor_id,
        "default_review_period_days": row.default_review_period_days,
        "allowed_item_types": _list(row.allowed_item_types),
        "allow_publication": row.allow_publication,
        "allow_ingestion": row.allow_ingestion,
        "allow_rag": row.allow_rag,
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }


def serialize_version(row: KnowledgeItemVersion) -> dict[str, Any]:
    return {
        "version_id": row.version_id,
        "item_id": row.item_id,
        "version_number": row.version_number,
        "title": row.title,
        "summary": row.summary,
        "body_format": row.body_format,
        "body": row.body,
        "rendered_body": row.rendered_body,
        "change_summary": row.change_summary,
        "source_refs": _list(row.source_refs),
        "created_by": row.created_by,
        "reviewed_by": row.reviewed_by,
        "published_by": row.published_by,
        "created_at": _iso(row.created_at),
        "reviewed_at": _iso(row.reviewed_at),
        "published_at": _iso(row.published_at),
        "metadata": _dict(row.metadata_json),
    }


def serialize_item(row: KnowledgeItem, *, current_version: KnowledgeItemVersion | None = None) -> dict[str, Any]:
    payload = {
        "item_id": row.item_id,
        "space_id": row.space_id,
        "slug": row.slug,
        "item_type": row.item_type,
        "type": row.item_type,
        "title": row.title,
        "summary": row.summary,
        "status": row.status,
        "visibility": row.visibility,
        "language": row.language,
        "owner_actor_id": row.owner_actor_id,
        "reviewer_actor_id": row.reviewer_actor_id,
        "current_version_id": row.current_version_id,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "source_ticket_id": row.source_ticket_id,
        "source_passport_id": row.source_passport_id,
        "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
        "review_due_at": _iso(row.review_due_at),
        "published_at": _iso(row.published_at),
        "archived_at": _iso(row.archived_at),
        "tags": _list(row.tags),
        "metadata": _dict(row.metadata_json),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
    }
    if current_version is not None:
        payload["current_version"] = serialize_version(current_version)
        payload["version_id"] = current_version.version_id
    return payload


def serialize_binding(row: KnowledgeBinding) -> dict[str, Any]:
    return {
        "binding_id": row.binding_id,
        "item_id": row.item_id,
        "service_code": row.service_code,
        "offering_code": row.offering_code,
        "request_template_key": row.request_template_key,
        "ticket_type": row.ticket_type,
        "reporting_category": row.reporting_category,
        "device_class": row.device_class,
        "os_family": row.os_family,
        "symptom_code": row.symptom_code,
        "error_code": row.error_code,
        "priority": row.priority,
        "queue_code": row.queue_code,
        "weight": float(row.weight),
        "created_at": _iso(row.created_at),
        "created_by": row.created_by,
        "metadata": _dict(row.metadata_json),
    }


class KnowledgeRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_space(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        code = normalize_knowledge_slug(payload.get("code"))
        row = (await self.session.execute(select(KnowledgeSpace).where(KnowledgeSpace.code == code))).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row is None:
            row = KnowledgeSpace(
                space_id=str(payload.get("space_id") or _new_id()),
                code=code,
                title=_text(payload.get("title") or code) or code,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
            )
            self.session.add(row)
        row.title = _text(payload.get("title") or row.title) or row.title
        row.description = _text(payload.get("description"))
        row.visibility = _validate_choice(
            str(payload.get("visibility") or row.visibility or "support_internal"),
            KNOWLEDGE_VISIBILITIES,
            "visibility",
        )
        row.lifecycle_status = _validate_choice(
            str(payload.get("lifecycle_status") or row.lifecycle_status or "draft"),
            ("draft", "active", "archived"),
            "lifecycle_status",
        )
        row.owner_actor_id = _text(payload.get("owner_actor_id"))
        row.default_reviewer_actor_id = _text(payload.get("default_reviewer_actor_id"))
        row.default_review_period_days = payload.get("default_review_period_days")
        row.allowed_item_types = _list(payload.get("allowed_item_types"))
        row.allow_publication = bool(payload.get("allow_publication", row.allow_publication))
        row.allow_ingestion = bool(payload.get("allow_ingestion", row.allow_ingestion))
        row.allow_rag = bool(payload.get("allow_rag", row.allow_rag))
        row.metadata_json = _dict(payload.get("metadata") or payload.get("metadata_json"))
        row.updated_at = now
        row.updated_by = actor_id
        await self.session.flush()
        return serialize_space(row)

    async def get_space_by_code(self, code: str) -> KnowledgeSpace | None:
        return (
            await self.session.execute(select(KnowledgeSpace).where(KnowledgeSpace.code == normalize_knowledge_slug(code)))
        ).scalar_one_or_none()

    async def list_spaces(self) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(select(KnowledgeSpace).order_by(KnowledgeSpace.lifecycle_status.asc(), KnowledgeSpace.code.asc()))
        ).scalars().all()
        return [serialize_space(row) for row in rows]

    async def create_item_draft(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        space = await self.get_space_by_code(str(payload.get("space_code") or ""))
        if space is None:
            raise ValueError("knowledge space not found")
        slug = normalize_knowledge_slug(payload.get("slug") or payload.get("title"))
        item_type = _validate_choice(str(payload.get("item_type") or "article"), KNOWLEDGE_ITEM_TYPES, "item_type")
        visibility = _validate_choice(str(payload.get("visibility") or space.visibility), KNOWLEDGE_VISIBILITIES, "visibility")
        now = datetime.now(timezone.utc)
        row = KnowledgeItem(
            item_id=str(payload.get("item_id") or _new_id()),
            space_id=space.space_id,
            slug=slug,
            item_type=item_type,
            title=_text(payload.get("title") or slug) or slug,
            summary=_text(payload.get("summary")),
            status="draft",
            visibility=visibility,
            language=_text(payload.get("language")) or "ru",
            owner_actor_id=_text(payload.get("owner_actor_id") or space.owner_actor_id),
            reviewer_actor_id=_text(payload.get("reviewer_actor_id") or space.default_reviewer_actor_id),
            source_kind=_text(payload.get("source_kind")),
            source_ref=_text(payload.get("source_ref")),
            source_ticket_id=_text(payload.get("source_ticket_id")),
            source_passport_id=payload.get("source_passport_id"),
            tags=_list(payload.get("tags")),
            metadata_json=_dict(payload.get("metadata") or payload.get("metadata_json")),
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.session.add(row)
        await self.session.flush()
        return serialize_item(row)

    async def get_item_row(self, item_id_or_slug: str) -> KnowledgeItem | None:
        return (
            await self.session.execute(
                select(KnowledgeItem).where(
                    or_(KnowledgeItem.item_id == item_id_or_slug, KnowledgeItem.slug == item_id_or_slug)
                )
            )
        ).scalar_one_or_none()

    async def _current_version(self, item: KnowledgeItem) -> KnowledgeItemVersion | None:
        if not item.current_version_id:
            return None
        return (
            await self.session.execute(
                select(KnowledgeItemVersion).where(KnowledgeItemVersion.version_id == item.current_version_id)
            )
        ).scalar_one_or_none()

    async def get_item(self, item_id_or_slug: str, *, actor_role: str = "admin") -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        return serialize_item(item, current_version=await self._current_version(item))

    async def list_items(self, *, include_archived: bool = True) -> list[dict[str, Any]]:
        stmt = select(KnowledgeItem).order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.slug.asc())
        if not include_archived:
            stmt = stmt.where(KnowledgeItem.status != "archived")
        rows = (await self.session.execute(stmt)).scalars().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(serialize_item(row, current_version=await self._current_version(row)))
        return result

    async def create_version(self, item_id_or_slug: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        body_format = _validate_choice(str(payload.get("body_format") or "markdown"), KNOWLEDGE_BODY_FORMATS, "body_format")
        number = (
            await self.session.execute(
                select(func.coalesce(func.max(KnowledgeItemVersion.version_number), 0)).where(
                    KnowledgeItemVersion.item_id == item.item_id
                )
            )
        ).scalar_one()
        version = KnowledgeItemVersion(
            version_id=str(payload.get("version_id") or _new_id()),
            item_id=item.item_id,
            version_number=int(number) + 1,
            title=_text(payload.get("title") or item.title) or item.title,
            summary=_text(payload.get("summary") or item.summary),
            body_format=body_format,
            body=str(payload.get("body") or ""),
            rendered_body=_text(payload.get("rendered_body")),
            change_summary=_text(payload.get("change_summary")),
            source_refs=_list(payload.get("source_refs")),
            metadata_json=_dict(payload.get("metadata") or payload.get("metadata_json")),
            created_by=actor_id,
        )
        self.session.add(version)
        await self.session.flush()
        await self._replace_chunks(item, version)
        return serialize_version(version)

    async def _replace_chunks(self, item: KnowledgeItem, version: KnowledgeItemVersion) -> None:
        for index, (heading, text) in enumerate(_chunk_text(version.body)):
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.session.add(
                KnowledgeChunk(
                    chunk_id=_new_id(),
                    item_id=item.item_id,
                    version_id=version.version_id,
                    chunk_index=index,
                    heading=heading,
                    text=text,
                    token_count=len(text.split()),
                    content_hash=content_hash,
                    visibility=item.visibility,
                )
            )
        await self.session.flush()

    async def publish_item(self, item_id_or_slug: str, version_id: str | None, *, actor_id: str | None) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        if not item.reviewer_actor_id:
            raise ValueError("reviewer is required before publishing")
        if not version_id:
            raise ValueError("version_id is required before publishing")
        version = (
            await self.session.execute(
                select(KnowledgeItemVersion).where(
                    KnowledgeItemVersion.item_id == item.item_id,
                    KnowledgeItemVersion.version_id == version_id,
                )
            )
        ).scalar_one_or_none()
        if version is None:
            raise ValueError("knowledge version not found")
        now = datetime.now(timezone.utc)
        version.published_at = version.published_at or now
        version.published_by = actor_id
        item.current_version_id = version.version_id
        item.status = "published"
        item.published_at = item.published_at or now
        item.updated_at = now
        item.updated_by = actor_id
        await self.session.flush()
        return serialize_item(item, current_version=version)

    async def add_binding(self, item_id_or_slug: str, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        row = KnowledgeBinding(
            binding_id=str(payload.get("binding_id") or _new_id()),
            item_id=item.item_id,
            service_code=_text(payload.get("service_code")),
            offering_code=_text(payload.get("offering_code")),
            request_template_key=_text(payload.get("request_template_key")),
            ticket_type=_text(payload.get("ticket_type")),
            reporting_category=_text(payload.get("reporting_category")),
            device_class=_text(payload.get("device_class")),
            os_family=_text(payload.get("os_family")),
            symptom_code=_text(payload.get("symptom_code")),
            error_code=_text(payload.get("error_code")),
            priority=_text(payload.get("priority")),
            queue_code=_text(payload.get("queue_code")),
            weight=payload.get("weight") or 1,
            created_by=actor_id,
            metadata_json=_dict(payload.get("metadata") or payload.get("metadata_json")),
        )
        self.session.add(row)
        await self.session.flush()
        return serialize_binding(row)

    async def list_bindings(self, item_id_or_slug: str) -> list[dict[str, Any]]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        rows = (
            await self.session.execute(
                select(KnowledgeBinding).where(KnowledgeBinding.item_id == item.item_id).order_by(KnowledgeBinding.created_at.asc())
            )
        ).scalars().all()
        return [serialize_binding(row) for row in rows]
