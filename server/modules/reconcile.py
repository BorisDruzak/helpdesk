"""
Reconcile Engine для модульной системы.

Сравнивает desired state (device_desired_modules) с actual state (device_modules)
и генерирует недостающие install/remove команды агентам.

Запускается:
1. По расписанию (periodic job — каждые 5 минут)
2. Сразу после получения module_state_changed event от агента
3. При reconnect агента (handshake)
"""

import uuid
from typing import Optional, List
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repos import DeviceDesiredModulesRepo, DeviceModulesRepo, ModulesRepo
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.devices_repo import DevicesRepo
from websocket.protocol import enqueue_command_async
from config import SERVER_PUBLIC_BASE_URL, MODULES_STORAGE_DIR
from utils.module_manifest import get_module_manifest


async def reconcile_device(
    device_id: str,
    state: object,  # app state для enqueue_command_async
    session: Optional[AsyncSession] = None,
    reason: str = "periodic",
) -> dict:
    """
    Reconcile для одного устройства.
    
    Алгоритм:
    1. Загружаем desired state (device_desired_modules)
    2. Загружаем actual state (device_modules — только active)
    3. Для каждого desired=installed: если actual не active — enqueue install
    4. Для каждого desired=absent: если actual active — enqueue remove
    
    Returns:
        {"installs": int, "removes": int, "skipped": int, "operations": list}
    """
    stats = {"installs": 0, "removes": 0, "skipped": 0, "operations": []}

    async def _run(sess: AsyncSession) -> dict:
        desired_repo = DeviceDesiredModulesRepo(sess)
        actual_repo = DeviceModulesRepo(sess)
        modules_repo = ModulesRepo(sess)
        devices_repo = DevicesRepo(sess)
        audit_repo = AgentRuntimeAuditRepo(sess)

        async def _write_reconcile_failure(
            *,
            module_name: str,
            desired_version: Optional[str],
            error_kind: str,
            message: str,
            severity: str = "warning",
            operation_id: Optional[str] = None,
        ) -> None:
            await audit_repo.add(
                device_id=device_id,
                event_type="module_reconcile_failed",
                severity=severity,
                source="module_reconcile",
                operation_id=operation_id,
                actor_role="system",
                details_json={
                    "module_name": module_name,
                    "module_version": desired_version,
                    "stage": "reconcile",
                    "reason": reason,
                    "message": message,
                    "error_kind": error_kind,
                },
            )

        # Проверяем, что устройство существует
        device = await devices_repo.get_by_device_id(device_id)
        if not device:
            logger.warning(f"[reconcile] device_id={device_id} not found, skip")
            return stats

        desired_list = await desired_repo.get_desired(device_id)
        if not desired_list:
            return stats

        # Строим map actual: module_name -> {version, state, active}
        actual_list = await actual_repo.get_device_modules(device_id)
        actual_map: dict[str, object] = {}
        for mod in actual_list:
            if mod.active:
                actual_map[mod.module_name] = mod

        for desired in desired_list:
            module_name = desired.module_name
            desired_version = desired.desired_version

            if desired.state == "installed":
                current_actual = actual_map.get(module_name)

                # Если actual уже совпадает — пропускаем
                if current_actual and current_actual.version == desired_version and current_actual.active:
                    stats["skipped"] += 1
                    continue

                if not desired_version:
                    logger.warning(
                        f"[reconcile] desired=installed but no version: "
                        f"device={device_id} module={module_name}, skip"
                    )
                    await _write_reconcile_failure(
                        module_name=module_name,
                        desired_version=desired_version,
                        error_kind="MODULE_DESIRED_VERSION_MISSING",
                        message="desired=installed without desired_version",
                    )
                    stats["skipped"] += 1
                    continue

                # Ищем модуль в реестре сервера
                module = await modules_repo.get_module(module_name, desired_version)
                if not module:
                    logger.warning(
                        f"[reconcile] module {module_name}/{desired_version} not in server registry, skip"
                    )
                    await _write_reconcile_failure(
                        module_name=module_name,
                        desired_version=desired_version,
                        error_kind="MODULE_REGISTRY_MISSING",
                        message="module version is not present in server registry",
                    )
                    stats["skipped"] += 1
                    continue

                # Проверяем совместимость ОС
                full_path = MODULES_STORAGE_DIR / module.storage_path
                if not full_path.exists():
                    logger.error(
                        f"[reconcile] module archive missing on disk, skip: "
                        f"device={device_id} module={module_name}/{desired_version} "
                        f"storage_path={module.storage_path} full_path={full_path}"
                    )
                    await _write_reconcile_failure(
                        module_name=module_name,
                        desired_version=desired_version,
                        error_kind="MODULE_ARCHIVE_MISSING",
                        message=f"module archive missing: {module.storage_path}",
                        severity="error",
                    )
                    stats["skipped"] += 1
                    continue

                manifest = get_module_manifest(module)
                mod_platforms = manifest.get("platforms") or ["any"]
                if (
                    isinstance(mod_platforms, list)
                    and len(mod_platforms) > 0
                    and "any" not in [str(p).lower() for p in mod_platforms]
                ):
                    device_os = (device.os or "").strip().lower()
                    os_norm = device_os
                    if os_norm == "windows":
                        os_norm = "win32"
                    allowed = [str(p).lower() for p in mod_platforms]
                    if os_norm and os_norm not in allowed:
                        logger.warning(
                            f"[reconcile] OS mismatch: device={device_id} os={device_os} "
                            f"module={module_name} platforms={allowed}, skip"
                        )
                        await _write_reconcile_failure(
                            module_name=module_name,
                            desired_version=desired_version,
                            error_kind="MODULE_PLATFORM_MISMATCH",
                            message=f"device os {device_os} not in module platforms {allowed}",
                        )
                        stats["skipped"] += 1
                        continue

                download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{module_name}/{desired_version}/download"
                operation_id = str(uuid.uuid4())

                try:
                    await enqueue_command_async(
                        state=state,
                        device_id=device_id,
                        command="install_module_package",
                        params={
                            "module_name": module_name,
                            "module_version": desired_version,
                            "download_url": download_url,
                            "sha256": module.sha256,
                            "size": module.size,
                            "replace_if_different_sha": True,
                        },
                        actor_role="system",
                        operation_id=operation_id,
                    )
                    stats["installs"] += 1
                    stats["operations"].append(
                        {
                            "operation_id": operation_id,
                            "command": "install_module_package",
                            "module_name": module_name,
                            "module_version": desired_version,
                        }
                    )
                    logger.info(
                        f"[reconcile/{reason}] Enqueued install: device={device_id} "
                        f"module={module_name}@{desired_version} op={operation_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"[reconcile] Failed to enqueue install: device={device_id} "
                        f"module={module_name}@{desired_version}: {e}"
                    )
                    await _write_reconcile_failure(
                        module_name=module_name,
                        desired_version=desired_version,
                        error_kind="MODULE_RECONCILE_ENQUEUE_FAILED",
                        message=str(e),
                        severity="error",
                        operation_id=operation_id,
                    )
                    stats["skipped"] += 1

            elif desired.state == "absent":
                current_actual = actual_map.get(module_name)
                if not current_actual:
                    # Уже отсутствует — skip
                    stats["skipped"] += 1
                    continue

                operation_id = str(uuid.uuid4())
                try:
                    await enqueue_command_async(
                        state=state,
                        device_id=device_id,
                        command="remove_module",
                        params={"name": module_name},
                        actor_role="system",
                        operation_id=operation_id,
                    )
                    stats["removes"] += 1
                    stats["operations"].append(
                        {
                            "operation_id": operation_id,
                            "command": "remove_module",
                            "module_name": module_name,
                            "module_version": getattr(current_actual, "version", None),
                        }
                    )
                    logger.info(
                        f"[reconcile/{reason}] Enqueued remove: device={device_id} "
                        f"module={module_name} op={operation_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"[reconcile] Failed to enqueue remove: device={device_id} "
                        f"module={module_name}: {e}"
                    )
                    await _write_reconcile_failure(
                        module_name=module_name,
                        desired_version=getattr(current_actual, "version", None),
                        error_kind="MODULE_RECONCILE_ENQUEUE_FAILED",
                        message=str(e),
                        severity="error",
                        operation_id=operation_id,
                    )
                    stats["skipped"] += 1

        return stats

    if session is not None:
        return await _run(session)
    else:
        async with get_session() as sess:
            return await _run(sess)


