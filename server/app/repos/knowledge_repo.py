from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
from typing import Any
import uuid

from sqlalchemy import func, or_, select, update
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
    KnowledgePublicationBlockedError,
    KnowledgeValidationError,
    actor_visible_visibilities,
    can_mutate_knowledge_visibility,
    can_read_knowledge_visibility,
    lint_requester_safe_publication,
    normalize_knowledge_slug,
)
from knowledge.content_lint import lint_knowledge_content


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


def _knowledge_review_required() -> bool:
    raw = str(os.getenv("KNOWLEDGE_REVIEW_REQUIRED", "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _default_reviewer_actor_id(actor_id: str | None) -> str:
    return _text(actor_id) or "servicedesk"


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

    async def list_spaces(self, *, actor_role: str = "admin") -> list[dict[str, Any]]:
        allowed = set(actor_visible_visibilities(actor_role))
        rows = (
            await self.session.execute(
                select(KnowledgeSpace)
                .where(KnowledgeSpace.visibility.in_(allowed))
                .order_by(KnowledgeSpace.lifecycle_status.asc(), KnowledgeSpace.code.asc())
            )
        ).scalars().all()
        return [serialize_space(row) for row in rows]

    async def create_item_draft(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str = "admin",
    ) -> dict[str, Any]:
        space = await self.get_space_by_code(str(payload.get("space_code") or ""))
        if space is None:
            raise ValueError("knowledge space not found")
        slug = normalize_knowledge_slug(payload.get("slug") or payload.get("title"))
        item_type = _validate_choice(str(payload.get("item_type") or "article"), KNOWLEDGE_ITEM_TYPES, "item_type")
        visibility = _validate_choice(str(payload.get("visibility") or space.visibility), KNOWLEDGE_VISIBILITIES, "visibility")
        if not can_mutate_knowledge_visibility(actor_role, visibility):
            raise KnowledgeValidationError("actor cannot create knowledge with this visibility")
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
        if item is None or not can_read_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        if str(actor_role or "").lower() not in {"admin", "support", "auditor", "security"} and item.status != "published":
            raise ValueError("knowledge item not found")
        return serialize_item(item, current_version=await self._current_version(item))

    async def update_item_settings(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str = "admin",
    ) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None or not can_read_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise KnowledgeValidationError("actor cannot update this knowledge item")
        if "space_code" in payload:
            space = await self.get_space_by_code(str(payload.get("space_code") or ""))
            if space is None:
                raise KnowledgeValidationError("knowledge space not found")
            item.space_id = space.space_id
        if "item_type" in payload:
            item.item_type = _validate_choice(str(payload.get("item_type") or item.item_type), KNOWLEDGE_ITEM_TYPES, "item_type")
        if "visibility" in payload:
            visibility = _validate_choice(str(payload.get("visibility") or item.visibility), KNOWLEDGE_VISIBILITIES, "visibility")
            if not can_mutate_knowledge_visibility(actor_role, visibility):
                raise KnowledgeValidationError("actor cannot set this knowledge visibility")
            item.visibility = visibility
            if item.current_version_id:
                await self.session.execute(
                    update(KnowledgeChunk)
                    .where(KnowledgeChunk.item_id == item.item_id, KnowledgeChunk.version_id == item.current_version_id)
                    .values(visibility=visibility)
                )
        if "title" in payload:
            item.title = _text(payload.get("title")) or item.title
        if "summary" in payload:
            item.summary = _text(payload.get("summary"))
        if "owner_actor_id" in payload:
            item.owner_actor_id = _text(payload.get("owner_actor_id"))
        if "reviewer_actor_id" in payload:
            item.reviewer_actor_id = _text(payload.get("reviewer_actor_id"))
        if "tags" in payload:
            item.tags = _list(payload.get("tags"))
        if "metadata" in payload or "metadata_json" in payload:
            metadata = _dict(item.metadata_json)
            metadata.update(_dict(payload.get("metadata") or payload.get("metadata_json")))
            item.metadata_json = metadata
        now = datetime.now(timezone.utc)
        item.updated_at = now
        item.updated_by = actor_id
        await self.session.flush()
        return serialize_item(item, current_version=await self._current_version(item))

    async def list_items(self, *, actor_role: str = "admin", include_archived: bool = True) -> list[dict[str, Any]]:
        allowed = set(actor_visible_visibilities(actor_role))
        stmt = (
            select(KnowledgeItem)
            .where(KnowledgeItem.visibility.in_(allowed))
            .order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.slug.asc())
        )
        if not include_archived:
            stmt = stmt.where(KnowledgeItem.status != "archived")
        if str(actor_role or "").lower() not in {"admin", "support", "auditor", "security"}:
            stmt = stmt.where(KnowledgeItem.status == "published")
        rows = (await self.session.execute(stmt)).scalars().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(serialize_item(row, current_version=await self._current_version(row)))
        return result

    async def list_versions(self, item_id_or_slug: str, *, actor_role: str = "admin") -> list[dict[str, Any]]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None or not can_read_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        rows = (
            await self.session.execute(
                select(KnowledgeItemVersion)
                .where(KnowledgeItemVersion.item_id == item.item_id)
                .order_by(KnowledgeItemVersion.version_number.desc(), KnowledgeItemVersion.created_at.desc())
            )
        ).scalars().all()
        return [serialize_version(row) for row in rows]

    async def get_latest_version(self, item_id_or_slug: str, *, actor_role: str = "admin") -> dict[str, Any] | None:
        versions = await self.list_versions(item_id_or_slug, actor_role=actor_role)
        return versions[0] if versions else None

    async def create_version(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str = "admin",
    ) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None or not can_read_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise KnowledgeValidationError("actor cannot create a version for this knowledge item")
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

    async def publish_item(
        self,
        item_id_or_slug: str,
        version_id: str | None,
        *,
        actor_id: str | None,
        actor_role: str = "admin",
        acknowledge_stale_passport: bool = False,
        review_note: str | None = None,
    ) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None:
            raise ValueError("knowledge item not found")
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        if not version_id:
            blockers = self._publish_blockers(
                item,
                None,
                version_id=version_id,
                acknowledge_stale_passport=acknowledge_stale_passport,
                review_note=review_note,
            )
            raise KnowledgePublicationBlockedError(blockers)
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
        if not _knowledge_review_required() and not item.reviewer_actor_id:
            item.reviewer_actor_id = _default_reviewer_actor_id(actor_id)
        blockers = self._publish_blockers(
            item,
            version,
            version_id=version_id,
            acknowledge_stale_passport=acknowledge_stale_passport,
            review_note=review_note,
        )
        if blockers:
            raise KnowledgePublicationBlockedError(blockers)
        now = datetime.now(timezone.utc)
        if review_note:
            metadata = _dict(version.metadata_json)
            metadata["publish_review"] = {"note": review_note, "acknowledge_stale_passport": bool(acknowledge_stale_passport)}
            version.metadata_json = metadata
            version.reviewed_by = version.reviewed_by or actor_id
            version.reviewed_at = version.reviewed_at or now
        version.published_at = version.published_at or now
        version.published_by = actor_id
        item.current_version_id = version.version_id
        item.status = "published"
        item.published_at = item.published_at or now
        item.updated_at = now
        item.updated_by = actor_id
        await self.session.flush()
        return serialize_item(item, current_version=version)

    def _publish_blockers(
        self,
        item: KnowledgeItem,
        version: KnowledgeItemVersion | None,
        *,
        version_id: str | None,
        acknowledge_stale_passport: bool,
        review_note: str | None,
    ) -> list[dict[str, str]]:
        blockers: list[dict[str, str]] = []
        if not version_id:
            blockers.append(
                {
                    "severity": "error",
                    "code": "missing_version",
                    "message": "version_id is required before publishing",
                    "suggested_fix": "Create or select a knowledge version before publishing.",
                }
            )
            return blockers
        if _knowledge_review_required() and not item.reviewer_actor_id:
            blockers.append(
                {
                    "severity": "error",
                    "code": "missing_reviewer",
                    "message": "reviewer is required before publishing",
                    "suggested_fix": "Assign a reviewer to the knowledge item.",
                }
            )
        if item.status == "archived":
            blockers.append(
                {
                    "severity": "error",
                    "code": "archived_item",
                    "message": "archived knowledge items cannot be published",
                    "suggested_fix": "Create a new draft or unarchive through a governed path.",
                }
            )
        if version is not None and not str(version.body or "").strip():
            blockers.append(
                {
                    "severity": "error",
                    "code": "empty_body",
                    "message": "knowledge version body is required before publishing",
                    "suggested_fix": "Add reviewed content to the selected version.",
                }
            )
        metadata = _dict(item.metadata_json)
        warnings = metadata.get("warnings")
        stale_warning = False
        if isinstance(warnings, list):
            stale_warning = any("stale" in str(entry).lower() for entry in warnings)
        passport_stale = bool(metadata.get("passport_stale") or stale_warning)
        if item.source_kind == "ticket_passport" or metadata.get("review_required") or passport_stale:
            if metadata.get("review_required") and not (review_note or acknowledge_stale_passport):
                blockers.append(
                    {
                        "severity": "error",
                        "code": "review_required",
                        "message": "passport-derived knowledge requires explicit review before publishing",
                        "suggested_fix": "Record a review note or acknowledgement before publishing.",
                    }
                )
            if passport_stale and not acknowledge_stale_passport:
                blockers.append(
                    {
                        "severity": "error",
                        "code": "stale_passport",
                        "message": "stale passport draft cannot be published without acknowledgement",
                        "suggested_fix": "Review the source passport and acknowledge the stale source.",
                    }
                )
        if item.visibility in {"public", "requester", "agent_requester_safe"} and metadata.get("internal_evidence_markers"):
            blockers.append(
                {
                    "severity": "error",
                    "code": "internal_evidence_in_safe_item",
                    "message": "requester-safe knowledge cannot expose internal evidence",
                    "suggested_fix": "Remove internal evidence or change visibility.",
                }
            )
        blockers.extend(
            lint_requester_safe_publication(
                visibility=item.visibility,
                title=version.title if version is not None else item.title,
                summary=version.summary if version is not None else item.summary,
                body=version.body if version is not None else "",
                metadata={**metadata, **(_dict(version.metadata_json) if version is not None else {})},
            )
        )
        if item.review_due_at is None:
            item.review_due_at = datetime.now(timezone.utc) + timedelta(days=90)
        lint = lint_knowledge_content(
            item_type=item.item_type,
            visibility=item.visibility,
            title=(version.title if version is not None else None) or item.title,
            summary=(version.summary if version is not None else None) or item.summary or item.title,
            body=version.body if version is not None else "",
            owner_actor_id=item.owner_actor_id,
            reviewer_actor_id=item.reviewer_actor_id,
            review_due_at=item.review_due_at,
            bindings=[],
            source_refs=version.source_refs if version is not None else [],
            metadata={**metadata, **(_dict(version.metadata_json) if version is not None else {})},
            acknowledged_warning_codes={"missing_required_sections", "missing_self_service_binding"},
        )
        blockers.extend(lint["errors"])
        return blockers

    async def add_binding(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str = "admin",
    ) -> dict[str, Any]:
        item = await self.get_item_row(item_id_or_slug)
        if item is None or not can_read_knowledge_visibility(actor_role, item.visibility):
            raise ValueError("knowledge item not found")
        if not can_mutate_knowledge_visibility(actor_role, item.visibility):
            raise KnowledgeValidationError("actor cannot add bindings to this knowledge item")
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
