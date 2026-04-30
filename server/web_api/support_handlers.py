import json
import uuid

from aiohttp import web
from loguru import logger
from sqlalchemy import func, select

from access_control.service import can
from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.db.models import Playbook, PlaybookStep, PlaybookVersion, TicketResolutionPassport
from app.repos import DevicesRepo, NotificationRepo, OperationsRepo
from app.repos.registry_repo import RegistryRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.ticket_passport_repo import TicketPassportRepo
from app.services.playbook_engine import start_run
from auth.middleware import require_auth
from observer.service import ObserverOverlayService
from playbooks.tool_catalog import expand_preset_params, normalize_tool_catalog_entry
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
from tickets.passport_service import TicketPassportService
from tickets.workflow_service import TicketWorkflowService, validate_transition_for_ticket
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
    SupportTicketPassportDetailPayload,
    SupportTicketPassportEvidenceRequest,
    SupportTicketPassportGenerateRequest,
    SupportTicketPassportPatchRequest,
    SupportTicketPlaybooksPayload,
    SupportTicketPresence,
    SupportTicketQueueInfo,
    SupportTicketQueueMember,
    SupportTicketRegistrySnapshot,
    SupportTicketRequestFormPayload,
    SupportTicketRequestFormRow,
    SupportTicketReplyTo,
    SupportTicketSnapshot,
    SupportTicketToolsPayload,
    SupportTicketKnowledgeDraftPayload,
    SupportPlaybookItem,
    SupportPlaybookRunActionResult,
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
    ("queued", "В очередь"),
    ("assigned", "Назначена"),
    ("in_progress", "Взять в работу"),
    ("waiting_on_user", "Ждём пользователя"),
    ("waiting_on_internal_team", "Ждём внутреннюю группу"),
    ("waiting_on_vendor", "Ждём внешнюю сторону"),
    ("waiting_on_approval", "Ждём согласование"),
    ("scheduled", "Запланирована"),
    ("resolved", "Решено"),
    ("canceled", "Отменить"),
]

HIGH_RISK_TOOL_LEVELS = {"high", "dangerous", "system_write", "code_exec"}


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


def _permission_denied(permission_code: str) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": f"Недостаточно прав: {permission_code}",
            "error_code": "FORBIDDEN",
            "required_permission": permission_code,
        },
        status=403,
    )


async def _require_permission(session, auth_context, permission_code: str) -> web.Response | None:
    if await can(session, auth_context, permission_code):
        return None
    return _permission_denied(permission_code)


def _tool_risk_permission(risk_level: str | None) -> str:
    normalized = str(risk_level or "").strip().lower()
    if normalized in HIGH_RISK_TOOL_LEVELS:
        return "module.tool.run.high_risk"
    return "module.tool.run.low_risk"


async def _resolve_tool_risk_level(
    *,
    tool_service: ToolExecutionService,
    device_id: str,
    tool_name: str,
) -> str:
    raw_sources: list[tuple[str, list[object]]] = []
    for source, method_name in (("device", "get_tools_list"), ("server", "get_tools_from_server")):
        method = getattr(tool_service, method_name, None)
        if not callable(method):
            continue
        try:
            raw_items = await method(device_id) or []
        except Exception as exc:
            logger.debug(
                f"[web_support_run_tool] risk lookup skipped: device_id={device_id}, "
                f"tool={tool_name}, source={source}, error={exc}"
            )
            raw_items = []
        raw_sources.append((source, raw_items))
    for source, raw_items in raw_sources:
        raw_tool = _find_raw_tool_entry(raw_items, tool_name)
        if raw_tool is None:
            continue
        normalized = _normalize_support_tool_entry(raw_tool, source=source)
        if normalized is not None:
            return normalized.risk_level
    return "safe_read"


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
        status_label=str(ticket_data.get("status_label") or status_label_ru(ticket_data.get("status"))),
        requester_status=str(ticket_data.get("requester_status") or "accepted"),
        requester_status_label=str(ticket_data.get("requester_status_label") or ""),
        public_status=str(ticket_data.get("public_status") or ticket_data.get("requester_status") or "accepted"),
        public_status_label=str(ticket_data.get("public_status_label") or ticket_data.get("requester_status_label") or ""),
        next_action_owner=ticket_data.get("next_action_owner"),
        next_action_due_at=ticket_data.get("next_action_due_at"),
        status_reason=ticket_data.get("status_reason"),
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
        ticket.requester_status_label,
        ticket.next_action_owner,
        ticket.status_reason,
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


