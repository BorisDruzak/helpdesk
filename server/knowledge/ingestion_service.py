from __future__ import annotations

import re
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeIngestionJob
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.contracts import KNOWLEDGE_INGESTION_SOURCE_KINDS, KnowledgeValidationError


def _new_id() -> str:
    return str(uuid.uuid4())


def _slug_from_title(title: str) -> str:
    ascii_title = re.sub(r"[^a-zA-Z0-9_-]+", "-", title.lower()).strip("-")
    return ascii_title or f"import-{uuid.uuid4().hex[:8]}"


def _redact_error(error: BaseException) -> str:
    text = str(error)
    text = re.sub(r"(?i)(token|password|secret)=\S+", r"\1=<redacted>", text)
    return text[:500]


class KnowledgeIngestionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_text(self, payload: dict[str, Any], *, actor_id: str | None, actor_role: str = "admin") -> dict[str, Any]:
        repo = KnowledgeRepo(self.session)
        space = await repo.get_space_by_code(str(payload.get("space_code") or ""))
        if space is None:
            raise ValueError("knowledge space not found")
        source_kind = str(payload.get("source_kind") or "text")
        if source_kind not in KNOWLEDGE_INGESTION_SOURCE_KINDS:
            raise KnowledgeValidationError(f"unsupported ingestion source_kind: {source_kind}")
        job = KnowledgeIngestionJob(
            job_id=_new_id(),
            space_id=space.space_id,
            source_kind=source_kind,
            source_name=str(payload.get("source_name") or payload.get("title") or "manual text"),
            status="queued",
            created_by=actor_id,
        )
        self.session.add(job)
        await self.session.flush()
        item = await repo.create_item_draft(
            {
                "space_code": space.code,
                "slug": payload.get("slug") or _slug_from_title(str(payload.get("title") or payload.get("source_name") or "knowledge")),
                "item_type": payload.get("item_type") or "document",
                "title": payload.get("title") or payload.get("source_name") or "Imported knowledge",
                "summary": payload.get("summary"),
                "visibility": payload.get("visibility") or "support_internal",
                "source_kind": "imported_document",
                "source_ref": payload.get("source_name"),
                "owner_actor_id": payload.get("owner_actor_id") or actor_id,
                "reviewer_actor_id": payload.get("reviewer_actor_id") or actor_id,
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        version = await repo.create_version(
            item["item_id"],
            {
                "title": item["title"],
                "summary": item.get("summary"),
                "body_format": "markdown" if str(payload.get("source_kind") or "").lower() == "markdown" else "plain_text",
                "body": str(payload.get("body") or ""),
                "change_summary": "Imported draft",
            },
            actor_id=actor_id,
            actor_role=actor_role,
        )
        job.status = "review_required"
        job.created_item_id = item["item_id"]
        job.created_version_id = version["version_id"]
        job.stats_json = {"chunk_count": len((payload.get("body") or "").split("\n\n"))}
        await self.session.flush()
        return {"job": {"job_id": job.job_id, "status": job.status}, "item": item, "version": version, "chunk_count": max(1, job.stats_json["chunk_count"])}

    async def fail_job_redacted(self, *, space_code: str, source_name: str, error: BaseException, actor_id: str | None) -> dict[str, Any]:
        return {"job_id": None, "status": "failed", "source_name": source_name, "error_message_redacted": _redact_error(error)}
