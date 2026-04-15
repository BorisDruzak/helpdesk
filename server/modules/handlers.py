"""
HTTP обработчики для modules API (управление динамическими модулями).
"""

import asyncio
import base64
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from aiohttp import web
from loguru import logger
from sqlalchemy import select
from websocket.protocol import send_ws_command, enqueue_command_async
from config import AGENT_BUILTIN_MODULES, MODULES_STORAGE_DIR, MAX_MODULE_SIZE, SERVER_PUBLIC_BASE_URL
from utils.module_storage import save_module_zip_from_stream, save_module_zip_bytes, load_module_zip, stream_module_zip
from utils.module_preflight import apply_smoke_validation, preflight_module_zip
from utils.module_builder import build_module_package, DEFAULT_RISK_LEVEL
from utils.module_manifest import get_module_manifest, get_module_validation, module_to_api_record
from utils.versioning import version_key
from app.db import get_session
from app.repos import ModulesRepo, DeviceModulesRepo, ModuleRolloutRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.db.models import DeviceDesiredModule, DeviceModule, DownloadAudit
from auth.context import AuthContext
from core.policy_engine import PolicyEngine
from core.tool_metadata import ToolMetadata
from modules.reconcile import set_desired_installed, set_desired_absent
from modules.workbench_service import build_editable_spec, build_editable_spec_from_archive_bytes
try:
    from shared.tool_contracts import normalize_risk_level
except ModuleNotFoundError:  # pragma: no cover - defensive path for nested cwd entrypoints
    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from shared.tool_contracts import normalize_risk_level


async def handle_modules_ping(_request: web.Request) -> web.Response:
    """GET /api/modules/ping for module-prefix reachability checks."""
    return web.json_response({"status": "ok"})


def _flatten_validation_errors(validation_json: Optional[dict]) -> list[str]:
    if not isinstance(validation_json, dict):
        return []
    errors = validation_json.get("errors") or {}
    result: list[str] = []
    for section in ("manifest", "tools", "metadata", "smoke"):
        for item in errors.get(section, []) or []:
            result.append(f"{section}: {item}")
    return result


def _extract_tool_payload(response: object) -> dict:
    if isinstance(response, dict) and isinstance(response.get("payload"), dict):
        return response["payload"]
    return response if isinstance(response, dict) else {}


def _extract_observations(payload: dict) -> dict:
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("observations"), dict):
        return data["observations"]
    if isinstance(payload.get("observations"), dict):
        return payload["observations"]
    return {}


def _extract_active_version_from_observations(observations: dict) -> Optional[str]:
    active_version = observations.get("active_version")
    if isinstance(active_version, str) and active_version.strip():
        return active_version.strip()

    active_path = observations.get("active_path")
    if isinstance(active_path, str) and active_path.strip():
        active_name = Path(active_path).name.strip()
        if active_name:
            return active_name
    return None


def _manifest_tool_identifiers(manifest_json: Optional[dict]) -> Dict[str, str]:
    identifiers: Dict[str, str] = {}
    if not isinstance(manifest_json, dict):
        return identifiers
    for tool in manifest_json.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        canonical_name = str(tool.get("tool") or tool.get("name") or "").strip()
        if not canonical_name:
            continue
        identifiers.setdefault(canonical_name, canonical_name)
        for alias in tool.get("aliases") or []:
            alias_name = str(alias or "").strip()
            if alias_name:
                identifiers.setdefault(alias_name, canonical_name)
    return identifiers


async def _find_registry_tool_conflicts(session, manifest_json: Optional[dict]) -> list[dict]:
    if not isinstance(manifest_json, dict):
        return []
    incoming_module_name = str(manifest_json.get("module_name") or "").strip()
    if not incoming_module_name:
        return []
    incoming_identifiers = _manifest_tool_identifiers(manifest_json)
    if not incoming_identifiers:
        return []

    modules_repo = ModulesRepo(session)
    conflicts: list[dict] = []
    for existing in await modules_repo.list_modules(limit=1000):
        if existing.module_name == incoming_module_name:
            continue
        existing_manifest = get_module_manifest(existing)
        existing_identifiers = _manifest_tool_identifiers(existing_manifest)
        for identifier, incoming_owner in incoming_identifiers.items():
            existing_owner = existing_identifiers.get(identifier)
            if not existing_owner:
                continue
            conflicts.append(
                {
                    "identifier": identifier,
                    "incoming_tool": incoming_owner,
                    "existing_tool": existing_owner,
                    "existing_module_name": existing.module_name,
                    "existing_version": existing.version,
                }
            )
    return conflicts


def _module_archive_path(module: object) -> Path:
    return MODULES_STORAGE_DIR / str(getattr(module, "storage_path", "")).strip()


def _module_file_missing_payload(module_name: str, version: str, storage_path: str) -> dict:
    return {
        "status": "error",
        "error_code": "MODULE_FILE_MISSING",
        "error": f"Module file missing on server: {module_name}/{version}",
        "hint": "Re-upload the module package to the server registry before installing it on a device.",
        "storage_path": storage_path,
    }


def _module_storage_state(module: object) -> dict:
    archive_path = _module_archive_path(module)
    file_exists = archive_path.exists()
    return {
        "storage_path": str(getattr(module, "storage_path", "") or ""),
        "file_exists": file_exists,
        "file_missing": not file_exists,
    }


def _module_api_record(module: object, *, include_detail: bool = False) -> dict:
    record = module_to_api_record(module, include_detail=include_detail)
    record.update(_module_storage_state(module))
    return record


def _pick_preferred_module_record(modules: list[object], preferred_version: Optional[str]) -> Optional[object]:
    if not modules:
        return None
    if preferred_version:
        for module in modules:
            if str(getattr(module, "version", "")).strip() == preferred_version:
                return module
    return max(
        modules,
        key=lambda module: (
            version_key(getattr(module, "version", "")).key,
            getattr(module, "created_at", None) or datetime.fromtimestamp(0, tz=timezone.utc),
        ),
    )


async def _get_module_preferred_assignments(session) -> Dict[str, dict]:
    repo = ModuleRolloutRepo(session)
    assignments = await repo.list_assignments()
    return {item["module_name"]: item for item in assignments}


async def _get_module_rollout_settings(session) -> dict:
    repo = ModuleRolloutRepo(session)
    return await repo.get_settings()


async def _collect_module_rollout_target_device_ids(session, module_name: str) -> list[str]:
    desired_rows = await session.execute(
        select(DeviceDesiredModule.device_id).where(
            DeviceDesiredModule.module_name == module_name,
            DeviceDesiredModule.state == "installed",
        )
    )
    actual_rows = await session.execute(
        select(DeviceModule.device_id).where(
            DeviceModule.module_name == module_name,
            DeviceModule.installed.is_(True),
        )
    )
    device_ids = {
        str(device_id).strip()
        for (device_id,) in desired_rows.all() + actual_rows.all()
        if isinstance(device_id, str) and device_id.strip()
    }
    return sorted(device_ids)


async def _apply_module_preferred_rollout(
    *,
    session,
    state,
    module_name: str,
    version: str,
    updated_by: Optional[str],
    settings: dict,
) -> dict:
    mode = str(settings.get("preferred_version_rollout_mode") or "manual").strip().lower()
    should_sync = bool(settings.get("sync_after_preferred_change", True))
    if mode != "installed_devices":
        return {
            "mode": mode,
            "should_sync": should_sync,
            "desired_updates": 0,
            "sync_enqueued": 0,
            "device_ids": [],
        }

    modules_repo = ModulesRepo(session)
    module = await modules_repo.get_module(module_name, version)
    if not module:
        return {
            "mode": mode,
            "should_sync": should_sync,
            "desired_updates": 0,
            "sync_enqueued": 0,
            "device_ids": [],
        }

    device_ids = await _collect_module_rollout_target_device_ids(session, module_name)
    for device_id in device_ids:
        await set_desired_installed(
            device_id=device_id,
            module_name=module_name,
            desired_version=version,
            desired_sha256=module.sha256,
            reason="preferred_rollout",
            updated_by=updated_by,
            session=session,
        )

    return {
        "mode": mode,
        "should_sync": should_sync,
        "desired_updates": len(device_ids),
        "sync_enqueued": 0,
        "device_ids": device_ids,
    }


async def _finalize_module_preferred_rollout(
    *,
    state,
    updated_by: Optional[str],
    rollout_summary: Optional[dict],
) -> dict | None:
    if not isinstance(rollout_summary, dict):
        return rollout_summary
    device_ids = list(rollout_summary.get("device_ids") or [])
    if not rollout_summary.get("should_sync") or state is None or not device_ids:
        return rollout_summary

    from modules.reconcile import reconcile_device

    reconcile_enqueued = 0
    followup_refresh_enqueued = 0
    for device_id in device_ids:
        await reconcile_device(
            device_id=device_id,
            state=state,
            reason="preferred_rollout",
        )
        reconcile_enqueued += 1
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role=updated_by or "admin",
            require_online=False,
        )
        followup_refresh_enqueued += 1
    rollout_summary["sync_enqueued"] = reconcile_enqueued
    rollout_summary["refresh_enqueued"] = followup_refresh_enqueued
    return rollout_summary


async def _build_and_store_module_package(
    *,
    auth_context: AuthContext,
    payload: dict,
    app_state=None,
) -> tuple[int, dict]:
    status_code, response_payload, prepared = await _prepare_module_package_payload(payload)
    if prepared is None:
        return status_code, response_payload

    name_final = prepared["module_name"]
    version_final = prepared["version"]
    zip_bytes = prepared["zip_bytes"]
    manifest_json = prepared["manifest_json"]
    validation_json = prepared["validation_json"]
    manifest_summary = prepared["manifest_summary"]
    overwrite = prepared["overwrite"]
    set_preferred = prepared["set_preferred"]
    rollout_summary = None

    async with get_session() as session:
        modules_repo = ModulesRepo(session)
        tool_conflicts = await _find_registry_tool_conflicts(session, manifest_json)
        if tool_conflicts:
            return 409, {
                "status": "error",
                "error": "Tool ownership conflict",
                "error_code": "MODULE_TOOL_OWNERSHIP_CONFLICT",
                "conflicts": tool_conflicts,
                "module_name": name_final,
                "version": version_final,
            }
        existing = await modules_repo.get_module(name_final, version_final)
        if existing and not overwrite:
            return 409, {
                "status": "error",
                "error": "Module already exists",
                "module_name": name_final,
                "version": version_final,
            }
        if overwrite and auth_context.actor_role != "admin":
            return 403, {"status": "error", "error": "Only admin can overwrite modules"}

        storage_path, sha256, size = save_module_zip_bytes(
            zip_bytes=zip_bytes,
            module_name=name_final,
            version=version_final,
            storage_dir=MODULES_STORAGE_DIR,
            max_size=MAX_MODULE_SIZE,
        )
        if existing and overwrite:
            existing.sha256 = sha256
            existing.size = size
            existing.storage_path = storage_path
            existing.manifest_json = manifest_json
            existing.validation_json = validation_json
            existing.manifest_summary = manifest_summary
            await session.flush()
            logger.info(f"Module updated (create/save): {name_final}/{version_final}")
        else:
            await modules_repo.create_module(
                module_name=name_final,
                version=version_final,
                sha256=sha256,
                size=size,
                storage_path=storage_path,
                uploaded_by=auth_context.actor_role or "admin",
                manifest_json=manifest_json,
                validation_json=validation_json,
                manifest_summary=manifest_summary,
            )
            logger.info(f"Module created (create/save): {name_final}/{version_final}")

        if set_preferred:
            rollout_repo = ModuleRolloutRepo(session)
            await rollout_repo.set_assignment(
                module_name=name_final,
                version=version_final,
                updated_by=auth_context.actor_role,
            )
            rollout_settings = await _get_module_rollout_settings(session)
            rollout_summary = await _apply_module_preferred_rollout(
                session=session,
                state=app_state,
                module_name=name_final,
                version=version_final,
                updated_by=auth_context.actor_role,
                settings=rollout_settings,
            )
        await session.commit()
    rollout_summary = await _finalize_module_preferred_rollout(
        state=app_state,
        updated_by=auth_context.actor_role,
        rollout_summary=rollout_summary,
    )

    return 200, {
        "status": "success",
        "module_name": name_final,
        "version": version_final,
        "sha256": sha256,
        "size": size,
        "download_path": f"/api/modules/{name_final}/{version_final}/download",
        "preflight_status": "passed",
        "manifest_version": 1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version", 2),
        "validation_status": validation_json.get("validation_status"),
        "warnings": validation_json.get("warnings") or [],
        "tools_count": len((manifest_json or {}).get("tools") or []),
        "validation_json": validation_json,
        "preferred_version": version_final if set_preferred else None,
        "rollout_summary": rollout_summary,
    }


