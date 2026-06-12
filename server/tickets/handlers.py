"""HTTP handlers for the ticket domain."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional

from aiohttp import web
from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.api.serializers import serialize_datetime_recursive, ticket_to_dict
from app.db import get_session
from knowledge.attempts import attach_knowledge_attempts, sanitize_knowledge_attempts
from knowledge.feedback_service import KnowledgeFeedbackService
from observer.service import ObserverOverlayService
from app.repos import (
    ArtifactsRepo,
    ChangeLinksRepo,
    DevicesRepo,
    NotificationPrefsRepo,
    NotificationRepo,
    ProblemsRepo,
    TicketEventsRepo,
)
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from auth.context import AuthContext, AuthType
from tickets.assignment_service import (
    MAX_ACTIVE_TICKETS_PER_OPERATOR,
    TicketAssignmentError,
    TicketAssignmentService,
)
from tickets.account_access_service import TicketAccountAccessService, requester_account_from_payload
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects
from tickets.diagnostic_policy import normalize_diagnostic_consent_payload
from tickets.form_catalog import (
    DEFAULT_TICKET_FORM_PACK_KEY,
    attach_request_template_computed_snapshot,
    build_form_custom_fields,
)
from tickets.helpdesk_policy_runtime import apply_effective_registry_policies
from tickets.priority_policy import compute_priority_from_policy
from tickets.request_template_submission import resolve_create_form_submission
from tickets.service_catalog_runtime import ServiceCatalogResolutionError, ServiceCatalogRuntimeResolver
from tickets.ola_service import build_ola_block, close_ola_processing, start_ola_for_ticket
from tickets.public_access import (
    is_public_support_reply_payload,
    mark_public_ticket_unbound,
)
from tickets.queue_position_service import QueuePositionService
from tickets.requester_timeline import build_requester_timeline_projection, projection_to_fields
from tickets.routing_service import TicketRoutingService, set_routing_lock
from tickets.sla_service import TicketSlaService
from tickets.statuses import (
    default_create_priority_payload,
    enrich_chat_payload_with_requester_name,
    get_requester_display_name,
    get_requester_profile,
    merge_requester_custom_fields,
    normalize_requester_profile,
    normalize_ticket_priority_inputs,
    resolve_status,
)
from tickets.workflow_service import TicketWorkflowService, validate_transition_for_ticket
from tickets.visibility_policy import apply_ticket_visibility_payload_async
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

PINNED_STUB_META_KEY = "agent_stub_reply_to_message"
RESOLUTION_CONFIRMATION_TEXT = "Проблема решена. Для подтверждения используйте одну из кнопок ниже."
RESOLUTION_CONFIRMATION_MESSAGE = "Если проблема решена, нажмите «Подтверждаю». Если нет, выберите «Не принято»."


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


def _read_scope_from_auth(auth_context: AuthContext) -> str:
    return "staff" if auth_context.actor_role in {"admin", "support"} else "requester"


def _extract_reply_to_from_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    raw_reply = payload.get("reply_to")
    if not isinstance(raw_reply, dict):
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            if isinstance(metadata.get("reply_to"), dict):
                raw_reply = metadata.get("reply_to")
            elif isinstance(metadata.get(PINNED_STUB_META_KEY), dict):
                raw_reply = metadata.get(PINNED_STUB_META_KEY)
    if not isinstance(raw_reply, dict):
        return None

    parent_message_id = str(raw_reply.get("parent_message_id") or "").strip()
    preview = str(raw_reply.get("preview") or raw_reply.get("target_preview") or "").strip()
    sender_role = str(raw_reply.get("sender_role") or raw_reply.get("from_role") or "").strip().lower()
    sender_display_name = str(raw_reply.get("sender_display_name") or raw_reply.get("sender") or "").strip()
    ts = str(raw_reply.get("ts") or raw_reply.get("target_ts") or "").strip()
    normalized: Dict[str, Any] = {}
    if parent_message_id:
        normalized["parent_message_id"] = parent_message_id
    if preview:
        normalized["preview"] = preview[:280]
    if sender_role:
        normalized["sender_role"] = sender_role
    if sender_display_name:
        normalized["sender_display_name"] = sender_display_name[:120]
    if ts:
        normalized["ts"] = ts
    return normalized or None


def _resolution_confirmation_state(ticket: Any) -> Dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None)
    if not isinstance(custom_fields, dict):
        return {}
    state = custom_fields.get("resolution_confirmation")
    return dict(state) if isinstance(state, dict) else {}


def _resolution_confirmation_pending(ticket: Any) -> bool:
    return bool(_resolution_confirmation_state(ticket).get("pending"))


def _serialize_ticket_watcher(watcher: Any) -> Dict[str, Any]:
    return {
        "ticket_id": getattr(watcher, "ticket_id", None),
        "actor_id": getattr(watcher, "actor_id", None),
    }


def _serialize_ticket_link(link: Any) -> Dict[str, Any]:
    return {
        "id": getattr(link, "id", None),
        "src_ticket_id": getattr(link, "src_ticket_id", None),
        "dst_ticket_id": getattr(link, "dst_ticket_id", None),
        "link_type": getattr(link, "link_type", None),
        "created_by": getattr(link, "created_by", None),
        "created_at": serialize_datetime_recursive(getattr(link, "created_at", None)),
    }


def _serialize_ticket_kb_link(kb_link: Any) -> Dict[str, Any]:
    return {
        "id": getattr(kb_link, "id", None),
        "ticket_id": getattr(kb_link, "ticket_id", None),
        "article_ref": getattr(kb_link, "article_ref", None),
        "title": getattr(kb_link, "title", None),
        "source": getattr(kb_link, "source", None),
        "created_by": getattr(kb_link, "created_by", None),
        "created_at": serialize_datetime_recursive(getattr(kb_link, "created_at", None)),
    }


def _serialize_ticket_worklog(worklog: Any) -> Dict[str, Any]:
    return {
        "id": getattr(worklog, "id", None),
        "ticket_id": getattr(worklog, "ticket_id", None),
        "actor_id": getattr(worklog, "actor_id", None),
        "spent_minutes": getattr(worklog, "spent_minutes", None),
        "note": getattr(worklog, "note", None),
        "created_at": serialize_datetime_recursive(getattr(worklog, "created_at", None)),
    }


def _resolution_confirmation_policy(ticket: Any) -> Dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None)
    if not isinstance(custom_fields, dict):
        return {}
    policy = custom_fields.get("resolution_confirmation_policy")
    return dict(policy) if isinstance(policy, dict) else {}


def _build_resolution_confirmation_request() -> Dict[str, Any]:
    request_id = str(uuid.uuid4())
    return {
        "request_id": request_id,
        "kind": "ticket_resolution",
        "message": RESOLUTION_CONFIRMATION_MESSAGE,
        "options": [
            {"option_id": "confirm", "label": "Подтверждаю"},
            {"option_id": "reject", "label": "Не принято"},
        ],
    }


async def _store_resolution_confirmation_state(
    repo: TicketEventsRepo,
    ticket: Any,
    *,
    pending: bool,
    request_id: Optional[str] = None,
    responded_option_id: Optional[str] = None,
) -> Any:
    custom_fields = dict(getattr(ticket, "custom_fields", None) or {})
    state = dict(custom_fields.get("resolution_confirmation") or {})
    state["pending"] = pending
    if request_id is not None:
        state["request_id"] = request_id
    if responded_option_id is not None:
        state["responded_option_id"] = responded_option_id
    custom_fields["resolution_confirmation"] = state
    custom_fields["resolution_confirmation_pending"] = pending
    await repo.update_ticket(ticket.ticket_id, custom_fields=custom_fields)
    return await repo.get_ticket(ticket.ticket_id)


def _chat_counters_defaults() -> Dict[str, Any]:
    return {
        "requester_last_read_event_id": 0,
        "support_last_read_event_id": 0,
        "requester_unread_messages": 0,
        "requester_unread_tool_calls": 0,
        "requester_latest_unread_event_id": None,
        "support_unread_user_messages": 0,
        "support_pending_user_messages": 0,
        "last_user_message_event_id": None,
        "last_user_message_id": None,
        "last_user_message_text": None,
        "last_user_message_at": None,
    }


def _merge_ticket_with_chat_counters(ticket_data: Dict[str, Any], chat_counters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(ticket_data)
    merged["chat_counters"] = {**_chat_counters_defaults(), **(chat_counters or {})}
    return merged


def _ticket_presence_payload(request: web.Request, ticket: Any) -> Dict[str, Any]:
    state = request.app.get("state")
    if state is None:
        return {
            "requester_online": False,
            "requester_last_seen_at": None,
            "requester_actor_ids": [],
            "support_online": False,
            "support_last_seen_at": None,
            "support_actor_ids": [],
            "agent_online": False,
        }
    presence = state.get_ticket_presence(getattr(ticket, "ticket_id", None))
    return {
        **presence,
        "agent_online": bool(getattr(state, "is_agent_online", lambda _device_id: False)(getattr(ticket, "device_id", None))),
    }


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


def _account_session_error(payload: dict[str, Any], *, status: int = 403) -> web.Response:
    return _json_error(
        "account_session_invalid",
        status=status,
        error_code=payload.get("error_code") or "ACCOUNT_SESSION_INVALID",
        details=payload,
    )


async def _validate_agent_ticket_account(
    request: web.Request,
    session: Any,
    *,
    device_id: str,
) -> tuple[dict[str, Any] | None, Optional[web.Response]]:
    cached = request.get("_validated_account_session")
    if isinstance(cached, dict):
        return cached, None
    body_payload = request.get("_requester_account_payload")
    requester_account = requester_account_from_payload(
        body_payload if isinstance(body_payload, dict) else None,
        query=request.query,
        headers=request.headers,
    )
    access = TicketAccountAccessService(session)
    validation = await access.validate_agent_account_session(
        device_id=device_id,
        requester_account=requester_account,
        require=True,
    )
    if not validation.get("valid"):
        return None, _account_session_error(validation)
    account_session = validation.get("session") or {}
    request["_validated_account_session"] = account_session
    return account_session, None


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
    if auth_context.actor_role == "support":
        queue_allowed = await ticket_repo.is_actor_in_queue(getattr(ticket, "queue_id", None), auth_context.actor_id)
        assignee_allowed = auth_context.actor_id == getattr(ticket, "assignee_id", None)
        queue_less_ticket = getattr(ticket, "queue_id", None) is None
        if not queue_allowed and not assignee_allowed and not queue_less_ticket:
            return None, _json_error("forbidden", status=403), ticket_repo, auth_context
    if auth_context.actor_role == "agent":
        account_session, account_error = await _validate_agent_ticket_account(
            request,
            session,
            device_id=auth_context.actor_id,
        )
        if account_error:
            return None, account_error, ticket_repo, auth_context
        access = TicketAccountAccessService(session)
        allowed = (
            await access.can_send_message(ticket=ticket, account_session=account_session or {})
            if write
            else await access.can_view_ticket(ticket=ticket, account_session=account_session or {})
        )
        if not allowed:
            return None, _json_error("account_access_denied", status=403, error_code="ACCOUNT_ACCESS_DENIED"), ticket_repo, auth_context
        return ticket, None, ticket_repo, auth_context
    allowed = _allow_ticket_write(ticket, auth_context) if write else _allow_ticket_read(ticket, auth_context)
    if not allowed:
        return None, _json_error("forbidden", status=403), ticket_repo, auth_context
    return ticket, None, ticket_repo, auth_context


def _serialize_event_raw(event: Any, ticket: Any | None = None) -> Dict[str, Any]:
    ts = getattr(event, "created_at", None)
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    if ticket is not None and getattr(event, "event_type", None) == "chat_message":
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
    reply_to = _extract_reply_to_from_payload(payload)
    if reply_to:
        payload["reply_to"] = reply_to
    data = {
        "id": getattr(event, "id", None),
        "ticket_id": getattr(event, "ticket_id", None),
        "device_id": getattr(event, "device_id", None),
        "agent_seq": getattr(event, "agent_seq", None),
        "event_type": getattr(event, "event_type", None),
        "payload": payload,
        "trace_id": getattr(event, "trace_id", None),
        "event_id": getattr(event, "event_id", None),
        "operation_id": getattr(event, "operation_id", None),
        "ts": ts.isoformat() if ts else None,
        "created_at": ts.isoformat() if ts else None,
    }
    projection = build_requester_timeline_projection(
        {"event_type": getattr(event, "event_type", None), "payload": payload},
        ticket=ticket,
    )
    data.update(projection_to_fields(projection))
    return data


def _serialize_event_for_agent(event: Any, ticket: Any | None = None) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    if ticket is not None and getattr(event, "event_type", None) == "chat_message":
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
    data = {
        "id": getattr(event, "id", None),
        "type": getattr(event, "event_type", None),
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
        "source": "server",
    }
    if isinstance(payload, dict):
        data.update(payload)
    projection = build_requester_timeline_projection(
        {"event_type": getattr(event, "event_type", None), "payload": payload},
        ticket=ticket,
    )
    data.update(projection_to_fields(projection))
    return data


def _serialize_message(event: Any, ticket: Any | None = None) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    if ticket is not None:
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
    sender_role = payload.get("sender_role") or payload.get("from") or "user"
    reply_to = _extract_reply_to_from_payload(payload)
    return {
        "message_id": payload.get("message_id"),
        "from_role": sender_role,
        "text": payload.get("text") or "",
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
        "agent_seq": getattr(event, "agent_seq", None),
        "event_id": getattr(event, "id", None),
        "visibility": payload.get("visibility") or "public",
        "attachment_refs": payload.get("attachment_refs") or [],
        "attachments": payload.get("attachments") or [],
        "metadata": payload.get("metadata") or {},
        "reply_to": reply_to,
        "direction": "from_agent" if sender_role == "agent" else "to_agent",
    }


def _serialize_message_for_requester(event: Any, ticket: Any | None = None) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    if ticket is not None:
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
    projection = build_requester_timeline_projection(
        {"event_type": getattr(event, "event_type", None), "payload": payload},
        ticket=ticket,
    )
    sender_role = payload.get("sender_role") or payload.get("from") or "user"
    reply_to = _extract_reply_to_from_payload(payload)
    metadata: dict[str, Any] = {}
    if projection is not None and projection.payload.get("message_kind"):
        metadata["message_kind"] = projection.payload["message_kind"]
    return {
        "message_id": payload.get("message_id"),
        "from_role": sender_role,
        "text": projection.text if projection is not None else (payload.get("text") or ""),
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
        "event_id": getattr(event, "id", None),
        "visibility": payload.get("visibility") or "public",
        "attachment_refs": payload.get("attachment_refs") or [],
        "attachments": payload.get("attachments") or [],
        "metadata": metadata,
        "reply_to": reply_to,
        "direction": "from_agent" if sender_role in {"agent", "support", "admin"} else "to_agent",
    }


def _serialize_event_for_requester(event: Any, ticket: Any | None = None) -> Dict[str, Any]:
    payload = serialize_datetime_recursive(getattr(event, "payload", None) or {})
    if ticket is not None and getattr(event, "event_type", None) == "chat_message":
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
    projection = build_requester_timeline_projection(
        {"event_type": getattr(event, "event_type", None), "payload": payload},
        ticket=ticket,
    )
    data = {
        "id": getattr(event, "id", None),
        "type": getattr(event, "event_type", None),
        "ts": getattr(event, "created_at", None).isoformat() if getattr(event, "created_at", None) else None,
    }
    data.update(projection_to_fields(projection))
    return data


REQUESTER_HIDDEN_EVENT_TYPES = frozenset(
    {
        "sla_paused",
        "sla_resumed",
        "ola_paused",
        "ola_resumed",
    }
)


def _event_visible_to_requester(event: Any) -> bool:
    return build_requester_timeline_projection(event) is not None


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


async def _normalize_reply_to_for_ticket(
    repo: TicketEventsRepo,
    ticket_id: str,
    raw_reply: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_reply, dict):
        return None

    parent_message_id = str(raw_reply.get("parent_message_id") or "").strip()
    preview = str(raw_reply.get("preview") or raw_reply.get("target_preview") or "").strip()
    sender_role = str(raw_reply.get("sender_role") or raw_reply.get("from_role") or "").strip().lower()
    sender_display_name = str(raw_reply.get("sender_display_name") or raw_reply.get("sender") or "").strip()
    ts = str(raw_reply.get("ts") or raw_reply.get("target_ts") or "").strip()

    parent_event = None
    if parent_message_id:
        parent_event = await repo.get_chat_message_by_message_id(ticket_id, parent_message_id)
        if parent_event is None:
            raise ValueError("reply_to.parent_message_id not found in this ticket")

    if parent_event is not None:
        parent_payload = serialize_datetime_recursive(getattr(parent_event, "payload", None) or {})
        preview = str(parent_payload.get("text") or preview or "").strip()
        sender_role = str(parent_payload.get("sender_role") or parent_payload.get("from") or sender_role or "").strip().lower()
        sender_display_name = str(
            parent_payload.get("sender_display_name")
            or parent_payload.get("requester_display_name")
            or sender_display_name
            or ""
        ).strip()
        parent_ts = getattr(parent_event, "created_at", None)
        if parent_ts is not None:
            ts = parent_ts.isoformat()

    if not parent_message_id and not preview:
        return None

    normalized: Dict[str, Any] = {}
    if parent_message_id:
        normalized["parent_message_id"] = parent_message_id
    if preview:
        normalized["preview"] = preview[:280]
    if sender_role:
        normalized["sender_role"] = sender_role
    if sender_display_name:
        normalized["sender_display_name"] = sender_display_name[:120]
    if ts:
        normalized["ts"] = ts
    return normalized or None


async def _resolve_attachment_descriptors(
    artifacts_repo: ArtifactsRepo,
    ticket_id: str,
    device_id: str | None,
    attachment_refs: List[str],
) -> List[Dict[str, Any]]:
    descriptors: List[Dict[str, Any]] = []
    for artifact_id in attachment_refs:
        artifact = await artifacts_repo.get_by_id(artifact_id)
        if not artifact:
            raise ValueError(f"artifact {artifact_id} not found")
        if artifact.ticket_id and artifact.ticket_id != ticket_id:
            raise ValueError(f"artifact {artifact_id} belongs to another ticket")
        if device_id and artifact.device_id and artifact.device_id != device_id:
            raise ValueError(f"artifact {artifact_id} device mismatch")
        if not artifact.ticket_id:
            artifact.ticket_id = ticket_id
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


async def _ticket_payload(
    session: Any,
    ticket: Any,
    *,
    chat_counters: Optional[Dict[str, Any]] = None,
    include_assignment_context: bool = False,
    visibility: str = "support",
) -> Dict[str, Any]:
    queue_map = await _queue_code_map(session, [getattr(ticket, "queue_id", None)])
    ticket_data = ticket_to_dict(ticket, queue_map.get(getattr(ticket, "queue_id", None)), visibility=visibility)
    ticket_data["ola"] = build_ola_block(ticket)
    if getattr(ticket, "device_id", None):
        try:
            device = await DevicesRepo(session).get_by_device_id(ticket.device_id)
        except Exception as exc:
            logger.debug(f"[ticket_payload] failed to load device metadata ticket_id={ticket.ticket_id} err={exc}")
            device = None
        if device is not None and isinstance(getattr(device, "device_metadata", None), dict):
            ticket_data["device_metadata"] = device.device_metadata
    queue_id = getattr(ticket, "queue_id", None)
    admin_repo = TicketAdminConfigRepo(session)
    if queue_id is not None:
        queue = await admin_repo.get_queue(queue_id)
        if queue is not None:
            ticket_data["queue_auto_assign_enabled"] = getattr(queue, "auto_assign_enabled", True)
    if include_assignment_context:
        queue_members = await admin_repo.list_queue_members(queue_id) if queue_id is not None else []
        available_queues = [queue for queue in await admin_repo.list_queues(include_inactive=False) if getattr(queue, "is_active", True)]
        ticket_repo = TicketEventsRepo(session)
        assignable_users = await ticket_repo.list_assignable_users_with_load(queue_id=queue_id)
        ticket_data["queue_members"] = [
            {"actor_id": member.actor_id, "role_in_queue": member.role_in_queue}
            for member in queue_members
        ]
        ticket_data["assignable_users"] = [
            serialize_datetime_recursive(user)
            for user in assignable_users
        ]
        ticket_data["available_queues"] = [
            {
                "id": queue.id,
                "code": queue.code,
                "name": queue.name,
                "is_active": getattr(queue, "is_active", True),
                "auto_assign_enabled": getattr(queue, "auto_assign_enabled", True),
            }
            for queue in available_queues
        ]
    ticket_data = _merge_ticket_with_chat_counters(ticket_data, chat_counters)
    return await apply_ticket_visibility_payload_async(session, ticket, ticket_data, visibility=visibility)


async def _chat_counters_by_ticket_ids(repo: TicketEventsRepo, ticket_ids: Iterable[Optional[str]]) -> Dict[str, Dict[str, Any]]:
    normalized = [str(ticket_id).strip() for ticket_id in ticket_ids if ticket_id]
    if not normalized:
        return {}
    return await repo.get_ticket_chat_counters_batch(normalized)


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
                to_status="assigned",
                actor_id="system",
                actor_role="system",
                reason="auto_assign_on_create",
                source="system",
            )
            ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    except TicketAssignmentError:
        return ticket
    return ticket


async def _reconcile_queue_scope_state(
    session: Any,
    ticket_repo: TicketEventsRepo,
    ticket: Any,
    *,
    actor_id: str,
    actor_role: str,
    reason_prefix: str,
) -> tuple[Any, List[tuple[str, Dict[str, Any], Optional[tuple]]]]:
    captured: List[tuple[str, Dict[str, Any], Optional[tuple]]] = []
    assignment_service = TicketAssignmentService(ticket_repo)
    workflow = TicketWorkflowService(session, ticket_repo)
    current_assignee = getattr(ticket, "assignee_id", None)
    queue_id = getattr(ticket, "queue_id", None)

    if current_assignee:
        clear_payload = {
            "field_name": "assignee_id",
            "old_value": current_assignee,
            "new_value": None,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": f"{reason_prefix}_queue_scope",
            "comment": "",
            "assignee_id": None,
            "previous_assignee_id": current_assignee,
            "auto_assigned": False,
            "target_active_count": 0,
            "limit": MAX_ACTIVE_TICKETS_PER_OPERATOR,
        }
        clear_result = await assignment_service.assign_ticket(
            ticket.ticket_id,
            ticket.device_id,
            None,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=f"{reason_prefix}_queue_scope",
            comment="",
            old_assignee=current_assignee,
            auto_assigned=False,
            active_count=0,
            limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
            db_session=session,
            close_ola=False,
        )
        captured.append(("assignee_changed", clear_payload, clear_result))
        ticket = await ticket_repo.get_ticket(ticket.ticket_id)

    if not getattr(ticket, "assignee_id", None):
        try:
            selection = await assignment_service.resolve_assignee(
                ticket,
                requested_assignee_id=None,
                auto_assign=True,
            )
        except TicketAssignmentError:
            selection = None
        if selection and selection.get("assignee_id"):
            auto_assignee_id = selection["assignee_id"]
            auto_payload = {
                "field_name": "assignee_id",
                "old_value": None,
                "new_value": auto_assignee_id,
                "actor_id": "system",
                "actor_role": "system",
                "reason": f"{reason_prefix}_auto_assign",
                "comment": "",
                "assignee_id": auto_assignee_id,
                "previous_assignee_id": None,
                "auto_assigned": True,
                "target_active_count": selection["active_count"],
                "limit": MAX_ACTIVE_TICKETS_PER_OPERATOR,
            }
            auto_result = await assignment_service.assign_ticket(
                ticket.ticket_id,
                ticket.device_id,
                auto_assignee_id,
                actor_id="system",
                actor_role="system",
                reason=f"{reason_prefix}_auto_assign",
                comment="",
                old_assignee=None,
                auto_assigned=True,
                active_count=selection["active_count"],
                limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                db_session=session,
                close_ola=True,
            )
            captured.append(("assignee_changed", auto_payload, auto_result))
            ticket = await ticket_repo.get_ticket(ticket.ticket_id)

    current_status = str(getattr(ticket, "status", "") or "").lower()
    if current_status and current_status not in ("closed", "resolved"):
        target_status = "assigned" if getattr(ticket, "assignee_id", None) else "queued"
        if current_status != target_status:
            transition = await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=current_status,
                to_status=target_status,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=f"{reason_prefix}_queue_state",
                source="system",
            )
            captured.append(("status_changed", transition["event_payload"], transition["event_result"]))
            ticket = await ticket_repo.get_ticket(ticket.ticket_id)

    return ticket, captured


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
        await start_ola_for_ticket(session, ticket, trigger="ticket_created")
    except Exception as exc:
        logger.warning(f"[create] ola failed ticket_id={ticket.ticket_id} err={exc}")
    ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    ticket = await _auto_assign_if_possible(session, ticket_repo, ticket)
    if (
        ticket
        and getattr(ticket, "queue_id", None)
        and not getattr(ticket, "assignee_id", None)
        and getattr(ticket, "status", None) == "new"
    ):
        workflow = TicketWorkflowService(session, ticket_repo)
        await workflow.apply_status_transition(
            ticket_id=ticket.ticket_id,
            from_status="new",
            to_status="queued",
            actor_id="system",
            actor_role="system",
            reason="routed_to_queue",
            source="system",
        )
        ticket = await ticket_repo.get_ticket(ticket.ticket_id)
    return ticket


def _default_priority_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return default_create_priority_payload(data)


def _priority_policy_fallback(data: Dict[str, Any], *, actor_role: str) -> Dict[str, Any]:
    fallback: Dict[str, Any] = {
        "impact": data.get("impact"),
        "urgency": data.get("urgency"),
        "importance": data.get("importance"),
        "actor_role": actor_role,
        "manual_actor_role": actor_role,
    }
    manual_priority = data.get("manual_priority")
    if manual_priority is not None:
        fallback["manual_priority"] = manual_priority
        fallback["manual_reason"] = data.get("manual_reason") or data.get("manual_priority_reason")
    return fallback


async def handle_tickets_create(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.actor_role not in {"user", "agent", "admin", "support"}:
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

    request_template_key = str(data.get("request_template_key") or "").strip()
    service_code = str(data.get("service_code") or "").strip()
    offering_code = str(data.get("offering_code") or "").strip()
    offering_full_code = str(data.get("offering_full_code") or data.get("full_offering_code") or "").strip()
    form_key = str(data.get("form_key") or request_template_key or "").strip()
    pack_key = str(data.get("form_pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = str(data.get("form_pack_version") or "").strip() or None
    form_payload = data.get("form_payload")
    requester_account = data.get("requester_account")
    if requester_account is not None and not isinstance(requester_account, dict):
        return _validation_error({"requester_account": "requester_account must be an object"})
    knowledge_attempts = sanitize_knowledge_attempts(data.get("knowledge_attempts"), surface="agent_gui" if auth_context.actor_role == "agent" else "requester_portal")

    if auth_context.actor_role == "agent":
        device_id = auth_context.actor_id
    else:
        device_id = str(data.get("device_id") or "").strip()
        if not device_id:
            return _validation_error({"device_id": "device_id is required"})

    async with get_session() as session:
        if auth_context.actor_role == "agent":
            validation = await TicketAccountAccessService(session).validate_agent_account_session(
                device_id=device_id,
                requester_account=requester_account,
                require=True,
            )
            if not validation.get("valid"):
                return _account_session_error(validation)
            if not await TicketAccountAccessService(session).can_create_ticket(
                device_id=device_id,
                account_session=validation.get("session") or {},
            ):
                return _json_error("account_access_denied", status=403, error_code="ACCOUNT_ACCESS_DENIED")
        extra_custom_fields: dict[str, Any] | None = None
        template_process_fields: dict[str, Any] = {}
        catalog_process_fields: dict[str, Any] = {}
        ticket_type = str(data.get("ticket_type") or "request").strip() or "request"
        catalog_selection = None
        catalog_template_key = request_template_key or form_key
        if service_code or offering_code or offering_full_code or catalog_template_key:
            try:
                catalog_selection = await ServiceCatalogRuntimeResolver(session).resolve_selection(
                    service_code=service_code or None,
                    offering_code=offering_code or None,
                    offering_full_code=offering_full_code or None,
                    request_template_key=catalog_template_key or None,
                    actor_role=auth_context.actor_role,
                )
                if catalog_selection.request_template_key:
                    request_template_key = catalog_selection.request_template_key
                    form_key = form_key or request_template_key
            except ServiceCatalogResolutionError as exc:
                return _validation_error(exc.details)
        if form_key:
            try:
                validated_submission = await resolve_create_form_submission(
                    session,
                    pack_key=pack_key,
                    pack_version=pack_version,
                    form_key=form_key,
                    request_template_key=request_template_key,
                    raw_values=form_payload or {},
                )
                if catalog_selection is not None:
                    validated_submission = await ServiceCatalogRuntimeResolver(session).apply_to_validated_submission(
                        validated_submission,
                        catalog_selection,
                    )
                validated_submission = await apply_effective_registry_policies(session, validated_submission)
                extra_custom_fields = build_form_custom_fields(validated_submission)
                catalog_process_fields = validated_submission.get("catalog_fields") if isinstance(validated_submission.get("catalog_fields"), dict) else {}
                diagnostic_consent = normalize_diagnostic_consent_payload(data.get("diagnostic_consent"))
                if diagnostic_consent:
                    extra_custom_fields["diagnostic_consent"] = diagnostic_consent
                ticket_type = str(validated_submission.get("ticket_type") or ticket_type).strip() or ticket_type
                template_context = validated_submission.get("template_context") or {}
                if isinstance(template_context, dict) and isinstance(template_context.get("service_catalog"), dict):
                    extra_custom_fields["service_catalog"] = template_context["service_catalog"]
                for key in ("category_id", "service_id", "subcategory_id", "sla_policy_id"):
                    if template_context.get(key) is not None:
                        template_process_fields[key] = template_context.get(key)
                priority_policy = template_context.get("priority_policy") or {}
                if priority_policy:
                    normalized_priority = compute_priority_from_policy(
                        priority_policy=priority_policy,
                        submitted_values=validated_submission.get("submitted_values") or {},
                        fallback=_priority_policy_fallback(data, actor_role=auth_context.actor_role),
                    )
            except ValueError as exc:
                details = exc.args[0] if exc.args else "invalid form payload"
                return _validation_error({"form_payload": details})
        extra_custom_fields = attach_knowledge_attempts(extra_custom_fields or {}, knowledge_attempts)
        created = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=auth_context.actor_id,
            title=title,
            description=description,
            user_display_name=user_display_name,
            requester_profile=requester_profile,
            normalized_priority=normalized_priority,
            initial_message_text=description,
            initial_message_sender_role="user",
            initial_message_from="user",
            include_public_access=True,
            ticket_type=ticket_type,
            **template_process_fields,
            **catalog_process_fields,
            extra_custom_fields=extra_custom_fields,
            requester_account=requester_account,
            state=request.app.get("state"),
        )
        if knowledge_attempts:
            ticket = created["ticket"]
            await KnowledgeFeedbackService(session).record_event(
                {
                    "event_type": "ticket_created_after_view",
                    "ticket_id": created["ticket_id"],
                    "service_code": service_code or getattr(ticket, "service_code", None),
                    "offering_code": offering_full_code or offering_code or getattr(ticket, "offering_code", None),
                    "surface": "agent_gui" if auth_context.actor_role == "agent" else "requester_portal",
                    "metadata": {"knowledge_attempts": knowledge_attempts},
                },
                actor_role=auth_context.actor_role,
                actor_id=auth_context.actor_id,
            )
        await session.commit()
        ticket_data = await _ticket_payload(session, created["ticket"])

    return _json_ok(
        ticket=ticket_data,
        session={"ticket_id": created["ticket_id"], "actor_role": auth_context.actor_role},
        initial_message_id=created["initial_message_id"],
        public_access_code=created["public_access_code"],
        public_access_url=ticket_data.get("public_access_url"),
    )


def _iso_or_none(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


async def handle_tickets_create_preview(request: web.Request) -> web.Response:
    auth_context = _auth(request)
    if auth_context.actor_role not in {"user", "agent", "admin", "support"}:
        return _json_error("forbidden", status=403)
    try:
        data = await request.json()
    except Exception:
        return _json_error("Invalid JSON", status=400)
    if not isinstance(data, dict):
        return _json_error("JSON body must be an object", status=400)

    request_template_key = str(data.get("request_template_key") or "").strip()
    service_code = str(data.get("service_code") or "").strip()
    offering_code = str(data.get("offering_code") or "").strip()
    offering_full_code = str(data.get("offering_full_code") or data.get("full_offering_code") or "").strip()
    form_key = str(data.get("form_key") or request_template_key or "").strip()
    catalog_selection = None
    if not form_key and not (service_code or offering_code or offering_full_code):
        return _validation_error({"form_key": "form_key or request_template_key is required"})
    pack_key = str(data.get("form_pack_key") or DEFAULT_TICKET_FORM_PACK_KEY).strip() or DEFAULT_TICKET_FORM_PACK_KEY
    pack_version = str(data.get("form_pack_version") or "").strip() or None

    try:
        normalized_priority = _default_priority_payload(data)
    except ValueError as exc:
        return _validation_error({"priority": str(exc)})

    async with get_session() as session:
        if auth_context.actor_role == "agent":
            validation = await TicketAccountAccessService(session).validate_agent_account_session(
                device_id=auth_context.actor_id,
                requester_account=data.get("requester_account") if isinstance(data.get("requester_account"), dict) else None,
                require=True,
            )
            if not validation.get("valid"):
                return _account_session_error(validation)
        try:
            catalog_template_key = request_template_key or form_key
            if service_code or offering_code or offering_full_code or catalog_template_key:
                catalog_selection = await ServiceCatalogRuntimeResolver(session).resolve_selection(
                    service_code=service_code or None,
                    offering_code=offering_code or None,
                    offering_full_code=offering_full_code or None,
                    request_template_key=catalog_template_key or None,
                    actor_role=auth_context.actor_role,
                )
                if catalog_selection.request_template_key:
                    request_template_key = catalog_selection.request_template_key
                    form_key = form_key or request_template_key
            validated_submission = await resolve_create_form_submission(
                session,
                pack_key=pack_key,
                pack_version=pack_version,
                form_key=form_key,
                request_template_key=request_template_key,
                raw_values=data.get("form_payload") or {},
            )
            if catalog_selection is not None:
                validated_submission = await ServiceCatalogRuntimeResolver(session).apply_to_validated_submission(
                    validated_submission,
                    catalog_selection,
                )
            validated_submission = await apply_effective_registry_policies(session, validated_submission)
            custom_fields = build_form_custom_fields(validated_submission)
            ticket_type = str(validated_submission.get("ticket_type") or data.get("ticket_type") or "request").strip() or "request"
            template_context = validated_submission.get("template_context") or {}
            priority_policy = template_context.get("priority_policy") or {}
            if priority_policy:
                normalized_priority = compute_priority_from_policy(
                    priority_policy=priority_policy,
                    submitted_values=validated_submission.get("submitted_values") or {},
                    fallback=_priority_policy_fallback(data, actor_role=auth_context.actor_role),
                )
        except ValueError as exc:
            details = exc.args[0] if exc.args else "invalid form payload"
            return _validation_error({"form_payload": details})

        priority_class = (
            normalized_priority.get("effective_priority")
            or normalized_priority.get("priority_class")
            or normalized_priority.get("computed_priority")
            or "P3"
        )
        priority_decision = {
            "impact": normalized_priority.get("impact"),
            "urgency": normalized_priority.get("urgency"),
            "importance": normalized_priority.get("importance"),
            "computed_priority": normalized_priority.get("computed_priority") or priority_class,
            "effective_priority": priority_class,
            "priority_class": priority_class,
            "legacy_priority": normalized_priority.get("legacy_priority", "P4"),
            "priority_source": normalized_priority.get("priority_source", "system"),
            "priority_reason": normalized_priority.get("priority_reason") or normalized_priority.get("urgency_reason"),
            "manual_priority": normalized_priority.get("manual_priority"),
            "manual_priority_reason": normalized_priority.get("manual_priority_reason"),
            "applied_modifiers": normalized_priority.get("applied_modifiers") or [],
            "manual_override_event": normalized_priority.get("manual_override_event"),
            "priority_explanation": normalized_priority.get("priority_explanation") or {},
        }
        custom_fields["priority_class"] = priority_class
        custom_fields["priority_decision"] = priority_decision

        ticket_repo = TicketEventsRepo(session)
        synthetic_ticket = SimpleNamespace(
            ticket_id="preview",
            device_id=str(data.get("device_id") or ""),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            status="new",
            priority=normalized_priority.get("legacy_priority", "P4"),
            impact=normalized_priority.get("impact"),
            urgency=normalized_priority.get("urgency"),
            importance=normalized_priority.get("importance"),
            queue_id=None,
            category_id=template_context.get("category_id"),
            service_id=template_context.get("service_id"),
            subcategory_id=template_context.get("subcategory_id"),
            assignee_id=None,
            requester_id=auth_context.actor_id,
            sla_policy_id=template_context.get("sla_policy_id"),
            custom_fields=custom_fields,
            ticket_type=ticket_type,
            catalog_service_id=(validated_submission.get("catalog_fields") or {}).get("catalog_service_id")
            if isinstance(validated_submission.get("catalog_fields"), dict)
            else None,
            catalog_offering_id=(validated_submission.get("catalog_fields") or {}).get("catalog_offering_id")
            if isinstance(validated_submission.get("catalog_fields"), dict)
            else None,
            service_code=(validated_submission.get("catalog_fields") or {}).get("service_code")
            if isinstance(validated_submission.get("catalog_fields"), dict)
            else None,
            offering_code=(validated_submission.get("catalog_fields") or {}).get("offering_code")
            if isinstance(validated_submission.get("catalog_fields"), dict)
            else None,
            request_type=(validated_submission.get("catalog_fields") or {}).get("request_type")
            if isinstance(validated_submission.get("catalog_fields"), dict)
            else None,
        )

        routing_service = TicketRoutingService(session, ticket_repo)
        routing_decision = await routing_service.resolve_routing_decision(synthetic_ticket, device_metadata=None)
        queue_id = routing_decision.get("queue_id") if isinstance(routing_decision, dict) else None
        queue = await ticket_repo.get_queue(queue_id) if queue_id is not None else None
        custom_fields = attach_request_template_computed_snapshot(
            custom_fields,
            priority_decision=priority_decision,
            routing_decision=routing_decision,
            queue=queue,
        )

        sla_preview: dict[str, Any] = {
            "first_response_due_at": None,
            "resolution_due_at": None,
            "first_response_minutes": None,
            "resolution_minutes": None,
        }
        sla_service = TicketSlaService(session, ticket_repo)
        policy, targets = await sla_service._get_policy_and_targets(synthetic_ticket)
        target = sla_service._target_for_priority(targets, priority_class) if targets else None
        if policy and target:
            now = datetime.now(timezone.utc)
            calendar = await sla_service._calendar_for_policy(policy)
            first_response_due_at = sla_service._due_at(now, target.first_response_min, calendar)
            resolution_due_at = sla_service._due_at(now, target.resolution_min, calendar)
            sla_preview = {
                "first_response_due_at": _iso_or_none(first_response_due_at),
                "resolution_due_at": _iso_or_none(resolution_due_at),
                "first_response_minutes": target.first_response_min,
                "resolution_minutes": target.resolution_min,
            }

    request_template = custom_fields.get("request_template") if isinstance(custom_fields.get("request_template"), dict) else {}
    approval_policy = request_template.get("approval_policy") if isinstance(request_template.get("approval_policy"), dict) else {}
    diagnostic_policy = request_template.get("diagnostic_policy") if isinstance(request_template.get("diagnostic_policy"), dict) else {}
    consent = diagnostic_policy.get("consent") if isinstance(diagnostic_policy.get("consent"), dict) else {}
    preview = {
        "request_template_key": request_template.get("key") or form_key,
        "request_template_title": request_template.get("title") or custom_fields.get("request_form_title") or form_key,
        "form_key": custom_fields.get("request_form_key") or form_key,
        "request_form": custom_fields.get("request_form") if isinstance(custom_fields.get("request_form"), dict) else {},
        "request_template": request_template,
        "service_catalog": request_template.get("service_catalog") if isinstance(request_template.get("service_catalog"), dict) else None,
        "ticket_type": ticket_type,
        "priority": priority_decision,
        "routing": {
            "source": routing_decision.get("source") if isinstance(routing_decision, dict) else None,
            "target_queue_id": queue_id,
            "target_queue_name": getattr(queue, "name", None),
            "fallback_applied": bool(isinstance(routing_decision, dict) and routing_decision.get("source") == "fallback_queue"),
            "matched_rule": routing_decision.get("matched_rule") if isinstance(routing_decision, dict) else None,
        },
        "sla": sla_preview,
        "approval_required": bool(approval_policy.get("required")),
        "diagnostic_consent_required": bool(
            diagnostic_policy.get("requires_user_consent") or consent.get("required_for_requester_device")
        ),
        "summary_rows": validated_submission.get("summary_rows") or [],
    }
    return _json_ok(preview=preview)


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
    elif auth_context.actor_role == "support":
        filters["support_actor_id"] = auth_context.actor_id
    elif auth_context.actor_role not in {"admin", "support", "auditor"}:
        filters["requester_id"] = auth_context.actor_id
    elif request.query.get("device_id"):
        filters["device_id"] = request.query.get("device_id")
    if auth_context.actor_role in {"admin", "support", "auditor"}:
        filters["exclude_archived"] = True

    async with get_session() as session:
        if auth_context.actor_role == "agent":
            account_session, account_error = await _validate_agent_ticket_account(
                request,
                session,
                device_id=auth_context.actor_id,
            )
            if account_error:
                return account_error
            filters["account_session_access"] = account_session
        repo = TicketEventsRepo(session)
        tickets = await repo.list_tickets(limit=limit, offset=offset, filters=filters)
        queue_map = await _queue_code_map(session, [getattr(ticket, "queue_id", None) for ticket in tickets])
        counters_map = await _chat_counters_by_ticket_ids(repo, [getattr(ticket, "ticket_id", None) for ticket in tickets])
        visibility = _read_scope_from_auth(auth_context)
        payload = [
            {
                "ticket": _merge_ticket_with_chat_counters(
                    ticket_to_dict(
                        ticket,
                        queue_map.get(getattr(ticket, "queue_id", None)),
                        visibility=visibility,
                    ),
                    counters_map.get(getattr(ticket, "ticket_id", None)),
                ),
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
        state = request.app.get("state")
        if state is not None and (
            auth_context.actor_role in {"agent", "user"}
            or auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN
        ):
            state.touch_ticket_presence(
                ticket.ticket_id,
                auth_context.actor_id,
                auth_context.actor_role,
                presence_key=f"http:{auth_context.actor_role}:{auth_context.actor_id}",
            )
        since_event_id_raw = request.query.get("since_event_id")
        before_event_id_raw = request.query.get("before_event_id")
        limit_raw = request.query.get("limit")
        if since_event_id_raw is not None and before_event_id_raw is not None:
            return _validation_error(
                {
                    "query": "since_event_id and before_event_id are mutually exclusive",
                }
            )

        incremental = since_event_id_raw is not None
        backward = before_event_id_raw is not None
        default_limit = 500 if incremental else 2000
        limit = default_limit
        if limit_raw is not None:
            try:
                limit = int(limit_raw)
            except ValueError:
                return _validation_error({"limit": "must be an integer >= 1"})
            if limit < 1:
                return _validation_error({"limit": "must be an integer >= 1"})
            limit = min(limit, 2000)

        if incremental:
            try:
                since_event_id = max(int(since_event_id_raw or "0"), 0)
            except ValueError:
                return _validation_error({"since_event_id": "must be an integer >= 0"})
            raw_events = await repo.get_events_since_id(ticket.ticket_id, since_event_id=since_event_id, limit=limit)
            has_older = False
            page_oldest_event_id = getattr(raw_events[0], "id", 0) if raw_events else 0
            next_before_event_id = None
        else:
            since_event_id = 0
            if backward:
                try:
                    before_event_id = int(before_event_id_raw or "0")
                except ValueError:
                    return _validation_error({"before_event_id": "must be an integer >= 1"})
                if before_event_id < 1:
                    return _validation_error({"before_event_id": "must be an integer >= 1"})
            else:
                before_event_id = None
            if backward or limit_raw is not None:
                raw_events, has_older = await repo.get_events_before_id(
                    ticket.ticket_id,
                    before_event_id=before_event_id,
                    limit=limit,
                )
                page_oldest_event_id = getattr(raw_events[0], "id", before_event_id or 0) if raw_events else (before_event_id or 0)
                next_before_event_id = page_oldest_event_id if has_older and page_oldest_event_id > 0 else None
            else:
                raw_events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=limit)
                has_older = False
                page_oldest_event_id = getattr(raw_events[0], "id", 0) if raw_events else 0
                next_before_event_id = None
        visibility = _read_scope_from_auth(auth_context)
        visible_events = list(raw_events)
        if visibility == "requester":
            visible_events = [event for event in raw_events if _event_visible_to_requester(event)]
        messages = [event for event in visible_events if getattr(event, "event_type", None) == "chat_message"]
        counters_map = await _chat_counters_by_ticket_ids(repo, [ticket.ticket_id])
        ticket_data = await _ticket_payload(
            session,
            ticket,
            chat_counters=counters_map.get(ticket.ticket_id),
            include_assignment_context=True,
            visibility=visibility,
        )
        presence = _ticket_presence_payload(request, ticket)
        ticket_data["presence"] = presence
        return _json_ok(
            ticket=ticket_data,
            session={"ticket_id": ticket.ticket_id, "actor_role": auth_context.actor_role},
            messages=[
                (
                    _serialize_message_for_requester(event, ticket=ticket)
                    if visibility == "requester"
                    else _serialize_message(event, ticket=ticket)
                )
                for event in messages
            ],
            events=[
                (
                    _serialize_event_for_requester(event, ticket=ticket)
                    if visibility == "requester"
                    else _serialize_event_for_agent(event, ticket=ticket)
                )
                for event in visible_events
            ],
            agent_online=presence["agent_online"],
            presence=presence,
            incremental=incremental,
            backward=backward,
            has_more=incremental and len(raw_events) >= limit,
            has_older=has_older,
            oldest_event_id=page_oldest_event_id,
            next_before_event_id=next_before_event_id,
            last_event_id=(getattr(raw_events[-1], "id", since_event_id) if raw_events else since_event_id),
        )


async def handle_ticket_get_snapshot(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        state = request.app.get("state")
        if state is not None and (
            auth_context.actor_role in {"agent", "user"}
            or auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN
        ):
            state.touch_ticket_presence(
                ticket.ticket_id,
                auth_context.actor_id,
                auth_context.actor_role,
                presence_key=f"http:{auth_context.actor_role}:{auth_context.actor_id}",
            )
        events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=2000)
        visibility = _read_scope_from_auth(auth_context)
        visible_events = list(events)
        if visibility == "requester":
            visible_events = [event for event in events if _event_visible_to_requester(event)]
        raw_events = [
            (
                _serialize_event_for_requester(event, ticket=ticket)
                if visibility == "requester"
                else _serialize_event_raw(event, ticket=ticket)
            )
            for event in visible_events
        ]
        history = [
            item
            for item in raw_events
            if (item.get("event_type") or item.get("type")) in HISTORY_EVENT_TYPES
        ]
        counters_map = await _chat_counters_by_ticket_ids(repo, [ticket.ticket_id])
        ticket_data = await _ticket_payload(
            session,
            ticket,
            chat_counters=counters_map.get(ticket.ticket_id),
            include_assignment_context=True,
            visibility=visibility,
        )
        presence = _ticket_presence_payload(request, ticket)
        ticket_data["presence"] = presence
        last_event_id = raw_events[-1]["id"] if raw_events else 0
        worklogs = await repo.list_worklogs(ticket.ticket_id, limit=100, offset=0)
        worklog_total = await repo.get_worklog_total(ticket.ticket_id)
        watchers = await repo.list_watchers(ticket.ticket_id)
        links = await repo.list_ticket_links(ticket.ticket_id)
        kb_links = await repo.list_kb_links(ticket.ticket_id)
        parent_ticket_id = getattr(ticket, "parent_ticket_id", None)
        child_tickets = await repo.list_child_tickets(ticket.ticket_id)

        from app.repos.auth_tokens_repo import AuthTokensRepo
        from app.repos.connection_requests_repo import ConnectionRequestsRepo
        from app.repos.operations_repo import OperationsRepo

        operations_repo = OperationsRepo(session)
        auth_tokens_repo = AuthTokensRepo(session)
        connection_requests_repo = ConnectionRequestsRepo(session)

        recent_operations = await operations_repo.get_recent_operations(
            device_id=ticket.device_id,
            limit=20,
        )
        recent_update_op = next((op for op in recent_operations if op.kind == "agent_update"), None)

        device_repo = DevicesRepo(session)
        device = await device_repo.get_by_device_id(ticket.device_id)
        device_meta = device.device_metadata if (device and isinstance(device.device_metadata, dict)) else {}

        tokens = await auth_tokens_repo.get_agent_tokens_by_device(ticket.device_id)
        now = datetime.now(timezone.utc)
        token_rows = list(tokens or [])
        active_tokens = [
            t for t in token_rows
            if t.revoked_at is None and (t.expires_at is None or t.expires_at > now)
        ]
        latest_token = max(token_rows, key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc), default=None)
        latest_request = await connection_requests_repo.get_latest_by_device_id(ticket.device_id)

        provisioning_summary = {
            "token_status": "active" if active_tokens else ("revoked" if token_rows else "missing"),
            "reprovision_required": len(active_tokens) == 0,
            "token_issued_at": latest_token.created_at.isoformat() if latest_token and latest_token.created_at else None,
            "token_last_used_at": latest_token.last_used_at.isoformat() if latest_token and latest_token.last_used_at else None,
            "token_revoked_at": latest_token.revoked_at.isoformat() if latest_token and latest_token.revoked_at else None,
            "last_connection_request_status": latest_request.status if latest_request else None,
            "last_connection_request_at": (
                latest_request.last_request_at.isoformat() if latest_request and latest_request.last_request_at else None
            ),
        }
        update_summary = {
            "applied_update_version": device_meta.get("applied_update_version"),
            "last_update_operation_id": device_meta.get("last_update_operation_id"),
            "last_update_operation_status": getattr(recent_update_op, "status", None),
            "last_update_error_code": getattr(recent_update_op, "error_code", None),
            "last_update_error_message": getattr(recent_update_op, "error_message", None),
            "last_update_result_summary": getattr(recent_update_op, "result_summary", None),
        }

        notification_repo = NotificationRepo(session)
        unread_count = await notification_repo.unread_count(auth_context.actor_id)
        response_payload = {
            **ticket_data,
            "actor_role": auth_context.actor_role,
            "presence": presence,
            "events": raw_events,
            "history": history,
            "last_event_id": last_event_id,
            "requester_profile": get_requester_profile(ticket),
            "requester_display_name": get_requester_display_name(ticket),
            "relations": {
                "parent_ticket_id": parent_ticket_id,
                "child_ticket_ids": [t.ticket_id for t in child_tickets],
            },
            "watchers": [_serialize_ticket_watcher(watcher) for watcher in watchers],
            "links": [_serialize_ticket_link(link) for link in links],
            "kb_links": [_serialize_ticket_kb_link(kb_link) for kb_link in kb_links],
            "worklogs": [_serialize_ticket_worklog(worklog) for worklog in worklogs],
            "worklog_totals": {"total_minutes": worklog_total},
            "device_summary": {
                "device_id": ticket.device_id,
                "hostname": getattr(device, "hostname", None),
                "os": getattr(device, "os", None),
                "agent_version": getattr(device, "agent_version", None),
                "last_seen_at": device.last_seen_at.isoformat() if device and device.last_seen_at else None,
                "online": request.app["state"].is_agent_online(ticket.device_id),
            },
            "latest_operations": [
                {
                    "operation_id": op.operation_id,
                    "kind": op.kind,
                    "status": op.status,
                    "tool_name": op.tool_name,
                    "command_name": op.command_name,
                    "error_code": op.error_code,
                    "error_message": op.error_message,
                    "result_summary": op.result_summary,
                    "queued_at": op.queued_at.isoformat() if op.queued_at else None,
                    "finished_at": op.finished_at.isoformat() if op.finished_at else None,
                }
                for op in recent_operations
            ],
            "notification_counters": {"unread": unread_count},
            "provisioning_summary": provisioning_summary,
            "update_summary": update_summary,
        }
        payload = await apply_ticket_visibility_payload_async(
            session,
            ticket,
            response_payload,
            visibility=visibility,
        )
        return web.json_response(payload)


async def handle_ticket_get_observer_summary(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        service = ObserverOverlayService(session)
        payload = await service.get_ticket_observer_summary(ticket.ticket_id)
        await session.commit()
    return _json_ok(**payload)


async def handle_ticket_send_message(request: web.Request) -> web.Response:
    data = await _read_json(request)
    request["_requester_account_payload"] = data
    text = str(data.get("text") or "").strip()
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
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
                    ticket.device_id,
                    attachment_refs,
                )
            except ValueError as exc:
                return _validation_error({"attachment_refs": [str(exc)]})
        visibility = str(data.get("visibility") or "public").strip() or "public"
        if visibility == "internal" and not _is_staff(auth_context):
            visibility = "public"
        sender_role = _message_role_from_auth(auth_context)
        raw_reply = None
        if isinstance(data.get("reply_to"), dict):
            raw_reply = data.get("reply_to")
        elif isinstance(metadata.get("reply_to"), dict):
            raw_reply = metadata.get("reply_to")
        elif isinstance(metadata.get(PINNED_STUB_META_KEY), dict):
            raw_reply = metadata.get(PINNED_STUB_META_KEY)
        try:
            reply_to = await _normalize_reply_to_for_ticket(repo, ticket.ticket_id, raw_reply)
        except ValueError as exc:
            return _validation_error({"reply_to": str(exc)})
        payload = {
            "message_id": message_id,
            "sender_role": sender_role,
            "from": sender_role,
            "text": text,
            "visibility": visibility,
        }
        account_session = request.get("_validated_account_session")
        if isinstance(account_session, dict):
            payload.update(
                {
                    "requester_account_session_id": account_session.get("session_id"),
                    "requester_account_mode": account_session.get("account_mode"),
                    "requester_person_id": account_session.get("person_id"),
                    "requester_binding_id": account_session.get("binding_id"),
                    "created_from_other_account": account_session.get("account_mode") == "verified_other_account",
                }
            )
        clean_metadata = dict(metadata)
        clean_metadata.pop(PINNED_STUB_META_KEY, None)
        if reply_to:
            payload["reply_to"] = reply_to
            clean_metadata["reply_to"] = reply_to
        if clean_metadata:
            payload["metadata"] = clean_metadata
        payload = enrich_chat_payload_with_requester_name(ticket, payload)
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
        status_result = None
        status_payload = None
        confirmation_response = None
        if isinstance(clean_metadata.get("confirmation_response"), dict):
            confirmation_response = clean_metadata.get("confirmation_response")
        if visibility == "public" and sender_role == "user" and confirmation_response and ticket.status == "resolved":
            pending_state = _resolution_confirmation_state(ticket)
            request_id = str(confirmation_response.get("request_id") or "").strip()
            option_id = str(confirmation_response.get("option_id") or "").strip().lower()
            if pending_state.get("pending") and request_id and request_id == pending_state.get("request_id"):
                workflow = TicketWorkflowService(session, repo)
                if option_id == "confirm":
                    transition = await workflow.apply_status_transition(
                        ticket_id=ticket.ticket_id,
                        from_status=ticket.status,
                        to_status="closed",
                        actor_id=auth_context.actor_id,
                        actor_role=auth_context.actor_role,
                        reason="requester_confirmed_resolution",
                        source="requester_confirmation",
                    )
                    status_result = transition.get("event_result")
                    status_payload = transition.get("event_payload") or {}
                    ticket = await repo.get_ticket(ticket.ticket_id)
                    ticket = await _store_resolution_confirmation_state(
                        repo,
                        ticket,
                        pending=False,
                        responded_option_id="confirm",
                    )
                elif option_id == "reject":
                    confirmation_policy = _resolution_confirmation_policy(ticket)
                    reopen_policy_present = "reopen_on_negative_feedback" in confirmation_policy
                    should_reopen = bool(confirmation_policy.get("reopen_on_negative_feedback", True))
                    if should_reopen:
                        transition = await workflow.apply_status_transition(
                            ticket_id=ticket.ticket_id,
                            from_status=ticket.status,
                            to_status="in_progress" if reopen_policy_present else "assigned",
                            actor_id=auth_context.actor_id,
                            actor_role=auth_context.actor_role,
                            reason="requester_rejected_resolution",
                            source="requester_confirmation",
                        )
                        status_result = transition.get("event_result")
                        status_payload = transition.get("event_payload") or {}
                        ticket = await repo.get_ticket(ticket.ticket_id)
                    ticket = await _store_resolution_confirmation_state(
                        repo,
                        ticket,
                        pending=False,
                        responded_option_id="reject",
                    )
        if visibility == "public" and sender_role == "user" and getattr(ticket, "status", None) == "waiting_on_user":
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
        if is_public_support_reply_payload(payload):
            sla = TicketSlaService(session, repo)
            await sla.close_frt(ticket.ticket_id)
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "chat_message", payload)
        if status_result:
            await _push_ticket_event(request, ticket.ticket_id, status_result, "status_changed", status_payload or {})
        return _json_ok(
            event_id=result[0] if result else None,
            message_id=message_id,
            attachments_count=len(attachments),
        )


async def handle_ticket_close(request: web.Request) -> web.Response:
    data = await _read_json(request)
    request["_requester_account_payload"] = data
    async with get_session() as session:
        ticket, error, _, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if ticket.status == "resolved" and _resolution_confirmation_pending(ticket) and auth_context.actor_role in {"admin", "support"}:
            return _json_error("closed_requires_requester_confirmation", status=409)
    data["to_status"] = "closed"
    request["_forced_status_payload"] = data
    return await handle_ticket_status(request)


async def handle_ticket_status(request: web.Request) -> web.Response:
    data = request.get("_forced_status_payload")
    if data is None:
        data = await _read_json(request)
    request["_requester_account_payload"] = data
    raw_to_status = str(data.get("to_status") or "").strip()
    to_status, _ = resolve_status(raw_to_status)
    if not to_status:
        return _validation_error({"to_status": "invalid status"})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        is_support_or_admin = auth_context.actor_role in {"admin", "support"}
        if not await validate_transition_for_ticket(session, ticket, to_status, is_support_or_admin):
            return _json_error(
                "invalid_transition",
                status=400,
                from_status=ticket.status,
                to_status=to_status,
            )
        workflow = TicketWorkflowService(session, repo)
        try:
            result = await workflow.apply_status_transition(
                ticket_id=ticket.ticket_id,
                from_status=ticket.status,
                to_status=to_status,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                reason=str(data.get("reason") or "").strip() or None,
                resolution_code=data.get("resolution_code"),
                resolution_summary=data.get("resolution_summary"),
                requester_resolution_summary=data.get("requester_resolution_summary"),
                root_cause=data.get("root_cause"),
                source="api",
            )
        except ValueError as exc:
            return _validation_error({"workflow_policy": str(exc)})
        followup_result = None
        followup_payload = None
        ticket = await repo.get_ticket(ticket.ticket_id)
        closure_policy_payload = (result.get("event_payload") or {}).get("closure_policy")
        requester_confirmation_policy = (
            closure_policy_payload.get("requester_confirmation")
            if isinstance(closure_policy_payload, dict)
            else None
        )
        requires_requester_confirmation = True
        if isinstance(requester_confirmation_policy, dict) and "required" in requester_confirmation_policy:
            requires_requester_confirmation = bool(requester_confirmation_policy.get("required"))
        if to_status == "resolved" and is_support_or_admin and requires_requester_confirmation:
            confirmation_request = _build_resolution_confirmation_request()
            if isinstance(requester_confirmation_policy, dict) and requester_confirmation_policy:
                confirmation_request["policy"] = {
                    key: requester_confirmation_policy.get(key)
                    for key in ("auto_close_after_days", "reopen_on_negative_feedback")
                    if requester_confirmation_policy.get(key) is not None
                }
            ticket = await _store_resolution_confirmation_state(
                repo,
                ticket,
                pending=True,
                request_id=confirmation_request["request_id"],
            )
            followup_payload = {
                "message_id": str(uuid.uuid4()),
                "sender_role": "support",
                "from": "support",
                "text": RESOLUTION_CONFIRMATION_TEXT,
                "visibility": "public",
                "metadata": {"confirmation_request": confirmation_request},
            }
            followup_result = await repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="chat_message",
                payload=followup_payload,
                trace_id=str(uuid.uuid4()),
                event_id=followup_payload["message_id"],
            )
        elif to_status == "closed" and _resolution_confirmation_pending(ticket):
            ticket = await _store_resolution_confirmation_state(repo, ticket, pending=False)
        await session.commit()
        await _push_ticket_event(
            request,
            ticket.ticket_id,
            result.get("event_result"),
            "status_changed",
            result.get("event_payload") or {},
        )
        if followup_result and followup_payload:
            await _push_ticket_event(request, ticket.ticket_id, followup_result, "chat_message", followup_payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket, include_assignment_context=True))


async def handle_ticket_reroute(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not _is_staff(auth_context):
            return _json_error("forbidden", status=403)
        routing = TicketRoutingService(session, repo, DevicesRepo(session))
        captured: List[tuple[str, Dict[str, Any], Optional[tuple]]] = []
        previous_queue_id = getattr(ticket, "queue_id", None)

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
        ticket = await repo.get_ticket(ticket.ticket_id)
        try:
            await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
            await start_ola_for_ticket(session, ticket, trigger="queue_changed")
        except Exception as exc:
            logger.warning(f"[reroute] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
        if getattr(ticket, "queue_id", None) != previous_queue_id:
            ticket, queue_events = await _reconcile_queue_scope_state(
                session,
                repo,
                ticket,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                reason_prefix="reroute",
            )
            captured.extend(queue_events)
        await session.commit()
        for event_type, payload, result in captured:
            await _push_ticket_event(request, ticket.ticket_id, result, event_type, payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket, include_assignment_context=True))


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
            await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
            await start_ola_for_ticket(session, ticket, trigger="queue_changed")
        except Exception as exc:
            logger.warning(f"[queue_change] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
        captured: List[tuple[str, Dict[str, Any], Optional[tuple]]] = []
        if queue_id != old_queue_id:
            ticket, captured = await _reconcile_queue_scope_state(
                session,
                repo,
                ticket,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                reason_prefix="manual_queue_change",
            )
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
        for event_type, event_payload, event_result in captured:
            await _push_ticket_event(request, ticket.ticket_id, event_result, event_type, event_payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket, include_assignment_context=True))


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
            ticket=await _ticket_payload(session, ticket, include_assignment_context=True),
            assignee_id=assignee_id,
            auto_assigned=selection["auto_assigned"],
        )


async def handle_tickets_archive(request: web.Request) -> web.Response:
    """POST /api/tickets/archive — пометить закрытые тикеты как архивные (скрыть из веб-очереди)."""
    data = await _read_json(request)
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    ticket_ids = data.get("ticket_ids") or []
    if not isinstance(ticket_ids, list) or not ticket_ids:
        return _validation_error({"ticket_ids": "ticket_ids (array) is required"})
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        archived = 0
        for ticket_id in ticket_ids[:100]:
            ticket_id = str(ticket_id).strip()
            if not ticket_id:
                continue
            ticket = await repo.get_ticket(ticket_id)
            if ticket is None:
                continue
            status = (getattr(ticket, "status", None) or "").lower()
            if status != "closed":
                continue
            await repo.update_ticket(ticket_id, archived_at=now)
            archived += 1
        await session.commit()
    return _json_ok(archived=archived)


async def handle_tickets_bulk_assign(request: web.Request) -> web.Response:
    """POST /api/tickets/bulk_assign — назначить исполнителя на до 3 тикетов (только не закрытые)."""
    data = await _read_json(request)
    auth_context = _auth(request)
    if not _is_staff(auth_context):
        return _json_error("forbidden", status=403)
    ticket_ids = data.get("ticket_ids") or []
    assignee_id = (data.get("assignee_id") or "").strip()
    if not assignee_id:
        return _validation_error({"assignee_id": "assignee_id is required"})
    if not isinstance(ticket_ids, list):
        return _validation_error({"ticket_ids": "ticket_ids must be an array"})
    if len(ticket_ids) > 3:
        return _json_error("Максимум 3 тикета для массового назначения", status=400)
    if not ticket_ids:
        return _json_ok(assigned=0)
    async with get_session() as session:
        repo = TicketEventsRepo(session)
        assignment_service = TicketAssignmentService(repo)
        assigned = 0
        for ticket_id in ticket_ids:
            ticket_id = str(ticket_id).strip()
            if not ticket_id:
                continue
            ticket = await repo.get_ticket(ticket_id)
            if ticket is None:
                continue
            status = (getattr(ticket, "status", None) or "").lower()
            if status in ("closed", "resolved"):
                continue
            try:
                selection = await assignment_service.resolve_assignee(
                    ticket,
                    requested_assignee_id=assignee_id,
                    auto_assign=False,
                )
            except TicketAssignmentError:
                continue
            aid = selection["assignee_id"]
            await assignment_service.assign_ticket(
                ticket.ticket_id,
                ticket.device_id,
                aid,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                reason="bulk_assign",
                comment=None,
                old_assignee=getattr(ticket, "assignee_id", None),
                auto_assigned=False,
                active_count=selection["active_count"],
                limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                db_session=session,
                close_ola=True,
            )
            assigned += 1
        await session.commit()
    return _json_ok(assigned=assigned)


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
        previous_device_id = ticket.device_id
        devices_repo = DevicesRepo(session)
        device = await devices_repo.get_by_device_id(device_id)
        if device is None:
            return _validation_error({"device_id": "unknown device_id"})
        custom_fields = mark_public_ticket_unbound(getattr(ticket, "custom_fields", None), False)
        await repo.update_ticket(ticket.ticket_id, device_id=device_id, custom_fields=custom_fields)
        payload = {
            "previous_device_id": previous_device_id,
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
    data = await _read_json(request)
    request["_requester_account_payload"] = data
    try:
        last_read_event_id = int(data.get("last_read_event_id") or 0)
    except (TypeError, ValueError):
        return _validation_error({"last_read_event_id": "last_read_event_id must be a positive integer"})
    if last_read_event_id <= 0:
        return _validation_error({"last_read_event_id": "last_read_event_id must be a positive integer"})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        read_scope = _read_scope_from_auth(auth_context)
        target_event = await repo.get_event_by_id(ticket.ticket_id, last_read_event_id)
        if target_event is None:
            return _validation_error({"last_read_event_id": "event not found in this ticket"})
        if read_scope == "requester" and not _event_visible_to_requester(target_event):
            return _validation_error({"last_read_event_id": "event is not visible to requester"})

        current_cursor = await repo.get_latest_message_read_cursor(ticket.ticket_id, read_scope)
        current_last_read_id = int(current_cursor.get("last_read_event_id") or 0)
        if current_last_read_id >= last_read_event_id:
            return _json_ok(
                no_op=True,
                last_read_event_id=current_last_read_id,
                last_read_message_id=current_cursor.get("last_read_message_id"),
                messages_read_count=0,
                tool_calls_read_count=0,
                message_preview=current_cursor.get("message_preview"),
            )

        summary = await repo.summarize_read_window(
            ticket_id=ticket.ticket_id,
            scope=read_scope,
            from_event_id=current_last_read_id,
            to_event_id=last_read_event_id,
        )
        payload = {
            "actor_id": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
            "read_scope": read_scope,
            "last_read_event_id": last_read_event_id,
            "last_read_message_id": summary.get("last_read_message_id"),
            "messages_read_count": int(summary.get("messages_read_count") or 0),
            "tool_calls_read_count": int(summary.get("tool_calls_read_count") or 0),
            "message_preview": summary.get("message_preview"),
        }
        account_session = request.get("_validated_account_session")
        if isinstance(account_session, dict):
            payload.update(
                {
                    "requester_account_session_id": account_session.get("session_id"),
                    "requester_account_mode": account_session.get("account_mode"),
                    "requester_person_id": account_session.get("person_id"),
                    "requester_binding_id": account_session.get("binding_id"),
                    "created_from_other_account": account_session.get("account_mode") == "verified_other_account",
                }
            )
        result = await repo.add_event(
            ticket_id=ticket.ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="message_read",
            payload=payload,
            trace_id=str(uuid.uuid4()),
            event_id=f"message_read:{read_scope}:{last_read_event_id}",
        )
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "message_read", payload)
        return _json_ok(
            event_id=result[0] if result else None,
            no_op=False,
            last_read_event_id=last_read_event_id,
            last_read_message_id=summary.get("last_read_message_id"),
            messages_read_count=int(summary.get("messages_read_count") or 0),
            tool_calls_read_count=int(summary.get("tool_calls_read_count") or 0),
            message_preview=summary.get("message_preview"),
        )


async def handle_ticket_requester_profile(request: web.Request) -> web.Response:
    data = await _read_json(request)
    user_display_name = str(data.get("user_display_name") or "").strip()
    reroute_requested = bool(data.get("reroute"))
    try:
        requester_profile = normalize_requester_profile(data.get("requester_profile"))
    except ValueError as exc:
        return _validation_error({"requester_profile": str(exc)})

    async with get_session() as session:
        ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        routing_events: List[tuple[str, Dict[str, Any], Optional[tuple]]] = []
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
        if reroute_requested and _is_staff(auth_context):
            routing = TicketRoutingService(session, repo, DevicesRepo(session))
            previous_queue_id = getattr(ticket, "queue_id", None)

            async def capture(ticket_id: str, device_id: str, event_type: str, event_payload: Dict[str, Any]) -> None:
                event_result = await repo.add_event(
                    ticket_id=ticket_id,
                    device_id=device_id,
                    agent_seq=None,
                    event_type=event_type,
                    payload=event_payload,
                    trace_id=str(uuid.uuid4()),
                )
                routing_events.append((event_type, event_payload, event_result))

            await routing.apply_routing(
                ticket.ticket_id,
                ticket.device_id,
                force_clear_lock=True,
                add_events_fn=capture,
            )
            ticket = await repo.get_ticket(ticket.ticket_id)
            try:
                await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
                await start_ola_for_ticket(session, ticket, trigger="queue_changed")
            except Exception as exc:
                logger.warning(f"[requester_profile] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
            if getattr(ticket, "queue_id", None) != previous_queue_id:
                ticket, queue_events = await _reconcile_queue_scope_state(
                    session,
                    repo,
                    ticket,
                    actor_id=auth_context.actor_id,
                    actor_role=auth_context.actor_role,
                    reason_prefix="requester_profile_reroute",
                )
                routing_events.extend(queue_events)
        await session.commit()
        await _push_ticket_event(request, ticket.ticket_id, result, "requester_profile_changed", payload)
        for event_type, event_payload, event_result in routing_events:
            await _push_ticket_event(request, ticket.ticket_id, event_result, event_type, event_payload)
        ticket = await repo.get_ticket(ticket.ticket_id)
        return _json_ok(ticket=await _ticket_payload(session, ticket, include_assignment_context=True))


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
            sla_paused_at=ticket.sla_paused_at.isoformat() if ticket.sla_paused_at else None,
            sla_paused_seconds=ticket.sla_paused_seconds,
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
        if str(data.get("source") or "") == "knowledge_support_workspace":
            await AgentRuntimeAuditRepo(session).add(
                device_id="server",
                event_type="knowledge.support.ticket_linked",
                severity="info",
                source="knowledge_support",
                ticket_id=ticket.ticket_id,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                details_json={
                    "kb_link_id": kb_link.id,
                    "article_ref": article_ref,
                    "source": "knowledge_support_workspace",
                },
            )
        await session.commit()
        return _json_ok(kb_link=_serialize_ticket_kb_link(kb_link))


async def handle_ticket_kb_links_list(request: web.Request) -> web.Response:
    async with get_session() as session:
        ticket, error, repo, _ = await _get_ticket_or_response(request, session, write=False)
        if error:
            return error
        kb_links = await repo.list_kb_links(ticket.ticket_id)
        return _json_ok(kb_links=[_serialize_ticket_kb_link(kb_link) for kb_link in kb_links])


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
        return _json_ok(
            preferences={
                "actor_id": pref.actor_id,
                "mute_internal": bool(pref.mute_internal),
                "muted_event_types": pref.muted_event_types if isinstance(pref.muted_event_types, list) else [],
                "suppress_self": bool(pref.suppress_self),
            }
        )


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
