from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from ai.contracts import AIModelProfile, AIProviderConfig
from ai.openrouter_client import OpenRouterClient
from knowledge.visibility import actor_visible_visibilities


Transport = Callable[..., Awaitable[dict[str, Any]]]

REQUESTER_SAFE_VISIBILITIES = {"public", "requester", "agent_requester_safe"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any, *, default: Any) -> str:
    return json.dumps(value if value is not None else default, ensure_ascii=False, sort_keys=True)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _serialize_row(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif hasattr(value, "__float__") and value.__class__.__module__ == "decimal":
            data[key] = float(value)
    return data


def _safe_embedding(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data.pop("embedding_vector", None)
    return data


def _resolve_secret_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if value.startswith("env:"):
        return os.getenv(value[4:])
    return None


class KnowledgeEmbeddingInputBuilder:
    """Builds safe provider input from chunk and article/segment metadata."""

    def build(self, row: dict[str, Any]) -> dict[str, Any]:
        keywords = row.get("keywords_json") if isinstance(row.get("keywords_json"), list) else []
        heading_path = row.get("heading_path_json") if isinstance(row.get("heading_path_json"), list) else []
        parts = [
            f"Статья: {row.get('item_title') or row.get('version_title') or ''}".strip(),
            f"Сегмент: {row.get('segment_title') or row.get('heading') or ''}".strip(),
            f"Кратко: {row.get('segment_summary') or ''}".strip(),
            f"Ключевые слова: {', '.join(str(item) for item in keywords)}" if keywords else "",
            f"Путь: {' / '.join(str(item) for item in heading_path)}" if heading_path else "",
            str(row.get("text") or "").strip(),
        ]
        input_text = "\n".join(part for part in parts if part)
        metadata = {
            "chunk_id": row.get("chunk_id"),
            "segment_id": row.get("segment_id"),
            "item_id": row.get("item_id"),
            "version_id": row.get("version_id"),
            "visibility": row.get("visibility"),
            "source": "knowledge_embedding_input",
        }
        return {"input_text": input_text, "input_hash": _hash(input_text), "metadata": metadata}


class KnowledgeEmbeddingService:
    def __init__(self, db: AsyncSession | AsyncConnection, *, transport: Transport | None = None):
        self.db = db
        self.transport = transport
        self.input_builder = KnowledgeEmbeddingInputBuilder()

    async def list_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_index_jobs
                    ORDER BY COALESCE(started_at, completed_at) DESC NULLS LAST, job_id DESC
                    LIMIT :limit
                    """
                ),
                {"limit": max(1, min(int(limit), 200))},
            )
        ).all()
        return [_serialize_row(row) for row in rows]

    async def status(self) -> dict[str, Any]:
        embedding_rows = (
            await self.db.execute(
                text("SELECT status, COUNT(*) AS count FROM knowledge_chunk_embeddings GROUP BY status ORDER BY status")
            )
        ).mappings().all()
        job_rows = (
            await self.db.execute(
                text("SELECT status, COUNT(*) AS count FROM knowledge_index_jobs GROUP BY status ORDER BY status")
            )
        ).mappings().all()
        profile = await self._get_embedding_profile()
        settings = await self._embedding_settings()
        return {
            "embeddings": {str(row["status"]): int(row["count"]) for row in embedding_rows},
            "jobs": {str(row["status"]): int(row["count"]) for row in job_rows},
            "vector_enabled": bool(settings.get("vector_enabled")),
            "embedding_model": profile.get("model_name") if profile else None,
            "model_profile_id": profile.get("profile_id") if profile else None,
        }

    async def reindex_item(
        self,
        item_id_or_slug: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("knowledge indexing requires admin or support")
        item = await self._get_item(item_id_or_slug)
        version_id = str(payload.get("version_id") or "").strip() or None
        chunks = await self._load_chunks(item["item_id"], version_id, actor_role=actor_role)
        job = await self._create_job("item", item["item_id"], actor_id=actor_id, metadata={"version_id": version_id})
        return await self._index_chunks(
            job,
            chunks,
            actor_id=actor_id,
            actor_role=actor_role,
            audit_details={"item_id": item["item_id"], "version_id": version_id},
        )

    async def reindex_segment(
        self,
        segment_id: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("knowledge indexing requires admin or support")
        segment = await self._get_segment(segment_id)
        chunks = await self._load_chunks(
            segment["item_id"],
            str(payload.get("version_id") or segment["version_id"]),
            actor_role=actor_role,
            segment_id=segment["segment_id"],
        )
        job = await self._create_job("segment", segment["segment_id"], actor_id=actor_id, metadata={"version_id": segment["version_id"]})
        return await self._index_chunks(
            job,
            chunks,
            actor_id=actor_id,
            actor_role=actor_role,
            audit_details={"item_id": segment["item_id"], "version_id": segment["version_id"], "segment_id": segment["segment_id"]},
        )

    async def reindex_space(
        self,
        space_id_or_code: str,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("knowledge indexing requires admin or support")
        space = await self._get_space(space_id_or_code)
        chunks = await self._load_scope_chunks(actor_role=actor_role, space_id=space["space_id"])
        job = await self._create_job("space", space["space_id"], actor_id=actor_id, metadata={"space_code": space.get("code")})
        return await self._index_chunks(
            job,
            chunks,
            actor_id=actor_id,
            actor_role=actor_role,
            audit_details={"space_id": space["space_id"], "space_code": space.get("code")},
        )

    async def reindex_all(
        self,
        payload: dict[str, Any],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role not in {"admin", "support"}:
            raise PermissionError("knowledge indexing requires admin or support")
        limit = int(payload.get("limit") or 500)
        chunks = await self._load_scope_chunks(actor_role=actor_role, limit=max(1, min(limit, 2000)))
        job = await self._create_job("all", "all", actor_id=actor_id, metadata={"limit": limit})
        return await self._index_chunks(
            job,
            chunks,
            actor_id=actor_id,
            actor_role=actor_role,
            audit_details={"limit": limit},
        )

    async def _index_chunks(
        self,
        job: dict[str, Any],
        chunks: list[dict[str, Any]],
        *,
        actor_id: str | None,
        actor_role: str,
        audit_details: dict[str, Any],
    ) -> dict[str, Any]:
        await self._record_audit(
            "knowledge.embedding.index_started",
            actor_id=actor_id,
            actor_role=actor_role,
            details={"job_id": job["job_id"], "chunks_seen": len(chunks), **audit_details},
        )

        stats = {
            "chunks_seen": len(chunks),
            "indexed_embeddings": 0,
            "disabled_embeddings": 0,
            "failed_embeddings": 0,
            "stale_embeddings": 0,
        }
        embeddings: list[dict[str, Any]] = []
        settings = await self._embedding_settings()
        profile = await self._get_embedding_profile()
        provider = await self._get_provider(profile["provider_id"]) if profile else None

        for chunk in chunks:
            await self._mark_stale_if_needed(chunk, stats, actor_id=actor_id, actor_role=actor_role)
            policy_allowed = await self._embedding_allowed(chunk, settings=settings)
            metadata = chunk.get("metadata_json") if isinstance(chunk.get("metadata_json"), dict) else {}
            if not policy_allowed or metadata.get("embedding_status") == "disabled":
                embeddings.append(
                    await self._insert_embedding(
                        chunk,
                        status="disabled",
                        model_profile=None,
                        embedding_model=None,
                        vector=None,
                        error_redacted=None,
                    )
                )
                stats["disabled_embeddings"] += 1
                await self._record_audit(
                    "knowledge.embedding.policy_blocked",
                    severity="warning",
                    actor_id=actor_id,
                    actor_role=actor_role,
                    details={"job_id": job["job_id"], "chunk_id": chunk["chunk_id"], "visibility": chunk["visibility"]},
                )
                continue

            if not profile or not provider:
                embeddings.append(
                    await self._insert_embedding(
                        chunk,
                        status="failed",
                        model_profile=profile,
                        embedding_model=profile.get("model_name") if profile else None,
                        vector=None,
                        error_redacted="embedding provider unavailable",
                    )
                )
                stats["failed_embeddings"] += 1
                continue

            api_key = _resolve_secret_ref(provider.get("api_key_secret_ref"))
            if not api_key or self.transport is None:
                embeddings.append(
                    await self._insert_embedding(
                        chunk,
                        status="failed",
                        model_profile=profile,
                        embedding_model=profile.get("model_name"),
                        vector=None,
                        error_redacted="embedding provider unavailable",
                    )
                )
                stats["failed_embeddings"] += 1
                continue

            built = self.input_builder.build(chunk)
            try:
                client = OpenRouterClient(
                    AIProviderConfig(
                        provider_id=str(provider["provider_id"]),
                        code=str(provider["code"]),
                        base_url=str(provider.get("base_url") or "https://openrouter.ai/api/v1"),
                        api_key=api_key,
                    ),
                    transport=self.transport,
                )
                result = await client.generate_embedding(
                    AIModelProfile(
                        profile_id=str(profile["profile_id"]),
                        provider_id=str(profile["provider_id"]),
                        task_type="embedding",
                        model_name=str(profile["model_name"]),
                        timeout_ms=int(profile.get("timeout_ms") or 30_000),
                    ),
                    input_text=built["input_text"],
                )
                embedding = await self._insert_embedding(
                    chunk,
                    status="indexed",
                    model_profile=profile,
                    embedding_model=str(profile["model_name"]),
                    vector=result.embedding,
                    error_redacted=None,
                    input_hash=built["input_hash"],
                    input_metadata=built["metadata"],
                )
                await self.db.execute(
                    text(
                        """
                        UPDATE knowledge_chunks
                        SET embedding_ref = :embedding_ref,
                            embedding_model = :embedding_model
                        WHERE chunk_id = :chunk_id
                        """
                    ),
                    {
                        "embedding_ref": f"embedding:{embedding['embedding_id']}",
                        "embedding_model": str(profile["model_name"]),
                        "chunk_id": chunk["chunk_id"],
                    },
                )
                embeddings.append(embedding)
                stats["indexed_embeddings"] += 1
            except Exception:
                embeddings.append(
                    await self._insert_embedding(
                        chunk,
                        status="failed",
                        model_profile=profile,
                        embedding_model=str(profile["model_name"]),
                        vector=None,
                        error_redacted="embedding provider unavailable",
                    )
                )
                stats["failed_embeddings"] += 1

        status = "failed" if stats["failed_embeddings"] and not stats["indexed_embeddings"] else "completed"
        error_redacted = "embedding provider unavailable" if status == "failed" else None
        job = await self._complete_job(job["job_id"], status=status, stats=stats, error_redacted=error_redacted, model_profile=profile)
        if stats["failed_embeddings"]:
            await self._record_audit(
                "knowledge.embedding.provider_unavailable",
                severity="warning",
                actor_id=actor_id,
                actor_role=actor_role,
                details={"job_id": job["job_id"], "failed_embeddings": stats["failed_embeddings"]},
            )
        if stats["indexed_embeddings"]:
            await self._record_audit(
                "knowledge.embedding.index_completed",
                actor_id=actor_id,
                actor_role=actor_role,
                details={"job_id": job["job_id"], "indexed_embeddings": stats["indexed_embeddings"]},
            )
        return {"job": job, "embeddings": [_safe_embedding(row) for row in embeddings], "stats": stats}

    async def _get_item(self, item_id_or_slug: str) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_items
                    WHERE item_id = :ref OR slug = :ref
                    """
                ),
                {"ref": item_id_or_slug},
            )
        ).first()
        if row is None:
            raise ValueError("knowledge item not found")
        return _serialize_row(row)

    async def _get_segment(self, segment_id: str) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text("SELECT * FROM knowledge_article_segments WHERE segment_id = :segment_id"),
                {"segment_id": segment_id},
            )
        ).first()
        if row is None:
            raise ValueError("knowledge segment not found")
        return _serialize_row(row)

    async def _get_space(self, space_id_or_code: str) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text("SELECT * FROM knowledge_spaces WHERE space_id = :ref OR code = :ref"),
                {"ref": space_id_or_code},
            )
        ).first()
        if row is None:
            raise ValueError("knowledge space not found")
        return _serialize_row(row)

    async def _load_chunks(
        self,
        item_id: str,
        version_id: str | None,
        *,
        actor_role: str,
        segment_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._load_scope_chunks(
            actor_role=actor_role,
            item_id=item_id,
            version_id=version_id,
            segment_id=segment_id,
        )

    async def _load_scope_chunks(
        self,
        *,
        actor_role: str,
        item_id: str | None = None,
        version_id: str | None = None,
        segment_id: str | None = None,
        space_id: str | None = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        allowed = tuple(actor_visible_visibilities(actor_role))
        rows = (
            await self.db.execute(
                text(
                    """
                    SELECT
                        c.*,
                        i.title AS item_title,
                        v.title AS version_title,
                        s.segment_id,
                        s.title AS segment_title,
                        s.summary AS segment_summary,
                        s.keywords_json,
                        s.heading_path_json,
                        s.embedding_enabled
                    FROM knowledge_chunks c
                    JOIN knowledge_items i ON i.item_id = c.item_id
                    JOIN knowledge_item_versions v ON v.version_id = c.version_id
                    LEFT JOIN knowledge_article_segments s ON s.segment_id = c.metadata_json->>'segment_id'
                    WHERE (CAST(:item_id AS text) IS NULL OR c.item_id = CAST(:item_id AS text))
                      AND (CAST(:version_id AS text) IS NULL OR c.version_id = CAST(:version_id AS text))
                      AND (CAST(:segment_id AS text) IS NULL OR c.metadata_json->>'segment_id' = CAST(:segment_id AS text))
                      AND (CAST(:space_id AS text) IS NULL OR i.space_id = CAST(:space_id AS text))
                      AND c.visibility = ANY(:allowed)
                    ORDER BY
                      CASE WHEN c.metadata_json->>'source' = 'article_segment' THEN 0 ELSE 1 END,
                      c.version_id, c.chunk_index, c.chunk_id
                    LIMIT :limit
                    """
                ),
                {
                    "item_id": item_id,
                    "version_id": version_id,
                    "segment_id": segment_id,
                    "space_id": space_id,
                    "allowed": list(allowed),
                    "limit": max(1, min(int(limit), 5000)),
                },
            )
        ).all()
        return [_serialize_row(row) for row in rows]

    async def _embedding_settings(self) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM knowledge_search_settings
                    WHERE scope_type = 'global'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                )
            )
        ).first()
        return _serialize_row(row) if row else {"vector_enabled": False}

    async def _embedding_allowed(self, chunk: dict[str, Any], *, settings: dict[str, Any]) -> bool:
        if not bool(settings.get("vector_enabled", False)):
            return False
        if chunk.get("visibility") == "security_restricted":
            return False
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM ai_policy_profiles
                    WHERE enabled = true
                      AND ai_allowed = true
                      AND embedding_allowed = true
                      AND (task_type IS NULL OR task_type = 'embedding')
                      AND (
                        scope_type = 'global'
                        OR (scope_type = 'visibility' AND visibility = :visibility)
                        OR (scope_type = 'space' AND space_id = (SELECT space_id FROM knowledge_items WHERE item_id = :item_id))
                      )
                    ORDER BY
                      CASE scope_type WHEN 'visibility' THEN 0 WHEN 'space' THEN 1 ELSE 2 END,
                      updated_at DESC
                    LIMIT 1
                    """
                ),
                {"visibility": chunk.get("visibility"), "item_id": chunk.get("item_id")},
            )
        ).first()
        if row is None:
            return False
        policy = _serialize_row(row)
        if chunk.get("visibility") in REQUESTER_SAFE_VISIBILITIES and not bool(policy.get("allow_cloud_for_requester_safe", False)):
            return False
        return True

    async def _get_embedding_profile(self) -> dict[str, Any] | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM ai_model_profiles
                    WHERE task_type = 'embedding'
                      AND enabled = true
                    ORDER BY is_default DESC, created_at DESC, profile_id DESC
                    LIMIT 1
                    """
                )
            )
        ).first()
        return _serialize_row(row) if row else None

    async def _get_provider(self, provider_id: str) -> dict[str, Any] | None:
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT *
                    FROM ai_providers
                    WHERE provider_id = :provider_id
                      AND enabled = true
                      AND provider_type = 'openrouter'
                    """
                ),
                {"provider_id": provider_id},
            )
        ).first()
        return _serialize_row(row) if row else None

    async def _create_job(self, scope_type: str, scope_ref: str, *, actor_id: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = _now()
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_index_jobs (
                        job_id, scope_type, scope_ref, status, requested_by, started_at, stats_json, metadata_json
                    )
                    VALUES (
                        :job_id, :scope_type, :scope_ref, 'running', :actor_id, :now, '{}'::jsonb, CAST(:metadata_json AS jsonb)
                    )
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "scope_type": scope_type,
                    "scope_ref": scope_ref,
                    "actor_id": actor_id,
                    "now": now,
                    "metadata_json": _json(metadata, default={}),
                },
            )
        ).first()
        return _serialize_row(row)

    async def _complete_job(
        self,
        job_id: str,
        *,
        status: str,
        stats: dict[str, Any],
        error_redacted: str | None,
        model_profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text(
                    """
                    UPDATE knowledge_index_jobs
                    SET status = :status,
                        completed_at = :now,
                        stats_json = CAST(:stats_json AS jsonb),
                        error_redacted = :error_redacted,
                        model_profile_id = :model_profile_id
                    WHERE job_id = :job_id
                    RETURNING *
                    """
                ),
                {
                    "job_id": job_id,
                    "status": status,
                    "now": _now(),
                    "stats_json": _json(stats, default={}),
                    "error_redacted": error_redacted,
                    "model_profile_id": model_profile.get("profile_id") if model_profile else None,
                },
            )
        ).first()
        return _serialize_row(row)

    async def _insert_embedding(
        self,
        chunk: dict[str, Any],
        *,
        status: str,
        model_profile: dict[str, Any] | None,
        embedding_model: str | None,
        vector: list[float] | None,
        error_redacted: str | None,
        input_hash: str | None = None,
        input_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        embedding_id = str(uuid.uuid4())
        now = _now()
        metadata = dict(input_metadata or {})
        metadata["source"] = "knowledge_embedding"
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_chunk_embeddings (
                        embedding_id, chunk_id, segment_id, item_id, version_id,
                        model_profile_id, embedding_model, embedding_dimensions,
                        embedding_vector, content_hash, embedding_input_hash, visibility,
                        status, indexed_at, error_redacted, metadata_json, created_at, updated_at
                    )
                    VALUES (
                        :embedding_id, :chunk_id, :segment_id, :item_id, :version_id,
                        :model_profile_id, :embedding_model, :embedding_dimensions,
                        CAST(:embedding_vector AS jsonb), :content_hash, :embedding_input_hash, :visibility,
                        :status, :indexed_at, :error_redacted, CAST(:metadata_json AS jsonb), :now, :now
                    )
                    RETURNING *
                    """
                ),
                {
                    "embedding_id": embedding_id,
                    "chunk_id": chunk["chunk_id"],
                    "segment_id": chunk.get("segment_id"),
                    "item_id": chunk["item_id"],
                    "version_id": chunk["version_id"],
                    "model_profile_id": model_profile.get("profile_id") if model_profile else None,
                    "embedding_model": embedding_model,
                    "embedding_dimensions": len(vector) if vector is not None else None,
                    "embedding_vector": _json(vector, default=None),
                    "content_hash": chunk["content_hash"],
                    "embedding_input_hash": input_hash,
                    "visibility": chunk["visibility"],
                    "status": status,
                    "indexed_at": now if status == "indexed" else None,
                    "error_redacted": error_redacted,
                    "metadata_json": _json(metadata, default={}),
                    "now": now,
                },
            )
        ).first()
        return _serialize_row(row)

    async def _mark_stale_if_needed(
        self,
        chunk: dict[str, Any],
        stats: dict[str, int],
        *,
        actor_id: str | None,
        actor_role: str,
    ) -> None:
        result = await self.db.execute(
            text(
                """
                UPDATE knowledge_chunk_embeddings
                SET status = 'stale',
                    updated_at = :now
                WHERE chunk_id = :chunk_id
                  AND status = 'indexed'
                  AND content_hash <> :content_hash
                RETURNING embedding_id
                """
            ),
            {"chunk_id": chunk["chunk_id"], "content_hash": chunk["content_hash"], "now": _now()},
        )
        rows = result.all()
        if rows:
            stats["stale_embeddings"] += len(rows)
            await self._record_audit(
                "knowledge.embedding.stale_detected",
                severity="warning",
                actor_id=actor_id,
                actor_role=actor_role,
                details={"chunk_id": chunk["chunk_id"], "stale_embeddings": len(rows)},
            )

    async def _record_audit(
        self,
        event_type: str,
        *,
        actor_id: str | None,
        actor_role: str,
        details: dict[str, Any],
        severity: str = "info",
    ) -> None:
        await self.db.execute(
            text(
                """
                INSERT INTO agent_runtime_audit (
                    device_id, event_type, severity, source, actor_id, actor_role,
                    details_json, created_at
                )
                VALUES (
                    'server', :event_type, :severity, 'knowledge_embedding',
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
