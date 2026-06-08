from __future__ import annotations

import uuid
from typing import Any

from aiohttp import web

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import require_auth
from quality.feedback_service import TicketFeedbackService
from quality.reopen_service import TicketReopenService
from requester.identity_service import RequesterIdentityResolver
from tickets.handlers import (
    _event_visible_to_requester,
    _push_ticket_event,
    _resolution_confirmation_pending,
    _serialize_event_for_requester,
    _serialize_message_for_requester,
    _store_resolution_confirmation_state,
)
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects
from tickets.statuses import enrich_chat_payload_with_requester_name
from tickets.workflow_service import TicketWorkflowService


def _success(data: dict[str, Any]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _error(message: str, *, status: int = 400, error_code: str = "VALIDATION_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": error_code}, status=status)


def _clean(value: object, *, max_length: int = 500) -> str:
    return str(value or "").strip()[:max_length]


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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
        repo = TicketEventsRepo(session)
        raw_events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=200)
        visible_events = [event for event in raw_events if _event_visible_to_requester(event)]
        messages = [event for event in visible_events if getattr(event, "event_type", None) == "chat_message"]
        payload = ticket_to_dict(ticket, visibility="requester")
    return _success(
        {
            "ticket": payload,
            "messages": [_serialize_message_for_requester(event, ticket=ticket) for event in messages],
            "events": [_serialize_event_for_requester(event, ticket=ticket) for event in visible_events],
        }
    )


@require_auth("user")
async def handle_web_requester_ticket_message(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    try:
        data = await request.json()
    except Exception:
        return _error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _error("JSON body must be an object", status=400)

    text = _clean(data.get("text"), max_length=5000)
    if not text:
        return _error("text is required", status=400)

    message_id = _clean(data.get("message_id"), max_length=120) or str(uuid.uuid4())
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        payload: dict[str, Any] = {
            "message_id": message_id,
            "sender_role": "user",
            "sender_display_name": auth_context.actor_id,
            "from": "user",
            "text": text,
            "visibility": "public",
            "requester_person_id": getattr(ticket, "requester_person_id", None),
            "requester_binding_id": getattr(ticket, "requester_binding_id", None),
            "requester_account_session_id": getattr(ticket, "requester_account_session_id", None),
            "requester_account_mode": getattr(ticket, "requester_account_mode", None),
        }
        if metadata:
            payload["metadata"] = metadata
        payload = enrich_chat_payload_with_requester_name(ticket, payload)

        repo = TicketEventsRepo(session)
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload=payload,
            trace_id=str(uuid.uuid4()),
            event_id=message_id,
        )

        status_result = None
        status_payload: dict[str, Any] | None = None
        if getattr(ticket, "status", None) == "waiting_on_user":
            workflow = TicketWorkflowService(session, repo)
            transition = await workflow.apply_triggered_transition(
                ticket_id=ticket.ticket_id,
                trigger="requester_replied",
                actor_id="system",
                actor_role="system",
                reason="requester_reply",
                source="requester_reply",
                trigger_actor_id=auth_context.actor_id,
                trigger_actor_role=auth_context.actor_role,
                fallback_status="assigned",
            )
            status_result = transition.get("event_result")
            status_payload = transition.get("event_payload") or {}

        await session.commit()

    await _push_ticket_event(request, ticket_id, result, "chat_message", payload)
    if status_result:
        await _push_ticket_event(request, ticket_id, status_result, "status_changed", status_payload or {})
    return _success({"message_id": message_id, "event_id": result[0] if result else None})


@require_auth("user")
async def handle_web_requester_ticket_close(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        repo = TicketEventsRepo(session)
        if getattr(ticket, "status", None) == "closed":
            return _success({"ticket": ticket_to_dict(ticket, visibility="requester")})
        if getattr(ticket, "status", None) != "resolved":
            return _error(
                "ticket can be closed only from resolved",
                status=400,
                error_code="INVALID_TICKET_STATUS",
            )

        workflow = TicketWorkflowService(session, repo)
        try:
            transition = await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=ticket.status,
                to_status="closed",
                actor_id=auth_context.actor_id,
                actor_role="requester",
                reason=_clean(data.get("reason"), max_length=200) or "requester_confirmed_resolution",
                source="requester_workspace",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="WORKFLOW_POLICY_ERROR")

        ticket = await repo.get_ticket(ticket.ticket_id)
        if ticket is not None and _resolution_confirmation_pending(ticket):
            ticket = await _store_resolution_confirmation_state(
                repo,
                ticket,
                pending=False,
                responded_option_id="confirm",
            )
        await session.commit()

    await _push_ticket_event(
        request,
        ticket_id,
        transition.get("event_result"),
        "status_changed",
        transition.get("event_payload") or {},
    )
    return _success({"ticket": ticket_to_dict(ticket, visibility="requester")})


@require_auth("user")
async def handle_web_requester_ticket_feedback(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        metadata["web_actor_id"] = auth_context.actor_id
        data["metadata"] = metadata
        data["ticket_id"] = ticket.ticket_id
        data["source_surface"] = "requester_portal"
        data.pop("visibility", None)
        try:
            result = await TicketFeedbackService(session).submit_feedback(
                data,
                actor_id=str(getattr(ticket, "requester_id", None) or auth_context.actor_id),
                actor_role="requester",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="QUALITY_FEEDBACK_ERROR")
        await session.commit()

    return _success(
        {
            "ok": True,
            "feedback_id": result["feedback_id"],
            "message": result.get("message"),
            "reopen_available": bool(result.get("reopen_available")),
        }
    )


@require_auth("user")
async def handle_web_requester_ticket_reopen(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = _clean(request.match_info.get("ticket_id"), max_length=80)
    data = await _json_body(request)

    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")

        try:
            result = await TicketReopenService(session).reopen_ticket(
                ticket.ticket_id,
                reason_code=str(data.get("reason_code") or ""),
                reason_comment=data.get("reason_comment"),
                linked_feedback_id=data.get("linked_feedback_id"),
                linked_knowledge_item_id=data.get("linked_knowledge_item_id"),
                actor_id=str(getattr(ticket, "requester_id", None) or auth_context.actor_id),
                actor_role="requester",
            )
        except ValueError as exc:
            return _error(str(exc), status=400, error_code="QUALITY_REOPEN_ERROR")
        await session.commit()

    return _success(
        {
            "ok": True,
            "ticket_id": result["ticket_id"],
            "ticket_status": result["status"],
            "reopen_id": result["reopen_id"],
            "linked_feedback_id": result.get("linked_feedback_id"),
        }
    )


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