async def _build_support_status_actions(session, ticket, *, is_staff: bool) -> SupportTicketActions:
    if not is_staff:
        return SupportTicketActions(status_options=[], can_send_internal_note=False)

    current_status = str(getattr(ticket, "status", "") or "")
    options: list[SupportStatusAction] = []
    for value, label in QUICK_STATUS_ACTIONS:
        if value == current_status:
            continue
        if await validate_transition_for_ticket(session, ticket, value, True):
            options.append(SupportStatusAction(value=value, label=label))
    return SupportTicketActions(
        status_options=options,
        can_send_internal_note=True,
    )


def _build_support_request_form_payload(ticket_data: dict) -> SupportTicketRequestFormPayload | None:
    custom_fields = ticket_data.get("custom_fields")
    if not isinstance(custom_fields, dict):
        return None
    raw_rows = custom_fields.get("request_form_summary")
    rows_source = raw_rows if isinstance(raw_rows, list) else []
    rows = [
        SupportTicketRequestFormRow(
            key=str(row.get("key") or ""),
            label=str(row.get("label") or row.get("key") or ""),
            value=str(row.get("value") or ""),
        )
        for row in rows_source
        if isinstance(row, dict) and str(row.get("label") or row.get("key") or "").strip()
    ]
    request_kind = str(custom_fields.get("request_kind") or "").strip() or None
    form_key = str(custom_fields.get("request_form_key") or "").strip() or None
    form_title = str(custom_fields.get("request_form_title") or "").strip() or None
    if not rows and not request_kind and not form_key and not form_title:
        return None
    return SupportTicketRequestFormPayload(
        request_kind=request_kind,
        form_key=form_key,
        form_title=form_title,
        rows=rows,
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


def _summarize_playbook_facts(facts_package: object) -> str | None:
    if not isinstance(facts_package, dict):
        return None
    raw_rows = facts_package.get("request_form_summary")
    if not isinstance(raw_rows, list):
        return None
    rows: list[str] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            continue
        label = str(raw_row.get("label") or raw_row.get("key") or "").strip()
        value = str(raw_row.get("value") or "").strip()
        if label and value:
            rows.append(f"{label}: {value}")
    if not rows:
        return None
    return ", ".join(rows[:3])


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

    if event_type == "playbook_started":
        playbook_key = str(payload.get("playbook_key") or "diagnostic.playbook")
        run_id = payload.get("playbook_run_id")
        trigger = str(payload.get("trigger") or "ticket_created")
        summary_parts: list[str] = []
        if run_id is not None:
            summary_parts.append(f"Run #{run_id}")
        if trigger:
            summary_parts.append(f"Событие: {trigger}")
        facts_summary = _summarize_playbook_facts(payload.get("facts_package"))
        if facts_summary:
            summary_parts.append(f"Факты формы: {facts_summary}")
        return SupportTicketMessage(
            message_id=None,
            event_id=getattr(event, "id", None),
            event_type=event_type,
            from_role="system",
            sender_display_name="Автодиагностика",
            text=f"Автодиагностика запущена: {playbook_key}",
            ts=_event_timestamp_iso(event, payload),
            visibility="system",
            direction="system",
            attachments=[],
            reply_to=None,
            tool_name=playbook_key,
            tool_status="running",
            result_summary=" • ".join(summary_parts) if summary_parts else None,
            result_preview=None,
        )

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
        label = str(preset.get("label") or preset.get("title") or preset.get("name") or preset_id).strip()
        params = preset.get("params") if isinstance(preset.get("params"), dict) else {}
        presets.append(
            SupportToolPreset(
                preset_id=preset_id,
                label=label,
                description=str(preset.get("description") or "").strip() or None,
                params=params,
            )
        )
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


def _iso(value: object) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _required_tools_from_manifest(manifest_json: object) -> list[str]:
    if not isinstance(manifest_json, dict):
        return []
    tools: list[str] = []
    for raw_item in manifest_json.get("required_tools") or []:
        if not isinstance(raw_item, dict):
            continue
        tool_name = str(raw_item.get("tool") or raw_item.get("tool_name") or "").strip()
        if tool_name and tool_name not in tools:
            tools.append(tool_name)
    return tools


async def _build_support_playbooks_payload(session, ticket: object) -> SupportTicketPlaybooksPayload:
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    rows = await session.execute(
        select(Playbook, PlaybookVersion, func.count(PlaybookStep.id))
        .join(PlaybookVersion, PlaybookVersion.playbook_id == Playbook.id)
        .join(PlaybookStep, PlaybookStep.playbook_version_id == PlaybookVersion.id, isouter=True)
        .where(Playbook.archived.is_(False), PlaybookVersion.status == "published")
        .group_by(Playbook.id, PlaybookVersion.id)
        .order_by(Playbook.key.asc(), PlaybookVersion.published_at.desc().nullslast(), PlaybookVersion.id.desc())
    )
    seen_playbook_ids: set[int] = set()
    playbooks: list[SupportPlaybookItem] = []
    for playbook, version, steps_count in rows.all():
        playbook_id = int(getattr(playbook, "id"))
        if playbook_id in seen_playbook_ids:
            continue
        seen_playbook_ids.add(playbook_id)
        can_run = bool(device_id)
        playbooks.append(
            SupportPlaybookItem(
                playbook_version_id=int(version.id),
                key=str(playbook.key),
                name=str(playbook.name),
                domain=playbook.domain,
                version=str(version.version) if version.version is not None else None,
                status=str(version.status),
                blocks_count=int(steps_count or 0),
                required_tools=_required_tools_from_manifest(version.manifest_json),
                can_run=can_run,
                readiness_label="Готов к запуску" if can_run else "Нужна привязка к устройству",
                updated_at=_iso(version.published_at or version.created_at),
            )
        )
    return SupportTicketPlaybooksPayload(
        ticket_id=str(getattr(ticket, "ticket_id")),
        device_id=device_id,
        playbooks=playbooks,
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


def _find_raw_tool_entry(raw_items: list[object], tool_name: str) -> dict | None:
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        current = str(raw_item.get("tool") or raw_item.get("name") or "").strip()
        aliases = raw_item.get("aliases") if isinstance(raw_item.get("aliases"), list) else []
        if current == tool_name or tool_name in aliases:
            return raw_item
    return None


async def _build_tool_params_for_dispatch(
    *,
    tool_service: ToolExecutionService,
    device_id: str,
    tool_name: str,
    params: dict,
    preset_id: str | None,
    operation_id: str,
) -> dict:
    dispatch_params = {"_operation_id": operation_id}
    if not preset_id:
        dispatch_params.update(params)
        return dispatch_params

    device_tools_raw = await tool_service.get_tools_list(device_id) or []
    server_tools_raw = await tool_service.get_tools_from_server(device_id) or []
    raw_tool = _find_raw_tool_entry(device_tools_raw, tool_name)
    source = "device"
    if raw_tool is None:
        raw_tool = _find_raw_tool_entry(server_tools_raw, tool_name)
        source = "server"
    if raw_tool is None:
        dispatch_params.update(params)
        dispatch_params["preset_id"] = preset_id
        return dispatch_params

    tool_entry = normalize_tool_catalog_entry(raw_tool, source=source)
    dispatch_params.update(expand_preset_params(tool_entry, preset_id=preset_id, overrides=params))
    dispatch_params["preset_id"] = preset_id
    return dispatch_params


async def _build_support_snapshot(request: web.Request, session, ticket, auth_context) -> SupportTicketSnapshot:
    presence = SupportTicketPresence.model_validate(_ticket_presence_payload(request, ticket))
    notification_unread = await NotificationRepo(session).unread_count(auth_context.actor_id)

    device = None
    registry_snapshot = None
    if getattr(ticket, "device_id", None):
        device = await DevicesRepo(session).get_by_device_id(ticket.device_id)
        registry_repo = RegistryRepo(session)
        asset = await registry_repo.get_asset_by_device_id(ticket.device_id)
        person = await registry_repo.get_person(getattr(asset, "assigned_person_id", None)) if asset else None
        location = await registry_repo.get_location(getattr(asset, "location_id", None)) if asset else None
        department = await registry_repo.get_department(getattr(asset, "department_id", None)) if asset else None
        if asset or person or location or department:
            registry_snapshot = SupportTicketRegistrySnapshot(
                person_id=getattr(person, "person_id", None),
                person_display_name=getattr(person, "display_name", None),
                department_id=getattr(department, "department_id", None),
                department_name=getattr(department, "name", None),
                location_id=getattr(location, "location_id", None),
                location_display_name=getattr(location, "display_name", None),
                building=getattr(location, "building", None),
                room=getattr(location, "room", None),
                asset_id=getattr(asset, "asset_id", None),
                asset_name=getattr(asset, "name", None),
                asset_type=getattr(asset, "asset_type", None),
                service_id=getattr(asset, "service_id", None),
                service_name=None,
            )

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
        registry=registry_snapshot,
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
                if getattr(item, "event_type", None)
                in {"chat_message", "tool_call_started", "tool_call_result", "playbook_started"}
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
    actions = await _build_support_status_actions(
        session,
        ticket,
        is_staff=auth_context.actor_role in {"admin", "support"},
    )
    request_form = _build_support_request_form_payload(ticket_data)
    custom_fields = ticket_data.get("custom_fields") if isinstance(ticket_data.get("custom_fields"), dict) else {}

    return SupportTicketDetailPayload(
        ticket=SupportTicketDetail(
            ticket_id=str(ticket_data.get("ticket_id") or ""),
            ticket_code=ticket_data.get("ticket_code"),
            title=str(ticket_data.get("title") or "Без названия"),
            description=ticket_data.get("description"),
            status=str(ticket_data.get("status") or "unknown"),
            status_label=str(ticket_data.get("status_label") or status_label_ru(ticket_data.get("status"))),
            requester_status=str(ticket_data.get("requester_status") or "accepted"),
            requester_status_label=str(ticket_data.get("requester_status_label") or ""),
            public_status=str(ticket_data.get("public_status") or ticket_data.get("requester_status") or "accepted"),
            public_status_label=str(ticket_data.get("public_status_label") or ticket_data.get("requester_status_label") or ""),
            next_action_owner=ticket_data.get("next_action_owner"),
            next_action_due_at=ticket_data.get("next_action_due_at"),
            status_reason=ticket_data.get("status_reason"),
            requester_display_name=ticket_data.get("requester_display_name"),
            device_id=ticket_data.get("device_id"),
            ticket_type=ticket_data.get("ticket_type"),
            category_id=ticket_data.get("category_id"),
            service_id=ticket_data.get("service_id"),
            subcategory_id=ticket_data.get("subcategory_id"),
            priority=ticket_data.get("priority"),
            priority_class=ticket_data.get("priority_class"),
            impact=ticket_data.get("impact"),
            urgency=ticket_data.get("urgency"),
            importance=ticket_data.get("importance"),
            priority_decision=custom_fields.get("priority_decision") if isinstance(custom_fields.get("priority_decision"), dict) else {},
            first_response_due_at=ticket_data.get("first_response_due_at"),
            resolution_due_at=ticket_data.get("resolution_due_at"),
            queue=SupportTicketQueueInfo(
                id=ticket_queue_id,
                code=ticket_data.get("queue_code"),
                name=queue_name,
            ),
            assignee_id=ticket_data.get("assignee_id"),
            updated_at=ticket_data.get("updated_at"),
            created_at=ticket_data.get("created_at"),
            resolution_code=ticket_data.get("resolution_code"),
            resolution_summary=ticket_data.get("resolution_summary"),
            requester_resolution_summary=ticket_data.get("requester_resolution_summary"),
            evidence_required=bool(ticket_data.get("evidence_required")),
            evidence_ref=ticket_data.get("evidence_ref"),
            closure_feedback=ticket_data.get("closure_feedback") or {},
            visibility=ticket_data.get("visibility") if isinstance(ticket_data.get("visibility"), dict) else {},
            requester_visible_fields=ticket_data.get("requester_visible_fields") if isinstance(ticket_data.get("requester_visible_fields"), list) else [],
            support_visible_fields=ticket_data.get("support_visible_fields") if isinstance(ticket_data.get("support_visible_fields"), list) else [],
            queue_members=[
                SupportTicketQueueMember(
                    actor_id=str(member.get("actor_id") or ""),
                    role_in_queue=member.get("role_in_queue"),
                )
                for member in ticket_data.get("queue_members", [])
                if member.get("actor_id")
            ],
        ),
        request_form=request_form,
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
async def handle_web_support_ticket_playbooks(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await _build_support_playbooks_payload(session, ticket)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_playbooks] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить плейбуки для тикета",
                "error_code": "SUPPORT_PLAYBOOKS_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPlaybooksPayload](data=payload))


def _passport_payload_model(payload: dict) -> SupportTicketPassportDetailPayload:
    return SupportTicketPassportDetailPayload.model_validate(payload)


@require_auth("admin", "support")
async def handle_web_support_ticket_passport(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить паспорт решения",
                "error_code": "PASSPORT_UNAVAILABLE",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPassportDetailPayload](data=_passport_payload_model(payload)))


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_generate(request: web.Request):
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return web.json_response({"status": "error", "error": "Тело запроса должно быть объектом"}, status=400)
    data = SupportTicketPassportGenerateRequest.model_validate(raw)
    mode = data.mode if data.mode in {"create", "refresh"} else "refresh"

    try:
        async with get_session() as session:
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            payload = await TicketPassportService(session).generate(
                ticket.ticket_id,
                actor_id=auth_context.actor_id,
                mode=mode,
                include_internal_notes=data.include_internal_notes,
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_generate] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось собрать паспорт решения",
                "error_code": "PASSPORT_GENERATE_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPassportDetailPayload](data=_passport_payload_model(payload)))


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_patch(request: web.Request):
    try:
        raw = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Некорректный JSON"}, status=400)
    if not isinstance(raw, dict):
        return web.json_response({"status": "error", "error": "Тело запроса должно быть объектом"}, status=400)
    data = SupportTicketPassportPatchRequest.model_validate(raw)

    try:
        async with get_session() as session:
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            repo = TicketPassportRepo(session)
            passport = await repo.get_latest_passport(ticket.ticket_id)
            if passport is None:
                payload = await TicketPassportService(session).generate(
                    ticket.ticket_id,
                    actor_id=auth_context.actor_id,
                    mode="create",
                )
                passport_id = payload["passport"]["passport_id"]
                passport = await session.get(TicketResolutionPassport, passport_id)
            await repo.update_passport_sections(
                passport,
                updated_by=auth_context.actor_id,
                sections=data.model_dump(exclude_none=True),
            )
            await session.commit()
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_patch] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось обновить паспорт решения",
                "error_code": "PASSPORT_UPDATE_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPassportDetailPayload](data=_passport_payload_model(payload)))


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_evidence(request: web.Request):
    try:
        raw = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Некорректный JSON"}, status=400)
    if not isinstance(raw, dict):
        return web.json_response({"status": "error", "error": "Тело запроса должно быть объектом"}, status=400)
    data = SupportTicketPassportEvidenceRequest.model_validate(raw)
    visibility = data.visibility if data.visibility in {"public", "internal"} else "internal"

    try:
        async with get_session() as session:
            ticket, error, ticket_repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            repo = TicketPassportRepo(session)
            passport = await repo.get_latest_passport(ticket.ticket_id)
            item = await repo.add_evidence(
                ticket_id=ticket.ticket_id,
                passport_id=passport.id if passport else None,
                evidence_type=data.evidence_type,
                source_ref=data.source_ref,
                title=data.title,
                summary=data.summary,
                visibility=visibility,
                created_by=auth_context.actor_id,
            )
            if not ticket.evidence_ref:
                await ticket_repo.update_ticket(ticket.ticket_id, evidence_ref=data.source_ref or f"evidence:{item.id}")
            await ticket_repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="passport_evidence_added",
                payload={
                    "event_id": f"passport-evidence-{item.id}",
                    "actor_id": auth_context.actor_id,
                    "evidence_id": item.id,
                    "evidence_type": item.evidence_type,
                    "title": item.title,
                },
                event_id=f"passport-evidence-{item.id}",
            )
            await session.commit()
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_evidence] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось добавить доказательство",
                "error_code": "PASSPORT_EVIDENCE_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPassportDetailPayload](data=_passport_payload_model(payload)))


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_knowledge_draft(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
            passport = payload.get("passport")
            if not passport:
                payload = await TicketPassportService(session).generate(ticket.ticket_id, actor_id=None, mode="create")
                passport = payload["passport"]
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_knowledge_draft] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось подготовить черновик знания",
                "error_code": "PASSPORT_KB_DRAFT_FAILED",
            },
            status=503,
        )
    sections = passport.get("sections") or {}
    draft = SupportTicketKnowledgeDraftPayload(
        title=f"Решение по тикету {request.match_info.get('ticket_id')}",
        problem=sections.get("problem") or "Проблема не описана",
        resolution=sections.get("user_result") or sections.get("changes_made") or "Решение не описано",
        repeat_guidance=sections.get("repeat_guidance") or "При повторе создать заявку с деталями ошибки.",
        source_passport_id=int(passport["passport_id"]),
    )
    return json_model_response(SuccessResponse[SupportTicketKnowledgeDraftPayload](data=draft))


