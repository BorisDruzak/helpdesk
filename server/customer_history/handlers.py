from __future__ import annotations

from typing import Any

from aiohttp import web

from app.db import get_session
from auth.middleware import require_auth
from domain_ports.registry_contracts import ActorRef, RegistryReadActor, RequesterRef
from requester.identity_service import RequesterIdentityResolver
from tickets.handlers import _get_ticket_or_response

from .context_builder import CustomerHistoryContextBuilder
from .projection_service import CustomerHistoryProjectionService
from .retention import DEFAULT_CONTEXT_PACK_LIMIT, DEFAULT_HISTORY_LIMIT, MAX_CONTEXT_PACK_LIMIT, MAX_HISTORY_LIMIT


def _success(data: dict[str, Any]) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def _error(message: str, *, status: int = 400, error_code: str = "CUSTOMER_HISTORY_ERROR") -> web.Response:
    return web.json_response({"status": "error", "error": message, "error_code": error_code}, status=status)


def _limit(request: web.Request, *, default: int, maximum: int) -> int:
    try:
        return max(1, min(int(request.query.get("limit") or default), maximum))
    except (TypeError, ValueError):
        return default


def _window_filters(request: web.Request) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    since = str(request.query.get("since") or "").strip()
    if since:
        filters["since"] = since
    window_days = str(request.query.get("window_days") or "").strip()
    if window_days:
        try:
            filters["window_days"] = max(1, min(int(window_days), 3650))
        except ValueError:
            pass
    return filters


def _registry_actor_from_verified_auth(
    auth_context: Any,
    *,
    requester_ref: str | None = None,
) -> RegistryReadActor | None:
    """Translate middleware-authenticated values; never read actor data from HTTP input."""

    raw_role = str(getattr(auth_context, "actor_role", "") or "").strip().lower()
    role = "user" if raw_role in {"user", "requester"} else raw_role
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    if role not in {"admin", "support", "user"} or not actor_id:
        return None
    try:
        requester = RequesterRef(external_id=requester_ref) if requester_ref else None
        if role == "user" and requester is None:
            return None
        return RegistryReadActor(actor=ActorRef(external_id=actor_id), role=role, requester=requester)
    except ValueError:
        return None


@require_auth("admin", "support")
async def handle_web_support_person_history(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    person_id = str(request.match_info.get("person_id") or "").strip()
    if not person_id:
        return _error("person not found", status=404, error_code="NOT_FOUND")
    async with get_session() as session:
        payload = await CustomerHistoryProjectionService(session).history_for_person(
            person_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role},
            registry_actor=_registry_actor_from_verified_auth(auth_context),
            limit=_limit(request, default=DEFAULT_HISTORY_LIMIT, maximum=MAX_HISTORY_LIMIT),
            **_window_filters(request),
        )
    return _success(payload)


@require_auth("admin", "support")
async def handle_web_support_ticket_history(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        payload = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket.ticket_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role},
            limit=_limit(request, default=DEFAULT_HISTORY_LIMIT, maximum=MAX_HISTORY_LIMIT),
            **_window_filters(request),
        )
    return _success(payload)


@require_auth("admin", "support")
async def handle_web_support_ticket_context_pack(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        payload = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            ticket.ticket_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role},
            mode=str(request.query.get("mode") or "support_context_pack"),
            limit=_limit(request, default=DEFAULT_CONTEXT_PACK_LIMIT, maximum=MAX_CONTEXT_PACK_LIMIT),
            registry_actor=_registry_actor_from_verified_auth(auth_context),
        )
    return _success(payload)


@require_auth("admin", "support")
async def handle_web_support_ticket_llm_context_preview(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        payload = await CustomerHistoryContextBuilder(session).build_ticket_context_pack(
            ticket.ticket_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role},
            mode="llm_preview",
            limit=_limit(request, default=DEFAULT_CONTEXT_PACK_LIMIT, maximum=MAX_CONTEXT_PACK_LIMIT),
            registry_actor=_registry_actor_from_verified_auth(auth_context),
        )
    return _success(payload)


@require_auth("user")
async def handle_web_requester_history(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        person = await RequesterIdentityResolver(session).resolve_person_for_web_user(auth_context.actor_id)
        if person is None:
            return _error("requester profile not found", status=403, error_code="REQUESTER_IDENTITY_REQUIRED")
        payload = await CustomerHistoryProjectionService(session).history_for_person(
            person.person_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": "requester"},
            registry_actor=_registry_actor_from_verified_auth(
                auth_context,
                requester_ref=person.person_id,
            ),
            limit=_limit(request, default=DEFAULT_HISTORY_LIMIT, maximum=MAX_HISTORY_LIMIT),
            **_window_filters(request),
        )
    return _success(payload)


@require_auth("user")
async def handle_web_requester_ticket_history(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    ticket_id = str(request.match_info.get("ticket_id") or "").strip()
    async with get_session() as session:
        resolver = RequesterIdentityResolver(session)
        ticket = await resolver.get_ticket(actor_id=auth_context.actor_id, ticket_id=ticket_id)
        if ticket is None:
            return _error("ticket not found", status=404, error_code="NOT_FOUND")
        payload = await CustomerHistoryProjectionService(session).history_for_ticket(
            ticket.ticket_id,
            actor_context={"actor_id": auth_context.actor_id, "actor_role": "requester"},
            limit=_limit(request, default=DEFAULT_HISTORY_LIMIT, maximum=MAX_HISTORY_LIMIT),
            **_window_filters(request),
        )
    return _success(payload)


@require_auth("admin")
async def handle_web_admin_history_search(request: web.Request) -> web.Response:
    auth_context = request["auth_context"]
    async with get_session() as session:
        payload = await CustomerHistoryProjectionService(session).search_history(
            str(request.query.get("q") or ""),
            actor_context={"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role},
            limit=_limit(request, default=DEFAULT_HISTORY_LIMIT, maximum=MAX_HISTORY_LIMIT),
        )
    return _success(payload)
