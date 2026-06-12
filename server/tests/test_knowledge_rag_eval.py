from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.provider_registry import AIProviderRegistry
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ask_service import KnowledgeAskService
from knowledge.evaluation import KnowledgeEvalRecorder
from knowledge.retrieval_service import KnowledgeRetrievalService
from knowledge.search_service import KnowledgeSearchService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from knowledge.segmentation_service import KnowledgeSegmentationService


async def _publish_item(
    session: AsyncSession,
    *,
    space_code: str,
    slug: str,
    title: str,
    body: str,
    visibility: str,
    item_type: str = "article",
    binding: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    repo = KnowledgeRepo(session)
    item = await repo.create_item_draft(
        {
            "space_code": space_code,
            "slug": slug,
            "item_type": item_type,
            "title": title,
            "summary": title,
            "visibility": visibility,
            "owner_actor_id": "eval-owner",
            "reviewer_actor_id": "eval-reviewer",
            "metadata": metadata or {},
        },
        actor_id="eval-admin",
        actor_role="admin",
    )
    version = await repo.create_version(
        item["item_id"],
        {"title": title, "summary": title, "body_format": "markdown", "body": body},
        actor_id="eval-admin",
        actor_role="admin",
    )
    if binding:
        await repo.add_binding(item["item_id"], binding, actor_id="eval-admin", actor_role="admin")
    published = await repo.publish_item(item["item_id"], version["version_id"], actor_id="eval-admin", actor_role="admin")
    return {**published, "version_id": version["version_id"]}


async def _enable_rag_answer_mode(session: AsyncSession) -> None:
    await KnowledgeSearchSettingsService(session).upsert_settings(
        {
            "search_mode": "rag_answer",
            "keyword_enabled": True,
            "full_text_enabled": True,
            "vector_enabled": True,
            "rerank_enabled": False,
            "rag_answer_enabled": True,
            "max_results": 5,
        },
        actor_id="eval-admin",
    )
    await AIProviderRegistry(session).upsert_policy(
        {
            "policy_id": f"eval-answer-policy-{uuid.uuid4().hex[:8]}",
            "scope_type": "global",
            "task_type": "answer",
            "enabled": True,
            "ai_allowed": True,
            "answer_allowed": True,
            "allow_cloud_for_requester_safe": True,
        },
        actor_id="eval-admin",
    )


async def _enable_hybrid_rerank_mode(session: AsyncSession, *, suffix: str) -> None:
    await KnowledgeSearchSettingsService(session).upsert_settings(
        {
            "search_mode": "hybrid_vector_rerank",
            "keyword_enabled": True,
            "full_text_enabled": True,
            "vector_enabled": True,
            "rerank_enabled": True,
            "vector_weight": 1.25,
            "max_results": 10,
        },
        actor_id="eval-admin",
    )
    registry = AIProviderRegistry(session)
    provider = await registry.create_provider(
        {
            "code": f"eval-rerank-{suffix}",
            "title": "Eval rerank provider",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "auth_type": "api_key",
            "api_key_secret_ref": f"env:EVAL_RERANK_KEY_{suffix.upper()}",
            "enabled": True,
        },
        actor_id="eval-admin",
    )
    await registry.create_model_profile(
        {
            "provider_id": provider["provider_id"],
            "code": f"eval-rerank-profile-{suffix}",
            "title": "Eval rerank profile",
            "task_type": "rerank",
            "model_name": "cohere/rerank-v3.5",
            "is_default": True,
            "enabled": True,
        },
        actor_id="eval-admin",
    )
    await registry.upsert_policy(
        {
            "policy_id": f"eval-rerank-policy-{suffix}",
            "scope_type": "global",
            "task_type": "rerank",
            "enabled": True,
            "ai_allowed": True,
            "rerank_allowed": True,
        },
        actor_id="eval-admin",
    )


async def _first_chunk(session: AsyncSession, *, item_id: str, version_id: str) -> dict:
    row = (
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
            {"item_id": item_id, "version_id": version_id},
        )
    ).mappings().first()
    assert row is not None
    return dict(row)


async def _insert_embedding(session: AsyncSession, *, item: dict, chunk: dict, vector: list[float]) -> None:
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
                :embedding_id, :chunk_id, :item_id, :version_id, 'eval-vector-model',
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
            "version_id": item["version_id"],
            "embedding_dimensions": len(vector),
            "embedding_vector": json.dumps(vector),
            "content_hash": chunk["content_hash"],
            "embedding_input_hash": f"eval-{uuid.uuid4().hex}",
            "visibility": chunk["visibility"],
        },
    )


