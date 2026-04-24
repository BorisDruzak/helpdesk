"""
HTTP handlers for device connection requests (no-token flow).

- POST /api/connection_request — agent requests authorization (no auth)
- GET /api/connection_request/status — agent polls for result (no auth)
- GET/PATCH /api/admin/connection_policy — get/set policy (admin)
- GET /api/admin/connection_requests — list pending (admin)
- POST /api/admin/connection_requests/{device_id}/approve — approve (admin)
- POST /api/admin/connection_requests/{device_id}/reject — reject (admin)
"""
import uuid as uuid_lib
from aiohttp import web
from loguru import logger

from app.db import get_session
from app.repos.connection_requests_repo import (
    ConnectionRequestsRepo,
    POLICY_ACCEPT_ALL,
    POLICY_MANUAL,
    POLICY_REJECT_ALL,
)
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.devices_repo import DevicesRepo
from auth.middleware import require_auth
from auth.service import AuthService, ArchivedDeviceError
from auth.connection_request_service import ConnectionRequestService
from tech.runtime_audit import write_agent_runtime_audit


TOKEN_LIMIT_ERROR_CODE = "TOKEN_LIMIT_EXCEEDED"
TOKEN_LIMIT_MESSAGE = (
    "На сервере уже есть 2 активных токена для этого устройства. "
    "Отзовите старый токен в админке или восстановите локальное хранилище токена агента."
)


