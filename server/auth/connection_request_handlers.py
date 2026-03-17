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
from app.repos.devices_repo import DevicesRepo
from auth.middleware import require_auth
from auth.service import AuthService


def _get_client_ip(request: web.Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote or ""


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
    ip_address = _get_client_ip(request)

    state = request.app["state"]
    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        policy = await repo.get_policy()

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
            except ValueError as e:
                logger.warning(f"Connection request accept_all token limit: {e}")
                return web.json_response(
                    {"status": "error", "error": str(e)},
                    status=429,
                )
            logger.info(f"Connection request auto-approved (policy=accept_all): device_id={device_id[:8]}...")
            return web.json_response({
                "status": "approved",
                "token": token,
                "device_id": device_id,
            })

        # POLICY_MANUAL: create pending request
        existing = await repo.get_pending_by_device_id(device_id)
        if existing:
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

    state = request.app["state"]
    token_once = state.approved_connection_tokens.pop(device_id, None)
    if token_once:
        return web.json_response({
            "status": "approved",
            "token": token_once,
            "device_id": device_id,
        })

    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        status = await repo.get_status(device_id)

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
    if status == "rejected":
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
    state = request.app["state"]
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
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=429,
            )
        await repo.set_approved(device_id)
        await session.commit()

    state.approved_connection_tokens[device_id] = token
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
    return web.json_response({
        "status": "ok",
        "message": "Rejected",
        "device_id": device_id,
    })
