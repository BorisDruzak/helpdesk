from __future__ import annotations

from aiohttp import web
from loguru import logger

from access_control.catalog import CATALOG_VERSION, ROLE_LABELS, get_role_label, get_role_permission_codes
from access_control.service import grouped_permissions, resolve_effective_access
from app.db import get_session
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ui_users_repo import UiUsersRepo
from auth.middleware import require_auth
from web_api.dto.access_control import (
    AccessCatalogPayload,
    AccessEffectivePayload,
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


async def _load_queue_memberships(actor_id: str) -> list[AccessQueueMembershipItem]:
    if not actor_id:
        return []
    memberships: list[AccessQueueMembershipItem] = []
    async with get_session() as session:
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


async def _summary_payload() -> AccessSummaryPayload:
    users: list[AccessUserItem] = []
    queues_payload: list[AccessQueueItem] = []
    notes = [
        "Access groups are planned as the next RBAC slice; current effective access is role + direct queue membership.",
    ]
    try:
        async with get_session() as session:
            users_repo = UiUsersRepo(session)
            queue_repo = TicketAdminConfigRepo(session)
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

            users = [
                AccessUserItem(
                    user_login=str(user.user_login),
                    actor_role=str(user.actor_role),
                    role_label=get_role_label(user.actor_role),
                    is_active=bool(user.is_active),
                    groups=[],
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
        access_groups=[],
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
    if not actor_role and actor_id:
        try:
            async with get_session() as session:
                user = await UiUsersRepo(session).get_by_login(actor_id)
                if user is not None:
                    actor_role = str(user.actor_role)
        except Exception as exc:
            logger.warning(f"[web_admin_access_effective] could not resolve actor role: actor_id={actor_id} error={exc}")
    if not actor_role:
        actor_role = "user"

    queues: list[AccessQueueMembershipItem] = []
    try:
        queues = await _load_queue_memberships(actor_id)
    except Exception as exc:
        logger.warning(f"[web_admin_access_effective] queue memberships unavailable: actor_id={actor_id} error={exc}")

    effective = resolve_effective_access(
        actor_id=actor_id,
        actor_role=actor_role,
        queues=[queue.model_dump(mode="json") for queue in queues],
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
