import ast
from dataclasses import dataclass
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import cmp_to_key
from typing import Any

from aiohttp import web
from loguru import logger
from sqlalchemy import func, or_, select, update

from access_control.service import can
from app.api.serializers import ticket_to_dict
from app.db import get_session
from app.db.models import (
    Operation,
    Playbook,
    PlaybookRun,
    PlaybookStep,
    PlaybookStepRun,
    PlaybookVersion,
    SupportQueueSavedView,
    Ticket,
    TicketApproval,
    TicketEvent,
    TicketFeedback,
    TicketQualityReview,
    TicketQueue,
    TicketQueueMember,
    TicketReopenEvent,
    TicketResolutionPassport,
    ContinuousImprovementAction,
)
from app.repos import DevicesRepo, NotificationRepo
from app.repos.helpdesk_policy_repo import HelpdeskPolicyRepo
from app.repos.registry_repo import RegistryRepo
from app.repos.ticket_admin_config_repo import TicketAdminConfigRepo
from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.ticket_passport_repo import TicketPassportRepo
from app.services.operation_service import OperationService
from app.services.playbook_engine import start_run
from auth.middleware import require_auth
from core.policy_engine import PolicyDecision, PolicyEngine
from core.tool_metadata import ToolMetadata
from observer.service import ObserverOverlayService
from playbooks.tool_catalog import expand_preset_params, normalize_tool_catalog_entry
from shared.tool_contracts import normalize_risk_level
from tickets.handlers import (
    RESOLUTION_CONFIRMATION_TEXT,
    _build_resolution_confirmation_request,
    _chat_counters_by_ticket_ids,
    _get_ticket_or_response,
    _message_role_from_auth,
    _push_ticket_event,
    _queue_code_map,
    _reconcile_queue_scope_state,
    _resolution_confirmation_pending,
    _serialize_message,
    _store_resolution_confirmation_state,
    _ticket_payload,
    _ticket_presence_payload,
)
from tickets.assignment_service import MAX_ACTIVE_TICKETS_PER_OPERATOR, TicketAssignmentError, TicketAssignmentService
from tickets.ola_service import close_ola_processing, start_ola_for_ticket
from tickets.public_access import is_public_support_reply_payload
from tickets.requester_timeline import build_requester_timeline_projection, projection_to_fields
from tickets.routing_service import TicketRoutingService, set_routing_lock
from tickets.statuses import (
    CANONICAL_STATUSES,
    enrich_chat_payload_with_requester_name,
    merge_requester_custom_fields,
    normalize_status,
    normalize_ticket_priority_inputs,
    resolve_status,
    status_label_ru,
)
from tickets.sla_service import TicketSlaService
from tickets.approval_policy import build_approval_summary
from tickets.closure_policy import build_closure_requirements
from tickets.evidence_service import TicketEvidenceService
from tickets.knowledge_provider import build_knowledge_suggestions
from knowledge.suggestion_service import KnowledgeSuggestionService
from knowledge.passport_draft_service import KnowledgePassportDraftService
from inventory.service import DeviceInventoryService, binding_to_dict
from tickets.notification_service import notify_ticket_event
from tickets.passport_service import TicketPassportService
from tickets.smart_views import matches_smart_view, normalize_smart_view_id, smart_view_options
from tickets.workflow_service import TicketWorkflowService, validate_transition_for_ticket
from tools.service import ToolExecutionService
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.support import (
    SupportBootstrapPayload,
    SupportCountItem,
    SupportDiagnosticPolicyPayload,
    SupportFilterOption,
    SupportMessageActionResult,
    SupportObserverCapabilities,
    SupportQueueMassActionItem,
    SupportQueueMassActionRequest,
    SupportQueueMassActionResult,
    SupportQueueSavedViewDeletePayload,
    SupportQueueSavedViewItem,
    SupportQueueSavedViewsPayload,
    SupportQueueSavedViewUpsertRequest,
    SupportQueueFilters,
    SupportQueueCountItem,
    SupportQueuePayload,
    SupportQueueSummary,
    SupportQueueTicketItem,
    SupportStatusAction,
    SupportStatusActionResult,
    SupportTicketActions,
    SupportTicketClosurePlanItem,
    SupportTicketClosurePlanPayload,
    SupportTicketDetail,
    SupportTicketDetailPayload,
    SupportTicketDeviceSnapshot,
    SupportTicketKnowledgeSuggestionsPayload,
    SupportTicketInventoryAgentContext,
    SupportTicketInventoryBindingContext,
    SupportTicketInventoryContext,
    SupportTicketInventoryRefreshContext,
    SupportTicketInventorySignals,
    SupportTicketInventorySnapshotContext,
    SupportTicketQualityAction,
    SupportTicketQualityFeedback,
    SupportTicketQualityPayload,
    SupportTicketQualityReopenEvent,
    SupportTicketQualityReview,
    SupportKnowledgeAiSummary,
    SupportKnowledgeArticle,
    SupportKnowledgeDiagnostics,
    SupportKnowledgeSimilarTicket,
    SupportTicketMessage,
    SupportTicketMutationActionResult,
    SupportTicketEvidenceCandidatesPayload,
    SupportTicketObserverPayload,
    SupportTicketObserverOccurrenceCompact,
    SupportTicketObserverSignature,
    SupportTicketObserverSummary,
    SupportTicketObserverTraceCompact,
    SupportTicketOperationSnapshot,
    SupportTicketPassportDetailPayload,
    SupportTicketPassportEvidenceLinkRequest,
    SupportTicketPassportEvidenceRequest,
    SupportTicketPassportEvidenceUpdateRequest,
    SupportTicketPassportGenerateRequest,
    SupportTicketPassportPatchRequest,
    SupportTicketPassportReadinessItem,
    SupportTicketPassportReadinessPayload,
    SupportTicketPlaybooksPayload,
    SupportTicketPresence,
    SupportPlaybookRecentRun,
    SupportPlaybookRecentRunStepError,
    SupportTicketQueueInfo,
    SupportTicketQueueMember,
    SupportTicketRegistrySnapshot,
    SupportTicketRequestFormPayload,
    SupportTicketRequestFormRow,
    SupportTicketReplyTo,
    SupportTicketSnapshot,
    SupportTicketSlaOlaPayload,
    SupportTicketTimerPayload,
    SupportTicketTimelinePayload,
    SupportTicketToolsPayload,
    SupportTicketWorkspacePayload,
    SupportWorkspaceSummaryPayload,
    SupportWorkspaceSummaryQueueItem,
    SupportWorkspaceCleanupResult,
    SupportTicketKnowledgeDraftPayload,
    SupportPlaybookItem,
    SupportPlaybookRunActionResult,
    SupportToolActionResult,
    SupportToolItem,
    SupportToolParameter,
    SupportToolPreset,
)
from config import AGENT_BUILTIN_MODULES, ALLOW_REMOTE_CODE


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
SUPPORT_TIMELINE_RENDER_RESULT_MAX_BYTES = 128 * 1024
WORKSPACE_SUMMARY_VIEW_ALIASES = {
    "needs_action": "my_action",
    "sla_risk": "sla_risk",
    "unassigned": "unassigned",
    "requester_replied": "requester_reply",
}
SUPPORT_WORKSPACE_INTERNAL_NAV_PATTERNS = [
    re.compile(r"^stage[\s_-]*\d+", re.IGNORECASE),
    re.compile(r"^codex[\s_-]*ola\b", re.IGNORECASE),
    re.compile(r"^live[\s_-]", re.IGNORECASE),
    re.compile(r"\btest\b", re.IGNORECASE),
]
SUPPORT_WORKSPACE_VISIBILITY_KEY = "support_workspace_visibility"
SUPPORT_QUEUE_SAVED_VIEW_SCOPES = {"personal", "queue", "global"}
SUPPORT_QUEUE_VIEW_COLUMNS = {
    "number",
    "subject",
    "requester",
    "priority",
    "status",
    "next_action",
    "sla",
    "queue",
    "assignee",
    "last_event",
    "unread",
}
SUPPORT_QUEUE_REQUIRED_VIEW_COLUMNS = {"number", "subject"}
SUPPORT_QUEUE_DEFAULT_VIEW_COLUMNS = [
    "number",
    "subject",
    "requester",
    "priority",
    "status",
    "next_action",
    "sla",
    "queue",
    "assignee",
    "last_event",
    "unread",
]


@dataclass
class SupportQueueState:
    active_queues: list[object]
    smart_options: list[dict[str, str]]
    custom_smart_view_map: dict[str, dict[str, object]]
    accessible_entries: list[tuple[dict, SupportQueueTicketItem]]


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


def _is_internal_support_workspace_nav_item(*values: object) -> bool:
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        if any(pattern.search(text) for pattern in SUPPORT_WORKSPACE_INTERNAL_NAV_PATTERNS):
            return True
    return False


