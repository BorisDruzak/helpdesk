from __future__ import annotations

from aiohttp import web
from loguru import logger
from pydantic import ValidationError

from agents.agent_builds_handlers import (
    AgentUpdateRequestError,
    _infer_release_channel,
    _is_release_build,
    _resolve_recommended_build,
    _resolve_target_for_device,
    _sanitize_update_reason,
    enqueue_device_agent_update,
)
from app.db import get_session
from app.repos.agent_rollout_repo import AgentRolloutRepo
from app.repos.devices_repo import DevicesRepo
from app.repos import ModulesRepo
from config import MODULES_STORAGE_DIR
from modules.handlers import _get_module_preferred_assignments, _get_module_rollout_settings
from observer.service import ObserverOverlayService, TraceOverlayFilters
from auth.context import AuthContext
from auth.middleware import require_auth
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.admin import (
    AdminBuildIdentity,
    AdminBootstrapPayload,
    AdminObserverDangerousFlowItem,
    AdminObserverDegradationItem,
    AdminObserverQuickLinks,
    AdminObserverQuickPayload,
    AdminObserverQuickSummary,
    AdminObserverQuickTrace,
    AdminObserverRuntimeSummary,
    AdminObserverSignatureItem,
    AdminObserverTraceDetailPayload,
    AdminObserverTraceDetailSummary,
    AdminObserverTraceErrorOccurrenceItem,
    AdminObserverTraceItem,
    AdminObserverTraceSpanItem,
    AdminObserverTraceSpanLinkItem,
    AdminObserverTracesFilters,
    AdminObserverTracesLinks,
    AdminObserverTracesPayload,
    AdminObserverTracesQuery,
    AdminObserverTracesSummary,
    AdminDeviceItem,
    AdminDeviceUpdateAction,
    AdminDeviceUpdateRecommendation,
    AdminDeviceUpdateRunPayload,
    AdminDeviceUpdateRunRequest,
    AdminDevicesFilters,
    AdminModulesPayload,
    AdminModulesRolloutSettings,
    AdminModulesSummary,
    AdminModuleFamilyItem,
    AdminModuleVersionItem,
    AdminDevicesPayload,
    AdminDevicesSummary,
    AdminDeviceUpdateSummary,
    AdminDeviceUpdatesPayload,
    AdminFilterOption,
    AdminObserverCapabilities,
    AdminRolloutAssignment,
)
from utils.module_manifest import get_module_manifest, get_module_validation
from utils.versioning import version_key
from utils.versioning import compare_versions


STATUS_OPTIONS = [
    AdminFilterOption(value="all", label="Все устройства"),
    AdminFilterOption(value="online", label="Только онлайн"),
    AdminFilterOption(value="offline", label="Только офлайн"),
]

_MODULE_VALIDATION_STATUS_LABELS = {
    "passed": "Проверен",
    "warning": "Есть предупреждения",
    "failed": "Ошибка валидации",
    "unknown": "Статус неизвестен",
}

_MODULE_ROLLOUT_MODE_LABELS = {
    "manual": "Только вручную",
    "installed_devices": "Обновлять установленные устройства",
}

_OS_TYPE_TO_TARGET = {
    "windows": "windows_amd64",
    "windows 11": "windows_amd64",
    "windows 10": "windows_amd64",
    "linux": "linux_alt_x86_64",
    "alt linux": "linux_alt_x86_64",
    "linux_alt": "linux_alt_x86_64",
}

_UPDATE_RECOMMENDATION_SOURCE_LABELS = {
    "assigned_rollout": "Серверный rollout",
    "latest_release_fallback": "Последний release build",
    "none": "Рекомендация отсутствует",
}

_UPDATE_COMPARISON_LABELS = {
    "newer_release_available": "Назначена более новая release-версия",
    "recommended_release_is_older": "Назначен controlled rollback",
    "same_version": "Устройство уже на рекомендованной версии",
    "unknown": "Сравнение пока недоступно",
}

_UPDATE_REASON_LABELS = {
    "assigned_rollout_newer": "Назначенный rollout новее текущей версии.",
    "assigned_rollout_older": "Сервер просит откатиться на rollout-версию.",
    "assigned_rollout_non_release_current": "Текущая сборка не release, сервер выравнивает её по rollout policy.",
    "assigned_rollout": "Серверный rollout уже назначен для этого target.",
    "newer_release_available": "Для устройства доступен более новый release build.",
    "non_release_current_version": "Текущая версия агента не считается release.",
    "current_version_unknown": "Сервер не получил текущую версию агента.",
}


_OBSERVER_ROOT_KIND_LABELS = {
    "ticket": "Тикет",
    "tool_call": "Инструмент",
    "agent_update": "Обновление агента",
    "module_install": "Установка модуля",
    "module_remove": "Удаление модуля",
    "consent": "Запрос согласия",
}

_OBSERVER_STATUS_LABELS = {
    "queued": "В очереди",
    "sent": "Отправлено",
    "accepted": "Принято агентом",
    "running": "В работе",
    "waiting_consent": "Ждёт согласия",
    "cancel_requested": "Отменяется",
    "succeeded": "Успешно",
    "success": "Успешно",
    "failed": "Ошибка",
    "timed_out": "Таймаут",
    "canceled": "Отменено",
}

_OBSERVER_RUNTIME_STATUS_LABELS = {
    "ok": "Норма",
    "degraded": "Есть отставание",
    "down": "Не запущен",
    "unknown": "Статус неизвестен",
}

