"""Short-lived invitations for one verified inventory identity."""

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import unicodedata
from uuid import uuid4

from sqlalchemy import delete, select, text

from app.db.models import RegistryDepartment, RegistryInventoryInvite, RegistryInventoryLink
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.inventory_directory import inventory_enabled

INVITE_UNAVAILABLE = "Приглашение недействительно или уже использовано. Обратитесь в поддержку за новым кодом."


class InventoryInviteError(ValueError):
    pass


def invite_digest(code: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
        raise InventoryInviteError(INVITE_UNAVAILABLE)
    return hashlib.sha256(code.encode()).hexdigest()


def _name_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


async def lock_inventory_identity(session, inventory_person_id: str) -> None:
    digest = hashlib.sha256(f"inventory-person:{inventory_person_id}".encode()).digest()
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {
        "key": int.from_bytes(digest[:8], "big", signed=True),
    })


async def _linked(session, inventory_person_id: str) -> bool:
    return (await session.scalar(select(RegistryInventoryLink.person_id).where(
        RegistryInventoryLink.inventory_person_id == inventory_person_id,
    ))) is not None


async def issue_inventory_invite(session, profile, department_id: str, actor_id: str, reason: str) -> dict:
    inventory_id = str(profile.inventory_person_id)
    await lock_inventory_identity(session, inventory_id)
    department = await session.get(RegistryDepartment, department_id)
    if department is None or department.status != "active":
        raise InventoryInviteError("Выберите действующий отдел Helpdesk.")
    if await _linked(session, inventory_id):
        raise InventoryInviteError("У сотрудника уже есть связь с аккаунтом Helpdesk.")
    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    row = await session.get(RegistryInventoryInvite, inventory_id)
    if row is None:
        row = RegistryInventoryInvite(inventory_person_id=inventory_id)
        session.add(row)
    row.code_digest = invite_digest(code)
    row.full_name = profile.full_name
    row.inventory_department = profile.department
    row.department_id = department_id
    row.issued_by = actor_id
    row.expires_at = expires_at
    row.consumed_at = None
    await RegistryAdminOperationsService(session).append_event(
        object_type="inventory_invitation", object_id=inventory_id, event_type="inventory_invitation_issued",
        actor_id=actor_id, actor_role="admin", reason=reason, payload={"department_id": department_id},
    )
    return {"code": code, "expires_at": expires_at.isoformat(), "full_name": row.full_name}


async def invalidate_pending_inventory_invite(session, inventory_person_id: str) -> bool:
    result = await session.execute(delete(RegistryInventoryInvite).where(
        RegistryInventoryInvite.inventory_person_id == inventory_person_id,
        RegistryInventoryInvite.consumed_at.is_(None),
    ))
    return bool(result.rowcount)


async def read_inventory_invite(session, digest: str, *, lock: bool = False) -> RegistryInventoryInvite:
    if not inventory_enabled():
        raise InventoryInviteError(INVITE_UNAVAILABLE)
    query = select(RegistryInventoryInvite).where(RegistryInventoryInvite.code_digest == digest)
    row = await session.scalar(query)
    if row is None:
        raise InventoryInviteError(INVITE_UNAVAILABLE)
    if lock:
        await lock_inventory_identity(session, row.inventory_person_id)
        row = await session.scalar(query.execution_options(populate_existing=True))
    if row is None or row.consumed_at or row.expires_at <= datetime.now(timezone.utc):
        raise InventoryInviteError(INVITE_UNAVAILABLE)
    department = await session.get(RegistryDepartment, row.department_id)
    if department is None or department.status != "active" or await _linked(session, row.inventory_person_id):
        raise InventoryInviteError(INVITE_UNAVAILABLE)
    return row


async def validate_inventory_invite(session, digest: str, profile: dict) -> RegistryInventoryInvite:
    row = await read_inventory_invite(session, digest, lock=True)
    if _name_key(profile["full_name"]) != _name_key(row.full_name) or profile.get("department_id") != row.department_id:
        raise InventoryInviteError("Укажите ФИО и отдел из приглашения.")
    return row


async def consume_inventory_invite(session, row: RegistryInventoryInvite, person_id: str, login: str) -> None:
    approval_id = str(uuid4())
    session.add(RegistryInventoryLink(
        person_id=person_id, inventory_person_id=row.inventory_person_id,
        user_login=login, approval_id=approval_id,
    ))
    row.consumed_at = datetime.now(timezone.utc)
    await RegistryAdminOperationsService(session).append_event(
        object_type="person", object_id=person_id, event_type="inventory_link_confirmed",
        actor_id=row.issued_by, actor_role="admin", related_person_id=person_id,
        payload={"inventory_person_id": row.inventory_person_id, "approval_id": approval_id,
                 "user_login": login, "confirmation": "invitation"},
    )
