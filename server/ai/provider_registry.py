from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json
import re
import uuid

from sqlalchemy import text


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mask_secret_ref(secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    if secret_ref.startswith("env:"):
        name = secret_ref[4:]
        if len(name) <= 6:
            return "env:***"
        return f"env:{name[:4]}...{name[-3:]}"
    return "***"


def _jsonb(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _redact_error(message: str | None) -> str | None:
    text_value = str(message or "")
    if "OPENROUTER_API_KEY" in text_value or "API_KEY" in text_value:
        return "env secret missing"
    return re.sub(r"sk-[A-Za-z0-9_-]+", "<redacted>", text_value) or None


def _provider_payload(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    secret_ref = data.pop("api_key_secret_ref", None)
    data["api_key_configured"] = bool(secret_ref)
    data["api_key_secret_ref_masked"] = _mask_secret_ref(secret_ref)
    return data


class AIProviderRegistry:
    def __init__(self, session_or_connection):
        self.db = session_or_connection

    async def create_provider(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        provider_id = str(payload.get("provider_id") or _new_id())
        now = _now()
        values = {
            "provider_id": provider_id,
            "code": str(payload["code"]).strip(),
            "title": str(payload.get("title") or payload["code"]).strip(),
            "provider_type": str(payload.get("provider_type") or "openrouter"),
            "base_url": str(payload.get("base_url") or "").rstrip("/") or None,
            "auth_type": str(payload.get("auth_type") or "api_key"),
            "api_key_secret_ref": payload.get("api_key_secret_ref"),
            "default_headers_json": _jsonb(payload.get("default_headers_json") or {}),
            "data_policy": str(payload.get("data_policy") or "no_sensitive"),
            "enabled": bool(payload.get("enabled", True)),
            "metadata_json": _jsonb(payload.get("metadata_json") or {}),
            "created_at": now,
            "updated_at": now,
            "created_by": actor_id,
            "updated_by": actor_id,
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO ai_providers (
                        provider_id, code, title, provider_type, base_url, auth_type,
                        api_key_secret_ref, default_headers_json, data_policy, enabled,
                        metadata_json, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (
                        :provider_id, :code, :title, :provider_type, :base_url, :auth_type,
                        :api_key_secret_ref, :default_headers_json, :data_policy, :enabled,
                        :metadata_json, :created_at, :updated_at, :created_by, :updated_by
                    )
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        return _provider_payload(row)

    async def list_providers(self) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                text("SELECT * FROM ai_providers ORDER BY created_at DESC, provider_id DESC")
            )
        ).all()
        return [_provider_payload(row) for row in rows]

    async def create_model_profile(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        profile_id = str(payload.get("profile_id") or _new_id())
        now = _now()
        values = {
            "profile_id": profile_id,
            "provider_id": payload["provider_id"],
            "code": str(payload["code"]).strip(),
            "title": str(payload.get("title") or payload["code"]).strip(),
            "task_type": str(payload["task_type"]).strip(),
            "model_name": str(payload["model_name"]).strip(),
            "context_window": payload.get("context_window"),
            "embedding_dimensions": payload.get("embedding_dimensions"),
            "timeout_ms": int(payload.get("timeout_ms") or 30_000),
            "max_retries": int(payload.get("max_retries") or 0),
            "temperature": payload.get("temperature"),
            "top_p": payload.get("top_p"),
            "structured_output_supported": bool(payload.get("structured_output_supported", False)),
            "streaming_supported": bool(payload.get("streaming_supported", False)),
            "enabled": bool(payload.get("enabled", True)),
            "is_default": bool(payload.get("is_default", False)),
            "fallback_profile_id": payload.get("fallback_profile_id"),
            "metadata_json": _jsonb(payload.get("metadata_json") or {}),
            "created_at": now,
            "updated_at": now,
            "created_by": actor_id,
            "updated_by": actor_id,
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO ai_model_profiles (
                        profile_id, provider_id, code, title, task_type, model_name,
                        context_window, embedding_dimensions, timeout_ms, max_retries,
                        temperature, top_p, structured_output_supported, streaming_supported,
                        enabled, is_default, fallback_profile_id, metadata_json,
                        created_at, updated_at, created_by, updated_by
                    )
                    VALUES (
                        :profile_id, :provider_id, :code, :title, :task_type, :model_name,
                        :context_window, :embedding_dimensions, :timeout_ms, :max_retries,
                        :temperature, :top_p, :structured_output_supported, :streaming_supported,
                        :enabled, :is_default, :fallback_profile_id, :metadata_json,
                        :created_at, :updated_at, :created_by, :updated_by
                    )
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        return dict(row._mapping)

    async def upsert_policy(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        policy_id = str(payload.get("policy_id") or _new_id())
        now = _now()
        values = {
            "policy_id": policy_id,
            "scope_type": str(payload.get("scope_type") or "global"),
            "space_id": payload.get("space_id"),
            "visibility": payload.get("visibility"),
            "task_type": payload.get("task_type"),
            "enabled": bool(payload.get("enabled", True)),
            "ai_allowed": bool(payload.get("ai_allowed", False)),
            "embedding_allowed": bool(payload.get("embedding_allowed", False)),
            "rerank_allowed": bool(payload.get("rerank_allowed", False)),
            "answer_allowed": bool(payload.get("answer_allowed", False)),
            "rewrite_allowed": bool(payload.get("rewrite_allowed", False)),
            "auto_markup_allowed": bool(payload.get("auto_markup_allowed", False)),
            "require_local_for_security_restricted": bool(payload.get("require_local_for_security_restricted", True)),
            "allow_cloud_for_requester_safe": bool(payload.get("allow_cloud_for_requester_safe", False)),
            "redact_before_send": bool(payload.get("redact_before_send", True)),
            "store_prompts": bool(payload.get("store_prompts", False)),
            "store_outputs": bool(payload.get("store_outputs", False)),
            "max_tokens_per_request": payload.get("max_tokens_per_request"),
            "max_requests_per_day": payload.get("max_requests_per_day"),
            "max_cost_per_day": payload.get("max_cost_per_day"),
            "metadata_json": _jsonb(payload.get("metadata_json") or {}),
            "created_at": now,
            "updated_at": now,
            "created_by": actor_id,
            "updated_by": actor_id,
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO ai_policy_profiles (
                        policy_id, scope_type, space_id, visibility, task_type, enabled,
                        ai_allowed, embedding_allowed, rerank_allowed, answer_allowed,
                        rewrite_allowed, auto_markup_allowed, require_local_for_security_restricted,
                        allow_cloud_for_requester_safe, redact_before_send, store_prompts,
                        store_outputs, max_tokens_per_request, max_requests_per_day,
                        max_cost_per_day, metadata_json, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (
                        :policy_id, :scope_type, :space_id, :visibility, :task_type, :enabled,
                        :ai_allowed, :embedding_allowed, :rerank_allowed, :answer_allowed,
                        :rewrite_allowed, :auto_markup_allowed, :require_local_for_security_restricted,
                        :allow_cloud_for_requester_safe, :redact_before_send, :store_prompts,
                        :store_outputs, :max_tokens_per_request, :max_requests_per_day,
                        :max_cost_per_day, :metadata_json, :created_at, :updated_at, :created_by, :updated_by
                    )
                    ON CONFLICT (policy_id) DO UPDATE SET
                        scope_type = EXCLUDED.scope_type,
                        space_id = EXCLUDED.space_id,
                        visibility = EXCLUDED.visibility,
                        task_type = EXCLUDED.task_type,
                        enabled = EXCLUDED.enabled,
                        ai_allowed = EXCLUDED.ai_allowed,
                        embedding_allowed = EXCLUDED.embedding_allowed,
                        rerank_allowed = EXCLUDED.rerank_allowed,
                        answer_allowed = EXCLUDED.answer_allowed,
                        rewrite_allowed = EXCLUDED.rewrite_allowed,
                        auto_markup_allowed = EXCLUDED.auto_markup_allowed,
                        require_local_for_security_restricted = EXCLUDED.require_local_for_security_restricted,
                        allow_cloud_for_requester_safe = EXCLUDED.allow_cloud_for_requester_safe,
                        redact_before_send = EXCLUDED.redact_before_send,
                        store_prompts = EXCLUDED.store_prompts,
                        store_outputs = EXCLUDED.store_outputs,
                        max_tokens_per_request = EXCLUDED.max_tokens_per_request,
                        max_requests_per_day = EXCLUDED.max_requests_per_day,
                        max_cost_per_day = EXCLUDED.max_cost_per_day,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        data = dict(row._mapping)
        data["display_message"] = "Политика AI сохранена"
        return data

    async def record_audit(self, payload: dict[str, Any]) -> dict[str, Any]:
        audit_id = str(payload.get("audit_id") or _new_id())
        values = {
            "audit_id": audit_id,
            "provider_id": payload.get("provider_id"),
            "model_profile_id": payload.get("model_profile_id"),
            "task_type": payload.get("task_type"),
            "status": payload.get("status"),
            "error_code": payload.get("error_code"),
            "error_message_redacted": _redact_error(payload.get("error_message")),
            "prompt_redacted": "<redacted>" if payload.get("prompt_redacted") else None,
            "output_redacted": "<redacted>" if payload.get("output_redacted") else None,
            "metadata_json": _jsonb(payload.get("metadata_json") or {}),
            "created_at": _now(),
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO ai_request_audit (
                        audit_id, provider_id, model_profile_id, task_type, status,
                        error_code, error_message_redacted, prompt_redacted, output_redacted,
                        metadata_json, created_at
                    )
                    VALUES (
                        :audit_id, :provider_id, :model_profile_id, :task_type, :status,
                        :error_code, :error_message_redacted, :prompt_redacted, :output_redacted,
                        :metadata_json, :created_at
                    )
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        return dict(row._mapping)