def _get_client_ip(request: web.Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote or ""


def _token_limit_response_payload(*, active_token_count: int | None = None, error: str | None = None) -> dict:
    payload = {
        "status": "blocked",
        "message": TOKEN_LIMIT_MESSAGE,
        "error": error or TOKEN_LIMIT_MESSAGE,
        "error_code": TOKEN_LIMIT_ERROR_CODE,
    }
    if active_token_count is not None:
        payload["active_token_count"] = active_token_count
    return payload


async def _mark_pending_token_limit(
    repo: ConnectionRequestsRepo,
    *,
    device_id: str,
    ip_address: str | None,
    hostname: str | None,
    metadata: dict,
    active_token_count: int,
) -> None:
    metadata_patch = dict(metadata)
    metadata_patch.update(
        {
            "reason": "token_limit_exceeded",
            "error_code": TOKEN_LIMIT_ERROR_CODE,
            "active_token_count": active_token_count,
        }
    )
    existing = await repo.get_pending_by_device_id(device_id)
    if existing:
        await repo.touch_pending_request(device_id, metadata_patch=metadata_patch)
        return
    await repo.create_request(
        device_id=device_id,
        ip_address=ip_address or None,
        hostname=hostname,
        metadata=metadata_patch,
    )


async def handle_connection_request(request: web.Request) -> web.Response:
    """
    POST /api/connection_request (no auth).
    Body: { device_id, hostname?, metadata? }.
    Returns: { status: "pending"|"approved"|"rejected", token?, device_id? }.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON"},
            status=400,
        )
    device_id = (data.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "Missing device_id"},
            status=400,
        )
    try:
        uuid_lib.UUID(device_id)
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "Invalid device_id (must be UUID)"},
            status=400,
        )
    hostname = (data.get("hostname") or "").strip() or None
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    machine_id = str(metadata.get("machine_id") or "").strip()
    install_id = str(metadata.get("install_id") or "").strip()
    if machine_id and machine_id != device_id:
        return web.json_response(
            {"status": "error", "error": "metadata.machine_id must match device_id"},
            status=400,
        )
    if machine_id:
        try:
            uuid_lib.UUID(machine_id)
        except ValueError:
            return web.json_response(
                {"status": "error", "error": "Invalid metadata.machine_id"},
                status=400,
            )
    if install_id:
        try:
            uuid_lib.UUID(install_id)
        except ValueError:
            return web.json_response(
                {"status": "error", "error": "Invalid metadata.install_id"},
                status=400,
            )
    if metadata:
        metadata = dict(metadata)
    metadata["machine_id"] = device_id
    ip_address = _get_client_ip(request)

    state = request.app["state"]
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        devices_repo = DevicesRepo(session)
        policy = await repo.get_policy()
        device = await devices_repo.get_by_device_id(device_id, include_deleted=True)
        if device and device.deleted_at is not None:
            return web.json_response(
                {
                    "status": "rejected",
                    "message": "Устройство архивировано администратором",
                    "error_code": "DEVICE_ARCHIVED",
                },
                status=409,
            )

        if policy == POLICY_REJECT_ALL:
            logger.info(f"Connection request rejected (policy=reject_all): device_id={device_id[:8]}...")
            return web.json_response(
                {
                    "status": "rejected",
                    "message": "Administrator rejected connection",
                    "error_code": "CONNECTION_REJECTED",
                },
                status=403,
            )

        if policy == POLICY_ACCEPT_ALL:
            auth_service = AuthService(state)
            try:
                token = await auth_service.generate_agent_token(
                    device_id=device_id,
                    expires_hours=4320,
                )
            except ArchivedDeviceError:
                return web.json_response(
                    {
                        "status": "rejected",
                        "message": "Устройство архивировано администратором",
                        "error_code": "DEVICE_ARCHIVED",
                    },
                    status=409,
                )
            except ValueError as e:
                logger.warning(f"Connection request accept_all token limit: {e}")
                return web.json_response(
                    _token_limit_response_payload(error=str(e)),
                    status=429,
                )
            await repo.set_approved(device_id)
            await session.commit()
            logger.info(f"Connection request auto-approved (policy=accept_all): device_id={device_id[:8]}...")
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="connection_request_approved",
                severity="info",
                source="connection_request",
                details_json={"policy": "accept_all"},
            )
            return web.json_response({
                "status": "approved",
                "token": token,
                "device_id": device_id,
            })

        # POLICY_MANUAL: create pending request или обновить last_request_at (heartbeat)
        active_token_count = await AuthTokensRepo(session).check_active_token_limit(device_id)
        if active_token_count >= 2:
            await _mark_pending_token_limit(
                repo,
                device_id=device_id,
                ip_address=ip_address or None,
                hostname=hostname,
                metadata=metadata,
                active_token_count=active_token_count,
            )
            await session.commit()
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="connection_request_token_limit",
                severity="warning",
                source="connection_request",
                details_json={"active_token_count": active_token_count},
            )
            logger.warning(
                f"Connection request blocked by active token limit: "
                f"device_id={device_id[:8]}..., active={active_token_count}"
            )
            return web.json_response(
                _token_limit_response_payload(active_token_count=active_token_count),
                status=429,
            )
        existing = await repo.get_pending_by_device_id(device_id)
        if existing:
            await repo.touch_pending_request(device_id)
            await session.commit()
            return web.json_response({
                "status": "pending",
                "message": "Request already pending",
            })
        await repo.create_request(
            device_id=device_id,
            ip_address=ip_address or None,
            hostname=hostname,
            metadata=metadata,
        )
        await session.commit()
    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="connection_request_created",
        severity="info",
        source="connection_request",
    )
    logger.info(f"Connection request created (pending): device_id={device_id[:8]}...")
    return web.json_response({
        "status": "pending",
        "message": "Wait for authorization from Administrator",
    })


async def handle_connection_request_status(request: web.Request) -> web.Response:
    """
    GET /api/connection_request/status?device_id=... (no auth).
    Returns: { status: "pending"|"approved"|"rejected", token? }.
    Token is returned once on approved, then removed from server cache.
    """
    device_id = (request.query.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "Missing device_id"},
            status=400,
        )
    try:
        uuid_lib.UUID(device_id)
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "Invalid device_id"},
            status=400,
        )

    connection_request_service = ConnectionRequestService()
    token_once = await connection_request_service.consume_approved_token_once(device_id=device_id)
    if token_once:
        return web.json_response({
            "status": "approved",
            "token": token_once,
            "device_id": device_id,
        })

    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        status = await repo.get_status(device_id)
        latest_request = await repo.get_latest_by_device_id(device_id)
        archived_reject = False
        token_limit_blocked = False
        active_token_count = None
        if latest_request and status == "rejected":
            metadata = latest_request.request_metadata if isinstance(latest_request.request_metadata, dict) else {}
            archived_reject = bool(metadata.get("archived_at"))
        if latest_request and status == "pending":
            metadata = latest_request.request_metadata if isinstance(latest_request.request_metadata, dict) else {}
            token_limit_blocked = metadata.get("error_code") == TOKEN_LIMIT_ERROR_CODE or metadata.get("reason") == "token_limit_exceeded"
            if token_limit_blocked:
                active_token_count = metadata.get("active_token_count")

    if not status:
        return web.json_response({
            "status": "pending",
            "message": "No request found or not yet processed",
        })
    if status == "approved":
        return web.json_response({
            "status": "approved",
            "message": "Already approved; token was delivered earlier. Request a new connection if needed.",
        })
    if token_limit_blocked:
        return web.json_response(
            _token_limit_response_payload(active_token_count=active_token_count),
            status=429,
        )
    if status == "rejected":
        if archived_reject:
            return web.json_response({
                "status": "rejected",
                "message": "Device archived by administrator",
                "error_code": "DEVICE_ARCHIVED",
            })
        return web.json_response({
            "status": "rejected",
            "message": "Administrator rejected connection",
        })
    return web.json_response({
        "status": "pending",
        "message": "Wait for authorization from Administrator",
    })


@require_auth("admin")
async def handle_admin_connection_policy_get(request: web.Request) -> web.Response:
    """GET /api/admin/connection_policy (auth: admin)."""
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        policy = await repo.get_policy()
    return web.json_response({"status": "ok", "policy": policy})


@require_auth("admin")
async def handle_admin_connection_policy_patch(request: web.Request) -> web.Response:
    """PATCH /api/admin/connection_policy (auth: admin). Body: { policy }."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "error": "Invalid JSON"},
            status=400,
        )
    policy = (data.get("policy") or "").strip()
    if policy not in (POLICY_REJECT_ALL, POLICY_ACCEPT_ALL, POLICY_MANUAL):
        return web.json_response(
            {"status": "error", "error": "Invalid policy; use reject_all, accept_all, or manual"},
            status=400,
        )
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        await repo.set_policy(policy)
        await session.commit()
    logger.info(f"Connection policy set to: {policy}")
    return web.json_response({"status": "ok", "policy": policy})


