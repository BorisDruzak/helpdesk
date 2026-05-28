"""
HTTP обработчики для загрузки файлов (артефакты: скриншоты, запись экрана).

Потоковая запись, лимит 200MB, SHA256 на лету, сохранение в таблицу artifacts.
Контракты: server/docs/ARTIFACTS_API.md
"""

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path
from urllib.parse import quote

from aiohttp import web
from loguru import logger

from config import UPLOAD_DIR, ARTIFACT_MAX_BYTES
from auth.context import AuthType


_FILENAME_FALLBACK_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _suffix_from_filename(filename: str) -> str:
    """Извлекает расширение из имени файла (включая точку)."""
    p = Path(filename)
    ext = p.suffix.lower()
    return ext if ext else ".bin"


def _default_kind(mime_type: str, current_kind: str | None) -> str:
    if current_kind:
        return current_kind
    mime = (mime_type or "").lower()
    if mime.startswith("image/"):
        return "screenshot"
    if mime.startswith("video/"):
        return "screen_recording"
    return "file"


def _ascii_filename_fallback(filename: str) -> str:
    base = Path((filename or "download").replace("\\", "/")).name or "download"
    normalized = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    cleaned = _FILENAME_FALLBACK_RE.sub("_", normalized).strip("._ ")
    return cleaned or "download"


