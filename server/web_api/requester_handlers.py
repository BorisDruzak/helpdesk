from __future__ import annotations

from typing import Any

from aiohttp import web

from app.api.serializers import ticket_to_dict
from app.db import get_session
from auth.middleware import require_auth
from requester.identity_service import RequesterIdentityResolver
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects


def _success(data: dict[str, Any]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _error(message: str, *, status: int = 400, error_code: str = "VALIDATION_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": error_code}, status=status)


def _clean(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


@require_auth("user")
async def handle_web_requester_bootstrap(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        payload = await RequesterIdentityResolver(session).build_bootstrap(actor_id=auth_context.actor_id)
    return _success(payload)


@require_auth("user")
async def handle_web_requester_devices(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        person = await resolver.resolve_person_for_web_user(auth_context.actor_id)
        devices = await resolver.list_allowed_devices(person.person_id if person else None)
    return _success({"devices": devices, "count": len(devices)})


@require_auth("user")
async def handle_web_requester_tickets(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    limit = int(request.query.get("limit") or 100)
    async with get_session() as session:
        tickets = await RequesterIdentityResolver(session).list_tickets(actor_id=auth_context.actor_id, limit=limit)
        payload = [ticket_to_dict(ticket, visibility="requester") for ticket in tickets]
    return _success({"tickets": payload, "count": len(payload)})


@require_auth("user")
async def handle_web_requester_ticket_detail(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    async with get_session() as session:
        ticket = await RequesterIdentityResolver(session).get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        payload = ticket_to_dict(ticket, visibility="requester")
    return _success({"ticket": payload})


@require_auth("user")
async def handle_web_requester_ticket_create(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    try:
        data = await request.json()
    except Exception:
        return _error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _error("JSON body must be an object", status=400)

    device_id = _clean(data.get("device_id"), max_length=80)
    if not device_id:
        return _error("device_id is required", status=400)
    description = _clean(data.get("description"), max_length=5000)
    if not description:
        return _error("description is required", status=400)
    title = _clean(data.get("title"), max_length=300) or "Requester workspace request"

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        try:
            person, binding = await resolver.require_owned_device(actor_id=auth_context.actor_id, device_id=device_id)
        except PermissionError as exc:
            return _error(str(exc), status=403, error_code="REQUESTER_DEVICE_FORBIDDEN")

        requester_profile = {
            "full_name": getattr(person, "full_name", None) or getattr(person, "display_name", None) or auth_context.actor_id,
            "email": getattr(person, "email", None) or auth_context.actor_id,
            "phone": getattr(person, "phone", None),
        }
        requester_account = {
            "account_mode": "confirmed_binding",
            "person_id": person.person_id if person else None,
            "binding_id": binding.binding_id,
            "display_name": getattr(person, "display_name", None),
            "full_name": getattr(person, "full_name", None),
            "email": getattr(person, "email", None),
            "validation": "web_requester_identity_resolved",
        }
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=auth_context.actor_id,
            title=title,
            description=description,
            user_display_name=_clean(data.get("user_display_name"), max_length=300)
            or getattr(person, "display_name", None)
            or auth_context.actor_id,
            requester_profile=requester_profile,
            normalized_priority=build_default_priority_payload(data),
            initial_message_text=description,
            initial_message_sender_role="user",
            initial_message_from="user",
            include_public_access=True,
            ticket_type=_clean(data.get("ticket_type"), max_length=64) or "request",
            extra_custom_fields={"request_context": "authenticated_requester_workspace"},
            requester_account=requester_account,
            state=request.app.get("state"),
        )
        await session.commit()
        ticket = ticket_to_dict(created["ticket"], visibility="requester")

    return _success(
        {
            "ticket": ticket,
            "ticket_id": created["ticket_id"],
            "public_access_code": created.get("public_access_code"),
            "public_access_url": ticket.get("public_access_url"),
        }
    )
