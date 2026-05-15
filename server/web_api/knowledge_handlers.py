from __future__ import annotations

from aiohttp import web
from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import KnowledgeIngestionJob, KnowledgeNode, KnowledgeSpace
from app.repos.knowledge_repo import KnowledgeRepo
from auth.middleware import require_auth
from knowledge.contracts import (
    KnowledgePublicationBlockedError,
    actor_visible_visibilities,
    can_mutate_knowledge_visibility,
)
from knowledge.feedback_service import KnowledgeFeedbackService
from knowledge.graph_service import KnowledgeGraphService
from knowledge.ingestion_service import KnowledgeIngestionService
from knowledge.metrics_service import KnowledgeMetricsService
from knowledge.search_service import KnowledgeSearchService
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
    try:
        _actor_id, actor_role = _actor(request)
        payload = await _json_payload(request)
        async with get_session() as session:
            results = await KnowledgeSearchService(session).search(
                query=payload.get("query"),
                actor_role=actor_role,
                service_code=payload.get("service_code"),
                offering_code=payload.get("offering_code"),
                request_template_key=payload.get("request_template_key"),
                limit=int(payload.get("limit") or 10),
            )
        return web.json_response({"status": "ok", "results": results})
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)


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
