from __future__ import annotations

import pytest
from sqlalchemy import text

from web_api import knowledge_ai_handlers

pytestmark = pytest.mark.db_cleanup("knowledge")

ADMIN_TOKEN = "test-ui-admin-token"
SUPPORT_TOKEN = "test-ui-support-token"
USER_TOKEN = "test-ui-user:plain-user"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_knowledge_ai_provider_api_masks_secret_refs_and_uses_russian_messages(test_client) -> None:
    create_response = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(),
        json={
            "code": "openrouter-main",
            "title": "OpenRouter",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_secret_ref": "env:OPENROUTER_API_KEY",
            "data_policy": "no_sensitive",
        },
    )

    assert create_response.status == 200
    created = await create_response.json()
    assert created["status"] == "ok"
    assert created["display_message"] == "Провайдер AI сохранён"
    assert created["provider"]["api_key_configured"] is True
    assert created["provider"]["api_key_secret_ref_masked"] == "env:OPEN...KEY"
    assert "api_key_secret_ref" not in created["provider"]
    assert "OPENROUTER_API_KEY" not in str(created)

    patch_response = await test_client.patch(
        f"/api/web/knowledge/ai/providers/{created['provider']['provider_id']}",
        headers=_auth(),
        json={"enabled": False, "title": "OpenRouter выключен"},
    )
    assert patch_response.status == 200
    patched = await patch_response.json()
    assert patched["provider"]["enabled"] is False
    assert patched["provider"]["title"] == "OpenRouter выключен"
    assert patched["display_message"] == "Провайдер AI сохранён"

    list_response = await test_client.get("/api/web/knowledge/ai/providers", headers=_auth())
    listed = await list_response.json()
    assert list_response.status == 200
    assert listed["providers"][0]["api_key_secret_ref_masked"] == "env:OPEN...KEY"
    assert "OPENROUTER_API_KEY" not in str(listed)


@pytest.mark.asyncio
async def test_knowledge_ai_model_profile_and_policy_api_are_admin_only_and_localized(test_client) -> None:
    forbidden = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(SUPPORT_TOKEN),
        json={"code": "blocked", "title": "Blocked"},
    )
    assert forbidden.status == 403
    forbidden_payload = await forbidden.json()
    assert forbidden_payload["error_code"] == "FORBIDDEN"
    assert forbidden_payload["display_message"] == "Недостаточно прав для настройки AI"

    provider_response = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(),
        json={
            "code": "openrouter-main",
            "title": "OpenRouter",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_secret_ref": "env:OPENROUTER_API_KEY",
        },
    )
    provider = (await provider_response.json())["provider"]

    profile_response = await test_client.post(
        "/api/web/knowledge/ai/model-profiles",
        headers=_auth(),
        json={
            "provider_id": provider["provider_id"],
            "code": "answer-default",
            "title": "Ответы через OpenRouter",
            "task_type": "answer",
            "model_name": "openai/gpt-4o-mini",
            "is_default": True,
        },
    )
    assert profile_response.status == 200
    profile_payload = await profile_response.json()
    assert profile_payload["display_message"] == "Профиль модели сохранён"
    assert profile_payload["model_profile"]["task_type"] == "answer"

    policy_response = await test_client.post(
        "/api/web/knowledge/ai/policies",
        headers=_auth(),
        json={
            "policy_id": "global-answer-policy",
            "scope_type": "global",
            "task_type": "answer",
            "enabled": True,
            "ai_allowed": True,
            "answer_allowed": True,
            "allow_cloud_for_requester_safe": True,
        },
    )
    assert policy_response.status == 200
    policy_payload = await policy_response.json()
    assert policy_payload["policy"]["display_message"] == "Политика AI сохранена"
    assert policy_payload["display_message"] == "Политика AI сохранена"

    profiles_list = await (await test_client.get("/api/web/knowledge/ai/model-profiles", headers=_auth())).json()
    policies_list = await (await test_client.get("/api/web/knowledge/ai/policies", headers=_auth())).json()
    assert profiles_list["model_profiles"][0]["code"] == "answer-default"
    assert policies_list["policies"][0]["policy_id"] == "global-answer-policy"

    patch_response = await test_client.patch(
        f"/api/web/knowledge/ai/model-profiles/{profile_payload['model_profile']['profile_id']}",
        headers=_auth(),
        json={"enabled": False, "title": "Ответы OpenRouter отключены"},
    )
    assert patch_response.status == 200
    patched_profile = await patch_response.json()
    assert patched_profile["display_message"] == "Профиль модели сохранён"
    assert patched_profile["model_profile"]["enabled"] is False
    assert patched_profile["model_profile"]["title"] == "Ответы OpenRouter отключены"


