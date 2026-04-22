import json
import uuid

from aiohttp import web
from loguru import logger

from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.repos import DevicesRepo, NotificationRepo, OperationsRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from auth.middleware import require_auth
from observer.service import ObserverOverlayService
from tickets.handlers import (
    RESOLUTION_CONFIRMATION_TEXT,
    _build_resolution_confirmation_request,
    _chat_counters_by_ticket_ids,
    _get_ticket_or_response,
    _message_role_from_auth,
    _push_ticket_event,
    _queue_code_map,
    _resolution_confirmation_pending,
    _serialize_message,
    _store_resolution_confirmation_state,
    _ticket_payload,
    _ticket_presence_payload,
)
from tickets.statuses import (
    CANONICAL_STATUSES,
    enrich_chat_payload_with_requester_name,
    normalize_status,
    resolve_status,
    status_label_ru,
)
from tickets.sla_service import TicketSlaService
from tickets.workflow_service import TicketWorkflowService, validate_transition
from tools.service import ToolExecutionService
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.support import (
    SupportBootstrapPayload,
    SupportCountItem,
    SupportFilterOption,
    SupportMessageActionResult,
    SupportObserverCapabilities,
    SupportQueueFilters,
    SupportQueuePayload,
    SupportQueueSummary,
    SupportQueueTicketItem,
    SupportStatusAction,
    SupportStatusActionResult,
    SupportTicketActions,
    SupportTicketDetail,
    SupportTicketDetailPayload,
    SupportTicketDeviceSnapshot,
    SupportTicketMessage,
    SupportTicketObserverPayload,
    SupportTicketObserverSummary,
    SupportTicketOperationSnapshot,
    SupportTicketPresence,
    SupportTicketQueueInfo,
    SupportTicketQueueMember,
    SupportTicketReplyTo,
    SupportTicketSnapshot,
    SupportTicketToolsPayload,
    SupportToolActionResult,
    SupportToolItem,
    SupportToolParameter,
    SupportToolPreset,
)


SCOPE_OPTIONS = [
    SupportFilterOption(value="all", label="Все доступные"),
    SupportFilterOption(value="mine", label="Только мои"),
]

QUICK_STATUS_ACTIONS = [
    ("in_progress", "Взять в работу"),
    ("waiting_on_user", "Ждём пользователя"),
    ("resolved", "Решено"),
]


def _normalize_scope(raw_scope: str | None) -> str:
    return "mine" if raw_scope == "mine" else "all"


def _normalize_status_filter(raw_status: str | None) -> str:
    if not raw_status or raw_status == "all":
        return "all"
    normalized, _ = normalize_status(raw_status)
    return normalized or "all"


def _build_status_options(statuses: set[str]) -> list[SupportFilterOption]:
    options = [SupportFilterOption(value="all", label="Все статусы")]
    for status in CANONICAL_STATUSES:
        if status in statuses:
            options.append(SupportFilterOption(value=status, label=status_label_ru(status)))
    for status in sorted(status for status in statuses if status not in CANONICAL_STATUSES):
        options.append(SupportFilterOption(value=status, label=status_label_ru(status)))
    return options


def _build_empty_queue_payload(*, scope: str, query: str, status_filter: str) -> SupportQueuePayload:
    return SupportQueuePayload(
        scope=scope,
        query=query,
        status_filter=status_filter,
        summary=SupportQueueSummary(
            visible_count=0,
            selected_ticket_id=None,
            scope_counts=[
                SupportCountItem(value="all", label="Все доступные", count=0),
                SupportCountItem(value="mine", label="Только мои", count=0),
            ],
            status_counts=[SupportCountItem(value="all", label="Все статусы", count=0)],
        ),
        filters=SupportQueueFilters(
            scope_options=SCOPE_OPTIONS,
            status_options=[SupportFilterOption(value="all", label="Все статусы")],
        ),
        tickets=[],
    )


