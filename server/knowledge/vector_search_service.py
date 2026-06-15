from __future__ import annotations

import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.contracts import actor_visible_visibilities
from knowledge.rag_policy import evaluate_rag_eligibility


def _coerce_vector(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    vector: list[float] = []
    for item in value[:4096]:
        try:
            number = float(item)
        except (TypeError, ValueError):
            return []
        if not math.isfinite(number):
            return []
        vector.append(number)
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size]))
    right_norm = math.sqrt(sum(value * value for value in right[:size]))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


class KnowledgeVectorSearchService:
    """JSONB-vector fallback for environments without pgvector."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        *,
        query_vector: list[float],
        actor_role: str,
        limit: int = 10,
        min_score: float = 0.01,
    ) -> list[dict[str, Any]]:
        vector = _coerce_vector(query_vector)
        if not vector:
            return []
        allowed = tuple(actor_visible_visibilities(actor_role))
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT
                        e.embedding_id,
                        e.chunk_id,
                        e.segment_id,
                        e.item_id,
                        e.version_id,
                        e.embedding_model,
                        e.embedding_dimensions,
                        e.embedding_vector,
                        e.content_hash,
                        e.visibility,
                        e.indexed_at,
                        i.slug,
                        i.title,
                        i.visibility AS item_visibility,
                        i.metadata_json AS item_metadata_json,
                        sp.allow_rag AS space_allow_rag,
                        c.text AS chunk_text,
                        c.heading AS chunk_heading
                    FROM knowledge_chunk_embeddings e
                    JOIN knowledge_items i ON i.item_id = e.item_id
                    JOIN knowledge_spaces sp ON sp.space_id = i.space_id
                    JOIN knowledge_chunks c ON c.chunk_id = e.chunk_id
                    WHERE e.status = 'indexed'
                      AND e.embedding_vector IS NOT NULL
                      AND i.status = 'published'
                      AND i.current_version_id = e.version_id
                      AND i.visibility = ANY(:allowed)
                      AND e.visibility = ANY(:allowed)
                      AND c.visibility = ANY(:allowed)
                      AND c.content_hash = e.content_hash
                    ORDER BY e.indexed_at DESC NULLS LAST, e.embedding_id DESC
                    LIMIT :candidate_limit
                    """
                ),
                {"allowed": list(allowed), "candidate_limit": max(20, min(int(limit) * 20, 500))},
            )
        ).mappings().all()

        scored: list[dict[str, Any]] = []
        for row in rows:
            decision = evaluate_rag_eligibility(
                {
                    "item_id": row.get("item_id"),
                    "slug": row.get("slug"),
                    "title": row.get("title"),
                    "visibility": row.get("item_visibility"),
                    "metadata_json": row.get("item_metadata_json"),
                },
                {"allow_rag": row.get("space_allow_rag")},
                actor_role=actor_role,
            )
            if not decision.allowed:
                continue
            embedding_vector = _coerce_vector(row.get("embedding_vector"))
            score = cosine_similarity(vector, embedding_vector)
            if score < min_score:
                continue
            scored.append(
                {
                    "embedding_id": row["embedding_id"],
                    "chunk_id": row["chunk_id"],
                    "segment_id": row["segment_id"],
                    "item_id": row["item_id"],
                    "version_id": row["version_id"],
                    "embedding_model": row["embedding_model"],
                    "embedding_dimensions": row["embedding_dimensions"],
                    "content_hash": row["content_hash"],
                    "visibility": row["visibility"],
                    "chunk_text": row["chunk_text"],
                    "chunk_heading": row["chunk_heading"],
                    "score": score,
                }
            )
        scored.sort(key=lambda item: (-float(item["score"]), str(item.get("chunk_heading") or ""), str(item["chunk_id"])))
        return scored[: max(1, min(int(limit), 50))]