@pytest.mark.asyncio
async def test_knowledge_rag_eval_records_recall_no_answer_and_acl_safety(test_engine) -> None:
    suffix = uuid.uuid4().hex[:8]
    space_code = f"eval-{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": space_code, "title": "Eval KB", "visibility": "support_internal", "lifecycle_status": "active"}, actor_id="eval-admin")
        requester_article = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-requester-{suffix}",
            title="Requester VPN recovery",
            body="Requester-safe VPN recovery body. Use the portal reset flow.",
            visibility="requester",
            binding={"service_code": "network", "offering_code": "network.vpn_issue"},
        )
        await KnowledgeSegmentationService(session).create_segment(
            requester_article["item_id"],
            {
                "version_id": requester_article["version_id"],
                "segment_type": "manual",
                "title": "Authenticator recovery evaluation",
                "text": "Requester can refresh the authenticator prompt through the portal reset flow.",
                "keywords": ["eval-totp-marker"],
                "visibility": "requester",
                "boost": 3,
            },
            actor_id="eval-admin",
            actor_role="admin",
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-runbook-{suffix}",
            title="Support internal VPN runbook",
            body="Support-only escalation marker eval-support-secret.",
            visibility="support_internal",
            item_type="runbook",
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-admin-{suffix}",
            title="Admin-only VPN article",
            body="Admin-only marker eval-admin-secret.",
            visibility="admin_internal",
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-security-{suffix}",
            title="Security restricted VPN article",
            body="Security-only marker eval-security-secret.",
            visibility="security_restricted",
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-known-error-{suffix}",
            title="VPN known error 809",
            body="Known error marker eval-known-error.\n\nWorkaround: reconnect after policy refresh.",
            visibility="support_internal",
            item_type="known_error",
            metadata={"known_error_status": "active", "workaround": "Reconnect after policy refresh."},
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-workaround-{suffix}",
            title="VPN workaround",
            body="Workaround marker eval-workaround.",
            visibility="support_internal",
            item_type="workaround",
        )
        await _enable_rag_answer_mode(session)
        await session.commit()

    async with session_maker() as session:
        search = KnowledgeSearchService(session)
        recorder = KnowledgeEvalRecorder()

        requester_results = await search.search(query="eval-totp-marker", actor_role="requester", service_code="network", offering_code="network.vpn_issue")
        recorder.record_search_case("manual_segment_recall", expected_slugs={requester_article["slug"]}, results=requester_results)

        requester_forbidden = await search.search(query="eval-support-secret eval-admin-secret eval-security-secret", actor_role="requester")
        recorder.record_acl_case("requester_acl", forbidden_visibilities={"support_internal", "admin_internal", "security_restricted"}, results=requester_forbidden)

        support_forbidden = await search.search(query="eval-admin-secret eval-security-secret", actor_role="support")
        recorder.record_acl_case("support_acl", forbidden_visibilities={"admin_internal", "security_restricted"}, results=support_forbidden)

        ask_no_answer = await KnowledgeAskService(session).ask(query=f"no evidence phrase {suffix}", actor_role="requester", surface="eval_suite")
        recorder.record_no_answer_case("requester_no_answer", ask_no_answer)

        ask_allowed = await KnowledgeAskService(session).ask(query="eval-totp-marker", actor_role="requester", surface="eval_suite")
        recorder.record_answer_status_case("requester_provider_unavailable", ask_allowed, expected_status="provider_unavailable")
        recorder.record_citation_case("requester_citations_acl", allowed_item_ids={requester_article["item_id"]}, citations=ask_allowed["citations"])
        report = recorder.report(latency_ms=0)
        await session.commit()

    assert requester_results[0]["slug"] == requester_article["slug"]
    assert ask_no_answer["answer_status"] == "not_enough_evidence"
    assert ask_allowed["answer_status"] == "provider_unavailable"
    assert report["metrics"]["top_k_recall"] == 1.0
    assert report["metrics"]["no_answer_correctness"] == 1.0
    assert report["metrics"]["acl_leakage_count"] == 0
    assert report["metrics"]["citation_precision"] == 1.0
    assert report["metrics"]["fallback_count"] == 2
    assert report["metrics"]["provider_failure_count"] == 1