_OBSERVER_QUICK_ENDPOINT = "/api/web/admin/observer/quick"
_OBSERVER_TRACES_ENDPOINT = "/api/web/admin/observer/traces"
_OBSERVER_TRACE_DETAIL_TEMPLATE = "/api/web/admin/observer/traces/{trace_id}"
_OBSERVER_RUNTIME_ENDPOINT = "/api/admin/tech/traces/runtime"
_OBSERVER_ACTIVE_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
_OBSERVER_ERROR_STATUSES = {"failed", "timed_out", "error"}
_OBSERVER_TRACE_STATUS_OPTIONS = [
    AdminFilterOption(value="all", label="Все статусы"),
    AdminFilterOption(value="running", label="В работе"),
    AdminFilterOption(value="failed", label="С ошибкой"),
    AdminFilterOption(value="succeeded", label="Успешно"),
    AdminFilterOption(value="timed_out", label="Таймаут"),
]
_OBSERVER_TRACE_ROOT_KIND_OPTIONS = [
    AdminFilterOption(value="all", label="Все потоки"),
    AdminFilterOption(value="ticket", label="Тикет"),
    AdminFilterOption(value="tool_call", label="Инструмент"),
    AdminFilterOption(value="agent_update", label="Обновление агента"),
    AdminFilterOption(value="module_install", label="Установка модуля"),
    AdminFilterOption(value="module_remove", label="Удаление модуля"),
    AdminFilterOption(value="consent", label="Запрос согласия"),
]


def _normalize_status_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"online", "offline"}:
        return normalized
    return "all"


def _empty_devices_payload(*, query: str, status_filter: str) -> AdminDevicesPayload:
    return AdminDevicesPayload(
        query=query,
        status_filter=status_filter,
        summary=AdminDevicesSummary(
            visible_count=0,
            online_count=0,
            rollout_targets=0,
        ),
        filters=AdminDevicesFilters(status_options=STATUS_OPTIONS),
        rollout=[],
        devices=[],
    )


def _module_validation_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "unknown"
    return _MODULE_VALIDATION_STATUS_LABELS.get(normalized, normalized.replace("_", " "))


def _module_rollout_mode_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "manual"
    return _MODULE_ROLLOUT_MODE_LABELS.get(normalized, normalized.replace("_", " "))


def _module_tool_ids(manifest_json: dict | None) -> list[str]:
    if not isinstance(manifest_json, dict):
        return []
    tool_ids: list[str] = []
    for raw_tool in manifest_json.get("tools") or []:
        if not isinstance(raw_tool, dict):
            continue
        tool_id = str(raw_tool.get("tool") or raw_tool.get("name") or "").strip()
        if tool_id:
            tool_ids.append(tool_id)
    return tool_ids


def _module_file_exists(module: object) -> bool:
    storage_path = str(getattr(module, "storage_path", "") or "").strip()
    if not storage_path:
        return False
    return (MODULES_STORAGE_DIR / storage_path).exists()


def _pick_primary_module_record(modules: list[object], preferred_version: str | None) -> object | None:
    if not modules:
        return None
    if preferred_version:
        for module in modules:
            if str(getattr(module, "version", "") or "").strip() == preferred_version:
                return module
    return max(
        modules,
        key=lambda module: (
            version_key(str(getattr(module, "version", "") or "")).key,
            getattr(module, "created_at", None).isoformat() if getattr(module, "created_at", None) else "",
        ),
    )


def _map_admin_module_version_item(module: object, *, preferred_version: str | None) -> AdminModuleVersionItem:
    manifest_json = get_module_manifest(module)
    validation_json = get_module_validation(module)
    validation_status = str(validation_json.get("validation_status") or "unknown").strip().lower() or "unknown"
    preflight_status = str(validation_json.get("preflight_status") or "unknown").strip().lower() or "unknown"
    return AdminModuleVersionItem(
        version=str(getattr(module, "version", "") or ""),
        created_at=getattr(module, "created_at", None).isoformat() if getattr(module, "created_at", None) else None,
        uploaded_by=getattr(module, "uploaded_by", None),
        manifest_version=1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version"),
        module_api_version=manifest_json.get("module_api_version"),
        owner_scope=manifest_json.get("owner_scope"),
        validation_status=validation_status,
        validation_status_label=_module_validation_label(validation_status),
        preflight_status=preflight_status,
        preflight_status_label=_module_validation_label(preflight_status),
        is_preferred=preferred_version == str(getattr(module, "version", "") or ""),
        tools_count=len(manifest_json.get("tools") or []),
        platforms=[str(item) for item in (manifest_json.get("platforms") or ["any"])],
        tool_ids=_module_tool_ids(manifest_json),
        warnings_count=len(validation_json.get("warnings") or []),
        file_exists=_module_file_exists(module),
    )


def _empty_admin_modules_payload(*, query: str) -> AdminModulesPayload:
    return AdminModulesPayload(
        query=query,
        summary=AdminModulesSummary(
            visible_count=0,
            preferred_count=0,
            invalid_count=0,
            missing_files_count=0,
        ),
        rollout_settings=AdminModulesRolloutSettings(
            preferred_version_rollout_mode="manual",
            preferred_version_rollout_mode_label=_module_rollout_mode_label("manual"),
            sync_after_preferred_change=True,
        ),
        modules=[],
    )


def _parse_observer_lookback_hours(value: str | None) -> int:
    try:
        parsed = int(str(value or "").strip() or "24")
    except (TypeError, ValueError):
        return 24
    return max(1, min(parsed, 24 * 7))


def _compact_query_value(value: str | None) -> str | None:
    compacted = str(value or "").strip()
    return compacted or None


def _normalize_observer_status_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"running", "failed", "succeeded", "timed_out"}:
        return normalized
    return "all"


def _normalize_observer_root_kind_filter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    allowed = {"ticket", "tool_call", "agent_update", "module_install", "module_remove", "consent"}
    if normalized in allowed:
        return normalized
    return "all"


def _parse_observer_trace_limit(value: str | None) -> int:
    try:
        parsed = int(str(value or "").strip() or "25")
    except (TypeError, ValueError):
        return 25
    return max(5, min(parsed, 100))


def _observer_kind_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Неизвестный поток"
    return _OBSERVER_ROOT_KIND_LABELS.get(normalized, normalized.replace("_", " "))


def _observer_status_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "Статус неизвестен"
    return _OBSERVER_STATUS_LABELS.get(normalized, normalized.replace("_", " "))


