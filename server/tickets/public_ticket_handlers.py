"""Public requester ticket endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from aiohttp import web
from loguru import logger

from auth.service import AuthService
from config import PUBLIC_TICKET_SESSION_MINUTES
from tickets.public_access import (
    build_public_access_message,
    generate_public_access_code,
    make_public_requester_id,
    mark_public_ticket_unbound,
    set_public_access_code,
    verify_public_access_code,
)
from utils import new_ticket_id

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.repos import DevicesRepo, TicketEventsRepo, TicketFormPacksRepo
from tickets.assignment_service import (
    MAX_ACTIVE_TICKETS_PER_OPERATOR,
    TicketAssignmentError,
    TicketAssignmentService,
)
from tickets.ola_service import start_ola_for_ticket
from tickets.routing_service import TicketRoutingService
from tickets.sla_service import TicketSlaService
from tickets.statuses import (
    enrich_chat_payload_with_requester_name,
    merge_requester_custom_fields,
    normalize_requester_profile,
    normalize_ticket_priority_inputs,
)
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    build_form_custom_fields,
    resolve_ticket_form_pack,
    validate_form_submission,
)
from playbooks.form_triggers import start_ticket_created_playbooks
from tickets.workflow_service import TicketWorkflowService


def _validation_error(details: Dict[str, Any]) -> web.Response:
    return web.json_response(
        {"status": "error", "error": "validation_error", "details": details},
        status=400,
    )


async def _create_public_access_event(ticket_repo: Any, ticket: Any, code: str) -> None:
    payload = build_public_access_message(code, getattr(ticket, "ticket_id", None))
    await ticket_repo.add_event(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        agent_seq=None,
        event_type="chat_message",
        payload=payload,
        trace_id=str(uuid.uuid4()),
        event_id=payload["message_id"],
    )


async def handle_public_ticket_create(request: web.Request) -> web.Response:
    """POST /public_api/tickets/create - create requester ticket without prior auth."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid JSON"}, status=400)

    description = str(data.get("description") or "").strip()
    title = str(data.get("title") or "").strip() or "Заявка с веб-страницы"
    user_display_name = str(data.get("user_display_name") or "").strip()
    urgency_input = data.get("urgency")
    importance_input = data.get("importance")
    urgency_reason_input = data.get("urgency_reason")
    importance_reason_input = data.get("importance_reason")
    form_key = str(data.get("form_key") or "").strip()
    pack_key = str(data.get("form_pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = str(data.get("form_pack_version") or "").strip() or None
    form_payload = data.get("form_payload")

    validation_errors: Dict[str, Any] = {}
    if not description:
        validation_errors["description"] = "Description is required and cannot be empty"
    if not user_display_name:
        validation_errors["user_display_name"] = "User display name is required and cannot be empty"

    try:
        requester_profile = normalize_requester_profile(data.get("requester_profile"))
    except ValueError as exc:
        validation_errors["requester_profile"] = str(exc)
        requester_profile = {"full_name": None, "building": None, "room": None, "phone": None}

    normalized_priority = None
    if urgency_input is None:
        validation_errors["urgency"] = "urgency is required"
    if importance_input is None:
        validation_errors["importance"] = "importance is required"
    if not validation_errors:
        try:
            normalized_priority = normalize_ticket_priority_inputs(
                urgency_input,
                importance_input,
                urgency_reason_input,
                importance_reason_input,
            )
        except ValueError as exc:
            validation_errors["priority"] = str(exc)
    if validation_errors:
        return _validation_error(validation_errors)

    ticket_id = new_ticket_id()
    placeholder_device_id = ticket_id
    requester_id = make_public_requester_id(ticket_id)
    initial_message_id = str(uuid.uuid4())
    public_access_code = generate_public_access_code()
    public_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=PUBLIC_TICKET_SESSION_MINUTES)

    try:
        async with get_session() as db_session:
            ticket_repo = TicketEventsRepo(db_session)
            extra_custom_fields: dict[str, Any] | None = None
            if form_key:
                try:
                    form_pack = await resolve_ticket_form_pack(
                        TicketFormPacksRepo(db_session),
                        pack_key=pack_key,
                        version=pack_version,
                    )
                    validated_submission = validate_form_submission(
                        form_pack,
                        form_key=form_key,
                        raw_values=form_payload or {},
                    )
                    extra_custom_fields = build_form_custom_fields(validated_submission)
                except ValueError as exc:
                    details = exc.args[0] if exc.args else "invalid form payload"
                    return _validation_error({"form_payload": details})
            ticket = await ticket_repo.create_ticket(
                ticket_id=ticket_id,
                device_id=placeholder_device_id,
                title=title,
                description=description,
                status="new",
                requester_id=requester_id,
            )
            custom_fields = merge_requester_custom_fields(
                getattr(ticket, "custom_fields", None),
                user_display_name=user_display_name,
                requester_profile=requester_profile,
                priority_class=(normalized_priority or {}).get("priority_class", "P3"),
            )
            if extra_custom_fields:
                custom_fields.update(extra_custom_fields)
            custom_fields = set_public_access_code(custom_fields, public_access_code)
            custom_fields = mark_public_ticket_unbound(custom_fields, True)
            await ticket_repo.update_ticket(
                ticket_id,
                urgency=(normalized_priority or {}).get("urgency", 0),
                importance=(normalized_priority or {}).get("importance", 0),
                urgency_reason=(normalized_priority or {}).get("urgency_reason", "Не указано при создании"),
                importance_reason=(normalized_priority or {}).get("importance_reason", "Не указано при создании"),
                priority=(normalized_priority or {}).get("legacy_priority", "P4"),
                ticket_type=str(data.get("ticket_type") or "request").strip() or "request",
                custom_fields=custom_fields,
            )
            ticket = await ticket_repo.get_ticket(ticket_id)

            try:
                devices_repo = DevicesRepo(db_session)
                routing = TicketRoutingService(db_session, ticket_repo, devices_repo)

                async def add_routing_event(tid: str, did: str, etype: str, payload: Dict[str, Any]) -> None:
                    await ticket_repo.add_event(
                        ticket_id=tid,
                        device_id=did,
                        agent_seq=None,
                        event_type=etype,
                        payload=payload,
                        trace_id=str(uuid.uuid4()),
                    )

                await routing.apply_routing(ticket_id, placeholder_device_id, add_events_fn=add_routing_event)
                ticket = await ticket_repo.get_ticket(ticket_id)
            except Exception as routing_err:
                logger.warning(f"[public_create] routing failed: {routing_err}")

            try:
                sla = TicketSlaService(db_session, ticket_repo)
                await sla.start_sla(ticket)
                ticket = await ticket_repo.get_ticket(ticket_id)
            except Exception as sla_err:
                logger.warning(f"[public_create] sla start failed: {sla_err}")

            try:
                await start_ola_for_ticket(db_session, ticket)
            except Exception as ola_err:
                logger.warning(f"[public_create] OLA start failed: {ola_err}")

            if ticket and not getattr(ticket, "assignee_id", None):
                try:
                    assignment_service = TicketAssignmentService(ticket_repo)
                    selection = await assignment_service.resolve_assignee(
                        ticket,
                        requested_assignee_id=None,
                        auto_assign=True,
                    )
                    resolved_assignee_id = selection["assignee_id"]
                    if resolved_assignee_id:
                        await assignment_service.assign_ticket(
                            ticket_id,
                            ticket.device_id,
                            resolved_assignee_id,
                            actor_id="system",
                            actor_role="system",
                            reason="auto_assign_on_create",
                            comment="",
                            old_assignee=getattr(ticket, "assignee_id", None),
                            auto_assigned=True,
                            active_count=selection["active_count"],
                            limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                            db_session=db_session,
                            close_ola=True,
                        )
                        workflow = TicketWorkflowService(db_session, ticket_repo)
                        await workflow.apply_status_transition(
                            ticket_id=ticket_id,
                            from_status="new",
                            to_status="assigned",
                            actor_id="system",
                            actor_role="system",
                            reason="auto_assign_on_create",
                            source="system",
                        )
                        ticket = await ticket_repo.get_ticket(ticket_id)
                except TicketAssignmentError:
                    logger.info(f"[public_create] no free operators for auto-assign ticket_id={ticket_id}")
                except Exception as assign_err:
                    logger.warning(f"[public_create] auto-assign failed: {assign_err}")

            await ticket_repo.add_event(
                ticket_id=ticket_id,
                device_id=placeholder_device_id,
                agent_seq=None,
                event_type="chat_message",
                payload=enrich_chat_payload_with_requester_name(ticket, {
                    "message_id": initial_message_id,
                    "sender_role": "user",
                    "from": "user",
                    "is_initial": True,
                    "text": description,
                    "visibility": "public",
                }),
                trace_id=str(uuid.uuid4()),
                event_id=initial_message_id,
            )
            await _create_public_access_event(ticket_repo, ticket, public_access_code)
            try:
                await start_ticket_created_playbooks(
                    session=db_session,
                    state=request.app.get("state"),
                    ticket=ticket,
                    custom_fields=custom_fields,
                )
            except Exception as playbook_err:
                logger.warning(
                    f"[public_create] playbook form triggers failed ticket_id={ticket_id}: {playbook_err}"
                )
            await db_session.commit()
            ticket = await ticket_repo.get_ticket(ticket_id)
    except Exception as exc:
        logger.error(f"[public_create] failed: {exc}", exc_info=True)
        return web.json_response({"status": "error", "error": "service_unavailable"}, status=503)

    auth_service = AuthService(request.app["state"])
    public_token = await auth_service.generate_ticket_public_session_token(
        ticket_id=ticket_id,
        actor_id=requester_id,
        expires_minutes=PUBLIC_TICKET_SESSION_MINUTES,
    )
    return web.json_response(
        {
            "status": "ok",
            "ticket": ticket_to_dict(ticket),
            "initial_message_id": initial_message_id,
            "public_access_code": public_access_code,
            "public_token": public_token,
            "public_token_expires_at": public_token_expires_at.isoformat(),
        }
    )


async def handle_public_ticket_authorize(request: web.Request) -> web.Response:
    """POST /public_api/tickets/{ticket_id}/authorize - exchange auth code for ticket session."""
    ticket_id = request.match_info.get("ticket_id")
    if not ticket_id:
        return web.json_response({"status": "error", "error": "ticket_id required"}, status=400)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid JSON"}, status=400)

    code = str(data.get("code") or "").strip().upper()
    if not code:
        return _validation_error({"code": "code required"})

    try:
        async with get_session() as db_session:
            ticket_repo = TicketEventsRepo(db_session)
            ticket = await ticket_repo.get_ticket(ticket_id)
            if not ticket:
                return web.json_response({"status": "error", "error": "not_found"}, status=404)
            if not verify_public_access_code(ticket, code):
                return web.json_response(
                    {"status": "error", "error": "invalid_code", "message": "Неверный код авторизации"},
                    status=403,
                )
            actor_id = str(getattr(ticket, "requester_id", None) or make_public_requester_id(ticket_id))
    except Exception as exc:
        logger.error(f"[public_authorize] failed: {exc}", exc_info=True)
        return web.json_response({"status": "error", "error": "service_unavailable"}, status=503)

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PUBLIC_TICKET_SESSION_MINUTES)
    auth_service = AuthService(request.app["state"])
    public_token = await auth_service.generate_ticket_public_session_token(
        ticket_id=ticket_id,
        actor_id=actor_id,
        expires_minutes=PUBLIC_TICKET_SESSION_MINUTES,
    )
    return web.json_response(
        {
            "status": "ok",
            "ticket_id": ticket_id,
            "public_token": public_token,
            "public_token_expires_at": expires_at.isoformat(),
        }
    )