@pytest.mark.asyncio
async def test_knowledge_rag_eval_covers_vector_rerank_versions_and_archived_items(test_engine, monkeypatch) -> None:
    suffix = uuid.uuid4().hex[:8]
    space_code = f"eval-deep-{suffix}"
    body_marker = f"eval-body-marker-{suffix}"
    fallback_marker = f"eval-fallback-marker-{suffix}"
    archived_marker = f"eval-archived-marker-{suffix}"
    old_marker = f"eval-old-marker-{suffix}"
    current_marker = f"eval-current-marker-{suffix}"
    rerank_query = f"eval-rerank-marker-{suffix}"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        repo = KnowledgeRepo(session)
        await repo.upsert_space({"code": space_code, "title": "Eval deep KB", "visibility": "requester", "lifecycle_status": "active"}, actor_id="eval-admin")
        full_text_article = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-body-{suffix}",
            title="Body-only recall article",
            body=f"Body-only recall text with {body_marker}.",
            visibility="requester",
        )
        vector_target = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-vector-target-{suffix}",
            title="Semantic recovery target",
            body=f"Semantic recovery body with {fallback_marker}.",
            visibility="requester",
        )
        vector_other = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-vector-other-{suffix}",
            title="Semantic recovery other",
            body="Unrelated semantic recovery body.",
            visibility="requester",
        )
        await _insert_embedding(
            session,
            item=vector_target,
            chunk=await _first_chunk(session, item_id=vector_target["item_id"], version_id=vector_target["version_id"]),
            vector=[0.95, 0.05],
        )
        await _insert_embedding(
            session,
            item=vector_other,
            chunk=await _first_chunk(session, item_id=vector_other["item_id"], version_id=vector_other["version_id"]),
            vector=[0.05, 0.95],
        )
        versioned = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-versioned-{suffix}",
            title="Versioned evaluation article",
            body=f"Old body with {old_marker}.",
            visibility="requester",
        )
        current_version = await repo.create_version(
            versioned["item_id"],
            {"title": "Versioned evaluation article", "summary": "Current", "body_format": "markdown", "body": f"Current body with {current_marker}."},
            actor_id="eval-admin",
            actor_role="admin",
        )
        await repo.publish_item(versioned["item_id"], current_version["version_id"], actor_id="eval-admin", actor_role="admin")
        archived = await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-archived-{suffix}",
            title="Archived evaluation article",
            body=f"Archived body with {archived_marker}.",
            visibility="requester",
        )
        await session.execute(text("UPDATE knowledge_items SET status = 'archived' WHERE item_id = :item_id"), {"item_id": archived["item_id"]})
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-rerank-alpha-{suffix}",
            title=f"Alpha candidate {rerank_query}",
            body=f"Alpha body {rerank_query}.",
            visibility="requester",
        )
        await _publish_item(
            session,
            space_code=space_code,
            slug=f"eval-rerank-beta-{suffix}",
            title=f"Beta candidate {rerank_query}",
            body=f"Beta body {rerank_query}.",
            visibility="requester",
        )
        await _enable_hybrid_rerank_mode(session, suffix=suffix)
        await session.commit()

    monkeypatch.setenv(f"EVAL_RERANK_KEY_{suffix.upper()}", "test-rerank-secret")

    async def fake_rerank_transport(**kwargs):
        assert kwargs["json"]["query"] == rerank_query
        assert len(kwargs["json"]["documents"]) >= 2
        return {"results": [{"index": 1, "relevance_score": 0.99}, {"index": 0, "relevance_score": 0.1}]}

    async with session_maker() as session:
        search = KnowledgeSearchService(session)
        recorder = KnowledgeEvalRecorder()

        full_text_results = await search.search(query=body_marker, actor_role="requester")
        recorder.record_search_case("body_only_recall", expected_slugs={full_text_article["slug"]}, results=full_text_results)

        vector_results = await search.search(query=f"no-keyword-vector-{suffix}", actor_role="requester", vector_enabled=True, query_vector=[0.9, 0.1], limit=5)
        recorder.record_search_case("vector_recall", expected_slugs={vector_target["slug"]}, results=vector_results)

        vector_disabled_results = await search.search(query=fallback_marker, actor_role="requester", vector_enabled=False, query_vector=[0.9, 0.1], limit=5)
        recorder.record_search_case("vector_disabled_keyword_fallback", expected_slugs={vector_target["slug"]}, results=vector_disabled_results)

        archived_results = await search.search(query=archived_marker, actor_role="requester")
        old_version_results = await search.search(query=old_marker, actor_role="requester")
        current_version_results = await search.search(query=current_marker, actor_role="requester")
        reranked = await KnowledgeRetrievalService(session, transport=fake_rerank_transport).retrieve(query=rerank_query, actor_role="support")
        report = recorder.report(latency_ms=0)
        await session.commit()

    assert [item["slug"] for item in vector_results][:1] == [vector_target["slug"]]
    assert "vector_score" not in vector_disabled_results[0]
    assert archived_results == []
    assert old_version_results == []
    assert [item["slug"] for item in current_version_results][:1] == [versioned["slug"]]
    assert reranked["results"][0]["item"]["slug"] == f"eval-rerank-beta-{suffix}"
    assert "rerank" in reranked["results"][0]["source_mode"]
    assert report["metrics"]["top_k_recall"] == 1.0
