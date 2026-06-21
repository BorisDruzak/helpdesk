from __future__ import annotations

import os

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}


async def _create_article(test_client, *, slug: str = "embedding-vpn") -> tuple[dict, dict]:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": f"{slug}-space", "title": f"{slug} space", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": f"{slug}-space",
            "slug": slug,
            "item_type": "article",
            "title": "VPN article",
            "summary": "Article for embedding tests",
            "visibility": "requester",
        },
    )
    assert item_resp.status == 200
    item = (await item_resp.json())["item"]
    body = "# VPN\n\nCheck tunnel adapter and DNS suffix before escalation."
    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": "VPN article", "body_format": "markdown", "body": body},
    )
    assert version_resp.status == 200
    return item, (await version_resp.json())["version"]


async def _create_segment_chunk(test_client, item: dict, version: dict, *, embedding_enabled: bool = True) -> dict:
    segment_text = "Check tunnel adapter and DNS suffix before escalation."
    create_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments",
        headers=ADMIN_HEADERS,
        json={
            "version_id": version["version_id"],
            "title": "VPN checks",
            "summary": "Adapter and DNS prerequisites",
            "text": segment_text,
            "keywords": ["vpn", "dns"],
            "visibility": "requester",
            "embedding_enabled": embedding_enabled,
            "full_text_enabled": True,
        },
    )
    assert create_resp.status == 200
    sync_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/segments/index-sync",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert sync_resp.status == 200
    payload = await sync_resp.json()
    assert payload["stats"]["chunks_synced"] == 1
    return payload["chunks"][0]


async def _enable_vector_settings(test_client) -> None:
    resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=ADMIN_HEADERS,
        json={
            "search_mode": "hybrid_vector",
            "keyword_enabled": True,
            "full_text_enabled": True,
            "vector_enabled": True,
        },
    )
    assert resp.status == 200


@pytest.mark.asyncio
async def test_knowledge_embedding_tables_exist_after_migration(test_engine) -> None:
    async with test_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name IN ('knowledge_chunk_embeddings', 'knowledge_index_jobs')"
                )
            )
        ).scalars().all()

    assert {"knowledge_chunk_embeddings", "knowledge_index_jobs"} <= set(rows)


@pytest.mark.asyncio
async def test_reindex_item_with_embeddings_disabled_marks_chunks_disabled(test_client, test_engine) -> None:
    item, version = await _create_article(test_client, slug="embedding-disabled")
    chunk = await _create_segment_chunk(test_client, item, version)

    resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-item",
        headers=ADMIN_HEADERS,
        json={"item_id": item["item_id"], "version_id": version["version_id"]},
    )
    assert resp.status == 200
    payload = await resp.json()

    assert payload["job"]["status"] == "completed"
    assert payload["stats"]["disabled_embeddings"] >= 1
    assert payload["embeddings"][0]["status"] == "disabled"
    assert "embedding_vector" not in payload["embeddings"][0]

    async with test_engine.connect() as conn:
        status = (
            await conn.execute(
                text("SELECT status FROM knowledge_chunk_embeddings WHERE chunk_id = :chunk_id"),
                {"chunk_id": chunk["chunk_id"]},
            )
        ).scalar_one()
        audit = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.embedding.policy_blocked'")
            )
        ).scalar_one()

    assert status == "disabled"
    assert audit >= 1


@pytest.mark.asyncio
async def test_reindex_item_with_missing_embedding_provider_fails_safely(test_client, test_engine) -> None:
    item, version = await _create_article(test_client, slug="embedding-provider-missing")
    await _create_segment_chunk(test_client, item, version)
    await _enable_vector_settings(test_client)
    policy_resp = await test_client.post(
        "/api/web/knowledge/ai/policies",
        headers=ADMIN_HEADERS,
        json={
            "policy_id": "embedding-global",
            "scope_type": "global",
            "task_type": "embedding",
            "enabled": True,
            "ai_allowed": True,
            "embedding_allowed": True,
            "allow_cloud_for_requester_safe": True,
        },
    )
    assert policy_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-item",
        headers=ADMIN_HEADERS,
        json={"item_id": item["item_id"], "version_id": version["version_id"]},
    )
    assert resp.status == 200
    payload = await resp.json()

    assert payload["job"]["status"] == "failed"
    assert payload["job"]["error_redacted"] == "embedding provider unavailable"
    assert payload["stats"]["failed_embeddings"] >= 1
    assert "OPENROUTER" not in str(payload)

    async with test_engine.connect() as conn:
        audit = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.embedding.provider_unavailable'")
            )
        ).scalar_one()
    assert audit >= 1


