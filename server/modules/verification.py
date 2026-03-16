"""
Verification pipeline for module activation.
Дополнительно: run_tool smoke для каждого инструмента модуля, хранение результата (success/fail, код, duration).
"""
import asyncio
import time
from typing import Optional, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.repos import DeviceModulesRepo, ToolsetSnapshotsRepo


async def run_smoke_for_module_tools(
    state: Any,
    device_id: str,
    module_tools: List[Dict],
    timeout_per_tool: int = 15,
) -> List[Dict]:
    """
    Выполняет реальный run_tool smoke для каждого инструмента из списка.
    Возвращает список результатов: {tool, success, error_code?, duration_ms, device_id}.
    """
    from websocket.protocol import send_ws_command

    results = []
    for t in module_tools:
        tool_name = t.get("tool") or t.get("name")
        if not tool_name:
            continue
        start = time.perf_counter()
        try:
            response = await send_ws_command(
                state=state,
                device_id=device_id,
                command="run_tool",
                params={"tool_name": tool_name, "params": {}},
                actor_role="admin",
                timeout=timeout_per_tool,
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            payload = response.get("payload") or {}
            status = payload.get("status", "unknown")
            success = status == "success"
            error_code = payload.get("error_code") if not success else None
            results.append({
                "tool": tool_name,
                "success": success,
                "error_code": error_code,
                "duration_ms": duration_ms,
                "device_id": device_id,
            })
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            results.append({
                "tool": tool_name,
                "success": False,
                "error_code": getattr(e, "code", None) or "COMMAND_FAILED",
                "duration_ms": duration_ms,
                "device_id": device_id,
            })
            logger.warning(f"[verify_module] run_tool smoke failed for {tool_name}: {e}")
    return results


async def verify_module_activation(
    session: AsyncSession,
    device_id: str,
    module_name: str,
    version: str,
    timeout_seconds: int = 30,
    state: Optional[Any] = None,
    run_smoke: bool = True,
) -> Dict:
    """
    Проверяет работоспособность модуля после activation.
    Ждёт появления tools в snapshot; при state и run_smoke=True выполняет run_tool smoke
    для каждого инструмента и возвращает smoke_results (success/fail, код, duration, device_id, tool).

    Args:
        session: Database session
        device_id: ID устройства
        module_name: Имя модуля
        version: Версия модуля
        timeout_seconds: Максимальное время ожидания появления tools
        state: Опционально StateManager для вызова run_tool
        run_smoke: Если True и state задан — выполнить run_tool для каждого tool

    Returns:
        {
            "verified": bool,
            "tools_found": int,
            "error": Optional[str],
            "smoke_results": Optional[List[Dict]]  # {tool, success, error_code?, duration_ms, device_id}
        }
    """
    device_modules_repo = DeviceModulesRepo(session)
    snapshots_repo = ToolsetSnapshotsRepo(session)

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        module = await device_modules_repo.get_device_modules(device_id)
        module_found = None
        for m in module:
            if m.module_name == module_name and m.version == version:
                module_found = m
                break

        if not module_found or not module_found.active:
            await asyncio.sleep(1)
            continue

        latest_snapshot = await snapshots_repo.get_latest_snapshot(device_id)
        if latest_snapshot:
            tools_list = latest_snapshot.toolset_json.get("tools", [])
            module_tools = [t for t in tools_list if t.get("module") == module_name]

            if module_tools:
                out = {
                    "verified": True,
                    "tools_found": len(module_tools),
                    "error": None,
                    "smoke_results": None,
                }
                if state and run_smoke and module_tools:
                    out["smoke_results"] = await run_smoke_for_module_tools(
                        state=state,
                        device_id=device_id,
                        module_tools=module_tools,
                        timeout_per_tool=15,
                    )
                return out

        await asyncio.sleep(2)

    return {
        "verified": False,
        "tools_found": 0,
        "error": "Timeout waiting for tools_changed",
        "smoke_results": None,
    }


