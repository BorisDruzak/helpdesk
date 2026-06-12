from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.provider_registry import AIProviderRegistry
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ask_service import KnowledgeAskService
from knowledge.evaluation import KnowledgeEvalRecorder
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