@pytest.mark.asyncio
async def test_reindex_scope_endpoints_create_observable_jobs(test_client) -> None:
    item, version = await _create_article(test_client, slug="embedding-scope")
    chunk = await _create_segment_chunk(test_client, item, version)
    segment_id = chunk["metadata_json"]["segment_id"]

    segment_resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-segment",
        headers=ADMIN_HEADERS,
        json={"segment_id": segment_id},
    )
    assert segment_resp.status == 200
    segment_payload = await segment_resp.json()
    assert segment_payload["job"]["scope_type"] == "segment"
    assert segment_payload["job"]["scope_ref"] == segment_id

    space_resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-space",
        headers=ADMIN_HEADERS,
        json={"space_id": item["space_id"]},
    )
    assert space_resp.status == 200
    assert (await space_resp.json())["job"]["scope_type"] == "space"

    all_resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-all",
        headers=ADMIN_HEADERS,
        json={"limit": 25},
    )
    assert all_resp.status == 200
    assert (await all_resp.json())["job"]["scope_type"] == "all"

    generic_resp = await test_client.post(
        "/api/web/knowledge/indexing/jobs",
        headers=ADMIN_HEADERS,
        json={"scope_type": "segment", "scope_ref": segment_id},
    )
    assert generic_resp.status == 200
    assert (await generic_resp.json())["job"]["scope_type"] == "segment"


@pytest.mark.asyncio
async def test_reindex_item_indexes_embedding_with_safe_response(test_client, test_engine, monkeypatch) -> None:
    item, version = await _create_article(test_client, slug="embedding-success")
    chunk = await _create_segment_chunk(test_client, item, version)
    await _enable_vector_settings(test_client)
    monkeypatch.setenv("OPENROUTER_EMBEDDING_KEY", "test-secret")

    async def fake_transport(**kwargs):
        assert kwargs["json"]["model"] == "openai/text-embedding-3-small"
        assert "VPN" in kwargs["json"]["input"]
        assert "test-secret" in kwargs["headers"]["Authorization"]
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    test_client.server.app["knowledge_embedding_openrouter_transport"] = fake_transport

    provider_resp = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=ADMIN_HEADERS,
        json={
            "code": "openrouter-embeddings",
            "title": "OpenRouter embeddings",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "auth_type": "api_key",
            "api_key_secret_ref": "env:OPENROUTER_EMBEDDING_KEY",
            "enabled": True,
        },
    )
    assert provider_resp.status == 200
    provider = (await provider_resp.json())["provider"]
    profile_resp = await test_client.post(
        "/api/web/knowledge/ai/model-profiles",
        headers=ADMIN_HEADERS,
        json={
            "provider_id": provider["provider_id"],
            "code": "embedding-default",
            "title": "Embeddings через OpenRouter",
            "task_type": "embedding",
            "model_name": "openai/text-embedding-3-small",
            "embedding_dimensions": 3,
            "is_default": True,
            "enabled": True,
        },
    )
    assert profile_resp.status == 200
    policy_resp = await test_client.post(
        "/api/web/knowledge/ai/policies",
        headers=ADMIN_HEADERS,
        json={
            "policy_id": "embedding-global-success",
            "scope_type": "global",
            "task_type": "embedding",
            "enabled": True,
            "ai_allowed": True,
            "embedding_allowed": True,
            "allow_cloud_for_requester_safe": True,
        },
    )
    assert policy_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/indexing/reindex-item",
        headers=ADMIN_HEADERS,
        json={"item_id": item["item_id"], "version_id": version["version_id"]},
    )
    assert resp.status == 200
    payload = await resp.json()

    assert payload["job"]["status"] == "completed"
    assert payload["stats"]["indexed_embeddings"] >= 1
    indexed = [row for row in payload["embeddings"] if row["status"] == "indexed"]
    assert indexed
    assert indexed[0]["embedding_dimensions"] == 3
    assert "embedding_vector" not in indexed[0]

    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT e.embedding_vector, c.embedding_ref, c.embedding_model
                    FROM knowledge_chunk_embeddings e
                    JOIN knowledge_chunks c ON c.chunk_id = e.chunk_id
                    WHERE e.chunk_id = :chunk_id
                    """
                ),
                {"chunk_id": chunk["chunk_id"]},
            )
        ).mappings().first()
        completed = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.embedding.index_completed'")
            )
        ).scalar_one()

    assert row["embedding_vector"] == [0.1, 0.2, 0.3]
    assert row["embedding_ref"].startswith("embedding:")
    assert row["embedding_model"] == "openai/text-embedding-3-small"
    assert completed >= 1
