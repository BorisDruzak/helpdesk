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
    AdminDeviceItem,
    AdminDeviceUpdateAction,
    AdminDeviceUpdateRecommendation,
    AdminDeviceUpdateRunPayload,
    AdminDeviceUpdateRunRequest,
    AdminDevicesFilters,
    AdminDevicesPayload,
    AdminDevicesSummary,
    AdminDeviceUpdateSummary,
    AdminDeviceUpdatesPayload,
    AdminFilterOption,
    AdminObserverCapabilities,
    AdminRolloutAssignment,
)
from utils.versioning import compare_versions


STATUS_OPTIONS = [
    AdminFilterOption(value="all", label="Все устройства"),
    AdminFilterOption(value="online", label="Только онлайн"),
    AdminFilterOption(value="offline", label="Только офлайн"),
]

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

_OBSERVER_QUICK_ENDPOINT = "/api/admin/tech/observer/quick"
_OBSERVER_TRACES_ENDPOINT = "/api/admin/tech/traces"
_OBSERVER_RUNTIME_ENDPOINT = "/api/admin/tech/traces/runtime"


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


def _parse_observer_lookback_hours(value: str | None) -> int:
    try:
        parsed = int(str(value or "").strip() or "24")
    except (TypeError, ValueError):
        return 24
    return max(1, min(parsed, 24 * 7))


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
) -> AdminObserverQuickPayload:
    runtime = _observer_runtime_summary_from_app(request)

    try:
        async with get_session() as session:
            service = ObserverOverlayService(session)
            raw_payload = await service.get_quick_diagnosis(
                TraceOverlayFilters(lookback_hours=lookback_hours),
                hot_limit=5,
                signature_limit=4,
                degradation_limit=4,
                flow_limit=4,
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            f"[web_admin_observer_quick] returning empty payload for lookback_hours={lookback_hours}: {exc}"
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
    payload = await _build_admin_observer_quick_payload(request=request, lookback_hours=lookback_hours)
    return json_model_response(SuccessResponse[AdminObserverQuickPayload](data=payload))


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