def _parse_bool_query(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _ticket_custom_fields(ticket_or_data: object) -> dict[str, Any]:
    if isinstance(ticket_or_data, dict):
        raw = ticket_or_data.get("custom_fields")
    else:
        raw = getattr(ticket_or_data, "custom_fields", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _support_workspace_visibility(ticket_or_data: object) -> dict[str, Any]:
    custom_fields = _ticket_custom_fields(ticket_or_data)
    raw_meta = custom_fields.get(SUPPORT_WORKSPACE_VISIBILITY_KEY)
    meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    archived_at: object
    if isinstance(ticket_or_data, dict):
        archived_at = ticket_or_data.get("archived_at")
    else:
        archived_at = getattr(ticket_or_data, "archived_at", None)
    archived_at_value = archived_at.isoformat() if hasattr(archived_at, "isoformat") else archived_at
    return {
        "hidden_from_workspace": bool(meta.get("hidden")),
        "hidden_at": meta.get("hidden_at"),
        "hidden_by": meta.get("hidden_by"),
        "hidden_reason": meta.get("hidden_reason"),
        "archived_at": archived_at_value,
        "archived_by": meta.get("archived_by") if archived_at_value else None,
        "archive_reason": meta.get("archive_reason") if archived_at_value else None,
    }


def _is_support_workspace_hidden(ticket_or_data: object) -> bool:
    return bool(_support_workspace_visibility(ticket_or_data).get("hidden_from_workspace"))


def _apply_support_workspace_visibility(ticket_data: dict[str, Any], ticket: object) -> dict[str, Any]:
    ticket_data.update(_support_workspace_visibility(ticket))
    return ticket_data


def _support_workspace_custom_fields(
    ticket: object,
    *,
    hidden: bool | None = None,
    archived: bool | None = None,
    actor_id: str,
    reason: str | None,
    now: datetime,
) -> dict[str, Any]:
    custom_fields = _ticket_custom_fields(ticket)
    meta = dict(custom_fields.get(SUPPORT_WORKSPACE_VISIBILITY_KEY) or {})
    iso_now = now.isoformat()
    normalized_reason = str(reason or "").strip() or None
    if hidden is True:
        meta.update(
            {
                "hidden": True,
                "hidden_at": iso_now,
                "hidden_by": actor_id,
                "hidden_reason": normalized_reason,
            }
        )
    elif hidden is False:
        meta.update(
            {
                "hidden": False,
                "unhidden_at": iso_now,
                "unhidden_by": actor_id,
                "unhidden_reason": normalized_reason,
            }
        )
    if archived is True:
        meta.update(
            {
                "archived_by": actor_id,
                "archive_reason": normalized_reason,
                "archive_action_at": iso_now,
            }
        )
    elif archived is False:
        meta.update(
            {
                "unarchived_by": actor_id,
                "unarchive_reason": normalized_reason,
                "unarchive_action_at": iso_now,
            }
        )
    custom_fields[SUPPORT_WORKSPACE_VISIBILITY_KEY] = meta
    return custom_fields


def _is_support_workspace_cleanup_noise(ticket_data: dict[str, Any]) -> bool:
    return _is_internal_support_workspace_nav_item(
        ticket_data.get("title"),
        ticket_data.get("queue_code"),
        ticket_data.get("requester_display_name"),
    )


def _build_empty_queue_payload(*, scope: str, query: str, status_filter: str, smart_view: str = "all") -> SupportQueuePayload:
    return SupportQueuePayload(
        scope=scope,
        query=query,
        status_filter=status_filter,
        smart_view=smart_view,
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
            smart_view_options=[SupportFilterOption(**option) for option in smart_view_options()],
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


def _support_json_error(error: str, *, status: int = 400, error_code: str | None = None, **payload: Any) -> web.Response:
    body = {"status": "error", "error": error}
    if error_code:
        body["error_code"] = error_code
    body.update(payload)
    return web.json_response(body, status=status)


async def _read_support_json(request: web.Request) -> dict[str, Any] | web.Response:
    try:
        data = await request.json()
    except Exception:
        return _support_json_error("Некорректный JSON", status=400, error_code="VALIDATION_ERROR")
    if not isinstance(data, dict):
        return _support_json_error("Тело запроса должно быть объектом", status=400, error_code="VALIDATION_ERROR")
    return data


def _normalize_saved_view_scope(scope: str | None) -> str:
    normalized = str(scope or "personal").strip().lower()
    return normalized if normalized in SUPPORT_QUEUE_SAVED_VIEW_SCOPES else "personal"


def _normalize_saved_view_name(name: str) -> str:
    normalized = re.sub(r"\s+", " ", str(name or "").strip())
    return normalized[:120]


def _normalize_saved_view_columns(columns: list[str] | None) -> list[str]:
    ordered: list[str] = []
    for column in list(columns or SUPPORT_QUEUE_DEFAULT_VIEW_COLUMNS):
        normalized = str(column or "").strip()
        if normalized in SUPPORT_QUEUE_VIEW_COLUMNS and normalized not in ordered:
            ordered.append(normalized)
    for required in sorted(SUPPORT_QUEUE_REQUIRED_VIEW_COLUMNS):
        if required not in ordered:
            ordered.insert(0, required)
    return ordered


def _normalize_saved_view_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(filters or {})
    normalized: dict[str, Any] = {}
    for key in ("scope", "smartViewId", "queueId", "search", "showArchive"):
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, (str, int, bool)) or value is None:
            normalized[key] = value
    if "search" in normalized:
        normalized["search"] = str(normalized["search"] or "")[:200]
    if "scope" in normalized:
        normalized["scope"] = _normalize_scope(str(normalized["scope"]))
    if "showArchive" in normalized:
        normalized["showArchive"] = bool(normalized["showArchive"])
    return normalized


def _normalize_saved_view_sort(sort: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list(sort or [])[:5]:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        direction = str(item.get("direction") or "asc").strip().lower()
        if not field:
            continue
        normalized.append({"field": field[:80], "direction": "desc" if direction == "desc" else "asc"})
    return normalized


async def _support_accessible_queue_ids(session, auth_context) -> set[int]:
    if getattr(auth_context, "actor_role", None) == "admin":
        rows = (await session.execute(select(TicketQueue.id).where(TicketQueue.is_active.is_(True)))).scalars().all()
        return {int(row) for row in rows if row is not None}
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    if not actor_id:
        return set()
    rows = (
        await session.execute(
            select(TicketQueueMember.queue_id)
            .join(TicketQueue, TicketQueue.id == TicketQueueMember.queue_id)
            .where(TicketQueueMember.actor_id == actor_id)
            .where(TicketQueue.is_active.is_(True))
        )
    ).scalars().all()
    return {int(row) for row in rows if row is not None}


def _saved_view_visibility_clause(auth_context, accessible_queue_ids: set[int]):
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    clauses = [SupportQueueSavedView.scope == "global"]
    if actor_id:
        clauses.append((SupportQueueSavedView.scope == "personal") & (SupportQueueSavedView.owner_actor_id == actor_id))
    if accessible_queue_ids:
        clauses.append((SupportQueueSavedView.scope == "queue") & (SupportQueueSavedView.queue_id.in_(accessible_queue_ids)))
    return or_(*clauses)


def _serialize_support_queue_saved_view(view: SupportQueueSavedView) -> SupportQueueSavedViewItem:
    return SupportQueueSavedViewItem(
        id=view.id,
        name=view.name,
        scope=view.scope,
        owner_actor_id=view.owner_actor_id,
        queue_id=view.queue_id,
        filters=dict(view.filters_json or {}),
        columns=_normalize_saved_view_columns(list(view.columns_json or [])),
        sort=list(view.sort_json or []),
        is_favorite=bool(view.is_favorite),
        is_default=bool(view.is_default),
        created_at=view.created_at.isoformat() if view.created_at else None,
        updated_at=view.updated_at.isoformat() if view.updated_at else None,
        created_by=view.created_by,
        updated_by=view.updated_by,
    )


def _can_manage_saved_view(auth_context, view: SupportQueueSavedView) -> bool:
    if getattr(auth_context, "actor_role", None) == "admin":
        return True
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    return bool(actor_id and (view.owner_actor_id == actor_id or view.created_by == actor_id))


async def _validate_saved_view_scope(
    session,
    auth_context,
    *,
    scope: str,
    queue_id: int | None,
    accessible_queue_ids: set[int] | None = None,
) -> web.Response | None:
    if scope == "global" and getattr(auth_context, "actor_role", None) != "admin":
        return _support_json_error("Global saved views are admin-only", status=403, error_code="FORBIDDEN")
    if scope != "queue":
        return None
    if queue_id is None:
        return _support_json_error("queue_id is required for queue saved views", status=400, error_code="VALIDATION_ERROR")
    queue = (await session.execute(select(TicketQueue).where(TicketQueue.id == queue_id))).scalar_one_or_none()
    if queue is None or not bool(getattr(queue, "is_active", False)):
        return _support_json_error("Queue not found or inactive", status=404, error_code="NOT_FOUND")
    if getattr(auth_context, "actor_role", None) == "admin":
        return None
    ids = accessible_queue_ids if accessible_queue_ids is not None else await _support_accessible_queue_ids(session, auth_context)
    if queue_id not in ids:
        return _support_json_error("Queue is not available to the current operator", status=403, error_code="FORBIDDEN")
    return None


async def _clear_saved_view_default_peers(session, view: SupportQueueSavedView) -> None:
    stmt = (
        update(SupportQueueSavedView)
        .where(SupportQueueSavedView.id != view.id)
        .where(SupportQueueSavedView.scope == view.scope)
        .where(SupportQueueSavedView.is_default.is_(True))
    )
    if view.scope == "personal":
        stmt = stmt.where(SupportQueueSavedView.owner_actor_id == view.owner_actor_id)
    elif view.scope == "queue":
        stmt = stmt.where(SupportQueueSavedView.queue_id == view.queue_id)
    await session.execute(stmt.values(is_default=False))


async def _support_mutation_result(session, ticket: object, *, action: str, auto_assigned: bool = False) -> SupportTicketMutationActionResult:
    ticket_data = await _ticket_payload(session, ticket, include_assignment_context=True)
    visibility = _support_workspace_visibility(ticket)
    return SupportTicketMutationActionResult(
        ticket_id=str(ticket_data.get("ticket_id") or getattr(ticket, "ticket_id", "")),
        action=action,
        status=str(ticket_data.get("status") or getattr(ticket, "status", "unknown")),
        status_label=str(ticket_data.get("status_label") or status_label_ru(getattr(ticket, "status", None))),
        queue=SupportTicketQueueInfo(
            id=ticket_data.get("queue_id"),
            code=ticket_data.get("queue_code"),
            name=next(
                (
                    queue.get("name")
                    for queue in ticket_data.get("available_queues", [])
                    if queue.get("id") == ticket_data.get("queue_id")
                ),
                None,
            ),
        ),
        assignee_id=ticket_data.get("assignee_id"),
        priority=ticket_data.get("priority"),
        priority_class=ticket_data.get("priority_class"),
        auto_assigned=auto_assigned,
        hidden_from_workspace=bool(visibility.get("hidden_from_workspace")),
        hidden_at=visibility.get("hidden_at"),
        hidden_by=visibility.get("hidden_by"),
        hidden_reason=visibility.get("hidden_reason"),
        archived_at=visibility.get("archived_at"),
        archived_by=visibility.get("archived_by"),
        archive_reason=visibility.get("archive_reason"),
    )


def _priority_request_to_inputs(data: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    priority = str(data.get("priority") or "").strip().upper()
    if priority:
        flags = {
            "P0": (True, True),
            "P1": (True, False),
            "P2": (False, True),
            "P3": (False, False),
        }
        if priority not in flags:
            raise ValueError("priority must be one of P0, P1, P2, P3")
        reason = str(data.get("reason") or data.get("priority_reason") or "manual_priority_change").strip()
        urgency, importance = flags[priority]
        return urgency, importance, data.get("urgency_reason") or reason, data.get("importance_reason") or reason
    return data.get("urgency"), data.get("importance"), data.get("urgency_reason"), data.get("importance_reason")


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


def _tool_metadata_from_raw_tool(raw_tool: dict, tool_name: str) -> ToolMetadata:
    spec = raw_tool.get("spec") if isinstance(raw_tool.get("spec"), dict) else {}
    spec_metadata = spec.get("metadata") if isinstance(spec.get("metadata"), dict) else {}
    raw_metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else {}
    metadata = dict(spec_metadata)
    metadata.update(raw_metadata)

    allow_roles = metadata.get("allow_roles")
    if tool_name in ("screen.collect", "screen.record"):
        screen_roles = ["user", "agent", "llm", "support", "admin"]
        allow_roles = list(dict.fromkeys((allow_roles or []) + screen_roles))
        metadata["requires_consent"] = False

    return ToolMetadata(
        domain=str(metadata.get("domain") or "system"),
        platforms=metadata.get("platforms", ["any"]),
        risk_level=normalize_risk_level(spec.get("risk_level") or metadata.get("risk_level") or "safe_read"),
        scopes=metadata.get("scopes", []),
        requires_consent=bool(metadata.get("requires_consent")),
        allow_roles=allow_roles,
        timeout_sec=metadata.get("timeout_sec"),
        idempotent=bool(metadata.get("idempotent")),
        origin=str(metadata.get("origin") or "builtin"),
        side_effects=bool(metadata.get("side_effects")),
        tool_kind=metadata.get("tool_kind") or "diagnostic",
    )


async def _resolve_tool_policy_decision(
    *,
    tool_service: ToolExecutionService,
    device_id: str,
    tool_name: str,
    actor_role: str,
    params: dict,
) -> PolicyDecision:
    policy_engine = PolicyEngine(config={"allow_remote_code": ALLOW_REMOTE_CODE})
    for source, method_name in (("device", "get_tools_list"), ("server", "get_tools_from_server")):
        method = getattr(tool_service, method_name, None)
        if not callable(method):
            continue
        try:
            raw_items = await method(device_id) or []
        except Exception as exc:
            logger.debug(
                f"[web_support_run_tool] policy lookup skipped: device_id={device_id}, "
                f"tool={tool_name}, source={source}, error={exc}"
            )
            raw_items = []
        raw_tool = _find_raw_tool_entry(raw_items, tool_name)
        if raw_tool is not None:
            return policy_engine.check_policy(
                actor_role=actor_role,
                tool_name=tool_name,
                metadata=_tool_metadata_from_raw_tool(raw_tool, tool_name),
                params=params,
            )

    fallback_metadata = ToolMetadata(risk_level="safe_read")
    if tool_name in ("screen.collect", "screen.record"):
        fallback_metadata = ToolMetadata(
            risk_level="sensitive_read",
            allow_roles=["user", "agent", "llm", "support", "admin"],
            requires_consent=False,
        )
    return policy_engine.check_policy(
        actor_role=actor_role,
        tool_name=tool_name,
        metadata=fallback_metadata,
        params=params,
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
        status_label=str(ticket_data.get("status_label") or status_label_ru(ticket_data.get("status"))),
        requester_status=str(ticket_data.get("requester_status") or "accepted"),
        requester_status_label=str(ticket_data.get("requester_status_label") or ""),
        public_status=str(ticket_data.get("public_status") or ticket_data.get("requester_status") or "accepted"),
        public_status_label=str(ticket_data.get("public_status_label") or ticket_data.get("requester_status_label") or ""),
        next_action_owner=ticket_data.get("next_action_owner"),
        next_action_due_at=ticket_data.get("next_action_due_at"),
        status_reason=ticket_data.get("status_reason"),
        priority=ticket_data.get("priority"),
        priority_class=ticket_data.get("priority_class"),
        queue_code=ticket_data.get("queue_code"),
        assignee_id=ticket_data.get("assignee_id"),
        assignee_display_name=ticket_data.get("assignee_display_name") or ticket_data.get("assignee_id"),
        requester_display_name=ticket_data.get("requester_display_name"),
        device_id=ticket_data.get("device_id"),
        updated_at=ticket_data.get("updated_at"),
        created_at=ticket_data.get("created_at"),
        hidden_from_workspace=bool(ticket_data.get("hidden_from_workspace")),
        hidden_at=ticket_data.get("hidden_at"),
        hidden_by=ticket_data.get("hidden_by"),
        hidden_reason=ticket_data.get("hidden_reason"),
        archived_at=ticket_data.get("archived_at"),
        archived_by=ticket_data.get("archived_by"),
        archive_reason=ticket_data.get("archive_reason"),
        requires_operator_action=bool(ticket_data.get("requires_operator_action")),
        unread_user_messages=unread_messages,
    )


def _iso_attr(obj, name: str) -> str | None:
    value = getattr(obj, name, None)
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ticket_timer_status(
    due_at: datetime | None,
    *,
    breached_at: datetime | None = None,
    paused_at: datetime | None = None,
    paused_seconds: int | None = None,
    now: datetime | None = None,
) -> str:
    due_at = _aware_datetime(due_at)
    breached_at = _aware_datetime(breached_at)
    paused_at = _aware_datetime(paused_at)
    now = _aware_datetime(now) or datetime.now(timezone.utc)
    if due_at is None:
        return "unknown"
    if breached_at is not None:
        return "breached"
    if paused_at is not None:
        return "paused"
    effective_due_at = due_at + timedelta(seconds=max(0, int(paused_seconds or 0)))
    remaining_seconds = int((effective_due_at - now).total_seconds())
    if remaining_seconds < 0:
        return "breached"
    if remaining_seconds <= 30 * 60:
        return "at_risk"
    return "ok"


def _ticket_timer_payload(
    ticket,
    *,
    due_attr: str,
    breached_attr: str | None = None,
    paused_attr: str | None = None,
    paused_seconds_attr: str | None = None,
    completed_attr: str | None = None,
    anchor_attr: str = "created_at",
    now: datetime | None = None,
) -> SupportTicketTimerPayload:
    due_at = _aware_datetime(getattr(ticket, due_attr, None))
    now = _aware_datetime(now) or datetime.now(timezone.utc)
    paused_seconds = int(getattr(ticket, paused_seconds_attr, None) or 0) if paused_seconds_attr else 0
    effective_due_at = due_at + timedelta(seconds=max(0, paused_seconds)) if due_at is not None else None
    anchor_at = _aware_datetime(getattr(ticket, anchor_attr, None) or getattr(ticket, "created_at", None))
    target_seconds = None
    if anchor_at is not None and due_at is not None:
        target_seconds = max(0, int((due_at - anchor_at).total_seconds()))
    if completed_attr and _aware_datetime(getattr(ticket, completed_attr, None)) is not None:
        return SupportTicketTimerPayload(
            due_at=None,
            remaining_seconds=None,
            target_seconds=target_seconds,
            status="unknown",
        )
    return SupportTicketTimerPayload(
        due_at=due_at.isoformat() if due_at is not None else None,
        remaining_seconds=int((effective_due_at - now).total_seconds()) if effective_due_at is not None else None,
        target_seconds=target_seconds,
        status=_ticket_timer_status(
            due_at,
            breached_at=getattr(ticket, breached_attr, None) if breached_attr else None,
            paused_at=getattr(ticket, paused_attr, None) if paused_attr else None,
            paused_seconds=paused_seconds,
            now=now,
        ),
    )


def _build_support_sla_ola_payload(ticket, now: datetime | None = None) -> SupportTicketSlaOlaPayload:
    now = _aware_datetime(now) or datetime.now(timezone.utc)
    return SupportTicketSlaOlaPayload(
        first_response=_ticket_timer_payload(
            ticket,
            due_attr="first_response_due_at",
            breached_attr="first_response_breached_at",
            paused_attr="sla_paused_at",
            paused_seconds_attr="sla_paused_seconds",
            completed_attr="first_response_at",
            now=now,
        ),
        resolution=_ticket_timer_payload(
            ticket,
            due_attr="resolution_due_at",
            breached_attr="resolution_breached_at",
            paused_attr="sla_paused_at",
            paused_seconds_attr="sla_paused_seconds",
            now=now,
        ),
        ola_ack=_ticket_timer_payload(
            ticket,
            due_attr="ola_ack_due_at",
            breached_attr="ola_ack_breached_at",
            paused_attr="ola_paused_at",
            paused_seconds_attr="ola_paused_seconds",
            now=now,
        ),
        ola_processing=_ticket_timer_payload(
            ticket,
            due_attr="ola_processing_due_at",
            breached_attr="ola_processing_breached_at",
            paused_attr="ola_paused_at",
            paused_seconds_attr="ola_paused_seconds",
            now=now,
        ),
    )


_PASSPORT_READINESS_FACTS: tuple[tuple[str, str, set[str]], ...] = (
    ("problem_identified", "Проблема идентифицирована", {"problem", "problem_identified"}),
    ("cause_found", "Причина установлена", {"root_cause", "cause", "cause_found"}),
    ("solution_applied", "Решение применено", {"solution", "solution_applied", "user_result"}),
    ("verified_and_closed", "Проверка и закрытие", {"verification", "verified_and_closed", "closure"}),
)


def _build_support_passport_readiness_payload(
    ticket_id: str,
    passport: SupportTicketPassportDetailPayload,
) -> SupportTicketPassportReadinessPayload:
    missing_fact_keys = {
        str(getattr(fact, "required_fact", "") or "").strip()
        for fact in passport.requirements.missing_facts
    }
    ready_statuses = {"ready", "approved", "final", "closed"}
    items: list[SupportTicketPassportReadinessItem] = []
    for key, label, related_facts in _PASSPORT_READINESS_FACTS:
        is_done = missing_fact_keys.isdisjoint(related_facts)
        if key == "verified_and_closed" and passport.status in ready_statuses:
            is_done = True
        items.append(
            SupportTicketPassportReadinessItem(
                key=key,
                label=label,
                status="done" if is_done else "pending",
            )
        )
    done = sum(1 for item in items if item.status == "done")
    return SupportTicketPassportReadinessPayload(
        ticket_id=str(ticket_id),
        status=passport.status,
        done=done,
        total=len(items),
        items=items,
    )


def _closure_action_for_requirement(requirement: object) -> tuple[str, str]:
    key = str(getattr(requirement, "key", "") or "").strip().lower()
    fact_key = str(getattr(requirement, "fact_key", "") or "").strip().lower()
    candidate_count = int(getattr(requirement, "candidate_count", 0) or 0)
    if candidate_count > 0 or "evidence" in key or fact_key:
        return "attach_evidence", "Добавить evidence"
    if "passport" in key:
        return "open_passport", "Открыть паспорт"
    if "resolution" in key or "summary" in key:
        return "edit_resolution", "Заполнить решение"
    if "approval" in key:
        return "check_approval", "Проверить согласование"
    if "worklog" in key:
        return "add_worklog", "Добавить worklog"
    return "review_requirement", "Проверить требование"


def _build_support_closure_plan_payload(
    ticket_id: str,
    detail: SupportTicketDetailPayload,
) -> SupportTicketClosurePlanPayload:
    requirements = list(detail.actions.closure_requirements or [])
    blockers: list[SupportTicketClosurePlanItem] = []
    for requirement in requirements:
        if requirement.met:
            continue
        action_kind, action_label = _closure_action_for_requirement(requirement)
        blockers.append(
            SupportTicketClosurePlanItem(
                key=requirement.key,
                label=requirement.label,
                met=False,
                detail=requirement.detail,
                source="closure_requirement",
                action_kind=action_kind,
                action_label=action_label,
                severity=requirement.severity or "blocking",
                candidate_count=requirement.candidate_count,
                fact_key=requirement.fact_key,
                blocking_for_closure=True,
            )
        )
    evidence_candidate_count = sum(item.candidate_count for item in blockers if item.action_kind == "attach_evidence")
    return SupportTicketClosurePlanPayload(
        ticket_id=str(ticket_id),
        ready_for_resolution=len(blockers) == 0,
        missing_count=len(blockers),
        total=len(requirements),
        evidence_candidate_count=evidence_candidate_count,
        recommended_next_action=blockers[0].action_label if blockers else None,
        blockers=blockers,
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


def _build_queue_counts(
    queues: list[object],
    entries: list[tuple[dict, SupportQueueTicketItem]],
) -> list[SupportQueueCountItem]:
    counts_by_code: dict[str, int] = {}
    for ticket_data, item in entries:
        code = str(ticket_data.get("queue_code") or item.queue_code or "").strip()
        if not code:
            continue
        counts_by_code[code] = counts_by_code.get(code, 0) + 1

    result: list[SupportQueueCountItem] = []
    known_codes: set[str] = set()
    for queue in queues:
        code = str(getattr(queue, "code", "") or "").strip()
        if not code:
            continue
        name = getattr(queue, "name", None) or code
        if _is_internal_support_workspace_nav_item(code, name):
            known_codes.add(code)
            continue
        known_codes.add(code)
        result.append(
            SupportQueueCountItem(
                id=getattr(queue, "id", None),
                code=code,
                name=name,
                count=counts_by_code.get(code, 0),
            )
        )

    for code, count in sorted(counts_by_code.items()):
        if code in known_codes:
            continue
        if _is_internal_support_workspace_nav_item(code):
            continue
        result.append(SupportQueueCountItem(id=None, code=code, name=code, count=count))
    return result


def _build_smart_view_counts(
    entries: list[tuple[dict, SupportQueueTicketItem]],
    options: list[dict[str, str]],
    *,
    actor_id: str,
    custom_smart_view_map: dict[str, dict[str, object]],
) -> list[SupportCountItem]:
    counts: list[SupportCountItem] = []
    for option in options:
        view_id = str(option.get("value") or "").strip()
        if not view_id:
            continue
        count = sum(
            1
            for ticket_data, _item in entries
            if matches_smart_view(
                ticket_data,
                view_id,
                actor_id=actor_id,
                custom_views=custom_smart_view_map,
            )
        )
        counts.append(
            SupportCountItem(
                value=view_id,
                label=str(option.get("label") or view_id),
                count=count,
            )
        )
    return counts


async def _load_support_queue_state(
    session,
    auth_context,
    *,
    limit: int,
    include_hidden: bool = False,
    include_archived: bool = False,
) -> SupportQueueState:
    filters: dict[str, object] = {"exclude_archived": not include_archived}
    if auth_context.actor_role == "support":
        filters["support_actor_id"] = auth_context.actor_id

    helpdesk_policy_repo = HelpdeskPolicyRepo(session)
    admin_config_repo = TicketAdminConfigRepo(session)
    custom_smart_views = await helpdesk_policy_repo.list_smart_views(include_inactive=False)
    active_queues = await admin_config_repo.list_queues(include_inactive=False)
    operator_smart_views = [
        view
        for view in custom_smart_views
        if not _is_internal_support_workspace_nav_item(
            view.get("code"),
            view.get("title"),
            view.get("name"),
            view.get("label"),
        )
    ]
    custom_smart_view_map = {
        str(view.get("code") or "").strip(): view
        for view in operator_smart_views
        if str(view.get("code") or "").strip()
    }

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

    accessible_entries: list[tuple[dict, SupportQueueTicketItem]] = []
    for ticket in tickets:
        ticket_data = ticket_to_dict(ticket, queue_map.get(getattr(ticket, "queue_id", None)))
        _apply_support_workspace_visibility(ticket_data, ticket)
        if _is_support_workspace_hidden(ticket_data) and not include_hidden:
            continue
        ticket_data.update(counters_map.get(getattr(ticket, "ticket_id", None), {}))
        ticket_data.update(
            {
                "ola_ack_due_at": _iso_attr(ticket, "ola_ack_due_at"),
                "ola_ack_breached_at": _iso_attr(ticket, "ola_ack_breached_at"),
                "ola_processing_due_at": _iso_attr(ticket, "ola_processing_due_at"),
                "ola_processing_breached_at": _iso_attr(ticket, "ola_processing_breached_at"),
            }
        )
        accessible_entries.append((ticket_data, _build_ticket_item(ticket_data)))

    return SupportQueueState(
        active_queues=active_queues,
        smart_options=smart_view_options(operator_smart_views),
        custom_smart_view_map=custom_smart_view_map,
        accessible_entries=accessible_entries,
    )


def _workspace_summary_view_counts(smart_view_counts: list[SupportCountItem]) -> dict[str, int]:
    counts_by_view = {item.value: item.count for item in smart_view_counts}
    return {
        alias: int(counts_by_view.get(source_view, 0))
        for alias, source_view in WORKSPACE_SUMMARY_VIEW_ALIASES.items()
    }


def _workspace_summary_queues(queue_counts: list[SupportQueueCountItem]) -> list[SupportWorkspaceSummaryQueueItem]:
    result: list[SupportWorkspaceSummaryQueueItem] = []
    for item in queue_counts:
        code = str(item.code or "").strip()
        item_id = code or (str(item.id) if item.id is not None else "")
        if not item_id:
            continue
        result.append(
            SupportWorkspaceSummaryQueueItem(
                id=item_id,
                code=code or None,
                name=str(item.name or code or item_id),
                count=item.count,
            )
        )
    return result


def _get_ticket_data_path(ticket_data: dict[str, object], path: str) -> object:
    current: object = ticket_data
    for part in str(path or "").split("."):
        if not part:
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _normalize_sort_value(value: object) -> object:
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.timestamp()
    if isinstance(value, (int, float, bool)):
        return value
    if value is None:
        return None
    parsed = None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    if parsed is not None:
        normalized = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return normalized.timestamp()
    return str(value).lower()


def _compare_sort_values(left: object, right: object, *, direction: str) -> int:
    left_value = _normalize_sort_value(left)
    right_value = _normalize_sort_value(right)
    if left_value is None and right_value is None:
        return 0
    if left_value is None:
        return 1
    if right_value is None:
        return -1
    if left_value == right_value:
        return 0
    result = -1 if left_value < right_value else 1
    return -result if direction == "desc" else result


def _apply_custom_smart_view_sort(
    entries: list[tuple[dict, SupportQueueTicketItem]],
    *,
    smart_view: str,
    custom_smart_view_map: dict[str, dict[str, object]],
) -> list[tuple[dict, SupportQueueTicketItem]]:
    view = custom_smart_view_map.get(smart_view)
    if not view:
        return entries
    sort_config = view.get("sort")
    if not isinstance(sort_config, list) or not sort_config:
        return entries

    normalized_sort: list[tuple[str, str]] = []
    for raw_item in sort_config:
        if not isinstance(raw_item, dict):
            continue
        field = str(raw_item.get("field") or "").strip()
        direction = str(raw_item.get("direction") or "asc").strip().lower()
        if field and direction in {"asc", "desc"}:
            normalized_sort.append((field, direction))
    if not normalized_sort:
        return entries

    def compare(left: tuple[dict, SupportQueueTicketItem], right: tuple[dict, SupportQueueTicketItem]) -> int:
        for field, direction in normalized_sort:
            result = _compare_sort_values(
                _get_ticket_data_path(left[0], field),
                _get_ticket_data_path(right[0], field),
                direction=direction,
            )
            if result:
                return result
        return 0

    return sorted(entries, key=cmp_to_key(compare))


async def _build_support_status_actions(session, ticket, *, is_staff: bool, is_admin: bool = False) -> SupportTicketActions:
    if not is_staff:
        return SupportTicketActions(status_options=[], can_send_internal_note=False)

    current_status = str(getattr(ticket, "status", "") or "")
    options: list[SupportStatusAction] = []
    for value, label in QUICK_STATUS_ACTIONS:
        if value == current_status:
            continue
        if await validate_transition_for_ticket(session, ticket, value, True):
            options.append(SupportStatusAction(value=value, label=label))
    approval_summary = await build_approval_summary(session, ticket, requester_safe=False)
    approval_action = None
    if approval_summary:
        approval_action = {
            "waiting_status": approval_summary.get("waiting_status"),
            "approved_transition": approval_summary.get("approved_transition"),
            "rejected_transition": approval_summary.get("rejected_transition"),
            "reject_requires_comment": bool(approval_summary.get("require_comment_on_reject")),
            "current_action_owner": approval_summary.get("current_action_owner"),
            "pending_count": approval_summary.get("pending_count", 0),
        }
    return SupportTicketActions(
        status_options=options,
        can_send_internal_note=True,
        can_hide_from_workspace=not _is_support_workspace_hidden(ticket),
        can_unhide_from_workspace=_is_support_workspace_hidden(ticket),
        can_archive_ticket=is_admin and getattr(ticket, "archived_at", None) is None,
        can_unarchive_ticket=is_admin and getattr(ticket, "archived_at", None) is not None,
        closure_requirements=await build_closure_requirements(session, ticket),
        approval=approval_action,
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


SUPPORT_TIMELINE_DIRECT_EVENT_TYPES = {
    "chat_message",
    "tool_call_started",
    "tool_call_result",
    "playbook_started",
    "diagnostic_result_classified",
    "routing_applied",
    "status_changed",
    "assignee_changed",
    "queue_changed",
    "queue_order_changed",
    "priority_changed",
    "classification_changed",
    "requester_profile_changed",
    "device_changed",
    "worklog_added",
}

SUPPORT_TIMELINE_EVENT_PREFIXES = (
    "sla_",
    "ola_",
    "passport_",
    "approval_",
    "remote_assist_",
)
SUPPORT_TIMELINE_FILTERS = {"all", "messages", "message", "internal", "diagnostics", "history"}
SUPPORT_TIMELINE_HISTORY_CATEGORIES = {"history", "sla", "ola", "passport", "approval", "remote_assist"}

SUPPORT_TIMELINE_DETAIL_KEYS = {
    "action",
    "actor_id",
    "actor_role",
    "approval_id",
    "approval_type",
    "assignee_id",
    "breached_at",
    "breached_fields",
    "comment",
    "decision",
    "due_at",
    "evidence_id",
    "evidence_type",
    "field_name",
    "from_queue_id",
    "from_status",
    "new_priority",
    "new_queue_code",
    "new_value",
    "old_priority",
    "old_queue_code",
    "old_value",
    "operation_id",
    "passport_id",
    "playbook_key",
    "previous_assignee_id",
    "reason",
    "session_id",
    "run_id",
    "source_ref",
    "status",
    "summary",
    "timer",
    "timer_type",
    "to_queue_id",
    "to_status",
    "tool_name",
    "trigger",
    "verification_status",
    "warning_type",
}


def _is_support_timeline_event(event_type: str) -> bool:
    return event_type in SUPPORT_TIMELINE_DIRECT_EVENT_TYPES or event_type.startswith(SUPPORT_TIMELINE_EVENT_PREFIXES)


def _timeline_event_category(event_type: str, payload: dict) -> str:
    if event_type == "chat_message":
        return "internal" if str(payload.get("visibility") or "public") == "internal" else "message"
    if event_type in {"tool_call_started", "tool_call_result", "playbook_started", "diagnostic_result_classified", "routing_applied"}:
        return "diagnostics"
    if event_type.startswith("sla_"):
        return "sla"
    if event_type.startswith("ola_"):
        return "ola"
    if event_type.startswith("passport_"):
        return "passport"
    if event_type.startswith("approval_"):
        return "approval"
    if event_type.startswith("remote_assist_"):
        return "remote_assist"
    return "history"


def _timeline_event_label(event_type: str) -> str:
    labels = {
        "status_changed": "Status changed",
        "assignee_changed": "Assignee changed",
        "queue_changed": "Queue changed",
        "queue_order_changed": "Queue order changed",
        "priority_changed": "Priority changed",
        "classification_changed": "Classification changed",
        "requester_profile_changed": "Requester changed",
        "device_changed": "Device changed",
        "worklog_added": "Worklog added",
        "diagnostic_result_classified": "Diagnostic result classified",
        "routing_applied": "Routing applied",
        "passport_generated": "Resolution passport generated",
        "passport_evidence_added": "Resolution evidence added",
        "passport_evidence_linked": "Resolution evidence linked",
        "passport_evidence_verified": "Resolution evidence verified",
        "passport_evidence_rejected": "Resolution evidence rejected",
        "approval_approved": "Approval approved",
        "approval_rejected": "Approval rejected",
        "approval_reminder_due": "Approval reminder due",
        "approval_escalated": "Approval escalated",
        "approval_timed_out": "Approval timed out",
        "remote_assist_requested": "Удалённая помощь запрошена",
        "remote_assist_consent_approved": "Удалённая помощь разрешена",
        "remote_assist_consent_denied": "Удалённая помощь отклонена",
        "remote_assist_session_started": "Удалённая помощь началась",
        "remote_assist_session_ended": "Удалённая помощь завершена",
        "remote_assist_session_expired": "Удалённая помощь истекла",
        "remote_assist_session_failed": "Удалённая помощь завершилась с ошибкой",
        "remote_assist_control_enabled": "Удалённое управление включено",
        "remote_assist_control_disabled": "Удалённое управление выключено",
        "remote_assist_control_rejected": "Команда управления отклонена",
        "remote_assist_clipboard_sync_enabled": "Буфер обмена синхронизируется",
        "remote_assist_clipboard_sync_disabled": "Синхронизация буфера обмена выключена",
        "remote_assist_file_transfer_started": "Передача файла началась",
        "remote_assist_file_transfer_completed": "Файл передан",
        "remote_assist_file_transfer_failed": "Передача файла завершилась с ошибкой",
        "sla_started": "SLA started",
        "sla_first_response_stopped": "SLA first response stopped",
        "sla_resolution_stopped": "SLA resolution stopped",
        "sla_paused": "SLA paused",
        "sla_resumed": "SLA resumed",
        "sla_warning": "SLA warning",
        "sla_breached": "SLA breached",
        "sla_reminder_sent": "SLA reminder sent",
        "ola_started": "OLA started",
        "ola_ack_stopped": "OLA acknowledgement stopped",
        "ola_processing_stopped": "OLA processing stopped",
        "ola_paused": "OLA paused",
        "ola_resumed": "OLA resumed",
        "ola_breached": "OLA breached",
    }
    return labels.get(event_type, event_type.replace("_", " ").strip().title() or "System event")


def _timeline_event_details(payload: dict) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key in SUPPORT_TIMELINE_DETAIL_KEYS and value is not None
    }


def _timeline_event_text(event_type: str, payload: dict) -> str:
    summary = str(payload.get("summary") or "").strip()
    if summary:
        return summary
    if event_type == "remote_assist_requested":
        operator = str(payload.get("operator_id") or payload.get("actor_id") or "Оператор").strip()
        return f"{operator} запросил удалённую помощь: Только просмотр."
    if event_type == "remote_assist_consent_approved":
        return "Пользователь разрешил удалённую помощь."
    if event_type == "remote_assist_consent_denied":
        return "Пользователь отклонил удалённую помощь."
    if event_type == "remote_assist_session_started":
        return "Удалённая помощь началась."
    if event_type == "remote_assist_session_ended":
        duration_sec = payload.get("duration_sec")
        if isinstance(duration_sec, int) and duration_sec > 0:
            minutes = duration_sec // 60
            seconds = duration_sec % 60
            return f"Удалённая помощь завершена. Длительность: {minutes:02d}:{seconds:02d}."
        return "Удалённая помощь завершена."
    if event_type == "remote_assist_session_expired":
        return "Удалённая помощь истекла."
    if event_type == "remote_assist_session_failed":
        return "Удалённая помощь завершилась с ошибкой."
    if event_type == "remote_assist_control_enabled":
        return "Оператор включил управление мышью и клавиатурой."
    if event_type == "remote_assist_control_disabled":
        return "Оператор выключил управление мышью и клавиатурой."
    if event_type == "remote_assist_control_rejected":
        return "Команда удалённого управления отклонена агентом."
    if event_type == "remote_assist_clipboard_sync_enabled":
        return "Автосинхронизация буфера обмена включена."
    if event_type == "remote_assist_clipboard_sync_disabled":
        return "Автосинхронизация буфера обмена выключена."
    if event_type == "remote_assist_file_transfer_started":
        name = str(payload.get("name") or "файл").strip()
        return f"Начата передача файла: {name}."
    if event_type == "remote_assist_file_transfer_completed":
        name = str(payload.get("name") or "файл").strip()
        return f"Файл передан на устройство: {name}."
    if event_type == "remote_assist_file_transfer_failed":
        return "Передача файла завершилась с ошибкой."
    if event_type == "status_changed":
        return " -> ".join(str(payload.get(key) or "").strip() for key in ("from_status", "to_status") if str(payload.get(key) or "").strip()) or "Status changed"
    if event_type == "assignee_changed":
        assignee = str(payload.get("new_value") or payload.get("assignee_id") or "").strip()
        return f"Assigned to {assignee}" if assignee else "Assignee changed"
    if event_type == "queue_changed":
        queue = str(payload.get("new_queue_code") or payload.get("to_queue_id") or "").strip()
        return f"Moved to queue {queue}" if queue else "Queue changed"
    if event_type == "priority_changed":
        old_priority = str(payload.get("old_priority") or payload.get("old_value") or "").strip()
        new_priority = str(payload.get("new_priority") or payload.get("new_value") or payload.get("priority") or "").strip()
        if old_priority or new_priority:
            return f"Priority {old_priority or '?'} -> {new_priority or '?'}"
        return "Priority changed"
    return _timeline_event_label(event_type)


def _timeline_nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _timeline_candidate_steps(payload: dict[str, Any]) -> list[Any]:
    for path in (
        ("steps",),
        ("checks",),
        ("diagnostics",),
        ("result", "steps"),
        ("result", "checks"),
        ("result", "diagnostics"),
        ("result", "observations"),
        ("observations", "steps"),
        ("diagnostic", "steps"),
    ):
        raw_steps = _timeline_nested_value(payload, path)
        if isinstance(raw_steps, list) and raw_steps:
            return raw_steps
        if isinstance(raw_steps, dict) and raw_steps:
            return [
                {"key": key, **value} if isinstance(value, dict) else {"key": key, "value": value}
                for key, value in raw_steps.items()
            ]
    return []


def _timeline_operation_steps(payload: dict) -> list[dict[str, Any]]:
    raw_steps = _timeline_candidate_steps(payload)
    steps: list[dict[str, Any]] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue
        name = str(
            raw_step.get("name")
            or raw_step.get("title")
            or raw_step.get("label")
            or raw_step.get("check")
            or raw_step.get("stage")
            or raw_step.get("key")
            or ""
        ).strip()
        status = str(
            raw_step.get("status")
            or raw_step.get("state")
            or raw_step.get("result")
            or raw_step.get("outcome")
            or ""
        ).strip()
        value = (
            raw_step.get("value")
            if raw_step.get("value") is not None
            else raw_step.get("summary")
            if raw_step.get("summary") is not None
            else raw_step.get("message")
            if raw_step.get("message") is not None
            else raw_step.get("output")
        )
        details = raw_step.get("details")
        if details is None:
            details = raw_step.get("detail") or raw_step.get("description") or raw_step.get("error") or raw_step.get("stderr")
        if not name and not status and value is None:
            continue
        value_text = "" if value is None else str(value)
        details_text = None if details is None else str(details).strip() or None
        if details_text == value_text:
            details_text = None
        steps.append(
            {
                "name": name or "step",
                "status": status or "unknown",
                "value": value_text,
                "details": details_text,
            }
        )
    return steps[:20]


def _timeline_tool_name(payload: dict[str, Any]) -> str | None:
    tool_name = str(payload.get("tool_name") or payload.get("tool") or "").strip()
    return tool_name or None


def _timeline_renderable_result_payload(payload: dict[str, Any]) -> Any | None:
    if "result" in payload:
        result = payload.get("result")
    elif "output" in payload:
        result = payload.get("output")
    else:
        return None
    if isinstance(result, dict) and isinstance(result.get("output"), (dict, list)):
        result = result["output"]
    try:
        encoded = json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return None
    if len(encoded.encode("utf-8")) > SUPPORT_TIMELINE_RENDER_RESULT_MAX_BYTES:
        return None
    return result


async def _timeline_presentation_by_tool(
    *,
    session: Any,
    state: Any,
    ticket: Ticket,
    events: list[Any],
) -> dict[str, dict[str, Any]]:
    tool_ids: set[str] = set()
    for event in events:
        if str(getattr(event, "event_type", "") or "") != "tool_call_result":
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict) or _timeline_renderable_result_payload(payload) is None:
            continue
        tool_name = _timeline_tool_name(payload)
        if tool_name:
            tool_ids.add(tool_name)
    if not tool_ids:
        return {}

    from diagnostics.capability_registry import CapabilityRegistry
    from diagnostics.presentation_overrides import ToolPresentationOverrideService

    service = ToolPresentationOverrideService(session)
    descriptors_by_id: dict[str, Any] = {}
    try:
        registry = CapabilityRegistry(tool_service=ToolExecutionService(state), state=state)
        for descriptor in await registry.list_capabilities(device_id=str(getattr(ticket, "device_id", "") or "") or None):
            if descriptor.id in tool_ids:
                descriptors_by_id[descriptor.id] = descriptor
    except Exception as exc:
        logger.debug(f"[support_timeline] capability registry presentation lookup failed: {exc}")

    for tool_id in tool_ids - set(descriptors_by_id):
        descriptor = await service.descriptor_from_persisted_capability(tool_id)
        if descriptor is not None:
            descriptors_by_id[tool_id] = descriptor

    if not descriptors_by_id:
        return {}
    effective_descriptors = await service.apply_to_capabilities(list(descriptors_by_id.values()))
    return {
        descriptor.id: {
            "schema": descriptor.effective_presentation_schema if isinstance(descriptor.effective_presentation_schema, dict) else {},
            "source": descriptor.presentation_schema_source,
        }
        for descriptor in effective_descriptors
    }


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


def _requester_timeline_projection_fields(
    event: object,
    ticket: object | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    event_type = None
    if isinstance(event, dict):
        event_type = event.get("event_type") or event.get("type")
    else:
        event_type = getattr(event, "event_type", None)
    event_payload = payload if payload is not None else getattr(event, "payload", None)
    if not isinstance(event_payload, dict):
        event_payload = {}
    projection = build_requester_timeline_projection(
        {"event_type": event_type, "payload": event_payload},
        ticket=ticket,
    )
    return projection_to_fields(projection)


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
        event_category=_timeline_event_category("chat_message", payload if isinstance(payload, dict) else {}),
        event_label="Message",
        event_details=_timeline_event_details(payload) if isinstance(payload, dict) else {},
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
        operation_steps=[],
        **_requester_timeline_projection_fields(event, ticket=ticket, payload=payload if isinstance(payload, dict) else None),
    )


def _build_timeline_entry(
    event: object,
    ticket: object | None = None,
    *,
    presentation_by_tool: dict[str, dict[str, Any]] | None = None,
) -> SupportTicketMessage:
    event_type = str(getattr(event, "event_type", None) or "")
    payload = getattr(event, "payload", None) or {}

    if event_type == "chat_message":
        return _build_timeline_message(event, ticket=ticket)

    if event_type == "playbook_started":
        playbook_key = str(payload.get("playbook_key") or "diagnostic.playbook")
        run_id = payload.get("playbook_run_id")
        operation_id = payload.get("operation_id") or payload.get("first_operation_id")
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
            event_category=_timeline_event_category(event_type, payload),
            event_label=_timeline_event_label(event_type),
            event_details=_timeline_event_details(payload),
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
            operation_id=str(operation_id) if operation_id else None,
            trace_id=str(payload.get("trace_id")) if payload.get("trace_id") else None,
            can_retry=False,
            can_cancel=_operation_can_cancel("running"),
            retry_url=None,
            cancel_url=_operation_cancel_url(operation_id, "running"),
            retry_disabled_reason=_operation_retry_disabled_reason("running", None, None),
            cancel_disabled_reason=_operation_cancel_disabled_reason("running"),
            details_url=_operation_details_url(operation_id),
            **_requester_timeline_projection_fields(event, ticket=ticket, payload=payload),
        )

    if event_type == "tool_call_started":
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Инструмент")
        operation_id = payload.get("operation_id")
        return SupportTicketMessage(
            message_id=None,
            event_id=getattr(event, "id", None),
            event_type=event_type,
            event_category=_timeline_event_category(event_type, payload),
            event_label=_timeline_event_label(event_type),
            event_details=_timeline_event_details(payload),
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
            operation_id=str(operation_id) if operation_id else None,
            trace_id=str(payload.get("trace_id")) if payload.get("trace_id") else None,
            can_retry=False,
            can_cancel=_operation_can_cancel("accepted"),
            retry_url=None,
            cancel_url=_operation_cancel_url(operation_id, "accepted"),
            retry_disabled_reason=_operation_retry_disabled_reason("accepted", None, None),
            cancel_disabled_reason=_operation_cancel_disabled_reason("accepted"),
            details_url=_operation_details_url(operation_id),
            **_requester_timeline_projection_fields(event, ticket=ticket, payload=payload),
        )

    if event_type == "tool_call_result":
        tool_name = str(payload.get("tool_name") or payload.get("tool") or "Инструмент")
        operation_id = payload.get("operation_id")
        status = str(payload.get("status") or "unknown")
        result_payload = _timeline_renderable_result_payload(payload)
        presentation = (presentation_by_tool or {}).get(tool_name) or {}
        presentation_schema = presentation.get("schema") if isinstance(presentation.get("schema"), dict) else None
        retry_count = _coerce_int(payload.get("retry_count"))
        max_retries = _coerce_int(payload.get("max_retries"))
        retryable = _coerce_bool(payload.get("retryable"))
        if retryable is None:
            retryable = _operation_retryable(status, retry_count, max_retries)
        error_code = str(payload.get("error_code") or "").strip() or None
        return SupportTicketMessage(
            message_id=None,
            event_id=getattr(event, "id", None),
            event_type=event_type,
            event_category=_timeline_event_category(event_type, payload),
            event_label=_timeline_event_label(event_type),
            event_details=_timeline_event_details(payload),
            from_role="system",
            sender_display_name="Система",
            text=f"Результат инструмента: {tool_name}",
            ts=_event_timestamp_iso(event, payload),
            visibility="system",
            direction="system",
            attachments=list(payload.get("artifacts") or []),
            reply_to=None,
            tool_name=tool_name,
            tool_status=status,
            result_summary=str(payload.get("summary") or payload.get("error") or "Без краткого результата"),
            result_preview=_tool_result_preview(payload),
            result_payload=result_payload,
            result_presentation_schema=presentation_schema,
            result_presentation_schema_source=str(presentation.get("source") or "none"),
            operation_steps=_timeline_operation_steps(payload),
            operation_id=str(operation_id) if operation_id else None,
            trace_id=str(payload.get("trace_id")) if payload.get("trace_id") else None,
            duration_ms=_payload_duration_ms(payload),
            retry_count=retry_count,
            max_retries=max_retries,
            retryable=retryable,
            can_retry=retryable,
            can_cancel=_operation_can_cancel(status),
            retry_url=_operation_retry_url(operation_id, status, retry_count, max_retries),
            cancel_url=_operation_cancel_url(operation_id, status),
            retry_disabled_reason=_operation_retry_disabled_reason(status, retry_count, max_retries),
            cancel_disabled_reason=_operation_cancel_disabled_reason(status),
            error_code=error_code,
            error_category=_operation_error_category(status, error_code, str(payload.get("error") or "")),
            details_url=_operation_details_url(operation_id),
            **_requester_timeline_projection_fields(event, ticket=ticket, payload=payload),
        )

    return SupportTicketMessage(
        message_id=None,
        event_id=getattr(event, "id", None),
        event_type=event_type or "system",
        event_category=_timeline_event_category(event_type, payload),
        event_label=_timeline_event_label(event_type),
        event_details=_timeline_event_details(payload),
        from_role="system",
        sender_display_name="Система",
        text=_timeline_event_text(event_type, payload),
        ts=_event_timestamp_iso(event, payload),
        visibility="system",
        direction="system",
        attachments=[],
        reply_to=None,
        tool_name=None,
        tool_status=None,
        result_summary=None,
        result_preview=None,
        **_requester_timeline_projection_fields(event, ticket=ticket, payload=payload),
    )


def _normalize_support_timeline_filter(raw_filter: str | None) -> str:
    value = str(raw_filter or "all").strip().lower()
    if value not in SUPPORT_TIMELINE_FILTERS:
        return "all"
    return "messages" if value == "message" else value


def _support_timeline_entry_matches_filter(entry: SupportTicketMessage, timeline_filter: str) -> bool:
    if timeline_filter == "all":
        return True
    if timeline_filter == "messages":
        return entry.event_category == "message"
    if timeline_filter == "internal":
        return entry.event_category == "internal" or entry.visibility == "internal"
    if timeline_filter == "diagnostics":
        return entry.event_category == "diagnostics"
    if timeline_filter == "history":
        return entry.event_category in SUPPORT_TIMELINE_HISTORY_CATEGORIES
    return True


async def _build_support_timeline_payload(
    repo: TicketEventsRepo,
    ticket: Ticket,
    *,
    session: Any | None = None,
    state: Any = None,
    timeline_filter: str = "all",
    limit: int = 80,
) -> SupportTicketTimelinePayload:
    normalized_filter = _normalize_support_timeline_filter(timeline_filter)
    event_limit = min(max(limit * 3, limit), 1000)
    events = await repo.get_events(ticket.ticket_id, since_agent_seq=None, limit=event_limit)
    presentation_by_tool = (
        await _timeline_presentation_by_tool(session=session, state=state, ticket=ticket, events=events)
        if session is not None
        else {}
    )
    items = [
        _build_timeline_entry(event, ticket=ticket, presentation_by_tool=presentation_by_tool)
        for event in events
        if _is_support_timeline_event(str(getattr(event, "event_type", None) or ""))
    ]
    filtered_items = [
        item
        for item in items
        if _support_timeline_entry_matches_filter(item, normalized_filter)
    ]
    visible_items = filtered_items[-limit:]
    return SupportTicketTimelinePayload(
        ticket_id=str(ticket.ticket_id),
        filter=normalized_filter,
        items=visible_items,
        total=len(visible_items),
        limit=limit,
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


def _support_tool_metadata(raw_tool: dict, tool_name: str) -> ToolMetadata:
    try:
        return _tool_metadata_from_raw_tool(raw_tool, tool_name)
    except Exception as exc:
        logger.debug(f"[web_support_tools] metadata fallback: tool={tool_name}, error={exc}")
        spec = raw_tool.get("spec") if isinstance(raw_tool.get("spec"), dict) else {}
        metadata = raw_tool.get("metadata") if isinstance(raw_tool.get("metadata"), dict) else {}
        return ToolMetadata(
            domain=str(metadata.get("domain") or "system"),
            platforms=metadata.get("platforms", ["any"]),
            risk_level=normalize_risk_level(spec.get("risk_level") or metadata.get("risk_level") or "safe_read"),
            scopes=metadata.get("scopes", []),
            requires_consent=bool(metadata.get("requires_consent")),
            allow_roles=metadata.get("allow_roles"),
            timeout_sec=metadata.get("timeout_sec"),
            idempotent=bool(metadata.get("idempotent")),
            origin=str(metadata.get("origin") or "builtin"),
            side_effects=bool(metadata.get("side_effects")),
            tool_kind=metadata.get("tool_kind") or "diagnostic",
        )


def _support_tool_policy_labels(
    *,
    metadata: ToolMetadata,
    required_permission: str,
    install_required: bool,
    requires_consent: bool,
) -> list[str]:
    labels = [f"permission:{required_permission}"]
    if metadata.allow_roles:
        labels.append("roles:" + ",".join(str(role) for role in metadata.allow_roles))
    labels.append("consent:required" if requires_consent else "consent:not_required")
    if install_required:
        labels.append("install:required")
    if metadata.scopes:
        labels.append("scopes:" + ",".join(str(scope) for scope in metadata.scopes[:3]))
    return labels


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
    execution = raw_tool.get("execution") if isinstance(raw_tool.get("execution"), dict) else spec.get("execution", {})
    deployment = raw_tool.get("deployment") if isinstance(raw_tool.get("deployment"), dict) else spec.get("deployment", {})
    safety = raw_tool.get("safety") if isinstance(raw_tool.get("safety"), dict) else spec.get("safety", {})
    readiness = raw_tool.get("readiness") if isinstance(raw_tool.get("readiness"), dict) else spec.get("readiness", {})
    evidence = raw_tool.get("evidence") if isinstance(raw_tool.get("evidence"), dict) else spec.get("evidence", {})
    artifacts = raw_tool.get("artifacts") if isinstance(raw_tool.get("artifacts"), dict) else spec.get("artifacts", {})
    module_name = raw_tool.get("module")
    if not module_name and "." in tool_name:
        module_name = tool_name.split(".", 1)[0]
    metadata_model = _support_tool_metadata(raw_tool, tool_name)
    risk_level = str(spec.get("risk_level") or metadata_model.risk_level or "safe_read")
    requires_consent = bool(safety.get("requires_consent", metadata.get("requires_consent")))
    install_required = bool(raw_tool.get("install_required", deployment.get("install_required_on_agent", False)))
    required_permission = _tool_risk_permission(risk_level)
    return SupportToolItem(
        tool_name=tool_name,
        module_name=str(module_name).strip() if module_name else None,
        description=str(raw_tool.get("description") or "").strip() or None,
        domain=metadata_model.domain,
        tool_kind=metadata_model.tool_kind,
        risk_level=risk_level,
        requires_consent=requires_consent,
        install_required=install_required,
        required_permission=required_permission,
        allowed_roles=[str(role) for role in (metadata_model.allow_roles or [])],
        policy_labels=_support_tool_policy_labels(
            metadata=metadata_model,
            required_permission=required_permission,
            install_required=install_required,
            requires_consent=requires_consent,
        ),
        source=source,
        params_schema=_normalize_tool_schema(params_schema),
        presets=_normalize_tool_presets(presets),
        execution=dict(execution or {}),
        deployment=dict(deployment or {}),
        safety=dict(safety or {}),
        readiness=dict(readiness or {}),
        evidence=dict(evidence or {}),
        artifacts=dict(artifacts or {}),
    )


def _iso(value: object) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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
    for raw_block in manifest_json.get("blocks") or []:
        if not isinstance(raw_block, dict):
            continue
        execution_target = str(raw_block.get("execution_target") or "").strip()
        if execution_target and execution_target not in {"agent_builtin", "agent_managed_module"}:
            continue
        tool_name = str(raw_block.get("tool") or raw_block.get("tool_name") or "").strip()
        if tool_name and tool_name not in tools:
            tools.append(tool_name)
    return tools


def _required_capabilities_from_manifest(manifest_json: object) -> list[dict[str, str | None]]:
    if not isinstance(manifest_json, dict):
        return []
    capabilities: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for raw_item in manifest_json.get("required_capabilities") or []:
        if not isinstance(raw_item, dict):
            continue
        capability_id = str(raw_item.get("capability_id") or raw_item.get("id") or "").strip()
        if not capability_id or capability_id in seen:
            continue
        seen.add(capability_id)
        capabilities.append(
            {
                "capability_id": capability_id,
                "execution_target": str(raw_item.get("execution_target") or "").strip() or None,
            }
        )
    for raw_block in manifest_json.get("blocks") or []:
        if not isinstance(raw_block, dict):
            continue
        capability_id = str(
            raw_block.get("capability_id") or raw_block.get("capability") or raw_block.get("tool") or ""
        ).strip()
        if not capability_id or capability_id in seen:
            continue
        seen.add(capability_id)
        capabilities.append(
            {
                "capability_id": capability_id,
                "execution_target": str(raw_block.get("execution_target") or "").strip() or None,
            }
        )
    return capabilities


@dataclass(frozen=True)
class PlaybookLaunchReadiness:
    can_run: bool
    label: str
    missing_tools: list[str]
    missing_params: list[str]


def _tool_names_from_raw_entries(raw_items: list[object] | None) -> set[str]:
    names: set[str] = set()
    for raw_item in raw_items or []:
        if not isinstance(raw_item, dict):
            continue
        for value in (raw_item.get("tool"), raw_item.get("name")):
            text = str(value or "").strip()
            if text:
                names.add(text)
        aliases = raw_item.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                text = str(alias or "").strip()
                if text:
                    names.add(text)
    return names


def _schema_required_param_names(schema: object) -> list[str]:
    if not isinstance(schema, dict):
        return []
    raw_required = schema.get("required")
    if not isinstance(raw_required, list):
        return []
    names: list[str] = []
    for raw_name in raw_required:
        name = str(raw_name or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _schema_param_has_default(schema: object, param_name: str) -> bool:
    if not isinstance(schema, dict):
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return False
    param_schema = properties.get(param_name)
    return isinstance(param_schema, dict) and "default" in param_schema


def _block_required_param_gaps(block: dict) -> list[str]:
    executable_id = str(
        block.get("tool") or block.get("tool_name") or block.get("capability_id") or block.get("capability") or ""
    ).strip()
    if not executable_id:
        return []
    params = block.get("params") if isinstance(block.get("params"), dict) else {}
    default_params = block.get("default_params") if isinstance(block.get("default_params"), dict) else {}
    tool_manifest = block.get("tool_manifest") if isinstance(block.get("tool_manifest"), dict) else {}
    schema = tool_manifest.get("params_schema") or block.get("params_schema")
    missing: list[str] = []
    for param_name in _schema_required_param_names(schema):
        if param_name in params or param_name in default_params or _schema_param_has_default(schema, param_name):
            continue
        missing.append(f"{executable_id}.{param_name}")
    return missing


def _required_param_gaps_from_manifest(manifest_json: object) -> list[str]:
    if not isinstance(manifest_json, dict):
        return []
    missing: list[str] = []
    for raw_block in manifest_json.get("blocks") or []:
        if not isinstance(raw_block, dict):
            continue
        for item in _block_required_param_gaps(raw_block):
            if item not in missing:
                missing.append(item)
    return missing


def _build_playbook_launch_readiness(
    manifest_json: object,
    *,
    device_id: str | None,
    available_tool_names: set[str],
) -> PlaybookLaunchReadiness:
    if not device_id:
        return PlaybookLaunchReadiness(
            can_run=False,
            label="Нужна привязка к устройству",
            missing_tools=[],
            missing_params=[],
        )

    required_tools = _required_tools_from_manifest(manifest_json)
    required_capabilities = _required_capabilities_from_manifest(manifest_json)
    missing_tools = []
    for tool in required_tools:
        builtin_prefix = tool.split(".", 1)[0].lower() if "." in tool else ""
        if tool in available_tool_names or builtin_prefix in AGENT_BUILTIN_MODULES:
            continue
        missing_tools.append(tool)
    for capability in required_capabilities:
        capability_id = str(capability.get("capability_id") or "").strip()
        execution_target = str(capability.get("execution_target") or "").strip()
        if execution_target and execution_target not in {"agent_builtin", "agent_managed_module"}:
            continue
        builtin_prefix = capability_id.split(".", 1)[0].lower() if "." in capability_id else ""
        if capability_id in available_tool_names or builtin_prefix in AGENT_BUILTIN_MODULES:
            continue
        if capability_id not in missing_tools:
            missing_tools.append(capability_id)
    missing_params = _required_param_gaps_from_manifest(manifest_json)
    label_parts: list[str] = []
    if missing_tools:
        label_parts.append("Недоступны инструменты: " + ", ".join(missing_tools[:3]))
    if missing_params:
        label_parts.append("Не заполнены параметры: " + ", ".join(missing_params[:3]))
    if label_parts:
        return PlaybookLaunchReadiness(
            can_run=False,
            label="; ".join(label_parts),
            missing_tools=missing_tools,
            missing_params=missing_params,
        )
    return PlaybookLaunchReadiness(
        can_run=True,
        label="Готов к запуску",
        missing_tools=[],
        missing_params=[],
    )


def _operation_result_payload(operation: object) -> dict:
    raw = getattr(operation, "result_summary", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    text = raw.strip()
    if not text:
        return {}
    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return None


def _duration_ms(started_at: object, finished_at: object) -> int | None:
    if started_at is None or finished_at is None:
        return None
    if not isinstance(started_at, datetime) or not isinstance(finished_at, datetime):
        return None
    try:
        return max(0, int((finished_at - started_at).total_seconds() * 1000))
    except Exception:
        return None


def _payload_duration_ms(payload: dict) -> int | None:
    for key in ("duration_ms", "elapsed_ms"):
        duration = _coerce_int(payload.get(key))
        if duration is not None:
            return max(0, duration)
    duration_seconds = _coerce_int(payload.get("duration_seconds") or payload.get("elapsed_seconds"))
    if duration_seconds is not None:
        return max(0, duration_seconds * 1000)
    return None


def _operation_error_category(status: str | None, error_code: str | None, error_message: str | None = None) -> str | None:
    raw = f"{error_code or ''} {error_message or ''}".lower()
    if status in {"timed_out", "timeout"} or "timeout" in raw or "timed out" in raw:
        return "timeout"
    if status in {"denied"} or "consent" in raw or "denied" in raw:
        return "consent"
    if "policy" in raw or "permission" in raw or "forbidden" in raw or "rbac" in raw:
        return "policy"
    if "offline" in raw or "transport" in raw or "websocket" in raw or "connection" in raw:
        return "transport"
    if status in {"failed", "partial"} or error_code or error_message:
        return "execution"
    return None


def _operation_retryable(status: str | None, retry_count: int | None, max_retries: int | None) -> bool:
    return bool(status in {"failed", "timed_out", "timeout"} and max_retries is not None and (retry_count or 0) < max_retries)


_OPERATION_CANCELABLE_STATUSES = {"accepted", "in_progress", "queued", "running", "sent", "waiting_consent"}
_OPERATION_FAILED_STATUSES = {"failed", "timed_out", "timeout"}


def _operation_can_cancel(status: str | None) -> bool:
    return bool(status in _OPERATION_CANCELABLE_STATUSES)


def _operation_cancel_disabled_reason(status: str | None) -> str | None:
    if _operation_can_cancel(status):
        return None
    if status in {"succeeded", "failed", "timed_out", "timeout", "canceled", "cancelled", "denied"}:
        return "already_finished"
    if not status or status == "unknown":
        return "status_unknown"
    return "status_not_cancelable"


def _operation_retry_disabled_reason(status: str | None, retry_count: int | None, max_retries: int | None) -> str | None:
    if _operation_retryable(status, retry_count, max_retries):
        return None
    if status not in _OPERATION_FAILED_STATUSES:
        return "status_not_retryable"
    if max_retries is None:
        return "retry_policy_missing"
    if (retry_count or 0) >= max_retries:
        return "retry_limit_reached"
    return "retry_not_available"


def _operation_details_url(operation_id: object) -> str | None:
    value = str(operation_id or "").strip()
    return f"/api/operations/{value}" if value else None


def _observer_trace_url(trace_id: object) -> str | None:
    value = str(trace_id or "").strip()
    return f"/app/admin/observer?trace_id={value}" if value else None


def _operation_trace_relation(operation: Operation, *, ticket_root_trace_id: str | None, scope: str) -> str:
    trace_id = str(getattr(operation, "trace_id", None) or "").strip()
    retry_of_operation_id = str(getattr(operation, "retry_of_operation_id", None) or "").strip()
    if retry_of_operation_id:
        return "retry_child"
    if scope == "playbook" or getattr(operation, "playbook_run_id", None):
        return "playbook_child"
    if trace_id and ticket_root_trace_id and trace_id == ticket_root_trace_id:
        return "ticket_root"
    if trace_id:
        return "operation_child"
    return "unknown"


def _operation_cancel_url(operation_id: object, status: str | None) -> str | None:
    value = str(operation_id or "").strip()
    if not value or not _operation_can_cancel(status):
        return None
    return f"/api/operations/{value}/cancel"


def _operation_retry_url(operation_id: object, status: str | None, retry_count: int | None, max_retries: int | None) -> str | None:
    value = str(operation_id or "").strip()
    if not value or not _operation_retryable(status, retry_count, max_retries):
        return None
    return f"/api/operations/{value}/retry"


def _operation_policy_labels(
    status: str | None,
    *,
    can_cancel: bool,
    retryable: bool,
    requires_consent: bool,
    cancel_disabled_reason: str | None,
    retry_disabled_reason: str | None,
) -> list[str]:
    labels: list[str] = []
    labels.append("cancel:available" if can_cancel else f"cancel:{cancel_disabled_reason or 'unavailable'}")
    if retryable:
        labels.append(f"retry:{retry_disabled_reason or 'available'}")
    elif status in _OPERATION_FAILED_STATUSES:
        labels.append(f"retry:{retry_disabled_reason or 'unavailable'}")
    if requires_consent:
        labels.append("consent:required")
    return labels


def _build_operation_display(operation: object) -> tuple[str, str]:
    status = str(getattr(operation, "status", None) or "unknown")
    if status == "succeeded":
        payload = _operation_result_payload(operation)
        ok_value = payload.get("ok")
        error_code = str(payload.get("error_code") or "").strip()
        if ok_value is False or error_code:
            return ("failed", f"Ошибка результата: {error_code or 'ok=false'}")
    if status in {"failed", "timed_out", "canceled"}:
        message = str(getattr(operation, "error_message", None) or status).strip()
        return (status, message)
    return (status, status)


def _string_list(value: object) -> list[str]:
    raw_items = value if isinstance(value, list) else []
    items: list[str] = []
    for raw_item in raw_items:
        item = str(raw_item or "").strip()
        if item and item not in items:
            items.append(item)
    return items


def _support_diagnostic_policy_payload(ticket: object) -> SupportDiagnosticPolicyPayload | None:
    custom_fields = getattr(ticket, "custom_fields", None)
    if not isinstance(custom_fields, dict):
        return None
    request_template = custom_fields.get("request_template")
    if not isinstance(request_template, dict):
        return None
    policy = request_template.get("diagnostic_policy") or request_template.get("diagnostics")
    if not isinstance(policy, dict) or not policy:
        return None

    auto_run = policy.get("auto_run") if isinstance(policy.get("auto_run"), dict) else {}
    consent = policy.get("consent") if isinstance(policy.get("consent"), dict) else {}
    attach_results = policy.get("attach_results") if isinstance(policy.get("attach_results"), dict) else {}
    reroute_raw = policy.get("reroute_by_result") if isinstance(policy.get("reroute_by_result"), dict) else {}
    reroute_by_result = {
        str(result_key).strip(): str(queue_code).strip()
        for result_key, queue_code in reroute_raw.items()
        if str(result_key).strip() and str(queue_code).strip()
    }

    suggested_playbooks = _string_list(policy.get("suggested_playbooks"))
    legacy_playbook = str(policy.get("suggested_playbook_id") or "").strip()
    if legacy_playbook and legacy_playbook not in suggested_playbooks:
        suggested_playbooks.append(legacy_playbook)

    return SupportDiagnosticPolicyPayload(
        suggested_playbooks=suggested_playbooks,
        auto_run_enabled=bool(auto_run.get("enabled") or policy.get("auto_run_enabled")),
        auto_run_priorities=_string_list(auto_run.get("only_for_priorities")),
        requester_consent_required=bool(
            policy.get("requires_user_consent") or consent.get("required_for_requester_device")
        ),
        high_risk_consent_required=bool(consent.get("required_for_high_risk_tools")),
        attach_to_timeline=bool(attach_results.get("to_timeline")),
        attach_to_passport=bool(attach_results.get("to_passport")),
        attach_as_evidence=bool(attach_results.get("as_evidence")),
        reroute_by_result=reroute_by_result,
    )


def _playbook_step_error_payload(error_json: object) -> tuple[str | None, str, str | None]:
    if not isinstance(error_json, dict):
        return (None, "Шаг завершился ошибкой", None)
    code = str(error_json.get("code") or error_json.get("error_code") or "").strip() or None
    message = str(error_json.get("message") or error_json.get("error") or code or "Шаг завершился ошибкой").strip()
    stage = str(error_json.get("stage") or "").strip() or None
    return (code, message, stage)


async def _build_support_recent_playbook_runs(session, ticket: object, *, limit: int = 5) -> list[SupportPlaybookRecentRun]:
    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    if not ticket_id:
        return []
    rows = await session.execute(
        select(PlaybookRun, PlaybookVersion, Playbook)
        .join(PlaybookVersion, PlaybookRun.playbook_version_id == PlaybookVersion.id)
        .join(Playbook, PlaybookVersion.playbook_id == Playbook.id)
        .where(PlaybookRun.context_json["ticket_id"].as_string() == ticket_id)
        .order_by(PlaybookRun.scheduled_at.desc(), PlaybookRun.id.desc())
        .limit(limit)
    )
    runs = list(rows.all())
    if not runs:
        return []

    run_ids = [int(run.id) for run, _version, _playbook in runs]
    step_rows = await session.execute(
        select(PlaybookStepRun, PlaybookStep)
        .join(PlaybookStep, PlaybookStepRun.playbook_step_id == PlaybookStep.id)
        .where(PlaybookStepRun.playbook_run_id.in_(run_ids), PlaybookStepRun.status == "failed")
        .order_by(PlaybookStepRun.id.asc())
    )
    errors_by_run: dict[int, list[SupportPlaybookRecentRunStepError]] = {}
    for step_run, step in step_rows.all():
        error_code, error_message, stage = _playbook_step_error_payload(step_run.error_json)
        errors_by_run.setdefault(int(step_run.playbook_run_id), []).append(
            SupportPlaybookRecentRunStepError(
                step_key=str(getattr(step, "step_key", "") or "") or None,
                tool_name=str(getattr(step, "tool", "") or "") or None,
                error_code=error_code,
                error_message=error_message,
                stage=stage,
            )
        )

    return [
        SupportPlaybookRecentRun(
            playbook_run_id=int(run.id),
            playbook_version_id=int(run.playbook_version_id),
            playbook_key=str(playbook.key) if getattr(playbook, "key", None) is not None else None,
            playbook_name=str(playbook.name) if getattr(playbook, "name", None) is not None else None,
            status=str(run.status),
            error_code=run.error_code,
            error_message=run.error_message,
            trigger_type=run.trigger_type,
            started_at=_iso(run.started_at),
            finished_at=_iso(run.finished_at),
            step_errors=errors_by_run.get(int(run.id), []),
        )
        for run, _version, playbook in runs
    ]


async def _playbook_available_tool_names(device_id: str | None, state: object | None = None) -> set[str]:
    if not device_id:
        return set()
    tool_service = ToolExecutionService(state)
    try:
        device_tools_raw = await tool_service.get_tools_list(device_id) or []
    except Exception as exc:
        logger.debug(f"[support_playbooks] device tool preflight failed: device_id={device_id} error={exc}")
        device_tools_raw = []
    try:
        server_tools_raw = await tool_service.get_tools_from_server(device_id) or []
    except Exception as exc:
        logger.debug(f"[support_playbooks] server tool preflight failed: device_id={device_id} error={exc}")
        server_tools_raw = []
    return _tool_names_from_raw_entries(device_tools_raw) | _tool_names_from_raw_entries(server_tools_raw)


async def _build_support_playbooks_payload(
    session,
    ticket: object,
    state: object | None = None,
) -> SupportTicketPlaybooksPayload:
    device_id = str(getattr(ticket, "device_id", "") or "").strip() or None
    available_tool_names = await _playbook_available_tool_names(device_id, state)
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
        readiness = _build_playbook_launch_readiness(
            version.manifest_json,
            device_id=device_id,
            available_tool_names=available_tool_names,
        )
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
                missing_tools=readiness.missing_tools,
                missing_params=readiness.missing_params,
                can_run=readiness.can_run,
                readiness_label=readiness.label,
                updated_at=_iso(version.published_at or version.created_at),
            )
        )
    recent_runs = await _build_support_recent_playbook_runs(session, ticket)
    return SupportTicketPlaybooksPayload(
        ticket_id=str(getattr(ticket, "ticket_id")),
        device_id=device_id,
        diagnostic_policy=_support_diagnostic_policy_payload(ticket),
        playbooks=playbooks,
        recent_runs=recent_runs,
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


async def _recent_ticket_operations(session, ticket: object, *, limit: int = 5) -> list[tuple[Operation, str]]:
    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    if not ticket_id:
        return []
    run_rows = await session.execute(
        select(PlaybookRun.id).where(PlaybookRun.context_json["ticket_id"].as_string() == ticket_id)
    )
    playbook_run_ids = [int(item) for item in run_rows.scalars().all()]
    predicates = [Operation.ticket_id == ticket_id]
    if playbook_run_ids:
        predicates.append(Operation.playbook_run_id.in_(playbook_run_ids))
    rows = await session.execute(
        select(Operation)
        .where(or_(*predicates))
        .order_by(Operation.queued_at.desc())
        .limit(limit)
    )
    scoped: list[tuple[Operation, str]] = []
    for operation in rows.scalars().all():
        scope = "ticket"
        if getattr(operation, "playbook_run_id", None) in playbook_run_ids:
            scope = "playbook"
        scoped.append((operation, scope))
    return scoped


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
        service = await registry_repo.get_service(getattr(asset, "service_id", None)) if asset else None
        service_owner_queue = None
        if getattr(service, "owner_queue_id", None):
            service_owner_queue = await session.get(TicketQueue, service.owner_queue_id)
        location_id = getattr(asset, "location_id", None) or getattr(person, "location_id", None)
        department_id = getattr(asset, "department_id", None) or getattr(person, "department_id", None)
        location = await registry_repo.get_location(location_id) if location_id else None
        department = await registry_repo.get_department(department_id) if department_id else None
        if asset or person or location or department:
            registry_snapshot = SupportTicketRegistrySnapshot(
                person_id=getattr(person, "person_id", None),
                person_display_name=getattr(person, "display_name", None),
                person_phone=getattr(person, "phone", None),
                person_email=getattr(person, "email", None),
                person_source=getattr(person, "source", None),
                department_id=getattr(department, "department_id", None),
                department_name=getattr(department, "name", None),
                location_id=getattr(location, "location_id", None),
                location_display_name=getattr(location, "display_name", None),
                building=getattr(location, "building", None),
                floor=getattr(location, "floor", None),
                room=getattr(location, "room", None),
                asset_id=getattr(asset, "asset_id", None),
                asset_name=getattr(asset, "name", None),
                asset_type=getattr(asset, "asset_type", None),
                service_id=getattr(service, "service_id", None) or getattr(asset, "service_id", None),
                service_name=getattr(service, "name", None),
                service_owner_queue_id=getattr(service, "owner_queue_id", None),
                service_owner_queue_name=getattr(service_owner_queue, "name", None),
                service_source=getattr(service, "source", None),
            )

    device_snapshot = SupportTicketDeviceSnapshot(
        device_id=getattr(ticket, "device_id", None),
        hostname=getattr(device, "hostname", None) if device is not None else None,
        os=getattr(device, "os", None) if device is not None else None,
        agent_version=getattr(device, "agent_version", None) if device is not None else None,
        last_seen_at=(device.last_seen_at.isoformat() if device is not None and device.last_seen_at else None),
        online=bool(presence.agent_online),
    )

    latest_operation_rows = await _recent_ticket_operations(session, ticket, limit=5)
    retry_source_ids = [
        str(getattr(operation, "retry_of_operation_id", "") or "").strip()
        for operation, _scope in latest_operation_rows
        if str(getattr(operation, "retry_of_operation_id", "") or "").strip()
    ]
    retry_source_trace_by_id: dict[str, str | None] = {}
    if retry_source_ids:
        source_rows = (
            await session.execute(
                select(Operation.operation_id, Operation.trace_id).where(Operation.operation_id.in_(retry_source_ids))
            )
        ).all()
        retry_source_trace_by_id = {str(row[0]): row[1] for row in source_rows}
    operation_ids = [
        str(getattr(operation, "operation_id", "") or "").strip()
        for operation, _scope in latest_operation_rows
        if str(getattr(operation, "operation_id", "") or "").strip()
    ]
    consent_required_by_operation_id: dict[str, bool] = {}
    if operation_ids:
        event_rows = (
            await session.execute(
                select(TicketEvent.operation_id, TicketEvent.payload).where(
                    TicketEvent.ticket_id == str(getattr(ticket, "ticket_id", "") or ""),
                    TicketEvent.operation_id.in_(operation_ids),
                    TicketEvent.event_type == "tool_call_started",
                )
            )
        ).all()
        for operation_id, payload in event_rows:
            payload_dict = payload if isinstance(payload, dict) else {}
            consent_required_by_operation_id[str(operation_id)] = bool(payload_dict.get("requires_consent"))

    ticket_root_trace_id = str(getattr(ticket, "observer_root_trace_id", None) or "").strip() or None
    latest_operations: list[SupportTicketOperationSnapshot] = []
    for operation, scope in latest_operation_rows:
        display_status, display_label = _build_operation_display(operation)
        retry_count = int(getattr(operation, "retry_count", 0) or 0)
        max_retries = int(getattr(operation, "max_retries", 0) or 0)
        error_code = str(getattr(operation, "error_code", None) or "").strip() or None
        retryable = _operation_retryable(display_status, retry_count, max_retries)
        can_cancel = _operation_can_cancel(display_status)
        cancel_disabled_reason = _operation_cancel_disabled_reason(display_status)
        retry_disabled_reason = _operation_retry_disabled_reason(display_status, retry_count, max_retries)
        retry_of_operation_id = str(getattr(operation, "retry_of_operation_id", "") or "").strip() or None
        latest_operations.append(
            SupportTicketOperationSnapshot(
                operation_id=operation.operation_id,
                kind=operation.kind,
                status=operation.status,
                display_status=display_status,
                display_label=display_label,
                scope=scope,
                tool_name=operation.tool_name,
                command_name=operation.command_name,
                queued_at=operation.queued_at.isoformat() if operation.queued_at else None,
                started_at=operation.started_at.isoformat() if operation.started_at else None,
                finished_at=operation.finished_at.isoformat() if operation.finished_at else None,
                duration_ms=_duration_ms(operation.started_at or operation.queued_at, operation.finished_at),
                trace_id=operation.trace_id,
                retry_count=retry_count,
                max_retries=max_retries,
                retryable=retryable,
                can_retry=retryable,
                can_cancel=can_cancel,
                retry_url=_operation_retry_url(operation.operation_id, display_status, retry_count, max_retries),
                cancel_url=_operation_cancel_url(operation.operation_id, display_status),
                retry_disabled_reason=retry_disabled_reason,
                cancel_disabled_reason=cancel_disabled_reason,
                policy_labels=_operation_policy_labels(
                    display_status,
                    can_cancel=can_cancel,
                    retryable=retryable,
                    requires_consent=consent_required_by_operation_id.get(str(operation.operation_id), False),
                    cancel_disabled_reason=cancel_disabled_reason,
                    retry_disabled_reason=retry_disabled_reason,
                ),
                error_code=error_code,
                error_category=_operation_error_category(display_status, error_code, operation.error_message),
                details_url=_operation_details_url(operation.operation_id),
                result_summary=operation.result_summary,
                error_message=operation.error_message,
                trace_relation=_operation_trace_relation(operation, ticket_root_trace_id=ticket_root_trace_id, scope=scope),
                root_trace_id=ticket_root_trace_id,
                root_trace_url=_observer_trace_url(ticket_root_trace_id),
                trace_url=_observer_trace_url(operation.trace_id),
                retry_of_operation_id=retry_of_operation_id,
                retry_source_trace_id=retry_source_trace_by_id.get(retry_of_operation_id) if retry_of_operation_id else None,
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
    observer_data = await _safe_support_observer_summary(session, ticket.ticket_id)
    timeline_payload = await _build_support_timeline_payload(
        repo,
        ticket,
        session=session,
        state=request.app.get("state"),
        timeline_filter="all",
        limit=80,
    )
    timeline = timeline_payload.items

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
        is_admin=auth_context.actor_role == "admin",
    )
    request_form = _build_support_request_form_payload(ticket_data)
    custom_fields = ticket_data.get("custom_fields") if isinstance(ticket_data.get("custom_fields"), dict) else {}
    approval_summary = await build_approval_summary(session, ticket, requester_safe=False)
    quality = await _build_support_quality_payload(session, ticket.ticket_id)

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
            first_response_at=ticket_data.get("first_response_at"),
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
            hidden_from_workspace=bool(_support_workspace_visibility(ticket).get("hidden_from_workspace")),
            hidden_at=_support_workspace_visibility(ticket).get("hidden_at"),
            hidden_by=_support_workspace_visibility(ticket).get("hidden_by"),
            hidden_reason=_support_workspace_visibility(ticket).get("hidden_reason"),
            archived_at=_support_workspace_visibility(ticket).get("archived_at"),
            archived_by=_support_workspace_visibility(ticket).get("archived_by"),
            archive_reason=_support_workspace_visibility(ticket).get("archive_reason"),
            resolution_code=ticket_data.get("resolution_code"),
            resolution_summary=ticket_data.get("resolution_summary"),
            requester_resolution_summary=ticket_data.get("requester_resolution_summary"),
            evidence_required=bool(ticket_data.get("evidence_required")),
            evidence_ref=ticket_data.get("evidence_ref"),
            closure_feedback=ticket_data.get("closure_feedback") or {},
            approval_summary=approval_summary,
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
            root_trace=SupportTicketObserverTraceCompact.model_validate(observer_data["root_trace_compact"])
            if observer_data.get("root_trace_compact")
            else None,
            related_traces=[
                SupportTicketObserverTraceCompact.model_validate(item)
                for item in observer_data.get("related_traces_compact", [])
            ],
            active_traces=[
                SupportTicketObserverTraceCompact.model_validate(item)
                for item in observer_data.get("active_traces_compact", [])
            ],
            error_traces=[
                SupportTicketObserverTraceCompact.model_validate(item)
                for item in observer_data.get("error_traces_compact", [])
            ],
            signatures=[
                SupportTicketObserverSignature.model_validate(item)
                for item in observer_data.get("signatures_compact", [])
            ],
            recent_occurrences=[
                SupportTicketObserverOccurrenceCompact.model_validate(item)
                for item in observer_data.get("recent_occurrences_compact", [])
            ],
        ),
        timeline=timeline,
        snapshot=snapshot,
        actions=actions,
        quality=quality,
    )


async def _build_support_quality_payload(session, ticket_id: str) -> SupportTicketQualityPayload:
    feedback_rows = (
        await session.execute(
            select(TicketFeedback)
            .where(TicketFeedback.ticket_id == ticket_id)
            .order_by(TicketFeedback.is_latest.desc(), TicketFeedback.submitted_at.desc())
            .limit(5)
        )
    ).scalars().all()
    reopen_rows = (
        await session.execute(
            select(TicketReopenEvent)
            .where(TicketReopenEvent.ticket_id == ticket_id)
            .order_by(TicketReopenEvent.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    review_rows = (
        await session.execute(
            select(TicketQualityReview)
            .where(TicketQualityReview.ticket_id == ticket_id)
            .order_by(TicketQualityReview.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    action_rows = (
        await session.execute(
            select(ContinuousImprovementAction)
            .where(ContinuousImprovementAction.ticket_id == ticket_id)
            .order_by(ContinuousImprovementAction.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    latest_feedback = feedback_rows[0] if feedback_rows else None
    indicators: list[str] = []
    if latest_feedback and (latest_feedback.rating <= 3 or latest_feedback.problem_resolved is False):
        indicators.append("low_csat")
    if reopen_rows:
        indicators.append("reopened")
    if any(review.status in {"open", "assigned", "in_review", "action_required", "failed"} for review in review_rows):
        indicators.append("qa_attention")
    if any(action.status in {"open", "assigned", "in_progress", "blocked"} for action in action_rows):
        indicators.append("improvement_open")

    return SupportTicketQualityPayload(
        latest_feedback=SupportTicketQualityFeedback(
            feedback_id=latest_feedback.feedback_id,
            rating=int(latest_feedback.rating),
            sentiment=latest_feedback.sentiment,
            problem_resolved=latest_feedback.problem_resolved,
            resolution_confirmed=latest_feedback.resolution_confirmed,
            reason_codes=list(latest_feedback.reason_codes or []),
            comment=latest_feedback.comment,
            source_surface=latest_feedback.source_surface,
            submitted_at=_iso(latest_feedback.submitted_at),
        )
        if latest_feedback
        else None,
        reopen_events=[
            SupportTicketQualityReopenEvent(
                reopen_id=row.reopen_id,
                reason_code=row.reason_code,
                reason_comment=row.reason_comment,
                previous_status=row.previous_status,
                new_status=row.new_status,
                created_at=_iso(row.created_at),
            )
            for row in reopen_rows
        ],
        reviews=[
            SupportTicketQualityReview(
                review_id=row.review_id,
                review_type=row.review_type,
                severity=row.severity,
                status=row.status,
                assigned_to_actor_id=row.assigned_to_actor_id,
                score=row.score,
                due_at=_iso(row.due_at),
                created_at=_iso(row.created_at),
                closed_at=_iso(row.closed_at),
            )
            for row in review_rows
        ],
        improvement_actions=[
            SupportTicketQualityAction(
                action_id=row.action_id,
                source_kind=row.source_kind,
                action_type=row.action_type,
                title=row.title,
                status=row.status,
                priority=row.priority,
                owner_actor_id=row.owner_actor_id,
                due_at=_iso(row.due_at),
                created_at=_iso(row.created_at),
                closed_at=_iso(row.closed_at),
            )
            for row in action_rows
        ],
        indicators=indicators,
    )


async def _safe_support_observer_summary(session, ticket_id: str) -> dict[str, Any]:
    try:
        return await ObserverOverlayService(session).get_ticket_observer_summary(ticket_id)
    except Exception as exc:
        logger.warning(
            f"[support_observer_summary] degraded: ticket_id={ticket_id}, error={exc}"
        )
        summary = SupportTicketObserverSummary(
            ticket_id=ticket_id,
            trace_count=0,
            active_trace_count=0,
            error_trace_count=0,
            signature_count=0,
            health_label="degraded",
            latest_error_label="Observer summary unavailable",
            latest_error_stage="observer_projection",
        )
        return {
            "summary": summary.model_dump(),
            "root_trace_compact": None,
            "related_traces_compact": [],
            "active_traces_compact": [],
            "error_traces_compact": [],
            "signatures_compact": [],
            "recent_occurrences_compact": [],
        }


async def _build_support_knowledge_suggestions_payload(session, ticket: Ticket) -> SupportTicketKnowledgeSuggestionsPayload:
    ticket_id = str(getattr(ticket, "ticket_id", "") or "")
    kb_links = await TicketEventsRepo(session).list_kb_links(ticket_id)
    suggestions = await build_knowledge_suggestions(session, ticket, kb_links)
    custom_fields = getattr(ticket, "custom_fields", None) if isinstance(getattr(ticket, "custom_fields", None), dict) else {}
    request_template = custom_fields.get("request_template") if isinstance(custom_fields.get("request_template"), dict) else {}
    p2_suggestions = await KnowledgeSuggestionService(session).suggest(
        {
            "service_code": getattr(ticket, "service_code", None),
            "offering_code": getattr(ticket, "offering_code", None),
            "request_template_key": request_template.get("key") or request_template.get("template_code"),
            "ticket_type": getattr(ticket, "ticket_type", None),
            "query": f"{getattr(ticket, 'title', '')} {getattr(ticket, 'description', '')}".strip(),
            "surface": "support_workspace",
        },
        actor_role="support",
    )
    p2_articles = [
        SupportKnowledgeArticle(
            id=str(item.get("slug") or item.get("item_id") or ""),
            title=str(item.get("title") or item.get("slug") or ""),
            url=f"/app/knowledge?item={item.get('slug') or item.get('item_id')}",
        )
        for item in p2_suggestions.get("suggestions", [])
        if isinstance(item, dict) and (item.get("slug") or item.get("item_id")) and item.get("title")
    ]
    return SupportTicketKnowledgeSuggestionsPayload(
        ticket_id=ticket_id,
        similar_tickets=[
            SupportKnowledgeSimilarTicket(
                id=item.id,
                number=item.number,
                subject=item.subject,
                resolution_summary=item.resolution_summary,
            )
            for item in suggestions.similar_tickets
        ],
        articles=[
            SupportKnowledgeArticle(id=item.id, title=item.title, url=item.url)
            for item in suggestions.articles
        ] + p2_articles,
        ai_summary=SupportKnowledgeAiSummary(
            text=suggestions.ai_summary.text,
            sources=suggestions.ai_summary.sources,
            confidence=suggestions.ai_summary.confidence,
            source_count=suggestions.ai_summary.source_count,
        ),
        diagnostics=SupportKnowledgeDiagnostics(
            provider=suggestions.diagnostics.provider,
            provider_version=suggestions.diagnostics.provider_version,
            provider_status=suggestions.diagnostics.provider_status,
            external_provider_status=suggestions.diagnostics.external_provider_status,
            fallback_reason=suggestions.diagnostics.fallback_reason,
            catalog_entry_count=suggestions.diagnostics.catalog_entry_count,
            query_tokens=suggestions.diagnostics.query_tokens,
            source_counts=suggestions.diagnostics.source_counts,
            query_signals=suggestions.diagnostics.query_signals,
            article_matches=suggestions.diagnostics.article_matches,
            similar_ticket_matches=suggestions.diagnostics.similar_ticket_matches,
        ),
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
async def handle_web_support_ticket_timeline(request: web.Request):
    timeline_filter = _normalize_support_timeline_filter(request.query.get("filter"))
    try:
        limit = min(max(int(request.query.get("limit", "80")), 1), 300)
    except ValueError:
        limit = 80
    try:
        async with get_session() as session:
            ticket, error, repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await _build_support_timeline_payload(
                repo,
                ticket,
                session=session,
                state=request.app.get("state"),
                timeline_filter=timeline_filter,
                limit=limit,
            )
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_timeline] failed: "
            f"ticket_id={request.match_info.get('ticket_id')}, filter={timeline_filter}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Timeline временно недоступен",
                "error_code": "SUPPORT_TIMELINE_UNAVAILABLE",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketTimelinePayload](data=payload))


async def _handle_support_visibility_mutation(
    request: web.Request,
    *,
    hidden: bool | None = None,
    archived: bool | None = None,
    action: str,
    event_type: str,
    admin_only: bool = False,
) -> web.Response:
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    reason = str(data.get("reason") or "").strip() or None
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            if admin_only and auth_context.actor_role != "admin":
                return _permission_denied("ticket.archive.manage")

            now = datetime.now(timezone.utc)
            previous_visibility = _support_workspace_visibility(ticket)
            custom_fields = _support_workspace_custom_fields(
                ticket,
                hidden=hidden,
                archived=archived,
                actor_id=auth_context.actor_id,
                reason=reason,
                now=now,
            )
            updates: dict[str, Any] = {"custom_fields": custom_fields}
            if archived is True:
                updates["archived_at"] = now
            elif archived is False:
                updates["archived_at"] = None
            await repo.update_ticket(ticket.ticket_id, **updates)
            refreshed_ticket = await repo.get_ticket(ticket.ticket_id)
            payload = {
                "actor_id": auth_context.actor_id,
                "actor_role": auth_context.actor_role,
                "reason": reason,
                "hidden": hidden,
                "archived": archived,
                "previous": previous_visibility,
                "current": _support_workspace_visibility(refreshed_ticket),
            }
            event_result = await repo.add_event(
                ticket_id=refreshed_ticket.ticket_id,
                device_id=refreshed_ticket.device_id,
                agent_seq=None,
                event_type=event_type,
                payload=payload,
            )
            await session.commit()
            await _push_ticket_event(request, refreshed_ticket.ticket_id, event_result, event_type, payload)
            refreshed_ticket = await repo.get_ticket(refreshed_ticket.ticket_id)
            return json_model_response(
                SuccessResponse[SupportTicketMutationActionResult](
                    data=await _support_mutation_result(session, refreshed_ticket, action=action)
                )
            )
    except Exception as exc:
        logger.warning(
            f"[web_support_visibility_mutation] failed: "
            f"ticket_id={request.match_info.get('ticket_id')}, action={action}, error={exc}"
        )
        return _support_json_error("Не удалось обновить видимость тикета", status=503, error_code="SUPPORT_VISIBILITY_FAILED")


@require_auth("admin", "support")
async def handle_web_support_hide_ticket(request: web.Request):
    return await _handle_support_visibility_mutation(
        request,
        hidden=True,
        action="hide",
        event_type="ticket_hidden_from_workspace",
    )


@require_auth("admin", "support")
async def handle_web_support_unhide_ticket(request: web.Request):
    return await _handle_support_visibility_mutation(
        request,
        hidden=False,
        action="unhide",
        event_type="ticket_unhidden_from_workspace",
    )


@require_auth("admin", "support")
async def handle_web_support_archive_ticket(request: web.Request):
    return await _handle_support_visibility_mutation(
        request,
        archived=True,
        action="archive",
        event_type="ticket_archived_from_workspace",
        admin_only=True,
    )


@require_auth("admin", "support")
async def handle_web_support_unarchive_ticket(request: web.Request):
    return await _handle_support_visibility_mutation(
        request,
        archived=False,
        action="unarchive",
        event_type="ticket_unarchived_from_workspace",
        admin_only=True,
    )


def _mass_action_item(
    *,
    ticket_id: str,
    action: str,
    status: str,
    message: str,
    ticket_code: str | None = None,
    result: SupportTicketMutationActionResult | SupportToolActionResult | None = None,
) -> SupportQueueMassActionItem:
    return SupportQueueMassActionItem(
        ticket_id=ticket_id,
        ticket_code=ticket_code,
        status=status,
        action=action,
        message=message,
        result=result,
    )


def _normalize_mass_action_ids(raw_ids: list[str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        ticket_id = str(raw_id or "").strip()
        if not ticket_id or ticket_id in seen:
            continue
        seen.add(ticket_id)
        ids.append(ticket_id)
    return ids


async def _support_mass_action_internal_note(
    *,
    repo: TicketEventsRepo,
    ticket: Any,
    auth_context: Any,
    text: str,
) -> tuple[Any, dict[str, Any]]:
    message_id = str(uuid.uuid4())
    payload = {
        "message_id": message_id,
        "sender_role": _message_role_from_auth(auth_context),
        "sender_display_name": auth_context.actor_id,
        "from": _message_role_from_auth(auth_context),
        "text": text,
        "visibility": "internal",
        "bulk_action": True,
    }
    payload = enrich_chat_payload_with_requester_name(ticket, payload)
    result = await repo.add_event(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        agent_seq=None,
        event_type="chat_message",
        payload=payload,
        event_id=message_id,
    )
    return result, payload


@require_auth("admin", "support")
async def handle_web_support_queue_saved_views(request: web.Request):
    auth_context = request["auth_context"]
    try:
        async with get_session() as session:
            denied = await _require_permission(session, auth_context, "ticket.queue.view")
            if denied:
                return denied
            accessible_queue_ids = await _support_accessible_queue_ids(session, auth_context)
            views = (
                await session.execute(
                    select(SupportQueueSavedView)
                    .where(_saved_view_visibility_clause(auth_context, accessible_queue_ids))
                    .order_by(SupportQueueSavedView.is_favorite.desc(), SupportQueueSavedView.updated_at.desc())
                )
            ).scalars().all()
            serialized = [_serialize_support_queue_saved_view(view) for view in views]
            personal_default = next(
                (
                    view
                    for view in serialized
                    if view.scope == "personal"
                    and view.owner_actor_id == str(getattr(auth_context, "actor_id", "") or "")
                    and view.is_default
                ),
                None,
            )
            fallback_default = next((view for view in serialized if view.is_default), None)
            default_view = personal_default or fallback_default
            return json_model_response(
                SuccessResponse[SupportQueueSavedViewsPayload](
                    data=SupportQueueSavedViewsPayload(
                        views=serialized,
                        default_view_id=default_view.id if default_view else None,
                        default_columns=default_view.columns if default_view else SUPPORT_QUEUE_DEFAULT_VIEW_COLUMNS,
                    )
                )
            )
    except Exception as exc:
        logger.warning(f"[web_support_queue_saved_views] failed: {exc}")
        return _support_json_error("Saved queue views are unavailable", status=500, error_code="SERVER_ERROR")


@require_auth("admin", "support")
async def handle_web_support_queue_saved_view_create(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        payload = SupportQueueSavedViewUpsertRequest.model_validate(data)
    except Exception as exc:
        return _support_json_error(str(exc), status=400, error_code="VALIDATION_ERROR")

    name = _normalize_saved_view_name(payload.name)
    if not name:
        return _support_json_error("Saved view name is required", status=400, error_code="VALIDATION_ERROR")

    auth_context = request["auth_context"]
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    scope = _normalize_saved_view_scope(payload.scope)
    queue_id = payload.queue_id if scope == "queue" else None

    try:
        async with get_session() as session:
            denied = await _require_permission(session, auth_context, "ticket.queue.view")
            if denied:
                return denied
            accessible_queue_ids = await _support_accessible_queue_ids(session, auth_context)
            invalid_scope = await _validate_saved_view_scope(
                session,
                auth_context,
                scope=scope,
                queue_id=queue_id,
                accessible_queue_ids=accessible_queue_ids,
            )
            if invalid_scope:
                return invalid_scope
            now = datetime.now(timezone.utc)
            view = SupportQueueSavedView(
                id=str(uuid.uuid4()),
                name=name,
                scope=scope,
                owner_actor_id=actor_id if scope == "personal" else None,
                queue_id=queue_id,
                filters_json=_normalize_saved_view_filters(payload.filters),
                columns_json=_normalize_saved_view_columns(payload.columns),
                sort_json=_normalize_saved_view_sort(payload.sort),
                is_favorite=bool(payload.is_favorite),
                is_default=bool(payload.is_default),
                created_at=now,
                updated_at=now,
                created_by=actor_id or None,
                updated_by=actor_id or None,
            )
            session.add(view)
            await session.flush()
            if view.is_default:
                await _clear_saved_view_default_peers(session, view)
            await session.commit()
            return json_model_response(SuccessResponse[SupportQueueSavedViewItem](data=_serialize_support_queue_saved_view(view)))
    except Exception as exc:
        logger.warning(f"[web_support_queue_saved_view_create] failed: {exc}")
        return _support_json_error("Saved view was not created", status=500, error_code="SERVER_ERROR")


@require_auth("admin", "support")
async def handle_web_support_queue_saved_view_update(request: web.Request):
    view_id = str(request.match_info.get("view_id") or "").strip()
    if not view_id:
        return _support_json_error("view_id is required", status=400, error_code="VALIDATION_ERROR")
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        payload = SupportQueueSavedViewUpsertRequest.model_validate(data)
    except Exception as exc:
        return _support_json_error(str(exc), status=400, error_code="VALIDATION_ERROR")

    name = _normalize_saved_view_name(payload.name)
    if not name:
        return _support_json_error("Saved view name is required", status=400, error_code="VALIDATION_ERROR")

    auth_context = request["auth_context"]
    actor_id = str(getattr(auth_context, "actor_id", "") or "").strip()
    scope = _normalize_saved_view_scope(payload.scope)
    queue_id = payload.queue_id if scope == "queue" else None

    try:
        async with get_session() as session:
            denied = await _require_permission(session, auth_context, "ticket.queue.view")
            if denied:
                return denied
            view = (await session.execute(select(SupportQueueSavedView).where(SupportQueueSavedView.id == view_id))).scalar_one_or_none()
            if view is None:
                return _support_json_error("Saved view not found", status=404, error_code="NOT_FOUND")
            if not _can_manage_saved_view(auth_context, view):
                return _support_json_error("Saved view is owned by another operator", status=403, error_code="FORBIDDEN")
            accessible_queue_ids = await _support_accessible_queue_ids(session, auth_context)
            invalid_scope = await _validate_saved_view_scope(
                session,
                auth_context,
                scope=scope,
                queue_id=queue_id,
                accessible_queue_ids=accessible_queue_ids,
            )
            if invalid_scope:
                return invalid_scope
            view.name = name
            view.scope = scope
            view.owner_actor_id = actor_id if scope == "personal" else None
            view.queue_id = queue_id
            view.filters_json = _normalize_saved_view_filters(payload.filters)
            view.columns_json = _normalize_saved_view_columns(payload.columns)
            view.sort_json = _normalize_saved_view_sort(payload.sort)
            view.is_favorite = bool(payload.is_favorite)
            view.is_default = bool(payload.is_default)
            view.updated_at = datetime.now(timezone.utc)
            view.updated_by = actor_id or None
            await session.flush()
            if view.is_default:
                await _clear_saved_view_default_peers(session, view)
            await session.commit()
            return json_model_response(SuccessResponse[SupportQueueSavedViewItem](data=_serialize_support_queue_saved_view(view)))
    except Exception as exc:
        logger.warning(f"[web_support_queue_saved_view_update] failed view_id={view_id}: {exc}")
        return _support_json_error("Saved view was not updated", status=500, error_code="SERVER_ERROR")


@require_auth("admin", "support")
async def handle_web_support_queue_saved_view_delete(request: web.Request):
    view_id = str(request.match_info.get("view_id") or "").strip()
    if not view_id:
        return _support_json_error("view_id is required", status=400, error_code="VALIDATION_ERROR")
    auth_context = request["auth_context"]
    try:
        async with get_session() as session:
            denied = await _require_permission(session, auth_context, "ticket.queue.view")
            if denied:
                return denied
            view = (await session.execute(select(SupportQueueSavedView).where(SupportQueueSavedView.id == view_id))).scalar_one_or_none()
            if view is None:
                return _support_json_error("Saved view not found", status=404, error_code="NOT_FOUND")
            if not _can_manage_saved_view(auth_context, view):
                return _support_json_error("Saved view is owned by another operator", status=403, error_code="FORBIDDEN")
            await session.delete(view)
            await session.commit()
            return json_model_response(
                SuccessResponse[SupportQueueSavedViewDeletePayload](
                    data=SupportQueueSavedViewDeletePayload(deleted=True, id=view_id)
                )
            )
    except Exception as exc:
        logger.warning(f"[web_support_queue_saved_view_delete] failed view_id={view_id}: {exc}")
        return _support_json_error("Saved view was not deleted", status=500, error_code="SERVER_ERROR")


@require_auth("admin", "support")
async def handle_web_support_queue_mass_action(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        payload = SupportQueueMassActionRequest.model_validate(data)
    except Exception as exc:
        return _support_json_error(str(exc), status=400, error_code="VALIDATION_ERROR")

    action = payload.action.strip().lower()
    ticket_ids = _normalize_mass_action_ids(payload.ticket_ids)
    supported_actions = {
        "assign_self",
        "assign",
        "change_queue",
        "change_priority",
        "internal_note",
        "run_diagnostics",
        "link_mass_problem",
    }
    if action not in supported_actions:
        return _support_json_error("Неподдерживаемое массовое действие", status=400, error_code="VALIDATION_ERROR")
    if not ticket_ids:
        return _support_json_error("Нужно выбрать хотя бы один тикет", status=400, error_code="VALIDATION_ERROR")
    if len(ticket_ids) > 100:
        return _support_json_error("За один раз можно обработать не больше 100 тикетов", status=400, error_code="VALIDATION_ERROR")
    raw_reason = (payload.reason or "").strip()
    reason = raw_reason or "support_queue_mass_action"
    if action == "change_priority" and len(raw_reason) < 3:
        return _support_json_error("Для смены приоритета нужна причина", status=400, error_code="VALIDATION_ERROR")
    if action == "change_queue" and payload.queue_id is None:
        return _support_json_error("Для смены очереди нужен queue_id", status=400, error_code="VALIDATION_ERROR")
    if action == "internal_note" and not (payload.internal_note or "").strip():
        return _support_json_error("Для внутренней заметки нужен текст", status=400, error_code="VALIDATION_ERROR")
    if action == "run_diagnostics" and not (payload.tool_name or "").strip():
        return _support_json_error("Для массовой диагностики нужно имя инструмента", status=400, error_code="VALIDATION_ERROR")

    permission_by_action = {
        "assign_self": "ticket.assign",
        "assign": "ticket.assign",
        "change_queue": "ticket.queue.change",
        "change_priority": "ticket.status.change",
        "internal_note": "ticket.comment.internal",
        "run_diagnostics": "ticket.tool.run",
        "link_mass_problem": "ticket.comment.internal",
    }
    auth_context = request["auth_context"]
    results: list[SupportQueueMassActionItem] = []
    pushed_events: list[tuple[str, Any, str, dict[str, Any]]] = []
    requested_set = set(ticket_ids)

    try:
        async with get_session() as session:
            denied = await _require_permission(session, auth_context, permission_by_action[action])
            if denied:
                return denied
            state = await _load_support_queue_state(
                session,
                auth_context,
                limit=2000,
                include_hidden=False,
                include_archived=False,
            )
            accessible_ids = {
                str(ticket_data.get("ticket_id") or "")
                for ticket_data, _item in state.accessible_entries
                if str(ticket_data.get("ticket_id") or "") in requested_set
            }
            repo = TicketEventsRepo(session)
            tool_service = ToolExecutionService(request.app["state"])

            for ticket_id in ticket_ids:
                if ticket_id not in accessible_ids:
                    results.append(_mass_action_item(ticket_id=ticket_id, action=action, status="skipped", message="Тикет недоступен текущей роли или очередям"))
                    continue
                ticket = await repo.get_ticket(ticket_id)
                if ticket is None:
                    results.append(_mass_action_item(ticket_id=ticket_id, action=action, status="skipped", message="Тикет не найден"))
                    continue
                ticket_code = getattr(ticket, "ticket_code", None)
                try:
                    if action in {"assign_self", "assign"}:
                        assignment_service = TicketAssignmentService(repo)
                        requested_assignee_id = auth_context.actor_id if action == "assign_self" else payload.assignee_id
                        auto_assign = action == "assign" and not requested_assignee_id
                        selection = await assignment_service.resolve_assignee(ticket, requested_assignee_id=requested_assignee_id, auto_assign=auto_assign)
                        assignee_id = selection["assignee_id"]
                        event_result = await assignment_service.assign_ticket(
                            ticket.ticket_id,
                            ticket.device_id,
                            assignee_id,
                            actor_id=auth_context.actor_id,
                            actor_role=auth_context.actor_role,
                            reason=reason,
                            comment=payload.comment,
                            old_assignee=getattr(ticket, "assignee_id", None),
                            auto_assigned=auto_assign,
                            active_count=selection["active_count"],
                            limit=MAX_ACTIVE_TICKETS_PER_OPERATOR,
                            db_session=session,
                            close_ola=True,
                        )
                        await session.commit()
                        event_payload = {
                            "field_name": "assignee_id",
                            "old_value": getattr(ticket, "assignee_id", None),
                            "new_value": assignee_id,
                            "assignee_id": assignee_id,
                            "actor_id": auth_context.actor_id,
                            "actor_role": auth_context.actor_role,
                            "bulk_action": True,
                            "reason": reason,
                            "auto_assigned": auto_assign,
                        }
                        pushed_events.append((ticket.ticket_id, event_result, "assignee_changed", event_payload))
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Исполнитель назначен", result=await _support_mutation_result(session, refreshed, action="assign", auto_assigned=auto_assign)))
                        continue

                    if action == "change_queue":
                        old_queue_id = ticket.queue_id
                        queue_id = int(payload.queue_id)
                        await repo.update_ticket(ticket.ticket_id, queue_id=queue_id, custom_fields=set_routing_lock(getattr(ticket, "custom_fields", None), reason), manual_rank=None, manual_rank_updated_at=None, manual_rank_updated_by=None)
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        try:
                            await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
                            await start_ola_for_ticket(session, refreshed, trigger="queue_changed")
                        except Exception as exc:
                            logger.warning(f"[web_support_queue_mass_action] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
                        event_payload = {"queue_id": queue_id, "previous_queue_id": old_queue_id, "actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role, "reason": reason, "bulk_action": True}
                        event_result = await repo.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None, event_type="queue_changed", payload=event_payload)
                        await session.commit()
                        pushed_events.append((ticket.ticket_id, event_result, "queue_changed", event_payload))
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Очередь изменена", result=await _support_mutation_result(session, refreshed, action="queue")))
                        continue

                    if action == "change_priority":
                        normalized = normalize_ticket_priority_inputs(*_priority_request_to_inputs({"priority": payload.priority, "reason": reason}))
                        custom_fields = merge_requester_custom_fields(getattr(ticket, "custom_fields", None), priority_class=normalized["priority_class"])
                        await repo.update_ticket(ticket.ticket_id, urgency=normalized["urgency"], importance=normalized["importance"], urgency_reason=normalized["urgency_reason"], importance_reason=normalized["importance_reason"], priority=normalized["legacy_priority"], custom_fields=custom_fields)
                        await TicketSlaService(session, repo).recalc_due_for_priority(ticket.ticket_id, normalized["legacy_priority"])
                        event_payload = {"priority_class": normalized["priority_class"], "priority": normalized["legacy_priority"], "reason": reason, "actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role, "bulk_action": True}
                        event_result = await repo.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None, event_type="priority_changed", payload=event_payload)
                        await session.commit()
                        pushed_events.append((ticket.ticket_id, event_result, "priority_changed", event_payload))
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Приоритет изменён", result=await _support_mutation_result(session, refreshed, action="priority")))
                        continue

                    if action == "internal_note":
                        event_result, event_payload = await _support_mass_action_internal_note(repo=repo, ticket=ticket, auth_context=auth_context, text=(payload.internal_note or "").strip())
                        await session.commit()
                        pushed_events.append((ticket.ticket_id, event_result, "chat_message", event_payload))
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Внутренняя заметка добавлена", result=await _support_mutation_result(session, refreshed, action="internal_note")))
                        continue

                    if action == "link_mass_problem":
                        event_payload = {
                            "mass_problem_key": (payload.mass_problem_key or "").strip() or f"mass-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                            "related_ticket_ids": ticket_ids,
                            "actor_id": auth_context.actor_id,
                            "actor_role": auth_context.actor_role,
                            "reason": reason,
                            "bulk_action": True,
                        }
                        event_result = await repo.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None, event_type="mass_problem_linked", payload=event_payload)
                        await session.commit()
                        pushed_events.append((ticket.ticket_id, event_result, "mass_problem_linked", event_payload))
                        refreshed = await repo.get_ticket(ticket.ticket_id)
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Связь с массовой проблемой добавлена", result=await _support_mutation_result(session, refreshed, action="link_mass_problem")))
                        continue

                    if action == "run_diagnostics":
                        device_id = str(getattr(ticket, "device_id", "") or "").strip()
                        if not device_id:
                            results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="skipped", message="Тикет не привязан к устройству"))
                            continue
                        tool_name = (payload.tool_name or "").strip()
                        risk_level = await _resolve_tool_risk_level(tool_service=tool_service, device_id=device_id, tool_name=tool_name)
                        if not await can(session, auth_context, _tool_risk_permission(risk_level)):
                            results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="skipped", message=f"Недостаточно прав для инструмента: {_tool_risk_permission(risk_level)}"))
                            continue
                        operation_id = str(uuid.uuid4())
                        params = await _build_tool_params_for_dispatch(
                            tool_service=tool_service,
                            device_id=device_id,
                            tool_name=tool_name,
                            params=payload.params,
                            preset_id=payload.preset_id,
                            operation_id=operation_id,
                        )
                        dispatch = await tool_service.run_tool(
                            device_id=device_id,
                            ticket_id=ticket.ticket_id,
                            tool_name=tool_name,
                            params=params,
                            call_id=str(uuid.uuid4()),
                            auth_context=auth_context,
                            wait_for_result=False,
                        )
                        dispatch_status = str(dispatch.get("status") or "accepted")
                        if dispatch_status != "accepted":
                            results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="error", message=str(dispatch.get("error") or "Инструмент не поставлен в очередь")))
                            continue
                        resolved_operation_id = str(dispatch.get("operation_id") or operation_id)
                        tool_result = SupportToolActionResult(
                            ticket_id=ticket.ticket_id,
                            device_id=device_id,
                            tool_name=tool_name,
                            dispatch_status=dispatch_status,
                            operation_id=resolved_operation_id,
                            poll_url=str(dispatch.get("poll_url") or f"/api/operations/{resolved_operation_id}"),
                            trace_id=dispatch.get("trace_id"),
                            message="Инструмент поставлен в очередь выполнения",
                        )
                        results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="success", message="Диагностика запущена", result=tool_result))
                        continue
                except Exception as exc:
                    await session.rollback()
                    logger.warning(f"[web_support_queue_mass_action] item failed: ticket_id={ticket_id} action={action} error={exc}")
                    results.append(_mass_action_item(ticket_id=ticket_id, ticket_code=ticket_code, action=action, status="error", message=str(exc) or "Действие не выполнено"))

        for ticket_id, event_result, event_type, event_payload in pushed_events:
            await _push_ticket_event(request, ticket_id, event_result, event_type, event_payload)
    except Exception as exc:
        logger.warning(f"[web_support_queue_mass_action] failed: action={action} error={exc}")
        return _support_json_error("Не удалось выполнить массовое действие", status=503, error_code="MASS_ACTION_FAILED")

    success_count = sum(1 for item in results if item.status == "success")
    skipped_count = sum(1 for item in results if item.status == "skipped")
    error_count = sum(1 for item in results if item.status == "error")
    result_payload = SupportQueueMassActionResult(
        action=action,
        requested_count=len(ticket_ids),
        success_count=success_count,
        skipped_count=skipped_count,
        error_count=error_count,
        results=results,
    )
    return json_model_response(SuccessResponse[SupportQueueMassActionResult](data=result_payload))


@require_auth("admin", "support")
async def handle_web_support_cleanup_noise(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    reason = str(data.get("reason") or "manual_live_stage_test_cleanup").strip() or "manual_live_stage_test_cleanup"
    auth_context = request["auth_context"]
    hidden_ticket_ids: list[str] = []
    skipped_ticket_ids: list[str] = []
    pushed_events: list[tuple[str, object, dict[str, Any]]] = []
    try:
        async with get_session() as session:
            state = await _load_support_queue_state(
                session,
                auth_context,
                limit=1000,
                include_hidden=False,
                include_archived=False,
            )
            repo = TicketEventsRepo(session)
            now = datetime.now(timezone.utc)
            for ticket_data, _item in state.accessible_entries:
                if not _is_support_workspace_cleanup_noise(ticket_data):
                    continue
                ticket_id = str(ticket_data.get("ticket_id") or "")
                ticket = await repo.get_ticket(ticket_id)
                if ticket is None or _is_support_workspace_hidden(ticket):
                    skipped_ticket_ids.append(ticket_id)
                    continue
                previous_visibility = _support_workspace_visibility(ticket)
                custom_fields = _support_workspace_custom_fields(
                    ticket,
                    hidden=True,
                    actor_id=auth_context.actor_id,
                    reason=reason,
                    now=now,
                )
                await repo.update_ticket(ticket.ticket_id, custom_fields=custom_fields)
                refreshed_ticket = await repo.get_ticket(ticket.ticket_id)
                payload = {
                    "actor_id": auth_context.actor_id,
                    "actor_role": auth_context.actor_role,
                    "reason": reason,
                    "cleanup": "live_stage_test",
                    "previous": previous_visibility,
                    "current": _support_workspace_visibility(refreshed_ticket),
                }
                event_result = await repo.add_event(
                    ticket_id=refreshed_ticket.ticket_id,
                    device_id=refreshed_ticket.device_id,
                    agent_seq=None,
                    event_type="ticket_hidden_from_workspace",
                    payload=payload,
                )
                hidden_ticket_ids.append(refreshed_ticket.ticket_id)
                pushed_events.append((refreshed_ticket.ticket_id, event_result, payload))
            await session.commit()
        for ticket_id, event_result, payload in pushed_events:
            await _push_ticket_event(request, ticket_id, event_result, "ticket_hidden_from_workspace", payload)
        result = SupportWorkspaceCleanupResult(
            matched_count=len(hidden_ticket_ids) + len(skipped_ticket_ids),
            hidden_count=len(hidden_ticket_ids),
            hidden_ticket_ids=hidden_ticket_ids,
            skipped_ticket_ids=skipped_ticket_ids,
        )
        return json_model_response(SuccessResponse[SupportWorkspaceCleanupResult](data=result))
    except Exception as exc:
        logger.warning(f"[web_support_cleanup_noise] failed: error={exc}")
        return _support_json_error("Не удалось скрыть live/test тикеты", status=503, error_code="SUPPORT_CLEANUP_FAILED")


@require_auth("admin", "support")
async def handle_web_support_queue(request: web.Request):
    auth_context = request["auth_context"]
    scope = _normalize_scope(request.query.get("scope"))
    status_filter = _normalize_status_filter(request.query.get("status"))
    requested_smart_view = request.query.get("smart_view")
    smart_view = normalize_smart_view_id(requested_smart_view)
    query = str(request.query.get("query", "") or "").strip()
    limit = min(max(int(request.query.get("limit", "200")), 1), 300)
    include_hidden = _parse_bool_query(request.query.get("include_hidden"))
    include_archived = _parse_bool_query(request.query.get("include_archived"))

    try:
        async with get_session() as session:
            state = await _load_support_queue_state(
                session,
                auth_context,
                limit=limit,
                include_hidden=include_hidden,
                include_archived=include_archived,
            )
            smart_view = normalize_smart_view_id(
                requested_smart_view,
                custom_view_ids=set(state.custom_smart_view_map),
            )

        smart_view_counts = _build_smart_view_counts(
            state.accessible_entries,
            state.smart_options,
            actor_id=auth_context.actor_id,
            custom_smart_view_map=state.custom_smart_view_map,
        )
        matching_entries = [
            (ticket_data, item)
            for ticket_data, item in state.accessible_entries
            if matches_smart_view(
                ticket_data,
                smart_view,
                actor_id=auth_context.actor_id,
                custom_views=state.custom_smart_view_map,
            )
        ]
        matching_entries = _apply_custom_smart_view_sort(
            matching_entries,
            smart_view=smart_view,
            custom_smart_view_map=state.custom_smart_view_map,
        )
        queue_counts = _build_queue_counts(state.active_queues, matching_entries)
        accessible_items = [item for _ticket_data, item in matching_entries]
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
            smart_view=smart_view,
            summary=SupportQueueSummary(
                visible_count=len(typed_items),
                selected_ticket_id=typed_items[0].ticket_id if typed_items else None,
                scope_counts=scope_counts,
                status_counts=status_counts,
                smart_view_counts=smart_view_counts,
                queue_counts=queue_counts,
            ),
            filters=SupportQueueFilters(
                scope_options=SCOPE_OPTIONS,
                status_options=_build_status_options(status_values),
                smart_view_options=[SupportFilterOption(**option) for option in state.smart_options],
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
            smart_view=smart_view,
        )
    return json_model_response(SuccessResponse[SupportQueuePayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_workspace_summary(request: web.Request):
    auth_context = request["auth_context"]
    limit = min(max(int(request.query.get("limit", "1000")), 1), 2000)
    try:
        async with get_session() as session:
            state = await _load_support_queue_state(session, auth_context, limit=limit)

        smart_view_counts = _build_smart_view_counts(
            state.accessible_entries,
            state.smart_options,
            actor_id=auth_context.actor_id,
            custom_smart_view_map=state.custom_smart_view_map,
        )
        queue_counts = _build_queue_counts(state.active_queues, state.accessible_entries)
        payload = SupportWorkspaceSummaryPayload(
            views=_workspace_summary_view_counts(smart_view_counts),
            queues=_workspace_summary_queues(queue_counts),
            smart_view_counts=smart_view_counts,
            smart_view_options=[SupportFilterOption(**option) for option in state.smart_options],
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_workspace_summary] DB unavailable, returning empty summary: "
            f"actor_id={auth_context.actor_id}, error={exc}"
        )
        empty_smart_options = smart_view_options()
        empty_smart_counts = [
            SupportCountItem(value=str(option.get("value") or ""), label=str(option.get("label") or ""), count=0)
            for option in empty_smart_options
            if str(option.get("value") or "").strip()
        ]
        payload = SupportWorkspaceSummaryPayload(
            views=_workspace_summary_view_counts(empty_smart_counts),
            queues=[],
            smart_view_counts=empty_smart_counts,
            smart_view_options=[SupportFilterOption(**option) for option in empty_smart_options],
        )
    return json_model_response(SuccessResponse[SupportWorkspaceSummaryPayload](data=payload))


def _support_inventory_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    text = str(value).strip()
    return text or None


def _support_inventory_age_seconds(value: datetime | None, now: datetime) -> int | None:
    if value is None:
        return None
    collected_at = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return max(0, int((now - collected_at.astimezone(timezone.utc)).total_seconds()))


def _support_inventory_freshness(latest: Any, age_seconds: int | None, stale_seconds: int = 7 * 24 * 60 * 60) -> str:
    if latest is None:
        return "missing"
    if age_seconds is None:
        return "unknown"
    return "stale" if age_seconds > stale_seconds else "fresh"


def _support_inventory_summary(latest: Any) -> dict[str, Any] | None:
    if latest is None:
        return None
    normalized = getattr(latest, "normalized", None)
    if isinstance(normalized, dict) and normalized:
        return normalized
    snapshot = getattr(latest, "snapshot", None)
    if not isinstance(snapshot, dict):
        return None
    identity = snapshot.get("identity") if isinstance(snapshot.get("identity"), dict) else {}
    platform = snapshot.get("platform") if isinstance(snapshot.get("platform"), dict) else {}
    network = snapshot.get("network") if isinstance(snapshot.get("network"), dict) else {}
    resources = snapshot.get("resources") if isinstance(snapshot.get("resources"), dict) else {}
    return {
        "hostname": identity.get("hostname"),
        "current_user": identity.get("current_user"),
        "os_name": platform.get("os_name"),
        "os_version": platform.get("os_version"),
        "primary_ip": network.get("primary_ip"),
        "cpu_percent": resources.get("cpu_percent"),
        "memory_percent": resources.get("memory_percent"),
    }


def _compose_support_inventory_context(
    *,
    device_id: str,
    detail: SupportTicketDetailPayload,
    latest: Any,
    binding: dict[str, Any],
    policy: Any,
    last_refresh_run: Any,
) -> SupportTicketInventoryContext | None:
    if not device_id:
        return None

    now = datetime.now(timezone.utc)
    age_seconds = _support_inventory_age_seconds(getattr(latest, "collected_at", None), now)
    freshness = _support_inventory_freshness(latest, age_seconds)
    failed_recent_operation = any(
        (operation.status or "").lower() in {"failed", "error"}
        or (operation.display_status or "").lower() in {"failed", "error"}
        for operation in detail.snapshot.latest_operations
    )
    agent_offline = not bool(detail.snapshot.device.online)
    failed_recent_refresh = str(getattr(last_refresh_run, "status", "") or "").lower() == "failed"

    return SupportTicketInventoryContext(
        device_id=device_id,
        hostname=detail.snapshot.device.hostname,
        display_name=detail.snapshot.device.hostname or device_id,
        agent=SupportTicketInventoryAgentContext(
            connection_state="offline" if agent_offline else "online",
            last_seen_at=detail.snapshot.device.last_seen_at,
            version=detail.snapshot.device.agent_version,
            update_status=None,
            update_available=None,
        ),
        inventory=SupportTicketInventorySnapshotContext(
            latest_snapshot_id=str(getattr(latest, "id", "") or "") or None,
            collected_at=_support_inventory_iso(getattr(latest, "collected_at", None)),
            age_seconds=age_seconds,
            freshness=freshness,
            source=getattr(latest, "source_tool", None),
            summary=_support_inventory_summary(latest),
        ),
        binding=SupportTicketInventoryBindingContext(
            responsible_person=binding.get("responsible_user"),
            department=binding.get("department"),
            building=binding.get("building"),
            room=binding.get("room"),
            status=binding.get("status"),
            tags=list(binding.get("tags") or []),
        ),
        refresh=SupportTicketInventoryRefreshContext(
            policy_enabled=bool(getattr(policy, "enabled", False)) if policy is not None else None,
            last_run_id=str(getattr(last_refresh_run, "id", "") or "") or None,
            last_run_status=getattr(last_refresh_run, "status", None),
            last_run_at=_support_inventory_iso(getattr(last_refresh_run, "requested_at", None)),
            next_due_at=_support_inventory_iso(getattr(policy, "next_due_at", None)),
            can_request_refresh=False,
        ),
        signals=SupportTicketInventorySignals(
            stale_inventory=freshness == "stale",
            missing_inventory=freshness == "missing",
            agent_offline=agent_offline,
            failed_recent_refresh=failed_recent_refresh,
            failed_recent_operation=failed_recent_operation,
        ),
    )


async def _build_support_inventory_context(
    session: Any,
    ticket: Ticket,
    detail: SupportTicketDetailPayload,
) -> SupportTicketInventoryContext | None:
    device_id = str(getattr(ticket, "device_id", "") or detail.snapshot.device.device_id or "").strip()
    if not device_id:
        return None

    inventory_service = DeviceInventoryService(session)
    try:
        latest = await inventory_service.get_latest(device_id)
        binding_row = await inventory_service.get_binding(device_id)
        policy = await inventory_service.get_effective_refresh_policy(device_id)
        refresh_runs = await inventory_service.list_refresh_runs(device_id=device_id, limit=1)
    except Exception as exc:
        logger.warning(f"[support_inventory_context] inventory lookup failed: device_id={device_id}, error={exc}")
        latest = None
        binding_row = None
        policy = None
        refresh_runs = []
    last_refresh_run = refresh_runs[0] if refresh_runs else None
    return _compose_support_inventory_context(
        device_id=device_id,
        detail=detail,
        latest=latest,
        binding=binding_to_dict(binding_row) if binding_row is not None else {},
        policy=policy,
        last_refresh_run=last_refresh_run,
    )


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
async def handle_web_support_ticket_workspace(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            detail = await _build_support_detail_payload(request, session, ticket, repo, auth_context)
            tools = await _build_support_tools_payload(
                ticket,
                ToolExecutionService(request.app["state"]),
            )
            playbooks = await _build_support_playbooks_payload(session, ticket, request.app["state"])
            passport = _passport_payload_model(await TicketPassportService(session).get_payload(ticket.ticket_id))
            knowledge = await _build_support_knowledge_suggestions_payload(session, ticket)
            sla_ola = _build_support_sla_ola_payload(ticket)
            passport_readiness = _build_support_passport_readiness_payload(ticket.ticket_id, passport)
            closure_plan = _build_support_closure_plan_payload(ticket.ticket_id, detail)
            inventory_context = await _build_support_inventory_context(session, ticket, detail)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_workspace] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Рабочее пространство тикета временно недоступно",
                "error_code": "SUPPORT_WORKSPACE_UNAVAILABLE",
            },
            status=503,
        )

    payload = SupportTicketWorkspacePayload(
        detail=detail,
        tools=tools,
        playbooks=playbooks,
        passport=passport,
        knowledge=knowledge,
        sla_ola=sla_ola,
        passport_readiness=passport_readiness,
        closure_plan=closure_plan,
        inventory_context=inventory_context,
    )
    return json_model_response(SuccessResponse[SupportTicketWorkspacePayload](data=payload))


@require_auth("admin", "support")
async def handle_web_support_ticket_knowledge_suggestions(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            payload = await _build_support_knowledge_suggestions_payload(session, ticket)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_knowledge_suggestions] failed: "
            f"ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Knowledge suggestions временно недоступны",
                "error_code": "SUPPORT_KNOWLEDGE_UNAVAILABLE",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketKnowledgeSuggestionsPayload](data=payload))


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
            payload = await _build_support_playbooks_payload(session, ticket, request.app["state"])
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
async def handle_web_support_ticket_passport_evidence_candidates(request: web.Request):
    try:
        async with get_session() as session:
            ticket, error, _repo, _auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            candidates = await TicketEvidenceService(session).collect_candidates(ticket.ticket_id)
            payload = SupportTicketEvidenceCandidatesPayload(ticket_id=ticket.ticket_id, candidates=candidates)
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_evidence_candidates] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить кандидаты доказательств",
                "error_code": "PASSPORT_EVIDENCE_CANDIDATES_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketEvidenceCandidatesPayload](data=payload))


def _passport_evidence_event_payload(
    *,
    action: str,
    event_id: str,
    actor_id: str | None,
    item: Any,
    reason: str | None = None,
) -> dict[str, Any]:
    source_ref = getattr(item, "source_ref", None) or (
        f"{getattr(item, 'source_kind', None)}:{getattr(item, 'source_id', None)}"
        if getattr(item, "source_kind", None) and getattr(item, "source_id", None)
        else None
    )
    provenance = {
        "domain": "passport_evidence",
        "action": action,
        "source_ref": source_ref,
        "required_fact": getattr(item, "required_fact", None),
    }
    verification_status = getattr(item, "verification_status", None)
    if action == "update" and verification_status:
        provenance["verification_status"] = verification_status
    payload = {
        "event_id": event_id,
        "actor_id": actor_id,
        "evidence_id": getattr(item, "id", None),
        "passport_id": getattr(item, "passport_id", None),
        "evidence_type": getattr(item, "evidence_type", None),
        "source_ref": source_ref,
        "source_kind": getattr(item, "source_kind", None),
        "source_id": getattr(item, "source_id", None),
        "artifact_id": getattr(item, "artifact_id", None),
        "required_fact": getattr(item, "required_fact", None),
        "section_key": getattr(item, "section_key", None),
        "verification_status": verification_status,
        "visibility": getattr(item, "visibility", None),
        "export_visibility": getattr(item, "export_visibility", None),
        "title": getattr(item, "title", None),
        "observer_provenance": provenance,
    }
    if reason:
        payload["reason"] = reason
    return payload


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_evidence_link(request: web.Request):
    try:
        raw = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Некорректный JSON"}, status=400)
    if not isinstance(raw, dict):
        return web.json_response({"status": "error", "error": "Тело запроса должно быть объектом"}, status=400)
    data = SupportTicketPassportEvidenceLinkRequest.model_validate(raw)
    visibility = data.visibility if data.visibility in {"public", "internal"} else "internal"

    try:
        async with get_session() as session:
            ticket, error, ticket_repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            item = await TicketEvidenceService(session).link_source(
                ticket.ticket_id,
                source_kind=data.source_kind,
                source_id=data.source_id,
                required_fact=data.required_fact,
                actor_id=auth_context.actor_id,
                visibility=visibility,
            )
            if not ticket.evidence_ref:
                await ticket_repo.update_ticket(ticket.ticket_id, evidence_ref=item.source_ref or f"evidence:{item.id}")
            await ticket_repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="passport_evidence_linked",
                payload=_passport_evidence_event_payload(
                    action="link",
                    event_id=f"passport-evidence-linked-{item.id}",
                    actor_id=auth_context.actor_id,
                    item=item,
                ),
                event_id=f"passport-evidence-linked-{item.id}",
            )
            await session.commit()
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "Источник доказательства не найден для этого обращения",
                "error_code": str(exc) or "EVIDENCE_SOURCE_NOT_FOUND",
            },
            status=404,
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_evidence_link] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось привязать доказательство",
                "error_code": "PASSPORT_EVIDENCE_LINK_FAILED",
            },
            status=503,
        )

    return json_model_response(SuccessResponse[SupportTicketPassportDetailPayload](data=_passport_payload_model(payload)))


