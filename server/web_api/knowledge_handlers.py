from __future__ import annotations

import math

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from access_control.service import can
from app.db import get_session
from app.db.models import KnowledgeContentPack, KnowledgeGapFinding, KnowledgeIngestionJob, KnowledgeNode, KnowledgeReviewTask, KnowledgeSpace
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.knowledge_repo import KnowledgeRepo
from auth.middleware import require_auth
from knowledge.contracts import (
    KNOWLEDGE_RELATION_TYPES,
    KnowledgePublicationBlockedError,
    KnowledgeValidationError,
    actor_visible_visibilities,
    can_mutate_knowledge_visibility,
)
from knowledge.ask_service import KnowledgeAskService
from knowledge.ai_proposal_service import KnowledgeAiProposalService
from knowledge.audience_rules_service import KnowledgeAudienceRulesService
from knowledge.content_pack_service import KnowledgeContentPackService
from knowledge.editor_history_service import KnowledgeEditorHistoryService
from knowledge.embedding_service import KnowledgeEmbeddingService
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.graph_service import KnowledgeGraphService
from knowledge.ingestion_service import KnowledgeIngestionService, KnowledgeRemoteImportBlockedError
from knowledge.metadata_service import KnowledgeMetadataService
from knowledge.metrics_service import KnowledgeMetricsService
from knowledge.ops_summary_service import KnowledgeOpsSummaryService
from knowledge.operations_service import CONTENT_TEMPLATES, KnowledgeOperationsService
from knowledge.portal_service import KnowledgePortalService
from knowledge.retrieval_service import KnowledgeRetrievalService
from knowledge.gap_service import KnowledgeGapService, serialize_gap_finding
from knowledge.review_task_service import KnowledgeReviewTaskService, serialize_review_task
from knowledge.search_service import KnowledgeSearchService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from knowledge.segmentation_service import KnowledgeSegmentationPolicyBlockedError, KnowledgeSegmentationService
from knowledge.suggestion_service import KnowledgeSuggestionService
from registry.effective_identity_service import EffectiveIdentityService

KNOWLEDGE_METADATA_MANAGE_PERMISSION = "knowledge.metadata.manage"


def _actor(request: web.Request) -> tuple[str | None, str]:
    auth = request.get("auth_context") or request.get("auth")
    actor_id = str(getattr(auth, "actor_id", "") or "") or None
    actor_role = str(getattr(auth, "actor_role", "") or "requester")
    if actor_role == "user":
        actor_role = "requester"
    return actor_id, actor_role


def _safe_query_vector(value: object) -> list[float] | None:
    if not isinstance(value, list):
        return None
    vector: list[float] = []
    for item in value[:4096]:
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        vector.append(number)
    return vector or None


def _get_retrieval_transport(request: web.Request):
    return request.app.get("knowledge_ai_openrouter_transport")


def _get_ask_transport(request: web.Request):
    return request.app.get("knowledge_ai_openrouter_transport")


async def _json_payload(request: web.Request) -> dict:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def _permission_denied(permission_code: str) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": f"Недостаточно прав: {permission_code}",
            "error_code": "FORBIDDEN",
            "required_permission": permission_code,
        },
        status=403,
    )