async def reconcile_all_devices(state: object, reason: str = "periodic") -> dict:
    """
    Запускает reconcile для всех устройств с pending desired state.
    
    Используется периодическим планировщиком.
    Returns: суммарная статистика по всем устройствам.
    """
    total = {"installs": 0, "removes": 0, "skipped": 0, "devices": 0}

    try:
        async with get_session() as session:
            desired_repo = DeviceDesiredModulesRepo(session)
            all_desired = await desired_repo.get_all_installed_desired()

        # Уникальные device_id
        device_ids = list({d.device_id for d in all_desired})

        for device_id in device_ids:
            try:
                stats = await reconcile_device(device_id, state=state, reason=reason)
                total["installs"] += stats["installs"]
                total["removes"] += stats["removes"]
                total["skipped"] += stats["skipped"]
                total["devices"] += 1
            except Exception as e:
                logger.error(f"[reconcile_all] Error for device={device_id}: {e}")

        if total["devices"] > 0:
            logger.info(
                f"[reconcile_all/{reason}] Done: devices={total['devices']} "
                f"installs={total['installs']} removes={total['removes']} "
                f"skipped={total['skipped']}"
            )

    except Exception as e:
        logger.error(f"[reconcile_all] Fatal error: {e}", exc_info=True)

    return total


async def set_desired_installed(
    device_id: str,
    module_name: str,
    desired_version: str,
    desired_sha256: Optional[str] = None,
    reason: str = "manual",
    updated_by: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    """Устанавливает desired=installed для модуля на устройстве."""
    async def _run(sess: AsyncSession) -> None:
        repo = DeviceDesiredModulesRepo(sess)
        await repo.upsert_desired(
            device_id=device_id,
            module_name=module_name,
            desired_version=desired_version,
            desired_sha256=desired_sha256,
            state="installed",
            reason=reason,
            updated_by=updated_by,
        )

    if session is not None:
        await _run(session)
    else:
        async with get_session() as sess:
            await _run(sess)
            await sess.commit()


async def set_desired_absent(
    device_id: str,
    module_name: str,
    reason: str = "manual",
    updated_by: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> None:
    """Устанавливает desired=absent для модуля на устройстве."""
    async def _run(sess: AsyncSession) -> None:
        repo = DeviceDesiredModulesRepo(sess)
        await repo.upsert_desired(
            device_id=device_id,
            module_name=module_name,
            desired_version=None,
            desired_sha256=None,
            state="absent",
            reason=reason,
            updated_by=updated_by,
        )

    if session is not None:
        await _run(session)
    else:
        async with get_session() as sess:
            await _run(sess)
            await sess.commit()
