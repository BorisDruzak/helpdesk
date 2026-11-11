"""Inventory is a display-only projection of an explicitly approved employee link."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from aiohttp import web
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.db.models import RegistryInventoryLink, RegistryPerson, RegistryPersonIdentity, UiUser
from app.repos.ui_users_repo import normalize_user_login
from auth.middleware import require_auth
from registry import inventory_directory as inventory
from registry.admin_operations_service import RegistryAdminOperationsService


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_person_id: UUID
    user_login: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class Removal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


def _reply(data: dict, status: int = 200) -> web.Response:
    payload = {"status": "success", "data": data} if status < 400 else {"status": "error", **data}
    return web.json_response(payload, status=status,
                             headers={"Cache-Control": "no-store"})


async def _is_owner(session, person_id: str, login: str) -> bool:
    person = await session.get(RegistryPerson, person_id)
    account = await session.get(UiUser, login)
    if (person is None or person.status != "active" or (person.metadata_json or {}).get("merged_into")
            or account is None or not account.is_active or account.actor_role != "user"):
        return False
    canonical = normalize_user_login(account.user_login)
    alias = await session.scalar(select(RegistryPersonIdentity).where(
        RegistryPersonIdentity.person_id == person_id,
        RegistryPersonIdentity.provider == "ui_login",
        RegistryPersonIdentity.normalized_identifier == canonical,
        RegistryPersonIdentity.verified.is_(True),
    ))
    return bool(alias is not None and normalize_user_login(alias.identifier) == canonical
                and not any((alias.metadata_json or {}).get(key) for key in ("collision_person_id", "merge_conflict")))


async def _audit(session, request, link, event_type: str, reason: str) -> None:
    auth = request["auth_context"]
    await RegistryAdminOperationsService(session).append_event(
        object_type="person", object_id=link.person_id, event_type=event_type,
        actor_id=auth.actor_id, actor_role=auth.actor_role, reason=reason, related_person_id=link.person_id,
        payload={"inventory_person_id": link.inventory_person_id, "approval_id": link.approval_id,
                 "user_login": link.user_login},
    )


@require_auth("admin")
async def confirm_inventory_link(request: web.Request) -> web.Response:
    if not inventory.inventory_enabled():
        return _reply({"error": "Inventory integration is disabled"}, 503)
    try:
        person_id = str(UUID(request.match_info["person_id"]))
        payload = Confirmation.model_validate(await request.json())
    except (ValueError, ValidationError):
        return _reply({"error": "Invalid inventory link confirmation"}, 400)
    try:
        profile = await inventory.fetch_person(payload.inventory_person_id)
    except inventory.InventoryPersonMissing:
        return _reply({"error": "Inventory employee not found"}, 404)
    except inventory.InventoryUnavailable:
        return _reply({"error": "Inventory unavailable"}, 503)

    async with get_session() as session:
        await session.scalar(select(RegistryPerson.person_id).where(RegistryPerson.person_id == person_id).with_for_update())
        if not await _is_owner(session, person_id, payload.user_login):
            return _reply({"error": "The account must have an active verified requester profile"}, 409)
        existing = await session.get(RegistryInventoryLink, person_id)
        if existing:
            if (existing.inventory_person_id, existing.user_login) != (str(payload.inventory_person_id), payload.user_login):
                return _reply({"error": "Remove the existing link explicitly before confirming another"}, 409)
            return _reply({"inventory_person_id": existing.inventory_person_id, "user_login": existing.user_login})
        row = RegistryInventoryLink(person_id=person_id, inventory_person_id=str(payload.inventory_person_id),
            user_login=payload.user_login, approval_id=str(uuid4()), snapshot=profile.model_dump(mode="json"),
            observed_at=profile.observed_at)
        session.add(row)
        try:
            await session.flush()
            await _audit(session, request, row, "inventory_link_confirmed", payload.reason)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return _reply({"error": "Inventory employee or account is already linked"}, 409)
    return _reply({"inventory_person_id": str(payload.inventory_person_id), "user_login": payload.user_login})


@require_auth("admin")
async def remove_inventory_link(request: web.Request) -> web.Response:
    try:
        person_id = str(UUID(request.match_info["person_id"]))
        payload = Removal.model_validate(await request.json())
    except (ValueError, ValidationError):
        return _reply({"error": "Invalid inventory link removal"}, 400)
    async with get_session() as session:
        await session.scalar(select(RegistryPerson.person_id).where(RegistryPerson.person_id == person_id).with_for_update())
        row = await session.scalar(select(RegistryInventoryLink).where(RegistryInventoryLink.person_id == person_id).with_for_update())
        if row is not None:
            await _audit(session, request, row, "inventory_link_removed", payload.reason)
            await session.delete(row)
            await session.commit()
    return _reply({"removed": True})


@require_auth("user")
async def read_inventory_devices(request: web.Request) -> web.Response:
    if not inventory.inventory_enabled():
        return _reply({"sync_state": "disabled", "assignments": []})
    login = request["auth_context"].actor_id
    query = select(RegistryInventoryLink).where(RegistryInventoryLink.user_login == login)
    async with get_session() as session:
        row = await session.scalar(query)
        if row is None or not await _is_owner(session, row.person_id, login):
            return _reply({"sync_state": "unlinked", "assignments": []})
        approval_id = row.approval_id
        person_id = UUID(row.inventory_person_id)

    profile = None
    missing = False
    try:
        profile = await inventory.fetch_person(person_id)
    except inventory.InventoryPersonMissing:
        missing = True
    except inventory.InventoryUnavailable:
        pass

    async with get_session() as session:
        current = await session.scalar(query.where(RegistryInventoryLink.approval_id == approval_id).with_for_update())
        if current is None or not await _is_owner(session, current.person_id, login):
            return _reply({"sync_state": "unlinked", "assignments": []})
        if missing:
            current.snapshot = None
            current.observed_at = None
            await session.commit()
            return _reply({"sync_state": "unavailable", "assignments": []})
        if profile is not None:
            if current.observed_at is None or profile.observed_at > current.observed_at:
                current.snapshot = profile.model_dump(mode="json")
                current.observed_at = profile.observed_at
                await session.commit()
            elif current.snapshot:
                profile = inventory.InventoryProfile.model_validate(current.snapshot)
            return _reply({"sync_state": "current", "observed_at": profile.observed_at.isoformat(),
                           "assignments": inventory.display_assignments(profile, stale=False)})
        if current.snapshot:
            previous = inventory.InventoryProfile.model_validate(current.snapshot)
            return _reply({"sync_state": "stale", "observed_at": previous.observed_at.isoformat(),
                           "assignments": inventory.display_assignments(previous, stale=True)})
        return _reply({"sync_state": "unavailable", "assignments": []})