@pytest.mark.asyncio
async def test_knowledge_ai_health_check_uses_masked_secret_and_records_observer_audit(
    test_client,
    test_engine,
    monkeypatch,
) -> None:
    calls: list[dict] = []

    async def fake_transport(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(knowledge_ai_handlers, "_get_openrouter_transport", lambda _request: fake_transport)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-secret")

    provider_response = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(),
        json={
            "code": "openrouter-main",
            "title": "OpenRouter",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_secret_ref": "env:OPENROUTER_API_KEY",
        },
    )
    provider = (await provider_response.json())["provider"]

    health_response = await test_client.post(
        f"/api/web/knowledge/ai/providers/{provider['provider_id']}/health-check",
        headers=_auth(),
        json={"model_name": "openai/gpt-4o-mini"},
    )

    assert health_response.status == 200
    payload = await health_response.json()
    assert payload["status"] == "ok"
    assert payload["health"]["status"] == "ok"
    assert payload["display_message"] == "Проверка OpenRouter выполнена успешно"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-test-secret"
    assert "sk-test-secret" not in str(payload)

    async with test_engine.connect() as conn:
        audit_rows = (
            await conn.execute(
                text("SELECT status, error_message_redacted FROM ai_request_audit WHERE provider_id = :provider_id"),
                {"provider_id": provider["provider_id"]},
            )
        ).mappings().all()
        runtime_rows = (
            await conn.execute(
                text(
                    "SELECT event_type, severity, details_json FROM agent_runtime_audit "
                    "WHERE event_type = 'knowledge.ai.provider_health_ok'"
                )
            )
        ).mappings().all()

    assert audit_rows[0]["status"] == "succeeded"
    assert runtime_rows[0]["severity"] == "info"
    assert runtime_rows[0]["details_json"]["provider_code"] == "openrouter-main"
    assert "sk-test-secret" not in str(runtime_rows)


@pytest.mark.asyncio
async def test_knowledge_ai_health_check_missing_secret_is_safe_russian_failure(
    test_client,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider_response = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(),
        json={
            "code": "openrouter-main",
            "title": "OpenRouter",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_secret_ref": "env:OPENROUTER_API_KEY",
        },
    )
    provider = (await provider_response.json())["provider"]

    health_response = await test_client.post(
        f"/api/web/knowledge/ai/providers/{provider['provider_id']}/health-check",
        headers=_auth(),
        json={"model_name": "openai/gpt-4o-mini"},
    )

    assert health_response.status == 200
    payload = await health_response.json()
    assert payload["status"] == "ok"
    assert payload["health"]["status"] == "failed"
    assert payload["health"]["error_code"] == "SECRET_NOT_CONFIGURED"
    assert payload["display_message"] == "Ключ OpenRouter не настроен"
    assert "OPENROUTER_API_KEY" not in str(payload)
    assert "sk-" not in str(payload)


@pytest.mark.asyncio
async def test_knowledge_ai_audit_api_lists_redacted_recent_requests(test_client, test_engine) -> None:
    provider_response = await test_client.post(
        "/api/web/knowledge/ai/providers",
        headers=_auth(),
        json={
            "code": "openrouter-main",
            "title": "OpenRouter",
            "provider_type": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_secret_ref": "env:OPENROUTER_API_KEY",
        },
    )
    provider = (await provider_response.json())["provider"]

    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO ai_request_audit (
                    audit_id, provider_id, task_type, status, error_code,
                    error_message_redacted, prompt_redacted, output_redacted,
                    metadata_json, created_at
                )
                VALUES (
                    'audit-safe-1', :provider_id, 'answer', 'failed', 'PROVIDER_UNAVAILABLE',
                    'sk-secret-raw should be redacted', '<redacted>', '<redacted>',
                    '{"provider_code": "openrouter-main"}'::jsonb, NOW()
                )
                """
            ),
            {"provider_id": provider["provider_id"]},
        )

    audit_response = await test_client.get("/api/web/knowledge/ai/audit", headers=_auth())
    assert audit_response.status == 200
    payload = await audit_response.json()
    assert payload["status"] == "ok"
    assert payload["display_message"] == "Журнал AI загружен"
    assert payload["audit"][0]["audit_id"] == "audit-safe-1"
    assert payload["audit"][0]["error_message_redacted"] == "<redacted>"
    assert "sk-secret-raw" not in str(payload)
    assert "OPENROUTER_API_KEY" not in str(payload)
