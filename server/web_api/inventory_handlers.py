"""Requester inventory for explicitly approved employee links."""

from __future__ import annotations

import os
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from aiohttp import web
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import config as config_module
from app.db import get_session
from app.db.models import RegistryInventoryLink, RegistryPerson
from auth.inventory_invitation import (
    INVITE_UNAVAILABLE, InventoryInviteError, invalidate_pending_inventory_invite, invite_digest, issue_inventory_invite,
    lock_inventory_identity, read_inventory_invite,
)
from auth.middleware import _same_origin_error, require_auth
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from registry import inventory_directory as inventory
from registry.admin_operations_service import RegistryAdminOperationsService
from registry.inventory_device_binding import (
    InventoryDeviceBindingService, fresh_inventory_observation, inventory_ticket_targets,
)
from registry.inventory_binding_refresh import inventory_link_owner, sync_managed_inventory
from tickets.handlers import _get_ticket_or_response
from tickets.ticket_context import requester_reference_snapshot_from_record


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
        await lock_inventory_identity(session, str(payload.inventory_person_id))
        await session.scalar(select(RegistryPerson.person_id).where(RegistryPerson.person_id == person_id).with_for_update())
        if not await inventory_link_owner(session, person_id, payload.user_login):
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
            await invalidate_pending_inventory_invite(session, row.inventory_person_id)
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
            await InventoryDeviceBindingService(session, None).revoke_all(person_id, "inventory_link_removed")
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
        if row is None or not await inventory_link_owner(session, row.person_id, login):
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
        if current is None or not await inventory_link_owner(session, current.person_id, login):
            return _reply({"sync_state": "unlinked", "assignments": []})
        binding_results = await sync_managed_inventory(session, current, profile, missing=missing)
        if missing:
            current.snapshot = None
            current.observed_at = None
            await session.commit()
            return _reply({"sync_state": "unavailable", "assignments": []})
        if profile is not None and fresh_inventory_observation(profile.observed_at):
            if not fresh_inventory_observation(current.observed_at) or profile.observed_at > current.observed_at:
                current.snapshot = profile.model_dump(mode="json")
                current.observed_at = profile.observed_at
            elif current.snapshot:
                profile = inventory.InventoryProfile.model_validate(current.snapshot)
            assignments = inventory.display_assignments(profile, stale=False)
            await session.flush()
            ticket_targets = await inventory_ticket_targets(session, current.person_id, profile)
            for assignment in assignments:
                assignment_id = assignment["assignment_id"]
                if result := binding_results.get(assignment_id):
                    assignment["helpdesk_binding_state"] = result["state"]
                if assignment_id in ticket_targets and assignment.get("helpdesk_binding_state") != "unavailable":
                    assignment["request_device_id"] = ticket_targets[assignment_id]
            return _reply({"sync_state": "current", "observed_at": profile.observed_at.isoformat(),
                           "assignments": assignments})
        if current.snapshot:
            previous = inventory.InventoryProfile.model_validate(current.snapshot)
            return _reply({"sync_state": "stale", "observed_at": previous.observed_at.isoformat(),
                           "assignments": inventory.display_assignments(previous, stale=True)})
        return _reply({"sync_state": "unavailable", "assignments": []})



def _inventory_web_origin() -> str | None:
    configured = (os.getenv("HELPDESK_INVENTORY_WEB_URL")
                  or os.getenv("HELPDESK_INVENTORY_BASE_URL", "")).strip()
    try:
        origin = urlsplit(configured)
        if (origin.scheme != "https" or not origin.hostname or origin.username is not None
                or origin.path not in {"", "/"} or origin.query or origin.fragment
                or "\\" in origin.netloc or any(ch.isspace() for ch in origin.netloc)):
            return None
    except ValueError:
        return None
    return f"https://{origin.netloc}"


async def _read_operator_inventory(person_id: str | None, *, ticket_endpoint_ref: str | None = None) -> web.Response:
    if not inventory.inventory_enabled():
        return _reply({"sync_state": "disabled", "assignments": []})
    if person_id is None:
        return _reply({"sync_state": "unlinked", "assignments": []})
    async with get_session() as session:
        link = await session.get(RegistryInventoryLink, person_id)
        if link is None or not await inventory_link_owner(session, person_id, link.user_login):
            return _reply({"sync_state": "unlinked", "assignments": []})
        inventory_id = UUID(link.inventory_person_id)
        approval_id = link.approval_id

    profile = None
    try:
        profile = await inventory.fetch_person(inventory_id)
    except inventory.InventoryPersonMissing:
        return _reply({"sync_state": "unavailable", "assignments": []})
    except inventory.InventoryUnavailable:
        pass

    async with get_session() as session:
        link = await session.get(RegistryInventoryLink, person_id)
        if (link is None or link.approval_id != approval_id
                or not await inventory_link_owner(session, person_id, link.user_login)):
            return _reply({"sync_state": "unlinked", "assignments": []})
        if profile is not None and str(profile.inventory_person_id) != link.inventory_person_id:
            return _reply({"sync_state": "unavailable", "assignments": []})
        stale = profile is None or not fresh_inventory_observation(profile.observed_at)
        if link.snapshot and (stale or (link.observed_at and link.observed_at > profile.observed_at)):
            try:
                profile = inventory.InventoryProfile.model_validate(link.snapshot)
            except ValidationError:
                return _reply({"sync_state": "unavailable", "assignments": []})
            stale = stale or not fresh_inventory_observation(profile.observed_at)
        elif stale:
            return _reply({"sync_state": "unavailable", "assignments": []})

    origin = _inventory_web_origin()
    assignments = []
    for assignment in profile.assignments:
        asset_id = str(assignment.inventory_asset_id)
        assignments.append({
            "assignment_id": str(assignment.assignment_id),
            "name": assignment.name,
            "inventory_number": assignment.inventory_number,
            "os_name": assignment.os_name,
            "role": assignment.role,
            "endpoint_binding_state": assignment.endpoint_binding_state,
            "endpoint_status": "unknown" if stale else assignment.endpoint_status,
            "agent_version": assignment.agent_version,
            "last_seen_at": assignment.last_seen_at.isoformat() if assignment.last_seen_at else None,
            "diagnostic_target": bool(not stale and ticket_endpoint_ref and assignment.endpoint_device_id
                                      and ticket_endpoint_ref == str(assignment.endpoint_device_id)),
            "inventory_url": f"{origin}/inventory/assets/{asset_id}" if origin else None,
            "workstation_url": f"{origin}/workstations?inventory_asset_id={asset_id}" if origin else None,
        })
    return _reply({"sync_state": "stale" if stale else "current", "assignments": assignments})


