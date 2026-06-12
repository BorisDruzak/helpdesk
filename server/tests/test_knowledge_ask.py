from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.provider_registry import AIProviderRegistry
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ask_service import KnowledgeAskService
from knowledge.search_settings_service import KnowledgeSearchSettingsService


ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


async def _published_item(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    body: str,
    visibility: str = "requester",
) -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space({"code": "ask-rag", "title": "Ask RAG", "visibility": "requester", "lifecycle_status": "active"}, actor_id="admin")
    item = await repo.create_item_draft(
        {
            "space_code": "ask-rag",
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
    return item


async def _enable_rag(session: AsyncSession) -> None:
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
        actor_id="admin",
    )


async def _enable_answer_ai(session: AsyncSession, *, policy_allowed: bool = True) -> None:
    registry = AIProviderRegistry(session)
    suffix = uuid.uuid4().hex[:8]
    provider = await registry.create_provider(
        {
            "code": f"openrouter-answer-{suffix}",
            "title": "OpenRouter answer",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "auth_type": "api_key",
            "api_key_secret_ref": "env:OPENROUTER_ANSWER_TEST_KEY",
            "enabled": True,
        },
        actor_id="admin",
    )
    await registry.create_model_profile(
        {
            "provider_id": provider["provider_id"],
            "code": f"answer-default-{suffix}",
            "title": "Answer default",
            "task_type": "answer",
            "model_name": "openai/gpt-4o-mini",
            "is_default": True,
            "enabled": True,
        },
        actor_id="admin",
    )
    await registry.upsert_policy(
        {
            "policy_id": f"answer-global-{suffix}",
            "scope_type": "global",
            "task_type": "answer",
            "enabled": True,
            "ai_allowed": policy_allowed,
            "answer_allowed": policy_allowed,
            "allow_cloud_for_requester_safe": True,
        },
        actor_id="admin",
    )


@pytest.mark.asyncio
async def test_knowledge_ask_ai_disabled_returns_search_fallback(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="ask-disabled-vpn", title="VPN восстановление", body="VPN инструкция без AI.")
        await session.commit()

    async with session_maker() as session:
        result = await KnowledgeAskService(session).ask(query="VPN", actor_role="requester", surface="requester_ask")
        await session.commit()

    assert result["answer_status"] == "ai_disabled"
    assert result["answer"] is None
    assert result["ai_used"] is False
    assert result["display_message"] == "AI-ответы отключены. Ниже показаны результаты поиска по базе знаний."
    assert result["retrieval_results"][0]["item"]["slug"] == "ask-disabled-vpn"
    assert "score_parts" not in result["retrieval_results"][0]

    async with test_engine.connect() as conn:
        count = (await conn.execute(text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.rag.ai_disabled'"))).scalar_one()
    assert count >= 1


@pytest.mark.asyncio
async def test_public_knowledge_ask_endpoint_keeps_requester_safe_fallback(test_client) -> None:
    space_resp = await test_client.post(
        "/api/web/knowledge/spaces",
        headers=ADMIN_HEADERS,
        json={"code": "ask-api", "title": "Ask API", "visibility": "requester", "lifecycle_status": "active"},
    )
    assert space_resp.status == 200
    item_resp = await test_client.post(
        "/api/web/knowledge/items",
        headers=ADMIN_HEADERS,
        json={
            "space_code": "ask-api",
            "slug": "ask-api-vpn",
            "item_type": "article",
            "title": "VPN портал",
            "summary": "Ответы по VPN",
            "visibility": "requester",
            "owner_actor_id": "owner",
            "reviewer_actor_id": "reviewer",
        },
    )
    item = (await item_resp.json())["item"]
    version_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/versions",
        headers=ADMIN_HEADERS,
        json={"title": "VPN портал", "body_format": "markdown", "body": "Инструкция VPN для портала знаний."},
    )
    version = (await version_resp.json())["version"]
    publish_resp = await test_client.post(
        f"/api/web/knowledge/items/{item['item_id']}/publish",
        headers=ADMIN_HEADERS,
        json={"version_id": version["version_id"]},
    )
    assert publish_resp.status == 200

    ask_resp = await test_client.post("/api/knowledge/ask", json={"query": "VPN", "surface": "requester_portal"})
    assert ask_resp.status == 200
    payload = await ask_resp.json()
    assert payload["status"] == "ok"
    assert payload["answer_status"] == "ai_disabled"
    assert payload["display_message"] == "AI-ответы отключены. Ниже показаны результаты поиска по базе знаний."
    assert payload["retrieval_results"][0]["item"]["slug"] == "ask-api-vpn"
    assert "score_parts" not in payload["retrieval_results"][0]


@pytest.mark.asyncio
async def test_knowledge_ask_uses_mocked_answer_model_with_citations(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="ask-answered-vpn", title="VPN answered", body="VPN evidence for cited answer.")
        await _enable_rag(session)
        await _enable_answer_ai(session)
        await session.commit()

    monkeypatch.setenv("OPENROUTER_ANSWER_TEST_KEY", "test-answer-secret")

    async def fake_transport(**kwargs):
        assert kwargs["json"]["model"] == "openai/gpt-4o-mini"
        assert kwargs["json"]["messages"][0]["role"] == "system"
        assert "test-answer-secret" in kwargs["headers"]["Authorization"]
        assert "[1]" in kwargs["json"]["messages"][1]["content"]
        return {"choices": [{"message": {"content": "Используйте инструкцию VPN из базы знаний. [1]"}}]}

    async with session_maker() as session:
        result = await KnowledgeAskService(session, transport=fake_transport).ask(query="VPN", actor_role="support", surface="admin_ask_preview")
        await session.commit()

    assert result["answer_status"] == "answered"
    assert result["answer"] == "Используйте инструкцию VPN из базы знаний. [1]"
    assert result["citations"]
    assert result["audit_id"]
    assert result["ai_used"] is True

    async with test_engine.connect() as conn:
        answered = (await conn.execute(text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.rag.answer_generated'"))).scalar_one()
        audit = (await conn.execute(text("SELECT COUNT(*) FROM ai_request_audit WHERE task_type = 'answer' AND status = 'ok'"))).scalar_one()
    assert answered >= 1
    assert audit >= 1


@pytest.mark.asyncio
async def test_knowledge_ask_blocks_uncited_critical_claims(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="ask-critical-vpn", title="VPN critical evidence", body="VPN evidence for cited answer.")
        await _enable_rag(session)
        await _enable_answer_ai(session)
        await session.commit()

    monkeypatch.setenv("OPENROUTER_ANSWER_TEST_KEY", "test-answer-secret")

    async def fake_transport(**kwargs):
        assert "[1]" in kwargs["json"]["messages"][1]["content"]
        return {"choices": [{"message": {"content": "Сбросьте пароль администратора и отключите MFA."}}]}

    async with session_maker() as session:
        result = await KnowledgeAskService(session, transport=fake_transport).ask(query="VPN", actor_role="support", surface="admin_ask_preview")
        await session.commit()

    assert result["answer_status"] == "not_enough_evidence"
    assert result["answer"] is None
    assert result["ai_used"] is False
    assert result["retrieval_results"][0]["item"]["slug"] == "ask-critical-vpn"

    async with test_engine.connect() as conn:
        blocked = (
            await conn.execute(
                text("SELECT COUNT(*) FROM ai_request_audit WHERE task_type = 'answer' AND status = 'blocked' AND error_code = 'UNCITED_CRITICAL_CLAIM'")
            )
        ).scalar_one()
        fallback = (
            await conn.execute(
                text("SELECT COUNT(*) FROM agent_runtime_audit WHERE event_type = 'knowledge.rag.not_enough_evidence' AND details_json ->> 'reason' = 'uncited_critical_claim'")
            )
        ).scalar_one()
    assert blocked >= 1
    assert fallback >= 1


@pytest.mark.asyncio
async def test_web_knowledge_ask_preview_falls_back_when_provider_unavailable(test_client, test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _published_item(session, slug="ask-provider-fallback", title="VPN provider fallback", body="VPN provider fallback evidence.")
        await _enable_rag(session)
        await _enable_answer_ai(session)
        await session.commit()

    resp = await test_client.post(
        "/api/web/knowledge/ask/preview",
        headers=SUPPORT_HEADERS,
        json={"query": "VPN", "surface": "admin_ask_preview"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["status"] == "ok"
    assert payload["answer_status"] == "provider_unavailable"
    assert payload["display_message"] == "AI-провайдер недоступен. Ниже показаны результаты поиска."
    assert payload["retrieval_results"][0]["item"]["slug"] == "ask-provider-fallback"
    assert payload["audit_id"]
