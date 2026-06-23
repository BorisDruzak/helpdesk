from __future__ import annotations

import pytest
from sqlalchemy import text

from ai.provider_registry import AIProviderRegistry

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_ai_settings_tables_exist_after_migration(test_engine) -> None:
    expected = {
        "ai_providers",
        "ai_model_profiles",
        "ai_policy_profiles",
        "ai_request_audit",
    }
    async with test_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name LIKE 'ai_%'"
                )
            )
        ).scalars().all()

    assert expected <= set(rows)


@pytest.mark.asyncio
async def test_ai_provider_crud_masks_env_secret_ref(test_engine) -> None:
    async with test_engine.begin() as conn:
        registry = AIProviderRegistry(conn)
        provider = await registry.create_provider(
            {
                "code": "openrouter-main",
                "title": "OpenRouter",
                "provider_type": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "auth_type": "api_key",
                "api_key_secret_ref": "env:OPENROUTER_API_KEY",
                "data_policy": "no_sensitive",
                "enabled": True,
            },
            actor_id="admin",
        )

        assert provider["provider_type"] == "openrouter"
        assert provider["api_key_configured"] is True
        assert provider["api_key_secret_ref_masked"] == "env:OPEN...KEY"
        assert "api_key_secret_ref" not in provider

        providers = await registry.list_providers()
        assert providers[0]["api_key_secret_ref_masked"] == "env:OPEN...KEY"
        assert "OPENROUTER_API_KEY" not in str(providers)


@pytest.mark.asyncio
async def test_ai_model_profile_and_policy_defaults(test_engine) -> None:
    async with test_engine.begin() as conn:
        registry = AIProviderRegistry(conn)
        provider = await registry.create_provider(
            {
                "code": "openrouter-main",
                "title": "OpenRouter",
                "provider_type": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_secret_ref": "env:OPENROUTER_API_KEY",
            },
            actor_id="admin",
        )
        profile = await registry.create_model_profile(
            {
                "provider_id": provider["provider_id"],
                "code": "answer-default",
                "title": "Ответы через OpenRouter",
                "task_type": "answer",
                "model_name": "openai/gpt-4o-mini",
                "timeout_ms": 30_000,
                "max_retries": 2,
                "is_default": True,
            },
            actor_id="admin",
        )
        policy = await registry.upsert_policy(
            {
                "policy_id": "global-answer-policy",
                "scope_type": "global",
                "task_type": "answer",
                "enabled": True,
                "ai_allowed": True,
                "answer_allowed": True,
                "require_local_for_security_restricted": True,
                "allow_cloud_for_requester_safe": True,
            },
            actor_id="admin",
        )

        assert profile["task_type"] == "answer"
        assert profile["is_default"] is True
        assert policy["scope_type"] == "global"
        assert policy["require_local_for_security_restricted"] is True
        assert policy["display_message"] == "Политика AI сохранена"

        updated_policy = await registry.upsert_policy(
            {
                "policy_id": "global-answer-policy",
                "scope_type": "global",
                "task_type": "answer",
                "enabled": True,
                "ai_allowed": False,
                "answer_allowed": False,
            },
            actor_id="admin-2",
        )

        assert updated_policy["policy_id"] == "global-answer-policy"
        assert updated_policy["ai_allowed"] is False
        assert updated_policy["answer_allowed"] is False
        assert updated_policy["updated_by"] == "admin-2"


@pytest.mark.asyncio
async def test_ai_request_audit_redacts_secrets_and_prompts(test_engine) -> None:
    async with test_engine.begin() as conn:
        registry = AIProviderRegistry(conn)
        provider = await registry.create_provider(
            {
                "code": "openrouter-main",
                "title": "OpenRouter",
                "provider_type": "openrouter",
                "api_key_secret_ref": "env:OPENROUTER_API_KEY",
            },
            actor_id="admin",
        )
        audit = await registry.record_audit(
            {
                "provider_id": provider["provider_id"],
                "task_type": "answer",
                "status": "failed",
                "error_code": "secret_missing",
                "error_message": "OPENROUTER_API_KEY missing",
                "prompt_redacted": "Как настроить VPN?",
                "output_redacted": None,
            }
        )

        assert audit["error_message_redacted"] == "env secret missing"
        assert "OPENROUTER_API_KEY" not in str(audit)
        assert audit["prompt_redacted"] == "<redacted>"