@require_auth("admin")
async def read_registry_inventory_devices(request: web.Request) -> web.Response:
    try:
        person_id = str(UUID(request.match_info["person_id"]))
    except ValueError:
        return _reply({"error": "Invalid registry person"}, 400)
    return await _read_operator_inventory(person_id)


@require_auth("admin", "support")
async def read_ticket_inventory_devices(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _repo, _auth = await _get_ticket_or_response(request, session, write=False)
        if error is not None:
            return error
        try:
            requester, _snapshot = requester_reference_snapshot_from_record(ticket)
            person_id = requester.external_id if requester is not None else ticket.requester_person_id
        except (TypeError, ValueError):
            person_id = None
        endpoint_ref = ticket.endpoint_device_ref
    return await _read_operator_inventory(person_id, ticket_endpoint_ref=endpoint_ref)

class InvitationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_person_id: UUID
    department_id: UUID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class InvitationLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(min_length=43, max_length=43)]


@require_auth("admin")
async def create_inventory_invitation(request: web.Request) -> web.Response:
    if not config_module.WEB_SELF_REGISTRATION_ENABLED or not inventory.inventory_enabled():
        return _reply({"error": "Inventory integration is disabled"}, 503)
    try:
        payload = InvitationIssue.model_validate(await request.json())
    except (ValueError, ValidationError):
        return _reply({"error": "Проверьте сотрудника, отдел и причину выдачи."}, 400)
    try:
        profile = await inventory.fetch_person(payload.inventory_person_id)
    except inventory.InventoryPersonMissing:
        return _reply({"error": "Сотрудник не найден в инвентаризации."}, 404)
    except inventory.InventoryUnavailable:
        return _reply({"error": "Инвентаризация недоступна."}, 503)
    from auth.requester_registration import clean_registration_name, registration_login_base
    parts = profile.full_name.split(maxsplit=2)
    try:
        if len(parts) < 2 or len(profile.full_name) > 240:
            raise ValueError("Invalid name")
        registration_login_base(parts[1], parts[0])
        if len(parts) == 3:
            clean_registration_name(parts[2], optional=True)
    except ValueError:
        return _reply({"error": "ФИО в инвентаризации должно подходить для регистрации. Проверьте карточку сотрудника."}, 409)
    try:
        async with get_session() as session:
            result = await issue_inventory_invite(
                session, profile, str(payload.department_id), request["auth_context"].actor_id, payload.reason,
            )
    except InventoryInviteError as exc:
        return _reply({"error": str(exc)}, 409)
    return _reply(result, 201)


@require_auth("admin")
async def revoke_inventory_invitation(request: web.Request) -> web.Response:
    try:
        inventory_id = str(UUID(request.match_info["inventory_person_id"]))
        payload = Removal.model_validate(await request.json())
    except (ValueError, ValidationError):
        return _reply({"error": "Проверьте сотрудника и причину отзыва."}, 400)
    async with get_session() as session:
        await lock_inventory_identity(session, inventory_id)
        revoked = await invalidate_pending_inventory_invite(session, inventory_id)
        if revoked:
            await RegistryAdminOperationsService(session).append_event(
                object_type="inventory_invitation", object_id=inventory_id, event_type="inventory_invitation_revoked",
                actor_id=request["auth_context"].actor_id, actor_role="admin", reason=payload.reason,
            )
    return _reply({"revoked": revoked})


async def preview_inventory_invitation(request: web.Request) -> web.Response:
    if not config_module.WEB_SELF_REGISTRATION_ENABLED or not inventory.inventory_enabled():
        return _reply({"error": "Регистрация по приглашению недоступна."}, 403)
    if _same_origin_error(request):
        return _reply({"error": "Откройте регистрацию на странице Helpdesk."}, 403)
    if not check_rate_limit("requester_inventory_invitation", client_ip(request), limit=10, window_seconds=60):
        return rate_limited_response()
    try:
        payload = InvitationLookup.model_validate(await request.json())
        digest = invite_digest(payload.code)
        async with get_session() as session:
            row = await read_inventory_invite(session, digest)
            result = {"full_name": row.full_name, "department": row.inventory_department,
                      "department_id": row.department_id}
    except (ValueError, ValidationError):
        return _reply({"error": INVITE_UNAVAILABLE}, 409)
    return _reply(result)