@require_auth("admin", "support", "auditor")
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
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            permission = "ticket.comment.internal" if visibility == "internal" else "ticket.comment.public"
            denied = await _require_permission(session, auth_context, permission)
            if denied:
                return denied

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


@require_auth("admin", "support", "auditor")
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
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.status.change")
            if denied:
                return denied

            is_staff = auth_context.actor_role in {"admin", "support"}
            if not await validate_transition_for_ticket(session, ticket, to_status, is_staff):
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Переход статуса недоступен",
                        "error_code": "INVALID_TRANSITION",
                    },
                    status=400,
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
                    source="web_support_api",
                )
            except ValueError as exc:
                message = str(exc)
                if message.startswith("approval_policy"):
                    error_code = "APPROVAL_POLICY_BLOCKED"
                elif message.startswith("closure_policy"):
                    error_code = "CLOSURE_POLICY_BLOCKED"
                elif message.startswith("workflow_profile"):
                    error_code = "WORKFLOW_POLICY_BLOCKED"
                else:
                    error_code = "WORKFLOW_POLICY_BLOCKED"
                return web.json_response(
                    {
                        "status": "error",
                        "error": message,
                        "error_code": error_code,
                    },
                    status=400,
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


@require_auth("admin", "support", "auditor")
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
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.tool.run")
            if denied:
                return denied

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
            tool_service = ToolExecutionService(request.app["state"])
            risk_level = await _resolve_tool_risk_level(
                tool_service=tool_service,
                device_id=device_id,
                tool_name=tool_name,
            )
            denied = await _require_permission(session, auth_context, _tool_risk_permission(risk_level))
            if denied:
                return denied
            params_with_operation = await _build_tool_params_for_dispatch(
                tool_service=tool_service,
                device_id=device_id,
                tool_name=tool_name,
                params=params,
                preset_id=preset_id,
                operation_id=operation_id,
            )

            result = await tool_service.run_tool(
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


@require_auth("admin", "support", "auditor")
async def handle_web_support_run_playbook(request: web.Request):
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
    try:
        playbook_version_id = int(data.get("playbook_version_id"))
    except (TypeError, ValueError):
        return web.json_response(
            {
                "status": "error",
                "error": "Нужно выбрать опубликованную версию плейбука",
                "error_code": "PLAYBOOK_VERSION_REQUIRED",
            },
            status=400,
        )

    try:
        async with get_session() as session:
            ticket, error, _repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.playbook.run")
            if denied:
                return denied
            device_id = str(getattr(ticket, "device_id", "") or "").strip()
            if not device_id:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Тикет не привязан к устройству, плейбук нельзя запустить",
                        "error_code": "DEVICE_REQUIRED",
                    },
                    status=400,
                )
            version = await session.get(PlaybookVersion, playbook_version_id)
            if version is None or str(version.status) != "published":
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Выбранный плейбук не опубликован",
                        "error_code": "PLAYBOOK_NOT_PUBLISHED",
                    },
                    status=400,
                )
            context_json = {
                "ticket_id": str(getattr(ticket, "ticket_id")),
                "ticket_code": getattr(ticket, "ticket_code", None),
                "requester_id": getattr(ticket, "requester_id", None),
                "triggered_by": auth_context.actor_id,
                "triggered_from": "support_ticket_detail",
            }
            run_id, first_operation_id = await start_run(
                session=session,
                state=request.app["state"],
                playbook_version_id=playbook_version_id,
                device_id=device_id,
                trigger_type="support_ticket",
                context_json=context_json,
                idempotency_key=str(data.get("idempotency_key") or "").strip() or None,
            )
            await session.commit()
            payload = SupportPlaybookRunActionResult(
                ticket_id=str(getattr(ticket, "ticket_id")),
                device_id=device_id,
                playbook_version_id=playbook_version_id,
                playbook_run_id=int(run_id),
                status="running",
                first_operation_id=first_operation_id,
                observer_url=f"/app/admin/observer?root_kind=playbook_run&playbook_run_id={run_id}",
                message="Плейбук поставлен в очередь выполнения.",
            )
    except Exception as exc:
        logger.warning(
            f"[web_support_run_playbook] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось запустить плейбук из карточки тикета",
                "error_code": "PLAYBOOK_ACTION_FAILED",
            },
            status=503,
        )
    return json_model_response(SuccessResponse[SupportPlaybookRunActionResult](data=payload), status=202)