def _content_disposition_attachment(filename: str) -> str:
    fallback = _ascii_filename_fallback(filename)
    encoded = quote(filename or fallback, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _can_upload_to_ticket(auth_context, ticket) -> bool:
    if auth_context.actor_role in {"admin", "support"}:
        return True
    if auth_context.actor_role == "agent":
        return auth_context.actor_id == getattr(ticket, "device_id", None)
    if auth_context.auth_type == AuthType.PUBLIC_TICKET_TOKEN:
        return auth_context.ticket_scope == getattr(ticket, "ticket_id", None)
    if auth_context.actor_role == "user":
        return auth_context.actor_id == getattr(ticket, "requester_id", None)
    return False


def _account_session_error_response(payload: dict, *, status: int = 403) -> web.Response:
    return web.json_response(
        {
            "status": "error",
            "error": "account_session_invalid",
            "error_code": payload.get("error_code") or "ACCOUNT_SESSION_INVALID",
            "details": payload,
        },
        status=status,
    )


async def _require_agent_ticket_account_access(
    *,
    session,
    request: web.Request,
    auth_context,
    ticket_id: str,
    write: bool,
) -> web.Response | None:
    from app.repos.ticket_events_repo import TicketEventsRepo
    from tickets.account_access_service import TicketAccountAccessService, requester_account_from_payload

    ticket = await TicketEventsRepo(session).get_ticket(ticket_id)
    if not ticket:
        return web.json_response({"status": "error", "error": "ticket_not_found"}, status=404)
    requester_account = requester_account_from_payload(None, query=request.query, headers=request.headers)
    access = TicketAccountAccessService(session)
    validation = await access.validate_agent_account_session(
        device_id=auth_context.actor_id,
        requester_account=requester_account,
        require=True,
    )
    if not validation.get("valid"):
        return _account_session_error_response(validation)
    allowed = (
        await access.can_send_message(ticket=ticket, account_session=validation.get("session") or {})
        if write
        else await access.can_view_ticket(ticket=ticket, account_session=validation.get("session") or {})
    )
    if not allowed:
        return _account_session_error_response({"error_code": "ACCOUNT_ACCESS_DENIED"})
    return None


async def handle_upload(request: web.Request) -> web.StreamResponse:
    """
    HTTP API для загрузки файлов: POST /api/upload

    Multipart: file (обязательно), ticket_id, operation_id, kind (опционально).
    device_id берётся из токена (только агент).
    """
    auth_context = request.get("auth_context")
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required"},
            status=401,
        )
    is_agent_upload = auth_context.auth_type == AuthType.AGENT_TOKEN
    if auth_context.auth_type not in {
        AuthType.AGENT_TOKEN,
        AuthType.UI_TOKEN,
        AuthType.PUBLIC_TICKET_TOKEN,
    }:
        return web.json_response(
            {"status": "error", "error": "Authentication type is not allowed for uploads"},
            status=403,
        )
    device_id = auth_context.actor_id if is_agent_upload else None

    ticket_id = None
    operation_id = None
    kind = None
    file_saved_path = None
    sha256_hex = None
    size_bytes = 0
    mime_type = "application/octet-stream"
    original_name = ""
    storage_path = None
    file_processed = False

    try:
        reader = await request.multipart()
        async for part in reader:
            if part.filename:
                if file_processed:
                    await part.read()  # consume extra file parts
                    continue
                file_processed = True
                original_name = part.filename
                suffix = _suffix_from_filename(original_name)
                artifact_id = str(uuid.uuid4())
                storage_path = artifact_id + suffix
                file_saved_path = UPLOAD_DIR / storage_path
                hasher = hashlib.sha256()

                file_saved_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_saved_path, "wb") as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        size_bytes += len(chunk)
                        if size_bytes > ARTIFACT_MAX_BYTES:
                            f.close()
                            file_saved_path.unlink(missing_ok=True)
                            return web.json_response(
                                {
                                    "status": "error",
                                    "error": f"File size exceeds {ARTIFACT_MAX_BYTES // (1024*1024)} MB limit",
                                },
                                status=413,
                            )
                        hasher.update(chunk)
                        f.write(chunk)

                sha256_hex = hasher.hexdigest()
                ct = part.headers.get("Content-Type")
                if ct and ct.split(";")[0].strip():
                    mime_type = ct.split(";")[0].strip()
                else:
                    mime_map = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                        ".mp4": "video/mp4",
                    }
                    mime_type = mime_map.get(suffix, "application/octet-stream")
                # не break — читаем остальные части (ticket_id, operation_id, kind могут идти после file)

            else:
                name = part.name
                value = (await part.read()).decode("utf-8", errors="replace").strip()
                if name == "ticket_id" and value:
                    ticket_id = value
                elif name == "operation_id" and value:
                    operation_id = value
                elif name == "kind" and value:
                    kind = value

        if not file_saved_path or not file_saved_path.exists():
            return web.json_response(
                {"status": "error", "error": "No file provided"},
                status=400,
            )
        kind = _default_kind(mime_type, kind)

        from app.db import get_session
        from app.repos import ArtifactsRepo
        from app.repos.ticket_events_repo import TicketEventsRepo

        async with get_session() as session:
            if is_agent_upload and ticket_id:
                access_error = await _require_agent_ticket_account_access(
                    session=session,
                    request=request,
                    auth_context=auth_context,
                    ticket_id=ticket_id,
                    write=True,
                )
                if access_error is not None:
                    return access_error
            if not is_agent_upload:
                if not ticket_id:
                    return web.json_response(
                        {"status": "error", "error": "ticket_id is required for UI/Public upload"},
                        status=400,
                    )
                ticket_repo = TicketEventsRepo(session)
                ticket = await ticket_repo.get_ticket(ticket_id)
                if not ticket:
                    return web.json_response(
                        {"status": "error", "error": "ticket_not_found"},
                        status=404,
                    )
                if not _can_upload_to_ticket(auth_context, ticket):
                    return web.json_response(
                        {"status": "error", "error": "forbidden"},
                        status=403,
                    )
                device_id = ticket.device_id

            repo = ArtifactsRepo(session)
            # Этап 7.3: идемпотентность — при совпадении sha256+operation_id возвращаем существующий artifact
            if operation_id and sha256_hex:
                existing = await repo.get_by_sha256_and_operation_id(sha256_hex, operation_id)
                if existing:
                    try:
                        file_saved_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    download_url = f"/api/artifacts/{existing.artifact_id}/download"
                    logger.info(f"Идемпотентный upload: возвращаем существующий артефакт {existing.artifact_id}")
                    return web.json_response({
                        "status": "success",
                        "artifact_id": existing.artifact_id,
                        "filename": existing.storage_path,
                        "url": download_url,
                        "size": existing.size_bytes,
                        "sha256": existing.sha256,
                        "mime_type": existing.mime_type,
                        "kind": existing.kind,
                    })

            artifact_id = file_saved_path.stem
            await repo.create(
                artifact_id=artifact_id,
                storage_path=storage_path,
                original_name=original_name,
                mime_type=mime_type,
                size_bytes=size_bytes,
                sha256=sha256_hex,
                device_id=device_id,
                kind=kind,
                ticket_id=ticket_id,
                operation_id=operation_id,
                expires_at=None,
            )

        download_url = f"/api/artifacts/{artifact_id}/download"
        logger.success(f"Артефакт загружен: {artifact_id}, size={size_bytes}, kind={kind}")
        return web.json_response({
            "status": "success",
            "artifact_id": artifact_id,
            "filename": storage_path,
            "url": download_url,
            "size": size_bytes,
            "sha256": sha256_hex,
            "mime_type": mime_type,
            "kind": kind,
        })

    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}", exc_info=True)
        if file_saved_path and file_saved_path.exists():
            try:
                file_saved_path.unlink()
            except OSError:
                pass
        return web.json_response(
            {"status": "error", "error": str(e)},
            status=500,
        )

