from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import json

from sqlalchemy import text


SEARCH_SETTINGS_ID = "global"

ALLOWED_SEARCH_MODES = {
    "keyword_only",
    "full_text",
    "hybrid_no_ai",
    "hybrid_vector",
    "hybrid_vector_rerank",
    "rag_answer",
}

DEFAULT_SEARCH_SETTINGS: dict[str, Any] = {
    "settings_id": SEARCH_SETTINGS_ID,
    "scope_type": "global",
    "space_id": None,
    "visibility": None,
    "search_mode": "keyword_only",
    "enabled": True,
    "keyword_enabled": True,
    "full_text_enabled": False,
    "vector_enabled": False,
    "rerank_enabled": False,
    "ai_query_rewrite_enabled": False,
    "rag_answer_enabled": False,
    "keyword_weight": 1.0,
    "full_text_weight": 1.0,
    "vector_weight": 1.0,
    "max_results": 10,
    "snippet_length": 180,
    "metadata_json": {},
    "created_at": None,
    "updated_at": None,
    "created_by": None,
    "updated_by": None,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonb(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _serialize_row(row: Any) -> dict[str, Any]:
    data = dict(row._mapping if hasattr(row, "_mapping") else row)
    return {key: _serialize_value(value) for key, value in data.items()}


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    return bool(value)


def _with_effective_mode(settings: dict[str, Any]) -> dict[str, Any]:
    mode = str(settings.get("search_mode") or "keyword_only")
    enabled = bool(settings.get("enabled", True))
    keyword_enabled = bool(settings.get("keyword_enabled", True))
    full_text_enabled = bool(settings.get("full_text_enabled", False))
    vector_enabled = bool(settings.get("vector_enabled", False))
    rerank_enabled = bool(settings.get("rerank_enabled", False))
    rewrite_enabled = bool(settings.get("ai_query_rewrite_enabled", False))
    rag_enabled = bool(settings.get("rag_answer_enabled", False))

    ai_enabled = vector_enabled or rerank_enabled or rewrite_enabled or rag_enabled
    if not enabled:
        effective_mode = "keyword_only"
    elif mode == "rag_answer" and rag_enabled and vector_enabled:
        effective_mode = "rag_answer"
    elif vector_enabled and rerank_enabled:
        effective_mode = "hybrid_vector_rerank"
    elif vector_enabled:
        effective_mode = "hybrid_vector"
    elif full_text_enabled and keyword_enabled:
        effective_mode = "hybrid_no_ai"
    elif full_text_enabled:
        effective_mode = "full_text"
    else:
        effective_mode = "keyword_only"

    payload = dict(settings)
    payload["search_mode"] = mode if mode in ALLOWED_SEARCH_MODES else "keyword_only"
    payload["effective_mode"] = effective_mode
    payload["fallback_mode"] = effective_mode if effective_mode != payload["search_mode"] else None
    payload["ai_enabled"] = ai_enabled and effective_mode in {"hybrid_vector", "hybrid_vector_rerank", "rag_answer"}
    return payload


class KnowledgeSearchSettingsService:
    def __init__(self, session_or_connection):
        self.db = session_or_connection

    async def get_settings(self) -> dict[str, Any]:
        row = (
            await self.db.execute(
                text("SELECT * FROM knowledge_search_settings WHERE settings_id = :settings_id"),
                {"settings_id": SEARCH_SETTINGS_ID},
            )
        ).first()
        if row is None:
            return _with_effective_mode(dict(DEFAULT_SEARCH_SETTINGS))
        return _with_effective_mode(_serialize_row(row))

    async def upsert_settings(self, payload: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        existing = await self.get_settings()
        search_mode = str(payload.get("search_mode", existing["search_mode"]) or "keyword_only").strip()
        if search_mode not in ALLOWED_SEARCH_MODES:
            raise ValueError("unsupported search_mode")

        now = _now()
        values = {
            "settings_id": SEARCH_SETTINGS_ID,
            "scope_type": "global",
            "space_id": None,
            "visibility": None,
            "search_mode": search_mode,
            "enabled": _bool(payload.get("enabled"), default=bool(existing.get("enabled", True))),
            "keyword_enabled": _bool(payload.get("keyword_enabled"), default=bool(existing.get("keyword_enabled", True))),
            "full_text_enabled": _bool(payload.get("full_text_enabled"), default=bool(existing.get("full_text_enabled", False))),
            "vector_enabled": _bool(payload.get("vector_enabled"), default=bool(existing.get("vector_enabled", False))),
            "rerank_enabled": _bool(payload.get("rerank_enabled"), default=bool(existing.get("rerank_enabled", False))),
            "ai_query_rewrite_enabled": _bool(
                payload.get("ai_query_rewrite_enabled"),
                default=bool(existing.get("ai_query_rewrite_enabled", False)),
            ),
            "rag_answer_enabled": _bool(payload.get("rag_answer_enabled"), default=bool(existing.get("rag_answer_enabled", False))),
            "keyword_weight": _bounded_float(payload.get("keyword_weight"), default=float(existing.get("keyword_weight") or 1.0), minimum=0.0, maximum=10.0),
            "full_text_weight": _bounded_float(payload.get("full_text_weight"), default=float(existing.get("full_text_weight") or 1.0), minimum=0.0, maximum=10.0),
            "vector_weight": _bounded_float(payload.get("vector_weight"), default=float(existing.get("vector_weight") or 1.0), minimum=0.0, maximum=10.0),
            "max_results": _bounded_int(payload.get("max_results"), default=int(existing.get("max_results") or 10), minimum=1, maximum=50),
            "snippet_length": _bounded_int(payload.get("snippet_length"), default=int(existing.get("snippet_length") or 180), minimum=80, maximum=1000),
            "metadata_json": _jsonb(payload.get("metadata_json", existing.get("metadata_json") or {})),
            "created_at": now,
            "updated_at": now,
            "created_by": existing.get("created_by") or actor_id,
            "updated_by": actor_id,
        }
        row = (
            await self.db.execute(
                text(
                    """
                    INSERT INTO knowledge_search_settings (
                        settings_id, scope_type, space_id, visibility, search_mode, enabled,
                        keyword_enabled, full_text_enabled, vector_enabled, rerank_enabled,
                        ai_query_rewrite_enabled, rag_answer_enabled, keyword_weight,
                        full_text_weight, vector_weight, max_results, snippet_length,
                        metadata_json, created_at, updated_at, created_by, updated_by
                    )
                    VALUES (
                        :settings_id, :scope_type, :space_id, :visibility, :search_mode, :enabled,
                        :keyword_enabled, :full_text_enabled, :vector_enabled, :rerank_enabled,
                        :ai_query_rewrite_enabled, :rag_answer_enabled, :keyword_weight,
                        :full_text_weight, :vector_weight, :max_results, :snippet_length,
                        CAST(:metadata_json AS jsonb), :created_at, :updated_at, :created_by, :updated_by
                    )
                    ON CONFLICT (settings_id) DO UPDATE SET
                        search_mode = EXCLUDED.search_mode,
                        enabled = EXCLUDED.enabled,
                        keyword_enabled = EXCLUDED.keyword_enabled,
                        full_text_enabled = EXCLUDED.full_text_enabled,
                        vector_enabled = EXCLUDED.vector_enabled,
                        rerank_enabled = EXCLUDED.rerank_enabled,
                        ai_query_rewrite_enabled = EXCLUDED.ai_query_rewrite_enabled,
                        rag_answer_enabled = EXCLUDED.rag_answer_enabled,
                        keyword_weight = EXCLUDED.keyword_weight,
                        full_text_weight = EXCLUDED.full_text_weight,
                        vector_weight = EXCLUDED.vector_weight,
                        max_results = EXCLUDED.max_results,
                        snippet_length = EXCLUDED.snippet_length,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                    RETURNING *
                    """
                ),
                values,
            )
        ).first()
        return _with_effective_mode(_serialize_row(row))

    async def search_metadata(self) -> dict[str, Any]:
        settings = await self.get_settings()
        return {
            "search_mode": settings["search_mode"],
            "effective_mode": settings["effective_mode"],
            "ai_used": bool(settings["ai_enabled"]),
            "settings": settings,
        }
