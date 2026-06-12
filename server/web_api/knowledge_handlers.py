from __future__ import annotations

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import KnowledgeContentPack, KnowledgeGapFinding, KnowledgeIngestionJob, KnowledgeNode, KnowledgeReviewTask, KnowledgeSpace
from app.repos.knowledge_repo import KnowledgeRepo
from auth.middleware import require_auth
from knowledge.contracts import (
    KnowledgePublicationBlockedError,
    actor_visible_visibilities,
    can_mutate_knowledge_visibility,
)
from knowledge.content_pack_service import KnowledgeContentPackService
from knowledge.embedding_service import KnowledgeEmbeddingService
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.graph_service import KnowledgeGraphService
from knowledge.ingestion_service import KnowledgeIngestionService
from knowledge.metrics_service import KnowledgeMetricsService
from knowledge.operations_service import CONTENT_TEMPLATES, KnowledgeOperationsService
from knowledge.gap_service import KnowledgeGapService, serialize_gap_finding
from knowledge.review_task_service import KnowledgeReviewTaskService, serialize_review_task
from knowledge.search_service import KnowledgeSearchService
from knowledge.search_settings_service import KnowledgeSearchSettingsService
from knowledge.segmentation_service import KnowledgeSegmentationPolicyBlockedError, KnowledgeSegmentationService
from knowledge.suggestion_service import KnowledgeSuggestionService


def _actor(request: web.Request) -> tuple[str | None, str]:
    auth = request.get("auth_context") or request.get("auth")
    actor_id = str(getattr(auth, "actor_id", "") or "") or None
    actor_role = str(getattr(auth, "actor_role", "") or "requester")
    if actor_role == "user":
        actor_role = "requester"
    return actor_id, actor_role


async def _json_payload(request: web.Request) -> dict:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
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
            version = await repo.create_version(item_id, payload, actor_id=actor_id, actor_role=role)
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
            item = await KnowledgeRepo(session).publish_item(
                item_id,
                payload.get("version_id"),
                actor_id=actor_id,
                actor_role=role,
                acknowledge_stale_passport=bool(payload.get("acknowledge_stale_passport")),
                review_note=payload.get("review_note"),
            )
            await session.commit()
        return web.json_response({"status": "ok", "item": item})
    except KnowledgePublicationBlockedError as exc:
        return web.json_response({"status": "error", "error": "publish_blocked", "blockers": exc.blockers}, status=400)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


async def handle_knowledge_suggest(request: web.Request) -> web.Response:
    try:
        _actor_id, actor_role = _actor(request)
        payload = await _json_payload(request)
        async with get_session() as session:
            result = await KnowledgeSuggestionService(session).suggest(payload, actor_role=actor_role)
        return web.json_response({"status": "ok", **result})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[knowledge] suggest failed")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


async def handle_knowledge_search(request: web.Request) -> web.Response:
    return await _handle_knowledge_search_response(request)


async def _handle_knowledge_search_response(request: web.Request) -> web.Response:
    try:
        _actor_id, actor_role = _actor(request)
        payload = await _json_payload(request)
        async with get_session() as session:
            settings = await KnowledgeSearchSettingsService(session).get_settings()
            configured_limit = int(settings.get("max_results") or 10)
            snippet_length = int(settings.get("snippet_length") or 180)
            requested_limit = int(payload.get("limit") or configured_limit)
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
        await session.commit()
    return web.json_response({"status": "ok", "event": event})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_metrics_summary(request: web.Request) -> web.Response:
    _actor_id, role = _actor(request)
    async with get_session() as session:
        summary = await KnowledgeMetricsService(session).summary(actor_role=role)
    return web.json_response({"status": "ok", "summary": summary})


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
    actor_id, _role = _actor(request)
    item_id = str(request.match_info.get("item_id_or_slug") or "")
    payload = await _json_payload(request)
    try:
        async with get_session() as session:
            result = await KnowledgeOperationsService(session).review_action(
                item_id,
                action=str(payload.get("action") or ""),
                actor_id=actor_id,
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
    async with get_session() as session:
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            visibility = str(payload.get("visibility") or "support_internal")
            if not can_mutate_knowledge_visibility(role, visibility):
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            node = await KnowledgeGraphService(session).upsert_node(
                stable_key=str(payload.get("stable_key") or ""),
                node_type=str(payload.get("node_type") or "concept"),
                label=str(payload.get("label") or payload.get("stable_key") or ""),
                visibility=visibility,
                linked_item_id=payload.get("linked_item_id"),
                service_code=payload.get("service_code"),
                offering_code=payload.get("offering_code"),
                actor_id=actor_id,
            )
            await session.commit()
            return web.json_response({"status": "ok", "node": {"node_id": node.node_id, "stable_key": node.stable_key, "label": node.label}})
        allowed = set(actor_visible_visibilities(role))
        rows = (
            await session.execute(
                select(KnowledgeNode)
                .where(KnowledgeNode.visibility.in_(allowed))
                .order_by(KnowledgeNode.updated_at.desc())
                .limit(100)
            )
        ).scalars().all()
        return web.json_response(
            {
                "status": "ok",
                "nodes": [
                    {
                        "node_id": row.node_id,
                        "stable_key": row.stable_key,
                        "node_type": row.node_type,
                        "label": row.label,
                        "visibility": row.visibility,
                    }
                    for row in rows
                ],
            }
        )


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


@require_auth("admin", "support")
async def handle_web_knowledge_graph_edges(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    payload = await _json_payload(request)
    async with get_session() as session:
        graph = KnowledgeGraphService(session)
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
        edge = await graph.create_edge(
            source,
            target,
            relation_type=str(payload.get("relation_type") or "mentions"),
            visibility=visibility,
            actor_id=actor_id,
        )
        await session.commit()
    return web.json_response({"status": "ok", "edge": {"edge_id": edge.edge_id, "relation_type": edge.relation_type}})


@require_auth("admin", "support", "auditor")
async def handle_web_knowledge_ingestion_jobs(request: web.Request) -> web.Response:
    actor_id, role = _actor(request)
    async with get_session() as session:
        if request.method == "POST":
            if role not in {"admin", "support"}:
                return web.json_response({"status": "error", "error": "forbidden"}, status=403)
            payload = await _json_payload(request)
            result = await KnowledgeIngestionService(session).ingest_text(payload, actor_id=actor_id, actor_role=role)
            await session.commit()
            return web.json_response({"status": "ok", **result})
        allowed = set(actor_visible_visibilities(role))
        rows = (
            await session.execute(
                select(KnowledgeIngestionJob)
                .join(KnowledgeSpace, KnowledgeIngestionJob.space_id == KnowledgeSpace.space_id)
                .where(KnowledgeSpace.visibility.in_(allowed))
                .order_by(KnowledgeIngestionJob.created_at.desc())
                .limit(100)
            )
        ).scalars().all()
        return web.json_response(
            {
                "status": "ok",
                "jobs": [
                    {
                        "job_id": row.job_id,
                        "space_id": row.space_id,
                        "source_kind": row.source_kind,
                        "source_name": row.source_name,
                        "status": row.status,
                        "created_item_id": row.created_item_id,
                        "created_version_id": row.created_version_id,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in rows
                ],
            }
        )
