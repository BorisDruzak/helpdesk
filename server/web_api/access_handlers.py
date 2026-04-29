from __future__ import annotations

from aiohttp import web
from loguru import logger
from pydantic import ValidationError

from access_control.catalog import (
    CATALOG_VERSION,
    ROLE_LABELS,
    get_permission_catalog,
    get_role_label,
    get_role_permission_codes,
)
from access_control.service import grouped_permissions, resolve_effective_access
from app.db import get_session
from app.repos.access_control_repo import AccessControlRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ui_users_repo import UiUsersRepo
from auth.middleware import require_auth
from web_api.dto.access_control import (
    AccessAuditItem,
    AccessAuditPayload,
    AccessCatalogPayload,
    AccessEffectivePayload,
    AccessGroupCreateRequest,
    AccessGroupItem,
    AccessGroupMembersRequest,
    AccessGroupPermissionsRequest,
    AccessGroupQueuesRequest,
    AccessGroupUpdateRequest,
    AccessQueueItem,
    AccessQueueMembershipItem,
    AccessRoleItem,
    AccessSummaryPayload,
    AccessUserItem,
)
from web_api.dto.common import SuccessResponse, json_model_response


def _catalog_payload() -> AccessCatalogPayload:
    return AccessCatalogPayload(
        version=CATALOG_VERSION,
        roles=[
            AccessRoleItem(
                code=role,
                label=label,
                permissions=get_role_permission_codes(role),
            )
            for role, label in ROLE_LABELS.items()
        ],
        groups=grouped_permissions(),
    )


PERMISSION_CODES = {item.code for item in get_permission_catalog()}


def _bad_request(error: str, error_code: str = "VALIDATION_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": error, "error_code": error_code}, status=400)


def _not_found(error: str, error_code: str = "NOT_FOUND") -> web.Response:
    return web.json_response({"status": "error", "error": error, "error_code": error_code}, status=404)


async def _load_queue_memberships(session, actor_id: str) -> list[AccessQueueMembershipItem]:
    if not actor_id:
        return []
    memberships: list[AccessQueueMembershipItem] = []
    repo = TicketAdminConfigRepo(session)
    queues = await repo.list_queues(include_inactive=True)
    for queue in queues:
        member = await repo.get_queue_member(int(queue.id), actor_id)
        if member is None:
            continue
        memberships.append(
            AccessQueueMembershipItem(
                queue_id=int(queue.id),
                queue_code=str(queue.code),
                queue_name=str(queue.name),
                role_in_queue=member.role_in_queue,
            )
        )
    return memberships


async def _group_item(repo: AccessControlRepo, group) -> AccessGroupItem:
    return AccessGroupItem(
        group_id=int(group.id),
        code=str(group.code),
        name=str(group.name),
        description=group.description,
        is_active=bool(group.is_active),
        permissions=await repo.list_group_permissions(int(group.id)),
        members=await repo.list_group_members(int(group.id)),
        queue_grants=[
            AccessQueueMembershipItem(**item)
            for item in await repo.list_group_queue_grants(int(group.id))
        ],
    )


async def _summary_payload() -> AccessSummaryPayload:
    users: list[AccessUserItem] = []
    queues_payload: list[AccessQueueItem] = []
    groups_payload: list[AccessGroupItem] = []
    notes = ["Access groups are enabled; effective access is role defaults + group grants + direct queue membership."]
    try:
        async with get_session() as session:
            users_repo = UiUsersRepo(session)
            queue_repo = TicketAdminConfigRepo(session)
            access_repo = AccessControlRepo(session)
            users_rows = await users_repo.list_users(include_inactive=True, limit=500)
            queues = await queue_repo.list_queues(include_inactive=True)

            queue_members_by_actor: dict[str, int] = {}
            for queue in queues:
                members = await queue_repo.list_queue_members(int(queue.id))
                queues_payload.append(
                    AccessQueueItem(
                        queue_id=int(queue.id),
                        queue_code=str(queue.code),
                        queue_name=str(queue.name),
                        is_active=bool(queue.is_active),
                        members_count=len(members),
                    )
                )
                for member in members:
                    queue_members_by_actor[str(member.actor_id)] = queue_members_by_actor.get(str(member.actor_id), 0) + 1

            group_codes_by_actor: dict[str, list[str]] = {}
            for group in await access_repo.list_groups(include_inactive=True):
                groups_payload.append(await _group_item(access_repo, group))
                if not group.is_active:
                    continue
                for member in await access_repo.list_group_members(int(group.id)):
                    group_codes_by_actor.setdefault(member, []).append(str(group.code))

            users = [
                AccessUserItem(
                    user_login=str(user.user_login),
                    actor_role=str(user.actor_role),
                    role_label=get_role_label(user.actor_role),
                    is_active=bool(user.is_active),
                    groups=sorted(group_codes_by_actor.get(str(user.user_login), [])),
                    queue_count=queue_members_by_actor.get(str(user.user_login), 0),
                )
                for user in users_rows
            ]
    except Exception as exc:
        logger.warning(f"[web_admin_access_summary] DB unavailable, returning empty access summary: {exc}")
        notes.append("DB-backed users/queues are temporarily unavailable.")

    return AccessSummaryPayload(
        version=CATALOG_VERSION,
        users=users,
        queues=queues_payload,
        access_groups=groups_payload,
        notes=notes,
    )


