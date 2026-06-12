from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.contracts import AIModelProfile, AIProviderConfig
from ai.openrouter_client import OpenRouterClient
from knowledge.retrieval_service import KnowledgeRetrievalService
from knowledge.search_settings_service import KnowledgeSearchSettingsService


Transport = Callable[..., Awaitable[dict[str, Any]]]
_CITATION_MARK_RE = re.compile(r"\[(\d{1,2})\]")
_CRITICAL_CLAIM_RE = re.compile(
    r"("
    r"access|delete|disable|enable|install|must|password|reset|security|should|vpn|"
    r"доступ|отключ|парол|сброс|удал|установ|mfa"
    r")",
    re.IGNORECASE,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _resolve_secret_ref(secret_ref: str | None) -> str | None:
    value = str(secret_ref or "").strip()
    if value.startswith("env:"):
        return os.getenv(value[4:])
    return None


class KnowledgeAskService:
    def __init__(self, session: AsyncSession, *, transport: Transport | None = None):
        self.session = session
        self.transport = transport

    async def ask(
        self,
        *,
        query: str | None,
        actor_role: str,
        surface: str = "knowledge_ask",
        session_id: str | None = None,
        limit: int | None = None,
        query_vector: list[float] | None = None,
    ) -> dict[str, Any]:
        query_text = str(query or "").strip()
        settings = await KnowledgeSearchSettingsService(self.session).get_settings()
        retrieval = await KnowledgeRetrievalService(self.session, transport=self.transport).retrieve(
            query=query_text,
            actor_role=actor_role,
            surface=surface,
            session_id=session_id,
            limit=limit,
            query_vector=query_vector,
        )
        retrieval_results = list(retrieval.get("results") or [])
        citations = self._collect_citations(retrieval_results)

        if not bool(settings.get("rag_answer_enabled")) or settings.get("effective_mode") != "rag_answer":
            await self._record_observer_event(
                "knowledge.rag.ai_disabled",
                actor_role=actor_role,
                details={"surface": surface, "result_count": len(retrieval_results), "effective_mode": settings.get("effective_mode")},
            )
            return self._fallback_response(
                answer_status="ai_disabled",
                display_message="AI-ответы отключены. Ниже показаны результаты поиска по базе знаний.",
                retrieval=retrieval,
                citations=citations,
            )

        if not retrieval_results or not citations:
            await self._record_observer_event(
                "knowledge.rag.not_enough_evidence",
                actor_role=actor_role,
                details={"surface": surface, "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="not_enough_evidence",
                display_message="В базе знаний недостаточно подтверждённых материалов для ответа.",
                retrieval=retrieval,
                citations=[],
            )

        profile = await self._get_ai_profile("answer")
        provider = await self._get_provider(profile["provider_id"]) if profile else None
        policy_allowed = await self._ai_task_allowed("answer")
        if not policy_allowed:
            audit_id = await self._record_ai_audit(
                provider_id=provider.get("provider_id") if provider else None,
                model_profile_id=profile.get("profile_id") if profile else None,
                status="blocked",
                error_code="POLICY_BLOCKED",
                error_message="AI answer is blocked by policy",
                metadata={"surface": surface},
            )
            await self._record_observer_event(
                "knowledge.rag.policy_blocked",
                actor_role=actor_role,
                details={"surface": surface, "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="policy_blocked",
                display_message="AI-ответ заблокирован политикой. Ниже показаны результаты поиска.",
                retrieval=retrieval,
                citations=citations,
                audit_id=audit_id,
            )

        api_key = _resolve_secret_ref(provider.get("api_key_secret_ref")) if provider else None
        if not profile or not provider or not api_key or self.transport is None:
            audit_id = await self._record_ai_audit(
                provider_id=provider.get("provider_id") if provider else None,
                model_profile_id=profile.get("profile_id") if profile else None,
                status="failed",
                error_code="PROVIDER_UNAVAILABLE",
                error_message="AI answer provider is not configured or unavailable",
                metadata={"surface": surface},
            )
            await self._record_observer_event(
                "knowledge.rag.provider_unavailable",
                actor_role=actor_role,
                details={"surface": surface, "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="provider_unavailable",
                display_message="AI-провайдер недоступен. Ниже показаны результаты поиска.",
                retrieval=retrieval,
                citations=citations,
                audit_id=audit_id,
            )

        prompt = self._build_prompt(query_text, citations)
        try:
            client = OpenRouterClient(
                AIProviderConfig(
                    provider_id=str(provider["provider_id"]),
                    code=str(provider["code"]),
                    base_url=str(provider.get("base_url") or "https://openrouter.ai/api/v1"),
                    api_key=api_key,
                ),
                transport=self.transport,
            )
            ai_result = await client.chat_completion(
                AIModelProfile(
                    profile_id=str(profile["profile_id"]),
                    provider_id=str(profile["provider_id"]),
                    task_type="answer",
                    model_name=str(profile["model_name"]),
                    timeout_ms=int(profile.get("timeout_ms") or 30_000),
                    temperature=float(profile["temperature"]) if profile.get("temperature") is not None else None,
                ),
                messages=[
                    {
                        "role": "system",
                        "content": "Отвечай только по предоставленным источникам. Добавляй ссылки вида [1], [2].",
                    },
                    {"role": "user", "content": prompt},
                ],
                metadata={"surface": surface, "actor_role": actor_role},
            )
        except Exception:
            audit_id = await self._record_ai_audit(
                provider_id=str(provider["provider_id"]),
                model_profile_id=str(profile["profile_id"]),
                status="failed",
                error_code="REQUEST_FAILED",
                error_message="AI answer request failed",
                metadata={"surface": surface},
            )
            await self._record_observer_event(
                "knowledge.rag.provider_unavailable",
                actor_role=actor_role,
                details={"surface": surface, "reason": "request_failed", "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="provider_unavailable",
                display_message="AI-провайдер недоступен. Ниже показаны результаты поиска.",
                retrieval=retrieval,
                citations=citations,
                audit_id=audit_id,
            )

        answer = str(ai_result.output_text or "").strip()
        if not answer:
            await self._record_observer_event(
                "knowledge.rag.not_enough_evidence",
                actor_role=actor_role,
                details={"surface": surface, "reason": "empty_answer", "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="not_enough_evidence",
                display_message="AI не смог подготовить подтверждённый ответ по материалам базы знаний.",
                retrieval=retrieval,
                citations=citations,
            )

        citation_error = self._answer_citation_error(answer, citations)
        if citation_error:
            audit_id = await self._record_ai_audit(
                provider_id=str(provider["provider_id"]),
                model_profile_id=str(profile["profile_id"]),
                status="blocked",
                error_code=citation_error,
                error_message="AI answer failed citation validation",
                prompt=prompt,
                output=answer,
                metadata={"surface": surface, "citation_count": len(citations)},
            )
            await self._record_observer_event(
                "knowledge.rag.not_enough_evidence",
                actor_role=actor_role,
                details={"surface": surface, "reason": citation_error.lower(), "result_count": len(retrieval_results)},
            )
            return self._fallback_response(
                answer_status="not_enough_evidence",
                display_message="AI не смог подготовить подтверждённый ответ по материалам базы знаний.",
                retrieval=retrieval,
                citations=citations,
                audit_id=audit_id,
            )

        audit_id = await self._record_ai_audit(
            provider_id=str(provider["provider_id"]),
            model_profile_id=str(profile["profile_id"]),
            status="ok",
            prompt=prompt,
            output=answer,
            metadata={"surface": surface, "citation_count": len(citations)},
        )
        await self._record_observer_event(
            "knowledge.rag.answer_generated",
            actor_role=actor_role,
            details={"surface": surface, "citation_count": len(citations), "result_count": len(retrieval_results)},
        )
        return {
            "answer": answer,
            "answer_status": "answered",
            "citations": citations,
            "retrieval_results": retrieval_results,
            "confidence": "medium",
            "suggested_actions": [{"type": "view_citations", "label": "Открыть источники"}],
            "observer_event_id": None,
            "audit_id": audit_id,
            "ai_used": True,
            "search_mode": retrieval.get("search_mode"),
            "effective_mode": retrieval.get("effective_mode"),
            "fallback_mode": retrieval.get("fallback_mode"),
            "display_message": "AI-ответ подготовлен по материалам базы знаний.",
        }

    def _fallback_response(
        self,
        *,
        answer_status: str,
        display_message: str,
        retrieval: dict[str, Any],
        citations: list[dict[str, Any]],
        audit_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "answer": None,
            "answer_status": answer_status,
            "citations": citations,
            "retrieval_results": list(retrieval.get("results") or []),
            "confidence": "none",
            "suggested_actions": [{"type": "search", "label": "Посмотреть результаты поиска"}],
            "observer_event_id": None,
            "audit_id": audit_id,
            "ai_used": False,
            "search_mode": retrieval.get("search_mode"),
            "effective_mode": retrieval.get("effective_mode"),
            "fallback_mode": retrieval.get("fallback_mode"),
            "display_message": display_message,
        }

    def _collect_citations(self, retrieval_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        seen: set[str] = set()
        for result in retrieval_results:
            for citation in result.get("citations") or []:
                ref = str(citation.get("chunk_id") or citation.get("segment_id") or citation.get("item_id") or "")
                if not ref or ref in seen:
                    continue
                seen.add(ref)
                citations.append(
                    {
                        "ref_id": ref,
                        "item_id": citation.get("item_id"),
                        "version_id": citation.get("version_id"),
                        "chunk_id": citation.get("chunk_id"),
                        "segment_id": citation.get("segment_id"),
                        "title": citation.get("title"),
                        "snippet": citation.get("snippet"),
                    }
                )
                if len(citations) >= 5:
                    return citations
        return citations

    def _build_prompt(self, query: str, citations: list[dict[str, Any]]) -> str:
        source_lines = []
        for index, citation in enumerate(citations, start=1):
            source_lines.append(f"[{index}] {citation.get('title') or 'Источник'}: {citation.get('snippet') or ''}")
        return f"Вопрос: {query}\n\nИсточники:\n" + "\n".join(source_lines)

    def _answer_citation_error(self, answer: str, citations: list[dict[str, Any]]) -> str | None:
        markers = [int(match.group(1)) for match in _CITATION_MARK_RE.finditer(answer)]
        if any(marker < 1 or marker > len(citations) for marker in markers):
            return "UNKNOWN_CITATION"
        if not markers and _CRITICAL_CLAIM_RE.search(answer):
            return "UNCITED_CRITICAL_CLAIM"
        return None

    async def _get_ai_profile(self, task_type: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT *
                    FROM ai_model_profiles
                    WHERE task_type = :task_type
                      AND enabled = true
                    ORDER BY is_default DESC, created_at DESC, profile_id DESC
                    LIMIT 1
                    """
                ),
                {"task_type": task_type},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _get_provider(self, provider_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT *
                    FROM ai_providers
                    WHERE provider_id = :provider_id
                      AND enabled = true
                      AND provider_type = 'openrouter'
                    """
                ),
                {"provider_id": provider_id},
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _ai_task_allowed(self, task_type: str) -> bool:
        row = (
            await self.session.execute(
                text(
                    """
                    SELECT policy_id
                    FROM ai_policy_profiles
                    WHERE enabled = true
                      AND ai_allowed = true
                      AND (:task_type <> 'answer' OR answer_allowed = true)
                      AND (task_type IS NULL OR task_type = :task_type)
                    ORDER BY updated_at DESC, policy_id DESC
                    LIMIT 1
                    """
                ),
                {"task_type": task_type},
            )
        ).first()
        return row is not None

    async def _record_ai_audit(
        self,
        *,
        provider_id: str | None,
        model_profile_id: str | None,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        prompt: str | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        audit_id = str(uuid.uuid4())
        await self.session.execute(
            text(
                """
                INSERT INTO ai_request_audit (
                    audit_id, provider_id, model_profile_id, task_type, status,
                    error_code, error_message_redacted, prompt_redacted,
                    output_redacted, metadata_json, created_at
                )
                VALUES (
                    :audit_id, :provider_id, :model_profile_id, 'answer', :status,
                    :error_code, :error_message, :prompt, :output,
                    CAST(:metadata_json AS jsonb), :created_at
                )
                """
            ),
            {
                "audit_id": audit_id,
                "provider_id": provider_id,
                "model_profile_id": model_profile_id,
                "status": status,
                "error_code": error_code,
                "error_message": error_message,
                "prompt": prompt,
                "output": output,
                "metadata_json": _json(metadata),
                "created_at": _now(),
            },
        )
        return audit_id

    async def _record_observer_event(self, event_type: str, *, actor_role: str, details: dict[str, Any]) -> None:
        await self.session.execute(
            text(
                """
                INSERT INTO agent_runtime_audit (
                    device_id, event_type, severity, source, actor_role,
                    details_json, created_at
                )
                VALUES (
                    'server', :event_type, 'info', 'knowledge_ask',
                    :actor_role, CAST(:details_json AS jsonb), :created_at
                )
                """
            ),
            {
                "event_type": event_type,
                "actor_role": actor_role,
                "details_json": _json(details),
                "created_at": _now(),
            },
        )