@require_auth("admin", "support", "auditor")
async def handle_web_support_ticket_passport_evidence_update(request: web.Request):
    try:
        evidence_id = int(request.match_info.get("evidence_id") or "0")
    except ValueError:
        return web.json_response({"status": "error", "error": "Некорректный evidence_id"}, status=400)
    try:
        raw = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Некорректный JSON"}, status=400)
    if not isinstance(raw, dict):
        return web.json_response({"status": "error", "error": "Тело запроса должно быть объектом"}, status=400)
    data = SupportTicketPassportEvidenceUpdateRequest.model_validate(raw)

    try:
        async with get_session() as session:
            ticket, error, ticket_repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.passport.manage")
            if denied:
                return denied
            item = await TicketEvidenceService(session).update_evidence(
                ticket.ticket_id,
                evidence_id,
                verification_status=data.verification_status,
                actor_id=auth_context.actor_id,
                reason=data.reason,
                visibility=data.visibility,
                export_visibility=data.export_visibility,
                public_summary=data.public_summary,
                internal_summary=data.internal_summary,
                metadata_json=data.metadata_json,
            )
            event_type_by_status = {
                "accepted": "passport_evidence_verified",
                "rejected": "passport_evidence_rejected",
                "archived": "passport_evidence_archived",
                "superseded": "passport_evidence_superseded",
                "unverified": "passport_evidence_unverified",
            }
            event_type = event_type_by_status.get(item.verification_status, "passport_evidence_updated")
            await ticket_repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type=event_type,
                payload=_passport_evidence_event_payload(
                    action="update",
                    event_id=f"{event_type}-{item.id}",
                    actor_id=auth_context.actor_id,
                    item=item,
                    reason=data.reason,
                ),
                event_id=f"{event_type}-{item.id}-{uuid.uuid4().hex[:8]}",
            )
            await session.commit()
            payload = await TicketPassportService(session).get_payload(ticket.ticket_id)
    except ValueError as exc:
        return web.json_response(
            {
                "status": "error",
                "error": "Доказательство не найдено или статус некорректен",
                "error_code": str(exc) or "EVIDENCE_UPDATE_FAILED",
            },
            status=404,
        )
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_passport_evidence_update] failed: ticket_id={request.match_info.get('ticket_id')}, evidence_id={request.match_info.get('evidence_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось обновить доказательство",
                "error_code": "PASSPORT_EVIDENCE_UPDATE_FAILED",
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
                source_kind=data.source_kind,
                source_id=data.source_id,
                required_fact=data.required_fact,
                section_key=data.section_key or data.required_fact,
                artifact_id=data.artifact_id,
                title=data.title,
                summary=data.summary,
                visibility=visibility,
                verification_status=data.verification_status,
                captured_at=_parse_optional_datetime(data.captured_at),
                public_summary=data.public_summary,
                internal_summary=data.internal_summary,
                metadata_json=data.metadata_json,
                export_visibility=data.export_visibility,
                created_by=auth_context.actor_id,
            )
            if not ticket.evidence_ref:
                await ticket_repo.update_ticket(ticket.ticket_id, evidence_ref=data.source_ref or f"evidence:{item.id}")
            await ticket_repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type="passport_evidence_added",
                payload=_passport_evidence_event_payload(
                    action="add",
                    event_id=f"passport-evidence-{item.id}",
                    actor_id=auth_context.actor_id,
                    item=item,
                ),
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
    request_payload: dict[str, Any] = {}
    if request.can_read_body:
        try:
            raw_payload = await _read_support_json(request)
            request_payload = raw_payload if isinstance(raw_payload, dict) else {}
        except Exception:
            request_payload = {}
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
            draft_result = await KnowledgePassportDraftService(session).create_draft_from_ticket(
                ticket.ticket_id,
                item_type=str(request_payload.get("item_type") or "article"),
                actor_id=auth_context.actor_id,
            )
            await session.commit()
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
    item = draft_result["item"]
    version = draft_result["version"]
    draft.title = item["title"]
    draft.item_id = item["item_id"]
    draft.version_id = version["version_id"]
    draft.status = item["status"]
    draft.item_type = item["item_type"]
    draft.edit_url = f"/app/admin/knowledge?item={item['item_id']}"
    draft.warnings = draft_result.get("warnings") or []
    draft.bindings = draft_result.get("bindings") or []
    return json_model_response(SuccessResponse[SupportTicketKnowledgeDraftPayload](data=draft))


@require_auth("admin", "support")
async def handle_web_support_ticket_worklog(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data

    try:
        spent_minutes = int(data.get("spent_minutes"))
    except Exception:
        return _support_json_error(
            "spent_minutes должен быть целым числом",
            status=400,
            error_code="VALIDATION_ERROR",
            details={"spent_minutes": "spent_minutes must be integer"},
        )
    note = str(data.get("note") or "").strip() or None

    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=True)
            if error:
                return error
            worklog = await repo.add_worklog(ticket.ticket_id, auth_context.actor_id, spent_minutes, note)
            if worklog is None:
                return _support_json_error(
                    "spent_minutes должен быть больше 0",
                    status=400,
                    error_code="VALIDATION_ERROR",
                    details={"spent_minutes": "spent_minutes must be > 0"},
                )
            payload = {
                "worklog_id": worklog.id,
                "ticket_id": ticket.ticket_id,
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
            )
            await session.commit()

        await _push_ticket_event(request, ticket.ticket_id, result, "worklog_added", payload)
        return web.json_response({"status": "success", "worklog": payload})
    except Exception as exc:
        logger.warning(
            f"[web_support_ticket_worklog] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}"
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось добавить worklog",
                "error_code": "WORKLOG_ACTION_FAILED",
            },
            status=503,
        )


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
                event_id=message_id,
            )
            if is_public_support_reply_payload(payload):
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
            **_requester_timeline_projection_fields({"event_type": "chat_message", "payload": payload}, ticket=ticket, payload=payload),
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
                    public_comment=data.get("public_comment"),
                    internal_comment=data.get("internal_comment"),
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

            if (
                to_status == "in_progress"
                and is_staff
                and auth_context.actor_id
                and not getattr(ticket, "assignee_id", None)
            ):
                try:
                    assignment_service = TicketAssignmentService(repo)
                    await assignment_service.assign_ticket(
                        ticket.ticket_id,
                        ticket.device_id,
                        auth_context.actor_id,
                        actor_id=auth_context.actor_id,
                        actor_role=auth_context.actor_role,
                        reason="take_in_work",
                        comment="",
                        old_assignee=None,
                        auto_assigned=False,
                        db_session=session,
                        close_ola=True,
                    )
                    ticket = await repo.get_ticket(ticket.ticket_id) or ticket
                except TicketAssignmentError as exc:
                    logger.info(
                        f"[web_support_status] take_in_work assignment skipped: "
                        f"ticket_id={ticket.ticket_id} actor_id={auth_context.actor_id} error={exc}"
                    )

            closure_policy_payload = (result.get("event_payload") or {}).get("closure_policy")
            requester_confirmation_policy = (
                closure_policy_payload.get("requester_confirmation")
                if isinstance(closure_policy_payload, dict)
                else None
            )
            requires_requester_confirmation = True
            if isinstance(requester_confirmation_policy, dict) and "required" in requester_confirmation_policy:
                requires_requester_confirmation = bool(requester_confirmation_policy.get("required"))

            if to_status == "resolved" and is_staff and requires_requester_confirmation:
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
async def handle_web_support_assign_ticket(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.assign")
            if denied:
                return denied
            assignment_service = TicketAssignmentService(repo)
            try:
                selection = await assignment_service.resolve_assignee(
                    ticket,
                    requested_assignee_id=data.get("assignee_id"),
                    auto_assign=bool(data.get("auto_assign")),
                )
            except TicketAssignmentError as exc:
                return _support_json_error(str(exc), status=400, error_code="ASSIGNMENT_ERROR")
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
            return json_model_response(SuccessResponse[SupportTicketMutationActionResult](data=await _support_mutation_result(session, ticket, action="assign", auto_assigned=bool(selection["auto_assigned"]))))
    except Exception as exc:
        logger.warning(f"[web_support_assign_ticket] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}")
        return _support_json_error("Не удалось назначить исполнителя", status=503, error_code="ASSIGN_ACTION_FAILED")


@require_auth("admin", "support", "auditor")
async def handle_web_support_change_queue(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        queue_id = int(data.get("queue_id"))
    except Exception:
        return _support_json_error("queue_id must be integer", status=400, error_code="VALIDATION_ERROR")
    reason = str(data.get("reason") or "manual").strip() or "manual"
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.queue.change")
            if denied:
                return denied
            old_queue_id = ticket.queue_id
            await repo.update_ticket(ticket.ticket_id, queue_id=queue_id, custom_fields=set_routing_lock(getattr(ticket, "custom_fields", None), reason), manual_rank=None, manual_rank_updated_at=None, manual_rank_updated_by=None)
            ticket = await repo.get_ticket(ticket.ticket_id)
            try:
                await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
                await start_ola_for_ticket(session, ticket, trigger="queue_changed")
            except Exception as exc:
                logger.warning(f"[web_support_queue_change] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
            captured = []
            if queue_id != old_queue_id:
                ticket, captured = await _reconcile_queue_scope_state(session, repo, ticket, actor_id=auth_context.actor_id, actor_role=auth_context.actor_role, reason_prefix="manual_queue_change")
            payload = {"queue_id": queue_id, "previous_queue_id": old_queue_id, "actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role, "reason": reason}
            result = await repo.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None, event_type="queue_changed", payload=payload)
            await session.commit()
            await _push_ticket_event(request, ticket.ticket_id, result, "queue_changed", payload)
            for event_type, event_payload, event_result in captured:
                await _push_ticket_event(request, ticket.ticket_id, event_result, event_type, event_payload)
            ticket = await repo.get_ticket(ticket.ticket_id)
            return json_model_response(SuccessResponse[SupportTicketMutationActionResult](data=await _support_mutation_result(session, ticket, action="queue")))
    except Exception as exc:
        logger.warning(f"[web_support_change_queue] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}")
        return _support_json_error("Не удалось сменить очередь", status=503, error_code="QUEUE_ACTION_FAILED")


@require_auth("admin", "support", "auditor")
async def handle_web_support_change_priority(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        normalized = normalize_ticket_priority_inputs(*_priority_request_to_inputs(data))
    except ValueError as exc:
        return _support_json_error(str(exc), status=400, error_code="VALIDATION_ERROR")
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.status.change")
            if denied:
                return denied
            custom_fields = merge_requester_custom_fields(getattr(ticket, "custom_fields", None), priority_class=normalized["priority_class"])
            await repo.update_ticket(ticket.ticket_id, urgency=normalized["urgency"], importance=normalized["importance"], urgency_reason=normalized["urgency_reason"], importance_reason=normalized["importance_reason"], priority=normalized["legacy_priority"], custom_fields=custom_fields)
            await TicketSlaService(session, repo).recalc_due_for_priority(ticket.ticket_id, normalized["legacy_priority"])
            payload = {"priority_class": normalized["priority_class"], "priority": normalized["legacy_priority"], "urgency": normalized["urgency"], "importance": normalized["importance"], "urgency_reason": normalized["urgency_reason"], "importance_reason": normalized["importance_reason"], "reason": str(data.get("reason") or "").strip() or None, "actor_id": auth_context.actor_id, "actor_role": auth_context.actor_role}
            result = await repo.add_event(ticket_id=ticket.ticket_id, device_id=ticket.device_id, agent_seq=None, event_type="priority_changed", payload=payload)
            await session.commit()
            await _push_ticket_event(request, ticket.ticket_id, result, "priority_changed", payload)
            ticket = await repo.get_ticket(ticket.ticket_id)
            return json_model_response(SuccessResponse[SupportTicketMutationActionResult](data=await _support_mutation_result(session, ticket, action="priority")))
    except Exception as exc:
        logger.warning(f"[web_support_change_priority] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}")
        return _support_json_error("Не удалось изменить приоритет", status=503, error_code="PRIORITY_ACTION_FAILED")


@require_auth("admin", "support", "auditor")
async def handle_web_support_reroute_ticket(request: web.Request):
    data = await _read_support_json(request)
    if isinstance(data, web.Response):
        return data
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.queue.change")
            if denied:
                return denied
            routing = TicketRoutingService(session, repo, DevicesRepo(session))
            captured: list[tuple[str, dict[str, Any], Any]] = []
            previous_queue_id = getattr(ticket, "queue_id", None)

            async def capture(ticket_id: str, device_id: str, event_type: str, payload: dict[str, Any]) -> None:
                payload = {**payload, "manual_reason": str(data.get("reason") or "manual_recalculate")}
                result = await repo.add_event(ticket_id=ticket_id, device_id=device_id, agent_seq=None, event_type=event_type, payload=payload)
                captured.append((event_type, payload, result))

            await routing.apply_routing(ticket.ticket_id, ticket.device_id, force_clear_lock=True, add_events_fn=capture)
            ticket = await repo.get_ticket(ticket.ticket_id)
            try:
                await close_ola_processing(session, ticket.ticket_id, trigger="queue_changed")
                await start_ola_for_ticket(session, ticket, trigger="queue_changed")
            except Exception as exc:
                logger.warning(f"[web_support_reroute] OLA update failed ticket_id={ticket.ticket_id} err={exc}")
            if getattr(ticket, "queue_id", None) != previous_queue_id:
                ticket, queue_events = await _reconcile_queue_scope_state(session, repo, ticket, actor_id=auth_context.actor_id, actor_role=auth_context.actor_role, reason_prefix="reroute")
                captured.extend(queue_events)
            await session.commit()
            for event_type, payload, result in captured:
                await _push_ticket_event(request, ticket.ticket_id, result, event_type, payload)
            ticket = await repo.get_ticket(ticket.ticket_id)
            return json_model_response(SuccessResponse[SupportTicketMutationActionResult](data=await _support_mutation_result(session, ticket, action="reroute")))
    except Exception as exc:
        logger.warning(f"[web_support_reroute_ticket] failed: ticket_id={request.match_info.get('ticket_id')}, error={exc}")
        return _support_json_error("Не удалось пересчитать маршрут", status=503, error_code="REROUTE_ACTION_FAILED")


@require_auth("admin", "support", "auditor")
async def handle_web_support_approval_decision(request: web.Request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    if not isinstance(data, dict):
        return web.json_response(
            {"status": "error", "error": "Request body must be an object", "error_code": "VALIDATION_ERROR"},
            status=400,
        )

    raw_decision = str(data.get("decision") or data.get("status") or "").strip().lower()
    decision = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "deny": "rejected",
        "denied": "rejected",
        "decline": "rejected",
        "declined": "rejected",
    }.get(raw_decision)
    if decision not in {"approved", "rejected"}:
        return web.json_response(
            {
                "status": "error",
                "error": "decision must be approved or rejected",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    try:
        approval_id = int(str(request.match_info.get("approval_id") or "").strip())
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "approval_id must be an integer", "error_code": "VALIDATION_ERROR"},
            status=400,
        )

    reason = str(data.get("reason") or data.get("comment") or "").strip()
    try:
        async with get_session() as session:
            ticket, error, repo, auth_context = await _get_ticket_or_response(request, session, write=False)
            if error:
                return error
            denied = await _require_permission(session, auth_context, "ticket.status.change")
            if denied:
                return denied

            approval = await session.get(TicketApproval, approval_id)
            if approval is None or str(approval.ticket_id) != str(ticket.ticket_id):
                return web.json_response(
                    {"status": "error", "error": "approval not found", "error_code": "APPROVAL_NOT_FOUND"},
                    status=404,
                )

            approver_id = str(approval.approver_id or "").strip()
            if approver_id and approver_id != str(auth_context.actor_id or "").strip():
                return web.json_response(
                    {
                        "status": "error",
                        "error": "current actor is not the requested approver",
                        "error_code": "APPROVAL_ACTOR_MISMATCH",
                    },
                    status=403,
                )

            current_status = str(approval.status or "").strip().lower()
            if current_status not in {"requested", "pending", "waiting"}:
                return web.json_response(
                    {
                        "status": "error",
                        "error": f"approval is already decided: {current_status}",
                        "error_code": "APPROVAL_ALREADY_DECIDED",
                    },
                    status=409,
                )

            summary_before = await build_approval_summary(session, ticket, requester_safe=False)
            current_ids = {
                int(item["id"])
                for item in (summary_before or {}).get("items", [])
                if item.get("current")
            }
            if current_ids and approval_id not in current_ids:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "approval is not current for the active approval mode",
                        "error_code": "APPROVAL_NOT_CURRENT",
                    },
                    status=409,
                )
            if decision == "rejected" and (summary_before or {}).get("require_comment_on_reject") and not reason:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "approval reject comment required",
                        "error_code": "APPROVAL_COMMENT_REQUIRED",
                    },
                    status=400,
                )

            now = datetime.now(timezone.utc)
            previous_status = current_status
            approval.status = decision
            approval.reason = reason or approval.reason
            approval.decided_at = now
            next_requested_id = None
            if decision == "approved" and (summary_before or {}).get("approval_mode") == "sequential":
                next_approval = (
                    await session.execute(
                        select(TicketApproval)
                        .where(
                            TicketApproval.ticket_id == ticket.ticket_id,
                            TicketApproval.status == "pending",
                        )
                        .order_by(TicketApproval.id.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if next_approval is not None:
                    next_approval.status = "requested"
                    next_requested_id = int(next_approval.id)

            event_type = "approval_approved" if decision == "approved" else "approval_rejected"
            payload = {
                "ticket_id": ticket.ticket_id,
                "approval_id": approval_id,
                "approval_type": approval.approval_type,
                "approver_id": approval.approver_id,
                "decision": decision,
                "previous_status": previous_status,
                "reason": reason,
                "actor_id": auth_context.actor_id,
                "actor_role": auth_context.actor_role,
                "decided_at": now.isoformat(),
                "next_requested_approval_id": next_requested_id,
            }
            await repo.add_event(
                ticket_id=ticket.ticket_id,
                device_id=ticket.device_id,
                agent_seq=None,
                event_type=event_type,
                payload=payload,
            )
            await notify_ticket_event(
                repo,
                NotificationRepo(session),
                ticket.ticket_id,
                event_type,
                payload,
                visibility="internal",
                initiator_id=auth_context.actor_id,
            )
            await session.flush()
            summary_after = await build_approval_summary(session, ticket, requester_safe=False)
            await session.commit()

            return json_model_response(
                SuccessResponse[dict](
                    data={
                        "ticket_id": ticket.ticket_id,
                        "approval": {
                            "id": approval_id,
                            "approval_type": approval.approval_type,
                            "approver_id": approval.approver_id,
                            "status": decision,
                            "reason": approval.reason,
                            "decided_at": now.isoformat(),
                        },
                        "approval_summary": summary_after,
                        "event_type": event_type,
                        "next_requested_approval_id": next_requested_id,
                    }
                )
            )
    except Exception as exc:
        logger.error(f"[web_support_approval_decision] Failed: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Failed to record approval decision",
                "error_code": "APPROVAL_DECISION_FAILED",
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

            policy_decision = await _resolve_tool_policy_decision(
                tool_service=tool_service,
                device_id=device_id,
                tool_name=tool_name,
                actor_role=auth_context.actor_role,
                params=params,
            )
            if not policy_decision.allow:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Policy violation",
                        "error_code": policy_decision.reason,
                        "required_role": policy_decision.required_role,
                        "actor_role": auth_context.actor_role,
                    },
                    status=403,
                )

            if policy_decision.requires_consent:
                ui_publisher = request.app["state"].ui_publisher if hasattr(request.app["state"], "ui_publisher") else None
                op_service = OperationService(session, publisher=ui_publisher)
                operation = await op_service.enqueue_operation(
                    operation_id=operation_id,
                    device_id=device_id,
                    kind="tool_call",
                    tool_name=tool_name,
                    ticket_id=ticket.ticket_id,
                    job_id=None,
                    actor_role=auth_context.actor_role,
                    trace_id=str(uuid.uuid4()),
                    initial_status="waiting_consent",
                )
                await session.commit()
                result = {
                    "status": "waiting_consent",
                    "operation_id": operation.operation_id,
                    "poll_url": f"/api/operations/{operation.operation_id}",
                    "trace_id": operation.trace_id,
                }
            else:
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
            readiness = _build_playbook_launch_readiness(
                version.manifest_json,
                device_id=device_id,
                available_tool_names=await _playbook_available_tool_names(device_id, request.app["state"]),
            )
            if not readiness.can_run:
                return web.json_response(
                    {
                        "status": "error",
                        "error": readiness.label,
                        "error_code": "PLAYBOOK_PREFLIGHT_BLOCKED",
                        "missing_tools": readiness.missing_tools,
                        "missing_params": readiness.missing_params,
                    },
                    status=409,
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
