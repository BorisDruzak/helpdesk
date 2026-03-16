"""
Модуль синхронизации inventory модулей между агентом и сервером.
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repos import DeviceModulesRepo


def flatten_modules_list(modules_list: List[dict]) -> List[dict]:
    """
    Convert list_installed_modules format to flattened inventory format.
    
    КРИТИЧНО: Единый helper для handshake и command_result.
    
    Input format (от агента):
        [
            {
                "name": "module_name",
                "active": "1.0.0" | None,
                "versions": ["1.0.0", "1.0.1", ...]
            },
            ...
        ]
    
    Output format (flattened):
        [
            {"name": "module_name", "version": "1.0.0", "state": "active", "active": True},
            {"name": "module_name", "version": "1.0.1", "state": "installed", "active": False},
            ...
        ]
    """
    result = []
    for module_info in modules_list:
        module_name = module_info.get("name")
        active_version = module_info.get("active")  # может быть None
        versions = module_info.get("versions", [])
        
        if not module_name or not versions:
            continue
        
        for version in versions:
            result.append({
                "name": module_name,
                "version": version,
                "state": "active" if version == active_version else "installed",
                "active": version == active_version
            })
    return result


async def sync_modules_inventory(
    session: AsyncSession,
    device_id: str,
    inventory: List[dict],
    source: str = "command_result",
) -> None:
    """
    Синхронизирует device_modules с inventory от агента.
    
    Idempotent: upsert для всех записей из inventory,
    помечает отсутствующие как installed=False (опционально).
    
    Args:
        session: AsyncSession для БД
        device_id: ID устройства
        inventory: Список модулей в flattened формате
                   [{name, version, state, active}, ...]
        source: Источник обновления (handshake|command_result|event)
    """
    repo = DeviceModulesRepo(session)
    
    # Собираем множество (device_id, module_name, version) из inventory
    inventory_keys = set()
    for item in inventory:
        module_name = item.get("name")
        version = item.get("version")
        if module_name and version:
            inventory_keys.add((module_name, version))
    
    # Upsert всех записей из inventory
    for item in inventory:
        module_name = item.get("name")
        version = item.get("version")
        state = item.get("state", "installed")
        active = item.get("active", False)
        
        if not module_name or not version:
            continue
        
        await repo.upsert_device_module(
            device_id=device_id,
            module_name=module_name,
            version=version,
            installed=True,
            active=active,
            state=state if state in ["installed", "active"] else "installed",
            source=source,
            update_last_seen=True,
        )
    
    # Помечаем отсутствующие версии как missing (не removed!)
    # removed используется только для явных remove/uninstall команд
    existing_modules = await repo.get_device_modules(device_id)
    for existing in existing_modules:
        key = (existing.module_name, existing.version)
        if key not in inventory_keys and existing.state != "removed":
            # Помечаем как missing (не удаляем строку для истории)
            await repo.update_module_state(
                device_id=device_id,
                module_name=existing.module_name,
                version=existing.version,
                installed=False,
                active=False,
                state="missing"
            )
    
    logger.info(
        f"[modules_sync] Synced inventory for device_id={device_id}: "
        f"{len(inventory_keys)} modules, "
        f"{len([m for m in existing_modules if (m.module_name, m.version) not in inventory_keys])} marked as missing"
    )


async def check_module_tools_drift(
    session: AsyncSession,
    device_id: str
) -> List[dict]:
    """
    Проверяет расхождение между device_modules.active и toolset snapshot.
    
    Returns:
        List of drift warnings: [{"module_name": "...", "issue": "..."}]
    """
    from app.repos import DeviceModulesRepo, ToolsetSnapshotsRepo
    
    device_modules_repo = DeviceModulesRepo(session)
    snapshots_repo = ToolsetSnapshotsRepo(session)
    
    # Get active modules
    active_modules = await device_modules_repo.get_active_modules(device_id)
    
    # Get latest snapshot
    latest_snapshot = await snapshots_repo.get_latest_snapshot(device_id)
    if not latest_snapshot:
        return []  # No snapshot yet
    
    tools_list = latest_snapshot.toolset_json.get("tools", [])
    tools_by_module = {}
    for tool in tools_list:
        module_name = tool.get("module")
        if module_name:
            if module_name not in tools_by_module:
                tools_by_module[module_name] = []
            tools_by_module[module_name].append(tool)
    
    # Check drift
    drift_warnings = []
    for module in active_modules:
        module_name = module.module_name
        if module_name not in tools_by_module:
            drift_warnings.append({
                "module_name": module_name,
                "issue": "active but tools missing",
                "module_version": module.version
            })
    
    # Log warnings
    if drift_warnings:
        logger.warning(
            f"[drift_check] Device {device_id} has drift: {drift_warnings}"
        )
    
    return drift_warnings