async def handle_artifact_download(request: web.Request) -> web.StreamResponse:
    """
    GET /api/artifacts/{artifact_id}/download — скачивание артефакта с проверкой прав.

    Поддерживается Range: bytes=... для видео (206 Partial Content).
    """
    auth_context = request.get("auth_context")
    artifact_id = request.match_info.get("artifact_id")
    if not artifact_id:
        return web.json_response({"status": "error", "error": "Missing artifact_id"}, status=400)

    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required"},
            status=401,
        )

    from app.db import get_session
    from app.services.artifact_service import (
        ArtifactService,
        NOT_FOUND,
        EXPIRED,
        FORBIDDEN,
    )

    async with get_session() as session:
        service = ArtifactService(session)
        ticket_id_from_request = request.query.get("ticket_id")
        artifact, reason = await service.get_artifact_for_download(artifact_id, auth_context, ticket_id_from_request=ticket_id_from_request)
        if artifact is not None and auth_context.auth_type == AuthType.AGENT_TOKEN:
            target_ticket_id = artifact.ticket_id or ticket_id_from_request
            if target_ticket_id:
                access_error = await _require_agent_ticket_account_access(
                    session=session,
                    request=request,
                    auth_context=auth_context,
                    ticket_id=target_ticket_id,
                    write=False,
                )
                if access_error is not None:
                    return access_error

    if reason == NOT_FOUND:
        return web.json_response({"status": "error", "error": "Artifact not found"}, status=404)
    if reason == EXPIRED:
        return web.json_response(
            {"status": "error", "error": "Artifact expired"},
            status=410,
        )
    if reason == FORBIDDEN:
        return web.json_response(
            {"status": "error", "error": "Access denied"},
            status=403,
        )

    file_path = UPLOAD_DIR / artifact.storage_path
    if not file_path.exists():
        return web.json_response({"status": "error", "error": "Artifact file not found"}, status=404)

    size = artifact.size_bytes
    range_header = request.headers.get("Range")

    if not range_header or not range_header.strip().lower().startswith("bytes="):
        # Full file
        with open(file_path, "rb") as f:
            body = f.read()
        return web.Response(
            body=body,
            status=200,
            headers={
                "Content-Type": artifact.mime_type,
                "Content-Length": str(len(body)),
                "Accept-Ranges": "bytes",
                "Content-Disposition": _content_disposition_attachment(artifact.original_name),
            },
        )

    # Parse Range: bytes=start-end
    try:
        parts = range_header.strip()[6:].split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else size - 1
        if start < 0:
            start = 0
        if end >= size:
            end = size - 1
        if start > end:
            return web.Response(status=416, headers={"Content-Range": f"bytes */{size}"})
    except (ValueError, IndexError):
        return web.Response(status=416, headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1
    with open(file_path, "rb") as f:
        f.seek(start)
        body = f.read(length)

    return web.Response(
        body=body,
        status=206,
        headers={
            "Content-Type": artifact.mime_type,
            "Content-Length": str(len(body)),
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Disposition": _content_disposition_attachment(artifact.original_name),
        },
    )