def _build_ticket_item(ticket_data: dict) -> SupportQueueTicketItem:
    unread_messages = int(
        ticket_data.get("support_pending_user_messages")
        or ticket_data.get("support_unread_user_messages")
        or 0
    )
    return SupportQueueTicketItem(
        ticket_id=str(ticket_data.get("ticket_id") or ""),
        ticket_code=ticket_data.get("ticket_code"),
        title=str(ticket_data.get("title") or "Без названия"),
        status=str(ticket_data.get("status") or "unknown"),
        status_label=status_label_ru(ticket_data.get("status")),
        queue_code=ticket_data.get("queue_code"),
        assignee_id=ticket_data.get("assignee_id"),
        requester_display_name=ticket_data.get("requester_display_name"),
        device_id=ticket_data.get("device_id"),
        updated_at=ticket_data.get("updated_at"),
        created_at=ticket_data.get("created_at"),
        requires_operator_action=bool(ticket_data.get("requires_operator_action")),
        unread_user_messages=unread_messages,
    )


def _matches_ticket_query(ticket: SupportQueueTicketItem, query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True
    haystack = (
        ticket.ticket_code,
        ticket.title,
        ticket.status_label,
        ticket.queue_code,
        ticket.assignee_id,
        ticket.requester_display_name,
        ticket.device_id,
    )
    return any(normalized in str(value or "").lower() for value in haystack)


def _build_scope_counts(items: list[SupportQueueTicketItem], actor_id: str) -> list[SupportCountItem]:
    mine_count = sum(1 for item in items if str(item.assignee_id or "").strip() == actor_id)
    return [
        SupportCountItem(value="all", label="Все доступные", count=len(items)),
        SupportCountItem(value="mine", label="Только мои", count=mine_count),
    ]


def _build_status_counts(items: list[SupportQueueTicketItem]) -> list[SupportCountItem]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1

    result = [SupportCountItem(value="all", label="Все статусы", count=len(items))]
    for status in CANONICAL_STATUSES:
        if status in counts:
            result.append(
                SupportCountItem(
                    value=status,
                    label=status_label_ru(status),
                    count=counts[status],
                )
            )
    for status in sorted(status for status in counts if status not in CANONICAL_STATUSES):
        result.append(
            SupportCountItem(
                value=status,
                label=status_label_ru(status),
                count=counts[status],
            )
        )
    return result


def _build_support_status_actions(ticket_status: str | None, *, is_staff: bool) -> SupportTicketActions:
    if not is_staff:
        return SupportTicketActions(status_options=[], can_send_internal_note=False)

    current_status = str(ticket_status or "")
    options = [
        SupportStatusAction(value=value, label=label)
        for value, label in QUICK_STATUS_ACTIONS
        if value != current_status and validate_transition(current_status, value, True)
    ]
    return SupportTicketActions(
        status_options=options,
        can_send_internal_note=True,
    )


def _tool_result_preview(payload: dict) -> str | None:
    raw_preview = payload.get("result")
    if raw_preview is None:
        raw_preview = payload.get("observations")
    if raw_preview is None:
        return None
    if isinstance(raw_preview, (dict, list)):
        return json.dumps(raw_preview, ensure_ascii=False)[:300]
    return str(raw_preview)[:300]


def _event_timestamp_iso(event: object, payload: dict) -> str | None:
    created_at = getattr(event, "created_at", None)
    if created_at is not None:
        try:
            return created_at.isoformat()
        except Exception:
            pass
    raw_ts = payload.get("ts")
    return str(raw_ts) if raw_ts else None


def _build_timeline_message(event: object, ticket: object | None = None) -> SupportTicketMessage:
    raw_message = _serialize_message(event, ticket=ticket)
    metadata = raw_message.get("metadata") or {}
    sender_display_name = None
    if isinstance(metadata, dict):
        sender_display_name = metadata.get("sender_display_name") or metadata.get("requester_display_name")
    payload = getattr(event, "payload", None) or {}
    if not sender_display_name and isinstance(payload, dict):
        sender_display_name = payload.get("sender_display_name") or payload.get("requester_display_name")
    reply_to = raw_message.get("reply_to")
    return SupportTicketMessage(
        message_id=raw_message.get("message_id"),
        event_id=raw_message.get("event_id"),
        event_type="chat_message",
        from_role=str(raw_message.get("from_role") or "user"),
        sender_display_name=sender_display_name,
        text=str(raw_message.get("text") or ""),
        ts=raw_message.get("ts"),
        visibility=str(raw_message.get("visibility") or "public"),
        direction=str(raw_message.get("direction") or "to_agent"),
        attachments=list(raw_message.get("attachments") or []),
        reply_to=SupportTicketReplyTo.model_validate(reply_to) if isinstance(reply_to, dict) else None,
        tool_name=None,
        tool_status=None,
        result_summary=None,
        result_preview=None,
    )


def _build_timeline_entry(event: object, ticket: object | None = None) -> SupportTicketMessage:
    event_type = str(getattr(event, "event_type", None) or "")
    payload = getattr(event, "payload", None) or {}

    if event_type == "chat_message":
        return _build_timeline_message(event, ticket=ticket)

    if event_type == "tool_call_started":
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Инструмент")
        return SupportTicketMessage(
            message_id=None,
            event_id=getattr(event, "id", None),
            event_type=event_type,
            from_role="system",
            sender_display_name="Система",
            text=f"Запуск инструмента: {tool_name}",
            ts=_event_timestamp_iso(event, payload),
            visibility="system",
            direction="system",
            attachments=[],
            reply_to=None,
            tool_name=tool_name,
            tool_status="accepted",
            result_summary=None,
            result_preview=None,
        )

    if event_type == "tool_call_result":
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Инструмент")
        return SupportTicketMessage(
            message_id=None,
            event_id=getattr(event, "id", None),
            event_type=event_type,
            from_role="system",
            sender_display_name="Система",
            text=f"Результат инструмента: {tool_name}",
            ts=_event_timestamp_iso(event, payload),
            visibility="system",
            direction="system",
            attachments=list(payload.get("artifacts") or []),
            reply_to=None,
            tool_name=tool_name,
            tool_status=str(payload.get("status") or "unknown"),
            result_summary=str(payload.get("summary") or payload.get("error") or "Без краткого результата"),
            result_preview=_tool_result_preview(payload),
        )

    return SupportTicketMessage(
        message_id=None,
        event_id=getattr(event, "id", None),
        event_type=event_type or "system",
        from_role="system",
        sender_display_name="Система",
        text=event_type or "Системное событие",
        ts=_event_timestamp_iso(event, payload),
        visibility="system",
        direction="system",
        attachments=[],
        reply_to=None,
        tool_name=None,
        tool_status=None,
        result_summary=None,
        result_preview=None,
    )


def _normalize_tool_schema(raw_schema: object) -> list[SupportToolParameter]:
    if not raw_schema:
        return []

    entries: list[dict] = []
    if isinstance(raw_schema, list):
        entries = [item for item in raw_schema if isinstance(item, dict)]
    elif isinstance(raw_schema, dict) and isinstance(raw_schema.get("properties"), dict):
        required = {
            str(name)
            for name in (raw_schema.get("required") or [])
            if str(name or "").strip()
        }
        for name, descriptor in raw_schema["properties"].items():
            field_descriptor = descriptor if isinstance(descriptor, dict) else {"default": descriptor}
            entries.append(
                {
                    "name": name,
                    "required": name in required,
                    **field_descriptor,
                }
            )
    elif isinstance(raw_schema, dict):
        for name, descriptor in raw_schema.items():
            field_descriptor = descriptor if isinstance(descriptor, dict) else {"default": descriptor}
            entries.append({"name": name, **field_descriptor})

    normalized: list[SupportToolParameter] = []
    for entry in entries:
        field_name = str(entry.get("name") or "").strip()
        if not field_name:
            continue
        normalized.append(
            SupportToolParameter(
                name=field_name,
                label=entry.get("title") or entry.get("label"),
                description=entry.get("description"),
                type=str(entry.get("type") or "string"),
                required=bool(entry.get("required")),
                default=entry.get("default"),
            )
        )
    return normalized


def _normalize_tool_presets(raw_presets: object) -> list[SupportToolPreset]:
    if not isinstance(raw_presets, list):
        return []
    presets: list[SupportToolPreset] = []
    for preset in raw_presets:
        if not isinstance(preset, dict):
            continue
        preset_id = str(
            preset.get("preset_id") or preset.get("id") or preset.get("key") or ""
        ).strip()
        if not preset_id:
            continue
        label = str(preset.get("title") or preset.get("name") or preset_id).strip()
        presets.append(SupportToolPreset(preset_id=preset_id, label=label))
    return presets


def _normalize_support_tool_entry(raw_tool: object, *, source: str) -> SupportToolItem | None:
    if not isinstance(raw_tool, dict):
        return None
    tool_name = str(raw_tool.get("tool") or raw_tool.get("name") or "").strip()
    if not tool_name:
        return None
    spec = raw_tool.get("spec") if isinstance(raw_tool.get("spec"), dict) else {}
    metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else {}
    params_schema = spec.get("params_schema") if spec else raw_tool.get("params_schema")
    presets = spec.get("presets") if spec else raw_tool.get("presets")
    module_name = raw_tool.get("module")
    if not module_name and "." in tool_name:
        module_name = tool_name.split(".", 1)[0]
    return SupportToolItem(
        tool_name=tool_name,
        module_name=str(module_name).strip() if module_name else None,
        description=str(raw_tool.get("description") or "").strip() or None,
        risk_level=str(spec.get("risk_level") or metadata.get("risk_level") or "safe_read"),
        requires_consent=bool(metadata.get("requires_consent")),
        install_required=bool(raw_tool.get("install_required")),
        source=source,
        params_schema=_normalize_tool_schema(params_schema),
        presets=_normalize_tool_presets(presets),
    )


async def _build_support_tools_payload(ticket: object, tool_service: ToolExecutionService) -> SupportTicketToolsPayload:
    device_id = getattr(ticket, "device_id", None)
    if not device_id:
        return SupportTicketToolsPayload(
            ticket_id=str(getattr(ticket, "ticket_id", "") or ""),
            device_id=None,
            tools=[],
        )

    device_tools_raw = await tool_service.get_tools_list(device_id) or []
    server_tools_raw = await tool_service.get_tools_from_server(device_id) or []

    tools: list[SupportToolItem] = []
    seen: set[str] = set()
    for source, raw_items in (("device", device_tools_raw), ("server", server_tools_raw)):
        for raw_item in raw_items:
            item = _normalize_support_tool_entry(raw_item, source=source)
            if item is None or item.tool_name in seen:
                continue
            seen.add(item.tool_name)
            tools.append(item)

    return SupportTicketToolsPayload(
        ticket_id=str(getattr(ticket, "ticket_id", "") or ""),
        device_id=str(device_id),
        tools=tools,
    )


async def _build_support_snapshot(request: web.Request, session, ticket, auth_context) -> SupportTicketSnapshot:
    presence = SupportTicketPresence.model_validate(_ticket_presence_payload(request, ticket))
    notification_unread = await NotificationRepo(session).unread_count(auth_context.actor_id)

    device = None
    if getattr(ticket, "device_id", None):
        device = await DevicesRepo(session).get_by_device_id(ticket.device_id)

    device_snapshot = SupportTicketDeviceSnapshot(
        device_id=getattr(ticket, "device_id", None),
        hostname=getattr(device, "hostname", None) if device is not None else None,
        os=getattr(device, "os", None) if device is not None else None,
        agent_version=getattr(device, "agent_version", None) if device is not None else None,
        last_seen_at=(device.last_seen_at.isoformat() if device is not None and device.last_seen_at else None),
        online=bool(presence.agent_online),
    )

    latest_operations: list[SupportTicketOperationSnapshot] = []
    if getattr(ticket, "device_id", None):
        recent_operations = await OperationsRepo(session).get_recent_operations(
            device_id=ticket.device_id,
            limit=5,
        )
        for operation in recent_operations:
            latest_operations.append(
                SupportTicketOperationSnapshot(
                    operation_id=operation.operation_id,
                    kind=operation.kind,
                    status=operation.status,
                    tool_name=operation.tool_name,
                    command_name=operation.command_name,
                    queued_at=operation.queued_at.isoformat() if operation.queued_at else None,
                    finished_at=operation.finished_at.isoformat() if operation.finished_at else None,
                    result_summary=operation.result_summary,
                    error_message=operation.error_message,
                )
            )

    events = await TicketEventsRepo(session).get_events(ticket.ticket_id, since_agent_seq=None, limit=200)
    last_event_id = int(getattr(events[-1], "id", 0) or 0) if events else 0
    return SupportTicketSnapshot(
        last_event_id=last_event_id,
        notification_unread=int(notification_unread or 0),
        presence=presence,
        device=device_snapshot,
        latest_operations=latest_operations,
    )


async def _build_support_detail_payload(request: web.Request, session, ticket, repo, auth_context) -> SupportTicketDetailPayload:
    chat_counters = await _chat_counters_by_ticket_ids(repo, [ticket.ticket_id])
    ticket_data = await _ticket_payload(
        session,
        ticket,
        chat_counters=chat_counters.get(ticket.ticket_id),
        include_assignment_context=True,
    )
    observer_data = await ObserverOverlayService(session).get_ticket_observer_summary(ticket.ticket_id)
    events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=80)
    timeline = [
        _build_timeline_entry(event, ticket=ticket)
        for event in reversed(
            [
                item
                for item in events
                if getattr(item, "event_type", None) in {"chat_message", "tool_call_started", "tool_call_result"}
            ]
        )
    ]

    queue_name = None
    ticket_queue_id = ticket_data.get("queue_id")
    for queue in ticket_data.get("available_queues", []):
        if queue.get("id") == ticket_queue_id:
            queue_name = queue.get("name")
            break

    snapshot = await _build_support_snapshot(request, session, ticket, auth_context)
    actions = _build_support_status_actions(
        ticket_data.get("status"),
        is_staff=auth_context.actor_role in {"admin", "support"},
    )

    return SupportTicketDetailPayload(
        ticket=SupportTicketDetail(
            ticket_id=str(ticket_data.get("ticket_id") or ""),
            ticket_code=ticket_data.get("ticket_code"),
            title=str(ticket_data.get("title") or "Без названия"),
            description=ticket_data.get("description"),
            status=str(ticket_data.get("status") or "unknown"),
            status_label=status_label_ru(ticket_data.get("status")),
            requester_display_name=ticket_data.get("requester_display_name"),
            device_id=ticket_data.get("device_id"),
            queue=SupportTicketQueueInfo(
                id=ticket_queue_id,
                code=ticket_data.get("queue_code"),
                name=queue_name,
            ),
            assignee_id=ticket_data.get("assignee_id"),
            updated_at=ticket_data.get("updated_at"),
            created_at=ticket_data.get("created_at"),
            queue_members=[
                SupportTicketQueueMember(
                    actor_id=str(member.get("actor_id") or ""),
                    role_in_queue=member.get("role_in_queue"),
                )
                for member in ticket_data.get("queue_members", [])
                if member.get("actor_id")
            ],
        ),
        observer=SupportTicketObserverPayload(
            ticket_summary_endpoint=f"/api/tickets/{ticket.ticket_id}/observer",
            summary=SupportTicketObserverSummary.model_validate(observer_data.get("summary", {})),
        ),
        timeline=timeline,
        snapshot=snapshot,
        actions=actions,
    )


