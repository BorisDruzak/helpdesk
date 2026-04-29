"""
Stage 9: HTTP handlers для Admin Config API.
"""
from typing import Optional

from aiohttp import web
from loguru import logger

from config import (
    TICKET_ADMIN_CONFIG_API_ENABLED,
    TICKET_ADMIN_CONFIG_WRITE_ENABLED,
    TICKET_AUDITOR_ROLE_ENABLED,
)
from access_control.service import can
from auth.middleware import require_auth
from app.db import get_session
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from tickets.admin_config_service import (
    AdminConfigService,
    validate_condition_json,
    validate_sla_targets,
    validate_priority_matrix,
)


def _check_api_enabled() -> Optional[web.Response]:
    if not TICKET_ADMIN_CONFIG_API_ENABLED:
        return web.json_response(
            {"status": "error", "error": "Admin Config API disabled", "error_code": "API_DISABLED"},
            status=404,
        )
    return None


def _check_write_enabled() -> Optional[web.Response]:
    if not TICKET_ADMIN_CONFIG_WRITE_ENABLED:
        return web.json_response(
            {
                "status": "error",
                "error": "Admin Config write operations disabled",
                "error_code": "WRITE_DISABLED",
            },
            status=403,
        )
    return None


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


async def _check_permission(session, request: web.Request, permission_code: str) -> Optional[web.Response]:
    if await can(session, request["auth_context"], permission_code):
        return None
    return _permission_denied(permission_code)


async def _check_request_permission(request: web.Request, permission_code: str) -> Optional[web.Response]:
    async with get_session() as session:
        denied = await _check_permission(session, request, permission_code)
        await session.commit()
        return denied


def _allowed_read_roles() -> tuple:
    if TICKET_AUDITOR_ROLE_ENABLED:
        return ("admin", "support", "auditor")
    return ("admin", "support")


def _get_trace_id(request: web.Request) -> Optional[str]:
    return request.headers.get("X-Trace-Id") or request.query.get("trace_id")