def _admin_success(data: dict[str, object]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


async def _can_manage_knowledge_metadata(session, request: web.Request) -> bool:
    return await can(session, request["auth_context"], KNOWLEDGE_METADATA_MANAGE_PERMISSION)


def _serialize_ingestion_job(row: KnowledgeIngestionJob, space: KnowledgeSpace | None = None, *, include_detail: bool = False) -> dict:
    payload = {
        "job_id": row.job_id,
        "space_id": row.space_id,
        "source_kind": row.source_kind,
        "source_name": row.source_name,
        "source_uri": row.source_uri,
        "source_hash": row.source_hash,
        "status": row.status,
        "created_item_id": row.created_item_id,
        "created_version_id": row.created_version_id,
        "error_message_redacted": row.error_message_redacted,
        "stats_json": row.stats_json or {},
        "metadata_json": row.metadata_json or {},
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
    if include_detail and space is not None:
        payload["space"] = {
            "space_id": space.space_id,
            "code": space.code,
            "title": space.title,
            "visibility": space.visibility,
        }
    return payload


@require_auth("admin", "auditor", "support")
async def handle_web_knowledge_spaces(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if request.method == "POST" and role != "admin":
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    async with get_session() as session:
        repo = KnowledgeRepo(session)
        if request.method == "POST":
            payload = await _json_payload(request)
            space = await repo.upsert_space(payload, actor_id=actor_id)
            await session.commit()
            return web.json_response({"status": "ok", "space": space})
        spaces = await repo.list_spaces(actor_role=role)
        return web.json_response({"status": "ok", "spaces": spaces})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_items(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if request.method == "POST":
        try:
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            async with get_session() as session:
                repo = KnowledgeRepo(session)
                item = await repo.create_item_draft(payload, actor_id=actor_id, actor_role=role)
                bindings = []
                for binding in payload.get("bindings") or []:
                    if isinstance(binding, dict):
                        bindings.append(await repo.add_binding(item["item_id"], binding, actor_id=actor_id, actor_role=role))
                await KnowledgeEditorHistoryService(session).record_draft_created(item, actor_id=actor_id, actor_role=role)
                await session.commit()
            return web.json_response({"status": "ok", "item": item, "bindings": bindings})
        except ValueError as exc:
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    async with get_session() as session:
        items = await KnowledgeRepo(session).list_items(actor_role=role, include_archived=True)
    return web.json_response({"status": "ok", "items": items})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_item_detail(request: web.Request) -> web.Response:
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    _actor_id, role = _actor(request)
    try:
        async with get_session() as session:
            repo = KnowledgeRepo(session)
            item = await repo.get_item(item_id, actor_role=role)
            bindings = await repo.list_bindings(item_id)
        return web.json_response({"status": "ok", "item": item, "bindings": bindings})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_item_versions(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            repo = KnowledgeRepo(session)
            if request.method == "GET":
                versions = await repo.list_versions(item_id, actor_role=role)
                return web.json_response({"status": "ok", "versions": versions})
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            before_versions = await repo.list_versions(item_id, actor_role=role)
            base_version = before_versions[0] if before_versions else None
            version = await repo.create_version(item_id, payload, actor_id=actor_id, actor_role=role)
            await KnowledgeEditorHistoryService(session).record_version_created(
                item_id=version["item_id"],
                version=version,
                base_version=base_version,
                actor_id=actor_id,
                actor_role=role,
                change_summary=payload.get("change_summary"),
            )
            await session.commit()
            return web.json_response({"status": "ok", "version": version})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support")
async def handle_web_knowledge_item_publish(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    payload = await _json_payload(request)
    try:
        async with get_session() as session:
            repo = KnowledgeRepo(session)
            before_item = await repo.get_item(item_id, actor_role=role)
            previous_version_id = before_item.get("current_version_id")
            item = await repo.publish_item(
                item_id,
                payload.get("version_id"),
                actor_id=actor_id,
                actor_role=role,
                acknowledge_stale_passport=bool(payload.get("acknowledge_stale_passport")),
                review_note=payload.get("review_note"),
            )
            await KnowledgeEditorHistoryService(session).record_publish(
                item_id=item["item_id"],
                version_id=payload.get("version_id"),
                previous_version_id=previous_version_id,
                actor_id=actor_id,
                actor_role=role,
                review_note=payload.get("review_note"),
            )
            await session.commit()
        return web.json_response({"status": "ok", "item": item})
    except KnowledgePublicationBlockedError as exc:
        return web.json_response({"status": "error", "error": "publish_blocked", "blockers": exc.blockers}, status=400)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_editor_history(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        limit = int(request.query.get("limit") or "20")
    except ValueError:
        limit = 20
    try:
        async with get_session() as session:
            history = await KnowledgeEditorHistoryService(session).history(item_id, actor_role=role, limit=limit)
        return web.json_response({"status": "ok", **history})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


async def handle_knowledge_suggest(request: web.Request) -> web.Response:
    try:
        actor_id, actor_role = _actor(request)
        payload = await _json_payload(request)
        async with get_session() as session:
            effective_audience = await EffectiveIdentityService(session).resolve_person_audience(
                person_id=None,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            result = await KnowledgeSuggestionService(session).suggest(
                payload,
                actor_role=actor_role,
                effective_audience=effective_audience,
            )
        return web.json_response({"status": "ok", **result})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[knowledge] suggest failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_knowledge_search(request: web.Request) -> web.Response:
    return await _handle_knowledge_search_response(request)


async def handle_knowledge_ask(request: web.Request) -> web.Response:
    return await _handle_knowledge_ask_response(request, force_role="requester")


async def _handle_knowledge_search_response(request: web.Request) -> web.Response:
    try:
        actor_id, actor_role = _actor(request)
        payload = await _json_payload(request)
        async with get_session() as session:
            settings = await KnowledgeSearchSettingsService(session).get_settings()
            configured_limit = int(settings.get("max_results") or 10)
            snippet_length = int(settings.get("snippet_length") or 180)
            requested_limit = int(payload.get("limit") or configured_limit)
            effective_audience = await EffectiveIdentityService(session).resolve_person_audience(
                person_id=None,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            results = await KnowledgeSearchService(session).search(
                query=payload.get("query"),
                actor_role=actor_role,
                service_code=payload.get("service_code"),
                offering_code=payload.get("offering_code"),
                request_template_key=payload.get("request_template_key"),
                surface=str(payload.get("surface") or payload.get("source_surface") or "search"),
                session_id=payload.get("session_id"),
                limit=min(requested_limit, configured_limit),
                snippet_length=snippet_length,
                vector_enabled=bool(settings.get("vector_enabled")),
                query_vector=_safe_query_vector(payload.get("query_vector")),
                vector_weight=float(settings.get("vector_weight") or 1.0),
                effective_audience=effective_audience,
            )
            await session.commit()
        ai_used = bool(settings.get("ai_enabled"))
        return web.json_response(
            {
                "status": "ok",
                "results": results,
                "search_mode": settings.get("search_mode"),
                "effective_mode": settings.get("effective_mode"),
                "ai_used": ai_used,
                "display_message": "Поиск выполнен" if ai_used else "Поиск выполнен без AI",
            }
        )
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_search(request: web.Request) -> web.Response:
    return await _handle_knowledge_search_response(request)


async def _handle_knowledge_ask_response(request: web.Request, *, force_role: str | None = None) -> web.Response:
    try:
        _actor_id, actor_role = _actor(request)
        role = force_role or actor_role
        payload = await _json_payload(request)
        async with get_session() as session:
            result = await KnowledgeAskService(session, transport=_get_ask_transport(request)).ask(
                query=payload.get("query"),
                actor_role=role,
                surface=str(payload.get("surface") or "knowledge_ask"),
                session_id=payload.get("session_id"),
                limit=payload.get("limit"),
                query_vector=_safe_query_vector(payload.get("query_vector")),
            )
            await session.commit()
        return web.json_response({"status": "ok", **result})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры AI-вопроса",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ask(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    return await _handle_knowledge_ask_response(request, force_role=role)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ask_preview(request: web.Request) -> web.Response:
    return await handle_web_knowledge_ask(request)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_retrieve(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            result = await KnowledgeRetrievalService(session, transport=_get_retrieval_transport(request)).retrieve(
                query=payload.get("query"),
                actor_role=role,
                service_code=payload.get("service_code"),
                offering_code=payload.get("offering_code"),
                request_template_key=payload.get("request_template_key"),
                surface=str(payload.get("surface") or "admin_knowledge_retrieve"),
                session_id=payload.get("session_id"),
                limit=payload.get("limit"),
                query_vector=_safe_query_vector(payload.get("query_vector")),
            )
            await session.commit()
        return web.json_response({"status": "ok", **result, "display_message": "Retrieval выполнен"})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры retrieval",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_search_preview(request: web.Request) -> web.Response:
    return await handle_web_knowledge_retrieve(request)


def _search_settings_forbidden() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "forbidden",
            "error_code": "FORBIDDEN",
            "display_message": "Недостаточно прав для настройки поиска",
        },
        status=403,
    )


def _segmentation_forbidden() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "forbidden",
            "error_code": "FORBIDDEN",
            "display_message": "Недостаточно прав для разметки знаний",
        },
        status=403,
    )


def _indexing_forbidden() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "forbidden",
            "error_code": "FORBIDDEN",
            "display_message": "Недостаточно прав для индексации знаний",
        },
        status=403,
    )


def _get_embedding_transport(request: web.Request):
    return request.app.get("knowledge_embedding_openrouter_transport")


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_search_settings(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if request.method == "POST" and role != "admin":
        return _search_settings_forbidden()
    try:
        async with get_session() as session:
            service = KnowledgeSearchSettingsService(session)
            if request.method == "POST":
                settings = await service.upsert_settings(await _json_payload(request), actor_id=actor_id)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "settings": settings,
                        "display_message": "Настройки поиска сохранены",
                    }
                )
            settings = await service.get_settings()
            return web.json_response(
                {
                    "status": "ok",
                    "settings": settings,
                    "display_message": "Настройки поиска загружены",
                }
            )
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры поиска",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] search settings failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor", "user")
async def handle_web_knowledge_item_segments(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    if request.method == "POST" and role not in {"admin", "support"}:
        return _segmentation_forbidden()
    try:
        async with get_session() as session:
            service = KnowledgeSegmentationService(session)
            if request.method == "POST":
                segment = await service.create_segment(
                    item_id,
                    await _json_payload(request),
                    actor_id=actor_id,
                    actor_role=role,
                )
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "segment": segment,
                        "display_message": "Сегмент знаний сохранён",
                    }
                )
            segments = await service.list_segments(item_id, actor_role=role)
            return web.json_response({"status": "ok", "segments": segments})
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры сегмента",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] segment handler failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor", "user")
async def handle_web_knowledge_item_segments_auto(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeSegmentationService(session).auto_segment(
                item_id,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                **result,
                "display_message": "Авторазметка выполнена без AI",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры авторазметки",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] auto segmentation failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor", "user")
async def handle_web_knowledge_item_segments_revalidate(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeSegmentationService(session).revalidate_segments(
                item_id,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                **result,
                "display_message": "Сегменты перепроверены",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры перепроверки",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] segment revalidation failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor", "user")
async def handle_web_knowledge_item_segments_ai_proposals(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            try:
                result = await KnowledgeSegmentationService(session).propose_ai_segments(
                    item_id,
                    await _json_payload(request),
                    actor_id=actor_id,
                    actor_role=role,
                )
            except KnowledgeSegmentationPolicyBlockedError as exc:
                await session.commit()
                return web.json_response(
                    {
                        "status": "error",
                        "error": "policy_blocked",
                        "error_code": exc.error_code,
                        "display_message": "Политика AI не разрешает авторазметку",
                        "details": str(exc),
                    },
                    status=409,
                )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                **result,
                "display_message": "AI-предложения сегментов созданы",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры AI-предложений",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] AI segment proposals failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor", "user")
async def handle_web_knowledge_item_segments_index_sync(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeSegmentationService(session).sync_segment_index(
                item_id,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                **result,
                "display_message": "Индекс сегментов синхронизирован",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры синхронизации",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] segment index sync failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_indexing_status(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    if role not in {"admin", "support", "auditor"}:
        return _indexing_forbidden()
    async with get_session() as session:
        status = await KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request)).status()
    return web.json_response({"status": "ok", "indexing": status, "display_message": "Статус индексации загружен"})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_indexing_jobs(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if request.method == "POST" and role not in {"admin", "support"}:
        return _indexing_forbidden()
    async with get_session() as session:
        service = KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request))
        if request.method == "POST":
            payload = await _json_payload(request)
            scope_type = str(payload.get("scope_type") or "item")
            if scope_type == "item":
                result = await service.reindex_item(
                    str(payload.get("scope_ref") or payload.get("item_id") or ""),
                    payload,
                    actor_id=actor_id,
                    actor_role=role,
                )
            elif scope_type == "segment":
                result = await service.reindex_segment(
                    str(payload.get("scope_ref") or payload.get("segment_id") or ""),
                    payload,
                    actor_id=actor_id,
                    actor_role=role,
                )
            elif scope_type == "space":
                result = await service.reindex_space(
                    str(payload.get("scope_ref") or payload.get("space_id") or payload.get("space_code") or ""),
                    payload,
                    actor_id=actor_id,
                    actor_role=role,
                )
            elif scope_type == "all":
                result = await service.reindex_all(payload, actor_id=actor_id, actor_role=role)
            else:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "validation_error",
                        "error_code": "UNSUPPORTED_SCOPE",
                        "display_message": "Проверьте scope индексации",
                    },
                    status=400,
                )
            await session.commit()
            return web.json_response({"status": "ok", **result, "display_message": "Задание индексации выполнено"})
        jobs = await service.list_jobs()
    return web.json_response({"status": "ok", "jobs": jobs, "display_message": "Задания индексации загружены"})


