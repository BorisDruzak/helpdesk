from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.search_service import KnowledgeSearchService


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


async def _published_item(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    body: str,
    visibility: str,
) -> tuple[dict, dict, dict]:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": "vector-search", "title": "Vector search", "visibility": "requester", "lifecycle_status": "active", "allow_rag": True},
        actor_id="admin",
    )
    item = await repo.create_item_draft(
        {
            "space_code": "vector-search",
            "slug": slug,
            "item_type": "article",
            "title": title,
            "summary": title,
            "visibility": visibility,
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
        actor_id="admin",
        actor_role="admin",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": title, "body_format": "markdown", "body": body},
        actor_id="admin",
        actor_role="admin",
    )
    await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin", actor_role="admin")
    chunk = (
        await session.execute(
            text(
                """
                SELECT chunk_id, content_hash, visibility, text
                FROM knowledge_chunks
                WHERE item_id = :item_id AND version_id = :version_id
                ORDER BY chunk_index
                LIMIT 1
                """
            ),
            {"item_id": item["item_id"], "version_id": version["version_id"]},
        )
    ).mappings().first()
    assert chunk is not None
    return item, version, dict(chunk)


async def _insert_embedding(
    session: AsyncSession,
    *,
    item: dict,
    version: dict,
    chunk: dict,
    vector: list[float],
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO knowledge_chunk_embeddings (
                embedding_id, chunk_id, item_id, version_id, embedding_model,
                embedding_dimensions, embedding_vector, content_hash,
                embedding_input_hash, visibility, status, indexed_at,
                metadata_json, created_at, updated_at
            )
            VALUES (
                :embedding_id, :chunk_id, :item_id, :version_id, 'test-vector-model',
                :embedding_dimensions, CAST(:embedding_vector AS jsonb), :content_hash,
                :embedding_input_hash, :visibility, 'indexed', CURRENT_TIMESTAMP,
                '{}'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """
        ),
        {
            "embedding_id": str(uuid.uuid4()),
            "chunk_id": chunk["chunk_id"],
            "item_id": item["item_id"],
            "version_id": version["version_id"],
            "embedding_dimensions": len(vector),
            "embedding_vector": json.dumps(vector),
            "content_hash": chunk["content_hash"],
            "embedding_input_hash": "test-input",
            "visibility": chunk["visibility"],
        },
    )


@pytest.mark.asyncio
async def test_vector_search_merges_jsonb_embeddings_without_raw_vector(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        target_item, target_version, target_chunk = await _published_item(
            session,
            slug="vector-semantic-target",
            title="Router recovery",
            body="Restart the edge router and verify the uplink indicator.",
            visibility="requester",
        )
        other_item, other_version, other_chunk = await _published_item(
            session,
            slug="vector-semantic-other",
            title="Printer recovery",
            body="Replace paper and clear the printer queue.",
            visibility="requester",
        )
        await _insert_embedding(session, item=target_item, version=target_version, chunk=target_chunk, vector=[0.95, 0.05])
        await _insert_embedding(session, item=other_item, version=other_version, chunk=other_chunk, vector=[0.05, 0.95])
        await session.commit()

    async with session_maker() as session:
        requester_results = await KnowledgeSearchService(session).search(
            query="zeromatch-vector-query",
            actor_role="requester",
            vector_enabled=True,
            query_vector=[0.9, 0.1],
            limit=5,
        )
        support_results = await KnowledgeSearchService(session).search(
            query="zeromatch-vector-query",
            actor_role="support",
            vector_enabled=True,
            query_vector=[0.9, 0.1],
            limit=5,
        )

    assert [item["slug"] for item in requester_results][:1] == ["vector-semantic-target"]
    assert "embedding_vector" not in requester_results[0]
    assert [item["slug"] for item in support_results][:1] == ["vector-semantic-target"]
    assert support_results[0]["retrieval_source"] == "vector"
    assert support_results[0]["vector_score"] > 0.9
    assert "embedding_vector" not in support_results[0]


@pytest.mark.asyncio
async def test_vector_search_keeps_acl_before_similarity_scoring(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        requester_item, requester_version, requester_chunk = await _published_item(
            session,
            slug="vector-requester-allowed",
            title="Requester visible article",
            body="Visible article body.",
            visibility="requester",
        )
        support_item, support_version, support_chunk = await _published_item(
            session,
            slug="vector-support-hidden",
            title="Support hidden runbook",
            body="Internal runbook body.",
            visibility="support_internal",
        )
        await _insert_embedding(session, item=requester_item, version=requester_version, chunk=requester_chunk, vector=[0.2, 0.8])
        await _insert_embedding(session, item=support_item, version=support_version, chunk=support_chunk, vector=[0.99, 0.01])
        await session.commit()

    async with session_maker() as session:
        requester_results = await KnowledgeSearchService(session).search(
            query="vector-acl",
            actor_role="requester",
            vector_enabled=True,
            query_vector=[1.0, 0.0],
            limit=5,
        )
        support_results = await KnowledgeSearchService(session).search(
            query="vector-acl",
            actor_role="support",
            vector_enabled=True,
            query_vector=[1.0, 0.0],
            limit=5,
        )

    assert "vector-support-hidden" not in {item["slug"] for item in requester_results}
    assert [item["slug"] for item in support_results][:1] == ["vector-support-hidden"]


@pytest.mark.asyncio
async def test_web_search_uses_vector_settings_when_query_vector_is_supplied(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item, version, chunk = await _published_item(
            session,
            slug="vector-web-search",
            title="Vector web search",
            body="A body without the submitted semantic query words.",
            visibility="requester",
        )
        await _insert_embedding(session, item=item, version=version, chunk=chunk, vector=[0.8, 0.2])
        await session.commit()

    settings_resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=ADMIN_HEADERS,
        json={"search_mode": "hybrid_vector", "vector_enabled": True, "keyword_enabled": True, "vector_weight": 1.5},
    )
    assert settings_resp.status == 200

    search_resp = await test_client.post(
        "/api/web/knowledge/search",
        headers=SUPPORT_HEADERS,
        json={"query": "semantic-query-without-keyword", "query_vector": [0.8, 0.2]},
    )
    assert search_resp.status == 200
    payload = await search_resp.json()

    assert payload["status"] == "ok"
    assert payload["effective_mode"] == "hybrid_vector"
    assert payload["ai_used"] is True
    assert [item["slug"] for item in payload["results"]][:1] == ["vector-web-search"]
    assert payload["results"][0]["retrieval_source"] == "vector"
    assert "embedding_vector" not in payload["results"][0]