@require_auth("admin", "support")
async def handle_web_support_bootstrap(_request):
    payload = SupportBootstrapPayload(
        workspace="support",
        features=[
            "queue_overview",
            "ticket_workspace",
            "observer_trace",
            "tool_actions",
        ],
        observer=SupportObserverCapabilities(
            ticket_summary_endpoint="/api/tickets/{ticket_id}/observer",
            drawer_tab="trace",
        ),
    )
    return json_model_response(SuccessResponse[SupportBootstrapPayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_queue(request: web.Request):
    auth_context = request["auth_context"]
    scope = _normalize_scope(request.query.get("scope"))
    status_filter = _normalize_status_filter(request.query.get("status"))
    query = str(request.query.get("query", "") or "").strip()
    limit = min(max(int(request.query.get("limit", "200")), 1), 300)

    filters: dict[str, object] = {"exclude_archived": True}
    if auth_context.actor_role == "support":
        filters["support_actor_id"] = auth_context.actor_id

    try:
        async with get_session() as session:
            repo = TicketEventsRepo(session)
            tickets = await repo.list_tickets(
                order_by="updated_at",
                order_direction="desc",
                limit=limit,
                filters=filters,
            )
            queue_map = await _queue_code_map(
                session,
                [getattr(ticket, "queue_id", None) for ticket in tickets],
            )
            counters_map = await _chat_counters_by_ticket_ids(
                repo,
                [getattr(ticket, "ticket_id", None) for ticket in tickets],
            )

            accessible_items: list[SupportQueueTicketItem] = []
            for ticket in tickets:
                ticket_data = ticket_to_dict(ticket, queue_map.get(getattr(ticket, "queue_id", None)))
                ticket_data.update(counters_map.get(getattr(ticket, "ticket_id", None), {}))
                accessible_items.append(_build_ticket_item(ticket_data))

        scope_counts = _build_scope_counts(accessible_items, auth_context.actor_id)
        status_counts = _build_status_counts(accessible_items)
        status_values = {item.status for item in accessible_items if item.status}

        scoped_items = (
            [
                item
                for item in accessible_items
                if str(item.assignee_id or "").strip() == auth_context.actor_id
            ]
            if scope == "mine"
            else accessible_items
        )
        status_filtered_items = (
            [item for item in scoped_items if item.status == status_filter]
            if status_filter != "all"
            else scoped_items
        )
        typed_items = [item for item in status_filtered_items if _matches_ticket_query(item, query)]

        payload = SupportQueuePayload(
            scope=scope,
            query=query,
            status_filter=status_filter,
            summary=SupportQueueSummary(
                visible_count=len(typed_items),
                selected_ticket_id=typed_items[0].ticket_id if typed_items else None,
                scope_counts=scope_counts,
                status_counts=status_counts,
            ),
            filters=SupportQueueFilters(
                scope_options=SCOPE_OPTIONS,
                status_options=_build_status_options(status_values),
            ),
            tickets=typed_items,
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_queue] DB unavailable, returning empty queue payload: "
            f"scope={scope}, actor_id={auth_context.actor_id}, error={exc}"
        )
        payload = _build_empty_queue_payload(
            scope=scope,
            query=query,
            status_filter=status_filter,
        )
    return json_model_response(SuccessResponse[SupportQueuePayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_ticket_detail(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await _build_support_detail_payload(request, session, ticket, repo, auth_context)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_detail] DB unavailable for ticket detail: "
            f"ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Карточка тикета временно недоступна без базы данных",
                "error_code": "DB_UNAVAILABLE",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketDetailPayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_ticket_tools(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await _build_support_tools_payload(
                ticket,
                ToolExecutionService(request.app["state"]),
            )
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_tools] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить инструменты для нового workspace",
                "error_code": "TOOL_INVENTORY_UNAVAILABLE",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketToolsPayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_send_message(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Некорректный JSON"},
            status=400,
        )
    if not isinstance(data, dict):
        return web.json_response(
            {"status": "error", "error": "Тело запроса должно быть объектом"},
            status=400,
        )

    text = str(data.get("text") or "").strip()
    if not text:
        return web.json_response(
            {"status": "error", "error": "Нужно передать текст сообщения"},
            status=400,
        )

    visibility = str(data.get("visibility") or "public").strip().lower() or "public"
    if visibility not in {"public", "internal"}:
        visibility = "public"

    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
            if error:
                return error

            sender_role = _message_role_from_auth(auth_context)
            message_id = str(uuid.uuid4())
            payload = {
                "message_id": message_id,
                "sender_role": sender_role,
                "sender_display_name": auth_context.actor_id,
                "from": sender_role,
                "text": text,
                "visibility": visibility,
            }
            payload = enrich_chat_payload_with_requester_name(ticket, payload)
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
                await TicketSlaService(session, repo).close_frt(ticket.ticket_id)
            await session.commit()

        await _push_ticket_event(request, ticket.ticket_id, result, "chat_message", payload)
        message = SupportTicketMessage(
            message_id=message_id,
            event_id=int(result[0]) if result and result[0] is not None else None,
            from_role=sender_role,
            sender_display_name=auth_context.actor_id,
            text=text,
            ts=result[1].isoformat() if result and result[1] is not None else None,
            visibility=visibility,
            direction="to_agent",
            attachments=[],
            reply_to=None,
        )
        return json_model_response(
            SuccessResponse[SupportMessageActionResult](
                data=SupportMessageActionResult(
                    ticket_id=ticket.ticket_id,
                    message=message,
                )
            )
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_send_message] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось отправить сообщение из нового workspace",
                "error_code": "MESSAGE_ACTION_FAILED",
            },
            status=503,
        )


@require_auth("admin", "support")
async def handle_web_support_change_status(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Некорректный JSON"},
            status=400,
        )
    if not isinstance(data, dict):
        return web.json_response(
            {"status": "error", "error": "Тело запроса должно быть объектом"},
            status=400,
        )

    raw_to_status = str(data.get("to_status") or "").strip()
    to_status, _ = resolve_status(raw_to_status)
    if not to_status:
        return web.json_response(
            {"status": "error", "error": "Некорректный целевой статус"},
            status=400,
        )

    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
            if error:
                return error

            is_staff = auth_context.actor_role in {"admin", "support"}
            if not validate_transition(ticket.status, to_status, is_staff):
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Переход статуса недоступен",
                        "error_code": "INVALID_TRANSITION",
                    },
                    status=400,
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
                source="web_support_api",
            )
            followup_result = None
            followup_payload = None
            ticket = await repo.get_ticket(ticket.ticket_id)
            if ticket is None:
                return web.json_response(
                    {"status": "error", "error": "Тикет не найден после обновления"},
                    status=404,
                )

            if to_status == "resolved" and is_staff:
                confirmation_request = _build_resolution_confirmation_request()
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

        return json_model_response(
            SuccessResponse[SupportStatusActionResult](
                data=SupportStatusActionResult(
                    ticket_id=ticket.ticket_id,
                    status=to_status,
                    status_label=status_label_ru(to_status),
                )
            )
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_change_status] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось обновить статус из нового workspace",
                "error_code": "STATUS_ACTION_FAILED",
            },
            status=503,
        )