async def _prepare_module_package_payload(payload: dict) -> tuple[int, dict, dict | None]:
    module_name = (payload.get("module_name") or "").strip()
    version = (payload.get("version") or "").strip()
    tool_name = (payload.get("tool_name") or "").strip()
    method_name = (payload.get("method") or payload.get("method_name") or tool_name).strip()
    description = (payload.get("description") or "").strip()
    user_function_body = payload.get("user_function_body")
    if user_function_body is None:
        user_function_body = ""
    risk_level = (payload.get("risk_level") or DEFAULT_RISK_LEVEL).strip()
    overwrite = payload.get("overwrite") is True
    params_schema = payload.get("params_schema")
    presets = payload.get("presets")
    platforms = payload.get("platforms")
    capabilities = payload.get("capabilities")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    output_schema = payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else None
    aliases = payload.get("aliases") if isinstance(payload.get("aliases"), list) else None
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else None
    requirements = payload.get("requirements") if isinstance(payload.get("requirements"), list) else None
    optional_requirements = payload.get("optional_requirements") if isinstance(payload.get("optional_requirements"), list) else None
    min_agent_version = payload.get("min_agent_version")
    module_api_version = (payload.get("module_api_version") or "1.0.0").strip()
    owner_scope = (payload.get("owner_scope") or "core").strip().lower()
    entrypoint = (payload.get("entrypoint") or "module:register").strip()
    set_preferred = payload.get("set_preferred") is True

    if not module_name:
        return 400, {"status": "error", "error": "Missing module_name"}, None
    if not version:
        return 400, {"status": "error", "error": "Missing version"}, None
    if not tool_name and not tools:
        return 400, {"status": "error", "error": "Missing tool_name or tools"}, None
    if not description:
        return 400, {"status": "error", "error": "Missing description"}, None

    try:
        zip_bytes, manifest_summary = build_module_package(
            module_name=module_name,
            version=version,
            tool_name=tool_name,
            description=description,
            user_function_body=user_function_body,
            risk_level=risk_level,
            params_schema=params_schema if isinstance(params_schema, list) else None,
            presets=presets if isinstance(presets, list) else None,
            platforms=platforms if isinstance(platforms, list) else None,
            method_name=method_name,
            capabilities=capabilities if isinstance(capabilities, list) else None,
            metadata=metadata,
            output_schema=output_schema,
            aliases=aliases,
            tools=tools,
            requirements=requirements,
            optional_requirements=optional_requirements,
            min_agent_version=min_agent_version,
            module_api_version=module_api_version,
            owner_scope=owner_scope,
            entrypoint=entrypoint,
        )
    except ValueError as e:
        return 400, {"status": "error", "error": str(e)}, None

    preflight_ok, validation_json, manifest_json, _ = preflight_module_zip(zip_bytes)
    if not preflight_ok:
        return 400, {
            "status": "error",
            "error": "Module validation failed",
            "preflight_status": "failed",
            "preflight_errors": _flatten_validation_errors(validation_json),
            "validation_json": validation_json,
            "module_name": module_name,
            "version": version,
        }, None

    smoke_ok, smoke_result, smoke_errors = await _run_module_smoke(zip_bytes, "pc_create_smoke_")
    validation_json = apply_smoke_validation(manifest_json, validation_json, smoke_result)
    if not smoke_ok or validation_json.get("errors", {}).get("smoke"):
        return 400, {
            "status": "error",
            "error": "Module smoke check failed",
            "preflight_status": "failed",
            "preflight_errors": smoke_errors or _flatten_validation_errors(validation_json),
            "validation_json": validation_json,
            "module_name": manifest_json["module_name"],
            "version": manifest_json["module_version"],
        }, None

    manifest_summary = manifest_summary or {}
    manifest_summary["tools"] = (manifest_json or {}).get("tools") or manifest_summary.get("tools") or []
    return 200, {
        "status": "ok",
        "module_name": manifest_json["module_name"],
        "version": manifest_json["module_version"],
        "preflight_status": "passed",
        "validation_status": validation_json.get("validation_status"),
        "warnings": validation_json.get("warnings") or [],
        "tools_count": len((manifest_json or {}).get("tools") or []),
    }, {
        "module_name": manifest_json["module_name"],
        "version": manifest_json["module_version"],
        "zip_bytes": zip_bytes,
        "manifest_json": manifest_json,
        "validation_json": validation_json,
        "manifest_summary": manifest_summary,
        "overwrite": overwrite,
        "set_preferred": set_preferred,
    }


def _builtin_module_install_payload(module_name: str, version: str) -> dict:
    return {
        "status": "ok",
        "builtin": True,
        "module_name": module_name,
        "version": version,
        "message": (
            f"Module {module_name}/{version} is bundled with the agent and does not "
            "require server-side installation."
        ),
    }


async def _enqueue_module_followup_sync(
    *,
    state,
    device_id: str,
    actor_role: str = "admin",
    require_online: bool = False,
) -> dict:
    """
    Queue a lightweight inventory + toolset refresh after module operations.

    We deliberately enqueue the sync commands after the mutating command so the
    agent processes them in order and the server converges actual state without
    an extra manual "Sync modules" click in the UI.
    """
    modules_sync = await enqueue_command_async(
        state=state,
        device_id=device_id,
        command="list_installed_modules",
        params={},
        actor_role=actor_role,
        trace_id=None,
        require_online=require_online,
    )
    toolset_sync = await enqueue_command_async(
        state=state,
        device_id=device_id,
        command="list_tools",
        params={},
        actor_role=actor_role,
        trace_id=None,
        require_online=require_online,
    )
    return {
        "modules_sync": modules_sync,
        "toolset_sync": toolset_sync,
    }


def _module_auth_error_response() -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "Authentication required",
            "error_code": "AUTH_REQUIRED",
        },
        status=401,
    )


def _check_module_policy(
    *,
    auth_context: Optional[AuthContext],
    tool_name: str,
    risk_level: str,
) -> tuple[Optional[str], Optional[web.Response]]:
    if not auth_context:
        return None, _module_auth_error_response()
    metadata = ToolMetadata(
        risk_level=normalize_risk_level(risk_level),
        requires_consent=False,
        allow_roles=None,
    )
    decision = PolicyEngine().check_policy(
        actor_role=auth_context.actor_role,
        tool_name=tool_name,
        metadata=metadata,
    )
    if not decision.allow:
        return None, web.json_response(
            {
                "status": "error",
                "error": "Policy violation",
                "error_code": decision.reason,
                "required_role": decision.required_role,
            },
            status=403,
        )
    return auth_context.actor_role, None


async def _run_module_smoke(zip_bytes: bytes, smoke_prefix: str) -> tuple[bool, Optional[dict], list[str]]:
    project_root = Path(__file__).resolve().parent.parent.parent
    smoke_script = project_root / "pc_agent" / "scripts" / "smoke_check_module.py"
    temp_extract = Path(tempfile.mkdtemp(prefix=smoke_prefix))
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(temp_extract)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(smoke_script),
            "--dir",
            str(temp_extract),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env={**os.environ, "PYTHONPATH": str(project_root)},
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False, None, ["smoke: Smoke check timed out (60s)"]
        if proc.returncode != 0:
            err_msg = (stderr_bytes.decode("utf-8", errors="replace") or "Smoke check failed").strip()
            if len(err_msg) > 500:
                err_msg = err_msg[:497] + "..."
            return False, None, [f"smoke: Smoke check failed: {err_msg}"]
        smoke_result = {}
        if stdout_bytes:
            smoke_result = json.loads(stdout_bytes.decode("utf-8", errors="replace").strip() or "{}")
        return True, smoke_result, []
    except Exception as exc:
        logger.exception(exc)
        return False, None, [f"smoke: Smoke check error: {exc}"]
    finally:
        shutil.rmtree(temp_extract, ignore_errors=True)