def _observer_severity_label(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "critical":
        return "Критично"
    if normalized == "warning":
        return "Предупреждение"
    if normalized == "error":
        return "Ошибка"
    return "Инфо"


def _observer_runtime_summary_from_app(request: web.Request) -> AdminObserverRuntimeSummary:
    runtime = request.app._state.get("observer_refresh_runtime")
    if runtime is None:
        return AdminObserverRuntimeSummary(
            enabled=False,
            running=False,
            health_status="down",
            health_status_label=_OBSERVER_RUNTIME_STATUS_LABELS["down"],
            pending_trace_count=None,
            last_projected_at=None,
            issues=[],
        )

    snapshot = runtime.status_snapshot()
    health = snapshot.get("health") if isinstance(snapshot.get("health"), dict) else {}
    stats = snapshot.get("stats") if isinstance(snapshot.get("stats"), dict) else {}
    health_status = str(health.get("status") or "unknown").strip().lower() or "unknown"
    return AdminObserverRuntimeSummary(
        enabled=bool(snapshot.get("enabled")),
        running=bool(snapshot.get("running")),
        health_status=health_status,
        health_status_label=_OBSERVER_RUNTIME_STATUS_LABELS.get(
            health_status,
            _OBSERVER_RUNTIME_STATUS_LABELS["unknown"],
        ),
        pending_trace_count=health.get("pending_trace_count"),
        last_projected_at=stats.get("last_projected_at"),
        issues=[str(item) for item in health.get("issues") or []],
    )


def _empty_admin_observer_quick_payload(
    *,
    lookback_hours: int,
    request: web.Request,
) -> AdminObserverQuickPayload:
    return AdminObserverQuickPayload(
        summary=AdminObserverQuickSummary(
            lookback_hours=lookback_hours,
            recent_trace_count=0,
            hot_trace_count=0,
            signature_count=0,
            degradation_group_count=0,
            dangerous_flow_count=0,
        ),
        runtime=_observer_runtime_summary_from_app(request),
        hot_traces=[],
        top_signatures=[],
        top_degradations=[],
        dangerous_flows=[],
        links=AdminObserverQuickLinks(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


def _map_admin_observer_quick_trace(item: dict) -> AdminObserverQuickTrace:
    return AdminObserverQuickTrace(
        trace_id=str(item.get("trace_id") or ""),
        root_kind=item.get("root_kind"),
        root_kind_label=_observer_kind_label(item.get("root_kind")),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        ticket_id=item.get("ticket_id"),
        device_id=item.get("device_id"),
        duration_ms=item.get("duration_ms"),
        error_count=int(item.get("error_count") or 0),
        span_count=int(item.get("span_count") or 0),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
    )


def _map_admin_observer_trace_item(item: dict) -> AdminObserverTraceItem:
    return AdminObserverTraceItem(
        trace_id=str(item.get("trace_id") or ""),
        root_span_id=item.get("root_span_id"),
        root_kind=item.get("root_kind"),
        root_kind_label=_observer_kind_label(item.get("root_kind")),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        ticket_id=item.get("ticket_id"),
        device_id=item.get("device_id"),
        operation_id=item.get("operation_id"),
        job_id=item.get("job_id"),
        duration_ms=item.get("duration_ms"),
        error_count=int(item.get("error_count") or 0),
        span_count=int(item.get("span_count") or 0),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
    )


def _map_admin_observer_trace_span(item: dict) -> AdminObserverTraceSpanItem:
    return AdminObserverTraceSpanItem(
        span_id=str(item.get("span_id") or ""),
        trace_id=str(item.get("trace_id") or ""),
        parent_span_id=item.get("parent_span_id"),
        source_type=item.get("source_type"),
        source_ref=item.get("source_ref"),
        name=str(item.get("name") or ""),
        kind=item.get("kind"),
        component=item.get("component"),
        event_type=item.get("event_type"),
        module_name=item.get("module_name"),
        tool_name=item.get("tool_name"),
        status=item.get("status"),
        status_label=_observer_status_label(item.get("status")),
        started_at=item.get("started_at"),
        finished_at=item.get("finished_at"),
        duration_ms=item.get("duration_ms"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
    )


def _map_admin_observer_trace_span_link(item: dict) -> AdminObserverTraceSpanLinkItem:
    return AdminObserverTraceSpanLinkItem(
        id=int(item.get("id") or 0),
        span_id=str(item.get("span_id") or ""),
        linked_trace_id=item.get("linked_trace_id"),
        linked_span_id=item.get("linked_span_id"),
        reason=item.get("reason"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
        created_at=item.get("created_at"),
    )


def _map_admin_observer_error_occurrence(item: dict) -> AdminObserverTraceErrorOccurrenceItem:
    return AdminObserverTraceErrorOccurrenceItem(
        occurrence_id=str(item.get("occurrence_id") or ""),
        trace_id=str(item.get("trace_id") or ""),
        span_id=item.get("span_id"),
        error_signature=str(item.get("error_signature") or ""),
        device_id=item.get("device_id"),
        ticket_id=item.get("ticket_id"),
        operation_id=item.get("operation_id"),
        component=item.get("component"),
        module_name=item.get("module_name"),
        tool_name=item.get("tool_name"),
        error_kind=item.get("error_kind"),
        exception_type=item.get("exception_type"),
        failure_stage=item.get("failure_stage"),
        severity=item.get("severity"),
        severity_label=_observer_severity_label(item.get("severity")),
        message_norm=item.get("message_norm"),
        stack_hash=item.get("stack_hash"),
        attrs_json=item.get("attrs_json") if isinstance(item.get("attrs_json"), dict) else {},
        created_at=item.get("created_at"),
    )


def _map_admin_observer_signature(item: dict) -> AdminObserverSignatureItem:
    return AdminObserverSignatureItem(
        error_signature=str(item.get("error_signature") or ""),
        title=str(item.get("title") or "Без названия"),
        tool_name=item.get("tool_name"),
        component=item.get("component"),
        occurrences_count=int(item.get("occurrences_count") or 0),
        affected_devices_count=int(item.get("affected_devices_count") or 0),
        last_seen_at=item.get("last_seen_at"),
    )


def _map_admin_observer_degradation(item: dict) -> AdminObserverDegradationItem:
    return AdminObserverDegradationItem(
        operation_kind=item.get("operation_kind"),
        operation_kind_label=_observer_kind_label(item.get("operation_kind")),
        tool_name=item.get("tool_name"),
        operations_count=int(item.get("operations_count") or 0),
        timeout_count=int(item.get("timeout_count") or 0),
        retried_operations_count=int(item.get("retried_operations_count") or 0),
        slow_operations_count=int(item.get("slow_operations_count") or 0),
        max_duration_ms=int(item.get("max_duration_ms") or 0),
        latest_operation_at=item.get("latest_operation_at"),
    )


def _map_admin_observer_dangerous_flow(item: dict) -> AdminObserverDangerousFlowItem:
    root_kind = str(item.get("root_kind") or "").strip().lower() or "unknown"
    return AdminObserverDangerousFlowItem(
        root_kind=root_kind,
        root_kind_label=_observer_kind_label(root_kind),
        operations_count=int(item.get("operations_count") or 0),
        error_count=int(item.get("error_count") or 0),
        timeout_count=int(item.get("timeout_count") or 0),
        retried_count=int(item.get("retried_count") or 0),
        active_count=int(item.get("active_count") or 0),
        latest_operation_at=item.get("latest_operation_at"),
    )


def _resolve_target(device) -> str | None:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    raw = str(metadata.get("os_type") or getattr(device, "os", "") or "").strip().lower()
    if not raw:
        return None
    return _OS_TYPE_TO_TARGET.get(raw) or _OS_TYPE_TO_TARGET.get(raw.replace("_", " "))


def _matches_status_filter(*, online: bool, status_filter: str) -> bool:
    if status_filter == "online":
        return online
    if status_filter == "offline":
        return not online
    return True


def _matches_query(item: AdminDeviceItem, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [
            item.device_id,
            item.hostname or "",
            item.os or "",
            item.agent_version or "",
            item.target or "",
            item.connection_status_label,
            item.latest_update.label,
            item.latest_update.summary or "",
        ]
    ).lower()
    return query.lower() in haystack


def _build_update_summary(*, online: bool) -> AdminDeviceUpdateSummary:
    if online:
        return AdminDeviceUpdateSummary(
            status="healthy",
            label="Готово к действиям",
            summary="Устройство сейчас доступно для rollout и диагностики.",
        )
    return AdminDeviceUpdateSummary(
        status="unknown",
        label="Ждёт связи",
        summary="Свежий update-status появится после следующего подключения агента.",
    )


def _build_device_item(device, *, online: bool) -> AdminDeviceItem:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    hostname = getattr(device, "hostname", None) or metadata.get("hostname")
    os_name = getattr(device, "os", None) or metadata.get("os_type")
    agent_version = getattr(device, "agent_version", None) or metadata.get("agent_version") or metadata.get("version")
    last_seen_at = getattr(device, "last_seen_at", None)
    return AdminDeviceItem(
        device_id=str(getattr(device, "device_id", "") or ""),
        hostname=str(hostname) if hostname else None,
        os=str(os_name) if os_name else None,
        agent_version=str(agent_version) if agent_version else None,
        target=_resolve_target(device),
        online=online,
        last_seen_at=last_seen_at.isoformat() if last_seen_at else None,
        connection_status_label="Онлайн" if online else "Оффлайн",
        latest_update=_build_update_summary(online=online),
    )


def _current_agent_version(device) -> str | None:
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
    raw = getattr(device, "agent_version", None) or metadata.get("agent_version") or metadata.get("version")
    value = str(raw or "").strip()
    return value or None


def _rollout_assignment_model(payload: dict | None) -> AdminRolloutAssignment | None:
    if not payload:
        return None
    target = str(payload.get("target") or "").strip()
    channel = str(payload.get("channel") or "").strip().lower()
    version = str(payload.get("version") or "").strip()
    if not target or not channel or not version:
        return None
    return AdminRolloutAssignment(
        target=target,
        channel=channel,
        version=version,
        updated_at=payload.get("updated_at"),
        updated_by=payload.get("updated_by"),
    )


def _build_identity_model(payload: dict | None) -> AdminBuildIdentity | None:
    if not payload:
        return None
    target = str(payload.get("target") or "").strip()
    channel = str(payload.get("channel") or "").strip().lower()
    version = str(payload.get("version") or "").strip()
    if not target or not channel or not version:
        return None
    return AdminBuildIdentity(target=target, channel=channel, version=version)


async def _build_admin_observer_quick_payload(
    *,
    request: web.Request,
    lookback_hours: int,
    device_id: str | None,
) -> AdminObserverQuickPayload:
    runtime = _observer_runtime_summary_from_app(request)

    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_payload = await service.get_quick_diagnosis(
                TraceOverlayFilters(lookback_hours=lookback_hours, device_id=device_id),
                hot_limit=5,
                signature_limit=4,
                degradation_limit=4,
                flow_limit=4,
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "[web_admin_observer_quick] returning empty payload for "
            f"lookback_hours={lookback_hours}, device_id={device_id}: {exc}"
        )
        return _empty_admin_observer_quick_payload(lookback_hours=lookback_hours, request=request)

    summary = raw_payload.get("summary") if isinstance(raw_payload.get("summary"), dict) else {}
    return AdminObserverQuickPayload(
        summary=AdminObserverQuickSummary(
            lookback_hours=lookback_hours,
            recent_trace_count=int(summary.get("recent_trace_count") or 0),
            hot_trace_count=int(summary.get("hot_trace_count") or 0),
            signature_count=int(summary.get("signature_count") or 0),
            degradation_group_count=int(summary.get("degradation_group_count") or 0),
            dangerous_flow_count=int(summary.get("dangerous_flow_count") or 0),
        ),
        runtime=runtime,
        hot_traces=[
            _map_admin_observer_quick_trace(item)
            for item in raw_payload.get("hot_traces") or []
            if isinstance(item, dict)
        ],
        top_signatures=[
            _map_admin_observer_signature(item)
            for item in raw_payload.get("top_signatures") or []
            if isinstance(item, dict)
        ],
        top_degradations=[
            _map_admin_observer_degradation(item)
            for item in raw_payload.get("top_degradations") or []
            if isinstance(item, dict)
        ],
        dangerous_flows=[
            _map_admin_observer_dangerous_flow(item)
            for item in raw_payload.get("dangerous_flows") or []
            if isinstance(item, dict)
        ],
        links=AdminObserverQuickLinks(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


def _build_observer_trace_filters(
    *,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
) -> TraceOverlayFilters:
    return TraceOverlayFilters(
        device_id=device_id,
        lookback_hours=lookback_hours,
        status=None if status_filter == "all" else status_filter,
        root_kind=None if root_kind_filter == "all" else root_kind_filter,
    )


def _empty_admin_observer_traces_payload(
    *,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    limit: int,
) -> AdminObserverTracesPayload:
    return AdminObserverTracesPayload(
        query=AdminObserverTracesQuery(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
        ),
        summary=AdminObserverTracesSummary(
            visible_count=0,
            active_count=0,
            error_count=0,
            selected_trace_id=None,
        ),
        filters=AdminObserverTracesFilters(
            status_options=_OBSERVER_TRACE_STATUS_OPTIONS,
            root_kind_options=_OBSERVER_TRACE_ROOT_KIND_OPTIONS,
        ),
        traces=[],
        links=AdminObserverTracesLinks(
            detail_endpoint_template=_OBSERVER_TRACE_DETAIL_TEMPLATE,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


async def _build_admin_observer_traces_payload(
    *,
    request: web.Request,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    limit: int,
) -> AdminObserverTracesPayload:
    filters = _build_observer_trace_filters(
        device_id=device_id,
        lookback_hours=lookback_hours,
        status_filter=status_filter,
        root_kind_filter=root_kind_filter,
    )
    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_traces = await service.search_traces(filters, limit=limit)
            await session.commit()
    except Exception as exc:
        logger.warning(
            "[web_admin_observer_traces] returning empty payload for "
            f"device_id={device_id}, lookback_hours={lookback_hours}, "
            f"status_filter={status_filter}, root_kind_filter={root_kind_filter}: {exc}"
        )
        return _empty_admin_observer_traces_payload(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
        )

    traces = [
        _map_admin_observer_trace_item(item)
        for item in raw_traces
        if isinstance(item, dict) and item.get("trace_id")
    ]
    active_count = sum(1 for item in traces if str(item.status or "").strip().lower() in _OBSERVER_ACTIVE_STATUSES)
    error_count = sum(
        1
        for item in traces
        if item.error_count > 0 or str(item.status or "").strip().lower() in _OBSERVER_ERROR_STATUSES
    )
    return AdminObserverTracesPayload(
        query=AdminObserverTracesQuery(
            device_id=device_id,
            lookback_hours=lookback_hours,
            status_filter=status_filter,
            root_kind_filter=root_kind_filter,
            limit=limit,
        ),
        summary=AdminObserverTracesSummary(
            visible_count=len(traces),
            active_count=active_count,
            error_count=error_count,
            selected_trace_id=traces[0].trace_id if traces else None,
        ),
        filters=AdminObserverTracesFilters(
            status_options=_OBSERVER_TRACE_STATUS_OPTIONS,
            root_kind_options=_OBSERVER_TRACE_ROOT_KIND_OPTIONS,
        ),
        traces=traces,
        links=AdminObserverTracesLinks(
            detail_endpoint_template=_OBSERVER_TRACE_DETAIL_TEMPLATE,
            runtime_endpoint=_OBSERVER_RUNTIME_ENDPOINT,
        ),
    )


async def _build_admin_observer_trace_detail_payload(
    *,
    request: web.Request,
    trace_id: str,
) -> AdminObserverTraceDetailPayload:
    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_detail = await service.get_trace_detail(trace_id)
            if raw_detail is None:
                await session.rollback()
                raise LookupError("TRACE_NOT_FOUND")
            await session.commit()
    except LookupError:
        raise
    except Exception as exc:
        logger.error(f"[web_admin_observer_trace_detail] Failed to load trace_id={trace_id}: {exc}")
        logger.exception(exc)
        raise

    trace_payload = raw_detail.get("trace") if isinstance(raw_detail.get("trace"), dict) else {}
    spans = [
        _map_admin_observer_trace_span(item)
        for item in raw_detail.get("spans") or []
        if isinstance(item, dict) and item.get("span_id")
    ]
    span_links = [
        _map_admin_observer_trace_span_link(item)
        for item in raw_detail.get("span_links") or []
        if isinstance(item, dict) and item.get("id") is not None
    ]
    error_occurrences = [
        _map_admin_observer_error_occurrence(item)
        for item in raw_detail.get("error_occurrences") or []
        if isinstance(item, dict) and item.get("occurrence_id")
    ]
    linked_trace_count = len({item.linked_trace_id for item in span_links if item.linked_trace_id})
    return AdminObserverTraceDetailPayload(
        trace=_map_admin_observer_trace_item(trace_payload),
        summary=AdminObserverTraceDetailSummary(
            span_count=len(spans),
            error_count=len(error_occurrences),
            linked_trace_count=linked_trace_count,
        ),
        spans=spans,
        span_links=span_links,
        error_occurrences=error_occurrences,
    )


def _build_update_recommendation_summary(
    *,
    online: bool,
    target: str | None,
    recommended_build: AdminBuildIdentity | None,
    update_available: bool,
    comparison: str,
    source_label: str,
    reason_label: str | None,
) -> AdminDeviceUpdateSummary:
    if not target:
        return AdminDeviceUpdateSummary(
            status="target_unknown",
            label="Не удалось определить target",
            summary="Сервер не смог подобрать target для этого устройства, поэтому update workflow пока недоступен.",
        )
    if not online:
        return AdminDeviceUpdateSummary(
            status="offline",
            label="Ждёт связи",
            summary="Запуск обновления доступен только когда агент онлайн и может принять команду.",
        )
    if not recommended_build:
        return AdminDeviceUpdateSummary(
            status="missing_build",
            label="Нет рекомендуемого build",
            summary="Для этого target пока нет rollout policy или доступного release build на сервере.",
        )

    build_label = f"{recommended_build.channel}/{recommended_build.version}"
    if update_available:
        if comparison == "recommended_release_is_older":
            return AdminDeviceUpdateSummary(
                status="rollback_available",
                label="Назначен rollback",
                summary=f"{source_label} рекомендует {build_label}. {reason_label or ''}".strip(),
            )
        return AdminDeviceUpdateSummary(
            status="update_available",
            label="Доступно обновление",
            summary=f"{source_label} рекомендует {build_label}. {reason_label or ''}".strip(),
        )

    return AdminDeviceUpdateSummary(
        status="up_to_date",
        label="Актуальная версия",
        summary=f"Устройство уже синхронизировано с рекомендацией {source_label.lower()} {build_label}.",
    )


async def _build_admin_device_updates_payload(*, device_id: str, state) -> AdminDeviceUpdatesPayload:
    async with get_session() as session:
        device = await DevicesRepo(session).get_by_device_id(device_id)
        if not device:
            raise LookupError("DEVICE_NOT_FOUND")

        target = _resolve_target_for_device(device)
        current_version = _current_agent_version(device)
        recommended_build = None
        recommendation_source = "none"
        assignment = None
        if target:
            recommended_build, recommendation_source, assignment = await _resolve_recommended_build(session, target=target)

    source_label = _UPDATE_RECOMMENDATION_SOURCE_LABELS.get(
        recommendation_source,
        _UPDATE_RECOMMENDATION_SOURCE_LABELS["none"],
    )
    current_release_channel = _infer_release_channel(current_version) if current_version else "unknown"
    current_is_release = _is_release_build(version=current_version, channel=current_release_channel) if current_version else False
    comparison = "unknown"
    update_available = False
    recommended_reason = None

    if recommended_build and current_version:
        compare_result = compare_versions(recommended_build.version, current_version)
        version_mismatch = recommended_build.version != current_version
        if compare_result > 0:
            comparison = "newer_release_available"
        elif compare_result < 0:
            comparison = "recommended_release_is_older"
        else:
            comparison = "same_version"
        if recommendation_source == "assigned_rollout":
            if compare_result > 0:
                update_available = True
                recommended_reason = "assigned_rollout_newer"
            elif compare_result < 0:
                update_available = True
                recommended_reason = "assigned_rollout_older"
            elif not current_is_release and version_mismatch:
                update_available = True
                recommended_reason = "assigned_rollout_non_release_current"
            else:
                recommended_reason = "assigned_rollout"
        elif current_is_release:
            if compare_result > 0:
                update_available = True
                recommended_reason = "newer_release_available"
        elif version_mismatch:
            update_available = True
            recommended_reason = "non_release_current_version"
    elif recommended_build and not current_version:
        update_available = True
        comparison = "unknown"
        recommended_reason = "assigned_rollout" if recommendation_source == "assigned_rollout" else "current_version_unknown"

    recommended_build_model = _build_identity_model(
        {
            "target": getattr(recommended_build, "target", None),
            "channel": getattr(recommended_build, "channel", None),
            "version": getattr(recommended_build, "version", None),
        }
        if recommended_build
        else None
    )
    assignment_model = _rollout_assignment_model(assignment)
    online = bool(state is not None and hasattr(state, "is_agent_online") and state.is_agent_online(device_id))
    reason_label = _UPDATE_REASON_LABELS.get(recommended_reason)
    summary = _build_update_recommendation_summary(
        online=online,
        target=target,
        recommended_build=recommended_build_model,
        update_available=update_available,
        comparison=comparison,
        source_label=source_label,
        reason_label=reason_label,
    )
    action_enabled = bool(online and target and recommended_build_model)
    action_label = "Ожидает связи"
    if action_enabled:
        action_label = "Запустить обновление" if update_available else "Повторить rollout"
    elif target and not recommended_build_model:
        action_label = "Нет build-а"

    hostname = getattr(device, "hostname", None) or device_id
    return AdminDeviceUpdatesPayload(
        device_id=device_id,
        device_label=str(hostname),
        online=online,
        target=target,
        current_version=current_version,
        release_channel=current_release_channel,
        is_release=current_is_release,
        summary=summary,
        recommendation=AdminDeviceUpdateRecommendation(
            update_available=update_available,
            recommendation_source=recommendation_source,
            recommendation_source_label=source_label,
            comparison=comparison,
            comparison_label=_UPDATE_COMPARISON_LABELS.get(comparison, _UPDATE_COMPARISON_LABELS["unknown"]),
            recommended_reason=recommended_reason,
            recommended_reason_label=reason_label,
            recommended_build=recommended_build_model,
            assigned_rollout=assignment_model,
        ),
        action=AdminDeviceUpdateAction(
            enabled=action_enabled,
            label=action_label,
            reason_required=True,
            endpoint=f"/api/web/admin/devices/{device_id}/updates/run",
        ),
    )


async def _run_admin_device_update(
    *,
    state,
    auth_context: AuthContext,
    device_id: str,
    reason: str,
    restart_delay_sec: int | None,
) -> AdminDeviceUpdateRunPayload:
    update_payload = await _build_admin_device_updates_payload(device_id=device_id, state=state)
    recommended_build = update_payload.recommendation.recommended_build
    if not recommended_build:
        raise AgentUpdateRequestError(
            status=409,
            payload={
                "status": "error",
                "error": "Для устройства нет рекомендуемого build",
                "error_code": "RECOMMENDED_BUILD_MISSING",
                "device_id": device_id,
            },
        )

    raw_result = await enqueue_device_agent_update(
        state=state,
        auth_context=auth_context,
        device_id=device_id,
        target=recommended_build.target,
        channel=recommended_build.channel,
        version=recommended_build.version,
        restart_delay_sec=restart_delay_sec,
        reason=_sanitize_update_reason(reason),
    )
    build = raw_result["build"]
    build_identity = AdminBuildIdentity(
        target=str(build.get("target") or ""),
        channel=str(build.get("channel") or ""),
        version=str(build.get("version") or ""),
    )
    operation_id = str(raw_result["operation_id"])
    return AdminDeviceUpdateRunPayload(
        device_id=device_id,
        operation_id=operation_id,
        status="queued",
        message=(
            f"Операция {operation_id} поставлена в очередь. "
            f"Агент получит build {build_identity.channel}/{build_identity.version} после доставки команды."
        ),
        build_source=str(raw_result.get("build_source") or ""),
        poll_url=f"/api/operations/{operation_id}",
        build=build_identity,
    )


async def _build_admin_modules_payload(*, query: str) -> AdminModulesPayload:
    normalized_query = str(query or "").strip()
    query_lower = normalized_query.lower()

    async with get_session() as session:
        modules = await ModulesRepo(session).list_modules(limit=300)
        preferred_assignments = await _get_module_preferred_assignments(session)
        rollout_settings = await _get_module_rollout_settings(session)

    grouped: dict[str, list[object]] = {}
    for module in modules:
        grouped.setdefault(str(getattr(module, "module_name", "") or ""), []).append(module)

    families: list[AdminModuleFamilyItem] = []
    missing_files_count = 0
    invalid_count = 0
    preferred_count = 0
    for module_name in sorted(name for name in grouped if name):
        versions = sorted(
            grouped[module_name],
            key=lambda item: (
                version_key(str(getattr(item, "version", "") or "")).key,
                getattr(item, "created_at", None).isoformat() if getattr(item, "created_at", None) else "",
            ),
            reverse=True,
        )
        preferred_version = preferred_assignments.get(module_name, {}).get("version")
        version_items = [
            _map_admin_module_version_item(module, preferred_version=preferred_version)
            for module in versions
        ]
        primary_module = _pick_primary_module_record(versions, preferred_version)
        if primary_module is None:
            continue
        primary_manifest = get_module_manifest(primary_module)
        primary_validation = get_module_validation(primary_module)
        primary_validation_status = (
            str(primary_validation.get("validation_status") or "unknown").strip().lower() or "unknown"
        )
        tool_ids = _module_tool_ids(primary_manifest)
        family = AdminModuleFamilyItem(
            module_name=module_name,
            preferred_version=preferred_version,
            preferred_assigned=bool(preferred_version and any(item.is_preferred for item in version_items)),
            latest_version=version_items[0].version if version_items else None,
            owner_scope=primary_manifest.get("owner_scope"),
            module_api_version=primary_manifest.get("module_api_version"),
            validation_status=primary_validation_status,
            validation_status_label=_module_validation_label(primary_validation_status),
            version_count=len(version_items),
            tools_count=max((item.tools_count for item in version_items), default=0),
            platforms=[str(item) for item in (primary_manifest.get("platforms") or ["any"])],
            tool_ids=tool_ids,
            warnings_count=max((item.warnings_count for item in version_items), default=0),
            has_missing_files=any(not item.file_exists for item in version_items),
            versions=version_items,
        )
        haystack = " ".join(
            [
                family.module_name,
                family.preferred_version or "",
                family.latest_version or "",
                family.owner_scope or "",
                family.module_api_version or "",
                *family.platforms,
                *family.tool_ids,
                *(item.version for item in version_items),
            ]
        ).lower()
        if query_lower and query_lower not in haystack:
            continue
        if family.preferred_assigned:
            preferred_count += 1
        if family.validation_status in {"failed", "warning"}:
            invalid_count += 1
        if family.has_missing_files:
            missing_files_count += 1
        families.append(family)

    rollout_mode = str(rollout_settings.get("preferred_version_rollout_mode") or "manual").strip().lower() or "manual"
    return AdminModulesPayload(
        query=normalized_query,
        summary=AdminModulesSummary(
            visible_count=len(families),
            preferred_count=preferred_count,
            invalid_count=invalid_count,
            missing_files_count=missing_files_count,
        ),
        rollout_settings=AdminModulesRolloutSettings(
            preferred_version_rollout_mode=rollout_mode,
            preferred_version_rollout_mode_label=_module_rollout_mode_label(rollout_mode),
            sync_after_preferred_change=bool(rollout_settings.get("sync_after_preferred_change", True)),
        ),
        modules=families,
    )


@require_auth("admin")
async def handle_web_admin_bootstrap(_request):
    payload = AdminBootstrapPayload(
        workspace="admin",
        features=[
            "devices_inventory",
            "agent_rollout",
            "modules_workbench",
            "tech_panel",
        ],
        observer=AdminObserverCapabilities(
            quick_endpoint=_OBSERVER_QUICK_ENDPOINT,
            traces_endpoint=_OBSERVER_TRACES_ENDPOINT,
        ),
    )
    return json_model_response(SuccessResponse[AdminBootstrapPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_quick(request: web.Request):
    lookback_hours = _parse_observer_lookback_hours(request.query.get("lookback_hours"))
    device_id = _compact_query_value(request.query.get("device_id"))
    payload = await _build_admin_observer_quick_payload(
        request=request,
        lookback_hours=lookback_hours,
        device_id=device_id,
    )
    return json_model_response(SuccessResponse[AdminObserverQuickPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_traces(request: web.Request):
    device_id = _compact_query_value(request.query.get("device_id"))
    lookback_hours = _parse_observer_lookback_hours(request.query.get("lookback_hours"))
    status_filter = _normalize_observer_status_filter(request.query.get("status"))
    root_kind_filter = _normalize_observer_root_kind_filter(request.query.get("root_kind"))
    limit = _parse_observer_trace_limit(request.query.get("limit"))
    payload = await _build_admin_observer_traces_payload(
        request=request,
        device_id=device_id,
        lookback_hours=lookback_hours,
        status_filter=status_filter,
        root_kind_filter=root_kind_filter,
        limit=limit,
    )
    return json_model_response(SuccessResponse[AdminObserverTracesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_observer_trace_detail(request: web.Request):
    trace_id = request.match_info["trace_id"]
    try:
        payload = await _build_admin_observer_trace_detail_payload(request=request, trace_id=trace_id)
    except LookupError:
        return web.json_response(
            {
                "status": "error",
                "error": "Трасса не найдена",
                "error_code": "TRACE_NOT_FOUND",
                "trace_id": trace_id,
            },
            status=404,
        )
    except Exception:
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить детали трассы",
                "error_code": "ADMIN_OBSERVER_TRACE_DETAIL_FAILED",
                "trace_id": trace_id,
            },
            status=500,
        )
    return json_model_response(SuccessResponse[AdminObserverTraceDetailPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_devices(request: web.Request):
    query = str(request.query.get("query", "") or "").strip()
    status_filter = _normalize_status_filter(request.query.get("status"))
    state = request.app.get("state")

    try:
        async with get_session() as session:
            devices = await DevicesRepo(session).list_all()
            rollout_assignments = await AgentRolloutRepo(session).list_assignments()

        typed_devices: list[AdminDeviceItem] = []
        online_count = 0
        for device in devices:
            device_id = str(getattr(device, "device_id", "") or "")
            is_online = bool(
                device_id
                and state is not None
                and hasattr(state, "is_agent_online")
                and state.is_agent_online(device_id)
            )
            if is_online:
                online_count += 1
            if not _matches_status_filter(online=is_online, status_filter=status_filter):
                continue
            item = _build_device_item(device, online=is_online)
            if _matches_query(item, query):
                typed_devices.append(item)

        typed_rollout = [
            AdminRolloutAssignment(
                target=str(item.get("target") or ""),
                channel=str(item.get("channel") or ""),
                version=str(item.get("version") or ""),
                updated_at=item.get("updated_at"),
                updated_by=item.get("updated_by"),
            )
            for item in rollout_assignments
            if item.get("target") and item.get("channel") and item.get("version")
        ]
        payload = AdminDevicesPayload(
            query=query,
            status_filter=status_filter,
            summary=AdminDevicesSummary(
                visible_count=len(typed_devices),
                online_count=online_count,
                rollout_targets=len(typed_rollout),
            ),
            filters=AdminDevicesFilters(status_options=STATUS_OPTIONS),
            rollout=typed_rollout,
            devices=typed_devices,
        )
    except Exception as exc:
        logger.warning(
            f"[web_admin_devices] DB unavailable, returning empty devices payload: "
            f"status_filter={status_filter}, error={exc}"
        )
        payload = _empty_devices_payload(query=query, status_filter=status_filter)

    return json_model_response(SuccessResponse[AdminDevicesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_modules(request: web.Request):
    query = str(request.query.get("query", "") or "").strip()

    try:
        payload = await _build_admin_modules_payload(query=query)
    except Exception as exc:
        logger.warning(
            f"[web_admin_modules] DB unavailable, returning empty modules payload: "
            f"query={query!r}, error={exc}"
        )
        payload = _empty_admin_modules_payload(query=query)

    return json_model_response(SuccessResponse[AdminModulesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_updates(request: web.Request):
    device_id = request.match_info["device_id"]
    state = request.app.get("state")

    try:
        payload = await _build_admin_device_updates_payload(device_id=device_id, state=state)
    except LookupError:
        return web.json_response(
            {
                "status": "error",
                "error": "Устройство не найдено",
                "error_code": "DEVICE_NOT_FOUND",
                "device_id": device_id,
            },
            status=404,
        )
    except Exception as exc:
        logger.error(f"[web_admin_device_updates] Failed to build typed update payload for {device_id}: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить update workflow для устройства",
                "error_code": "ADMIN_DEVICE_UPDATES_FAILED",
                "device_id": device_id,
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminDeviceUpdatesPayload](data=payload))


@require_auth("admin")
async def handle_web_admin_device_update_run(request: web.Request):
    device_id = request.match_info["device_id"]
    state = request.app.get("state")
    auth_context: AuthContext = request["auth_context"]

    try:
        raw_payload = await request.json()
        payload = AdminDeviceUpdateRunRequest.model_validate(raw_payload)
    except (ValidationError, Exception):
        return web.json_response(
            {
                "status": "error",
                "error": "Укажите причину запуска обновления",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    if not str(payload.reason or "").strip():
        return web.json_response(
            {
                "status": "error",
                "error": "Укажите причину запуска обновления",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        result = await _run_admin_device_update(
            state=state,
            auth_context=auth_context,
            device_id=device_id,
            reason=payload.reason,
            restart_delay_sec=payload.restart_delay_sec,
        )
    except LookupError:
        return web.json_response(
            {
                "status": "error",
                "error": "Устройство не найдено",
                "error_code": "DEVICE_NOT_FOUND",
                "device_id": device_id,
            },
            status=404,
        )
    except AgentUpdateRequestError as exc:
        return web.json_response(exc.payload, status=exc.status)
    except Exception as exc:
        logger.error(f"[web_admin_device_update_run] Failed to queue device update for {device_id}: {exc}")
        logger.exception(exc)
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось поставить обновление в очередь",
                "error_code": "ADMIN_DEVICE_UPDATE_RUN_FAILED",
                "device_id": device_id,
            },
            status=500,
        )

    return json_model_response(SuccessResponse[AdminDeviceUpdateRunPayload](data=result), status=202)