# --- Queues ---
@require_auth("admin", "support", "auditor")
async def handle_admin_queues_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    include_inactive = request.query.get("include_inactive", "false").lower() == "true"
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        queues = await repo.list_queues(include_inactive=include_inactive)
        await session.commit()
    items = [
        {
            "id": q.id,
            "code": q.code,
            "name": q.name,
            "is_triage": q.is_triage,
            "is_active": q.is_active,
            "auto_assign_enabled": getattr(q, "auto_assign_enabled", True),
        }
        for q in queues
    ]
    return web.json_response({"status": "ok", "queues": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_queues_post(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_queues")
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    is_triage = data.get("is_triage", False)
    auto_assign_enabled = data.get("auto_assign_enabled", True)
    if not code or not name:
        return web.json_response(
            {"status": "error", "error": "code and name required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        existing = await repo.get_queue_by_code(code)
        if existing:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": f"Queue with code {code} already exists", "error_code": "CONFLICT"},
                status=409,
            )
        q = await repo.create_queue(
            code=code,
            name=name,
            is_triage=is_triage,
            auto_assign_enabled=bool(auto_assign_enabled),
        )
        svc = AdminConfigService(repo, audit_repo)
        await audit_repo.add(
            entity_type="queue",
            entity_id=str(q.id),
            action="create",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            after_json=svc._serialize_queue(q),
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "queue": {
                "id": q.id,
                "code": q.code,
                "name": q.name,
                "is_triage": q.is_triage,
                "is_active": q.is_active,
                "auto_assign_enabled": getattr(q, "auto_assign_enabled", True),
            },
        },
        status=201,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_queues_get(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        q = await repo.get_queue(queue_id)
        await session.commit()
    if not q:
        return web.json_response(
            {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response(
        {
            "status": "ok",
            "queue": {
                "id": q.id,
                "code": q.code,
                "name": q.name,
                "is_triage": q.is_triage,
                "is_active": q.is_active,
                "auto_assign_enabled": getattr(q, "auto_assign_enabled", True),
            },
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_queues_patch(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_queues")
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        svc = AdminConfigService(repo, audit_repo)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        if "is_active" in data and data["is_active"] is False:
            ok, err = await svc.can_deactivate_queue(queue_id)
            if not ok:
                await session.rollback()
                return web.json_response(
                    {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
                    status=409,
                )
        before = svc._serialize_queue(q)
        updates = {}
        for k in ("code", "name", "is_triage", "is_active", "auto_assign_enabled"):
            if k in data:
                updates[k] = data[k]
        q = await repo.update_queue(queue_id, **updates)
        if q:
            await audit_repo.add(
                entity_type="queue",
                entity_id=str(queue_id),
                action="update",
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
                before_json=before,
                after_json=svc._serialize_queue(q),
                trace_id=_get_trace_id(request),
            )
        await session.commit()
    if not q:
        return web.json_response(
            {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response(
        {
            "status": "ok",
            "queue": {
                "id": q.id,
                "code": q.code,
                "name": q.name,
                "is_triage": q.is_triage,
                "is_active": q.is_active,
                "auto_assign_enabled": getattr(q, "auto_assign_enabled", True),
            },
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_queue_members_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        members = await repo.list_queue_members(queue_id)
        await session.commit()
    items = [{"actor_id": m.actor_id, "role_in_queue": m.role_in_queue} for m in members]
    return web.json_response({"status": "ok", "members": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_queue_members_put(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_queues")
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    actor_id = request.match_info["actor_id"]
    try:
        data = await request.json() or {}
    except Exception:
        data = {}
    role_in_queue = data.get("role_in_queue")
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before_m = await repo.get_queue_member(queue_id, actor_id)
        before_json = {"actor_id": actor_id, "role_in_queue": before_m.role_in_queue} if before_m else None
        m = await repo.put_queue_member(queue_id, actor_id, role_in_queue=role_in_queue)
        await audit_repo.add(
            entity_type="queue_member",
            entity_id=f"{queue_id}:{actor_id}",
            action="upsert",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before_json,
            after_json={"actor_id": m.actor_id, "role_in_queue": m.role_in_queue},
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {"status": "ok", "member": {"actor_id": m.actor_id, "role_in_queue": m.role_in_queue}},
        status=200,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_queue_members_delete(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_queues")
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    actor_id = request.match_info["actor_id"]
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before_m = await repo.get_queue_member(queue_id, actor_id)
        if not before_m:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        await repo.delete_queue_member(queue_id, actor_id)
        await audit_repo.add(
            entity_type="queue_member",
            entity_id=f"{queue_id}:{actor_id}",
            action="delete",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json={"actor_id": actor_id, "role_in_queue": before_m.role_in_queue},
            after_json=None,
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok"}, status=200)


# --- Resolution codes ---
@require_auth("admin", "support", "auditor")
async def handle_admin_resolution_codes_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    include_inactive = request.query.get("include_inactive", "false").lower() == "true"
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        items = await repo.list_resolution_codes(include_inactive=include_inactive)
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "resolution_codes": [
                {
                    "code": item.code,
                    "name": item.name,
                    "is_active": item.is_active,
                    "sort_order": item.sort_order,
                }
                for item in items
            ],
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_resolution_codes_post(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    code = str(data.get("code") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        return web.json_response(
            {"status": "error", "error": "code and name required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        existing = await repo.get_resolution_code(code)
        if existing:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": f"Resolution code {code} already exists", "error_code": "CONFLICT"},
                status=409,
            )
        item = await repo.create_resolution_code(
            code=code,
            name=name,
            is_active=bool(data.get("is_active", True)),
            sort_order=int(data.get("sort_order", 0) or 0),
        )
        await audit_repo.add(
            entity_type="resolution_code",
            entity_id=item.code,
            action="create",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            after_json={
                "code": item.code,
                "name": item.name,
                "is_active": item.is_active,
                "sort_order": item.sort_order,
            },
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "resolution_code": {
                "code": item.code,
                "name": item.name,
                "is_active": item.is_active,
                "sort_order": item.sort_order,
            },
        },
        status=201,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_resolution_codes_patch(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    code = request.match_info["code"]
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        item = await repo.get_resolution_code(code)
        if not item:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before = {
            "code": item.code,
            "name": item.name,
            "is_active": item.is_active,
            "sort_order": item.sort_order,
        }
        updates = {}
        for key in ("name", "is_active", "sort_order"):
            if key in data:
                updates[key] = data[key]
        item = await repo.update_resolution_code(code, **updates)
        await audit_repo.add(
            entity_type="resolution_code",
            entity_id=code,
            action="update",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before,
            after_json={
                "code": item.code,
                "name": item.name,
                "is_active": item.is_active,
                "sort_order": item.sort_order,
            },
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "resolution_code": {
                "code": item.code,
                "name": item.name,
                "is_active": item.is_active,
                "sort_order": item.sort_order,
            },
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_resolution_codes_delete(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    code = request.match_info["code"]
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        item = await repo.get_resolution_code(code)
        if not item:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        usage_count = await repo.count_tickets_with_resolution_code(code)
        if usage_count > 0:
            await session.rollback()
            return web.json_response(
                {
                    "status": "error",
                    "error": "Resolution code is already used in tickets. Deactivate it instead of deleting.",
                    "error_code": "VALIDATION_ERROR",
                    "usage_count": usage_count,
                },
                status=409,
            )
        before = {
            "code": item.code,
            "name": item.name,
            "is_active": item.is_active,
            "sort_order": item.sort_order,
        }
        await repo.delete_resolution_code(code)
        await audit_repo.add(
            entity_type="resolution_code",
            entity_id=code,
            action="delete",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before,
            after_json=None,
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok"}, status=200)


# --- Routing rules ---
@require_auth("admin", "support", "auditor")
async def handle_admin_routing_rules_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    include_disabled = request.query.get("include_disabled", "false").lower() == "true"
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        rules = await repo.list_routing_rules(include_disabled=include_disabled)
        await session.commit()
    items = [
        {
            "id": r.id,
            "enabled": r.enabled,
            "priority_order": r.priority_order,
            "condition_json": r.condition_json,
            "target_queue_id": r.target_queue_id,
        }
        for r in rules
    ]
    return web.json_response({"status": "ok", "routing_rules": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_routing_rules_post(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    target_queue_id = data.get("target_queue_id")
    if target_queue_id is None:
        return web.json_response(
            {"status": "error", "error": "target_queue_id required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    target_queue_id = int(target_queue_id)
    priority_order = data.get("priority_order", 0)
    condition_json = data.get("condition_json")
    ok, err = validate_condition_json(condition_json)
    if not ok:
        return web.json_response(
            {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    enabled = data.get("enabled", True)
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        q = await repo.get_queue(target_queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "target queue not found", "error_code": "NOT_FOUND"},
                status=404,
            )
        r = await repo.create_routing_rule(
            target_queue_id=target_queue_id,
            priority_order=priority_order,
            condition_json=condition_json,
            enabled=enabled,
        )
        svc = AdminConfigService(repo, audit_repo)
        await audit_repo.add(
            entity_type="routing_rule",
            entity_id=str(r.id),
            action="create",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            after_json=svc._serialize_rule(r),
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "routing_rule": {
                "id": r.id,
                "enabled": r.enabled,
                "priority_order": r.priority_order,
                "condition_json": r.condition_json,
                "target_queue_id": r.target_queue_id,
            },
        },
        status=201,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_routing_rules_patch(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    rule_id = int(request.match_info["rule_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    if "condition_json" in data:
        ok, err = validate_condition_json(data["condition_json"])
        if not ok:
            return web.json_response(
                {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
                status=400,
            )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        svc = AdminConfigService(repo, audit_repo)
        rule = await repo.get_routing_rule(rule_id)
        if not rule:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before = svc._serialize_rule(rule)
        updates = {}
        for k in ("enabled", "priority_order", "condition_json", "target_queue_id"):
            if k in data:
                updates[k] = data[k]
        rule = await repo.update_routing_rule(rule_id, **updates)
        if rule:
            await audit_repo.add(
                entity_type="routing_rule",
                entity_id=str(rule_id),
                action="update",
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
                before_json=before,
                after_json=svc._serialize_rule(rule),
                trace_id=_get_trace_id(request),
            )
        await session.commit()
    if not rule:
        return web.json_response(
            {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response(
        {
            "status": "ok",
            "routing_rule": {
                "id": rule.id,
                "enabled": rule.enabled,
                "priority_order": rule.priority_order,
                "condition_json": rule.condition_json,
                "target_queue_id": rule.target_queue_id,
            },
        }
    )


# --- SLA policies ---
@require_auth("admin", "support", "auditor")
async def handle_admin_sla_policies_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    include_inactive = request.query.get("include_inactive", "false").lower() == "true"
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        policies = await repo.list_sla_policies(include_inactive=include_inactive)
        await session.commit()
    items = []
    for p in policies:
        d = {
            "id": p.id,
            "name": p.name,
            "timezone": p.timezone,
            "business_hours_json": p.business_hours_json,
            "is_default": p.is_default,
            "calendar_id": getattr(p, "calendar_id", None),
            "is_active": getattr(p, "is_active", True),
        }
        items.append(d)
    return web.json_response({"status": "ok", "sla_policies": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_sla_policies_post(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    name = (data.get("name") or "").strip()
    if not name:
        return web.json_response(
            {"status": "error", "error": "name required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    timezone = data.get("timezone", "UTC")
    business_hours_json = data.get("business_hours_json")
    calendar_id = data.get("calendar_id")
    is_default = data.get("is_default", False)
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        if is_default:
            default_p = await repo.get_default_sla_policy()
            if default_p:
                await repo.update_sla_policy(default_p.id, is_default=False)
        p = await repo.create_sla_policy(
            name=name,
            timezone=timezone,
            business_hours_json=business_hours_json,
            calendar_id=calendar_id,
            is_default=is_default,
        )
        svc = AdminConfigService(repo, audit_repo)
        await audit_repo.add(
            entity_type="sla_policy",
            entity_id=str(p.id),
            action="create",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            after_json=svc._serialize_policy(p),
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "sla_policy": {
                "id": p.id,
                "name": p.name,
                "timezone": p.timezone,
                "business_hours_json": p.business_hours_json,
                "calendar_id": getattr(p, "calendar_id", None),
                "is_default": p.is_default,
                "is_active": p.is_active,
            },
        },
        status=201,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_sla_policies_patch(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        svc = AdminConfigService(repo, audit_repo)
        p = await repo.get_sla_policy(policy_id)
        if not p:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        if "is_active" in data and data["is_active"] is False:
            ok, err = await svc.can_deactivate_sla_policy(policy_id)
            if not ok:
                await session.rollback()
                return web.json_response(
                    {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
                    status=409,
                )
        if data.get("is_default") is True:
            default_p = await repo.get_default_sla_policy()
            if default_p and default_p.id != policy_id:
                await repo.update_sla_policy(default_p.id, is_default=False)
        before = svc._serialize_policy(p)
        updates = {}
        for k in ("name", "timezone", "business_hours_json", "calendar_id", "is_default", "is_active"):
            if k in data:
                updates[k] = data[k]
        p = await repo.update_sla_policy(policy_id, **updates)
        if p:
            await audit_repo.add(
                entity_type="sla_policy",
                entity_id=str(policy_id),
                action="update",
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
                before_json=before,
                after_json=svc._serialize_policy(p),
                trace_id=_get_trace_id(request),
            )
        await session.commit()
    if not p:
        return web.json_response(
            {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
            status=404,
        )
    return web.json_response(
        {
            "status": "ok",
            "sla_policy": {
                "id": p.id,
                "name": p.name,
                "timezone": p.timezone,
                "business_hours_json": p.business_hours_json,
                "is_default": p.is_default,
                "is_active": p.is_active,
            },
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_sla_policies_set_default(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        svc = AdminConfigService(repo, audit_repo)
        p = await repo.get_sla_policy(policy_id)
        if not p:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        default_p = await repo.get_default_sla_policy()
        if default_p and default_p.id == policy_id:
            await session.commit()
            return web.json_response(
                {"status": "ok", "sla_policy": {"id": p.id, "is_default": True}}
            )
        if default_p:
            await repo.update_sla_policy(default_p.id, is_default=False)
        before = svc._serialize_policy(p)
        p = await repo.update_sla_policy(policy_id, is_default=True)
        await audit_repo.add(
            entity_type="sla_policy",
            entity_id=str(policy_id),
            action="set_default",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before,
            after_json=svc._serialize_policy(p),
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok", "sla_policy": {"id": p.id, "is_default": True}})


@require_auth("admin", "support", "auditor")
async def handle_admin_sla_targets_put(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    targets = data.get("targets")
    ok, err = validate_sla_targets(targets)
    if not ok:
        return web.json_response(
            {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        p = await repo.get_sla_policy(policy_id)
        if not p:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before_targets = await repo.get_sla_targets(policy_id)
        before_json = [
            {"priority": t.priority, "first_response_min": t.first_response_min, "resolution_min": t.resolution_min}
            for t in before_targets
        ]
        await repo.replace_sla_targets(policy_id, targets)
        after_json = [{"priority": t["priority"], "first_response_min": t["first_response_min"], "resolution_min": t["resolution_min"]} for t in targets]
        await audit_repo.add(
            entity_type="sla_targets",
            entity_id=str(policy_id),
            action="replace",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before_json,
            after_json=after_json,
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok", "targets": targets})


@require_auth("admin", "support", "auditor")
async def handle_admin_sla_targets_get(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        policy = await repo.get_sla_policy(policy_id)
        if not policy:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        targets = await repo.get_sla_targets(policy_id)
        await session.commit()
    payload = [
        {"priority": target.priority, "first_response_min": target.first_response_min, "resolution_min": target.resolution_min}
        for target in targets
    ]
    return web.json_response({"status": "ok", "targets": payload})


@require_auth("admin", "support", "auditor")
async def handle_admin_priority_matrix_put(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    matrix = data.get("matrix")
    ok, err = validate_priority_matrix(matrix)
    if not ok:
        return web.json_response(
            {"status": "error", "error": err, "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        p = await repo.get_sla_policy(policy_id)
        if not p:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before_rows = await repo.get_priority_matrix(policy_id)
        before_json = [{"impact": r.impact, "urgency": r.urgency, "priority": r.priority} for r in before_rows]
        await repo.replace_priority_matrix(policy_id, matrix)
        after_json = [{"impact": m["impact"], "urgency": m["urgency"], "priority": m["priority"]} for m in matrix]
        await audit_repo.add(
            entity_type="priority_matrix",
            entity_id=str(policy_id),
            action="replace",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before_json,
            after_json=after_json,
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok", "matrix": matrix})


@require_auth("admin", "support", "auditor")
async def handle_admin_priority_matrix_get(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    policy_id = int(request.match_info["policy_id"])
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        policy = await repo.get_sla_policy(policy_id)
        if not policy:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        rows = await repo.get_priority_matrix(policy_id)
        await session.commit()
    payload = [{"impact": row.impact, "urgency": row.urgency, "priority": row.priority} for row in rows]
    return web.json_response({"status": "ok", "matrix": payload})


# --- Stage 11: Calendars ---
@require_auth("admin", "support", "auditor")
async def handle_admin_calendars_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    include_inactive = request.query.get("include_inactive", "false").lower() == "true"
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        calendars = await repo.list_calendars(include_inactive=include_inactive)
        await session.commit()
    items = [
        {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "timezone": c.timezone,
            "weekly_hours_json": c.weekly_hours_json,
            "holidays_json": c.holidays_json,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in calendars
    ]
    return web.json_response({"status": "ok", "calendars": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_calendars_post(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        return web.json_response(
            {"status": "error", "error": "code and name required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    timezone = data.get("timezone", "UTC")
    weekly_hours_json = data.get("weekly_hours_json")
    holidays_json = data.get("holidays_json")
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        existing = await repo.get_calendar_by_code(code)
        if existing:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "Calendar code already exists", "error_code": "CONFLICT"},
                status=409,
            )
        c = await repo.create_calendar(
            code=code,
            name=name,
            timezone=timezone,
            weekly_hours_json=weekly_hours_json,
            holidays_json=holidays_json,
        )
        await audit_repo.add(
            entity_type="calendar",
            entity_id=str(c.id),
            action="create",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            after_json={"id": c.id, "code": c.code, "name": c.name, "timezone": c.timezone},
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response(
        {
            "status": "ok",
            "calendar": {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "timezone": c.timezone,
                "weekly_hours_json": c.weekly_hours_json,
                "holidays_json": c.holidays_json,
                "is_active": c.is_active,
            },
        },
        status=201,
    )


@require_auth("admin", "support", "auditor")
async def handle_admin_calendars_patch(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_routing")
    if r:
        return r
    calendar_id = int(request.match_info["calendar_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        c = await repo.get_calendar(calendar_id)
        if not c:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before = {"code": c.code, "name": c.name, "timezone": c.timezone, "is_active": c.is_active}
        updates = {}
        for k in ("code", "name", "timezone", "weekly_hours_json", "holidays_json", "is_active"):
            if k in data:
                updates[k] = data[k]
        c = await repo.update_calendar(calendar_id, **updates)
        if c:
            after = {"code": c.code, "name": c.name, "timezone": c.timezone, "is_active": c.is_active}
            await audit_repo.add(
                entity_type="calendar",
                entity_id=str(calendar_id),
                action="update",
                actor_id=auth.actor_id,
                actor_role=auth.actor_role,
                before_json=before,
                after_json=after,
                trace_id=_get_trace_id(request),
            )
        await session.commit()
    return web.json_response({
        "status": "ok",
        "calendar": {
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "timezone": c.timezone,
            "weekly_hours_json": c.weekly_hours_json,
            "holidays_json": c.holidays_json,
            "is_active": c.is_active,
        },
    })


# --- Stage 11: OLA targets ---
@require_auth("admin", "support", "auditor")
async def handle_admin_ola_targets_get(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        targets = await repo.list_ola_targets(queue_id)
        await session.commit()
    items = [{"priority": t.priority, "ack_min": t.ack_min, "processing_min": t.processing_min} for t in targets]
    return web.json_response({"status": "ok", "queue_id": queue_id, "ola_targets": items})


@require_auth("admin", "support", "auditor")
async def handle_admin_ola_targets_put(request: web.Request) -> web.Response:
    r = _check_api_enabled() or _check_write_enabled()
    if r:
        return r
    r = await _check_request_permission(request, "settings.manage_queues")
    if r:
        return r
    queue_id = int(request.match_info["queue_id"])
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "INVALID_JSON"},
            status=400,
        )
    targets = data.get("ola_targets") if isinstance(data.get("ola_targets"), list) else []
    for i, t in enumerate(targets):
        if not isinstance(t, dict) or t.get("priority") not in ("P1", "P2", "P3", "P4"):
            return web.json_response(
                {"status": "error", "error": f"ola_targets[{i}]: priority required (P1-P4)", "error_code": "VALIDATION_ERROR"},
                status=400,
            )
        if not isinstance(t.get("ack_min"), int) or t["ack_min"] < 0 or not isinstance(t.get("processing_min"), int) or t["processing_min"] < 0:
            return web.json_response(
                {"status": "error", "error": f"ola_targets[{i}]: ack_min and processing_min required (non-negative int)", "error_code": "VALIDATION_ERROR"},
                status=400,
            )
    auth = request["auth_context"]
    async with get_session() as session:
        repo = TicketAdminConfigRepo(session)
        audit_repo = TicketAdminAuditRepo(session)
        q = await repo.get_queue(queue_id)
        if not q:
            await session.rollback()
            return web.json_response(
                {"status": "error", "error": "not_found", "error_code": "NOT_FOUND"},
                status=404,
            )
        before_list = await repo.list_ola_targets(queue_id)
        before_json = [{"priority": t.priority, "ack_min": t.ack_min, "processing_min": t.processing_min} for t in before_list]
        out = await repo.replace_ola_targets(queue_id, targets)
        after_json = [{"priority": t.priority, "ack_min": t.ack_min, "processing_min": t.processing_min} for t in out]
        await audit_repo.add(
            entity_type="ola_targets",
            entity_id=str(queue_id),
            action="replace",
            actor_id=auth.actor_id,
            actor_role=auth.actor_role,
            before_json=before_json,
            after_json=after_json,
            trace_id=_get_trace_id(request),
        )
        await session.commit()
    return web.json_response({"status": "ok", "queue_id": queue_id, "ola_targets": after_json})


# --- Audit ---
@require_auth("admin", "support", "auditor")
async def handle_admin_audit_list(request: web.Request) -> web.Response:
    if not TICKET_AUDITOR_ROLE_ENABLED and request.get("auth_context").actor_role == "auditor":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )
    r = _check_api_enabled()
    if r:
        return r
    entity_type = request.query.get("entity_type")
    entity_id = request.query.get("entity_id")
    actor_id = request.query.get("actor_id")
    limit = min(int(request.query.get("limit", 100)), 500)
    offset = int(request.query.get("offset", 0))
    async with get_session() as session:
        audit_repo = TicketAdminAuditRepo(session)
        records = await audit_repo.list_audit(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            limit=limit,
            offset=offset,
        )
        await session.commit()
    items = [
        {
            "id": r.id,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "action": r.action,
            "actor_id": r.actor_id,
            "actor_role": r.actor_role,
            "before_json": r.before_json,
            "after_json": r.after_json,
            "trace_id": r.trace_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return web.json_response({"status": "ok", "audit": items})
