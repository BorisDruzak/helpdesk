"""Resolve an approver from reviewed Registry links, without role escalation."""
from __future__ import annotations

from typing import Any
from sqlalchemy import select

from access_control.service import can
from app.db.models import RegistryDepartment, RegistryPerson, RegistryPersonIdentity, UiUser
from auth.context import AuthContext, AuthType
from registry.organization_trust import field_trust, organization_value

ASSIGNED_APPROVAL_PERMISSION = "approval.decide.assigned"

REASONS = {
    "missing_requester": "Не определён действующий сотрудник заявителя.",
    "missing_manager": "Руководитель не указан; используйте резервный процесс политики.",
    "unconfirmed_manager": "Связь с руководителем не подтверждена или устарела.",
    "unconfirmed_department": "Подразделение заявителя не подтверждено или устарело.",
    "inactive_department": "Подразделение отсутствует или архивировано.",
    "inactive_manager": "Руководитель отсутствует или неактивен.",
    "missing_manager_identity": "У руководителя нет подтверждённой учётной записи.",
    "ambiguous_manager_identity": "У руководителя несколько учётных записей; требуется явное разрешение неоднозначности.",
    "inactive_manager_account": "Учётная запись руководителя неактивна.",
    "manager_permission_missing": "Руководителю не предоставлено предметное право согласования назначенных обращений.",
}


def unavailable(status: str) -> dict[str, Any]:
    return {"status": status, "actor_id": None, "message": REASONS[status]}


async def resolve_person_manager(session: Any, requester: Any, *, allow_department_fallback: bool = False) -> dict[str, Any]:
    if requester is None or getattr(requester, "status", "active") not in {"active", "self_reported"}:
        return unavailable("missing_requester")
    raw_personal = (requester.metadata_json or {}).get("manager_person_id")
    source = "person"
    if raw_personal:
        manager_id = organization_value(requester, "manager_person_id")
        record = field_trust(requester, "manager_person_id")
        if not manager_id or record.get("department_id", requester.department_id) != requester.department_id:
            return unavailable("unconfirmed_manager")
    elif allow_department_fallback:
        department_id = organization_value(requester, "department_id")
        if not department_id:
            return unavailable("unconfirmed_department")
        department = await session.get(RegistryDepartment, department_id)
        if department is None or department.status != "active":
            return unavailable("inactive_department")
        manager_id = organization_value(department, "manager_person_id")
        if not manager_id:
            return unavailable("unconfirmed_manager" if (department.metadata_json or {}).get("manager_person_id") else "missing_manager")
        source = "department"
    else:
        return unavailable("missing_manager")
    manager = await session.get(RegistryPerson, manager_id)
    if manager is None or manager.status not in {"active", "self_reported"}:
        return unavailable("inactive_manager")
    identities = (await session.scalars(select(RegistryPersonIdentity.normalized_identifier).where(
        RegistryPersonIdentity.person_id == manager.person_id, RegistryPersonIdentity.provider == "ui_login",
        RegistryPersonIdentity.verified.is_(True),
    ))).all()
    if len(identities) != 1:
        return unavailable("ambiguous_manager_identity" if identities else "missing_manager_identity")
    user = await session.get(UiUser, identities[0])
    if user is None or not user.is_active:
        return unavailable("inactive_manager_account")
    actor = AuthContext(actor_id=user.user_login, actor_role=user.actor_role, auth_type=AuthType.UI_TOKEN)
    assigned = await can(session, actor, ASSIGNED_APPROVAL_PERMISSION)
    if not assigned and not (user.actor_role in {"admin", "support", "auditor"} and await can(session, actor, "ticket.status.change")):
        return unavailable("manager_permission_missing")
    return {"status": "available", "actor_id": user.user_login, "actor_role": user.actor_role,
            "person_id": manager.person_id, "source": source, "assigned_only": assigned, "message": "Согласующий определён по подтверждённой связи Registry."}
