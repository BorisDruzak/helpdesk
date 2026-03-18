"""
HTTP РѕР±СЂР°Р±РѕС‚С‡РёРєРё РґР»СЏ modules API (СѓРїСЂР°РІР»РµРЅРёРµ РґРёРЅР°РјРёС‡РµСЃРєРёРјРё РјРѕРґСѓР»СЏРјРё).
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
from pathlib import Path
from typing import Optional
from aiohttp import web
from loguru import logger
from websocket.protocol import send_ws_command, enqueue_command_async
from config import MODULES_STORAGE_DIR, MAX_MODULE_SIZE, SERVER_PUBLIC_BASE_URL
from utils.module_storage import save_module_zip_from_stream, save_module_zip_bytes, load_module_zip, stream_module_zip
from utils.module_preflight import apply_smoke_validation, preflight_module_zip
from utils.module_builder import build_module_package, DEFAULT_RISK_LEVEL
from utils.module_manifest import get_module_manifest, get_module_validation, module_to_api_record
from app.db import get_session
from app.repos import ModulesRepo, DeviceModulesRepo
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.db.models import DownloadAudit
from auth.context import AuthContext
from core.policy_engine import PolicyEngine
from core.tool_metadata import ToolMetadata
from modules.reconcile import set_desired_installed, set_desired_absent


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
    
    Р”Р»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё:
    1. Р•СЃР»Рё РјРѕРґСѓР»СЊ СѓР¶Рµ Р·Р°РіСЂСѓР¶РµРЅ (РїРѕ sha256) в†’ РёСЃРїРѕР»СЊР·СѓРµС‚ download_url
    2. РРЅР°С‡Рµ в†’ СЃРѕС…СЂР°РЅСЏРµС‚ РЅР° РґРёСЃРє, Р·Р°С‚РµРј РёСЃРїРѕР»СЊР·СѓРµС‚ download_url
    3. Fallback: РµСЃР»Рё download_url РЅРµ СЂР°Р±РѕС‚Р°РµС‚, РёСЃРїРѕР»СЊР·СѓРµС‚ package_b64
    
    РљР РРўРР§РќРћ: Р”РѕР»Р¶РµРЅ РІРѕР·РІСЂР°С‰Р°С‚СЊ operation_id РґР»СЏ РµРґРёРЅРѕРѕР±СЂР°Р·РёСЏ СЃ РЅРѕРІС‹Рј API.
    РЎРѕС…СЂР°РЅСЏРµС‚ СЃС‚Р°СЂС‹Рµ РїРѕР»СЏ РІ response РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃРѕ СЃС‚Р°СЂС‹РјРё РєР»РёРµРЅС‚Р°РјРё.
    
    РџРѕР»СЏ С„РѕСЂРјС‹:
    - device_id: string (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - name: string (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ) - РёРјСЏ РјРѕРґСѓР»СЏ
    - version: string (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ) - РІРµСЂСЃРёСЏ РјРѕРґСѓР»СЏ
    - actor_role: string (optional, default "admin")
    - sha256: string (optional) - РѕР¶РёРґР°РµРјС‹Р№ С…СЌС€ РґР»СЏ РїСЂРѕРІРµСЂРєРё
    - file: Р±РёРЅР°СЂРЅС‹Р№ ZIP (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ) - Р°СЂС…РёРІ РјРѕРґСѓР»СЏ
    """
    try:
        state = request.app['state']
        
        logger.info("[SERVER] install_module_package (legacy) RX")
        
        # Р§РёС‚Р°РµРј multipart/form-data
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
        
        # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїРѕР»РµР№
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
        
        # РџСЂРѕРІРµСЂРєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Р°РіРµРЅС‚Р°
        if not state.is_agent_online(device_id):
            logger.warning(f"[SERVER] install_module_package agent {device_id} not connected")
            return web.json_response({
                "status": "error",
                "error": f"Agent {device_id} not connected"
            }, status=404)
        
        # РЎРѕР·РґР°РµРј async iterator РґР»СЏ stream
        async def file_stream():
            while True:
                chunk = await file_field.read_chunk()
                if not chunk:
                    break
                yield chunk
        
        # РЎРѕС…СЂР°РЅСЏРµРј РЅР° РґРёСЃРє (streaming + sha256)
        storage_path, computed_sha256, size = await save_module_zip_from_stream(
            stream=file_stream(),
            module_name=name,
            version=version,
            storage_dir=MODULES_STORAGE_DIR,
            max_size=MAX_MODULE_SIZE
        )
        
        logger.info(f"[SERVER] computed sha256={computed_sha256}")
        
        # РџСЂРѕРІРµСЂРєР° РѕР¶РёРґР°РµРјРѕРіРѕ С…СЌС€Р°, РµСЃР»Рё Р±С‹Р» РїРµСЂРµРґР°РЅ
        if expected_sha256 and expected_sha256 != computed_sha256:
            logger.error(f"[SERVER] install_module_package HASH_MISMATCH expected={expected_sha256} computed={computed_sha256}")
            return web.json_response({
                "status": "error",
                "error": "HASH_MISMATCH",
                "expected_sha256": expected_sha256,
                "computed_sha256": computed_sha256
            }, status=400)
        
        # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РјРѕРґСѓР»СЊ РІ Р‘Р” (РїРѕ sha256)
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            existing_module = await modules_repo.get_module_by_sha256(computed_sha256)
            
            if not existing_module:
                # РЎРѕР·РґР°РµРј РЅРѕРІСѓСЋ Р·Р°РїРёСЃСЊ РІ Р‘Р”
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
        
        # РџРѕСЃС‚СЂРѕРёС‚СЊ download_url РЅР° РѕСЃРЅРѕРІРµ SERVER_PUBLIC_BASE_URL
        download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{name}/{version}/download"
        
        # Enqueue install_module_package С‡РµСЂРµР· enqueue_command_async (fire-and-forget)
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
                "package_b64": None  # РћРїС†РёРѕРЅР°Р»СЊРЅРѕ, РґР»СЏ fallback
            },
            actor_role=actor_role
        )
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј СЂРµР·СѓР»СЊС‚Р°С‚ СЃ operation_id (РќРћР’РћР• РїРѕР»Рµ) Рё СЃС‚Р°СЂС‹РјРё РїРѕР»СЏРјРё РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё
        return web.json_response({
            "status": "success",
            "operation_id": command_id,  # РќРћР’РћР• РїРѕР»Рµ
            "request_id": command_id,  # РЎС‚Р°СЂРѕРµ РїРѕР»Рµ (РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё)
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё install_module_package: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_list_installed_modules(request):
    """
    API СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РїРѕР»СѓС‡РµРЅРёСЏ СЃРїРёСЃРєР° СѓСЃС‚Р°РЅРѕРІР»РµРЅРЅС‹С… РјРѕРґСѓР»РµР№: POST /api/list_installed_modules
    
    POST JSON:
    { "device_id": "...", "actor_role": "admin" }
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        actor_role = data.get("actor_role", "admin")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        logger.info(f"[SERVER] list_installed_modules device_id={device_id}")
        
        res = await send_ws_command(state=state, device_id=device_id, command="list_installed_modules", params={}, actor_role=actor_role)
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј payload РёР· command_result
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
        logger.error(f"вЏ±пёЏ  РўР°Р№РјР°СѓС‚ РєРѕРјР°РЅРґС‹ list_installed_modules")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё list_installed_modules: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_activate_module(request):
    """
    API СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ Р°РєС‚РёРІР°С†РёРё РјРѕРґСѓР»СЏ: POST /api/activate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "version": "0.1.0", "actor_role": "admin" }
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        version = data.get("version")
        actor_role = data.get("actor_role", "admin")
        
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
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј РїРѕР»РЅС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚
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
        logger.error(f"вЏ±пёЏ  РўР°Р№РјР°СѓС‚ РєРѕРјР°РЅРґС‹ activate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё activate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_rollback_module(request):
    """
    API СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РѕС‚РєР°С‚Р° РјРѕРґСѓР»СЏ: POST /api/rollback_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        actor_role = data.get("actor_role", "admin")
        
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
        logger.error(f"вЏ±пёЏ  РўР°Р№РјР°СѓС‚ РєРѕРјР°РЅРґС‹ rollback_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё rollback_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_deactivate_module(request):
    """
    API СЌРЅРґРїРѕРёРЅС‚ РґР»СЏ РґРµР°РєС‚РёРІР°С†РёРё РјРѕРґСѓР»СЏ: POST /api/deactivate_module
    
    POST JSON:
    { "device_id": "...", "name": "hello", "actor_role": "admin" }
    """
    try:
        state = request.app['state']
        
        data = await request.json()
        device_id = data.get("device_id")
        name = data.get("name")
        actor_role = data.get("actor_role", "admin")
        
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
        
        # Р’РѕР·РІСЂР°С‰Р°РµРј РїРѕР»РЅС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚
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
        logger.error(f"вЏ±пёЏ  РўР°Р№РјР°СѓС‚ РєРѕРјР°РЅРґС‹ deactivate_module")
        return web.json_response({
            "status": "error",
            "error": "Command timeout"
        }, status=504)
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё deactivate_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_smoke_install_and_run(request):
    """
    РЈСЃС‚Р°СЂРµРІС€РёР№ СЌРЅРґРїРѕРёРЅС‚: РЅР° Р°РіРµРЅС‚Рµ РЅРµС‚ РєРѕРјР°РЅРґС‹ smoke_install_and_run.
    РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ: POST /api/devices/{device_id}/modules/install Рё run_tool РґР»СЏ smoke.
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
    
    Р—Р°РіСЂСѓР¶Р°РµС‚ РјРѕРґСѓР»СЊ РЅР° СЃРµСЂРІРµСЂ (СЃРѕС…СЂР°РЅСЏРµС‚ ZIP РЅР° РґРёСЃРє Рё РІ Р‘Р”).
    
    РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·СѓРµС‚ РїРѕС‚РѕРєРѕРІСѓСЋ Р·Р°РїРёСЃСЊ РёР· multipart stream, РЅРµ РґРµСЂР¶РёС‚ РІРµСЃСЊ ZIP РІ РїР°РјСЏС‚Рё.
    
    Multipart fields:
    - file: ZIP С„Р°Р№Р» (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ, streaming read)
    - module_name: string (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - version: string (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - actor_role: string (optional, default "admin")
    - overwrite: string (optional, "true"/"false", default "false") - СЂР°Р·СЂРµС€РёС‚СЊ РїРµСЂРµР·Р°Р»РёРІ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ (module_name, version)
    
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
        # Р§РёС‚Р°РµРј multipart/form-data
        reader = await request.multipart()
        
        module_name = None
        version = None
        actor_role = "admin"
        overwrite = False
        file_field = None
        
        # РљР РРўРР§РќРћ: РќСѓР¶РЅРѕ С‡РёС‚Р°С‚СЊ С„Р°Р№Р» РїСЂСЏРјРѕ РІ С†РёРєР»Рµ, Р° РЅРµ СЃРѕС…СЂР°РЅСЏС‚СЊ field РґР»СЏ С‡С‚РµРЅРёСЏ РїРѕСЃР»Рµ
        # Р’ aiohttp multipart field РЅРµР»СЊР·СЏ С‡РёС‚Р°С‚СЊ РїРѕСЃР»Рµ Р·Р°РІРµСЂС€РµРЅРёСЏ С†РёРєР»Р° async for
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
                # РљР РРўРР§РќРћ: Р§РёС‚Р°РµРј С„Р°Р№Р» РїСЂСЏРјРѕ Р·РґРµСЃСЊ, РІ С†РёРєР»Рµ!
                file_field = field
                while True:
                    chunk = await field.read_chunk()
                    if not chunk:
                        break
                    file_chunks.append(chunk)
        
        # РџСЂРѕРІРµСЂРєР° РѕР±СЏР·Р°С‚РµР»СЊРЅС‹С… РїРѕР»РµР№
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё upload_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_create_module(request):
    """
    POST /api/modules/create

    РЎРѕР·РґР°С‘С‚ РјРѕРґСѓР»СЊ РёР· В«С‚РѕР»СЊРєРѕ РєРѕРґР° С„СѓРЅРєС†РёРёВ»: РїРѕРґСЃС‚Р°РІР»СЏРµС‚ РєРѕРґ РІ РµРґРёРЅС‹Р№ С€Р°Р±Р»РѕРЅ,
    СЃРѕР±РёСЂР°РµС‚ manifest.json + module.py, РїСЂРѕРіРѕРЅСЏРµС‚ preflight Рё smoke, СЃРѕС…СЂР°РЅСЏРµС‚ ZIP Рё Р·Р°РїРёСЃСЊ РІ Р‘Р”.
    Р”РѕСЃС‚СѓРїРЅРѕ РёР· РІРµР±-С„РѕСЂРјС‹ Рё РёР· API (СѓСЃС‚Р°РЅРѕРІРєР° С‡РµСЂРµР· С‚РµСЂРјРёРЅР°Р» Р±РµР· РІРµР±-РїР°РЅРµР»Рё).

    JSON body:
    - module_name (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - version (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - tool_name (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - description (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - user_function_body (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ, С‚РµР»Рѕ async-С„СѓРЅРєС†РёРё)
    - risk_level (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ: safe_readonly | safe_write | dangerous, default safe_readonly)
    - overwrite (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ, default false)

    Returns: РєР°Рє POST /api/modules/upload (200 + status/success, 400 СЃ preflight_errors, 409 conflict).
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
        if not tool_name:
            return web.json_response({
                "status": "error",
                "error": "Missing tool_name",
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
    
    РЎРєР°С‡РёРІР°РµС‚ ZIP РјРѕРґСѓР»СЏ (streaming).
    
    Phase 6: РўСЂРµР±СѓРµС‚ Р°СѓС‚РµРЅС‚РёС„РёРєР°С†РёРё С‡РµСЂРµР· Authorization header (Bearer token).
    Query param ?token= РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РєР°Рє fallback (СЃ warning РІ Р»РѕРіР°С…).
    Р’СЃРµ СЃРєР°С‡РёРІР°РЅРёСЏ Р»РѕРіРёСЂСѓСЋС‚СЃСЏ РІ download_audit РґР»СЏ Р°СѓРґРёС‚Р°.
    
    РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·СѓРµС‚ aiohttp.web.FileResponse (СЃР°РјС‹Р№ Р±С‹СЃС‚СЂС‹Р№) РёР»Рё StreamResponse.
    Р”РѕР±Р°РІР»СЏРµС‚ ETag (sha256) Рё Cache-Control РґР»СЏ РєРѕСЂСЂРµРєС‚РЅРѕРіРѕ РєРµС€РёСЂРѕРІР°РЅРёСЏ.
    
    Returns:
        200 OK: ZIP file (streaming, application/zip)
            Headers:
            - Content-Type: application/zip
            - Content-Disposition: attachment; filename="{module_name}-{version}.zip"
            - Content-Length: size
            - ETag: "{sha256}"  # Р”Р»СЏ conditional requests
            - Cache-Control: no-store  # РџРѕРєР° РЅРµ РёСЃРїРѕР»СЊР·СѓРµРј РєРµС€ (РјРѕР¶РЅРѕ РёР·РјРµРЅРёС‚СЊ РЅР° public, max-age=...)
        401: Authentication required
        404: Module not found
        304: Not Modified (РµСЃР»Рё If-None-Match header СЃРѕРІРїР°РґР°РµС‚ СЃ ETag)
    """
    try:
        # Phase 6: РџРѕР»СѓС‡Р°РµРј AuthContext РёР· middleware (СѓР¶Рµ РїСЂРѕРІРµСЂРµРЅ)
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            # Р­С‚Рѕ РЅРµ РґРѕР»Р¶РЅРѕ РїСЂРѕРёР·РѕР№С‚Рё, РµСЃР»Рё middleware СЂР°Р±РѕС‚Р°РµС‚ РїСЂР°РІРёР»СЊРЅРѕ
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
            
            # РџСЂРѕРІРµСЂРєР° СЃСѓС‰РµСЃС‚РІРѕРІР°РЅРёСЏ С„Р°Р№Р»Р° РЅР° РґРёСЃРєРµ
            full_path = MODULES_STORAGE_DIR / module.storage_path
            if not full_path.exists():
                logger.error(f"Module file not found on disk: {full_path}")
                return web.json_response({
                    "status": "error",
                    "error": "Module file not found"
                }, status=404)
            
            # РџСЂРѕРІРµСЂРєР° If-None-Match (ETag)
            if_none_match = request.headers.get("If-None-Match", "").strip('"')
            if if_none_match == module.sha256:
                return web.Response(status=304)  # Not Modified
            
            # Phase 6: Audit logging - Р»РѕРіРёСЂСѓРµРј СЃРєР°С‡РёРІР°РЅРёРµ
            try:
                # РџРѕР»СѓС‡Р°РµРј С‚РѕРєРµРЅ РёР· auth_context
                token = auth_context.token
                if token:
                    # РҐРµС€РёСЂСѓРµРј С‚РѕРєРµРЅ РґР»СЏ Р±РµР·РѕРїР°СЃРЅРѕСЃС‚Рё
                    token_hash = AuthTokensRepo.hash_token(token)
                    token_prefix = AuthTokensRepo.get_token_prefix(token)
                    
                    # РџРѕР»СѓС‡Р°РµРј IP Р°РґСЂРµСЃ Рё user agent
                    ip_address = request.remote
                    user_agent = request.headers.get("User-Agent")
                    
                    # РЎРѕР·РґР°РµРј Р·Р°РїРёСЃСЊ РІ audit log
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
                # РќРµ РїСЂРµСЂС‹РІР°РµРј СЃРєР°С‡РёРІР°РЅРёРµ РїСЂРё РѕС€РёР±РєРµ Р°СѓРґРёС‚Р°, РЅРѕ Р»РѕРіРёСЂСѓРµРј
                logger.error(f"[DownloadModule] Audit logging failed: {audit_error}")
                logger.exception(audit_error)
            
            # РСЃРїРѕР»СЊР·СѓРµРј FileResponse РґР»СЏ СЌС„С„РµРєС‚РёРІРЅРѕР№ РѕС‚РґР°С‡Рё С„Р°Р№Р»Р°
            # РљР РРўРР§РќРћ: FileResponse РїСЂРёРЅРёРјР°РµС‚ str РёР»Рё Path, РЅРѕ Р»СѓС‡С€Рµ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ str
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё download_module: {e}")
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
            modules = await modules_repo.list_modules(
                module_name=module_name,
                limit=limit
            )

            return web.json_response({
                "modules": [module_to_api_record(module) for module in modules]
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
                **module_to_api_record(module, include_detail=True),
            })
    except Exception as e:
        logger.error(f"Get module detail failed: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_delete_module(request):
    """
    DELETE /api/modules/{module_name}/{version}

    РЈРґР°Р»СЏРµС‚ РјРѕРґСѓР»СЊ СЃ СЃРµСЂРІРµСЂР°: Р·Р°РїРёСЃСЊ РёР· Р‘Р” Рё С„Р°Р№Р» СЃ РґРёСЃРєР°.
    РўСЂРµР±СѓРµС‚ Р°СѓС‚РµРЅС‚РёС„РёРєР°С†РёРё Рё СЂРѕР»СЊ admin.

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
            module = await modules_repo.get_module(module_name, version)
            if not module:
                return web.json_response({
                    "status": "error",
                    "error": "Module not found",
                    "module_name": module_name,
                    "version": version
                }, status=404)

            storage_path = module.storage_path
            deleted = await modules_repo.delete_module(module_name, version)
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

        # РЈРґР°Р»СЏРµРј РїСѓСЃС‚С‹Рµ РґРёСЂРµРєС‚РѕСЂРёРё (module_name/version/)
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё delete_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
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
    
    РЈСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ РјРѕРґСѓР»СЊ РЅР° СѓСЃС‚СЂРѕР№СЃС‚РІРѕ (enqueue install_module_package).
    
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
        # Phase 2: РџРѕР»СѓС‡Р°РµРј actor_role РёР· AuthContext, РЅРµ РёР· JSON body
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
        # РћРїС†РёРѕРЅР°Р»СЊРЅРѕ: Р·Р°РјРµРЅРёС‚СЊ СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ РІРµСЂСЃРёСЋ РїСЂРё РґСЂСѓРіРѕРј SHA (РїРµСЂРµРґР°С‘С‚СЃСЏ Р°РіРµРЅС‚Сѓ РєР°Рє replace_if_different_sha)
        replace_if_exists = data.get("replace_if_exists") or data.get("replace_if_different_sha") or False
        
        # РљР РРўРР§РќРћ: РРіРЅРѕСЂРёСЂСѓРµРј actor_role РёР· JSON body СЃ warning
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
        
        # Phase 4: Policy check РґР»СЏ install_module_package
        # install_module_package - СЃРёСЃС‚РµРјРЅР°СЏ РѕРїРµСЂР°С†РёСЏ, С‚СЂРµР±СѓРµС‚ admin РёР»Рё system СЂРѕР»СЊ
        install_metadata = ToolMetadata(
            risk_level="system_write",  # install_module_package - СЃРёСЃС‚РµРјРЅР°СЏ РѕРїРµСЂР°С†РёСЏ
            requires_consent=False,
            allow_roles=None  # PolicyEngine СЂРµС€Р°РµС‚ РїРѕ risk_level
        )
        
        policy_engine = PolicyEngine()
        policy_decision = policy_engine.check_policy(
            actor_role=actor_role,
            tool_name="install_module_package",
            metadata=install_metadata
        )
        
        # Р•СЃР»Рё policy Р·Р°РїСЂРµС‰Р°РµС‚ в†’ 403, РѕРїРµСЂР°С†РёСЏ РЅРµ СЃРѕР·РґР°РµС‚СЃСЏ
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
        
        # Р’Р°Р»РёРґР°С†РёСЏ: module_name, version РґРѕР»Р¶РЅС‹ СЃСѓС‰РµСЃС‚РІРѕРІР°С‚СЊ РІ modules; РїСЂРѕРІРµСЂРєР° РћРЎ СѓСЃС‚СЂРѕР№СЃС‚РІР°
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
            
            # РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ kind="module_install" РґР»СЏ РѕРїРµСЂР°С†РёР№
            from app.services.operation_service import OperationService
            from websocket.ui_publisher import UiPublisherImpl
            
            operation_id = str(uuid.uuid4())
            
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_install",  # NEW: СЃРїРµС†РёР°Р»СЊРЅС‹Р№ kind РґР»СЏ РјРѕРґСѓР»СЊРЅС‹С… РѕРїРµСЂР°С†РёР№
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
            
            # Enqueue install_module_package С‡РµСЂРµР· enqueue_command_async (fire-and-forget)
            params_install = {
                "module_name": module_name,
                "module_version": version,
                "download_url": download_url,
                "sha256": module.sha256,
                "size": module.size,
                "package_b64": None,  # РћРїС†РёРѕРЅР°Р»СЊРЅРѕ, РґР»СЏ fallback
            }
            if replace_if_exists:
                params_install["replace_if_different_sha"] = True
            await enqueue_command_async(
                state=state,
                device_id=device_id,
                command="install_module_package",
                params=params_install,
                actor_role=actor_role,
                operation_id=operation_id  # РЎРІСЏР·Р°С‚СЊ СЃ operation
            )

            # Р—Р°РїРёСЃС‹РІР°РµРј desired state: С…РѕС‚РёРј СЌС‚РѕС‚ РјРѕРґСѓР»СЊ РЅР° СЌС‚РѕРј СѓСЃС‚СЂРѕР№СЃС‚РІРµ
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё install_module: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_bulk_install_modules(request):
    """
    POST /api/modules/bulk_install

    РњР°СЃСЃРѕРІР°СЏ СѓСЃС‚Р°РЅРѕРІРєР° РјРѕРґСѓР»СЏ РЅР° РЅРµСЃРєРѕР»СЊРєРѕ СѓСЃС‚СЂРѕР№СЃС‚РІ.
    Р”Р»СЏ РєР°Р¶РґРѕРіРѕ device_id СЃС‚Р°РІРёС‚СЃСЏ РєРѕРјР°РЅРґР° install_module_package РІ outbox:
    РѕРЅР»Р°Р№РЅ-Р°РіРµРЅС‚С‹ РїРѕР»СѓС‡Р°СЋС‚ РєРѕРјР°РЅРґСѓ СЃСЂР°Р·Сѓ, РѕС„Р»Р°Р№РЅ вЂ” РїСЂРё РїРѕРґРєР»СЋС‡РµРЅРёРё РёР· РѕС‡РµСЂРµРґРё.
    РќР° РєР°Р¶РґРѕРј Р°РіРµРЅС‚Рµ РїСЂРё СѓСЃС‚Р°РЅРѕРІРєРµ СЃРЅР°С‡Р°Р»Р° РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ smoke-РїСЂРѕРІРµСЂРєР°, Р·Р°С‚РµРј СѓСЃС‚Р°РЅРѕРІРєР°.

    JSON body:
    - module_name (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - version (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)
    - device_ids (РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ, РјР°СЃСЃРёРІ UUID СѓСЃС‚СЂРѕР№СЃС‚РІ)
    - replace_if_exists (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ, default false)

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
    
    РђРєС‚РёРІРёСЂСѓРµС‚ РјРѕРґСѓР»СЊ РЅР° СѓСЃС‚СЂРѕР№СЃС‚РІРµ (enqueue activate_module).
    
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
        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        data = await request.json()
        module_name = data.get("module_name")
        version = data.get("version")
        actor_role = data.get("actor_role", "admin")
        
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
        
        # РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ kind="module_activate" РґР»СЏ РѕРїРµСЂР°С†РёР№
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_activate",  # NEW: СЃРїРµС†РёР°Р»СЊРЅС‹Р№ kind РґР»СЏ РјРѕРґСѓР»СЊРЅС‹С… РѕРїРµСЂР°С†РёР№
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Enqueue activate_module С‡РµСЂРµР· enqueue_command_async (fire-and-forget)
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="activate_module",
            params={
                "name": module_name,
                "version": version
            },
            actor_role=actor_role,
            operation_id=operation_id  # РЎРІСЏР·Р°С‚СЊ СЃ operation
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё activate_module_new: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_deactivate_module_new(request):
    """
    POST /api/devices/{device_id}/modules/deactivate
    
    Р”РµР°РєС‚РёРІРёСЂСѓРµС‚ РјРѕРґСѓР»СЊ РЅР° СѓСЃС‚СЂРѕР№СЃС‚РІРµ (enqueue deactivate_module).
    
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
        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        data = await request.json()
        module_name = data.get("module_name")
        actor_role = data.get("actor_role", "admin")
        
        if not module_name:
            return web.json_response({
                "status": "error",
                "error": "Missing module_name"
            }, status=400)
        
        # РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ kind="module_deactivate" РґР»СЏ РѕРїРµСЂР°С†РёР№
        from app.services.operation_service import OperationService
        from websocket.ui_publisher import UiPublisherImpl
        
        operation_id = str(uuid.uuid4())
        
        async with get_session() as session:
            ui_publisher = UiPublisherImpl(state)
            op_service = OperationService(session, publisher=ui_publisher)
            
            await op_service.enqueue_operation(
                operation_id=operation_id,
                device_id=device_id,
                kind="module_deactivate",  # NEW: СЃРїРµС†РёР°Р»СЊРЅС‹Р№ kind РґР»СЏ РјРѕРґСѓР»СЊРЅС‹С… РѕРїРµСЂР°С†РёР№
                actor_role=actor_role,
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # Enqueue deactivate_module С‡РµСЂРµР· enqueue_command_async (fire-and-forget)
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="deactivate_module",
            params={
                "name": module_name
            },
            actor_role=actor_role,
            operation_id=operation_id  # РЎРІСЏР·Р°С‚СЊ СЃ operation
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё deactivate_module_new: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_sync_modules(request):
    """
    POST /api/devices/{device_id}/modules/sync
    
    РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅР°СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РјРѕРґСѓР»РµР№:
    1. Enqueue list_installed_modules (РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё device_modules)
    2. Enqueue list_tools (РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ device_toolset_snapshots)
    
    РљР РРўРР§РќРћ: Sync Modules РґРѕР»Р¶РЅР° РѕР±РЅРѕРІР»СЏС‚СЊ Рё modules inventory, Рё toolset snapshot.
    
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
        state = request.app['state']
        device_id = request.match_info["device_id"]
        
        from websocket.protocol import enqueue_command_async
        
        # 1. Enqueue list_installed_modules (РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё device_modules)
        modules_op_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="list_installed_modules",
            params={},
            actor_role="admin",
            trace_id=None
        )
        
        # 2. Enqueue list_tools (РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ device_toolset_snapshots)
        toolset_op_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="list_tools",
            params={},
            actor_role="admin",
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё sync_modules: {e}")
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
    РџРµСЂРµРґ enqueue: capability/version check вЂ” РјРѕРґСѓР»СЊ СЃ С‚Р°РєРѕР№ РІРµСЂСЃРёРµР№ РµСЃС‚СЊ РІ device_modules.
    """
    try:
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

        # РџСЂРё force=True РЅРµ РїСЂРѕРІРµСЂСЏРµРј inventory вЂ” СЃСЂР°Р·Сѓ СЃС‚Р°РІРёРј РєРѕРјР°РЅРґСѓ remove_module_version Р°РіРµРЅС‚Сѓ
        if not force:
            # Capability/version check: РјРѕРґСѓР»СЊ СЃ РІРµСЂСЃРёРµР№ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ device_modules (РїРѕ snapshot/inventory)
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
                kind="module_remove_version",  # NEW: СЃРїРµС†РёР°Р»СЊРЅС‹Р№ kind РґР»СЏ РјРѕРґСѓР»СЊРЅС‹С… РѕРїРµСЂР°С†РёР№
                actor_role="admin",
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
            actor_role="admin",
            trace_id=None,
            operation_id=operation_id,  # РЎРІСЏР·Р°С‚СЊ СЃ operation
            require_online=False,
        )
        if len(module_versions) <= 1:
            try:
                await set_desired_absent(
                    device_id=device_id,
                    module_name=module_name,
                    reason="manual_remove",
                    updated_by="admin",
                )
            except Exception as desired_e:
                logger.warning(
                    f"[handle_remove_module_version] Failed to set desired absent "
                    f"for {device_id}:{module_name}@{version}: {desired_e}"
                )
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role="admin",
            require_online=False,
        )

        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё remove_module_version: {e}")
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
    РџРµСЂРµРґ СѓРґР°Р»РµРЅРёРµРј Р°РіРµРЅС‚ С‚СЂРµР±СѓРµС‚ РґРµР°РєС‚РёРІР°С†РёСЋ: СЃРЅР°С‡Р°Р»Р° РІ РѕС‡РµСЂРµРґСЊ СЃС‚Р°РІРёС‚СЃСЏ deactivate_module,
    Р·Р°С‚РµРј remove_module (Р°РіРµРЅС‚ РѕР±СЂР°Р±РѕС‚Р°РµС‚ РїРѕ РїРѕСЂСЏРґРєСѓ).
    """
    try:
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

        # РџСЂРё force=True РЅРµ РїСЂРѕРІРµСЂСЏРµРј inventory вЂ” СЃСЂР°Р·Сѓ СЃС‚Р°РІРёРј РєРѕРјР°РЅРґС‹ Р°РіРµРЅС‚Сѓ
        if not force:
            # Capability check: РјРѕРґСѓР»СЊ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РІ device_modules
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
                actor_role="admin",
                trace_id=str(uuid.uuid4()),
                ticket_id=None,
                job_id=None
            )
            await session.commit()
        
        # РђРіРµРЅС‚ РЅРµ СѓРґР°Р»СЏРµС‚ Р°РєС‚РёРІРЅС‹Р№ РјРѕРґСѓР»СЊ: "Deactivate first". РЎС‚Р°РІРёРј РІ РѕС‡РµСЂРµРґСЊ СЃРЅР°С‡Р°Р»Р°
        # deactivate_module, Р·Р°С‚РµРј remove_module вЂ” Р°РіРµРЅС‚ РѕР±СЂР°Р±РѕС‚Р°РµС‚ РїРѕ РїРѕСЂСЏРґРєСѓ.
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="deactivate_module",
            params={"name": module_name},
            actor_role="admin",
            trace_id=None,
            require_online=False,
        )
        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="remove_module",
            params={"name": module_name},
            actor_role="admin",
            trace_id=None,
            operation_id=operation_id,
            require_online=False,
        )

        # Р—Р°РїРёСЃС‹РІР°РµРј desired state: С…РѕС‚РёРј РѕС‚СЃСѓС‚СЃС‚РІРёРµ СЌС‚РѕРіРѕ РјРѕРґСѓР»СЏ
        try:
            await set_desired_absent(
                device_id=device_id,
                module_name=module_name,
                reason="manual",
                updated_by="admin",
            )
        except Exception as desired_e:
            logger.warning(f"[handle_remove_module] Failed to set desired absent: {desired_e}")
        await _enqueue_module_followup_sync(
            state=state,
            device_id=device_id,
            actor_role="admin",
            require_online=False,
        )
        
        return web.json_response({
            "status": "accepted",
            "operation_id": operation_id
        }, status=202)
    
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё remove_module: {e}")
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
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё verify_module: {e}")
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

    Р’РѕР·РІСЂР°С‰Р°РµС‚ СЂР°Р·РЅРёС†Сѓ РјРµР¶РґСѓ desired state Рё actual state РґР»СЏ СѓСЃС‚СЂРѕР№СЃС‚РІР°.
    РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РґР»СЏ admin-СЃС‚СЂР°РЅРёС†С‹ РЅР°Р±Р»СЋРґР°РµРјРѕСЃС‚Рё Рё drift detection.
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
        logger.error(f"вќЊ РћС€РёР±РєР° desired_diff: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_trigger_reconcile(request):
    """
    POST /api/devices/{device_id}/modules/reconcile

    Р—Р°РїСѓСЃРєР°РµС‚ РЅРµРјРµРґР»РµРЅРЅС‹Р№ reconcile РґР»СЏ СѓСЃС‚СЂРѕР№СЃС‚РІР°.
    """
    try:
        device_id = request.match_info["device_id"]
        state = request.app["state"]

        from modules.reconcile import reconcile_device
        stats = await reconcile_device(device_id=device_id, state=state, reason="manual_trigger")

        return web.json_response({
            "status": "ok",
            "device_id": device_id,
            "stats": stats,
        })

    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° trigger_reconcile: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)