async def handle_install_module_package(request):
    """
    Legacy endpoint: POST /api/install_module_package
    
    Для обратной совместимости:
    1. Если модуль уже загружен (по sha256) → использует download_url
    2. Иначе → сохраняет на диск, затем использует download_url
    3. Fallback: если download_url не работает, использует package_b64
    
    КРИТИЧНО: Должен возвращать operation_id для единообразия с новым API.
    Сохраняет старые поля в response для совместимости со старыми клиентами.
    
    Поля формы:
    - device_id: string (обязательно)
    - name: string (обязательно) - имя модуля
    - version: string (обязательно) - версия модуля
    - actor_role: string (optional, default "admin")
    - sha256: string (optional) - ожидаемый хэш для проверки
    - file: бинарный ZIP (обязательно) - архив модуля
    """
    try:
        state = request.app['state']
        
        logger.info("[SERVER] install_module_package (legacy) RX")
        
        # Читаем multipart/form-data
        reader = await request.multipart()
        
        device_id = None
        name = None
        version = None
        actor_role = "admin"
        expected_sha256 = None
        file_field = None
        
        async for field in reader:
            if field.name == "device_id":
                device_id = (await field.read()).decode('utf-8').strip()
            elif field.name == "name":
                name = (await field.read()).decode('utf-8').strip()
            elif field.name == "version":
                version = (await field.read()).decode('utf-8').strip()
            elif field.name == "actor_role":
                actor_role = (await field.read()).decode('utf-8').strip()
            elif field.name == "sha256":
                expected_sha256 = (await field.read()).decode('utf-8').strip()
            elif field.name == "file":
                file_field = field
        
        # Проверка обязательных полей
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)

        if not file_field:
            return web.json_response({
                "status": "error",
                "error": "Missing file"
            }, status=400)
        
        logger.info(f"[SERVER] install_module_package (legacy) RX device_id={device_id} name={name} version={version}")
        
        # Проверка подключения агента
        if not state.is_agent_online(device_id):
            logger.warning(f"[SERVER] install_module_package agent {device_id} not connected")
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        # Создаем async iterator для stream
        async def file_stream():
            while True:
                chunk = await file_field.read_chunk()
                if not chunk:
                    break
                yield chunk
        
        # Сохраняем на диск (streaming + sha256)
        storage_path, computed_sha256, size = await save_module_zip_from_stream(
            stream=file_stream(),
            module_name=name,
            version=version,
            storage_dir=MODULES_STORAGE_DIR,
            max_size=MAX_MODULE_SIZE
        )
        
        logger.info(f"[SERVER] computed sha256={computed_sha256}")
        
        # Проверка ожидаемого хэша, если был передан
        if expected_sha256 and expected_sha256 != computed_sha256:
            logger.error(f"[SERVER] install_module_package HASH_MISMATCH expected={expected_sha256} computed={computed_sha256}")
            return web.json_response({
                "status": "error",
                "error": "HASH_MISMATCH",
                "expected_sha256": expected_sha256,
                "computed_sha256": computed_sha256
            }, status=400)
        
        # Проверяем, есть ли модуль в БД (по sha256)
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            existing_module = await modules_repo.get_module_by_sha256(computed_sha256)
            
            if not existing_module:
                # Создаем новую запись в БД
                await modules_repo.create_module(
                    module_name=name,
                    version=version,
                    sha256=computed_sha256,
                    size=size,
                    storage_path=storage_path,
                    uploaded_by=actor_role,
                    manifest_summary=None
                )
                await session.commit()
                logger.info(f"Module created: {name}/{version}")
            else:
                logger.info(f"Module already exists: {existing_module.module_name}/{existing_module.version}")
        
        # Построить download_url на основе SERVER_PUBLIC_BASE_URL
        download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{name}/{version}/download"
        
        # Enqueue install_module_package через enqueue_command_async (fire-and-forget)
        command_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="install_module_package",
            params={
                "module_name": name,
                "module_version": version,
                "download_url": download_url,
                "sha256": computed_sha256,
                "size": size,
                "package_b64": None  # Опционально, для fallback
            },
            actor_role=actor_role
        )
        
        # Возвращаем результат с operation_id (НОВОЕ поле) и старыми полями для совместимости
        return web.json_response({
            "status": "success",
            "operation_id": command_id,  # НОВОЕ поле
            "request_id": command_id,  # Старое поле (для совместимости)
            "sha256": computed_sha256,
            "bytes_len": size
        })
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки install_module_package: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_list_installed_modules(request):
    """
    API эндпоинт для получения списка установленных модулей: POST /api/list_installed_modules
    
    POST JSON:
    { "device_id": "...", "actor_role": "admin" }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="list_installed_modules",
            risk_level="safe_read",
        )
        if error_response:
            return error_response

        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        if "actor_role" in data:
            logger.warning(
                f"[handle_list_installed_modules] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] list_installed_modules device_id={device_id}")
        
        res = await send_ws_command(state=state, device_id=device_id, command="list_installed_modules", params={}, actor_role=actor_role)
        
        # Возвращаем payload из command_result
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды list_installed_modules")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки list_installed_modules: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_activate_module(request):
    """
    API эндпоинт для активации модуля: POST /api/activate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "version": "0.1.0", "actor_role": "admin" }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="activate_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        version = data.get("version")
        if "actor_role" in data:
            logger.warning(
                f"[handle_activate_module] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        logger.info(f"[SERVER] activate_module device_id={device_id} name={name} version={version}")
        
        params = {"name": name, "version": version}
        res = await send_ws_command(state=state, device_id=device_id, command="activate_module", params=params, actor_role=actor_role)
        
        # Возвращаем полный результат
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды activate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки activate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_rollback_module(request):
    """
    API эндпоинт для отката модуля: POST /api/rollback_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="rollback_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        if "actor_role" in data:
            logger.warning(
                f"[handle_rollback_module] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        logger.info(f"[SERVER] rollback_module device_id={device_id} name={name}")

        params = {"name": name}
        res = await send_ws_command(
            state=state,
            device_id=device_id,
            command="rollback_module",
            params=params,
            actor_role=actor_role,
        )

        payload = _extract_tool_payload(res)
        observations = _extract_observations(payload)
        rolled_back_version = _extract_active_version_from_observations(observations)
        payload_status = str(payload.get("status") or "").lower()

        if payload_status in {"ok", "success"} and rolled_back_version:
            try:
                async with get_session() as session:
                    modules_repo = ModulesRepo(session)
                    module = await modules_repo.get_module(name, rolled_back_version)
                    await set_desired_installed(
                        device_id=device_id,
                        module_name=name,
                        desired_version=rolled_back_version,
                        desired_sha256=module.sha256 if module else None,
                        reason="manual_rollback",
                        updated_by=actor_role,
                        session=session,
                    )
                    await session.commit()
            except Exception as desired_e:
                logger.warning(
                    f"[rollback_module] Failed to update desired state for "
                    f"{device_id}:{name}@{rolled_back_version}: {desired_e}"
                )
            try:
                await _enqueue_module_followup_sync(
                    state=state,
                    device_id=device_id,
                    actor_role=actor_role,
                    require_online=False,
                )
            except Exception as sync_err:
                logger.warning(
                    f"[rollback_module] Failed to enqueue follow-up sync for "
                    f"{device_id}: {sync_err}"
                )

        return web.json_response(payload or res)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды rollback_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки rollback_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_deactivate_module(request):
    """
    API эндпоинт для деактивации модуля: POST /api/deactivate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="deactivate_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        if "actor_role" in data:
            logger.warning(
                f"[handle_deactivate_module] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not name:
            return web.json_response({
                "status": "error",
                "error": "Missing name"
            }, status=400)
        
        logger.info(f"[SERVER] deactivate_module device_id={device_id} name={name}")
        
        params = {"name": name}
        res = await send_ws_command(state=state, device_id=device_id, command="deactivate_module", params=params, actor_role=actor_role)
        
        # Возвращаем полный результат
        if isinstance(res, dict) and "payload" in res:
            return web.json_response(res["payload"])
        else:
            return web.json_response(res)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except asyncio.TimeoutError:
        logger.error(f"⏱️  Таймаут команды deactivate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки deactivate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_smoke_install_and_run(request):
    """
    Устаревший эндпоинт: на агенте нет команды smoke_install_and_run.
    Использовать: POST /api/devices/{device_id}/modules/install и run_tool для smoke.
    """
    return web.json_response({
        "status": "error",
        "error": "Endpoint deprecated. Agent has no command smoke_install_and_run. "
                 "Use POST /api/devices/{device_id}/modules/install and run_tool for smoke.",
        "deprecated": True,
        "alternative": "POST /api/devices/{device_id}/modules/install then run_tool"
    }, status=410)


async def handle_upload_module(request):
    """
    POST /api/modules/upload
    
    Загружает модуль на сервер (сохраняет ZIP на диск и в БД).
    
    КРИТИЧНО: Использует потоковую запись из multipart stream, не держит весь ZIP в памяти.
    
    Multipart fields:
    - file: ZIP файл (обязательно, streaming read)
    - module_name: string (обязательно)
    - version: string (обязательно)
    - actor_role: string (optional, default "admin")
    - overwrite: string (optional, "true"/"false", default "false") - разрешить перезалив существующего (module_name, version)
    
    Returns:
        200 OK: {
            "status": "success",
            "module_name": "...",
            "version": "...",
            "sha256": "...",
            "size": 12345,
            "download_path": "/api/modules/{name}/{version}/download"
        }
        
        409 Conflict: {
            "status": "error",
            "error": "Module already exists",
            "module_name": "...",
            "version": "..."
        }
    """
    try:
        # Читаем multipart/form-data
        reader = await request.multipart()
        
        module_name = None
        version = None
        actor_role = "admin"
        overwrite = False
        file_field = None
        
        # КРИТИЧНО: Нужно читать файл прямо в цикле, а не сохранять field для чтения после
        # В aiohttp multipart field нельзя читать после завершения цикла async for
        file_chunks = []
        
        async for field in reader:
            if field.name == "module_name":
                module_name = (await field.read()).decode('utf-8').strip()
            elif field.name == "version":
                version = (await field.read()).decode('utf-8').strip()
            elif field.name == "actor_role":
                actor_role = (await field.read()).decode('utf-8').strip()
            elif field.name == "overwrite":
                overwrite_str = (await field.read()).decode('utf-8').strip()
                overwrite = overwrite_str.lower() == "true"
            elif field.name == "file":
                # КРИТИЧНО: Читаем файл прямо здесь, в цикле!
                file_field = field
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    file_chunks.append(chunk)
        
        # Проверка обязательных полей
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        if not file_field:
            return web.json_response({
                "status": "error",
                "error": "Missing file"
            }, status=400)
        
        zip_bytes = b"".join(file_chunks)
        preflight_ok, validation_json, manifest_json, manifest_summary = preflight_module_zip(zip_bytes)
        if not preflight_ok:
            preflight_errors = _flatten_validation_errors(validation_json)
            logger.warning(f"Upload module preflight failed: {preflight_errors}")
            return web.json_response({
                "status": "error",
                "error": "Module validation failed",
                "preflight_status": "failed",
                "preflight_errors": preflight_errors,
                "validation_json": validation_json,
                "module_name": module_name or "",
                "version": version or "",
            }, status=400)

        smoke_ok, smoke_result, smoke_errors = await _run_module_smoke(zip_bytes, "pc_upload_smoke_")
        validation_json = apply_smoke_validation(manifest_json, validation_json, smoke_result)
        if not smoke_ok or validation_json.get("errors", {}).get("smoke"):
            preflight_errors = smoke_errors or _flatten_validation_errors(validation_json)
            logger.warning(f"Upload module smoke check failed: {preflight_errors}")
            return web.json_response({
                "status": "error",
                "error": "Module smoke check failed",
                "preflight_status": "failed",
                "preflight_errors": preflight_errors,
                "validation_json": validation_json,
                "module_name": (manifest_json or {}).get("module_name", module_name or ""),
                "version": (manifest_json or {}).get("module_version", version or ""),
            }, status=400)

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            manifest_name = manifest_json["module_name"]
            manifest_version = manifest_json["module_version"]
            tool_conflicts = await _find_registry_tool_conflicts(session, manifest_json)
            if tool_conflicts:
                return web.json_response({
                    "status": "error",
                    "error": "Tool ownership conflict",
                    "error_code": "MODULE_TOOL_OWNERSHIP_CONFLICT",
                    "conflicts": tool_conflicts,
                    "module_name": manifest_name,
                    "version": manifest_version,
                }, status=409)
            existing = await modules_repo.get_module(manifest_name, manifest_version)

            if existing and not overwrite:
                return web.json_response({
                    "status": "error",
                    "error": "Module already exists",
                    "module_name": manifest_name,
                    "version": manifest_version
                }, status=409)

            if overwrite and actor_role != "admin":
                return web.json_response({
                    "status": "error",
                    "error": "Only admin can overwrite modules"
                }, status=403)

            async def file_stream():
                for chunk in file_chunks:
                    yield chunk

            storage_path, sha256, size = await save_module_zip_from_stream(
                stream=file_stream(),
                module_name=manifest_name,
                version=manifest_version,
                storage_dir=MODULES_STORAGE_DIR,
                max_size=MAX_MODULE_SIZE
            )

            full_path = MODULES_STORAGE_DIR / storage_path
            if not full_path.exists() or full_path.stat().st_size == 0:
                logger.error(f"Module file was not saved correctly: {full_path} (size={full_path.stat().st_size if full_path.exists() else 0})")
                raise ValueError(f"Module file was not saved correctly: {storage_path}")

            if existing and overwrite:
                existing.sha256 = sha256
                existing.size = size
                existing.storage_path = storage_path
                existing.manifest_json = manifest_json
                existing.validation_json = validation_json
                existing.manifest_summary = manifest_summary
                await session.commit()
                logger.info(f"Module updated: {manifest_name}/{manifest_version}")
            else:
                await modules_repo.create_module(
                    module_name=manifest_name,
                    version=manifest_version,
                    sha256=sha256,
                    size=size,
                    storage_path=storage_path,
                    uploaded_by=actor_role,
                    manifest_json=manifest_json,
                    validation_json=validation_json,
                    manifest_summary=manifest_summary,
                )
                await session.commit()
                logger.info(f"Module created: {manifest_name}/{manifest_version}")

        download_path = f"/api/modules/{manifest_json['module_name']}/{manifest_json['module_version']}/download"

        return web.json_response({
            "status": "success",
            "module_name": manifest_json["module_name"],
            "version": manifest_json["module_version"],
            "sha256": sha256,
            "size": size,
            "download_path": download_path,
            "preflight_status": "passed",
            "manifest_version": 1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version", 2),
            "validation_status": validation_json.get("validation_status"),
            "warnings": validation_json.get("warnings") or [],
            "tools_count": len((manifest_json or {}).get("tools") or []),
            "validation_json": validation_json,
        })

    except ValueError as e:
        logger.error(f"Upload module error: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=400)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки upload_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_create_module(request):
    """
    POST /api/modules/create

    Создаёт модуль из «только кода функции»: подставляет код в единый шаблон,
    собирает manifest.json + module.py, прогоняет preflight и smoke, сохраняет ZIP и запись в БД.
    Доступно из веб-формы и из API (установка через терминал без веб-панели).

    JSON body:
    - module_name (обязательно)
    - version (обязательно)
    - tool_name (обязательно для single-tool legacy create)
    - tools (опционально, список typed tool definitions для multi-tool module)
    - description (обязательно)
    - user_function_body (обязательно, тело async-функции)
    - risk_level (опционально: safe_readonly | safe_write | dangerous, default safe_readonly)
    - overwrite (опционально, default false)

    Returns: как POST /api/modules/upload (200 + status/success, 400 с preflight_errors, 409 conflict).
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
            }, status=401)

        data = await request.json()
        module_name = (data.get("module_name") or "").strip()
        version = (data.get("version") or "").strip()
        tool_name = (data.get("tool_name") or "").strip()
        method_name = (data.get("method") or data.get("method_name") or tool_name).strip()
        description = (data.get("description") or "").strip()
        user_function_body = data.get("user_function_body")
        if user_function_body is None:
            user_function_body = ""
        risk_level = (data.get("risk_level") or DEFAULT_RISK_LEVEL).strip()
        overwrite = data.get("overwrite") is True
        params_schema = data.get("params_schema")
        presets = data.get("presets")
        platforms = data.get("platforms")
        capabilities = data.get("capabilities")
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        output_schema = data.get("output_schema") if isinstance(data.get("output_schema"), dict) else None
        aliases = data.get("aliases") if isinstance(data.get("aliases"), list) else None
        tools = data.get("tools") if isinstance(data.get("tools"), list) else None
        requirements = data.get("requirements") if isinstance(data.get("requirements"), list) else None
        optional_requirements = data.get("optional_requirements") if isinstance(data.get("optional_requirements"), list) else None
        min_agent_version = data.get("min_agent_version")

        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name",
            }, status=400)
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version",
            }, status=400)
        if not tool_name and not tools:
            return web.json_response({
                "status": "error",
                "error": "Missing tool_name or tools",
            }, status=400)
        if not description:
            return web.json_response({
                "status": "error",
                "error": "Missing description",
            }, status=400)

        try:
            zip_bytes, manifest_summary = build_module_package(
                module_name=module_name,
                version=version,
                tool_name=tool_name,
                description=description,
                user_function_body=user_function_body,
                risk_level=risk_level,
                params_schema=params_schema if isinstance(params_schema, list) else None,
                presets=presets if isinstance(presets, list) else None,
                platforms=platforms if isinstance(platforms, list) else None,
                method_name=method_name,
                capabilities=capabilities if isinstance(capabilities, list) else None,
                metadata=metadata,
                output_schema=output_schema,
                aliases=aliases,
                tools=tools,
                requirements=requirements,
                optional_requirements=optional_requirements,
                min_agent_version=min_agent_version,
            )
        except ValueError as e:
            return web.json_response({
                "status": "error",
                "error": str(e),
            }, status=400)

        preflight_ok, validation_json, manifest_json, _ = preflight_module_zip(zip_bytes)
        if not preflight_ok:
            return web.json_response({
                "status": "error",
                "error": "Module validation failed",
                "preflight_status": "failed",
                "preflight_errors": _flatten_validation_errors(validation_json),
                "validation_json": validation_json,
                "module_name": module_name,
                "version": version,
            }, status=400)

        smoke_ok, smoke_result, smoke_errors = await _run_module_smoke(zip_bytes, "pc_create_smoke_")
        validation_json = apply_smoke_validation(manifest_json, validation_json, smoke_result)
        if not smoke_ok or validation_json.get("errors", {}).get("smoke"):
            return web.json_response({
                "status": "error",
                "error": "Module smoke check failed",
                "preflight_status": "failed",
                "preflight_errors": smoke_errors or _flatten_validation_errors(validation_json),
                "validation_json": validation_json,
                "module_name": manifest_json["module_name"],
                "version": manifest_json["module_version"],
            }, status=400)

        manifest_summary = manifest_summary or {}
        manifest_summary["tools"] = (manifest_json or {}).get("tools") or manifest_summary.get("tools") or []

        name_final = manifest_json["module_name"]
        version_final = manifest_json["module_version"]

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            tool_conflicts = await _find_registry_tool_conflicts(session, manifest_json)
            if tool_conflicts:
                return web.json_response({
                    "status": "error",
                    "error": "Tool ownership conflict",
                    "error_code": "MODULE_TOOL_OWNERSHIP_CONFLICT",
                    "conflicts": tool_conflicts,
                    "module_name": name_final,
                    "version": version_final,
                }, status=409)
            existing = await modules_repo.get_module(name_final, version_final)
            if existing and not overwrite:
                return web.json_response({
                    "status": "error",
                    "error": "Module already exists",
                    "module_name": name_final,
                    "version": version_final,
                }, status=409)
            if overwrite and auth_context.actor_role != "admin":
                return web.json_response({
                    "status": "error",
                    "error": "Only admin can overwrite modules",
                }, status=403)

            storage_path, sha256, size = save_module_zip_bytes(
                zip_bytes=zip_bytes,
                module_name=name_final,
                version=version_final,
                storage_dir=MODULES_STORAGE_DIR,
                max_size=MAX_MODULE_SIZE,
            )
            if existing and overwrite:
                existing.sha256 = sha256
                existing.size = size
                existing.storage_path = storage_path
                existing.manifest_json = manifest_json
                existing.validation_json = validation_json
                existing.manifest_summary = manifest_summary
                await session.commit()
                logger.info(f"Module updated (create): {name_final}/{version_final}")
            else:
                await modules_repo.create_module(
                    module_name=name_final,
                    version=version_final,
                    sha256=sha256,
                    size=size,
                    storage_path=storage_path,
                    uploaded_by=auth_context.actor_role or "admin",
                    manifest_json=manifest_json,
                    validation_json=validation_json,
                    manifest_summary=manifest_summary,
                )
                await session.commit()
                logger.info(f"Module created (create): {name_final}/{version_final}")

        download_path = f"/api/modules/{name_final}/{version_final}/download"
        return web.json_response({
            "status": "success",
            "module_name": name_final,
            "version": version_final,
            "sha256": sha256,
            "size": size,
            "download_path": download_path,
            "preflight_status": "passed",
            "manifest_version": 1 if validation_json.get("legacy_manifest") else manifest_json.get("manifest_version", 2),
            "validation_status": validation_json.get("validation_status"),
            "warnings": validation_json.get("warnings") or [],
            "tools_count": len((manifest_json or {}).get("tools") or []),
            "validation_json": validation_json,
        })

    except Exception as e:
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e),
        }, status=500)


async def handle_download_module(request):
    """
    GET /api/modules/{module_name}/{version}/download
    
    Скачивает ZIP модуля (streaming).
    
    Phase 6: Требует аутентификации через Authorization header (Bearer token).
    Query param ?token= поддерживается как fallback (с warning в логах).
    Все скачивания логируются в download_audit для аудита.
    
    КРИТИЧНО: Использует aiohttp.web.FileResponse (самый быстрый) или StreamResponse.
    Добавляет ETag (sha256) и Cache-Control для корректного кеширования.
    
    Returns:
        200 OK: ZIP file (streaming, application/zip)
            Headers:
            - Content-Type: application/zip
            - Content-Disposition: attachment; filename="{module_name}-{version}.zip"
            - Content-Length: size
            - ETag: "{sha256}"  # Для conditional requests
            - Cache-Control: no-store  # Пока не используем кеш (можно изменить на public, max-age=...)
        401: Authentication required
        404: Module not found
        304: Not Modified (если If-None-Match header совпадает с ETag)
    """
    try:
        # Phase 6: Получаем AuthContext из middleware (уже проверен)
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            # Это не должно произойти, если middleware работает правильно
            logger.error(
                f"[DownloadModule] AuthContext not found in request: module={request.match_info.get('module_name')}, "
                f"version={request.match_info.get('version')}"
            )
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        module_name = request.match_info["module_name"]
        version = request.match_info["version"]
        
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            module = await modules_repo.get_module(module_name, version)
            
            if not module:
                return web.json_response({
                    "status": "error",
                    "error": "Module not found"
                }, status=404)
            
            # Проверка существования файла на диске
            full_path = _module_archive_path(module)
            if not full_path.exists():
                logger.error(
                    f"[DownloadModule] Module archive missing on disk: "
                    f"module={module_name}/{version} storage_path={module.storage_path} full_path={full_path}"
                )
                return web.json_response(
                    _module_file_missing_payload(module_name, version, module.storage_path),
                    status=409,
                )
            
            # Проверка If-None-Match (ETag)
            if_none_match = request.headers.get("If-None-Match", "").strip('"')
            if if_none_match == module.sha256:
                return web.Response(status=304)  # Not Modified
            
            # Phase 6: Audit logging - логируем скачивание
            try:
                # Получаем токен из auth_context
                token = auth_context.token
                if token:
                    # Хешируем токен для безопасности
                    token_hash = AuthTokensRepo.hash_token(token)
                    token_prefix = AuthTokensRepo.get_token_prefix(token)
                    
                    # Получаем IP адрес и user agent
                    ip_address = request.remote
                    user_agent = request.headers.get("User-Agent")
                    
                    # Создаем запись в audit log
                    audit_record = DownloadAudit(
                        token_hash=token_hash,
                        token_prefix=token_prefix,
                        module_name=module_name,
                        version=version,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    session.add(audit_record)
                    await session.commit()
                    
                    logger.info(
                        f"[DownloadModule] Download logged: module={module_name}, "
                        f"version={version}, actor_id={auth_context.actor_id}, "
                        f"actor_role={auth_context.actor_role}, token_prefix={token_prefix}"
                    )
            except Exception as audit_error:
                # Не прерываем скачивание при ошибке аудита, но логируем
                logger.error(f"[DownloadModule] Audit logging failed: {audit_error}")
                logger.exception(audit_error)
            
            # Используем FileResponse для эффективной отдачи файла
            # КРИТИЧНО: FileResponse принимает str или Path, но лучше использовать str
            response = web.FileResponse(
                str(full_path),
                headers={
                    "Content-Type": "application/zip",
                    "Content-Disposition": f'attachment; filename="{module_name}-{version}.zip"',
                    "ETag": f'"{module.sha256}"',
                    "Cache-Control": "no-store"
                }
            )
            
            return response
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки download_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_list_modules(request):
    """
    GET /api/modules?module_name=...
    """
    try:
        module_name = request.query.get("module_name")
        limit = int(request.query.get("limit", 100))

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            preferred_assignments = await _get_module_preferred_assignments(session)
            modules = await modules_repo.list_modules(
                module_name=module_name,
                limit=limit
            )

            return web.json_response({
                "modules": [
                    {
                        **_module_api_record(module),
                        "is_preferred": preferred_assignments.get(module.module_name, {}).get("version") == module.version,
                        "preferred_version": preferred_assignments.get(module.module_name, {}).get("version"),
                    }
                    for module in modules
                ]
            })

    except Exception as e:
        logger.error(f"List modules failed: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_module_detail(request):
    """
    GET /api/modules/{module_name}/{version}
    """
    try:
        module_name = request.match_info["module_name"]
        version = request.match_info["version"]

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            preferred_assignments = await _get_module_preferred_assignments(session)
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response({
                    "status": "error",
                    "error": "Module not found",
                    "module_name": module_name,
                    "version": version,
                }, status=404)
            return web.json_response({
                "status": "ok",
                **_module_api_record(module, include_detail=True),
                "is_preferred": preferred_assignments.get(module.module_name, {}).get("version") == module.version,
                "preferred_version": preferred_assignments.get(module.module_name, {}).get("version"),
            })
    except Exception as e:
        logger.error(f"Get module detail failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_list_modules_workbench(request):
    """
    GET /api/modules/workbench

    Returns module families grouped by module_name with preferred-version metadata.
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()

        limit = int(request.query.get("limit", 300))
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            modules = await modules_repo.list_modules(limit=limit)
            preferred_assignments = await _get_module_preferred_assignments(session)
            rollout_settings = await _get_module_rollout_settings(session)

        grouped: Dict[str, list[object]] = {}
        for module in modules:
            grouped.setdefault(module.module_name, []).append(module)

        families: list[dict] = []
        for module_name in sorted(grouped):
            versions = grouped[module_name]
            preferred_version = preferred_assignments.get(module_name, {}).get("version")
            preferred_active = any(item.version == preferred_version for item in versions)
            preferred_module = _pick_preferred_module_record(versions, preferred_version)
            version_records = []
            for module in sorted(
                versions,
                key=lambda item: (
                    version_key(getattr(item, "version", "")).key,
                    getattr(item, "created_at", None) or datetime.fromtimestamp(0, tz=timezone.utc),
                ),
                reverse=True,
            ):
                manifest = get_module_manifest(module)
                version_records.append(
                    {
                        **_module_api_record(module),
                        "is_preferred": preferred_version == module.version,
                        "tool_ids": [tool.get("tool") for tool in manifest.get("tools") or [] if tool.get("tool")],
                    }
                )
            latest = version_records[0] if version_records else None
            families.append(
                {
                    "module_name": module_name,
                    "preferred_version": preferred_version if preferred_active else (preferred_module.version if preferred_module else None),
                    "preferred_assigned": bool(preferred_version and preferred_active),
                    "latest_version": latest.get("version") if latest else None,
                    "owner_scope": (get_module_manifest(preferred_module).get("owner_scope") if preferred_module else None),
                    "module_api_version": (get_module_manifest(preferred_module).get("module_api_version") if preferred_module else None),
                    "versions": version_records,
                }
            )

        return web.json_response(
            {
                "status": "ok",
                "modules": families,
                "count": len(families),
                "rollout_settings": rollout_settings,
            }
        )
    except Exception as e:
        logger.error(f"List modules workbench failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_get_module_workbench_detail(request):
    """
    GET /api/modules/workbench/{module_name}/{version}
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()

        module_name = request.match_info["module_name"]
        version = request.match_info["version"]
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            preferred_assignments = await _get_module_preferred_assignments(session)
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Module not found",
                        "module_name": module_name,
                        "version": version,
                    },
                    status=404,
                )
            editable_spec = build_editable_spec(module)
            return web.json_response(
                {
                    "status": "ok",
                    "module": {
                        **_module_api_record(module, include_detail=True),
                        "is_preferred": preferred_assignments.get(module.module_name, {}).get("version") == module.version,
                        "preferred_version": preferred_assignments.get(module.module_name, {}).get("version"),
                    },
                    "editable_spec": editable_spec,
                }
            )
    except Exception as e:
        logger.error(f"Get module workbench detail failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_get_module_rollout_settings(request):
    """GET /api/modules/rollout_settings."""
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()
        async with get_session() as session:
            rollout_settings = await _get_module_rollout_settings(session)
        return web.json_response({"status": "ok", "rollout_settings": rollout_settings})
    except Exception as e:
        logger.error(f"Get module rollout settings failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_patch_module_rollout_settings(request):
    """PATCH /api/modules/rollout_settings."""
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()
        if auth_context.actor_role != "admin":
            return web.json_response(
                {
                    "status": "error",
                    "error": "Only admin can change module rollout settings",
                    "error_code": "FORBIDDEN",
                },
                status=403,
            )

        data = await request.json()
        mode = data.get("preferred_version_rollout_mode")
        sync_after_preferred_change = data.get("sync_after_preferred_change")
        if mode is not None:
            mode = str(mode or "").strip().lower()
        if sync_after_preferred_change is not None and not isinstance(sync_after_preferred_change, bool):
            return web.json_response(
                {
                    "status": "error",
                    "error": "sync_after_preferred_change must be a boolean",
                    "error_code": "VALIDATION_ERROR",
                },
                status=400,
            )

        async with get_session() as session:
            rollout_repo = ModuleRolloutRepo(session)
            settings = await rollout_repo.set_settings(
                preferred_version_rollout_mode=mode,
                sync_after_preferred_change=sync_after_preferred_change,
            )
            await session.commit()
        return web.json_response({"status": "ok", "rollout_settings": settings})
    except Exception as e:
        logger.error(f"Patch module rollout settings failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_set_module_preferred_version(request):
    """
    PATCH /api/modules/{module_name}/preferred
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()
        if auth_context.actor_role != "admin":
            return web.json_response(
                {
                    "status": "error",
                    "error": "Only admin can change preferred module versions",
                    "error_code": "FORBIDDEN",
                },
                status=403,
            )

        module_name = request.match_info["module_name"]
        data = await request.json()
        version = str(data.get("version") or "").strip()

        async with get_session() as session:
            rollout_repo = ModuleRolloutRepo(session)
            modules_repo = ModulesRepo(session)
            if not version:
                await rollout_repo.clear_assignment(module_name)
                await session.commit()
                return web.json_response(
                    {
                        "status": "ok",
                        "module_name": module_name,
                        "preferred_version": None,
                    }
                )
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Module version not found",
                        "error_code": "MODULE_NOT_FOUND",
                        "module_name": module_name,
                        "version": version,
                    },
                    status=404,
                )
            assignment = await rollout_repo.set_assignment(
                module_name=module_name,
                version=version,
                updated_by=auth_context.actor_role,
            )
            rollout_settings = await _get_module_rollout_settings(session)
            rollout_summary = await _apply_module_preferred_rollout(
                session=session,
                state=request.app.get("state"),
                module_name=module_name,
                version=version,
                updated_by=auth_context.actor_role,
                settings=rollout_settings,
            )
            await session.commit()
            rollout_summary = await _finalize_module_preferred_rollout(
                state=request.app.get("state"),
                updated_by=auth_context.actor_role,
                rollout_summary=rollout_summary,
            )
            return web.json_response(
                {
                    "status": "ok",
                    "module_name": module_name,
                    "preferred_version": assignment["version"],
                    "updated_at": assignment["updated_at"],
                    "updated_by": assignment["updated_by"],
                    "rollout_summary": rollout_summary,
                }
            )
    except Exception as e:
        logger.error(f"Set preferred module version failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_save_module_workbench(request):
    """
    POST /api/modules/workbench/save
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()
        status_code, response_payload = await _build_and_store_module_package(
            auth_context=auth_context,
            payload=await request.json(),
            app_state=request.app.get("state"),
        )
        return web.json_response(response_payload, status=status_code)
    except Exception as e:
        logger.error(f"Save module workbench failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_validate_module_workbench(request):
    """
    POST /api/modules/workbench/validate
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return _module_auth_error_response()

        status_code, response_payload, prepared = await _prepare_module_package_payload(await request.json())
        if prepared is None:
            return web.json_response(response_payload, status=status_code)

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            tool_conflicts = await _find_registry_tool_conflicts(session, prepared["manifest_json"])
            existing = await modules_repo.get_module(prepared["module_name"], prepared["version"])

        editable_preview = build_editable_spec_from_archive_bytes(
            zip_bytes=prepared["zip_bytes"],
            manifest_json=prepared["manifest_json"],
            fallback_module_name=prepared["module_name"],
            fallback_version=prepared["version"],
        )
        publish_ready = existing is None and not tool_conflicts
        response_payload.update(
            {
                "validation_json": prepared["validation_json"],
                "manifest_json": prepared["manifest_json"],
                "manifest_summary": prepared["manifest_summary"],
                "module_exists": existing is not None,
                "publish_ready": publish_ready,
                "conflicts": tool_conflicts,
                "editable_preview": editable_preview,
            }
        )
        return web.json_response(response_payload, status=200)
    except Exception as e:
        logger.error(f"Validate module workbench failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_delete_module(request):
    """
    DELETE /api/modules/{module_name}/{version}

    Удаляет модуль с сервера: запись из БД и файл с диска.
    Требует аутентификации и роль admin.

    Returns:
        200 OK: { "status": "ok", "module_name": "...", "version": "..." }
        401: Authentication required
        403: Only admin can delete modules
        404: Module not found
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        if auth_context.actor_role != "admin":
            return web.json_response({
                "status": "error",
                "error": "Only admin can delete modules from server"
            }, status=403)

        module_name = request.match_info["module_name"]
        version = request.match_info["version"]

        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            rollout_repo = ModuleRolloutRepo(session)
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response({
                    "status": "error",
                    "error": "Module not found",
                    "module_name": module_name,
                    "version": version
                }, status=404)

            storage_path = module.storage_path
            assignment = await rollout_repo.get_assignment(module_name)
            deleted = await modules_repo.delete_module(module_name, version)
            if assignment and assignment.get("version") == version:
                await rollout_repo.clear_assignment(module_name)
            await session.commit()

        if not deleted:
            return web.json_response({
                "status": "error",
                "error": "Module not found",
                "module_name": module_name,
                "version": version
            }, status=404)

        full_path = MODULES_STORAGE_DIR / storage_path
        if full_path.exists():
            try:
                full_path.unlink()
            except OSError as e:
                logger.error(f"Failed to delete module file {full_path}: {e}")
                return web.json_response({
                    "status": "error",
                    "error": f"Failed to delete file: {e}"
                }, status=500)
        else:
            logger.warning(f"Module file already missing on disk: {full_path}")

        # Удаляем пустые директории (module_name/version/)
        try:
            parent = full_path.parent
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
            top = parent.parent
            if top.exists() and not any(top.iterdir()):
                top.rmdir()
        except OSError:
            pass

        logger.info(f"Module deleted from server: {module_name}/{version}")
        return web.json_response({
            "status": "ok",
            "module_name": module_name,
            "version": version
        })

    except Exception as e:
        logger.error(f"❌ Ошибка обработки delete_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_cleanup_missing_modules(request):
    """
    POST /api/modules/cleanup_missing

    Deletes registry records whose archive files are already missing on disk.
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
            }, status=401)
        if auth_context.actor_role != "admin":
            return web.json_response({
                "status": "error",
                "error": "Only admin can cleanup missing modules",
                "error_code": "FORBIDDEN",
            }, status=403)

        removed: list[dict] = []
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            modules = await modules_repo.list_modules(limit=500)
            for module in modules:
                storage_state = _module_storage_state(module)
                if not storage_state["file_missing"]:
                    continue
                deleted = await modules_repo.delete_module(module.module_name, module.version)
                if deleted:
                    removed.append({
                        "module_name": module.module_name,
                        "version": module.version,
                        "storage_path": storage_state["storage_path"],
                    })
            await session.commit()

        logger.info(f"Module cleanup_missing removed {len(removed)} stale records")
        return web.json_response({
            "status": "ok",
            "removed": removed,
            "count": len(removed),
        })
    except Exception as e:
        logger.error(f"Cleanup missing modules failed: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e),
        }, status=500)


async def handle_get_device_modules(request):
    """
    GET /api/devices/{device_id}/modules?active_only=1
    """
    try:
        device_id = request.match_info["device_id"]
        active_only = request.query.get("active_only", "0") == "1"

        async with get_session() as session:
            device_modules_repo = DeviceModulesRepo(session)
            modules_repo = ModulesRepo(session)
            modules = await device_modules_repo.get_device_modules(
                device_id=device_id,
                active_only=active_only
            )
            modules = [item for item in modules if item.installed]
            registry_modules = await modules_repo.list_modules(limit=500)
            registry_map = {(item.module_name, item.version): item for item in registry_modules}

            payload_modules = []
            for item in modules:
                registry_module = registry_map.get((item.module_name, item.version))
                validation_json = get_module_validation(registry_module) if registry_module else {"legacy_manifest": False}
                payload_modules.append({
                    "module_name": item.module_name,
                    "version": item.version,
                    "installed": item.installed,
                    "active": item.active,
                    "installed_at": item.installed_at.isoformat() if item.installed_at else None,
                    "activated_at": item.activated_at.isoformat() if item.activated_at else None,
                    "state": item.state,
                    "last_error_code": item.last_error_code,
                    "last_error_message": item.last_error_message,
                    "source": "managed" if registry_module else "device",
                    "manifest_version": 1 if validation_json.get("legacy_manifest") else (get_module_manifest(registry_module).get("manifest_version", 2) if registry_module else None),
                    "legacy_manifest": bool(validation_json.get("legacy_manifest")) if registry_module else False,
                })
            return web.json_response({
                "status": "ok",
                "device_id": device_id,
                "modules": payload_modules,
                "count": len(payload_modules)
            })

    except Exception as e:
        logger.error(f"Get device modules failed: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_device_toolset(request):
    """
    GET /api/devices/{device_id}/toolset

    Returns latest toolset snapshot (tools grouped by module).
    """
    try:
        device_id = request.match_info["device_id"]

        async with get_session() as session:
            from app.repos import ToolsetSnapshotsRepo

            repo = ToolsetSnapshotsRepo(session)
            snapshot = await repo.get_latest_snapshot(device_id)

            if not snapshot:
                return web.json_response({
                    "status": "error",
                    "error": "No toolset snapshot found"
                }, status=404)

            modules_repo = ModulesRepo(session)
            registry_modules = await modules_repo.list_modules(limit=500)
            origin_by_module = {}
            for registry_module in registry_modules:
                manifest = get_module_manifest(registry_module)
                for tool in manifest.get("tools", []):
                    origin_by_module.setdefault(registry_module.module_name, tool.get("metadata", {}).get("origin") or "managed")

            tools_list = snapshot.toolset_json.get("tools", [])
            tools_by_module = {}
            for tool in tools_list:
                module_name = tool.get("module", "unknown")
                enriched = dict(tool)
                if module_name in origin_by_module:
                    enriched["origin"] = origin_by_module[module_name]
                if module_name not in tools_by_module:
                    tools_by_module[module_name] = []
                tools_by_module[module_name].append(enriched)

            return web.json_response({
                "status": "ok",
                "device_id": device_id,
                "toolset_hash": snapshot.toolset_hash,
                "tool_count": snapshot.tool_count,
                "captured_at": snapshot.captured_at.isoformat(),
                "tools_by_module": tools_by_module
            })

    except Exception as e:
        logger.error(f"Get device toolset failed: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_install_module(request):
    """
    POST /api/devices/{device_id}/modules/install
    
    Устанавливает модуль на устройство (enqueue install_module_package).
    
    JSON body:
    {
        "module_name": "...",
        "version": "...",
        "actor_role": "admin"
    }
    
    Returns:
        202 Accepted: {
            "status": "accepted",
            "operation_id": "..."
        }
    """
    try:
        # Phase 2: Получаем actor_role из AuthContext, не из JSON body
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        # Опционально: заменить существующую версию при другом SHA (передаётся агенту как replace_if_different_sha)
        replace_if_exists = data.get("replace_if_exists") or data.get("replace_if_different_sha") or False
        
        # КРИТИЧНО: Игнорируем actor_role из JSON body с warning
        if "actor_role" in data:
            logger.warning(
                f"[handle_install_module] actor_role in JSON body ignored: "
                f"using actor_role={auth_context.actor_role} from AuthContext"
            )
            data.pop("actor_role", None)
        
        actor_role = auth_context.actor_role
        
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        # Phase 4: Policy check для install_module_package
        # install_module_package - системная операция, требует admin или system роль
        if module_name.lower() in AGENT_BUILTIN_MODULES:
            logger.info(
                f"[handle_install_module] Builtin module install skipped: "
                f"device_id={device_id} module={module_name}/{version}"
            )
            payload = _builtin_module_install_payload(module_name, version)
            payload["status"] = "accepted"
            payload["operation_id"] = f"builtin:{device_id}:{module_name}:{version}"
            return web.json_response(payload, status=202)

        install_metadata = ToolMetadata(
            risk_level="system_write",  # install_module_package - системная операция
            requires_consent=False,
            allow_roles=None  # PolicyEngine решает по risk_level
        )
        
        policy_engine = PolicyEngine()
        policy_decision = policy_engine.check_policy(
            actor_role=actor_role,
            tool_name="install_module_package",
            metadata=install_metadata
        )
        
        # Если policy запрещает → 403, операция не создается
        if not policy_decision.allow:
            logger.warning(
                f"[handle_install_module] Policy violation: install_module_package "
                f"actor_role={actor_role} reason={policy_decision.reason}"
            )
            return web.json_response({
                "status": "error",
                "error": "Policy violation",
                "error_code": policy_decision.reason,
                "required_role": policy_decision.required_role
            }, status=403)
        
        # Валидация: module_name, version должны существовать в modules; проверка ОС устройства
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            module = await modules_repo.get_module(module_name, version)

            if not module:
                return web.json_response({
                    "status": "error",
                    "error_code": "MODULE_NOT_FOUND",
                    "error": f"Module {module_name}/{version} not found",
                    "hint": "Upload the module to the server registry before installing it on a device."
                }, status=404)

            full_path = _module_archive_path(module)
            if not full_path.exists():
                logger.error(
                    f"[handle_install_module] Module archive missing on disk: "
                    f"module={module_name}/{version} storage_path={module.storage_path} full_path={full_path}"
                )
                return web.json_response(
                    _module_file_missing_payload(module_name, version, module.storage_path),
                    status=409,
                )

            manifest_json = get_module_manifest(module)
            mod_platforms = manifest_json.get("platforms") or ["any"]
            if isinstance(mod_platforms, list) and mod_platforms and "any" not in [str(p).lower() for p in mod_platforms]:
                from app.repos.devices_repo import DevicesRepo
                devices_repo = DevicesRepo(session)
                device = await devices_repo.get_by_device_id(device_id)
                if not device:
                    return web.json_response({
                        "status": "error",
                        "error_code": "DEVICE_NOT_FOUND",
                        "error": f"Device {device_id} not found",
                        "hint": "Refresh the devices list and verify that the target agent is registered."
                    }, status=404)
                device_os = (device.os or "").strip()
                if not device_os:
                    return web.json_response({
                        "status": "error",
                        "error_code": "DEVICE_OS_UNKNOWN",
                        "error": "Device OS unknown, cannot verify module compatibility.",
                        "hint": "Reconnect the agent so the server can refresh the device platform information."
                    }, status=400)
                os_norm = device_os.lower()
                if os_norm == "windows":
                    os_norm = "win32"
                elif os_norm not in ("linux", "darwin"):
                    os_norm = os_norm.replace(" ", "")
                allowed = [str(p).lower() for p in mod_platforms]
                if os_norm not in allowed:
                    return web.json_response({
                        "status": "error",
                        "error_code": "MODULE_PLATFORM_MISMATCH",
                        "error": f"Module not supported on device OS: device os={device_os!r}, module platforms={allowed}",
                        "hint": "Choose a module build whose manifest platforms include the device OS."
                    }, status=400)

            download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{module_name}/{version}/download"
            
            # КРИТИЧНО: Использовать kind="module_install" для операций
            from app.services.operation_service import OperationService
            from websocket.ui_publisher import UiPublisherImpl
            
            operation_id = str(uuid.uuid4())
            
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_install",  # NEW: специальный kind для модульных операций
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
            
            # Enqueue install_module_package через enqueue_command_async (fire-and-forget)
            params_install = {
                "module_name": module_name,
                "module_version": version,
                "download_url": download_url,
                "sha256": module.sha256,
                "size": module.size,
                "package_b64": None,  # Опционально, для fallback
            }
            if replace_if_exists:
                params_install["replace_if_different_sha"] = True
            await enqueue_command_async(
                state=state,
                device_id=device_id,
                command="install_module_package",
                params=params_install,
                actor_role=actor_role,
                operation_id=operation_id  # Связать с operation
            )

            # Записываем desired state: хотим этот модуль на этом устройстве
            try:
                await set_desired_installed(
                    device_id=device_id,
                    module_name=module_name,
                    desired_version=version,
                    desired_sha256=module.sha256,
                    reason="manual",
                    updated_by=actor_role,
                    session=session,
                )
                await session.commit()
            except Exception as desired_e:
                logger.warning(f"[handle_install_module] Failed to set desired state: {desired_e}")
            await _enqueue_module_followup_sync(
                state=state,
                device_id=device_id,
                actor_role=actor_role,
                require_online=False,
            )
            
            return web.json_response({
                "status": "accepted",
                "operation_id": operation_id
            }, status=202)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки install_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_bulk_install_modules(request):
    """
    POST /api/modules/bulk_install

    Массовая установка модуля на несколько устройств.
    Для каждого device_id ставится команда install_module_package в outbox:
    онлайн-агенты получают команду сразу, офлайн — при подключении из очереди.
    На каждом агенте при установке сначала выполняется smoke-проверка, затем установка.

    JSON body:
    - module_name (обязательно)
    - version (обязательно)
    - device_ids (обязательно, массив UUID устройств)
    - replace_if_exists (опционально, default false)

    Returns:
        202 Accepted: { "status": "accepted", "operations": [ { "device_id", "operation_id" } ] }
        404: Module not found
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
            }, status=401)

        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        device_ids = data.get("device_ids")
        replace_if_exists = data.get("replace_if_exists") or False

        if not module_name:
            return web.json_response({"status": "error", "error": "Missing module_name"}, status=400)
        if not version:
            return web.json_response({"status": "error", "error": "Missing version"}, status=400)
        if not isinstance(device_ids, list) or len(device_ids) == 0:
            return web.json_response({
                "status": "error",
                "error": "device_ids must be a non-empty array",
            }, status=400)

        if module_name.lower() in AGENT_BUILTIN_MODULES:
            skipped = []
            for device_id in device_ids:
                if isinstance(device_id, str) and device_id.strip():
                    skipped.append({
                        "device_id": device_id.strip(),
                        "reason": f"builtin module {module_name!r} is already bundled with the agent",
                    })
            logger.info(
                f"[handle_bulk_install_modules] Builtin module install skipped: "
                f"module={module_name}/{version} devices={len(skipped)}"
            )
            payload = _builtin_module_install_payload(module_name, version)
            payload["status"] = "accepted"
            payload["operations"] = []
            payload["skipped"] = skipped
            return web.json_response(payload, status=202)

        actor_role = auth_context.actor_role
        install_metadata = ToolMetadata(
            risk_level="system_write",
            requires_consent=False,
            allow_roles=None,
        )
        policy_engine = PolicyEngine()
        policy_decision = policy_engine.check_policy(
            actor_role=actor_role,
            tool_name="install_module_package",
            metadata=install_metadata,
        )
        if not policy_decision.allow:
            return web.json_response({
                "status": "error",
                "error": "Policy violation",
                "error_code": policy_decision.reason,
                "required_role": policy_decision.required_role,
            }, status=403)

        state = request.app["state"]
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl

        operations_out = []
        sync_device_ids = []
        skipped = []
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response({
                    "status": "error",
                    "error": f"Module {module_name}/{version} not found",
                }, status=404)
            full_path = _module_archive_path(module)
            if not full_path.exists():
                logger.error(
                    f"[handle_bulk_install_modules] Module archive missing on disk: "
                    f"module={module_name}/{version} storage_path={module.storage_path} full_path={full_path}"
                )
                return web.json_response(
                    _module_file_missing_payload(module_name, version, module.storage_path),
                    status=409,
                )
            manifest_json = get_module_manifest(module)
            mod_platforms = manifest_json.get("platforms") or ["any"]
            check_platforms = isinstance(mod_platforms, list) and "any" not in [str(p).lower() for p in mod_platforms]
            from app.repos.devices_repo import DevicesRepo
            devices_repo = DevicesRepo(session)
            download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{module_name}/{version}/download"
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            for device_id in device_ids:
                if not isinstance(device_id, str) or not device_id.strip():
                    continue
                device_id = device_id.strip()
                if check_platforms:
                    device = await devices_repo.get_by_device_id(device_id)
                    if not device:
                        skipped.append({"device_id": device_id, "reason": "device not found"})
                        continue
                    device_os = (device.os or "").strip()
                    if not device_os:
                        skipped.append({"device_id": device_id, "reason": "device OS unknown"})
                        continue
                    os_norm = device_os.lower()
                    if os_norm == "linux":
                        os_norm = "linux"
                    elif os_norm == "windows":
                        os_norm = "win32"
                    elif os_norm == "darwin":
                        os_norm = "darwin"
                    else:
                        os_norm = os_norm.replace(" ", "")
                    allowed = [str(p).lower() for p in mod_platforms]
                    if os_norm not in allowed:
                        skipped.append({"device_id": device_id, "reason": f"OS {device_os!r} not in {allowed}"})
                        continue
                operation_id = str(uuid.uuid4())
                await op_service.enqueue_operation(
                    operation_id=operation_id,
                    device_id=device_id,
                    kind="module_install",
                    actor_role=actor_role,
                    trace_id=str(uuid.uuid4()),
                    ticket_id=None,
                    job_id=None,
                )
                params_install = {
                    "module_name": module_name,
                    "module_version": version,
                    "download_url": download_url,
                    "sha256": module.sha256,
                    "size": module.size,
                    "package_b64": None,
                }
                if replace_if_exists:
                    params_install["replace_if_different_sha"] = True
                await enqueue_command_async(
                    state=state,
                    device_id=device_id,
                    command="install_module_package",
                    params=params_install,
                    actor_role=actor_role,
                    operation_id=operation_id,
                    require_online=False,
                )
                await set_desired_installed(
                    device_id=device_id,
                    module_name=module_name,
                    desired_version=version,
                    desired_sha256=module.sha256,
                    reason="manual",
                    updated_by=actor_role,
                    session=session,
                )
                sync_device_ids.append(device_id)
                operations_out.append({"device_id": device_id, "operation_id": operation_id})
            await session.commit()
        for sync_device_id in sync_device_ids:
            await _enqueue_module_followup_sync(
                state=state,
                device_id=sync_device_id,
                actor_role=actor_role,
                require_online=False,
            )

        return web.json_response({
            "status": "accepted",
            "operations": operations_out,
            "skipped": skipped,
        }, status=202)
    except Exception as e:
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e),
        }, status=500)


async def handle_activate_module_new(request):
    """
    POST /api/devices/{device_id}/modules/activate
    
    Активирует модуль на устройстве (enqueue activate_module).
    
    JSON body:
    {
        "module_name": "...",
        "version": "...",
        "actor_role": "admin"
    }
    
    Returns:
        202 Accepted: {
            "status": "accepted",
            "operation_id": "..."
        }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="activate_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        if "actor_role" in data:
            logger.warning(
                f"[handle_activate_module_new] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name"
            }, status=400)
        
        if not version:
            return web.json_response({
                "status": "error",
                "error": "Missing version"
            }, status=400)
        
        # КРИТИЧНО: Использовать kind="module_activate" для операций
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_activate",  # NEW: специальный kind для модульных операций
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Enqueue activate_module через enqueue_command_async (fire-and-forget)
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="activate_module",
            params={
                "name": module_name,
                "version": version
            },
            actor_role=actor_role,
            operation_id=operation_id  # Связать с operation
        )
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role=actor_role,
            require_online=False,
        )

        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки activate_module_new: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_deactivate_module_new(request):
    """
    POST /api/devices/{device_id}/modules/deactivate
    
    Деактивирует модуль на устройстве (enqueue deactivate_module).
    
    JSON body:
    {
        "module_name": "...",
        "actor_role": "admin"
    }
    
    Returns:
        202 Accepted: {
            "status": "accepted",
            "operation_id": "..."
        }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="deactivate_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        data = await request.json()
        module_name = data.get("module_name")
        if "actor_role" in data:
            logger.warning(
                f"[handle_deactivate_module_new] actor_role in JSON body ignored: "
                f"using actor_role={actor_role} from AuthContext"
            )
        
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name"
            }, status=400)
        
        # КРИТИЧНО: Использовать kind="module_deactivate" для операций
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_deactivate",  # NEW: специальный kind для модульных операций
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Enqueue deactivate_module через enqueue_command_async (fire-and-forget)
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="deactivate_module",
            params={
                "name": module_name
            },
            actor_role=actor_role,
            operation_id=operation_id  # Связать с operation
        )
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role=actor_role,
            require_online=False,
        )

        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки deactivate_module_new: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_sync_modules(request):
    """
    POST /api/devices/{device_id}/modules/sync
    
    Принудительная синхронизация модулей:
    1. Enqueue list_installed_modules (для синхронизации device_modules)
    2. Enqueue list_tools (для обновления device_toolset_snapshots)
    
    КРИТИЧНО: Sync Modules должна обновлять и modules inventory, и toolset snapshot.
    
    Returns:
        202 Accepted: {
            "status": "accepted",
            "operations": {
                "modules_sync": "operation_id_1",
                "toolset_sync": "operation_id_2"
            }
        }
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="sync_modules",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        from websocket.protocol import enqueue_command_async
        
        # 1. Enqueue list_installed_modules (для синхронизации device_modules)
        modules_op_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="list_installed_modules",
            params={},
            actor_role=actor_role,
            trace_id=None
        )
        
        # 2. Enqueue list_tools (для обновления device_toolset_snapshots)
        toolset_op_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="list_tools",
            params={},
            actor_role=actor_role,
            trace_id=None
        )
        
        logger.info(
            f"[sync_modules] Enqueued sync operations: "
            f"device_id={device_id} modules_op={modules_op_id} toolset_op={toolset_op_id}"
        )
        
        return web.json_response({
            "status": "accepted",
            "operations": {
                "modules_sync": modules_op_id,
                "toolset_sync": toolset_op_id
            }
        }, status=202)
    
    except ValueError as e:
        logger.warning(f"вљ пёЏ  {str(e)}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки sync_modules: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_remove_module_version(request):
    """
    POST /api/devices/{device_id}/modules/remove_version
    
    JSON: {"module_name": "...", "version": "..."}
    Returns: {"status": "accepted", "operation_id": "..."}
    Перед enqueue: capability/version check — модуль с такой версией есть в device_modules.
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="remove_module_version",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        device_id = request.match_info["device_id"]
        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        force = data.get("force", False)
        
        if not module_name or not version:
            return web.json_response({
                "status": "error",
                "error": "module_name and version required"
            }, status=400)
        
        state = request.app['state']
        
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        from app.repos import DeviceModulesRepo
        module_versions = []

        # При force=True не проверяем inventory — сразу ставим команду remove_module_version агенту
        if not force:
            # Capability/version check: модуль с версией должен быть в device_modules (по snapshot/inventory)
            async with get_session() as session:
                dev_mod_repo = DeviceModulesRepo(session)
                installed = await dev_mod_repo.get_device_modules(device_id, active_only=False)
                module_versions = [
                    m for m in installed
                    if m.module_name == module_name and m.state != "removed"
                ]
                if installed:
                    found = any(m.module_name == module_name and m.version == version for m in installed)
                    if not found:
                        return web.json_response({
                            "status": "error",
                            "error": f"Module {module_name}@{version} not found in device inventory. Sync modules first or check name/version."
                        }, status=400)
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_remove_version",  # NEW: специальный kind для модульных операций
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Enqueue command
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="remove_module_version",
            params={"name": module_name, "version": version},
            actor_role=actor_role,
            trace_id=None,
            operation_id=operation_id,  # Связать с operation
            require_online=False,
        )
        if len(module_versions) <= 1:
            try:
                await set_desired_absent(
                    device_id=device_id,
                    module_name=module_name,
                    reason="manual_remove",
                    updated_by=actor_role,
                )
            except Exception as desired_e:
                logger.warning(
                    f"[handle_remove_module_version] Failed to set desired absent "
                    f"for {device_id}:{module_name}@{version}: {desired_e}"
                )
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role=actor_role,
            require_online=False,
        )

        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки remove_module_version: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_remove_module(request):
    """
    POST /api/devices/{device_id}/modules/remove
    
    JSON: {"module_name": "...", "version": "..." (optional), "force": false}
    Returns: {"status": "accepted", "operation_id": "..."}
    Перед удалением агент требует деактивацию: сначала в очередь ставится deactivate_module,
    затем remove_module (агент обработает по порядку).
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="remove_module",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        device_id = request.match_info["device_id"]
        data = await request.json()
        module_name = data.get("module_name")
        force = data.get("force", False)
        
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "module_name required"
            }, status=400)
        
        state = request.app['state']
        
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        from app.repos import DeviceModulesRepo

        # При force=True не проверяем inventory — сразу ставим команды агенту
        if not force:
            # Capability check: модуль должен быть в device_modules
            async with get_session() as session:
                dev_mod_repo = DeviceModulesRepo(session)
                installed = await dev_mod_repo.get_device_modules(device_id, active_only=False)
                if installed:
                    found = any(m.module_name == module_name for m in installed)
                    if not found:
                        return web.json_response({
                            "status": "error",
                            "error": f"Module {module_name} not found in device inventory. Sync modules first."
                        }, status=400)
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_remove",
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Агент не удаляет активный модуль: "Deactivate first". Ставим в очередь сначала
        # deactivate_module, затем remove_module — агент обработает по порядку.
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="deactivate_module",
            params={"name": module_name},
            actor_role=actor_role,
            trace_id=None,
            require_online=False,
        )
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="remove_module",
            params={"name": module_name},
            actor_role=actor_role,
            trace_id=None,
            operation_id=operation_id,
            require_online=False,
        )

        # Записываем desired state: хотим отсутствие этого модуля
        try:
            await set_desired_absent(
                device_id=device_id,
                module_name=module_name,
                reason="manual",
                updated_by=actor_role,
            )
        except Exception as desired_e:
            logger.warning(f"[handle_remove_module] Failed to set desired absent: {desired_e}")
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role=actor_role,
            require_online=False,
        )
        
        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки remove_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_verify_module(request):
    """
    POST /api/devices/{device_id}/modules/verify
    
    JSON: {"module_name": "...", "version": "..."}
    Returns: {"status": "ok", "verified": bool, "tools_found": int}
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        _actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="verify_module",
            risk_level="safe_read",
        )
        if error_response:
            return error_response

        device_id = request.match_info["device_id"]
        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        
        if not module_name or not version:
            return web.json_response({
                "status": "error",
                "error": "module_name and version required"
            }, status=400)
        
        state = request.app["state"]
        async with get_session() as session:
            from modules.verification import verify_module_activation

            result = await verify_module_activation(
                session=session,
                device_id=device_id,
                module_name=module_name,
                version=version,
                state=state,
                run_smoke=True,
            )

            return web.json_response({
                "status": "ok",
                **result
            })
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки verify_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_debug_modules(request):
    """
    GET /api/devices/{device_id}/modules/debug

    Returns comprehensive debug info for device modules.
    """
    try:
        device_id = request.match_info["device_id"]

        async with get_session() as session:
            from app.repos import DevicesRepo, DeviceModulesRepo, ToolsetSnapshotsRepo, OperationsRepo
            from app.repos.device_desired_modules_repo import DeviceDesiredModulesRepo

            devices_repo = DevicesRepo(session)
            device_modules_repo = DeviceModulesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)
            operations_repo = OperationsRepo(session)
            desired_repo = DeviceDesiredModulesRepo(session)

            device = await devices_repo.get_by_device_id(device_id)
            modules = await device_modules_repo.get_device_modules(device_id)
            snapshot = await snapshots_repo.get_latest_snapshot(device_id)
            desired_list = await desired_repo.get_desired(device_id)
            module_operations = await operations_repo.get_recent_operations(
                device_id=device_id,
                kinds=["module_install", "module_activate", "module_deactivate", "module_rollback", "module_remove_version", "module_remove"],
                limit=10
            )

            tool_names = []
            if snapshot and snapshot.toolset_json:
                tool_names = [tool.get("tool") or tool.get("name") for tool in snapshot.toolset_json.get("tools", [])]
            actual_active = {item.module_name: item.version for item in modules if item.active}
            desired_map = {item.module_name: {"state": item.state, "version": item.desired_version} for item in desired_list}
            mismatches = []
            for module_name, desired in desired_map.items():
                actual_version = actual_active.get(module_name)
                if desired["state"] == "installed" and actual_version != desired["version"]:
                    mismatches.append({
                        "module_name": module_name,
                        "kind": "desired_vs_actual",
                        "desired_version": desired["version"],
                        "actual_version": actual_version,
                    })
                if desired["state"] == "absent" and actual_version is not None:
                    mismatches.append({
                        "module_name": module_name,
                        "kind": "expected_absent",
                        "desired_version": None,
                        "actual_version": actual_version,
                    })
            for module_name in actual_active:
                if module_name not in desired_map:
                    mismatches.append({
                        "module_name": module_name,
                        "kind": "actual_without_desired",
                        "desired_version": None,
                        "actual_version": actual_active[module_name],
                    })

            return web.json_response({
                "status": "ok",
                "device": {
                    "device_id": device.device_id if device else None,
                    "hostname": device.hostname if device else None,
                    "toolset_hash": device.current_toolset_hash if device else None,
                    "last_tools_changed_at": device.last_tools_changed_at.isoformat() if device and device.last_tools_changed_at else None
                },
                "device_modules": [
                    {
                        "module_name": item.module_name,
                        "version": item.version,
                        "state": item.state,
                        "active": item.active,
                        "last_error_code": item.last_error_code,
                        "last_error_message": item.last_error_message
                    }
                    for item in modules
                ],
                "desired_modules": [
                    {
                        "module_name": item.module_name,
                        "desired_state": item.state,
                        "desired_version": item.desired_version,
                        "reason": item.reason,
                    }
                    for item in desired_list
                ],
                "toolset_snapshot": {
                    "toolset_hash": snapshot.toolset_hash if snapshot else None,
                    "tool_count": snapshot.tool_count if snapshot else 0,
                    "captured_at": snapshot.captured_at.isoformat() if snapshot else None,
                    "tools": tool_names,
                },
                "recent_operations": [
                    {
                        "operation_id": op.operation_id,
                        "kind": op.kind,
                        "status": op.status,
                        "error_code": op.error_code,
                        "error_message": op.error_message
                    }
                    for op in module_operations
                ],
                "mismatches": mismatches,
            })

    except Exception as e:
        logger.error(f"Debug modules failed: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_desired_diff(request):
    """
    GET /api/devices/{device_id}/modules/desired_diff

    Возвращает разницу между desired state и actual state для устройства.
    Используется для admin-страницы наблюдаемости и drift detection.
    """
    try:
        device_id = request.match_info["device_id"]

        async with get_session() as session:
            from app.repos import DeviceModulesRepo
            from app.repos.device_desired_modules_repo import DeviceDesiredModulesRepo

            desired_repo = DeviceDesiredModulesRepo(session)
            actual_repo = DeviceModulesRepo(session)

            desired_list = await desired_repo.get_desired(device_id)
            actual_list = await actual_repo.get_device_modules(device_id)

            # actual map: module_name -> active record
            actual_active: dict = {}
            for m in actual_list:
                if m.active:
                    actual_active[m.module_name] = m

            diff = []
            for d in desired_list:
                actual = actual_active.get(d.module_name)
                if d.state == "installed":
                    if actual and actual.version == d.desired_version:
                        status = "ok"
                    elif actual:
                        status = "version_mismatch"
                    else:
                        status = "missing"
                elif d.state == "absent":
                    if actual:
                        status = "not_removed"
                    else:
                        status = "ok"
                else:
                    status = "unknown"

                diff.append({
                    "module_name": d.module_name,
                    "desired_state": d.state,
                    "desired_version": d.desired_version,
                    "actual_state": actual.state if actual else None,
                    "actual_version": actual.version if actual else None,
                    "actual_active": actual.active if actual else False,
                    "diff_status": status,
                    "reason": d.reason,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                    "last_seen_at": actual.last_seen_at.isoformat() if actual and actual.last_seen_at else None,
                })

        return web.json_response({
            "status": "ok",
            "device_id": device_id,
            "diff": diff,
            "summary": {
                "total": len(diff),
                "ok": sum(1 for d in diff if d["diff_status"] == "ok"),
                "missing": sum(1 for d in diff if d["diff_status"] == "missing"),
                "version_mismatch": sum(1 for d in diff if d["diff_status"] == "version_mismatch"),
                "not_removed": sum(1 for d in diff if d["diff_status"] == "not_removed"),
            }
        })

    except Exception as e:
        logger.error(f"❌ Ошибка desired_diff: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_trigger_reconcile(request):
    """
    POST /api/devices/{device_id}/modules/reconcile

    Запускает немедленный reconcile для устройства.
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        actor_role, error_response = _check_module_policy(
            auth_context=auth_context,
            tool_name="reconcile_modules",
            risk_level="system_write",
        )
        if error_response:
            return error_response

        device_id = request.match_info["device_id"]
        state = request.app["state"]

        from modules.reconcile import reconcile_device
        stats = await reconcile_device(device_id=device_id, state=state, reason="manual_trigger")

        return web.json_response({
            "status": "ok",
            "device_id": device_id,
            "actor_role": actor_role,
            "stats": stats,
        })

    except Exception as e:
        logger.error(f"❌ Ошибка trigger_reconcile: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)