@require_auth("admin")
async def handle_web_admin_access_catalog(_request: web.Request):
    return json_model_response(SuccessResponse[AccessCatalogPayload](data=_catalog_payload()))


@require_auth("admin")
async def handle_web_admin_access_summary(_request: web.Request):
    payload = await _summary_payload()
    return json_model_response(SuccessResponse[AccessSummaryPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_access_effective(request: web.Request):
    actor_id = str(request.query.get("actor_id") or "").strip()
    actor_role = str(request.query.get("actor_role") or "").strip()
    groups: list[str] = []
    group_permissions: list[str] = []
    queues: list[AccessQueueMembershipItem] = []
    if actor_id:
        try:
            async with get_session() as session:
                users_repo = UiUsersRepo(session)
                access_repo = AccessControlRepo(session)
                if not actor_role:
                    user = await users_repo.get_by_login(actor_id)
                    if user is not None:
                        actor_role = str(user.actor_role)
                groups = await access_repo.get_actor_group_codes(actor_id)
                group_permissions = await access_repo.get_actor_group_permissions(actor_id)
                direct_queues = await _load_queue_memberships(session, actor_id)
                group_queues = [
                    AccessQueueMembershipItem(**item)
                    for item in await access_repo.get_actor_group_queues(actor_id)
                ]
                queues = _merge_queue_memberships(direct_queues + group_queues)
                if not actor_role:
                    user = await users_repo.get_by_login(actor_id)
                    if user is not None:
                        actor_role = str(user.actor_role)
        except Exception as exc:
            logger.warning(f"[web_admin_access_effective] could not resolve actor access: actor_id={actor_id} error={exc}")
    if not actor_role:
        actor_role = "user"

    effective = resolve_effective_access(
        actor_id=actor_id,
        actor_role=actor_role,
        queues=[queue.model_dump(mode="json") for queue in queues],
        groups=groups,
        group_permissions=group_permissions,
    )
    payload = AccessEffectivePayload(
        actor_id=effective.actor_id,
        actor_role=effective.actor_role,
        role_label=effective.role_label,
        permissions=effective.permissions,
        workspaces=effective.workspaces,
        groups=effective.groups,
        queues=queues,
        sources={
            "role": effective.actor_role,
            "groups": effective.groups,
            "queues": [queue.queue_code for queue in queues],
        },
    )
    return json_model_response(SuccessResponse[AccessEffectivePayload](data=payload))


def _merge_queue_memberships(queues: list[AccessQueueMembershipItem]) -> list[AccessQueueMembershipItem]:
    merged: dict[int, AccessQueueMembershipItem] = {}
    for queue in queues:
        if queue.queue_id not in merged:
            merged[queue.queue_id] = queue
    return sorted(merged.values(), key=lambda item: item.queue_code)


def _actor(request: web.Request) -> tuple[str, str]:
    auth_context = request["auth_context"]
    return str(auth_context.actor_id), str(auth_context.actor_role)


def _validate_permissions(permissions: list[str]) -> list[str] | web.Response:
    normalized = sorted({str(item).strip() for item in permissions if str(item).strip()})
    unknown = [item for item in normalized if item not in PERMISSION_CODES]
    if unknown:
        return _bad_request(f"Unknown permissions: {', '.join(unknown)}", "UNKNOWN_PERMISSION")
    return normalized


@require_auth("admin")
async def handle_web_admin_access_create_group(request: web.Request):
    try:
        payload = AccessGroupCreateRequest.model_validate(await request.json())
    except (ValidationError, ValueError):
        return _bad_request("Некорректные данные группы доступа")
    actor_id, actor_role = _actor(request)
    try:
        async with get_session() as session:
            repo = AccessControlRepo(session)
            group = await repo.create_group(
                code=payload.code.strip(),
                name=payload.name.strip(),
                description=payload.description,
                is_active=payload.is_active,
                actor_id=actor_id,
                actor_role=actor_role,
            )
            data = await _group_item(repo, group)
    except ValueError as exc:
        return _bad_request(str(exc), "ACCESS_GROUP_EXISTS")
    return json_model_response(SuccessResponse[AccessGroupItem](data=data))


@require_auth("admin")
async def handle_web_admin_access_update_group(request: web.Request):
    try:
        group_id = int(request.match_info["group_id"])
        payload = AccessGroupUpdateRequest.model_validate(await request.json())
    except (KeyError, TypeError, ValueError, ValidationError):
        return _bad_request("Некорректные данные группы доступа")
    actor_id, actor_role = _actor(request)
    async with get_session() as session:
        repo = AccessControlRepo(session)
        group = await repo.update_group(
            group_id,
            name=payload.name.strip() if payload.name is not None else None,
            description=payload.description,
            is_active=payload.is_active,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if group is None:
            return _not_found("Access group not found", "ACCESS_GROUP_NOT_FOUND")
        data = await _group_item(repo, group)
    return json_model_response(SuccessResponse[AccessGroupItem](data=data))


@require_auth("admin")
async def handle_web_admin_access_group_permissions(request: web.Request):
    try:
        group_id = int(request.match_info["group_id"])
        payload = AccessGroupPermissionsRequest.model_validate(await request.json())
    except (KeyError, TypeError, ValueError, ValidationError):
        return _bad_request("Некорректный список permissions")
    permissions = _validate_permissions(payload.permissions)
    if isinstance(permissions, web.Response):
        return permissions
    actor_id, actor_role = _actor(request)
    async with get_session() as session:
        repo = AccessControlRepo(session)
        result = await repo.set_group_permissions(group_id, permissions, actor_id=actor_id, actor_role=actor_role)
        if result is None:
            return _not_found("Access group not found", "ACCESS_GROUP_NOT_FOUND")
        group = await repo.get_group(group_id)
        data = await _group_item(repo, group)
    return json_model_response(SuccessResponse[AccessGroupItem](data=data))


@require_auth("admin")
async def handle_web_admin_access_group_members(request: web.Request):
    try:
        group_id = int(request.match_info["group_id"])
        payload = AccessGroupMembersRequest.model_validate(await request.json())
    except (KeyError, TypeError, ValueError, ValidationError):
        return _bad_request("Некорректный список участников")
    actor_id, actor_role = _actor(request)
    async with get_session() as session:
        repo = AccessControlRepo(session)
        result = await repo.set_group_members(group_id, payload.actor_ids, actor_id=actor_id, actor_role=actor_role)
        if result is None:
            return _not_found("Access group not found", "ACCESS_GROUP_NOT_FOUND")
        group = await repo.get_group(group_id)
        data = await _group_item(repo, group)
    return json_model_response(SuccessResponse[AccessGroupItem](data=data))


@require_auth("admin")
async def handle_web_admin_access_group_queues(request: web.Request):
    try:
        group_id = int(request.match_info["group_id"])
        payload = AccessGroupQueuesRequest.model_validate(await request.json())
    except (KeyError, TypeError, ValueError, ValidationError):
        return _bad_request("Некорректный список очередей")
    actor_id, actor_role = _actor(request)
    async with get_session() as session:
        repo = AccessControlRepo(session)
        result = await repo.set_group_queues(
            group_id,
            [item.model_dump(mode="json") for item in payload.queues],
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if result is None:
            return _not_found("Access group not found", "ACCESS_GROUP_NOT_FOUND")
        group = await repo.get_group(group_id)
        data = await _group_item(repo, group)
    return json_model_response(SuccessResponse[AccessGroupItem](data=data))


@require_auth("admin")
async def handle_web_admin_access_audit(_request: web.Request):
    async with get_session() as session:
        repo = AccessControlRepo(session)
        rows = await repo.list_audit(limit=100)
    payload = AccessAuditPayload(
        items=[
            AccessAuditItem(
                id=int(row.id),
                entity_type=str(row.entity_type),
                entity_id=str(row.entity_id),
                action=str(row.action),
                actor_id=str(row.actor_id),
                actor_role=str(row.actor_role),
                before_json=row.before_json,
                after_json=row.after_json,
                created_at=row.created_at.isoformat(),
            )
            for row in rows
        ]
    )
    return json_model_response(SuccessResponse[AccessAuditPayload](data=payload))
