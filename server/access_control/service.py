from __future__ import annotations

from dataclasses import dataclass, field

from access_control.catalog import (
    CATALOG_VERSION,
    get_available_workspaces,
    get_default_workspace,
    get_permission_catalog,
    get_role_label,
    get_role_permission_codes,
    normalize_role,
)
from app.repos.access_control_repo import AccessControlRepo


@dataclass(frozen=True, slots=True)
class EffectiveAccess:
    actor_id: str
    actor_role: str
    role_label: str
    permissions: list[str]
    workspaces: list[str]
    groups: list[str] = field(default_factory=list)
    queues: list[dict] = field(default_factory=list)


def resolve_effective_access(
    *,
    actor_id: str | None,
    actor_role: str | None,
    queues: list[dict] | None = None,
    groups: list[str] | None = None,
    group_permissions: list[str] | None = None,
) -> EffectiveAccess:
    role = normalize_role(actor_role)
    permissions = sorted(set(get_role_permission_codes(role)) | set(group_permissions or []))
    return EffectiveAccess(
        actor_id=str(actor_id or "").strip(),
        actor_role=role,
        role_label=get_role_label(role),
        permissions=permissions,
        workspaces=_workspaces_from_permissions(permissions),
        groups=list(groups or []),
        queues=list(queues or []),
    )


def resolve_session_access(actor_role: str | None) -> tuple[str | None, list[str], list[str], str]:
    role = normalize_role(actor_role)
    return (
        get_default_workspace(role),
        get_available_workspaces(role),
        get_role_permission_codes(role),
        CATALOG_VERSION,
    )


def can_role(actor_role: str | None, permission_code: str) -> bool:
    return permission_code in set(get_role_permission_codes(actor_role))


async def can(session, auth_context, permission_code: str) -> bool:
    actor_role = getattr(auth_context, "actor_role", None)
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    permissions = set(get_role_permission_codes(actor_role))
    if actor_id:
        permissions.update(await AccessControlRepo(session).get_actor_group_permissions(actor_id))
    return permission_code in permissions


def _workspaces_from_permissions(permissions: list[str]) -> list[str]:
    permission_set = set(permissions)
    workspaces: list[str] = []
    if "workspace.admin.view" in permission_set:
        workspaces.append("admin")
    if "workspace.support.view" in permission_set:
        workspaces.append("support")
    if "workspace.requester.view" in permission_set:
        workspaces.append("requester")
    return workspaces


def grouped_permissions() -> list[dict]:
    groups: dict[str, dict] = {}
    for item in get_permission_catalog():
        group = groups.setdefault(
            item.group,
            {
                "code": item.group,
                "label": item.group_label,
                "permissions": [],
            },
        )
        group["permissions"].append(
            {
                "code": item.code,
                "label": item.label,
                "description": item.description,
                "risk": item.risk,
            }
        )
    return list(groups.values())
