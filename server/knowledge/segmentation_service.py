from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import hashlib
import json
import re
import uuid

from sqlalchemy import text

from knowledge.contracts import actor_visible_visibilities, can_mutate_knowledge_visibility


class KnowledgeSegmentationPolicyBlockedError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "AI_MARKUP_POLICY_BLOCKED") -> None:
        super().__init__(message)
        self.error_code = error_code


DEFAULT_PROFILE: dict[str, Any] = {
    "profile_id": "default-auto",
    "code": "default-auto",
    "title": "Авторазметка по заголовкам",
    "mode": "auto",
    "split_by_headings": True,
    "split_by_paragraphs": True,
    "target_tokens": 450,
    "max_tokens": 900,
    "min_tokens": 80,
    "overlap_tokens": 40,
    "preserve_tables": True,
    "preserve_code_blocks": True,
    "default_segment_boost": 1.0,
    "ai_profile_id": None,
    "enabled": True,
    "metadata_json": {},
    "created_at": None,
    "updated_at": None,
    "created_by": None,
    "updated_by": None,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any, *, default: Any) -> str:
    return json.dumps(value if value is not None else default, ensure_ascii=False)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_row(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    payload = {key: _serialize_value(value) for key, value in data.items()}
    if "keywords_json" in payload:
        payload["keywords"] = payload.pop("keywords_json") or []
    if "heading_path_json" in payload:
        payload["heading_path"] = payload.pop("heading_path_json") or []
    return payload


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def _text(value: Any, *, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _keywords(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("keywords", payload.get("keywords_json", []))
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        keyword = _text(item)
        if keyword and keyword not in result:
            result.append(keyword)
    return result[:50]


def _content_hash(segment_text: str) -> str:
    return hashlib.sha256(segment_text.encode("utf-8")).hexdigest()


def _default_title(segment_text: str) -> str:
    first_line = next((line.strip() for line in segment_text.splitlines() if line.strip()), "")
    return first_line[:120] or "Сегмент знаний"


def _split_markdown_sections(body: str) -> list[dict[str, Any]]:
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_re.finditer(body or ""))
    sections: list[dict[str, Any]] = []
    if matches:
        for index, match in enumerate(matches):
            next_match_start = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            text_start = match.end()
            raw_text = body[text_start:next_match_start]
            leading_trim = len(raw_text) - len(raw_text.lstrip())
            trailing_trim = len(raw_text.rstrip())
            segment_text = raw_text.strip()
            if not segment_text:
                continue
            sections.append(
                {
                    "title": match.group(2).strip()[:180],
                    "text": segment_text,
                    "start_offset": text_start + leading_trim,
                    "end_offset": text_start + trailing_trim,
                    "heading_path": [match.group(2).strip()],
                    "source": "heading_split",
                }
            )
        if sections:
            return sections

    paragraph_re = re.compile(r"\S(?:.*\S)?", re.MULTILINE)
    for match in paragraph_re.finditer(body or ""):
        paragraph = match.group(0).strip()
        if paragraph:
            sections.append(
                {
                    "title": _default_title(paragraph),
                    "text": paragraph,
                    "start_offset": match.start(),
                    "end_offset": match.end(),
                    "heading_path": [],
                    "source": "paragraph_split",
                }
            )
    return sections


def _merge_metadata(existing: Any, updates: dict[str, Any]) -> dict[str, Any]:
    metadata = existing if isinstance(existing, dict) else {}
    return {**metadata, **updates}


class KnowledgeSegmentationService:
    def __init__(self, session_or_connection):
        self.db = session_or_connection

    async def list_profiles(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_segmentation_profiles
                    WHERE enabled = true
                    ORDER BY code
                    """
                )
            )
        ).all()
        if not rows:
            return [dict(DEFAULT_PROFILE)]
        profiles = []
        for row in rows:
            profile = _serialize_row(row)
            profile["metadata_json"] = profile.get("metadata_json") or {}
            profiles.append(profile)
        return profiles

    async def upsert_profile(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        code = _text(payload.get("code"))
        title = _text(payload.get("title"))
        mode = _text(payload.get("mode"), default="auto") or "auto"
        if not code or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,78}[a-z0-9]?", code):
            raise ValueError("profile code must be lowercase ascii")
        if not title:
            raise ValueError("profile title is required")
        if mode not in {"auto", "manual_default", "ai"}:
            raise ValueError("unsupported profile mode")

        now = _now()
        values = {
            "profile_id": str(uuid.uuid4()),
            "code": code,
            "title": title,
            "mode": mode,
            "split_by_headings": _bool(payload.get("split_by_headings"), default=True),
            "split_by_paragraphs": _bool(payload.get("split_by_paragraphs"), default=True),
            "target_tokens": int(payload.get("target_tokens") or 350),
            "max_tokens": int(payload.get("max_tokens") or 700),
            "min_tokens": int(payload.get("min_tokens") or 40),
            "overlap_tokens": int(payload.get("overlap_tokens") or 0),
            "preserve_tables": _bool(payload.get("preserve_tables"), default=True),
            "preserve_code_blocks": _bool(payload.get("preserve_code_blocks"), default=True),
            "default_segment_boost": _bounded_float(payload.get("default_segment_boost"), default=1.0, minimum=0.0, maximum=10.0),
            "ai_profile_id": _text(payload.get("ai_profile_id")) or None,
            "enabled": _bool(payload.get("enabled"), default=True),
            "metadata_json": _json(payload.get("metadata_json"), default={}),
            "now": now,
            "actor_id": actor_id,
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_segmentation_profiles (
                        profile_id, code, title, mode, split_by_headings, split_by_paragraphs,
                        target_tokens, max_tokens, min_tokens, overlap_tokens, preserve_tables,
                        preserve_code_blocks, default_segment_boost, ai_profile_id, enabled,
                        metadata_json, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (
                        :profile_id, :code, :title, :mode, :split_by_headings, :split_by_paragraphs,
                        :target_tokens, :max_tokens, :min_tokens, :overlap_tokens, :preserve_tables,
                        :preserve_code_blocks, :default_segment_boost, :ai_profile_id, :enabled,
                        CAST(:metadata_json AS jsonb), :now, :now, :actor_id, :actor_id
                    )
                    ON CONFLICT (code) DO UPDATE SET
                        title = EXCLUDED.title,
                        mode = EXCLUDED.mode,
                        split_by_headings = EXCLUDED.split_by_headings,
                        split_by_paragraphs = EXCLUDED.split_by_paragraphs,
                        target_tokens = EXCLUDED.target_tokens,
                        max_tokens = EXCLUDED.max_tokens,
                        min_tokens = EXCLUDED.min_tokens,
                        overlap_tokens = EXCLUDED.overlap_tokens,
                        preserve_tables = EXCLUDED.preserve_tables,
                        preserve_code_blocks = EXCLUDED.preserve_code_blocks,
                        default_segment_boost = EXCLUDED.default_segment_boost,
                        ai_profile_id = EXCLUDED.ai_profile_id,
                        enabled = EXCLUDED.enabled,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        profile = _serialize_row(row)
        profile["metadata_json"] = profile.get("metadata_json") or {}
        return profile

    async def list_segments(self, item_id_or_slug: str, *, actor_role: str) -> list[dict[str, Any]]:
        item = await self._get_item(item_id_or_slug)
        allowed = actor_visible_visibilities(actor_role)
        allowed_params = {f"visibility_{index}": value for index, value in enumerate(allowed)}
        allowed_sql = ", ".join(f":{key}" for key in allowed_params)
        rows = (
            await self.db.execute(
                text(
                    f"""
                    SELECT s.*
                    FROM knowledge_article_segments s
                    WHERE s.item_id = :item_id
                      AND s.visibility IN ({allowed_sql})
                      AND s.status <> 'archived'
                    ORDER BY s.segment_index, s.created_at, s.segment_id
                    """
                ),
                {"item_id": item["item_id"], **allowed_params},
            )
        ).all()
        return [_serialize_row(row) for row in rows]

    async def create_segment(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("segment mutation requires admin or support")
        item, version = await self._get_item_version(item_id_or_slug, payload.get("version_id"))
        segment = await self._insert_segment(item, version, payload, actor_id=actor_id, actor_role=actor_role)
        await self._record_audit(
            "knowledge.segmentation.segment_created",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "segment_id": segment["segment_id"],
                "segment_type": segment["segment_type"],
                "status": segment["status"],
                "source": segment.get("source"),
            },
        )
        return segment

    async def update_segment(
        self,
        segment_id: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        segment, item, version = await self._get_segment_context(segment_id)
        visibility = _text(payload.get("visibility"), default=segment["visibility"]) or segment["visibility"]
        if actor_role not in {"admin", "support"} or not can_mutate_knowledge_visibility(actor_role, visibility):
            raise PermissionError("segment mutation requires admin/support visibility")

        segment_text = _text(payload.get("text"), default=segment["text"])
        if not segment_text:
            raise ValueError("segment text is required")
        start = payload.get("start_offset", segment.get("start_offset"))
        end = payload.get("end_offset", segment.get("end_offset"))
        try:
            start_offset = int(start) if start is not None else None
            end_offset = int(end) if end is not None else None
        except (TypeError, ValueError):
            start_offset = None
            end_offset = None
        status = _text(payload.get("status"), default=segment["status"]) or "active"
        body = str(version.get("body") or "")
        if start_offset is not None and end_offset is not None and body[start_offset:end_offset] != segment_text:
            status = "stale"

        values = {
            "segment_id": segment_id,
            "title": _text(payload.get("title"), default=segment["title"]) or _default_title(segment_text),
            "summary": _text(payload.get("summary"), default=segment.get("summary") or "") or None,
            "text": segment_text,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "heading_path_json": _json(payload.get("heading_path", segment.get("heading_path") or []), default=[]),
            "keywords_json": _json(_keywords(payload) if "keywords" in payload or "keywords_json" in payload else segment.get("keywords") or [], default=[]),
            "boost": _bounded_float(payload.get("boost"), default=float(segment.get("boost") or 1.0), minimum=0.0, maximum=10.0),
            "visibility": visibility,
            "embedding_enabled": _bool(payload.get("embedding_enabled"), default=bool(segment.get("embedding_enabled", True))),
            "full_text_enabled": _bool(payload.get("full_text_enabled"), default=bool(segment.get("full_text_enabled", True))),
            "status": status,
            "content_hash": _content_hash(segment_text),
            "updated_at": _now(),
            "updated_by": actor_id,
            "metadata_json": _json(payload.get("metadata_json", segment.get("metadata_json") or {}), default={}),
        }
        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE knowledge_article_segments
                    SET title = :title,
                        summary = :summary,
                        text = :text,
                        start_offset = :start_offset,
                        end_offset = :end_offset,
                        heading_path_json = CAST(:heading_path_json AS jsonb),
                        keywords_json = CAST(:keywords_json AS jsonb),
                        boost = :boost,
                        visibility = :visibility,
                        embedding_enabled = :embedding_enabled,
                        full_text_enabled = :full_text_enabled,
                        status = :status,
                        content_hash = :content_hash,
                        updated_at = :updated_at,
                        updated_by = :updated_by,
                        metadata_json = CAST(:metadata_json AS jsonb)
                    WHERE segment_id = :segment_id
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        updated = _serialize_row(row)
        await self._record_audit(
            "knowledge.segmentation.segment_updated",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "segment_id": updated["segment_id"],
                "segment_type": updated["segment_type"],
                "status": updated["status"],
            },
        )
        return updated

    async def archive_segment(self, segment_id: str, *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        segment, item, version = await self._get_segment_context(segment_id)
        if actor_role not in {"admin", "support"} or not can_mutate_knowledge_visibility(actor_role, segment["visibility"]):
            raise PermissionError("segment mutation requires admin/support visibility")
        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE knowledge_article_segments
                    SET status = 'archived', updated_at = :updated_at, updated_by = :updated_by
                    WHERE segment_id = :segment_id
                    RETURNING *
                    """
                ),
                {"segment_id": segment_id, "updated_at": _now(), "updated_by": actor_id},
            )
        ).first()
        archived = _serialize_row(row)
        await self._record_audit(
            "knowledge.segmentation.segment_archived",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "segment_id": archived["segment_id"],
                "status": archived["status"],
            },
        )
        return archived

    async def auto_segment(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("segment mutation requires admin or support")
        item, version = await self._get_item_version(item_id_or_slug, payload.get("version_id"))
        now = _now()
        profile = await self._get_profile(str(payload.get("profile_code") or "default-auto"))
        sections = _split_markdown_sections(str(version.get("body") or ""))
        job_id = str(uuid.uuid4())
        job_row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_segmentation_jobs (
                        job_id, item_id, version_id, profile_id, mode, status, created_by,
                        started_at, completed_at, stats_json
                    )
                    VALUES (
                        :job_id, :item_id, :version_id, :profile_id, 'auto', 'completed',
                        :actor_id, :now, :now, CAST(:stats_json AS jsonb)
                    )
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "item_id": item["item_id"],
                    "version_id": version["version_id"],
                    "profile_id": profile.get("profile_id"),
                    "actor_id": actor_id,
                    "now": now,
                    "stats_json": _json({"segments_created": len(sections), "ai_used": False}, default={}),
                },
            )
        ).first()
        segments = []
        for section in sections:
            segments.append(
                await self._insert_segment(
                    item,
                    version,
                    {
                        "segment_type": "auto",
                        "title": section["title"],
                        "text": section["text"],
                        "start_offset": section["start_offset"],
                        "end_offset": section["end_offset"],
                        "heading_path": section["heading_path"],
                        "source": section["source"],
                        "visibility": item["visibility"],
                        "boost": profile.get("default_segment_boost") or 1.0,
                        "embedding_enabled": True,
                        "full_text_enabled": True,
                    },
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
            )
        await self._record_audit(
            "knowledge.segmentation.auto_completed",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "job_id": job_id,
                "segments_created": len(segments),
                "ai_used": False,
            },
        )
        return {"job": _serialize_row(job_row), "segments": segments}

    async def revalidate_segments(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("segment mutation requires admin or support")
        source_version_id = _text(payload.get("source_version_id"))
        target_version_id = _text(payload.get("target_version_id"))
        if not source_version_id or not target_version_id:
            raise ValueError("source_version_id and target_version_id are required")
        if source_version_id == target_version_id:
            raise ValueError("source and target versions must differ")

        item, target_version = await self._get_item_version(item_id_or_slug, target_version_id)
        _source_item, source_version = await self._get_item_version(item["item_id"], source_version_id)
        source_rows = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_article_segments
                    WHERE item_id = :item_id
                      AND version_id = :source_version_id
                      AND status IN ('active', 'draft', 'stale')
                    ORDER BY segment_index, created_at, segment_id
                    """
                ),
                {"item_id": item["item_id"], "source_version_id": source_version["version_id"]},
            )
        ).all()

        now = _now()
        job_id = str(uuid.uuid4())
        stats = {"segments_checked": len(source_rows), "segments_remapped": 0, "segments_stale": 0}
        job_row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_segmentation_jobs (
                        job_id, item_id, version_id, profile_id, mode, status, created_by,
                        started_at, completed_at, stats_json
                    )
                    VALUES (
                        :job_id, :item_id, :version_id, NULL, 'auto', 'completed',
                        :actor_id, :now, :now, CAST(:stats_json AS jsonb)
                    )
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "item_id": item["item_id"],
                    "version_id": target_version["version_id"],
                    "actor_id": actor_id,
                    "now": now,
                    "stats_json": _json(stats, default={}),
                },
            )
        ).first()

        target_body = str(target_version.get("body") or "")
        copied_segments: list[dict[str, Any]] = []
        for row in source_rows:
            source = _serialize_row(row)
            segment_text = str(source.get("text") or "")
            found_at = target_body.find(segment_text) if segment_text else -1
            matched = found_at >= 0
            if matched:
                stats["segments_remapped"] += 1
                status = "active" if source.get("status") != "draft" else "draft"
                start_offset: int | None = found_at
                end_offset: int | None = found_at + len(segment_text)
                remap_status = "matched_exact"
            else:
                stats["segments_stale"] += 1
                status = "stale"
                start_offset = None
                end_offset = None
                remap_status = "stale_no_match"

            copied_segments.append(
                await self._insert_segment(
                    item,
                    target_version,
                    {
                        "segment_type": source.get("segment_type") or "manual",
                        "title": source.get("title"),
                        "summary": source.get("summary"),
                        "text": segment_text,
                        "start_offset": start_offset,
                        "end_offset": end_offset,
                        "heading_path": source.get("heading_path") or [],
                        "keywords": source.get("keywords") or [],
                        "boost": source.get("boost") or 1.0,
                        "visibility": source.get("visibility") or item["visibility"],
                        "embedding_enabled": bool(source.get("embedding_enabled", True)),
                        "full_text_enabled": bool(source.get("full_text_enabled", True)),
                        "status": status,
                        "source": source.get("source") or "editor_selection",
                        "metadata_json": _merge_metadata(
                            source.get("metadata_json"),
                            {
                                "remap_status": remap_status,
                                "remapped_from_segment_id": source.get("segment_id"),
                                "source_version_id": source_version["version_id"],
                                "target_version_id": target_version["version_id"],
                            },
                        ),
                    },
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
            )

        await self.db.execute(
            text(
                """
                UPDATE knowledge_segmentation_jobs
                SET stats_json = CAST(:stats_json AS jsonb)
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id, "stats_json": _json(stats, default={})},
        )
        await self._record_audit(
            "knowledge.segmentation.revalidated",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "source_version_id": source_version["version_id"],
                "target_version_id": target_version["version_id"],
                "job_id": job_id,
                **stats,
            },
        )
        job = _serialize_row(job_row)
        job["stats_json"] = dict(stats)
        return {"job": job, "segments": copied_segments, "stats": stats}

    async def propose_ai_segments(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("segment mutation requires admin or support")
        item, version = await self._get_item_version(item_id_or_slug, payload.get("version_id"))
        policy = await self._get_markup_policy(item)
        if policy is None:
            await self._record_audit(
                "knowledge.segmentation.ai_blocked",
                severity="warning",
                actor_id=actor_id,
                actor_role=actor_role,
                details={
                    "item_id": item["item_id"],
                    "version_id": version["version_id"],
                    "error_code": "AI_MARKUP_POLICY_BLOCKED",
                },
            )
            raise KnowledgeSegmentationPolicyBlockedError("AI markup policy does not allow segment proposals")

        sections = _split_markdown_sections(str(version.get("body") or ""))
        now = _now()
        job_id = str(uuid.uuid4())
        stats = {"segments_proposed": len(sections), "ai_used": False, "policy_id": policy.get("policy_id")}
        job_row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_segmentation_jobs (
                        job_id, item_id, version_id, profile_id, mode, status, created_by,
                        started_at, completed_at, stats_json
                    )
                    VALUES (
                        :job_id, :item_id, :version_id, NULL, 'ai', 'completed',
                        :actor_id, :now, :now, CAST(:stats_json AS jsonb)
                    )
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "item_id": item["item_id"],
                    "version_id": version["version_id"],
                    "actor_id": actor_id,
                    "now": now,
                    "stats_json": _json(stats, default={}),
                },
            )
        ).first()

        segments = []
        for section in sections:
            segments.append(
                await self._insert_segment(
                    item,
                    version,
                    {
                        "segment_type": "ai_proposed",
                        "title": section["title"],
                        "text": section["text"],
                        "start_offset": section["start_offset"],
                        "end_offset": section["end_offset"],
                        "heading_path": section["heading_path"],
                        "source": "ai_markup",
                        "visibility": item["visibility"],
                        "status": "draft",
                        "embedding_enabled": True,
                        "full_text_enabled": True,
                        "metadata_json": {
                            "proposal_source": "policy_gated_structural_seed",
                            "policy_id": policy.get("policy_id"),
                            "job_id": job_id,
                        },
                    },
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
            )
        await self._record_audit(
            "knowledge.segmentation.ai_proposed",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "job_id": job_id,
                "segments_proposed": len(segments),
                "policy_id": policy.get("policy_id"),
                "ai_used": False,
            },
        )
        return {"job": _serialize_row(job_row), "segments": segments, "stats": stats}

    async def approve_ai_segment(self, segment_id: str, *, actor_id: str | None, actor_role: str) -> dict[str, Any]:
        segment, item, version = await self._get_segment_context(segment_id)
        if actor_role not in {"admin", "support"} or not can_mutate_knowledge_visibility(actor_role, segment["visibility"]):
            raise PermissionError("segment mutation requires admin/support visibility")
        if segment.get("segment_type") != "ai_proposed" or segment.get("status") != "draft":
            raise ValueError("only draft AI proposals can be approved")
        metadata = _merge_metadata(segment.get("metadata_json"), {"approved_at": _now().isoformat(), "approved_by": actor_id})
        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE knowledge_article_segments
                    SET segment_type = 'ai_approved',
                        status = 'active',
                        updated_at = :updated_at,
                        updated_by = :updated_by,
                        metadata_json = CAST(:metadata_json AS jsonb)
                    WHERE segment_id = :segment_id
                    RETURNING *
                    """
                ),
                {
                    "segment_id": segment_id,
                    "updated_at": _now(),
                    "updated_by": actor_id,
                    "metadata_json": _json(metadata, default={}),
                },
            )
        ).first()
        approved = _serialize_row(row)
        await self._record_audit(
            "knowledge.segmentation.proposal_approved",
            actor_id=actor_id,
            actor_role=actor_role,
            details={"item_id": item["item_id"], "version_id": version["version_id"], "segment_id": segment_id},
        )
        return approved

    async def reject_ai_segment(
        self,
        segment_id: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        segment, item, version = await self._get_segment_context(segment_id)
        if actor_role not in {"admin", "support"} or not can_mutate_knowledge_visibility(actor_role, segment["visibility"]):
            raise PermissionError("segment mutation requires admin/support visibility")
        if segment.get("segment_type") != "ai_proposed" or segment.get("status") != "draft":
            raise ValueError("only draft AI proposals can be rejected")
        reason = _text(payload.get("reason")) or None
        metadata = _merge_metadata(
            segment.get("metadata_json"),
            {"rejected_at": _now().isoformat(), "rejected_by": actor_id, "reject_reason": reason},
        )
        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE knowledge_article_segments
                    SET status = 'rejected',
                        updated_at = :updated_at,
                        updated_by = :updated_by,
                        metadata_json = CAST(:metadata_json AS jsonb)
                    WHERE segment_id = :segment_id
                    RETURNING *
                    """
                ),
                {
                    "segment_id": segment_id,
                    "updated_at": _now(),
                    "updated_by": actor_id,
                    "metadata_json": _json(metadata, default={}),
                },
            )
        ).first()
        rejected = _serialize_row(row)
        await self._record_audit(
            "knowledge.segmentation.proposal_rejected",
            actor_id=actor_id,
            actor_role=actor_role,
            details={"item_id": item["item_id"], "version_id": version["version_id"], "segment_id": segment_id, "has_reason": bool(reason)},
        )
        return rejected

    async def _get_item(self, item_id_or_slug: str) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT item_id, slug, visibility, current_version_id
                    FROM knowledge_items
                    WHERE item_id = :item_id_or_slug OR slug = :item_id_or_slug
                    """
                ),
                {"item_id_or_slug": item_id_or_slug},
            )
        ).first()
        if row is None:
            raise ValueError("knowledge item not found")
        return _serialize_row(row)

    async def _get_item_version(self, item_id_or_slug: str, version_id: Any | None) -> tuple[dict[str, Any], dict[str, Any]]:
        version_clause = "AND v.version_id = :version_id" if version_id is not None else "AND (v.version_id = i.current_version_id OR i.current_version_id IS NULL)"
        params = {"item_id_or_slug": item_id_or_slug}
        if version_id is not None:
            params["version_id"] = version_id
        row = (
            await self.db.execute(
                text(
                    f"""
                    SELECT
                        i.item_id,
                        i.slug,
                        i.visibility,
                        i.current_version_id,
                        v.version_id,
                        v.title AS version_title,
                        v.body
                    FROM knowledge_items i
                    JOIN knowledge_item_versions v ON v.item_id = i.item_id
                    WHERE (i.item_id = :item_id_or_slug OR i.slug = :item_id_or_slug)
                      {version_clause}
                    ORDER BY v.created_at DESC
                    LIMIT 1
                    """
                ),
                params,
            )
        ).first()
        if row is None:
            raise ValueError("knowledge item version not found")
        data = _serialize_row(row)
        item = {
            "item_id": data["item_id"],
            "slug": data["slug"],
            "visibility": data["visibility"],
            "current_version_id": data["current_version_id"],
        }
        version = {"version_id": data["version_id"], "title": data["version_title"], "body": data.get("body") or ""}
        return item, version

    async def _get_profile(self, profile_code: str) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_segmentation_profiles
                    WHERE code = :code AND enabled = true
                    """
                ),
                {"code": profile_code},
            )
        ).first()
        if row is not None:
            return _serialize_row(row)
        if profile_code == "default-auto":
            return dict(DEFAULT_PROFILE)
        raise ValueError("segmentation profile not found")

    async def _get_markup_policy(self, item: dict[str, Any]) -> dict[str, Any] | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM ai_policy_profiles
                    WHERE enabled = true
                      AND ai_allowed = true
                      AND auto_markup_allowed = true
                      AND (task_type IS NULL OR task_type = 'markup')
                      AND (
                        scope_type = 'global'
                        OR (scope_type = 'visibility' AND visibility = :visibility)
                      )
                    ORDER BY
                      CASE WHEN scope_type = 'visibility' THEN 0 ELSE 1 END,
                      updated_at DESC,
                      created_at DESC
                    LIMIT 1
                    """
                ),
                {"visibility": item.get("visibility")},
            )
        ).first()
        return _serialize_row(row) if row is not None else None

    async def _get_segment_context(self, segment_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT
                        s.*,
                        i.slug,
                        i.visibility AS item_visibility,
                        v.body AS version_body
                    FROM knowledge_article_segments s
                    JOIN knowledge_items i ON i.item_id = s.item_id
                    JOIN knowledge_item_versions v ON v.version_id = s.version_id
                    WHERE s.segment_id = :segment_id
                    """
                ),
                {"segment_id": segment_id},
            )
        ).first()
        if row is None:
            raise ValueError("segment not found")
        data = _serialize_row(row)
        item = {"item_id": data["item_id"], "slug": data["slug"], "visibility": data["item_visibility"]}
        version = {"version_id": data["version_id"], "body": data.get("version_body") or ""}
        return data, item, version

    async def _next_segment_index(self, version_id: str) -> int:
        value = (
            await self.db.execute(
                text("SELECT COALESCE(MAX(segment_index), 0) + 1 FROM knowledge_article_segments WHERE version_id = :version_id"),
                {"version_id": version_id},
            )
        ).scalar()
        return int(value or 1)

    async def _insert_segment(
        self,
        item: dict[str, Any],
        version: dict[str, Any],
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        segment_text = _text(payload.get("text"))
        if not segment_text:
            raise ValueError("segment text is required")

        body = str(version.get("body") or "")
        start_offset = payload.get("start_offset")
        end_offset = payload.get("end_offset")
        if start_offset is None or end_offset is None:
            found_at = body.find(segment_text)
            if found_at >= 0:
                start_offset = found_at
                end_offset = found_at + len(segment_text)
        try:
            start = int(start_offset) if start_offset is not None else None
            end = int(end_offset) if end_offset is not None else None
        except (TypeError, ValueError):
            start = None
            end = None

        status = _text(payload.get("status"), default="active") or "active"
        if start is not None and end is not None and body[start:end] != segment_text:
            status = "stale"

        visibility = _text(payload.get("visibility"), default=item["visibility"]) or item["visibility"]
        if not can_mutate_knowledge_visibility(actor_role, visibility):
            raise ValueError("unsupported segment visibility")

        now = _now()
        values = {
            "segment_id": str(uuid.uuid4()),
            "item_id": item["item_id"],
            "version_id": version["version_id"],
            "segment_index": await self._next_segment_index(version["version_id"]),
            "segment_type": _text(payload.get("segment_type"), default="manual") or "manual",
            "title": _text(payload.get("title")) or _default_title(segment_text),
            "summary": _text(payload.get("summary")) or None,
            "text": segment_text,
            "start_offset": start,
            "end_offset": end,
            "heading_path_json": _json(payload.get("heading_path", payload.get("heading_path_json")), default=[]),
            "keywords_json": _json(_keywords(payload), default=[]),
            "boost": _bounded_float(payload.get("boost"), default=1.0, minimum=0.0, maximum=10.0),
            "visibility": visibility,
            "embedding_enabled": _bool(payload.get("embedding_enabled"), default=True),
            "full_text_enabled": _bool(payload.get("full_text_enabled"), default=True),
            "status": status,
            "source": _text(payload.get("source"), default="editor_selection") or "editor_selection",
            "content_hash": _content_hash(segment_text),
            "created_at": now,
            "updated_at": now,
            "created_by": actor_id,
            "updated_by": actor_id,
            "metadata_json": _json(payload.get("metadata_json"), default={}),
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_article_segments (
                        segment_id, item_id, version_id, segment_index, segment_type, title,
                        summary, text, start_offset, end_offset, heading_path_json, keywords_json,
                        boost, visibility, embedding_enabled, full_text_enabled, status, source,
                        content_hash, created_at, updated_at, created_by, updated_by, metadata_json
                    )
                    VALUES (
                        :segment_id, :item_id, :version_id, :segment_index, :segment_type, :title,
                        :summary, :text, :start_offset, :end_offset, CAST(:heading_path_json AS jsonb),
                        CAST(:keywords_json AS jsonb), :boost, :visibility, :embedding_enabled,
                        :full_text_enabled, :status, :source, :content_hash, :created_at, :updated_at,
                        :created_by, :updated_by, CAST(:metadata_json AS jsonb)
                    )
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        return _serialize_row(row)

    async def _record_audit(
        self,
        event_type: str,
        *,
        severity: str = "info",
        actor_id: str | None,
        actor_role: str,
        details: dict[str, Any],
    ) -> None:
        await self.db.execute(
            text(
                """
                INSERT INTO agent_runtime_audit (
                    device_id, event_type, severity, source, actor_id, actor_role,
                    details_json, created_at
                )
                VALUES (
                    'server', :event_type, :severity, 'knowledge_segmentation',
                    :actor_id, :actor_role, CAST(:details_json AS jsonb), :created_at
                )
                """
            ),
            {
                "event_type": event_type,
                "severity": severity,
                "actor_id": actor_id,
                "actor_role": actor_role,
                "details_json": _json(details, default={}),
                "created_at": _now(),
            },
        )
