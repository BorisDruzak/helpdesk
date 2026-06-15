from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.provider_registry import AIProviderRegistry
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.retrieval_service import KnowledgeRetrievalService
from knowledge.search_settings_service import KnowledgeSearchSettingsService


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


async def _published_item(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    body: str,
    space_code: str = "hybrid-retrieval",
    space_allow_rag: bool = True,
    visibility: str = "requester",
    binding: dict | None = None,
    metadata: dict | None = None,
) -> tuple[dict, dict, dict]:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {
            "code": space_code,
            "title": f"{space_code} space",
            "visibility": "requester",
            "lifecycle_status": "active",
            "allow_rag": space_allow_rag,
        },
        actor_id="admin",
    )
    item = await repo.create_item_draft(
        {
            "space_code": space_code,
            "slug": slug,
            "item_type": "article",
            "title": title,
            "summary": title,
            "visibility": visibility,
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
            "metadata": metadata or {},
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
    if binding:
        await repo.add_binding(item["item_id"], binding, actor_id="admin", actor_role="admin")
    await repo.publish_item(item["item_id"], version["version_id"], actor_id="admin", actor_role="admin")
    chunk = (
        await session.execute(
            text(
                """
                SELECT chunk_id, content_hash, visibility
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


async def _insert_embedding(session: AsyncSession, *, item: dict, version: dict, chunk: dict, vector: list[float]) -> None:
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
                :embedding_id, :chunk_id, :item_id, :version_id, 'test-hybrid-vector',
                :embedding_dimensions, CAST(:embedding_vector AS jsonb), :content_hash,
                'hybrid-input', :visibility, 'indexed', CURRENT_TIMESTAMP,
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
            "visibility": chunk["visibility"],
        },
    )


async def _enable_hybrid(session: AsyncSession, *, vector_enabled: bool, rerank_enabled: bool = False) -> None:
    await KnowledgeSearchSettingsService(session).upsert_settings(
        {
            "search_mode": "hybrid_vector_rerank" if rerank_enabled else ("hybrid_vector" if vector_enabled else "hybrid_no_ai"),
            "keyword_enabled": True,
            "full_text_enabled": True,
            "vector_enabled": vector_enabled,
            "rerank_enabled": rerank_enabled,
            "vector_weight": 1.25,
            "max_results": 10,
        },
        actor_id="admin",
    )


async def _enable_rerank_ai(session: AsyncSession) -> None:
    registry = AIProviderRegistry(session)
    suffix = uuid.uuid4().hex[:8]
    provider = await registry.create_provider(
        {
            "code": f"openrouter-rerank-{suffix}",
            "title": "OpenRouter rerank",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "auth_type": "api_key",
            "api_key_secret_ref": "env:OPENROUTER_RERANK_TEST_KEY",
            "enabled": True,
        },
        actor_id="admin",
    )
    await registry.create_model_profile(
        {
            "provider_id": provider["provider_id"],
            "code": f"rerank-default-{suffix}",
            "title": "Rerank default",
            "task_type": "rerank",
            "model_name": "cohere/rerank-v3.5",
            "is_default": True,
            "enabled": True,
        },
        actor_id="admin",
    )
    await registry.upsert_policy(
        {
            "policy_id": "rerank-global-test",
            "scope_type": "global",
            "task_type": "rerank",
            "enabled": True,
            "ai_allowed": True,
            "rerank_allowed": True,
        },
        actor_id="admin",
    )


@pytest.mark.asyncio
async def test_hybrid_retrieval_merges_keyword_segment_binding_and_vector_scores(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item, version, chunk = await _published_item(
            session,
            slug="hybrid-vpn-access",
            title="VPN access recovery",
            body="VPN access troubleshooting for requester sign-in.",
            binding={"service_code": "network", "offering_code": "network.vpn_issue"},
        )
        await session.execute(
            text(
                """
                INSERT INTO knowledge_article_segments (
                    segment_id, item_id, version_id, segment_index, segment_type,
                    title, text, keywords_json, boost, visibility, status,
                    source, content_hash, full_text_enabled, embedding_enabled,
                    created_at, updated_at
                )
                VALUES (
                    :segment_id, :item_id, :version_id, 0, 'manual',
                    'VPN segment', 'VPN access segment text', '["vpn"]'::jsonb,
                    3, 'requester', 'active', 'editor_selection', :content_hash,
                    true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "segment_id": str(uuid.uuid4()),
                "item_id": item["item_id"],
                "version_id": version["version_id"],
                "content_hash": chunk["content_hash"],
            },
        )
        await _insert_embedding(session, item=item, version=version, chunk=chunk, vector=[0.9, 0.1])
        await _enable_hybrid(session, vector_enabled=True)
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeRetrievalService(session).retrieve(
            query="VPN",
            actor_role="support",
            service_code="network",
            offering_code="network.vpn_issue",
            query_vector=[0.9, 0.1],
        )

    first = result["results"][0]
    assert first["item"]["slug"] == "hybrid-vpn-access"
    assert {"keyword", "segment", "vector"} <= set(first["source_mode"])
    assert first["score_parts"]["keyword_title"] == 50.0
    assert first["score_parts"]["binding_service"] == 25.0
    assert first["score_parts"]["binding_offering"] == 35.0
    assert first["score_parts"]["segment_title"] == 60.0
    assert first["score_parts"]["vector"] > 100.0
    assert first["citations"]
    assert "embedding_vector" not in first
    assert result["effective_mode"] == "hybrid_vector"
    assert result["ai_used"] is True


@pytest.mark.asyncio
async def test_hybrid_retrieval_filters_disabled_rag_policy_before_citations(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        allowed_item, allowed_version, allowed_chunk = await _published_item(
            session,
            slug="rag-policy-allowed",
            title="VPN RAG allowed",
            body="VPN policy content allowed for RAG.",
            space_code="rag-policy-allowed-space",
        )
        disabled_section_item, disabled_section_version, disabled_section_chunk = await _published_item(
            session,
            slug="rag-policy-disabled-section",
            title="VPN disabled section",
            body="VPN disabled section content must not become a citation.",
            space_code="rag-policy-disabled-space",
            space_allow_rag=False,
        )
        disabled_article_item, disabled_article_version, disabled_article_chunk = await _published_item(
            session,
            slug="rag-policy-disabled-article",
            title="VPN disabled article",
            body="VPN disabled article content must not become a citation.",
            space_code="rag-policy-article-space",
            metadata={"ai_rag_policy": "disabled"},
        )
        await _insert_embedding(session, item=allowed_item, version=allowed_version, chunk=allowed_chunk, vector=[0.9, 0.1])
        await _insert_embedding(
            session,
            item=disabled_section_item,
            version=disabled_section_version,
            chunk=disabled_section_chunk,
            vector=[1.0, 0.0],
        )
        await _insert_embedding(
            session,
            item=disabled_article_item,
            version=disabled_article_version,
            chunk=disabled_article_chunk,
            vector=[1.0, 0.0],
        )
        await _enable_hybrid(session, vector_enabled=True)
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeRetrievalService(session).retrieve(
            query="VPN",
            actor_role="support",
            query_vector=[1.0, 0.0],
        )

    slugs = [entry["item"]["slug"] for entry in result["results"]]
    assert slugs == ["rag-policy-allowed"]
    assert result["results"][0]["citations"]
    assert "rag-policy-disabled-section" not in str(result)
    assert "rag-policy-disabled-article" not in str(result)
    assert result["rag_policy"]["excluded_count"] == 2
    assert {entry["reason_code"] for entry in result["rag_policy"]["excluded"]} >= {"section_rag_disabled", "article_rag_disabled"}


@pytest.mark.asyncio
async def test_hybrid_retrieval_vector_disabled_falls_back_to_non_vector(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        item, version, chunk = await _published_item(
            session,
            slug="hybrid-vector-disabled",
            title="Printer queue reset",
            body="Printer reset procedure.",
        )
        await _insert_embedding(session, item=item, version=version, chunk=chunk, vector=[1.0, 0.0])
        await _enable_hybrid(session, vector_enabled=False)
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeRetrievalService(session).retrieve(
            query="Printer",
            actor_role="support",
            query_vector=[1.0, 0.0],
        )

    first = result["results"][0]
    assert first["item"]["slug"] == "hybrid-vector-disabled"
    assert "vector" not in first["score_parts"]
    assert result["effective_mode"] == "hybrid_no_ai"
    assert result["ai_used"] is False


@pytest.mark.asyncio
async def test_web_retrieve_endpoint_returns_explainable_results_and_observer_event(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(
            session,
            slug="hybrid-web-preview",
            title="Web retrieval preview",
            body="Retrieval preview body.",
        )
        await session.commit()

    settings_resp = await test_client.post(
        "/api/web/knowledge/search-settings",
        headers=ADMIN_HEADERS,
        json={"search_mode": "hybrid_no_ai", "keyword_enabled": True, "full_text_enabled": True, "vector_enabled": False},
    )
    assert settings_resp.status == 200

    resp = await test_client.post(
        "/api/web/knowledge/retrieve",
        headers=SUPPORT_HEADERS,
        json={"query": "retrieval", "surface": "admin_knowledge_retrieve"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["status"] == "ok"
    assert payload["display_message"] == "Retrieval выполнен"
    assert payload["results"][0]["item"]["slug"] == "hybrid-web-preview"
    assert "score_parts" in payload["results"][0]

    async with test_engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.retrieval.executed'")
            )
        ).scalar_one()
    assert count >= 1


@pytest.mark.asyncio
async def test_retrieval_rerank_reorders_candidates_with_mocked_openrouter(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="rerank-alpha", title="VPN alpha", body="VPN alpha body.")
        await _published_item(session, slug="rerank-beta", title="VPN beta", body="VPN beta body.")
        await _enable_hybrid(session, vector_enabled=True, rerank_enabled=True)
        await _enable_rerank_ai(session)
        await session.commit()

    monkeypatch.setenv("OPENROUTER_RERANK_TEST_KEY", "test-rerank-secret")

    async def fake_transport(**kwargs):
        assert kwargs["json"]["model"] == "cohere/rerank-v3.5"
        assert kwargs["json"]["query"] == "VPN"
        assert len(kwargs["json"]["documents"]) >= 2
        assert "test-rerank-secret" in kwargs["headers"]["Authorization"]
        return {"results": [{"index": 1, "relevance_score": 0.99}, {"index": 0, "relevance_score": 0.1}]}

    async with session_maker() as session:
        result = await KnowledgeRetrievalService(session, transport=fake_transport).retrieve(query="VPN", actor_role="support")
        await session.commit()

    assert result["results"][0]["item"]["slug"] == "rerank-beta"
    assert result["results"][0]["score_parts"]["rerank"] == 99.0
    assert "rerank" in result["results"][0]["source_mode"]
    assert result["fallback_mode"] in {None, "query_vector_missing"}
    assert result["ai_used"] is True


@pytest.mark.asyncio
async def test_retrieval_rerank_failure_returns_pre_rerank_fallback(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="rerank-fallback-alpha", title="VPN fallback alpha", body="VPN fallback alpha body.")
        await _published_item(session, slug="rerank-fallback-beta", title="VPN fallback beta", body="VPN fallback beta body.")
        await _enable_hybrid(session, vector_enabled=True, rerank_enabled=True)
        await _enable_rerank_ai(session)
        await session.commit()

    monkeypatch.setenv("OPENROUTER_RERANK_TEST_KEY", "test-rerank-secret")

    async def failing_transport(**kwargs):
        raise RuntimeError("provider unavailable")

    async with session_maker() as session:
        result = await KnowledgeRetrievalService(session, transport=failing_transport).retrieve(query="VPN fallback", actor_role="support")
        await session.commit()

    assert result["results"][0]["item"]["slug"] == "rerank-fallback-alpha"
    assert result["fallback_mode"] in {"rerank_request_failed", "query_vector_missing"}
    assert result["ai_used"] is False
    async with test_engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.retrieval.rerank_failed_fallback'")
            )
        ).scalar_one()
    assert count >= 1
