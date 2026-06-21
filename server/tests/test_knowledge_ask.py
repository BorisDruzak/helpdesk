from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.provider_registry import AIProviderRegistry
from app.db.models import KnowledgeAudienceRule, RegistryDepartment, RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.knowledge_repo import KnowledgeRepo
from knowledge.ask_service import KnowledgeAskService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from registry.audience_contracts import EffectiveAudience


pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_HEADERS = {"Authorization": "Bearer test-ui-admin-token"}
SUPPORT_HEADERS = {"Authorization": "Bearer test-ui-support-token"}


async def _seed_requester_identity(session: AsyncSession, *, login: str, department_code: str) -> dict[str, str]:
    department = RegistryDepartment(
        department_id=str(uuid.uuid4()),
        code=department_code,
        name=department_code.upper(),
        status="active",
        source="manual",
    )
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"{department_code.upper()} Ask Requester",
        email=login,
        department_id=department.department_id,
        source="manual",
        status="active",
    )
    session.add_all(
        [
            department,
            person,
            UiUser(user_login=login, password_hash="test", actor_role="user", is_active=True),
            RegistryPersonIdentity(
                person_id=person.person_id,
                provider="ui_login",
                identifier=login,
                normalized_identifier=login,
                verified=True,
                source="admin_manual",
            ),
        ]
    )
    await session.flush()
    return {"department_id": department.department_id, "person_id": person.person_id}


async def _published_item(
    session: AsyncSession,
    *,
    slug: str,
    title: str,
    body: str,
    visibility: str = "requester",
) -> dict:
    repo = KnowledgeRepo(session)
    await repo.upsert_space(
        {"code": "ask-rag", "title": "Ask RAG", "visibility": "requester", "lifecycle_status": "active", "allow_rag": True},
        actor_id="admin",
    )
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


async def _enable_vector_retrieval(session: AsyncSession) -> None:
    await KnowledgeSearchSettingsService(session).upsert_settings(
        {
            "search_mode": "hybrid_vector",
            "keyword_enabled": False,
            "full_text_enabled": False,
            "vector_enabled": True,
            "rerank_enabled": False,
            "rag_answer_enabled": False,
            "max_results": 5,
        },
        actor_id="admin",
    )


async def _insert_first_chunk_embedding(session: AsyncSession, *, item_id: str, vector: list[float]) -> None:
    row = (
        await session.execute(
            text(
                """
                SELECT i.current_version_id AS version_id, c.chunk_id, c.content_hash, c.visibility
                FROM knowledge_items i
                JOIN knowledge_chunks c ON c.item_id = i.item_id AND c.version_id = i.current_version_id
                WHERE i.item_id = :item_id
                ORDER BY c.chunk_index
                LIMIT 1
                """
            ),
            {"item_id": item_id},
        )
    ).mappings().one()
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
            "chunk_id": row["chunk_id"],
            "item_id": item_id,
            "version_id": row["version_id"],
            "embedding_dimensions": len(vector),
            "embedding_vector": json.dumps(vector),
            "content_hash": row["content_hash"],
            "embedding_input_hash": f"test-input-{item_id}",
            "visibility": row["visibility"],
        },
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
        json={"code": "ask-api", "title": "Ask API", "visibility": "requester", "lifecycle_status": "active", "allow_rag": True},
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
async def test_public_knowledge_ask_applies_audience_rules_before_vector_retrieval_projection(test_client, test_engine) -> None:
    requester_login = "ask-audience-it"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        await _seed_requester_identity(session, login=requester_login, department_code="it")
        finance = await _seed_requester_identity(session, login="ask-audience-finance", department_code="finance")
        visible = await _published_item(
            session,
            slug="it-ask-vector-visible",
            title="Ask vector audience visible",
            body="Ask vector marker visible body.",
        )
        hidden = await _published_item(
            session,
            slug="finance-ask-vector-scoped",
            title="Ask vector audience Finance scoped",
            body="Ask vector marker finance body.",
        )
        session.add(
            KnowledgeAudienceRule(
                rule_id="rule-ask-vector-finance-hidden",
                subject_type="item",
                subject_id=hidden["item_id"],
                target_type="department",
                target_id=finance["department_id"],
                effect="allow",
                status="active",
            )
        )
        await _insert_first_chunk_embedding(session, item_id=visible["item_id"], vector=[0.4, 0.6])
        await _insert_first_chunk_embedding(session, item_id=hidden["item_id"], vector=[0.99, 0.01])
        await _enable_vector_retrieval(session)
        await session.commit()

    response = await test_client.post(
        "/api/knowledge/ask",
        headers={"Authorization": f"Bearer test-ui-user:{requester_login}"},
        json={"query": "semantic-only-ask-vector", "query_vector": [1.0, 0.0], "surface": "requester_portal"},
    )

    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    slugs = {result["item"]["slug"] for result in payload["retrieval_results"]}
    assert "it-ask-vector-visible" in slugs
    assert "finance-ask-vector-scoped" not in slugs
    assert "Finance scoped" not in str(payload)
    assert "finance body" not in str(payload)


@pytest.mark.asyncio
async def test_requester_ask_prompt_uses_creator_audience_before_answer_generation(test_engine, monkeypatch) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        visible = await _published_item(
            session,
            slug="pa7-ask-creator-visible",
            title="PA7 creator visible Ask",
            body="pa7-rag-payroll creator-visible snippet for ordinary requesters.",
        )
        hidden = await _published_item(
            session,
            slug="pa7-ask-finance-hidden",
            title="PA7 Finance hidden Ask",
            body="pa7-rag-payroll restricted finance snippet must never enter requester prompt.",
        )
        session.add(
            KnowledgeAudienceRule(
                rule_id="pa7-ask-finance-hidden",
                subject_type="item",
                subject_id=hidden["item_id"],
                target_type="department",
                target_id="finance",
                effect="allow",
                status="active",
            )
        )
        await _enable_rag(session)
        await _enable_answer_ai(session)
        await session.commit()

    monkeypatch.setenv("OPENROUTER_ANSWER_TEST_KEY", "test-answer-secret")
    prompts: list[str] = []

    async def fake_transport(**kwargs):
        prompt = kwargs["json"]["messages"][1]["content"]
        prompts.append(prompt)
        return {"choices": [{"message": {"content": "Используйте доступную инструкцию. [1]"}}]}

    creator_audience = EffectiveAudience(
        person_id="creator-it-pa7-ask",
        actor_id="creator-it-pa7-ask@example.test",
        actor_role="requester",
        department_path=[{"department_id": "it", "code": "it"}],
    )
    async with session_maker() as session:
        result = await KnowledgeAskService(session, transport=fake_transport).ask(
            query="pa7-rag-payroll",
            actor_role="requester",
            surface="requester_portal",
            effective_audience=creator_audience,
        )
        await session.commit()

    assert result["answer_status"] == "answered"
    assert prompts
    assert "PA7 creator visible Ask" in prompts[0]
    assert "creator-visible snippet" in prompts[0]
    assert "PA7 Finance hidden Ask" not in prompts[0]
    assert "restricted finance snippet" not in prompts[0]
    assert [item["item"]["slug"] for item in result["retrieval_results"]] == [visible["slug"]]


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
