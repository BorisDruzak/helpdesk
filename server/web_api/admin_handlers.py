from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.agent_rollout_repo import AgentRolloutRepo
from app.repos.devices_repo import DevicesRepo
from auth.middleware import require_auth
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.admin import (
    AdminBootstrapPayload,
    AdminDeviceItem,
    AdminDevicesFilters,
    AdminDevicesPayload,
    AdminDevicesSummary,
    AdminDeviceUpdateSummary,
    AdminFilterOption,
    AdminObserverCapabilities,
    AdminRolloutAssignment,
)


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
            quick_endpoint="/api/admin/tech/observer/quick",
            traces_endpoint="/api/admin/tech/traces",
        ),
    )
    return json_model_response(SuccessResponse[AdminBootstrapPayload](data=payload))


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
