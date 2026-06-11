from __future__ import annotations

import os
from typing import Any

from aiohttp import web

from ai.contracts import AIModelProfile, AIProviderConfig
from ai.openrouter_client import OpenRouterClient
from ai.provider_registry import AIProviderRegistry
from app.db import get_session
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from auth.middleware import require_auth


def _actor(request: web.Request) -> tuple[str | None, str]:
    auth = request.get("auth_context") or request.get("auth")
    actor_id = str(getattr(auth, "actor_id", "") or "") or None
    actor_role = str(getattr(auth, "actor_role", "") or "user")
    return actor_id, actor_role


def _forbidden() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "forbidden",
            "error_code": "FORBIDDEN",
            "display_message": "Недостаточно прав для настройки AI",
        },
        status=403,
    )


async def _json_payload(request: web.Request) -> dict[str, Any]:
    if request.can_read_body:
        payload = await request.json()
        if isinstance(payload, dict):
            return payload
    return {}


def _require_admin(request: web.Request) -> web.Response | None:
    _actor_id, role = _actor(request)
    if role != "admin":
        return _forbidden()
    return None


def _resolve_secret_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if not value:
        return None
    if value.startswith("env:"):
        return os.getenv(value[4:])
    return None


def _redacted_health_error(error_code: str) -> str:
    if error_code == "SECRET_NOT_CONFIGURED":
        return "Ключ OpenRouter не настроен"
    return "Проверка провайдера AI завершилась ошибкой"


def _get_openrouter_transport(request: web.Request):
    return request.app.get("knowledge_ai_openrouter_transport")


@require_auth()
async def handle_web_knowledge_ai_providers(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, _role = _actor(request)
    try:
        async with get_session() as session:
            registry = AIProviderRegistry(session)
            if request.method == "POST":
                provider = await registry.create_provider(await _json_payload(request), actor_id=actor_id)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "provider": provider,
                        "display_message": "Провайдер AI сохранён",
                    }
                )
            providers = await registry.list_providers()
            return web.json_response({"status": "ok", "providers": providers})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры провайдера AI",
                "details": str(exc),
            },
            status=400,
        )


@require_auth()
async def handle_web_knowledge_ai_provider_detail(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, _role = _actor(request)
    provider_id = str(request.match_info.get("provider_id") or "")
    try:
        async with get_session() as session:
            provider = await AIProviderRegistry(session).update_provider(
                provider_id,
                await _json_payload(request),
                actor_id=actor_id,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "provider": provider,
                "display_message": "Провайдер AI сохранён",
            }
        )
    except ValueError:
        return web.json_response(
            {
                "status": "error",
                "error": "not_found",
                "error_code": "NOT_FOUND",
                "display_message": "Провайдер AI не найден",
            },
            status=404,
        )


@require_auth()
async def handle_web_knowledge_ai_model_profiles(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, _role = _actor(request)
    try:
        async with get_session() as session:
            registry = AIProviderRegistry(session)
            if request.method == "POST":
                model_profile = await registry.create_model_profile(await _json_payload(request), actor_id=actor_id)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "model_profile": model_profile,
                        "display_message": "Профиль модели сохранён",
                    }
                )
            return web.json_response({"status": "ok", "model_profiles": await registry.list_model_profiles()})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры профиля модели",
                "details": str(exc),
            },
            status=400,
        )


@require_auth()
async def handle_web_knowledge_ai_model_profile_detail(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, _role = _actor(request)
    profile_id = str(request.match_info.get("profile_id") or "")
    try:
        async with get_session() as session:
            model_profile = await AIProviderRegistry(session).update_model_profile(
                profile_id,
                await _json_payload(request),
                actor_id=actor_id,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "model_profile": model_profile,
                "display_message": "Профиль модели сохранён",
            }
        )
    except ValueError:
        return web.json_response(
            {
                "status": "error",
                "error": "not_found",
                "error_code": "NOT_FOUND",
                "display_message": "Профиль модели не найден",
            },
            status=404,
        )


@require_auth()
async def handle_web_knowledge_ai_policies(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, _role = _actor(request)
    try:
        async with get_session() as session:
            registry = AIProviderRegistry(session)
            if request.method == "POST":
                policy = await registry.upsert_policy(await _json_payload(request), actor_id=actor_id)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "policy": policy,
                        "display_message": "Политика AI сохранена",
                    }
                )
            return web.json_response({"status": "ok", "policies": await registry.list_policies()})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры политики AI",
                "details": str(exc),
            },
            status=400,
        )