@require_auth("admin", "support")
async def handle_web_support_run_tool(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Некорректный JSON"},
            status=400,
        )
    if not isinstance(data, dict):
        return web.json_response(
            {"status": "error", "error": "Тело запроса должно быть объектом"},
            status=400,
        )

    tool_name = str(data.get("tool_name") or "").strip()
    if not tool_name:
        return web.json_response(
            {"status": "error", "error": "Нужно передать имя инструмента"},
            status=400,
        )

    raw_params = data.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    preset_id = str(data.get("preset_id") or "").strip() or None

    try:
        async with get_session() as session:
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=True)
            if error:
                return error

            device_id = str(getattr(ticket, "device_id", "") or "").strip()
            if not device_id:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Тикет не привязан к устройству, инструмент не запустить",
                        "error_code": "DEVICE_REQUIRED",
                    },
                    status=400,
                )

            operation_id = str(uuid.uuid4())
            params_with_operation = {"_operation_id": operation_id}
            if preset_id:
                params_with_operation["preset_id"] = preset_id
            else:
                params_with_operation.update(params)

            result = await ToolExecutionService(request.app["state"]).run_tool(
                device_id=device_id,
                ticket_id=ticket.ticket_id,
                tool_name=tool_name,
                params=params_with_operation,
                call_id=str(uuid.uuid4()),
                auth_context=auth_context,
                wait_for_result=False,
            )
    except Exception as exc:
        logger.warning(
            f"[web_support_run_tool] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось запустить инструмент из нового workspace",
                "error_code": "TOOL_ACTION_FAILED",
            },
            status=503,
        )

    dispatch_status = str(result.get("status") or "accepted")
    if dispatch_status not in {"accepted", "waiting_consent"}:
        return web.json_response(
            {
                "status": "error",
                "error": str(result.get("error") or "Не удалось поставить инструмент в очередь"),
                "error_code": str(result.get("error_code") or "TOOL_ACTION_FAILED"),
            },
            status=503,
        )

    resolved_operation_id = str(result.get("operation_id") or operation_id)
    payload = SupportToolActionResult(
        ticket_id=ticket.ticket_id,
        device_id=device_id,
        tool_name=tool_name,
        dispatch_status=dispatch_status,
        operation_id=resolved_operation_id,
        poll_url=str(result.get("poll_url") or f"/api/operations/{resolved_operation_id}"),
        trace_id=result.get("trace_id"),
        message=(
            "Операция ожидает согласование"
            if dispatch_status == "waiting_consent"
            else "Инструмент поставлен в очередь выполнения"
        ),
    )
    return json_model_response(
        SuccessResponse[SupportToolActionResult](data=payload),
        status=202,
    )