@require_auth("admin", "support")
async def handle_web_knowledge_indexing_reindex_item(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _indexing_forbidden()
    payload = await _json_payload(request)
    item_id = str(payload.get("item_id") or payload.get("item_id_or_slug") or payload.get("slug") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request)).reindex_item(
                item_id,
                payload,
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        message = "Индексация embeddings выполнена" if result["job"]["status"] == "completed" else "Индексация embeddings завершилась ошибкой"
        return web.json_response({"status": "ok", **result, "display_message": message})
    except PermissionError:
        return _indexing_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры индексации",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] embedding reindex failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support")
async def handle_web_knowledge_indexing_reindex_segment(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _indexing_forbidden()
    payload = await _json_payload(request)
    segment_id = str(payload.get("segment_id") or payload.get("scope_ref") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request)).reindex_segment(
                segment_id,
                payload,
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response({"status": "ok", **result, "display_message": "Индексация сегмента выполнена"})
    except PermissionError:
        return _indexing_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры индексации сегмента",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support")
async def handle_web_knowledge_indexing_reindex_space(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _indexing_forbidden()
    payload = await _json_payload(request)
    space_ref = str(payload.get("space_id") or payload.get("space_code") or payload.get("scope_ref") or "")
    try:
        async with get_session() as session:
            result = await KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request)).reindex_space(
                space_ref,
                payload,
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response({"status": "ok", **result, "display_message": "Индексация пространства выполнена"})
    except PermissionError:
        return _indexing_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры индексации пространства",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support")