@require_auth()
async def handle_web_knowledge_ai_audit(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    try:
        limit = int(request.query.get("limit") or "50")
    except ValueError:
        limit = 50
    async with get_session() as session:
        audit_rows = await AIProviderRegistry(session).list_audit(limit=limit)
    return web.json_response(
        {
            "status": "ok",
            "audit": audit_rows,
            "display_message": "Журнал AI загружен",
        }
    )


@require_auth()
async def handle_web_knowledge_ai_provider_health_check(request: web.Request) -> web.Response:
    if error := _require_admin(request):
        return error
    actor_id, actor_role = _actor(request)
    provider_id = str(request.match_info.get("provider_id") or "")
    payload = await _json_payload(request)
    model_name = str(payload.get("model_name") or "openai/gpt-4o-mini").strip()
    async with get_session() as session:
        registry = AIProviderRegistry(session)
        try:
            provider = await registry.get_provider_internal(provider_id)
        except ValueError:
            return web.json_response(
                {
                    "status": "error",
                    "error": "not_found",
                    "error_code": "NOT_FOUND",
                    "display_message": "Провайдер AI не найден",
                },
                status=404,
            )

        provider_code = str(provider.get("code") or "")
        provider_type = str(provider.get("provider_type") or "")
        api_key = _resolve_secret_ref(provider.get("api_key_secret_ref"))
        if provider.get("auth_type") != "none" and not api_key:
            await registry.update_provider_health(provider_id, status="failed", error_message_redacted="secret missing")
            await registry.record_audit(
                {
                    "provider_id": provider_id,
                    "task_type": "health_check",
                    "status": "failed",
                    "error_code": "SECRET_NOT_CONFIGURED",
                    "error_message": "OPENROUTER_API_KEY missing",
                }
            )
            await AgentRuntimeAuditRepo(session).add(
                device_id="server",
                event_type="knowledge.ai.provider_health_failed",
                severity="warning",
                source="knowledge_ai",
                actor_id=actor_id,
                actor_role=actor_role,
                details_json={
                    "provider_id": provider_id,
                    "provider_code": provider_code,
                    "provider_type": provider_type,
                    "error_code": "SECRET_NOT_CONFIGURED",
                },
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "ok",
                    "health": {
                        "provider_id": provider_id,
                        "status": "failed",
                        "error_code": "SECRET_NOT_CONFIGURED",
                    },
                    "display_message": _redacted_health_error("SECRET_NOT_CONFIGURED"),
                }
            )

        try:
            transport = _get_openrouter_transport(request)
            if transport is None:
                raise RuntimeError("health transport is not configured")
            client = OpenRouterClient(
                AIProviderConfig(
                    provider_id=provider_id,
                    code=provider_code,
                    base_url=str(provider.get("base_url") or "https://openrouter.ai/api/v1"),
                    api_key=api_key,
                ),
                transport=transport,
            )
            await client.chat_completion(
                AIModelProfile(
                    profile_id="health-check",
                    provider_id=provider_id,
                    task_type="health_check",
                    model_name=model_name,
                    timeout_ms=int(payload.get("timeout_ms") or 15_000),
                    temperature=0,
                ),
                messages=[{"role": "user", "content": "ping"}],
                metadata={"source": "knowledge_ai_health_check"},
            )
            await registry.update_provider_health(provider_id, status="ok")
            await registry.record_audit(
                {
                    "provider_id": provider_id,
                    "task_type": "health_check",
                    "status": "succeeded",
                    "metadata_json": {"provider_code": provider_code},
                }
            )
            await AgentRuntimeAuditRepo(session).add(
                device_id="server",
                event_type="knowledge.ai.provider_health_ok",
                severity="info",
                source="knowledge_ai",
                actor_id=actor_id,
                actor_role=actor_role,
                details_json={
                    "provider_id": provider_id,
                    "provider_code": provider_code,
                    "provider_type": provider_type,
                },
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "ok",
                    "health": {
                        "provider_id": provider_id,
                        "status": "ok",
                    },
                    "display_message": "Проверка OpenRouter выполнена успешно",
                }
            )
        except Exception as exc:
            await registry.update_provider_health(provider_id, status="failed", error_message_redacted=str(exc))
            await registry.record_audit(
                {
                    "provider_id": provider_id,
                    "task_type": "health_check",
                    "status": "failed",
                    "error_code": "PROVIDER_UNAVAILABLE",
                    "error_message": str(exc),
                }
            )
            await AgentRuntimeAuditRepo(session).add(
                device_id="server",
                event_type="knowledge.ai.provider_health_failed",
                severity="warning",
                source="knowledge_ai",
                actor_id=actor_id,
                actor_role=actor_role,
                details_json={
                    "provider_id": provider_id,
                    "provider_code": provider_code,
                    "provider_type": provider_type,
                    "error_code": "PROVIDER_UNAVAILABLE",
                },
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "ok",
                    "health": {
                        "provider_id": provider_id,
                        "status": "failed",
                        "error_code": "PROVIDER_UNAVAILABLE",
                    },
                    "display_message": _redacted_health_error("PROVIDER_UNAVAILABLE"),
                }
            )
