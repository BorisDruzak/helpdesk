"""
HTTP handlers for agent remote update (agent builds registry).
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional

from aiohttp import web
from loguru import logger

import config
from app.db import get_session
from app.db.models import AgentBuildDownloadAudit
from app.repos import AuthTokensRepo
from app.repos.agent_builds_repo import AgentBuildsRepo
from app.repos.agent_rollout_repo import AgentRolloutRepo
from app.services.operation_service import OperationService
from auth.context import AuthContext
from core.policy_engine import PolicyEngine
from core.tool_metadata import ToolMetadata
from utils.versioning import compare_versions, version_key
from websocket.protocol import enqueue_command_async
from tech.runtime_audit import write_agent_runtime_audit

# Маппинг ОС (из handshake metadata os_type) в target билда для массового обновления
OS_TYPE_TO_TARGET = {
    "windows": "windows_amd64",
    "Windows": "windows_amd64",
    "win": "windows_amd64",
    "linux": "linux_alt_x86_64",
    "Linux": "linux_alt_x86_64",
    "linux_alt": "linux_alt_x86_64",
}

RELEASE_CHANNELS = {"stable", "release"}
NON_RELEASE_CHANNELS = {"beta", "alpha", "rc", "dev", "nightly", "preview", "canary"}
VERSION_PRERELEASE_MARKERS = ("alpha", "beta", "rc", "dev", "preview", "nightly", "canary")


def _channel_priority(channel: Optional[str]) -> int:
    normalized = str(channel or "").strip().lower()
    if normalized in RELEASE_CHANNELS:
        return 3
    if normalized == "rc":
        return 2
    if normalized in {"beta", "preview", "canary"}:
        return 1
    if normalized in {"alpha", "dev", "nightly"}:
        return 0
    return -1


def _infer_release_channel(version: Optional[str], channel: Optional[str] = None) -> str:
    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel:
        if normalized_channel in RELEASE_CHANNELS:
            return "stable"
        if normalized_channel in NON_RELEASE_CHANNELS:
            return normalized_channel
    lowered = str(version or "").strip().lower()
    for marker in VERSION_PRERELEASE_MARKERS:
        if marker in lowered:
            return marker
    if "-" in lowered:
        return "prerelease"
    return "stable"


def _is_release_build(*, version: Optional[str], channel: Optional[str]) -> bool:
    inferred_channel = _infer_release_channel(version, channel)
    version_info = version_key(version)
    return inferred_channel == "stable" and not version_info.is_prerelease


def _pick_preferred_build(builds: list, *, release_only: bool = False):
    candidates = []
    for build in builds:
        if release_only and not _is_release_build(version=build.version, channel=build.channel):
            continue
        candidates.append(build)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda build: (
            version_key(getattr(build, "version", "")).key,
            _channel_priority(getattr(build, "channel", "")),
            getattr(build, "created_at", None) or 0,
        ),
    )


def _serialize_build_identity(build) -> dict:
    return {
        "target": build.target,
        "channel": build.channel,
        "version": build.version,
        "archive_type": build.archive_type,
        "artifact_name": build.artifact_filename,
        "is_release": _is_release_build(version=build.version, channel=build.channel),
        "download_path": f"/api/agent_builds/{build.target}/{build.channel}/{build.version}/download",
    }


def _resolve_target_for_device(device) -> Optional[str]:
    if not device:
        return None
    device_metadata = device.device_metadata if isinstance(device.device_metadata, dict) else {}
    os_type = device_metadata.get("os_type") or device.os
    return _os_type_to_target(os_type)


def _os_type_to_target(os_type: Optional[str]) -> Optional[str]:
    """Возвращает target билда по os_type из метаданных агента."""
    if not os_type:
        return None
    s = (os_type or "").strip()
    return OS_TYPE_TO_TARGET.get(s) or OS_TYPE_TO_TARGET.get(s.lower())


def _safe_str(v: Optional[str]) -> str:
    return (v or "").strip()


def _sanitize_update_reason(value: Optional[str]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:500]


async def _resolve_assigned_rollout_build(
    session,
    *,
    target: str,
    builds_repo: Optional[AgentBuildsRepo] = None,
    rollout_repo: Optional[AgentRolloutRepo] = None,
):
    repo = builds_repo or AgentBuildsRepo(session)
    rollout = rollout_repo or AgentRolloutRepo(session)
    assignment = await rollout.get_assignment(target)
    if not assignment:
        return None, None
    build = await repo.get_build(
        target=target,
        channel=assignment["channel"],
        version=assignment["version"],
    )
    return build, assignment


async def _resolve_recommended_build(session, *, target: str):
    repo = AgentBuildsRepo(session)
    assigned_build, assignment = await _resolve_assigned_rollout_build(session, target=target, builds_repo=repo)
    if assigned_build:
        return assigned_build, "assigned_rollout", assignment
    builds = await repo.list_builds_for_target(target=target)
    return _pick_preferred_build(builds, release_only=True), "latest_release_fallback", assignment


async def _resolve_requested_build(
    session,
    *,
    target: str,
    channel: str,
    version: Optional[str],
):
    repo = AgentBuildsRepo(session)
    if version:
        build = await repo.get_build(target=target, channel=channel, version=version)
        return build, "explicit_version"
    assigned_build, _assignment = await _resolve_assigned_rollout_build(session, target=target, builds_repo=repo)
    if assigned_build:
        return assigned_build, "assigned_rollout"
    build = await repo.get_latest_build(target=target, channel=channel)
    return build, "channel_latest"


def _build_identity_tuple(build) -> tuple[str, str, str]:
    return (
        str(getattr(build, "target", "") or "").strip(),
        str(getattr(build, "channel", "") or "").strip().lower(),
        str(getattr(build, "version", "") or "").strip(),
    )


async def _allow_agent_self_update_for_recommendation(
    session,
    *,
    auth_context: AuthContext,
    device_id: str,
    requested_build,
) -> tuple[bool, Optional[str], Optional[dict]]:
    if auth_context.actor_role != "agent":
        return False, None, None
    if auth_context.actor_id != device_id:
        return False, "AGENT_DEVICE_SCOPE_MISMATCH", None

    recommended_build, recommendation_source, assignment = await _resolve_recommended_build(
        session,
        target=str(getattr(requested_build, "target", "") or "").strip(),
    )
    if not recommended_build:
        return False, "AGENT_SELF_UPDATE_RECOMMENDATION_MISSING", None
    if _build_identity_tuple(recommended_build) != _build_identity_tuple(requested_build):
        return False, "AGENT_SELF_UPDATE_NOT_RECOMMENDED", {
            "recommended_build": _serialize_build_identity(recommended_build),
            "recommendation_source": recommendation_source,
            "assigned_rollout": assignment,
        }
    return True, None, {
        "recommended_build": _serialize_build_identity(recommended_build),
        "recommendation_source": recommendation_source,
        "assigned_rollout": assignment,
    }


async def handle_upload_agent_build(request: web.Request) -> web.Response:
    """
    POST /api/agent_builds/upload

    Multipart fields:
      - file: ZIP (required)
      - target: string (required) e.g. windows_amd64
      - channel: string (optional, default stable)
      - version: string (required)
      - notes: string (optional)
      - overwrite: string (optional "true"/"false", default "false")
    """
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )
    if auth_context.actor_role != "admin":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )

    reader = await request.multipart()

    target = None
    channel = "stable"
    version = None
    notes = None
    overwrite = False
    archive_type = None

    tmp_dir = config.AGENT_BUILDS_STORAGE_DIR / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    tmp_path: Optional[Path] = None
    sha256_hash = hashlib.sha256()
    total_size = 0
    max_size = config.MAX_AGENT_BUILD_SIZE

    try:
        async for field in reader:
            if field.name == "target":
                target = _safe_str((await field.read()).decode("utf-8"))
            elif field.name == "channel":
                channel_val = _safe_str((await field.read()).decode("utf-8")).lower()
                channel = channel_val or "stable"
            elif field.name == "version":
                version = _safe_str((await field.read()).decode("utf-8"))
            elif field.name == "notes":
                notes = _safe_str((await field.read()).decode("utf-8")) or None
            elif field.name == "overwrite":
                overwrite_str = _safe_str((await field.read()).decode("utf-8")).lower()
                overwrite = overwrite_str == "true"
            elif field.name == "archive_type":
                archive_type = _safe_str((await field.read()).decode("utf-8")).lower()
            elif field.name == "file":
                tmp_name = f"agent_build_{uuid.uuid4()}.tmp"
                tmp_path = tmp_dir / tmp_name
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = await field.read_chunk()
                        if not chunk:
                            break
                        total_size += len(chunk)
                        if total_size > max_size:
                            raise ValueError(f"File size {total_size} exceeds maximum {max_size}")
                        sha256_hash.update(chunk)
                        f.write(chunk)

        if not target:
            raise ValueError("Missing target")
        if not version:
            raise ValueError("Missing version")
        if not tmp_path:
            raise ValueError("Missing file")
        if not archive_type or archive_type not in ("zip", "tar.gz"):
            raise ValueError("Missing or invalid archive_type (required: zip or tar.gz)")

        if not channel:
            channel = "stable"

        sha256_hex = sha256_hash.hexdigest()
        ext = "zip" if archive_type == "zip" else "tar.gz"
        mime_type = "application/zip" if archive_type == "zip" else "application/gzip"
        artifact_filename = f"pc_agent-{target}-{version}.{ext}"
        storage_path = f"{target}/{channel}/{version}/agent.{ext}"
        final_dir = config.AGENT_BUILDS_STORAGE_DIR / target / channel / version
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = config.AGENT_BUILDS_STORAGE_DIR / storage_path

        async with get_session() as session:
            repo = AgentBuildsRepo(session)
            existing = await repo.get_build(target=target, channel=channel, version=version)

            if existing and not overwrite:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Build already exists",
                        "target": target,
                        "channel": channel,
                        "version": version,
                    },
                    status=409,
                )

            if final_path.exists():
                final_path.unlink()
            tmp_path.replace(final_path)
            tmp_path = None

            if existing:
                existing.sha256 = sha256_hex
                existing.size = total_size
                existing.storage_path = storage_path
                existing.artifact_filename = artifact_filename
                existing.archive_type = archive_type
                existing.mime_type = mime_type
                existing.uploaded_by = auth_context.actor_role
                existing.notes = notes
            else:
                await repo.create_build(
                    target=target,
                    channel=channel,
                    version=version,
                    sha256=sha256_hex,
                    size=total_size,
                    storage_path=storage_path,
                    uploaded_by=auth_context.actor_role,
                    notes=notes,
                    artifact_filename=artifact_filename,
                    archive_type=archive_type,
                    mime_type=mime_type,
                )

            await session.commit()

        download_path = f"/api/agent_builds/{target}/{channel}/{version}/download"

        return web.json_response(
            {
                "status": "success",
                "target": target,
                "channel": channel,
                "version": version,
                "sha256": sha256_hex,
                "size": total_size,
                "download_path": download_path,
            }
        )
    except ValueError as e:
        logger.warning(f"[AgentBuildUpload] Bad request: {e}")
        return web.json_response({"status": "error", "error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки upload_agent_build: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


async def handle_list_agent_builds(request: web.Request) -> web.Response:
    """
    GET /api/agent_builds?target=...&channel=...&limit=...

    Auth: обязателен (любая авторизованная роль).
    """
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )

    try:
        target = _safe_str(request.query.get("target")) or None
        channel = _safe_str(request.query.get("channel")).lower() or None
        limit_raw = _safe_str(request.query.get("limit")) or "50"
        try:
            limit = max(1, min(200, int(limit_raw)))
        except Exception:
            limit = 50

        async with get_session() as session:
            repo = AgentBuildsRepo(session)
            builds = await repo.list_builds(target=target, channel=channel, limit=limit)

        return web.json_response(
            {
                "status": "ok",
                "builds": [
                    {
                        "target": b.target,
                        "channel": b.channel,
                        "version": b.version,
                        "artifact_filename": b.artifact_filename,
                        "archive_type": b.archive_type,
                        "mime_type": b.mime_type,
                        "sha256": b.sha256,
                        "size": b.size,
                        "notes": b.notes,
                        "created_at": b.created_at.isoformat() if b.created_at else None,
                        "download_path": f"/api/agent_builds/{b.target}/{b.channel}/{b.version}/download",
                    }
                    for b in builds
                ],
                "count": len(builds),
            }
        )
    except Exception as e:
        logger.error(f"❌ Ошибка обработки list_agent_builds: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_get_agent_rollout_policy(request: web.Request) -> web.Response:
    """GET /api/agent_updates/rollout_policy."""
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )

    try:
        async with get_session() as session:
            repo = AgentBuildsRepo(session)
            rollout_repo = AgentRolloutRepo(session)
            assignments = await rollout_repo.list_assignments()
            builds = await repo.list_builds(limit=200)

        available_targets = sorted({str(build.target or "").strip() for build in builds if str(build.target or "").strip()})
        resolved = []
        for item in assignments:
            build = next(
                (
                    candidate
                    for candidate in builds
                    if candidate.target == item["target"]
                    and candidate.channel == item["channel"]
                    and candidate.version == item["version"]
                ),
                None,
            )
            resolved.append(
                {
                    "target": item["target"],
                    "channel": item["channel"],
                    "version": item["version"],
                    "updated_at": item.get("updated_at"),
                    "updated_by": item.get("updated_by"),
                    "build": _serialize_build_identity(build) if build else None,
                    "build_missing": build is None,
                }
            )
        return web.json_response(
            {
                "status": "ok",
                "assignments": resolved,
                "available_targets": available_targets,
            }
        )
    except Exception as e:
        logger.error(f"Failed to load agent rollout policy: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_patch_agent_rollout_policy(request: web.Request) -> web.Response:
    """PATCH /api/agent_updates/rollout_policy."""
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )
    if auth_context.actor_role != "admin":
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )

    try:
        data = await request.json()
    except Exception:
        data = {}
    target = _safe_str(data.get("target"))
    clear = bool(data.get("clear"))
    channel = _safe_str(data.get("channel")).lower()
    version = _safe_str(data.get("version"))

    if not target:
        return web.json_response({"status": "error", "error": "Missing target"}, status=400)

    try:
        async with get_session() as session:
            rollout_repo = AgentRolloutRepo(session)
            repo = AgentBuildsRepo(session)
            if clear:
                await rollout_repo.clear_assignment(target)
                await session.commit()
                return web.json_response({"status": "ok", "target": target, "cleared": True})

            if not channel or not version:
                return web.json_response(
                    {"status": "error", "error": "channel and version are required unless clear=true"},
                    status=400,
                )
            build = await repo.get_build(target=target, channel=channel, version=version)
            if not build:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Build not found",
                        "error_code": "BUILD_NOT_FOUND",
                        "target": target,
                        "channel": channel,
                        "version": version,
                    },
                    status=404,
                )
            assignment = await rollout_repo.set_assignment(
                target=target,
                channel=channel,
                version=version,
                updated_by=auth_context.actor_role,
            )
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "target": target,
                "assignment": assignment,
                "build": _serialize_build_identity(build),
            }
        )
    except Exception as e:
        logger.error(f"Failed to update agent rollout policy: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_download_agent_build(request: web.Request) -> web.Response:
    """
    GET /api/agent_builds/{target}/{channel}/{version}/download
    """
    try:
        auth_context: AuthContext = request.get("auth_context")
        if not auth_context:
            return web.json_response(
                {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
                status=401,
            )

        target = request.match_info["target"]
        channel = request.match_info["channel"]
        version = request.match_info["version"]

        async with get_session() as session:
            repo = AgentBuildsRepo(session)
            build = await repo.get_build(target=target, channel=channel, version=version)
            if not build:
                return web.json_response({"status": "error", "error": "Build not found"}, status=404)

            full_path = config.AGENT_BUILDS_STORAGE_DIR / build.storage_path
            if not full_path.exists():
                logger.error(f"Agent build file not found on disk: {full_path}")
                return web.json_response({"status": "error", "error": "Build file not found"}, status=404)

            if_none_match = request.headers.get("If-None-Match", "").strip('"')
            if if_none_match == build.sha256:
                return web.Response(status=304)

            # Audit logging
            try:
                token = auth_context.token
                if token:
                    token_hash = AuthTokensRepo.hash_token(token)
                    token_prefix = AuthTokensRepo.get_token_prefix(token)
                    audit = AgentBuildDownloadAudit(
                        token_hash=token_hash,
                        token_prefix=token_prefix,
                        target=target,
                        channel=channel,
                        version=version,
                        ip_address=request.remote,
                        user_agent=request.headers.get("User-Agent"),
                    )
                    session.add(audit)
                    await session.commit()
            except Exception as e:
                logger.warning(f"[DownloadAgentBuild] Failed to write audit record: {e}")

        filename = build.artifact_filename or f"pc_agent-{target}-{channel}-{version}.zip"
        content_type = build.mime_type or "application/zip"
        resp = web.FileResponse(
            path=full_path,
            headers={
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
                "ETag": f'"{build.sha256}"',
                "Cache-Control": "no-store",
            },
        )
        return resp
    except Exception as e:
        logger.error(f"❌ Ошибка обработки download_agent_build: {e}")
        logger.exception(e)
        return web.json_response({"status": "error", "error": str(e)}, status=500)


async def handle_get_device_update_recommendation(request: web.Request) -> web.Response:
    """
    GET /api/devices/{device_id}/agent/update_recommendation?current_version=...&target=...

    Returns server-side recommended release build for the device.
    """
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )

    device_id = request.match_info["device_id"]
    if auth_context.actor_role == "agent" and auth_context.actor_id != device_id:
        return web.json_response(
            {"status": "error", "error": "Forbidden", "error_code": "FORBIDDEN"},
            status=403,
        )

    current_version = _safe_str(request.query.get("current_version"))
    explicit_target = _safe_str(request.query.get("target")) or None

    async with get_session() as session:
        from app.repos.devices_repo import DevicesRepo

        devices_repo = DevicesRepo(session)
        device = await devices_repo.get_by_device_id(device_id)
        if not device:
            return web.json_response(
                {
                    "status": "error",
                    "error": "Device not found",
                    "error_code": "DEVICE_NOT_FOUND",
                    "device_id": device_id,
                },
                status=404,
            )

        target = explicit_target or _resolve_target_for_device(device)
        if not target:
            return web.json_response(
                {
                    "status": "error",
                    "error": "Could not determine build target for device",
                    "error_code": "TARGET_SELECTION_FAILED",
                    "device_id": device_id,
                },
                status=400,
            )

        recommended, recommendation_source, assignment = await _resolve_recommended_build(session, target=target)

    current_release_channel = _infer_release_channel(current_version) if current_version else "unknown"
    current_is_release = _is_release_build(version=current_version, channel=current_release_channel) if current_version else False
    current_comparison = "unknown"
    update_available = False
    recommended_reason = None

    if recommended and current_version:
        compare_result = compare_versions(recommended.version, current_version)
        version_mismatch = recommended.version != current_version
        if compare_result > 0:
            current_comparison = "newer_release_available"
        elif compare_result < 0:
            current_comparison = "recommended_release_is_older"
        else:
            current_comparison = "same_version"
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
    elif recommended and not current_version:
        update_available = True
        recommended_reason = "assigned_rollout" if recommendation_source == "assigned_rollout" else "current_version_unknown"

    payload = {
        "status": "ok",
        "device_id": device_id,
        "target": target,
        "current_version": current_version or None,
        "is_release": current_is_release,
        "release_channel": current_release_channel,
        "update_available": update_available,
        "recommended_version": recommended.version if recommended else None,
        "recommended_channel": recommended.channel if recommended else None,
        "recommended_reason": recommended_reason,
        "comparison": current_comparison,
        "recommended_build": _serialize_build_identity(recommended) if recommended else None,
        "recommendation_source": recommendation_source if recommended else "none",
        "assigned_rollout": assignment,
    }
    return web.json_response(payload)


async def handle_update_device_agent(request: web.Request) -> web.Response:
    """
    POST /api/devices/{device_id}/agent/update

    JSON:
      - target: string (required)
      - channel: string (optional, default stable)
      - version: string (optional; if omitted -> latest for target/channel)
      - restart_delay_sec: int (optional)

    Returns:
      202 Accepted: { status, operation_id, build }
    """
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )

    state = request.app["state"]
    device_id = request.match_info["device_id"]

    if not state.is_agent_online(device_id):
        return web.json_response(
            {
                "status": "error",
                "error": "Agent is offline",
                "error_code": "AGENT_OFFLINE",
                "device_id": device_id,
                "operation": None,
            },
            status=409,
        )

    data = await request.json()
    target = _safe_str(data.get("target"))
    channel = _safe_str(data.get("channel")).lower() or "stable"
    version = _safe_str(data.get("version")) or None
    restart_delay_sec = data.get("restart_delay_sec")
    reason = _sanitize_update_reason(data.get("reason"))

    if not target:
        return web.json_response({"status": "error", "error": "Missing target"}, status=400)

    async with get_session() as session:
        build, build_source = await _resolve_requested_build(
            session,
            target=target,
            channel=channel,
            version=version,
        )

        if not build:
            return web.json_response(
                {
                    "status": "error",
                    "error": "Build not found",
                    "target": target,
                    "channel": channel,
                    "version": version,
                },
                status=404,
            )

        agent_self_update_allowed = False
        agent_self_update_context = None
        if auth_context.actor_role == "agent":
            agent_self_update_allowed, agent_self_update_error, agent_self_update_context = (
                await _allow_agent_self_update_for_recommendation(
                    session,
                    auth_context=auth_context,
                    device_id=device_id,
                    requested_build=build,
                )
            )
            if not agent_self_update_allowed:
                error_message = "Insufficient permissions"
                if agent_self_update_error == "AGENT_SELF_UPDATE_NOT_RECOMMENDED":
                    error_message = "Agent may request only the current recommended build"
                elif agent_self_update_error == "AGENT_SELF_UPDATE_RECOMMENDATION_MISSING":
                    error_message = "No recommended build available for self-update"
                return web.json_response(
                    {
                        "status": "error",
                        "error": error_message,
                        "error_code": agent_self_update_error or "FORBIDDEN",
                        **(agent_self_update_context or {}),
                    },
                    status=403,
                )
        else:
            # Server-side policy check: update is system_write (admin/system only)
            policy_engine = PolicyEngine()
            decision = policy_engine.check_policy(
                actor_role=auth_context.actor_role,
                tool_name="update",
                metadata=ToolMetadata(risk_level="system_write", requires_consent=False, allow_roles=None),
            )
            if not decision.allow:
                return web.json_response(
                    {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
                    status=403,
                )

        # Create operation (materialized state)
        op_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        ui_publisher = state.ui_publisher if hasattr(state, "ui_publisher") else None
        op_service = OperationService(session, publisher=ui_publisher)
        await op_service.enqueue_operation(
            operation_id=op_id,
            device_id=device_id,
            kind="agent_update",
            actor_role=auth_context.actor_role,
            trace_id=trace_id,
            tool_name="update",
        )

        download_url = (
            f"{config.SERVER_PUBLIC_BASE_URL}/api/agent_builds/{build.target}/{build.channel}/{build.version}/download"
        )
        params = {
            "target": build.target,
            "channel": build.channel,
            "version": build.version,
            "download_url": download_url,
            "sha256": build.sha256,
            "size": build.size,
            "archive_type": build.archive_type or "zip",
            "artifact_name": build.artifact_filename,
        }
        if isinstance(restart_delay_sec, int):
            params["restart_delay_sec"] = restart_delay_sec
        if reason:
            params["reason"] = reason

        await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="update",
            params=params,
            actor_role=auth_context.actor_role,
            trace_id=trace_id,
            operation_id=op_id,
        )

        await session.commit()

    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="update_requested",
        severity="info",
        source="agent_update_api",
        operation_id=op_id,
        actor_id=auth_context.actor_id,
        actor_role=auth_context.actor_role,
        details_json={
            "target": build.target,
            "channel": build.channel,
            "version": build.version,
            "reason": reason,
        },
    )
    return web.json_response(
        {
            "status": "accepted",
            "device_id": device_id,
            "operation_id": op_id,
            "operation": {
                "operation_id": op_id,
                "kind": "agent_update",
                "status": "queued",
            },
            "build": {"target": build.target, "channel": build.channel, "version": build.version},
            "build_source": build_source,
            "self_update_authorized": agent_self_update_allowed if auth_context.actor_role == "agent" else False,
        },
        status=202,
    )


async def handle_bulk_update_agents(request: web.Request) -> web.Response:
    """
    POST /api/agents/update_bulk

    Массовое обновление агентов: по списку device_id или всем известным устройствам.
    Target подбирается автоматически по os_type устройства (Windows → windows_amd64, Linux → linux_alt_x86_64 и т.д.).

    Body:
      - device_ids: list[str] | null — если null или пусто, берутся все онлайн-агенты
      - channel: str (optional, default stable)
      - version: str (optional; если не указано — latest для каждого target)
      - restart_delay_sec: int (optional)

    Returns:
      200: { status, rollout_mode, operations: [...], skipped: [...], errors: [...] }
    """
    auth_context: AuthContext = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )

    policy_engine = PolicyEngine()
    decision = policy_engine.check_policy(
        actor_role=auth_context.actor_role,
        tool_name="update",
        metadata=ToolMetadata(risk_level="system_write", requires_consent=False, allow_roles=None),
    )
    if not decision.allow:
        return web.json_response(
            {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
            status=403,
        )

    try:
        data = await request.json()
    except Exception:
        data = {}
    device_ids_raw = data.get("device_ids")
    channel = _safe_str(data.get("channel")).lower() or "stable"
    version = _safe_str(data.get("version")) or None
    restart_delay_sec = data.get("restart_delay_sec")
    reason = _sanitize_update_reason(data.get("reason"))
    rollout_mode = _safe_str(data.get("rollout_mode")).lower() or "bulk"
    require_canary_confirmed = bool(data.get("require_canary_confirmed", False))
    canary_confirmed = bool(data.get("canary_confirmed", False))
    canary_operation_id = _safe_str(data.get("canary_operation_id")) or None

    if rollout_mode not in {"canary", "bulk"}:
        return web.json_response(
            {"status": "error", "error": "rollout_mode must be 'canary' or 'bulk'"},
            status=400,
        )
    if rollout_mode == "bulk" and require_canary_confirmed and not canary_confirmed:
        return web.json_response(
            {
                "status": "error",
                "error": "Canary confirmation required before bulk rollout",
                "error_code": "CANARY_REQUIRED",
            },
            status=409,
        )
    if rollout_mode == "bulk" and require_canary_confirmed:
        if not canary_operation_id:
            return web.json_response(
                {
                    "status": "error",
                    "error": "canary_operation_id is required for bulk rollout confirmation",
                    "error_code": "CANARY_OPERATION_REQUIRED",
                },
                status=409,
            )
        from app.repos.operations_repo import OperationsRepo
        from app.repos.device_outbox_repo import DeviceOutboxRepo
        async with get_session() as canary_session:
            canary_op_repo = OperationsRepo(canary_session)
            canary_outbox_repo = DeviceOutboxRepo(canary_session)
            canary_operation = await canary_op_repo.get_by_operation_id(canary_operation_id)
            if not canary_operation or canary_operation.kind != "agent_update" or canary_operation.status != "succeeded":
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Canary operation is not succeeded",
                        "error_code": "CANARY_NOT_SUCCEEDED",
                        "canary_operation_id": canary_operation_id,
                    },
                    status=409,
                )
            canary_outbox = await canary_outbox_repo.get_by_command_id(canary_operation_id)
            canary_params = canary_outbox.params if (canary_outbox and isinstance(canary_outbox.params, dict)) else {}
            if version and canary_params.get("version") != version:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Canary version does not match requested bulk version",
                        "error_code": "CANARY_BUILD_MISMATCH",
                    },
                    status=409,
                )
            if channel and canary_params.get("channel") != channel:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Canary channel does not match requested bulk channel",
                        "error_code": "CANARY_BUILD_MISMATCH",
                    },
                    status=409,
                )

    state = request.app["state"]
    from agents.service import AgentService

    from app.repos import DevicesRepo
    agent_service = AgentService(state)
    online_agents = {a.get("device_id"): a for a in agent_service.get_agents_list() if a.get("device_id")}

    async with get_session() as session:
        devices_repo = DevicesRepo(session)
        all_devices = await devices_repo.list_all()
        known_devices = {d.device_id: d for d in all_devices}

    if device_ids_raw is not None and isinstance(device_ids_raw, list) and len(device_ids_raw) > 0:
        device_ids = [str(d).strip() for d in device_ids_raw if str(d).strip()]
    else:
        device_ids = list(known_devices.keys())

    operations_result = []
    skipped_result = []
    errors_result = []
    audit_records: list[dict[str, str | None]] = []

    async with get_session() as session:
        ui_publisher = state.ui_publisher if hasattr(state, "ui_publisher") else None
        op_service = OperationService(session, publisher=ui_publisher)

        for device_id in device_ids:
            device_db = known_devices.get(device_id)
            if not device_db:
                errors_result.append(
                    {"device_id": device_id, "error": "Unknown device_id", "error_code": "DEVICE_NOT_FOUND"}
                )
                continue

            online_agent = online_agents.get(device_id)
            if not online_agent:
                skipped_result.append(
                    {
                        "device_id": device_id,
                        "reason": "agent_offline",
                        "error_code": "AGENT_OFFLINE",
                    }
                )
                continue

            device_meta = device_db.device_metadata if isinstance(device_db.device_metadata, dict) else {}
            os_type = online_agent.get("os_type") or online_agent.get("os") or device_db.os or device_meta.get("os_type")
            target = _os_type_to_target(os_type)
            if not target:
                errors_result.append({
                    "device_id": device_id,
                    "error": f"Unknown os_type: {os_type!r}, cannot select build target",
                    "error_code": "TARGET_SELECTION_FAILED",
                })
                continue

            build, build_source = await _resolve_requested_build(
                session,
                target=target,
                channel=channel,
                version=version,
            )
            if not build:
                errors_result.append({
                    "device_id": device_id,
                    "error": f"No build for target={target} channel={channel}" + (f" version={version}" if version else " (latest)"),
                    "error_code": "BUILD_NOT_FOUND",
                    "target": target,
                })
                continue

            op_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            await op_service.enqueue_operation(
                operation_id=op_id,
                device_id=device_id,
                kind="agent_update",
                actor_role=auth_context.actor_role,
                trace_id=trace_id,
                tool_name="update",
            )

            download_url = (
                f"{config.SERVER_PUBLIC_BASE_URL}/api/agent_builds/{build.target}/{build.channel}/{build.version}/download"
            )
            params = {
                "target": build.target,
                "channel": build.channel,
                "version": build.version,
                "download_url": download_url,
                "sha256": build.sha256,
                "size": build.size,
                "archive_type": build.archive_type or "zip",
                "artifact_name": build.artifact_filename,
            }
            if isinstance(restart_delay_sec, int):
                params["restart_delay_sec"] = restart_delay_sec
            if reason:
                params["reason"] = reason

            await enqueue_command_async(
                state=state,
                device_id=device_id,
                command="update",
                params=params,
                actor_role=auth_context.actor_role,
                trace_id=trace_id,
                operation_id=op_id,
            )

            operations_result.append({
                "device_id": device_id,
                "operation_id": op_id,
                "target": build.target,
                "channel": build.channel,
                "build_source": build_source,
                "build": {"target": build.target, "channel": build.channel, "version": build.version},
            })
            audit_records.append(
                {
                    "device_id": device_id,
                    "operation_id": op_id,
                    "target": build.target,
                    "channel": build.channel,
                    "version": build.version,
                }
            )

        await session.commit()

    for record in audit_records:
        await write_agent_runtime_audit(
            device_id=str(record["device_id"]),
            event_type="update_requested",
            severity="info",
            source="agent_update_bulk_api",
            operation_id=str(record["operation_id"]),
            actor_id=auth_context.actor_id,
            actor_role=auth_context.actor_role,
            details_json={
                "target": record["target"],
                "channel": record["channel"],
                "version": record["version"],
                "rollout_mode": rollout_mode,
                "reason": reason,
            },
        )

    return web.json_response({
        "status": "ok",
        "rollout_mode": rollout_mode,
        "operations": operations_result,
        "skipped": skipped_result,
        "errors": errors_result,
    })