async def handle_web_knowledge_indexing_reindex_all(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _indexing_forbidden()
    payload = await _json_payload(request)
    async with get_session() as session:
        result = await KnowledgeEmbeddingService(session, transport=_get_embedding_transport(request)).reindex_all(
            payload,
            actor_id=actor_id,
            actor_role=role,
        )
        await session.commit()
    return web.json_response({"status": "ok", **result, "display_message": "Полная индексация выполнена"})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_segment_detail(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    segment_id = str(request.match_info.get("segment_id") or "")
    try:
        async with get_session() as session:
            service = KnowledgeSegmentationService(session)
            if request.method == "DELETE":
                segment = await service.archive_segment(segment_id, actor_id=actor_id, actor_role=role)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "segment": segment,
                        "display_message": "Сегмент знаний архивирован",
                    }
                )
            segment = await service.update_segment(
                segment_id,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "ok",
                    "segment": segment,
                    "display_message": "Сегмент знаний обновлён",
                }
            )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры сегмента",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] segment detail failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_segment_approve(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    segment_id = str(request.match_info.get("segment_id") or "")
    try:
        async with get_session() as session:
            segment = await KnowledgeSegmentationService(session).approve_ai_segment(
                segment_id,
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "segment": segment,
                "display_message": "AI-предложение сегмента одобрено",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте AI-предложение сегмента",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_segment_reject(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return _segmentation_forbidden()
    segment_id = str(request.match_info.get("segment_id") or "")
    try:
        async with get_session() as session:
            segment = await KnowledgeSegmentationService(session).reject_ai_segment(
                segment_id,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "segment": segment,
                "display_message": "AI-предложение сегмента отклонено",
            }
        )
    except PermissionError:
        return _segmentation_forbidden()
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте AI-предложение сегмента",
                "details": str(exc),
            },
            status=400,
        )


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_segmentation_profiles(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if request.method == "POST" and role != "admin":
        return _segmentation_forbidden()
    try:
        async with get_session() as session:
            service = KnowledgeSegmentationService(session)
            if request.method == "POST":
                profile = await service.upsert_profile(await _json_payload(request), actor_id=actor_id)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "profile": profile,
                        "display_message": "Профиль разметки сохранён",
                    }
                )
            profiles = await service.list_profiles()
        return web.json_response({"status": "ok", "profiles": profiles})
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "validation_error",
                "error_code": "VALIDATION_ERROR",
                "display_message": "Проверьте параметры профиля разметки",
                "details": str(exc),
            },
            status=400,
        )
    except Exception:
        logger.exception("[knowledge] segmentation profiles failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_knowledge_feedback(request: web.Request) -> web.Response:
    actor_id, actor_role = _actor(request)
    payload = await _json_payload(request)
    async with get_session() as session:
        event = await KnowledgeFeedbackService(session).record_event(payload, actor_role=actor_role, actor_id=actor_id)
        if event.get("source_surface") == "support_workspace":
            observer_event_type = None
            severity = "info"
            if event.get("event_type") == "support_used":
                observer_event_type = "knowledge.support.article_used"
            elif event.get("event_type") == "not_helpful" and event.get("result") == "weak_article_reported":
                observer_event_type = "knowledge.support.weak_article_reported"
                severity = "warning"
            if observer_event_type:
                await AgentRuntimeAuditRepo(session).add(
                    device_id="server",
                    event_type=observer_event_type,
                    severity=severity,
                    source="knowledge_support",
                    ticket_id=event.get("ticket_id"),
                    actor_id=actor_id,
                    actor_role=actor_role,
                    details_json={
                        "event_id": event.get("event_id"),
                        "item_id": event.get("item_id"),
                        "version_id": event.get("version_id"),
                        "ticket_id": event.get("ticket_id"),
                        "result": event.get("result"),
                        "source_surface": "support_workspace",
                    },
                )
        await session.commit()
    return web.json_response({"status": "ok", "event": event})


async def handle_knowledge_portal_home(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            payload = await KnowledgePortalService(session).home(actor_role="requester")
        return web.json_response({"status": "ok", **payload})
    except Exception:
        logger.exception("[knowledge] portal home failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_knowledge_article_detail(request: web.Request) -> web.Response:
    slug = str(request.match_info.get("slug") or "").strip()
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            service = KnowledgePortalService(session)
            effective_audience = await EffectiveIdentityService(session).resolve_person_audience(
                person_id=None,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            payload = await service.article_detail(
                slug,
                actor_role="requester",
                effective_audience=effective_audience,
            )
            await service.record_article_view(
                payload["article"],
                payload["version"],
                actor_id=actor_id,
                actor_role="requester",
                session_id=request.query.get("session_id"),
            )
            await session.commit()
        return web.json_response({"status": "ok", **payload})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)
    except Exception:
        logger.exception("[knowledge] article detail failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def _portal_article_event_context(session, slug: str) -> tuple[dict, dict]:
    payload = await KnowledgePortalService(session).article_detail(slug, actor_role="requester")
    return payload["article"], payload["version"]


async def handle_knowledge_article_feedback(request: web.Request) -> web.Response:
    slug = str(request.match_info.get("slug") or "").strip()
    actor_id, _actor_role = _actor(request)
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            article, version = await _portal_article_event_context(session, slug)
            event = await KnowledgeFeedbackService(session).record_event(
                {
                    "item_id": article.get("item_id"),
                    "version_id": version.get("version_id"),
                    "event_type": "helpful" if bool(payload.get("helpful")) else "not_helpful",
                    "session_id": payload.get("session_id"),
                    "surface": "requester_portal",
                    "result": payload.get("result"),
                    "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
                },
                actor_role="requester",
                actor_id=actor_id,
            )
            await session.commit()
        return web.json_response({"status": "ok", "event": event})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


async def handle_knowledge_article_correction_request(request: web.Request) -> web.Response:
    slug = str(request.match_info.get("slug") or "").strip()
    actor_id, _actor_role = _actor(request)
    try:
        payload = await _json_payload(request)
        comment = str(payload.get("comment") or "").strip()[:2000]
        async with get_session() as session:
            article, version = await _portal_article_event_context(session, slug)
            event = await KnowledgeFeedbackService(session).record_event(
                {
                    "item_id": article.get("item_id"),
                    "version_id": version.get("version_id"),
                    "event_type": "not_helpful",
                    "result": "correction_requested",
                    "session_id": payload.get("session_id"),
                    "surface": "requester_portal",
                    "metadata": {
                        "comment": comment,
                        "source": "article_correction_request",
                    },
                },
                actor_role="requester",
                actor_id=actor_id,
            )
            await KnowledgePortalService(session).record_correction_request(
                article,
                version,
                comment=comment,
                feedback_event_id=event.get("event_id"),
                actor_id=actor_id,
                actor_role="requester",
                session_id=payload.get("session_id"),
            )
            await session.commit()
        return web.json_response({"status": "ok", "event": event})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


async def handle_knowledge_article_bookmark(request: web.Request) -> web.Response:
    slug = str(request.match_info.get("slug") or "").strip()
    actor_id, _actor_role = _actor(request)
    try:
        payload = await _json_payload(request) if request.method != "DELETE" else {}
        bookmarked = request.method != "DELETE"
        async with get_session() as session:
            article, version = await _portal_article_event_context(session, slug)
            event = await KnowledgeFeedbackService(session).record_event(
                {
                    "item_id": article.get("item_id"),
                    "version_id": version.get("version_id"),
                    "event_type": "viewed",
                    "result": "bookmarked" if bookmarked else "bookmark_removed",
                    "session_id": payload.get("session_id"),
                    "surface": "requester_portal",
                    "metadata": {"source": "article_bookmark"},
                },
                actor_role="requester",
                actor_id=actor_id,
            )
            await KnowledgePortalService(session).set_bookmark(
                article,
                version,
                bookmarked=bookmarked,
                actor_id=actor_id,
                actor_role="requester",
                session_id=payload.get("session_id"),
            )
            await session.commit()
        return web.json_response({"status": "ok", "bookmark": {"slug": slug, "bookmarked": bookmarked}, "event": event})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


async def handle_knowledge_portal_space(request: web.Request) -> web.Response:
    code = str(request.match_info.get("space_code") or "").strip()
    try:
        async with get_session() as session:
            payload = await KnowledgePortalService(session).collection(
                collection_type="space",
                code=code,
                actor_role="requester",
            )
        return web.json_response({"status": "ok", **payload})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


async def handle_knowledge_portal_tag(request: web.Request) -> web.Response:
    tag = str(request.match_info.get("tag") or "").strip()
    try:
        async with get_session() as session:
            payload = await KnowledgePortalService(session).collection(
                collection_type="tag",
                code=tag,
                actor_role="requester",
            )
        return web.json_response({"status": "ok", **payload})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "not_found", "details": str(exc)}, status=404)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_metrics_summary(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        summary = await KnowledgeMetricsService(session).summary(actor_role=role)
    return web.json_response({"status": "ok", "summary": summary})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ai_proposals(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    async with get_session() as session:
        service = KnowledgeAiProposalService(session)
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            try:
                proposal = await service.create(await _json_payload(request), actor_id=actor_id, actor_role=role)
            except ValueError as exc:
                return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
            await session.commit()
            return web.json_response({"status": "ok", "proposal": proposal})
        try:
            proposals = await service.list(
                actor_role=role,
                status=request.query.get("status"),
                target_kind=request.query.get("target_kind"),
                limit=int(request.query.get("limit") or 100),
            )
        except ValueError as exc:
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    return web.json_response({"status": "ok", "proposals": proposals})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ai_proposal_review(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    proposal_id = str(request.match_info.get("proposal_id") or "")
    async with get_session() as session:
        service = KnowledgeAiProposalService(session)
        try:
            proposal = await service.review(proposal_id, await _json_payload(request), actor_id=actor_id, actor_role=role)
        except ValueError as exc:
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
        if proposal is None:
            return web.json_response({"status": "error", "error": "not_found"}, status=404)
        await session.commit()
    return web.json_response({"status": "ok", "proposal": proposal})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ops_summary(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        summary = await KnowledgeOpsSummaryService(session).summary(actor_role=role)
    return web.json_response({"status": "ok", "summary": summary})


@require_auth("admin")
async def handle_web_admin_knowledge_audience_rules(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        service = KnowledgeAudienceRulesService(session)
        if request.method == "GET":
            include_archived = str(request.query.get("include_archived") or "").strip().lower() in {"1", "true", "yes"}
            try:
                rules = await service.list_rules(
                    subject_type=request.query.get("subject_type"),
                    subject_id=request.query.get("subject_id"),
                    include_archived=include_archived,
                )
            except ValueError as exc:
                return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
            return _admin_success({"rules": rules})
        try:
            payload = await _json_payload(request)
            rules = await service.replace_subject_rules(
                subject_type=str(payload.get("subject_type") or ""),
                subject_id=str(payload.get("subject_id") or ""),
                rules=payload.get("rules") or [],
                actor_id=auth_context.actor_id,
                reason=str(payload.get("reason") or "").strip() or None,
            )
            await session.commit()
            return _admin_success({"rules": rules})
        except ValueError as exc:
            await session.rollback()
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin")
async def handle_web_admin_knowledge_audience_rules_preview(request: web.Request) -> web.Response:
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            preview = await KnowledgeAudienceRulesService(session).preview_subject_access(
                subject_type=str(payload.get("subject_type") or ""),
                subject_id=str(payload.get("subject_id") or ""),
                actor_id=str(payload.get("actor_id") or "").strip() or None,
                actor_role=str(payload.get("actor_role") or "user"),
                rules=payload.get("rules") if isinstance(payload.get("rules"), list) else None,
                service_context=payload.get("service_context") if isinstance(payload.get("service_context"), dict) else None,
            )
        return _admin_success({"preview": preview})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin")
async def handle_web_admin_knowledge_access_explain(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            explain = await KnowledgeAudienceRulesService(session).explain_item_access(
                item_id=str(request.query.get("item_id") or ""),
                actor_id=str(request.query.get("actor_id") or "").strip() or None,
                actor_role=str(request.query.get("actor_role") or "user"),
                service_context={
                    "service_code": request.query.get("service_code"),
                    "offering_code": request.query.get("offering_code"),
                    "request_template_key": request.query.get("request_template_key"),
                },
            )
        return _admin_success({"explain": explain})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_content_packs(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    if role != "admin":
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    async with get_session() as session:
        rows = (
            await session.execute(
                select(KnowledgeContentPack).order_by(KnowledgeContentPack.installed_at.desc(), KnowledgeContentPack.code.asc())
            )
        ).scalars().all()
        return web.json_response(
            {
                "status": "ok",
                "packs": [
                    {
                        "pack_id": row.pack_id,
                        "code": row.code,
                        "title": row.title,
                        "version": row.version,
                        "description": row.description,
                        "installed_at": row.installed_at.isoformat() if row.installed_at else None,
                        "installed_by": row.installed_by,
                        "source_hash": row.source_hash,
                        "status": row.status,
                        "metadata": row.metadata_json or {},
                    }
                    for row in rows
                ],
            }
        )


@require_auth("admin")
async def handle_web_knowledge_content_pack_apply(request: web.Request) -> web.Response:
    actor_id, _role = _actor(request)
    payload = await _json_payload(request)
    pack = payload.get("pack")
    if not isinstance(pack, dict):
        return web.json_response({"status": "error", "error": "validation_error", "details": "pack is required"}, status=400)
    try:
        async with get_session() as session:
            result = await KnowledgeContentPackService(session).apply_pack(
                pack,
                actor_id=actor_id,
                dry_run=bool(payload.get("dry_run")),
                force=bool(payload.get("force")),
            )
            if not payload.get("dry_run"):
                await session.commit()
        return web.json_response({"status": "ok", "result": result})
    except Exception as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin")
async def handle_web_knowledge_content_pack_retire(request: web.Request) -> web.Response:
    actor_id, _role = _actor(request)
    code = str(request.match_info.get("pack_code") or "")
    async with get_session() as session:
        result = await KnowledgeContentPackService(session).retire_pack(code, actor_id=actor_id)
        await session.commit()
    return web.json_response({"status": "ok", "result": result})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_templates(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "templates": list(CONTENT_TEMPLATES)})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_review_queue(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        review_queue = await KnowledgeOperationsService(session).review_queue(actor_role=role)
    return web.json_response({"status": "ok", "review_queue": review_queue})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_review_tasks(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    async with get_session() as session:
        service = KnowledgeReviewTaskService(session)
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            result = await service.generate_tasks(actor_id=actor_id)
            await session.commit()
            return web.json_response({"status": "ok", **result})
        result = await service.list_tasks(actor_role=role, actor_id=actor_id, status=request.query.get("status"))
    return web.json_response({"status": "ok", **result})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_review_task_detail(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    task_id = str(request.match_info.get("task_id") or "")
    async with get_session() as session:
        row = (await session.execute(select(KnowledgeReviewTask).where(KnowledgeReviewTask.task_id == task_id))).scalar_one_or_none()
        if row is None:
            return web.json_response({"status": "error", "error": "not_found"}, status=404)
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            action = str(request.match_info.get("action") or payload.get("action") or "")
            service = KnowledgeReviewTaskService(session)
            if action == "assign":
                result = await service.assign_task(task_id, actor_id=actor_id, assigned_to_actor_id=payload.get("assigned_to_actor_id") or actor_id)
            elif action == "start":
                result = await service.start_task(task_id, actor_id=actor_id)
            elif action == "complete":
                result = await service.complete_task(task_id, actor_id=actor_id, note=payload.get("note"))
            elif action == "dismiss":
                result = await service.dismiss_task(task_id, actor_id=actor_id, reason=payload.get("reason") or payload.get("note"))
            else:
                return web.json_response({"status": "error", "error": "validation_error", "details": "unsupported action"}, status=400)
            await session.commit()
            return web.json_response({"status": "ok", **result})
        return web.json_response({"status": "ok", "task": serialize_review_task(row)})


@require_auth("admin", "support")
async def handle_web_knowledge_review_action(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    payload = await _json_payload(request)
    try:
        async with get_session() as session:
            action = str(payload.get("action") or "")
            result = await KnowledgeOperationsService(session).review_action(
                item_id,
                action=action,
                actor_id=actor_id,
                note=payload.get("note"),
            )
            await KnowledgeEditorHistoryService(session).record_review_action(
                item_id=result["item"]["item_id"],
                action=action,
                actor_id=actor_id,
                actor_role=role,
                note=payload.get("note"),
            )
            await session.commit()
        return web.json_response({"status": "ok", "result": result})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_quality(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        quality = await KnowledgeOperationsService(session).quality_summary(actor_role=role)
    return web.json_response({"status": "ok", "quality": quality})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_metadata(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        metadata = await KnowledgeMetadataService(session).bundle(actor_role=role)
    return web.json_response({"status": "ok", "metadata": metadata})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_taxonomy(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            if not await _can_manage_knowledge_metadata(session, request):
                return _permission_denied(KNOWLEDGE_METADATA_MANAGE_PERMISSION)
            term = await KnowledgeMetadataService(session).upsert_taxonomy_term(payload, actor_id=actor_id, actor_role=role)
            await session.commit()
        return web.json_response({"status": "ok", "term": term})
    except (KnowledgeValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_properties(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            if not await _can_manage_knowledge_metadata(session, request):
                return _permission_denied(KNOWLEDGE_METADATA_MANAGE_PERMISSION)
            property_definition = await KnowledgeMetadataService(session).upsert_property_definition(payload, actor_id=actor_id, actor_role=role)
            await session.commit()
        return web.json_response({"status": "ok", "property": property_definition})
    except (KnowledgeValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_item_metadata(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_ref = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            service = KnowledgeMetadataService(session)
            if request.method == "GET":
                item_metadata = await service.item_metadata(item_ref, actor_role=role)
                return web.json_response({"status": "ok", "item_metadata": item_metadata})
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            if not await _can_manage_knowledge_metadata(session, request):
                return _permission_denied(KNOWLEDGE_METADATA_MANAGE_PERMISSION)
            item_metadata = await service.update_item_metadata(
                item_ref,
                await _json_payload(request),
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
            return web.json_response({"status": "ok", "item_metadata": item_metadata})
    except (KnowledgeValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_item_applicability(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    item_ref = str(request.match_info.get("item_id_or_slug") or "")
    try:
        async with get_session() as session:
            service = KnowledgeMetadataService(session)
            if request.method == "GET":
                rules = await service.item_applicability_rules(item_ref, actor_role=role)
                return web.json_response({"status": "ok", "rules": rules})
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            if not await _can_manage_knowledge_metadata(session, request):
                return _permission_denied(KNOWLEDGE_METADATA_MANAGE_PERMISSION)
            payload = await _json_payload(request)
            rules_payload = payload.get("rules")
            if not isinstance(rules_payload, list):
                raise KnowledgeValidationError("rules must be a list")
            rules = await service.replace_applicability_rules(
                item_ref,
                [entry for entry in rules_payload if isinstance(entry, dict)],
                actor_id=actor_id,
                actor_role=role,
            )
            await session.commit()
            return web.json_response({"status": "ok", "rules": rules})
    except (KnowledgeValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_quality_models(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support"}:
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    try:
        payload = await _json_payload(request)
        async with get_session() as session:
            if not await _can_manage_knowledge_metadata(session, request):
                return _permission_denied(KNOWLEDGE_METADATA_MANAGE_PERMISSION)
            quality_model = await KnowledgeMetadataService(session).upsert_quality_model(payload, actor_id=actor_id, actor_role=role)
            await session.commit()
        return web.json_response({"status": "ok", "quality_model": quality_model})
    except (KnowledgeValidationError, ValueError) as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_gaps(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        gaps = await KnowledgeOperationsService(session).detect_gaps(actor_role=role)
    return web.json_response({"status": "ok", "gaps": gaps})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_gap_findings(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    async with get_session() as session:
        service = KnowledgeGapService(session)
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            result = await service.recompute(actor_id=actor_id)
            await session.commit()
            return web.json_response({"status": "ok", **result})
        rows = (await session.execute(select(KnowledgeGapFinding).order_by(KnowledgeGapFinding.updated_at.desc()))).scalars().all()
        findings = [serialize_gap_finding(row) for row in rows]
    return web.json_response({"status": "ok", "findings": findings, "count": len(findings)})


@require_auth("admin", "support")
async def handle_web_knowledge_gap_action(request: web.Request) -> web.Response:
    actor_id, _role = _actor(request)
    finding_id = str(request.match_info.get("finding_id") or "")
    action = str(request.match_info.get("action") or "")
    payload = await _json_payload(request)
    async with get_session() as session:
        service = KnowledgeGapService(session)
        if action == "dismiss":
            result = {"finding": await service.dismiss(finding_id, actor_id=actor_id, reason=payload.get("reason"))}
        elif action == "accept":
            row = (await session.execute(select(KnowledgeGapFinding).where(KnowledgeGapFinding.finding_id == finding_id))).scalar_one_or_none()
            if row is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            row.status = "accepted"
            result = {"finding": serialize_gap_finding(row)}
        elif action == "create-draft":
            result = await service.create_draft(finding_id, actor_id=actor_id, item_type=str(payload.get("item_type") or "article"))
        else:
            return web.json_response({"status": "error", "error": "validation_error", "details": "unsupported action"}, status=400)
        await session.commit()
    return web.json_response({"status": "ok", **result})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_rollout_policies(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    async with get_session() as session:
        ops = KnowledgeOperationsService(session)
        if request.method == "POST":
            if role != "admin":
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            result = await ops.upsert_rollout_policy(await _json_payload(request), actor_id=actor_id)
            await session.commit()
            return web.json_response({"status": "ok", "policy": result})
        result = await ops.list_rollout_policies()
    return web.json_response({"status": "ok", **result})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_rollout_effective_preview(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    payload = await _json_payload(request)
    async with get_session() as session:
        decision = await KnowledgeOperationsService(session).rollout_decision(payload, actor_role=role)
    return web.json_response({"status": "ok", "decision": decision})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_graph_nodes(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    node_ref = str(request.match_info.get("node_id") or "")
    async with get_session() as session:
        graph = KnowledgeGraphService(session)
        if node_ref and request.method == "GET":
            node = await graph.get_node(node_ref, actor_role=role)
            if node is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            return web.json_response({"status": "ok", "node": graph.serialize_node(node)})
        if node_ref and request.method == "PATCH":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            visibility = payload.get("visibility")
            if visibility is not None and not can_mutate_knowledge_visibility(role, str(visibility)):
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            try:
                node = await graph.update_node(node_ref, payload, actor_role=role, actor_id=actor_id)
            except ValueError as exc:
                return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
            if node is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            await session.commit()
            return web.json_response({"status": "ok", "node": node})
        if node_ref and request.method == "DELETE":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            node = await graph.archive_node(node_ref, actor_role=role, actor_id=actor_id)
            if node is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            await session.commit()
            return web.json_response({"status": "ok", "node": node, "display_message": "Узел графа архивирован"})
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            visibility = str(payload.get("visibility") or "support_internal")
            if not can_mutate_knowledge_visibility(role, visibility):
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            try:
                node = await graph.upsert_node(
                    stable_key=str(payload.get("stable_key") or ""),
                    node_type=str(payload.get("node_type") or "concept"),
                    label=str(payload.get("label") or payload.get("stable_key") or ""),
                    visibility=visibility,
                    linked_item_id=payload.get("linked_item_id"),
                    service_code=payload.get("service_code"),
                    offering_code=payload.get("offering_code"),
                    actor_id=actor_id,
                )
                if payload.get("description") is not None:
                    await graph.update_node(node.stable_key, {"description": payload.get("description")}, actor_role=role, actor_id=actor_id)
            except ValueError as exc:
                return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
            await session.commit()
            saved = await graph.get_node(node.stable_key, actor_role=role)
            return web.json_response({"status": "ok", "node": graph.serialize_node(saved) if saved else {"node_id": node.node_id, "stable_key": node.stable_key, "label": node.label}})
        nodes = await graph.list_nodes(actor_role=role, q=request.query.get("q"), limit=int(request.query.get("limit") or 100))
        return web.json_response({"status": "ok", "nodes": nodes})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_graph_search(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    query = str(request.query.get("q") or request.query.get("query") or "")
    limit = int(request.query.get("limit") or 50)
    async with get_session() as session:
        result = await KnowledgeGraphService(session).search(query=query, actor_role=role, limit=limit)
    return web.json_response({"status": "ok", **result})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_graph_neighborhood(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    node_ref = str(request.match_info.get("node_id") or "")
    depth = int(request.query.get("depth") or 1)
    async with get_session() as session:
        node = (
            await session.execute(
                select(KnowledgeNode).where((KnowledgeNode.node_id == node_ref) | (KnowledgeNode.stable_key == node_ref))
            )
        ).scalar_one_or_none()
        if node is None:
            return web.json_response({"status": "ok", "nodes": [], "edges": []})
        graph = await KnowledgeGraphService(session).neighborhood(stable_key=node.stable_key, actor_role=role, depth=depth)
    return web.json_response({"status": "ok", **graph})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_graph_layouts(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    scope_ref = str(request.match_info.get("scope") or "default").strip() or "default"
    if len(scope_ref) > 240:
        return web.json_response({"status": "error", "error": "validation_error", "details": "scope is too long"}, status=400)
    async with get_session() as session:
        graph = KnowledgeGraphService(session)
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            scope_type = str(payload.get("scope_type") or "graph")
            if scope_type not in {"graph", "space", "item"}:
                return web.json_response({"status": "error", "error": "validation_error", "details": "unsupported scope_type"}, status=400)
            layout = await graph.save_layout(
                scope_ref=scope_ref,
                scope_type=scope_type,
                layout_json=payload.get("layout_json") or {},
                actor_id=actor_id,
            )
            await session.commit()
            return web.json_response({"status": "ok", "layout": layout})
        layout = await graph.get_layout(scope_ref=scope_ref)
    return web.json_response({"status": "ok", "layout": layout})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_graph_edges(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    edge_id = str(request.match_info.get("edge_id") or "")
    async with get_session() as session:
        graph = KnowledgeGraphService(session)
        if request.method == "GET" and edge_id:
            edge = await graph.get_edge(edge_id, actor_role=role)
            if edge is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            return web.json_response({"status": "ok", "edge": graph.serialize_edge(edge)})
        if request.method == "GET":
            edges = await graph.list_edges(actor_role=role, q=request.query.get("q"), limit=int(request.query.get("limit") or 100))
            return web.json_response({"status": "ok", "edges": edges})
        if role not in {"admin", "support"}:
            return web.json_response({"status": "error", "error": "forbidden"}, status=403)
        if request.method == "PATCH" and edge_id:
            payload = await _json_payload(request)
            visibility = payload.get("visibility")
            if visibility is not None and not can_mutate_knowledge_visibility(role, str(visibility)):
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            try:
                edge = await graph.update_edge(edge_id, payload, actor_role=role, actor_id=actor_id)
            except ValueError as exc:
                return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
            if edge is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            await session.commit()
            return web.json_response({"status": "ok", "edge": edge})
        if request.method == "DELETE" and edge_id:
            edge = await graph.archive_edge(edge_id, actor_role=role, actor_id=actor_id)
            if edge is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            await session.commit()
            return web.json_response({"status": "ok", "edge": edge, "display_message": "Связь графа архивирована"})
        payload = await _json_payload(request)
        source = (
            await session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == str(payload.get("source_stable_key") or "")))
        ).scalar_one_or_none()
        target = (
            await session.execute(select(KnowledgeNode).where(KnowledgeNode.stable_key == str(payload.get("target_stable_key") or "")))
        ).scalar_one_or_none()
        if source is None or target is None:
            return web.json_response({"status": "error", "error": "validation_error", "details": "source and target nodes are required"}, status=400)
        visibility = str(payload.get("visibility") or source.visibility)
        if not can_mutate_knowledge_visibility(role, visibility):
            return web.json_response({"status": "error", "error": "forbidden"}, status=403)
        relation_type = str(payload.get("relation_type") or "mentions")
        if relation_type not in KNOWLEDGE_RELATION_TYPES:
            return web.json_response(
                {"status": "error", "error": "validation_error", "details": "unsupported relation_type"},
                status=400,
            )
        edge = await graph.create_edge(
            source,
            target,
            relation_type=relation_type,
            visibility=visibility,
            actor_id=actor_id,
        )
        await session.commit()
    return web.json_response({"status": "ok", "edge": graph.serialize_edge(edge)})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ingestion_jobs(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    job_id = request.match_info.get("job_id")
    async with get_session() as session:
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            result = await KnowledgeIngestionService(session).ingest_text(payload, actor_id=actor_id, actor_role=role)
            await session.commit()
            return web.json_response({"status": "ok", **result})
        allowed = set(actor_visible_visibilities(role))
        if job_id:
            row = (
                await session.execute(
                    select(KnowledgeIngestionJob, KnowledgeSpace)
                    .join(KnowledgeSpace, KnowledgeIngestionJob.space_id == KnowledgeSpace.space_id)
                    .where(KnowledgeIngestionJob.job_id == job_id, KnowledgeSpace.visibility.in_(allowed))
                )
            ).first()
            if row is None:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            job, space = row
            return web.json_response({"status": "ok", "job": _serialize_ingestion_job(job, space, include_detail=True)})
        rows = (
            await session.execute(
                select(KnowledgeIngestionJob, KnowledgeSpace)
                .join(KnowledgeSpace, KnowledgeIngestionJob.space_id == KnowledgeSpace.space_id)
                .where(KnowledgeSpace.visibility.in_(allowed))
                .order_by(KnowledgeIngestionJob.created_at.desc())
                .limit(100)
            )
        ).all()
        return web.json_response(
            {
                "status": "ok",
                "jobs": [_serialize_ingestion_job(row, space) for row, space in rows],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_import_preview(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    if role not in {"admin", "support", "auditor"}:
        return web.json_response({"status": "error", "error": "forbidden"}, status=403)
    payload = await _json_payload(request)
    async with get_session() as session:
        service = KnowledgeIngestionService(session)
        try:
            preview = service.preview_import(payload)
        except KnowledgeRemoteImportBlockedError:
            await service.record_observer_event(
                "knowledge.import.failed",
                severity="warning",
                actor_id=actor_id,
                actor_role=role,
                details={"stage": "preview", "source_kind": str(payload.get("source_kind") or "text"), "reason": "remote_import_blocked"},
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "error",
                    "error": "remote_import_blocked",
                    "display_message": "Импорт из внешнего источника заблокирован политикой безопасной загрузки",
                },
                status=400,
            )
        except KnowledgeValidationError as exc:
            await service.record_observer_event(
                "knowledge.import.failed",
                severity="warning",
                actor_id=actor_id,
                actor_role=role,
                details={"stage": "preview", "source_kind": str(payload.get("source_kind") or "text"), "reason": "validation_error"},
            )
            await session.commit()
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
        await service.record_observer_event(
            "knowledge.import.preview_created",
            actor_id=actor_id,
            actor_role=role,
            details={
                "source_kind": preview["source_kind"],
                "body_format": preview["body_format"],
                "word_count": preview["word_count"],
                "section_count": preview["section_count"],
                "ai_enrichment_enabled": bool(preview["ai_enrichment"]["enabled"]),
            },
        )
        if bool(preview["ai_enrichment"]["enabled"]) and preview["ai_enrichment"].get("status") == "blocked_pending_policy":
            await service.record_observer_event(
                "knowledge.import.ai_enrichment_blocked",
                severity="warning",
                actor_id=actor_id,
                actor_role=role,
                details={"stage": "preview", "source_kind": preview["source_kind"], "reason": "pending_governed_create"},
            )
        await session.commit()
    return web.json_response({"status": "ok", "preview": preview})


@require_auth("admin", "support")
async def handle_web_knowledge_import_create_drafts(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    payload = await _json_payload(request)
    async with get_session() as session:
        service = KnowledgeIngestionService(session, embedding_transport=_get_embedding_transport(request))
        try:
            result = await service.create_drafts_from_import(
                payload,
                actor_id=actor_id,
                actor_role=role,
            )
        except KnowledgeRemoteImportBlockedError:
            await service.record_observer_event(
                "knowledge.import.failed",
                severity="warning",
                actor_id=actor_id,
                actor_role=role,
                details={"stage": "create_drafts", "source_kind": str(payload.get("source_kind") or "text"), "reason": "remote_import_blocked"},
            )
            await session.commit()
            return web.json_response(
                {
                    "status": "error",
                    "error": "remote_import_blocked",
                    "display_message": "Импорт из внешнего источника заблокирован политикой безопасной загрузки",
                },
                status=400,
            )
        except KnowledgeValidationError as exc:
            await service.record_observer_event(
                "knowledge.import.failed",
                severity="warning",
                actor_id=actor_id,
                actor_role=role,
                details={"stage": "create_drafts", "source_kind": str(payload.get("source_kind") or "text"), "reason": "validation_error"},
            )
            await session.commit()
            return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
        await service.record_observer_event(
            "knowledge.import.drafts_created",
            actor_id=actor_id,
            actor_role=role,
            details={
                "job_id": result["job"]["job_id"],
                "item_id": result["item"]["item_id"],
                "version_id": result["version"]["version_id"],
                "source_kind": result["preview"]["source_kind"],
                "segmentation_enabled": bool(result["segmentation"]["enabled"]),
                "indexing_status": result["indexing"]["status"],
                "ai_enrichment_status": result["ai_enrichment"]["status"],
            },
        )
        await session.commit()
    return web.json_response({"status": "ok", **result})
