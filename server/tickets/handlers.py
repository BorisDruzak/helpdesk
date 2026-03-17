"""HTTP handlers for the ticket domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from aiohttp import web
from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.api.serializers import serialize_datetime_recursive, ticket_to_dict
from app.db import get_session
from app.repos import (
    ArtifactsRepo,
    ChangeLinksRepo,
    DevicesRepo,
    NotificationPrefsRepo,
    NotificationRepo,
    ProblemsRepo,
    TicketEventsRepo,
)
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from auth.context import AuthContext, AuthType
from tickets.assignment_service import (
    MAX_ACTIVE_TICKETS_PER_OPERATOR,
    TicketAssignmentError,
    TicketAssignmentService,
)
from tickets.ola_service import build_ola_block, close_ola_processing, start_ola_for_ticket
from tickets.public_access import (
    build_public_access_message,
    generate_public_access_code,
    mark_public_ticket_unbound,
    set_public_access_code,
)
from tickets.queue_position_service import QueuePositionService
from tickets.routing_service import TicketRoutingService, set_routing_lock
from tickets.sla_service import TicketSlaService
from tickets.statuses import (
    get_requester_display_name,
    merge_requester_custom_fields,
    normalize_requester_profile,
    normalize_ticket_priority_inputs,
    resolve_status,
)
from tickets.workflow_service import TicketWorkflowService, validate_transition
from utils import new_ticket_id
from websocket.ui_handler import push_ticket_event_committed


HISTORY_EVENT_TYPES = {
    "status_changed",
    "priority_changed",
    "assignee_changed",
    "queue_changed",
    "requester_profile_changed",
    "device_changed",
}


def _json_ok(**payload: Any) -> web.Response:
    return web.json_response({"status": "ok", **payload})


def _json_error(error: str, *, status: int = 400, **payload: Any) -> web.Response:
    return web.json_response({"status": "error", "error": error, **payload}, status=status)


def _validation_error(details: Any) -> web.Response:
    return _json_error("validation_error", status=400, details=details)


async def _read_json(request: web.Request) -> Dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text='{"status":"error","error":"Invalid JSON"}', content_type="application/json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(
            text='{"status":"error","error":"JSON body must be an object"}',
            content_type="application/json",
        )
    return data


def _auth(request: web.Request) -> AuthContext:
    auth_context = request.get("auth_context")
    if not auth_context:
        raise web.HTTPUnauthorized()
    return auth_context


def _is_staff(auth_context: AuthContext) -> bool:
    return auth_context.actor_role in {"admin", "support"}


def _can_write(auth_context: AuthContext) -> bool:
    return auth_context.actor_role != "auditor"


def _message_role_from_auth(auth_context: AuthContext) -> str:
    if auth_context.actor_role == "agent":
        return "agent"
    if auth_context.actor_role in {"admin", "support", "auditor"}:
        return "support"
    return "user"


def _allow_ticket_read(ticket: Any, auth_context: AuthContext) -> bool:
    if auth_context.actor_role in {"admin", "support", "auditor"}:
        return True
    if auth_context.actor_role == "agent":
        return auth_context.actor_id == getattr(ticket, "device_id", None)
    if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
        return auth_context.ticket_scope == getattr(ticket, "ticket_id", None)
    return auth_context.actor_id == getattr(ticket, "requester_id", None)


def _allow_ticket_write(ticket: Any, auth_context: AuthContext) -> bool:
    return _allow_ticket_read(ticket, auth_context) and _can_write(auth_context)


async def _get_ticket_or_response(
    request: web.Request,
    session: Any,
    *,
    write: bool = False,
) -> tuple[Any, Optional[web.Response], TicketEventsRepo, AuthContext]:
    ticket_id = request.match_info.get("ticket_id")
    auth_context = _auth(request)
    ticket_repo = TicketEventsRepo(session)
    ticket = await ticket_repo.get_ticket(ticket_id)
    if not ticket:
        return None, _json_error("ticket_not_found", status=404), ticket_repo, auth_context
    allowed = _allow_ticket_write(ticket, auth_context) if write else _allow_ticket_read(ticket, auth_context)
    if not allowed:
        return None, _json_error("forbidden", status=403), ticket_repo, auth_context
    return ticket, None, ticket_repo, auth_context


def _serialize_event_raw(event: Any) -> Dict[str, Any]:
    ts = getattr(event, "created_at", None)
    return {
        "id": getattr(event, "id", None),
        "ticket_id": getattr(event, "ticket_id", None),
        "device_id": getattr(event, "device_id", None),
        "agent_seq": getattr(event, "agent_seq", None),
        "event_type": getattr(event, "event_type", None),
        "payload": serialize_datetime_recursive(getattr(event, "payload", None) or {}),
        "trace_id": getattr(event, "trace_id", None),
        "event_id": getattr(event, "event_id", None),
        "operation_id": getattr(event, "operation_id", None),
        "ts": ts.isoformat() if ts else None,
        "created_at": ts.isoformat() if ts else None,
    }


def _serialize_event_for_agent(event: Any) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    data = {
        "id": getattr(event, "id", None),
        "type": getattr(event, "event_type", None),
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
        "source": "server",
    }
    if isinstance(payload, dict):
        data.update(payload)
    return data


def _serialize_message(event: Any) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    sender_role = payload.get("sender_role") or payload.get("from") or "user"
    return {
        "message_id": payload.get("message_id"),
        "from_role": sender_role,
        "text": payload.get("text") or "",
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
        "agent_seq": getattr(event, "agent_seq", None),
        "visibility": payload.get("visibility") or "public",
        "attachment_refs": payload.get("attachment_refs") or [],
        "attachments": payload.get("attachments") or [],
        "direction": "from_agent" if sender_role == "agent" else "to_agent",
    }


def _event_visible_to_requester(event: Any) -> bool:
    if getattr(event, "event_type", None) != "chat_message":
        return True
    payload = getattr(event, "payload", None) or {}
    return (payload.get("visibility") or "public") != "internal"


async def _queue_code_map(session: Any, queue_ids: Iterable[Optional[int]]) -> Dict[int, str]:
    ids = sorted({int(qid) for qid in queue_ids if qid is not None})
    if not ids:
        return {}
    admin_repo = TicketAdminConfigRepo(session)
    result: Dict[int, str] = {}
    for queue_id in ids:
        queue = await admin_repo.get_queue(queue_id)
        if queue:
            result[queue.id] = queue.code
    return result


def _normalize_attachment_refs(raw: Any) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("attachment_refs must be an array")
    refs: List[str] = []
    for item in raw:
        if isinstance(item, str):
            artifact_id = item.strip()
        elif isinstance(item, dict):
            artifact_id = str(item.get("artifact_id") or "").strip()
        else:
            artifact_id = ""
        if not artifact_id:
            raise ValueError("each attachment_refs item must contain artifact_id")
        if artifact_id not in refs:
            refs.append(artifact_id)
    return refs


def _artifact_type(mime_type: Optional[str], kind: Optional[str]) -> str:
    mime = (mime_type or "").lower()
    kind_val = (kind or "").lower()
    if mime.startswith("image/") or kind_val == "screenshot":
        return "image"
    if mime.startswith("video/") or kind_val == "screen_recording":
        return "video"
    return "file"


async def _resolve_attachment_descriptors(
    artifacts_repo: ArtifactsRepo,
    ticket_id: str,
    attachment_refs: List[str],
) -> List[Dict[str, Any]]:
    descriptors: List[Dict[str, Any]] = []
    for artifact_id in attachment_refs:
        artifact = await artifacts_repo.get_by_id(artifact_id)
        if not artifact:
            raise ValueError(f"artifact {artifact_id} not found")
        if artifact.ticket_id and artifact.ticket_id != ticket_id:
            raise ValueError(f"artifact {artifact_id} belongs to another ticket")
        descriptors.append(
            {
                "artifact_id": artifact.artifact_id,
                "type": _artifact_type(artifact.mime_type, artifact.kind),
                "mime_type": artifact.mime_type,
                "kind": artifact.kind,
                "name": artifact.original_name,
                "url": f"/api/artifacts/{artifact.artifact_id}/download",
            }
        )
    return descriptors


async def _ticket_payload(session: Any, ticket: Any) -> Dict[str, Any]:
    queue_map = await _queue_code_map(session, [getattr(ticket, "queue_id", None)])
    return ticket_to_dict(ticket, queue_map.get(getattr(ticket, "queue_id", None)))


async def _push_ticket_event(
    request: web.Request,
    ticket_id: str,
    result: Optional[tuple],
    event_type: str,
    payload: Dict[str, Any],
    *,
    operation_id: Optional[str] = None,
    agent_seq: Optional[int] = None,
) -> None:
    if not result:
        return
    event_id, created_at = result
    try:
        await push_ticket_event_committed(
            request.app["state"],
            ticket_id=ticket_id,
            event_id=event_id,
            event_type=event_type,
            operation_id=operation_id,
            agent_seq=agent_seq,
            created_at=created_at,
            payload=payload,
        )
    except Exception as exc:
        logger.warning(f"[tickets.handlers] WS push failed: ticket_id={ticket_id} err={exc}")


async def _auto_assign_if_possible(session: Any, ticket_repo: TicketEventsRepo, ticket: Any) -> Any:
    if getattr(ticket, "assignee_id", None):
        return ticket
    assignment_service = TicketAssignmentService(ticket_repo)
    workflow = TicketWorkflowService(session, ticket_repo)
    try:
        selection = await assignment_service.resolve_assignee(
            ticket,
            requested_assignee_id=None,
            auto_assign=True,
        )
        assignee_id = selection["assignee_id"]
        if assignee_id:
            await assignment_service.assign_ticket(
                ticket.ticket_id,
                ticket.device_id,
                assignee_id,
                actor_id="system",
                actor_role="system",
                reason="auto_assign_on_create",
                comment="",
                old_assignee=getattr(ticket, "assignee_id", None),
                auto_assigned=True,
                active_count=selection["active_count"],
                limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                db_session=session,
                close_ola=True,
            )
            await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=getattr(ticket, "status", "new") or "new",
                to_status="triaged",
                actor_id="system",
                actor_role="system",
                reason="auto_assign_on_create",
                source="system",
            )
            ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    except TicketAssignmentError:
        return ticket
    return ticket


async def _apply_create_side_effects(session: Any, ticket_repo: TicketEventsRepo, ticket: Any) -> Any:
    devices_repo = DevicesRepo(session)
    routing = TicketRoutingService(session, ticket_repo, devices_repo)
    sla = TicketSlaService(session, ticket_repo)

    async def add_routing_event(ticket_id: str, device_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type=event_type,
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )

    try:
        await routing.apply_routing(ticket.ticket_id, ticket.device_id, add_events_fn=add_routing_event)
    except Exception as exc:
        logger.warning(f"[create] routing failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    try:
        await sla.start_sla(ticket)
    except Exception as exc:
        logger.warning(f"[create] sla failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    try:
        await start_ola_for_ticket(session, ticket)
    except Exception as exc:
        logger.warning(f"[create] ola failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    ticket = await _auto_assign_if_possible(session, ticket_repo, ticket)
    return ticket


def _default_priority_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    urgency = data.get("urgency")
    importance = data.get("importance")
    urgency_reason = str(data.get("urgency_reason") or "").strip()
    importance_reason = str(data.get("importance_reason") or "").strip()
    if urgency is None or importance is None:
        urgency = False
        importance = False
    if not urgency_reason:
        urgency_reason = "Не указано при создании"
    if not importance_reason:
        importance_reason = "Не указано при создании"
    return normalize_ticket_priority_inputs(urgency, importance, urgency_reason, importance_reason)


async def handle_tickets_create(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.actor_role not in {"agent", "admin", "support"}:
        return _json_error("forbidden", status=403)
    try:
        data = await request.json()
    except Exception:
        return _json_error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _json_error("JSON body must be an object", status=400)

    description = str(data.get("description") or "").strip()
    title = str(data.get("title") or "").strip() or "Support Request"
    user_display_name = str(data.get("user_display_name") or "").strip()
    if not description:
        return _validation_error({"description": "description is required"})
    if not user_display_name:
        user_display_name = auth_context.actor_id

    try:
        requester_profile = normalize_requester_profile(data.get("requester_profile"))
    except ValueError as exc:
        return _validation_error({"requester_profile": str(exc)})

    try:
        normalized_priority = _default_priority_payload(data)
    except ValueError as exc:
        return _validation_error({"priority": str(exc)})

    if auth_context.actor_role == "agent":
        device_id = auth_context.actor_id
    else:
        device_id = str(data.get("device_id") or "").strip()
        if not device_id:
            return _validation_error({"device_id": "device_id is required"})

    ticket_id = new_ticket_id()
    initial_message_id = str(uuid.uuid4())
    public_access_code = generate_public_access_code()

    async with get_session() as session:
        ticket_repo = TicketEventsRepo(session)
        ticket = await ticket_repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title=title,
            description=description,
            status="new",
            requester_id=auth_context.actor_id,
        )
        custom_fields = merge_requester_custom_fields(
            getattr(ticket, "custom_fields", None),
            user_display_name=user_display_name,
            requester_profile=requester_profile,
            priority_class=normalized_priority["priority_class"],
        )
        custom_fields = set_public_access_code(custom_fields, public_access_code)
        await ticket_repo.update_ticket(
            ticket_id,
            urgency=normalized_priority["urgency"],
            importance=normalized_priority["importance"],
            urgency_reason=normalized_priority["urgency_reason"],
            importance_reason=normalized_priority["importance_reason"],
            priority=normalized_priority["legacy_priority"],
            custom_fields=custom_fields,
        )
        ticket = await ticket_repo.get_ticket(ticket_id)
        ticket = await _apply_create_side_effects(session, ticket_repo, ticket)
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={
                "message_id": initial_message_id,
                "sender_role": "user",
                "from": "user",
                "is_initial": True,
                "text": description,
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
            event_id=initial_message_id,
        )
        access_payload = build_public_access_message(public_access_code, ticket_id)
        await ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload=access_payload,
            trace_id=str(uuid.uuid4()),
            event_id=access_payload["message_id"],
        )
        await session.commit()
        ticket = await ticket_repo.get_ticket(ticket_id)
        ticket_data = await _ticket_payload(session, ticket)

    return _json_ok(
        ticket=ticket_data,
        session={"ticket_id": ticket_id, "actor_role": auth_context.actor_role},
        initial_message_id=initial_message_id,
        public_access_code=public_access_code,
        public_access_url=ticket_data.get("public_access_url"),
    )


async def handle_tickets_list(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
        return _json_error("forbidden", status=403)

    limit = min(max(int(request.query.get("limit", "100")), 1), 500)
    offset = max(int(request.query.get("offset", "0")), 0)
    filters: Dict[str, Any] = {}
    for query_key, filter_key in (
        ("status", "status"),
        ("queue_id", "queue_id"),
        ("assignee_id", "assignee_id"),
        ("watching_actor_id", "watching_actor_id"),
        ("ticket_code", "ticket_code"),
    ):
        value = request.query.get(query_key)
        if value:
            filters[filter_key] = int(value) if filter_key == "queue_id" else value
    if request.query.get("unassigned") == "true":
        filters["assignee_id__none"] = True
    if request.query.get("first_response_breached") == "true":
        filters["first_response_breached"] = True
    if request.query.get("resolution_breached") == "true":
        filters["resolution_breached"] = True
    if auth_context.actor_role == "agent":
        filters["device_id"] = auth_context.actor_id
    elif auth_context.actor_role not in {"admin", "support", "auditor"}:
        filters["requester_id"] = auth_context.actor_id
    elif request.query.get("device_id"):
        filters["device_id"] = request.query.get("device_id")

    async with get_session() as session:
        repo = TicketEventsRepo(session)
        tickets = await repo.list_tickets(limit=limit, offset=offset, filters=filters)
        queue_map = await _queue_code_map(session, [getattr(ticket, "queue_id", None) for ticket in tickets])
        payload = [
            {
                "ticket": ticket_to_dict(ticket, queue_map.get(getattr(ticket, "queue_id", None))),
                "session": {"ticket_id": ticket.ticket_id},
            }
            for ticket in tickets
        ]
    return _json_ok(tickets=payload, count=len(payload), limit=limit, offset=offset)


async def handle_ticket_get(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=2000)
        visible_events = list(events)
        if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
            visible_events = [event for event in events if _event_visible_to_requester(event)]
        messages = [event for event in visible_events if getattr(event, "event_type", None) == "chat_message"]
        ticket_data = await _ticket_payload(session, ticket)
        return _json_ok(
            ticket=ticket_data,
            session={"ticket_id": ticket.ticket_id, "actor_role": auth_context.actor_role},
            messages=[_serialize_message(event) for event in messages],
            events=[_serialize_event_for_agent(event) for event in visible_events],
            agent_online=False,
        )


async def handle_ticket_get_snapshot(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=2000)
        visible_events = list(events)
        if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
            visible_events = [event for event in events if _event_visible_to_requester(event)]
        raw_events = [_serialize_event_raw(event) for event in visible_events]
        history = [item for item in raw_events if item["event_type"] in HISTORY_EVENT_TYPES]
        ticket_data = await _ticket_payload(session, ticket)
        last_event_id = raw_events[-1]["id"] if raw_events else 0
        return web.json_response(
            {
                **ticket_data,
                "actor_role": auth_context.actor_role,
                "events": raw_events,
                "history": history,
                "last_event_id": last_event_id,
            }
        )


async def handle_ticket_send_message(request: web.Request) -> web.Response:
    data = await _read_json(request)
    text = str(data.get("text") or "").strip()
    try:
        attachment_refs = _normalize_attachment_refs(data.get("attachment_refs"))
    except ValueError as exc:
        return _validation_error({"attachment_refs": str(exc)})
    if not text and not attachment_refs:
        return _validation_error({"text": "text or attachment_refs is required"})
    message_id = str(data.get("message_id") or str(uuid.uuid4())).strip()

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        artifacts_repo = ArtifactsRepo(session)
        attachments: List[Dict[str, Any]] = []
        if attachment_refs:
            try:
                attachments = await _resolve_attachment_descriptors(
                    artifacts_repo,
                    ticket.ticket_id,
                    attachment_refs,
                )
            except ValueError as exc:
                return _validation_error({"attachment_refs": str(exc)})
        visibility = str(data.get("visibility") or "public").strip() or "public"
        if visibility == "internal" and not _is_staff(auth_context):
            visibility = "public"
        sender_role = _message_role_from_auth(auth_context)
        payload = {
            "message_id": message_id,
            "sender_role": sender_role,
            "from": sender_role,
            "text": text,
            "visibility": visibility,
        }
        if attachment_refs:
            payload["attachment_refs"] = attachment_refs
            payload["attachments"] = attachments
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="chat_message",
            payload=payload,
            trace_id=str(uuid.uuid4()),
            event_id=message_id,
        )
        if visibility == "public" and sender_role in {"support", "agent"}:
            sla = TicketSlaService(session, repo)
            await sla.close_frt(ticket.ticket_id)
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "chat_message", payload)
        return _json_ok(event_id=result[0] if result else None, message_id=message_id)


async def handle_ticket_close(request: web.Request) -> web.Response:
    data = await _read_json(request)
    data["to_status"] = "closed"
    request["_forced_status_payload"] = data
    return await handle_ticket_status(request)


async def handle_ticket_status(request: web.Request) -> web.Response:
    data = request.get("_forced_status_payload")
    if data is None:
        data = await _read_json(request)
    raw_to_status = str(data.get("to_status") or "").strip()
    to_status, _ = resolve_status(raw_to_status)
    if not to_status:
        return _validation_error({"to_status": "invalid status"})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        is_support_or_admin = auth_context.actor_role in {"admin", "support"}
        if not validate_transition(ticket.status, to_status, is_support_or_admin):
            return _json_error(
                "invalid_transition",
                status=400,
                from_status=ticket.status,
                to_status=to_status,
            )
        workflow = TicketWorkflowService(session, repo)
        result = await workflow.apply_status_transition(
            ticket_id=ticket.ticket_id,
            from_status=ticket.status,
            to_status=to_status,
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=str(data.get("reason") or "").strip() or None,
            resolution_code=data.get("resolution_code"),
            root_cause=data.get("root_cause"),
            source="api",
        )
        await session.commit()
        await _push_ticket_event(
            request,
            ticket.ticket_id,
            result.get("event_result"),
            "status_changed",
            result.get("event_payload") or {},
        )
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_reroute(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        routing = TicketRoutingService(session, repo, DevicesRepo(session))
        captured: List[tuple[str, Dict[str, Any], Optional[tuple]]] = []

        async def capture(ticket_id: str, device_id: str, event_type: str, payload: Dict[str, Any]) -> None:
            result = await repo.add_event(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type=event_type,
                payload=payload,
                trace_id=str(uuid.uuid4()),
            )
            captured.append((event_type, payload, result))

        await routing.apply_routing(
            ticket.ticket_id,
            ticket.device_id,
            force_clear_lock=True,
            add_events_fn=capture,
        )
        await session.commit()
        for event_type, payload, result in captured:
            await _push_ticket_event(request, ticket.ticket_id, result, event_type, payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_classify(request: web.Request) -> web.Response:
    data = await _read_json(request)
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        updates = {key: data.get(key) for key in ("category_id", "service_id", "subcategory_id") if key in data}
        await repo.update_ticket(ticket.ticket_id, **updates)
        payload = {"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role, **updates}
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="classification_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "classification_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_queue(request: web.Request) -> web.Response:
    data = await _read_json(request)
    try:
        queue_id = int(data.get("queue_id"))
    except Exception:
        return _validation_error({"queue_id": "queue_id must be integer"})
    reason = str(data.get("reason") or "manual").strip() or "manual"

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        old_queue_id = ticket.queue_id
        custom_fields = set_routing_lock(getattr(ticket, "custom_fields", None), reason)
        await repo.update_ticket(
            ticket.ticket_id,
            queue_id=queue_id,
            custom_fields=custom_fields,
            manual_rank=None,
            manual_rank_updated_at=None,
            manual_rank_updated_by=None,
        )
        ticket = await repo.get_ticket(ticket.ticket_id)
        try:
            await close_ola_processing(session, ticket.ticket_id)
            await start_ola_for_ticket(session, ticket)
        except Exception as exc:
            logger.warning(f"[queue_change] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
        payload = {
            "queue_id": queue_id,
            "previous_queue_id": old_queue_id,
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
            "reason": reason,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="queue_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "queue_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_priority(request: web.Request) -> web.Response:
    data = await _read_json(request)
    try:
        normalized = normalize_ticket_priority_inputs(
            data.get("urgency"),
            data.get("importance"),
            data.get("urgency_reason"),
            data.get("importance_reason"),
        )
    except ValueError as exc:
        return _validation_error({"priority": str(exc)})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        custom_fields = merge_requester_custom_fields(
            getattr(ticket, "custom_fields", None),
            priority_class=normalized["priority_class"],
        )
        await repo.update_ticket(
            ticket.ticket_id,
            urgency=normalized["urgency"],
            importance=normalized["importance"],
            urgency_reason=normalized["urgency_reason"],
            importance_reason=normalized["importance_reason"],
            priority=normalized["legacy_priority"],
            custom_fields=custom_fields,
        )
        sla = TicketSlaService(session, repo)
        await sla.recalc_due_for_priority(ticket.ticket_id, normalized["legacy_priority"])
        payload = {
            "priority_class": normalized["priority_class"],
            "priority": normalized["legacy_priority"],
            "urgency": normalized["urgency"],
            "importance": normalized["importance"],
            "urgency_reason": normalized["urgency_reason"],
            "importance_reason": normalized["importance_reason"],
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="priority_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "priority_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_order(request: web.Request) -> web.Response:
    data = await _read_json(request)
    direction = str(data.get("direction") or "").strip()
    if direction not in {"up", "down", "top", "bottom"}:
        return _validation_error({"direction": "direction must be one of up/down/top/bottom"})
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        if ticket.queue_id is None:
            return _json_error("queue_required", status=400)
        svc = QueuePositionService(repo)
        move_result = await svc.reorder_ticket(ticket.queue_id, ticket.ticket_id, direction, auth_context.actor_id)
        if not move_result:
            return _json_error("reorder_failed", status=400)
        payload = {
            "direction": direction,
            "queue_id": ticket.queue_id,
            "from_position": move_result["from_position"],
            "to_position": move_result["to_position"],
            "actor_id": auth_context.actor_id,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="queue_order_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "queue_order_changed", payload)
        return _json_ok(**payload)


async def handle_ticket_queue_order_reset(request: web.Request) -> web.Response:
    queue_id = request.match_info.get("queue_id")
    try:
        queue_id_int = int(queue_id)
    except Exception:
        return _validation_error({"queue_id": "invalid queue_id"})
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        svc = QueuePositionService(repo)
        cleared = await svc.reset_manual_order(queue_id_int, auth_context.actor_id)
        await session.commit()
        return _json_ok(cleared=cleared, queue_id=queue_id_int)


async def handle_ticket_assign(request: web.Request) -> web.Response:
    data = await _read_json(request)
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        assignment_service = TicketAssignmentService(repo)
        auto_assign = bool(data.get("auto_assign"))
        try:
            selection = await assignment_service.resolve_assignee(
                ticket,
                requested_assignee_id=data.get("assignee_id"),
                auto_assign=auto_assign,
            )
        except TicketAssignmentError as exc:
            return _json_error("assignment_error", status=400, message=str(exc))
        assignee_id = selection["assignee_id"]
        result = await assignment_service.assign_ticket(
            ticket.ticket_id,
            ticket.device_id,
            assignee_id,
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            reason=str(data.get("reason") or "").strip() or None,
            comment=str(data.get("comment") or "").strip() or None,
            old_assignee=getattr(ticket, "assignee_id", None),
            auto_assigned=selection["auto_assigned"],
            active_count=selection["active_count"],
            limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
            db_session=session,
            close_ola=True,
        )
        await session.commit()
        payload = {
            "field_name": "assignee_id",
            "old_value": getattr(ticket, "assignee_id", None),
            "new_value": assignee_id,
            "assignee_id": assignee_id,
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
            "auto_assigned": selection["auto_assigned"],
            "target_active_count": selection["active_count"],
            "limit": MAX_ACTIVE_TICKETS_PER_OPERATOR,
        }
        await _push_ticket_event(request, ticket.ticket_id, result, "assignee_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(
            ticket=await _ticket_payload(session, ticket),
            assignee_id=assignee_id,
            auto_assigned=selection["auto_assigned"],
        )


async def handle_ticket_bind_device(request: web.Request) -> web.Response:
    data = await _read_json(request)
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    device_id = str(data.get("device_id") or "").strip()
    if not device_id:
        return _validation_error({"device_id": "device_id is required"})
    reason = str(data.get("reason") or "manual_bind").strip() or "manual_bind"
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        custom_fields = mark_public_ticket_unbound(getattr(ticket, "custom_fields", None), False)
        await repo.update_ticket(ticket.ticket_id, device_id=device_id, custom_fields=custom_fields)
        payload = {
            "previous_device_id": ticket.device_id,
            "device_id": device_id,
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
            "reason": reason,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="device_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "device_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_mark_read(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        payload = {"actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role}
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="message_read",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "message_read", payload)
        return _json_ok(event_id=result[0] if result else None)


async def handle_ticket_requester_profile(request: web.Request) -> web.Response:
    data = await _read_json(request)
    user_display_name = str(data.get("user_display_name") or "").strip()
    try:
        requester_profile = normalize_requester_profile(data.get("requester_profile"))
    except ValueError as exc:
        return _validation_error({"requester_profile": str(exc)})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        custom_fields = merge_requester_custom_fields(
            getattr(ticket, "custom_fields", None),
            user_display_name=user_display_name if user_display_name else None,
            requester_profile=requester_profile,
        )
        await repo.update_ticket(ticket.ticket_id, custom_fields=custom_fields)
        payload = {
            "user_display_name": user_display_name or get_requester_display_name(ticket),
            "requester_profile": requester_profile,
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="requester_profile_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "requester_profile_changed", payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket))


async def handle_ticket_sla_get(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        return _json_ok(
            ticket_id=ticket.ticket_id,
            first_response_due_at=ticket.first_response_due_at.isoformat() if ticket.first_response_due_at else None,
            resolution_due_at=ticket.resolution_due_at.isoformat() if ticket.resolution_due_at else None,
            first_response_at=ticket.first_response_at.isoformat() if ticket.first_response_at else None,
            resolution_at=ticket.resolution_at.isoformat() if ticket.resolution_at else None,
            first_response_breached_at=ticket.first_response_breached_at.isoformat() if ticket.first_response_breached_at else None,
            resolution_breached_at=ticket.resolution_breached_at.isoformat() if ticket.resolution_breached_at else None,
            ola=build_ola_block(ticket),
        )


async def handle_ticket_worklogs_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    try:
        spent_minutes = int(data.get("spent_minutes"))
    except Exception:
        return _validation_error({"spent_minutes": "spent_minutes must be integer"})
    note = str(data.get("note") or "").strip() or None
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        worklog = await repo.add_worklog(ticket.ticket_id, auth_context.actor_id, spent_minutes, note)
        if worklog is None:
            return _validation_error({"spent_minutes": "spent_minutes must be > 0"})
        payload = {
            "worklog_id": worklog.id,
            "actor_id": worklog.actor_id,
            "spent_minutes": worklog.spent_minutes,
            "note": worklog.note,
        }
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="worklog_added",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "worklog_added", payload)
        return _json_ok(worklog=payload)


async def handle_ticket_worklogs_list(request: web.Request) -> web.Response:
    limit = min(max(int(request.query.get("limit", "100")), 1), 500)
    offset = max(int(request.query.get("offset", "0")), 0)
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        worklogs = await repo.list_worklogs(ticket.ticket_id, limit=limit, offset=offset)
        return _json_ok(worklogs=serialize_datetime_recursive(worklogs), count=len(worklogs))


async def handle_ticket_worklog_total(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        total = await repo.get_worklog_total(ticket.ticket_id)
        return _json_ok(ticket_id=ticket.ticket_id, total_minutes=total)


async def handle_ticket_links_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    dst_ticket_id = str(data.get("dst_ticket_id") or "").strip()
    link_type = str(data.get("link_type") or "related").strip() or "related"
    if not dst_ticket_id:
        return _validation_error({"dst_ticket_id": "dst_ticket_id is required"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        link = await repo.add_ticket_link(ticket.ticket_id, dst_ticket_id, link_type, auth_context.actor_id)
        await session.commit()
        return _json_ok(link=serialize_datetime_recursive(link))


async def handle_ticket_links_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        links = await repo.list_ticket_links(ticket.ticket_id, request.query.get("link_type"))
        return _json_ok(links=serialize_datetime_recursive(links))


async def handle_ticket_links_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    try:
        link_id = int(request.match_info.get("link_id"))
    except Exception:
        return _validation_error({"link_id": "invalid link_id"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        deleted = await repo.delete_ticket_link(link_id, ticket.ticket_id)
        await session.commit()
        return _json_ok(deleted=deleted)


async def handle_ticket_parent_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    parent_ticket_id = str(data.get("parent_ticket_id") or "").strip()
    if not parent_ticket_id:
        return _validation_error({"parent_ticket_id": "parent_ticket_id is required"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        await repo.set_parent_ticket(ticket.ticket_id, parent_ticket_id)
        await session.commit()
        return _json_ok(parent_ticket_id=parent_ticket_id)


async def handle_ticket_parent_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        deleted = await repo.clear_parent_ticket(ticket.ticket_id)
        await session.commit()
        return _json_ok(deleted=deleted)


async def handle_ticket_watchers_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    actor_id = str(data.get("actor_id") or "").strip()
    if not actor_id:
        return _validation_error({"actor_id": "actor_id is required"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        try:
            await repo.add_watcher(ticket.ticket_id, actor_id)
            await session.commit()
        except IntegrityError:
            await session.rollback()
        return _json_ok(actor_id=actor_id)


async def handle_ticket_watchers_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        watchers = await repo.list_watchers(ticket.ticket_id)
        return _json_ok(watchers=serialize_datetime_recursive(watchers))


async def handle_ticket_watchers_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    actor_id = request.match_info.get("actor_id")
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        deleted = await repo.remove_watcher(ticket.ticket_id, actor_id)
        await session.commit()
        return _json_ok(deleted=deleted)


async def handle_ticket_kb_links_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    article_ref = str(data.get("article_ref") or "").strip()
    if not article_ref:
        return _validation_error({"article_ref": "article_ref is required"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        kb_link = await repo.add_kb_link(
            ticket.ticket_id,
            article_ref,
            title=data.get("title"),
            source=data.get("source"),
            created_by=auth_context.actor_id,
        )
        await session.commit()
        return _json_ok(kb_link=serialize_datetime_recursive(kb_link))


async def handle_ticket_kb_links_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        kb_links = await repo.list_kb_links(ticket.ticket_id)
        return _json_ok(kb_links=serialize_datetime_recursive(kb_links))


async def handle_ticket_kb_links_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    try:
        kb_link_id = int(request.match_info.get("kb_link_id"))
    except Exception:
        return _validation_error({"kb_link_id": "invalid kb_link_id"})
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        deleted = await repo.delete_kb_link(kb_link_id, ticket.ticket_id)
        await session.commit()
        return _json_ok(deleted=deleted)


async def handle_ticket_resolution_codes_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        items = await repo.list_resolution_codes(active_only=request.query.get("include_inactive") != "true")
        return _json_ok(
            resolution_codes=[
                {"code": item.code, "name": item.name, "is_active": item.is_active, "sort_order": item.sort_order}
                for item in items
            ]
        )


def _parse_period(request: web.Request) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    days = request.query.get("days")
    if days:
        days_int = max(min(int(days), 365), 1)
        return now - timedelta(days=days_int), now
    start = request.query.get("period_start")
    end = request.query.get("period_end")
    if start and end:
        return datetime.fromisoformat(start.replace("Z", "+00:00")), datetime.fromisoformat(end.replace("Z", "+00:00"))
    return now - timedelta(days=7), now


async def handle_ticket_metrics_backlog(request: web.Request) -> web.Response:
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(rows=await repo.get_metrics_backlog(queue_id=qid))


async def handle_ticket_metrics_aging(request: web.Request) -> web.Response:
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(rows=await repo.get_metrics_aging(queue_id=qid))


async def handle_ticket_metrics_sla(request: web.Request) -> web.Response:
    start, end = _parse_period(request)
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(**await repo.get_metrics_sla(start, end, queue_id=qid))


async def handle_ticket_metrics_reopen_rate(request: web.Request) -> web.Response:
    start, end = _parse_period(request)
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(**await repo.get_metrics_reopen_rate(start, end, queue_id=qid))


async def handle_ticket_metrics_top(request: web.Request) -> web.Response:
    start, end = _parse_period(request)
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(**await repo.get_metrics_top(start, end, queue_id=qid))


async def handle_ticket_metrics_status_age(request: web.Request) -> web.Response:
    queue_id = request.query.get("queue_id")
    qid = int(queue_id) if queue_id else None
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        return _json_ok(rows=await repo.get_metrics_status_age(queue_id=qid))


async def handle_notifications_list(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    limit = min(max(int(request.query.get("limit", "50")), 1), 200)
    offset = max(int(request.query.get("offset", "0")), 0)
    unread_only = request.query.get("unread_only") == "true"
    async with get_session() as session:
        repo = NotificationRepo(session)
        rows = await repo.list_by_actor(auth_context.actor_id, limit=limit, offset=offset, unread_only=unread_only)
        return _json_ok(notifications=serialize_datetime_recursive(rows))


async def handle_notifications_unread_count(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    async with get_session() as session:
        repo = NotificationRepo(session)
        return _json_ok(unread_count=await repo.unread_count(auth_context.actor_id))


async def handle_notifications_read_all(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    async with get_session() as session:
        repo = NotificationRepo(session)
        updated = await repo.mark_all_read(auth_context.actor_id)
        await session.commit()
        return _json_ok(updated=updated)


async def handle_notification_preferences_get(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    async with get_session() as session:
        repo = NotificationPrefsRepo(session)
        mute_internal, muted_event_types, suppress_self = await repo.get_or_default(auth_context.actor_id)
        return _json_ok(
            preferences={
                "mute_internal": mute_internal,
                "muted_event_types": muted_event_types,
                "suppress_self": suppress_self,
            }
        )


async def handle_notification_preferences_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    data = await _read_json(request)
    async with get_session() as session:
        repo = NotificationPrefsRepo(session)
        pref = await repo.upsert(
            auth_context.actor_id,
            mute_internal=data.get("mute_internal"),
            muted_event_types=data.get("muted_event_types"),
            suppress_self=data.get("suppress_self"),
        )
        await session.commit()
        return _json_ok(preferences=serialize_datetime_recursive(pref))


async def handle_notification_mark_read(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    try:
        notification_id = int(request.match_info.get("id"))
    except Exception:
        return _validation_error({"id": "invalid id"})
    async with get_session() as session:
        repo = NotificationRepo(session)
        updated = await repo.mark_read(notification_id, auth_context.actor_id)
        await session.commit()
        return _json_ok(updated=updated)


async def handle_problems_create(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    if not title or not description:
        return _validation_error({"title": "title required", "description": "description required"})
    async with get_session() as session:
        repo = ProblemsRepo(session)
        problem = await repo.create(
            title=title,
            description=description,
            status=str(data.get("status") or "New"),
            priority=str(data.get("priority") or "P3"),
            owner_id=data.get("owner_id") or auth_context.actor_id,
        )
        await session.commit()
        return _json_ok(problem=serialize_datetime_recursive(problem))


async def handle_problems_list(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.actor_role not in {"admin", "support", "auditor"}:
        return _json_error("forbidden", status=403)
    async with get_session() as session:
        repo = ProblemsRepo(session)
        problems = await repo.list_problems(
            status=request.query.get("status"),
            owner_id=request.query.get("owner_id"),
            limit=min(max(int(request.query.get("limit", "50")), 1), 200),
            offset=max(int(request.query.get("offset", "0")), 0),
        )
        return _json_ok(problems=serialize_datetime_recursive(problems))


async def handle_problem_get(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.actor_role not in {"admin", "support", "auditor"}:
        return _json_error("forbidden", status=403)
    problem_id = request.match_info.get("problem_id")
    async with get_session() as session:
        repo = ProblemsRepo(session)
        problem = await repo.get(problem_id)
        if not problem:
            return _json_error("problem_not_found", status=404)
        links = await repo.list_ticket_links(problem_id)
        return _json_ok(problem=serialize_datetime_recursive(problem), ticket_links=serialize_datetime_recursive(links))


async def handle_problem_status_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    problem_id = request.match_info.get("problem_id")
    data = await _read_json(request)
    new_status = str(data.get("status") or "").strip()
    if not new_status:
        return _validation_error({"status": "status is required"})
    resolved_at = datetime.now(timezone.utc) if new_status.lower() == "resolved" else None
    closed_at = datetime.now(timezone.utc) if new_status.lower() == "closed" else None
    async with get_session() as session:
        repo = ProblemsRepo(session)
        updated = await repo.update_status(
            problem_id,
            new_status,
            resolved_at=resolved_at,
            closed_at=closed_at,
            root_cause=data.get("root_cause"),
            workaround=data.get("workaround"),
            kb_article_ref=data.get("kb_article_ref"),
        )
        await session.commit()
        return _json_ok(updated=updated)


async def handle_problem_tickets_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    problem_id = request.match_info.get("problem_id")
    data = await _read_json(request)
    ticket_id = str(data.get("ticket_id") or "").strip()
    if not ticket_id:
        return _validation_error({"ticket_id": "ticket_id is required"})
    async with get_session() as session:
        repo = ProblemsRepo(session)
        try:
            await repo.add_ticket_link(problem_id, ticket_id, auth_context.actor_id)
            await session.commit()
        except IntegrityError:
            await session.rollback()
        return _json_ok(problem_id=problem_id, ticket_id=ticket_id)


async def handle_problem_tickets_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    problem_id = request.match_info.get("problem_id")
    ticket_id = request.match_info.get("ticket_id")
    async with get_session() as session:
        repo = ProblemsRepo(session)
        deleted = await repo.remove_ticket_link(problem_id, ticket_id)
        await session.commit()
        return _json_ok(deleted=deleted)


async def handle_ticket_problems_get(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        repo = ProblemsRepo(session)
        rows = await repo.list_problems_by_ticket(ticket.ticket_id)
        payload = [
            {"problem": serialize_datetime_recursive(problem), "link": serialize_datetime_recursive(link)}
            for problem, link in rows
        ]
        return _json_ok(items=payload)


async def handle_ticket_change_links_post(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    data = await _read_json(request)
    change_ref = str(data.get("change_ref") or "").strip()
    change_system = str(data.get("change_system") or "").strip()
    if not change_ref or not change_system:
        return _validation_error({"change_ref": "change_ref required", "change_system": "change_system required"})
    async with get_session() as session:
        ticket, error, _, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        repo = ChangeLinksRepo(session)
        link = await repo.create(ticket.ticket_id, change_ref, change_system, auth_context.actor_id)
        await session.commit()
        return _json_ok(change_link=serialize_datetime_recursive(link))


async def handle_ticket_change_links_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        repo = ChangeLinksRepo(session)
        links = await repo.list_by_ticket(ticket.ticket_id)
        return _json_ok(change_links=serialize_datetime_recursive(links))


async def handle_ticket_change_links_delete(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    try:
        link_id = int(request.match_info.get("id"))
    except Exception:
        return _validation_error({"id": "invalid id"})
    async with get_session() as session:
        ticket, error, _, _ = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        repo = ChangeLinksRepo(session)
        deleted = await repo.delete(link_id, ticket.ticket_id)
        await session.commit()
        return _json_ok(deleted=deleted)
