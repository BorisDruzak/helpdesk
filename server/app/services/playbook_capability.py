"""
Этап 9: Capability Gate — проверка перед постановкой run_tool в очередь.

Проверяет: tool есть в актуальном toolset snapshot устройства; при наличии metadata — платформа и capability.
Формат snapshot: каждый tool имеет tool, spec; metadata в spec (tool.spec.metadata).
При несовместимости возвращает (False, error_code, message) без отправки команды агенту.
"""
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.devices_repo import DevicesRepo
from app.repos.toolset_snapshots_repo import ToolsetSnapshotsRepo


async def check_tool_available(
    session: AsyncSession,
    device_id: str,
    tool_name: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Проверяет, что tool доступен на устройстве (есть в toolset snapshot).
    Опционально: платформа (device.os vs metadata.platforms), capability для риск-команд.
    Читает metadata из формата snapshot: tool.spec.metadata (не tool.metadata).

    Returns:
        (ok, error_code, error_message). При ok=True — error_code и error_message None.
    """
    devices_repo = DevicesRepo(session)
    snap_repo = ToolsetSnapshotsRepo(session)
    device = await devices_repo.get_by_device_id(device_id)
    if not device:
        return (False, "TOOL_UNAVAILABLE", "Device not found")
    snapshot = await snap_repo.get_latest_snapshot(device_id)
    if not snapshot or not snapshot.toolset_json:
        return (False, "TOOL_UNAVAILABLE", "No toolset snapshot for device")
    tools = snapshot.toolset_json.get("tools") or []
    tool_entry = None
    for t in tools:
        name = t.get("tool") or t.get("name")
        if name == tool_name:
            tool_entry = t
            break
    if not tool_entry:
        return (False, "UNSUPPORTED_CAPABILITY", f"Tool {tool_name!r} not in device toolset")
    # Формат snapshot от агента: metadata внутри spec (tool.spec.metadata)
    spec = tool_entry.get("spec") or {}
    meta = spec.get("metadata") or tool_entry.get("metadata") or {}
    platforms = meta.get("platforms")
    if platforms and isinstance(platforms, list) and device.os:
        os_norm = (device.os or "").lower()
        if os_norm and not any(p and (str(p).lower() in os_norm or os_norm.startswith(str(p).lower())) for p in platforms):
            return (False, "UNSUPPORTED_CAPABILITY", f"Tool {tool_name!r} not supported on platform {device.os}")
    return (True, None, None)