@require_auth("admin")
async def handle_admin_connection_requests_list(request: web.Request) -> web.Response:
    """GET /api/admin/connection_requests (auth: admin)."""
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        pending = await repo.list_pending()
    return web.json_response({
        "status": "ok",
        "connection_requests": [
            {
                "device_id": r.device_id,
                "status": r.status,
                "ip_address": r.ip_address,
                "hostname": r.hostname,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "metadata": r.request_metadata or {},
            }
            for r in pending
        ],
        "count": len(pending),
    })


@require_auth("admin")
async def handle_admin_connection_request_approve(request: web.Request) -> web.Response:
    """POST /api/admin/connection_requests/{device_id}/approve (auth: admin)."""
    device_id = (request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "Missing device_id"},
            status=400,
        )
    try:
        uuid_lib.UUID(device_id)
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "Invalid device_id"},
            status=400,
        )

    state = request.app["state"]
    auth_service = AuthService(state)
    connection_request_service = ConnectionRequestService()
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        pending = await repo.get_pending_by_device_id(device_id)
        if not pending:
            return web.json_response(
                {"status": "error", "error": "No pending request for this device"},
                status=404,
            )
        try:
            token = await auth_service.generate_agent_token(
                device_id=device_id,
                expires_hours=4320,
            )
        except ArchivedDeviceError:
            return web.json_response(
                {"status": "error", "error": "Устройство архивировано администратором"},
                status=409,
            )
        except ValueError as e:
            await repo.touch_pending_request(
                device_id,
                metadata_patch={
                    "reason": "token_limit_exceeded",
                    "error_code": TOKEN_LIMIT_ERROR_CODE,
                },
            )
            await session.commit()
            return web.json_response(
                _token_limit_response_payload(error=str(e)),
                status=429,
            )
        await repo.set_approved(device_id)
        await session.commit()

    await connection_request_service.save_approved_token_once(device_id=device_id, token=token)
    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="connection_request_approved",
        severity="info",
        source="connection_request_admin",
        actor_id=request["auth_context"].actor_id if request.get("auth_context") else None,
        actor_role=request["auth_context"].actor_role if request.get("auth_context") else None,
    )
    logger.info(f"Connection request approved: device_id={device_id[:8]}...")
    return web.json_response({
        "status": "ok",
        "message": "Approved; agent will receive token on next status poll",
        "device_id": device_id,
    })


@require_auth("admin")
async def handle_admin_connection_request_reject(request: web.Request) -> web.Response:
    """POST /api/admin/connection_requests/{device_id}/reject (auth: admin)."""
    device_id = (request.match_info.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "Missing device_id"},
            status=400,
        )
    try:
        uuid_lib.UUID(device_id)
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "Invalid device_id"},
            status=400,
        )

    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        pending = await repo.get_pending_by_device_id(device_id)
        if not pending:
            return web.json_response(
                {"status": "error", "error": "No pending request for this device"},
                status=404,
            )
        await repo.set_rejected(device_id)
        await session.commit()

    logger.info(f"Connection request rejected: device_id={device_id[:8]}...")
    await write_agent_runtime_audit(
        device_id=device_id,
        event_type="connection_request_rejected",
        severity="warning",
        source="connection_request_admin",
        actor_id=request["auth_context"].actor_id if request.get("auth_context") else None,
        actor_role=request["auth_context"].actor_role if request.get("auth_context") else None,
    )
    return web.json_response({
        "status": "ok",
        "message": "Rejected",
        "device_id": device_id,
    })
