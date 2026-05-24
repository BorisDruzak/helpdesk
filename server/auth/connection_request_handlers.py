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
from datetime import datetime, timedelta, timezone
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
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from auth.service import AuthService, ArchivedDeviceError
from auth.connection_request_service import ConnectionRequestService
from auth.device_fingerprint import (
    FINGERPRINT_METADATA_KEY,
    compare_device_fingerprints,
    normalize_device_fingerprint,
)
from tech.runtime_audit import write_agent_runtime_audit


TOKEN_LIMIT_ERROR_CODE = "TOKEN_LIMIT_EXCEEDED"
TOKEN_LIMIT_MESSAGE = (
    "На сервере уже есть 2 активных токена для этого устройства. "
    "Отзовите старый токен в админке или восстановите локальное хранилище токена агента."
)
APPROVED_HEARTBEAT_GRACE_SECONDS = 600


DEVICE_FINGERPRINT_MISMATCH_CODE = "DEVICE_FINGERPRINT_MISMATCH"
DEVICE_FINGERPRINT_MISMATCH_MESSAGE = (
    "Device fingerprint does not match this machine_id. Check the device or approve reprovision manually."
)


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


def _fingerprint_mismatch_response_payload(*, verdict: dict | None = None) -> dict:
    payload = {
        "status": "blocked",
        "message": DEVICE_FINGERPRINT_MISMATCH_MESSAGE,
        "error": DEVICE_FINGERPRINT_MISMATCH_MESSAGE,
        "error_code": DEVICE_FINGERPRINT_MISMATCH_CODE,
    }
    if verdict:
        payload["fingerprint_verdict"] = verdict
    return payload


def _fingerprint_verdict_payload(verdict) -> dict:
    return {
        "allowed": bool(verdict.allowed),
        "status": verdict.status,
        "matched_count": verdict.matched_count,
        "mismatched_count": verdict.mismatched_count,
        "comparable_count": verdict.comparable_count,
        "missing_count": verdict.missing_count,
        "details": verdict.details,
    }


def _metadata_fingerprint(metadata: dict) -> dict | None:
    return normalize_device_fingerprint(metadata.get(FINGERPRINT_METADATA_KEY))


def _stored_fingerprint(device) -> dict | None:
    if not device:
        return None
    metadata = getattr(device, "device_metadata", None)
    if not isinstance(metadata, dict):
        return None
    return normalize_device_fingerprint(metadata.get(FINGERPRINT_METADATA_KEY))


async def _validate_device_fingerprint_or_block(*, device, metadata: dict) -> tuple[bool, dict | None]:
    incoming = _metadata_fingerprint(metadata)
    if not incoming:
        return True, None
    stored = _stored_fingerprint(device)
    verdict = compare_device_fingerprints(stored, incoming)
    verdict_payload = _fingerprint_verdict_payload(verdict)
    metadata["device_fingerprint_verdict"] = verdict_payload
    if verdict.allowed:
        return True, verdict_payload
    return False, verdict_payload


async def _remember_device_fingerprint(devices_repo: DevicesRepo, *, device_id: str, metadata: dict) -> None:
    fingerprint = _metadata_fingerprint(metadata)
    if not fingerprint:
        return
    await devices_repo.merge_device_metadata(
        device_id,
        {
            FINGERPRINT_METADATA_KEY: fingerprint,
            "device_fingerprint_verdict": metadata.get("device_fingerprint_verdict"),
        },
    )


async def _mark_pending_device_fingerprint_mismatch(
    repo: ConnectionRequestsRepo,
    *,
    device_id: str,
    ip_address: str | None,
    hostname: str | None,
    metadata: dict,
    verdict: dict | None,
) -> None:
    metadata_patch = dict(metadata)
    metadata_patch.update(
        {
            "reason": "device_fingerprint_mismatch",
            "error_code": DEVICE_FINGERPRINT_MISMATCH_CODE,
            "fingerprint_verdict": verdict or {},
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
    ip_address = client_ip(request)
    request_id = str(data.get("request_id") or "").strip() or None
    poll_secret = str(data.get("poll_secret") or "").strip() or None
    if not check_rate_limit("connection_request", f"{ip_address}:{device_id}", limit=30, window_seconds=60):
        return rate_limited_response()

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

        fingerprint_allowed, fingerprint_verdict = await _validate_device_fingerprint_or_block(
            device=device,
            metadata=metadata,
        )
        if not fingerprint_allowed:
            await _mark_pending_device_fingerprint_mismatch(
                repo,
                device_id=device_id,
                ip_address=ip_address or None,
                hostname=hostname,
                metadata=metadata,
                verdict=fingerprint_verdict,
            )
            await session.commit()
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="device_fingerprint_mismatch",
                severity="critical",
                source="connection_request",
                details_json={"fingerprint_verdict": fingerprint_verdict or {}},
            )
            return web.json_response(
                _fingerprint_mismatch_response_payload(verdict=fingerprint_verdict),
                status=409,
            )

        if policy == POLICY_REJECT_ALL:
            logger.info(f"Connection request rejected (policy=reject_all): device_id={device_id[:8]}...")
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="connection_request_policy_rejected",
                severity="warning",
                source="connection_request",
                details_json={"policy": "reject_all"},
            )
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
                await write_agent_runtime_audit(
                    device_id=device_id,
                    event_type="connection_request_token_limit",
                    severity="warning",
                    source="connection_request",
                    details_json={"policy": "accept_all", "reason": str(e), "error_code": TOKEN_LIMIT_ERROR_CODE},
                )
                return web.json_response(
                    _token_limit_response_payload(error=str(e)),
                    status=429,
                )
            await _remember_device_fingerprint(devices_repo, device_id=device_id, metadata=metadata)
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
        existing = await repo.get_pending_by_device_id(device_id)
        if existing and request_id and poll_secret and existing.request_id == request_id and existing.poll_secret_hash == ConnectionRequestService.hash_poll_secret(poll_secret):
            await repo.touch_pending_request(device_id, metadata_patch=metadata, request_id=request_id)
            await session.commit()
            return web.json_response({
                "status": "pending",
                "message": "Request already pending",
                "request_id": request_id,
            })
        latest_request = await repo.get_latest_by_device_id(device_id)
        if latest_request and latest_request.status == "approved" and latest_request.approved_token_delivered_at is None:
            approved_at = latest_request.resolved_at or latest_request.created_at
            recent_approval = False
            if approved_at:
                recent_approval = datetime.now(timezone.utc) - approved_at <= timedelta(
                    seconds=APPROVED_HEARTBEAT_GRACE_SECONDS
                )
            if latest_request.approved_token or recent_approval:
                await write_agent_runtime_audit(
                    device_id=device_id,
                    event_type="connection_request_approval_waiting_delivery",
                    severity="info",
                    source="connection_request",
                    details_json={"reason": "post_approval_heartbeat"},
                )
                return web.json_response({
                    "status": "pending",
                    "message": "Request already approved; waiting for token delivery",
                })
        new_request_id = str(uuid_lib.uuid4())
        new_poll_secret = ConnectionRequestService.generate_poll_secret()
        try:
            await repo.create_request(
                device_id=device_id,
                ip_address=ip_address or None,
                hostname=hostname,
                metadata=metadata,
                request_id=new_request_id,
                poll_secret_hash=ConnectionRequestService.hash_poll_secret(new_poll_secret),
            )
        except Exception as exc:
            logger.exception(f"Connection request create failed for device_id={device_id[:8]}...: {exc}")
            return web.json_response(
                {"status": "error", "error": "Failed to create connection request", "error_code": "INTERNAL_ERROR"},
                status=500,
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
        "request_id": new_request_id,
        "poll_secret": new_poll_secret,
    })


async def handle_connection_request_status(request: web.Request) -> web.Response:
    """
    GET /api/connection_request/status?device_id=... (no auth).
    Returns: { status: "pending"|"approved"|"rejected", token? }.
    Token is generated only after request_id + poll_secret validation and returned once.
    """
    device_id = (request.query.get("device_id") or "").strip()
    request_id = (request.query.get("request_id") or "").strip()
    poll_secret = (request.query.get("poll_secret") or "").strip()
    if not device_id:
        return web.json_response(
            {"status": "error", "error": "Missing device_id"},
            status=400,
        )
    if not request_id or not poll_secret:
        return web.json_response(
            {
                "status": "error",
                "error": "request_id and poll_secret are required",
                "error_code": "POLL_SECRET_REQUIRED",
            },
            status=400,
        )
    if not check_rate_limit("connection_request_status", f"{client_ip(request)}:{device_id}:{request_id}", limit=120, window_seconds=60):
        return rate_limited_response()
    try:
        uuid_lib.UUID(device_id)
    except ValueError:
        return web.json_response(
            {"status": "error", "error": "Invalid device_id"},
            status=400,
        )

    connection_request_service = ConnectionRequestService()
    try:
        token_once = await connection_request_service.consume_approved_token_once(
            device_id=device_id,
            request_id=request_id,
            poll_secret=poll_secret,
        )
    except ArchivedDeviceError:
        return web.json_response(
            {
                "status": "rejected",
                "message": "Device archived by administrator",
                "error_code": "DEVICE_ARCHIVED",
            },
            status=409,
        )
    except ValueError as e:
        await write_agent_runtime_audit(
            device_id=device_id,
            event_type="connection_request_token_limit",
            severity="warning",
            source="connection_request_status",
            details_json={"reason": str(e), "error_code": TOKEN_LIMIT_ERROR_CODE},
        )
        return web.json_response(
            _token_limit_response_payload(error=str(e)),
            status=429,
        )
    if token_once:
        await write_agent_runtime_audit(
            device_id=device_id,
            event_type="connection_request_token_delivered",
            severity="info",
            source="connection_request_status",
        )
        return web.json_response({
            "status": "approved",
            "token": token_once,
            "device_id": device_id,
        })

    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        latest_request = await repo.get_by_request_id(request_id)
        if (
            not latest_request
            or latest_request.device_id != device_id
            or not latest_request.poll_secret_hash
            or latest_request.poll_secret_hash != ConnectionRequestService.hash_poll_secret(poll_secret)
        ):
            return web.json_response(
                {"status": "error", "error": "invalid poll secret", "error_code": "INVALID_POLL_SECRET"},
                status=403,
            )
        status = latest_request.status
        archived_reject = False
        token_limit_blocked = False
        fingerprint_blocked = False
        active_token_count = None
        fingerprint_verdict = None
        if latest_request and status == "rejected":
            metadata = latest_request.request_metadata if isinstance(latest_request.request_metadata, dict) else {}
            archived_reject = bool(metadata.get("archived_at"))
        if latest_request and status == "pending":
            metadata = latest_request.request_metadata if isinstance(latest_request.request_metadata, dict) else {}
            token_limit_blocked = metadata.get("error_code") == TOKEN_LIMIT_ERROR_CODE or metadata.get("reason") == "token_limit_exceeded"
            if token_limit_blocked:
                active_token_count = metadata.get("active_token_count")
            fingerprint_blocked = (
                metadata.get("error_code") == DEVICE_FINGERPRINT_MISMATCH_CODE
                or metadata.get("reason") == "device_fingerprint_mismatch"
            )
            if fingerprint_blocked:
                fingerprint_verdict = metadata.get("fingerprint_verdict") or metadata.get("device_fingerprint_verdict")

    if not status:
        return web.json_response({
            "status": "pending",
            "message": "No request found or not yet processed",
        })
    if status == "approved":
        return web.json_response({
            "status": "approved",
                "message": "Already approved; token was delivered earlier or is no longer available. Request a new connection if needed.",
        })
    if token_limit_blocked:
        return web.json_response(
            _token_limit_response_payload(active_token_count=active_token_count),
            status=429,
        )
    if fingerprint_blocked:
        return web.json_response(
            _fingerprint_mismatch_response_payload(verdict=fingerprint_verdict),
            status=409,
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
                "request_id": r.request_id,
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

    async with get_session() as session:
        repo = ConnectionRequestsRepo(session)
        pending = await repo.get_pending_by_device_id(device_id)
        if not pending:
            return web.json_response(
                {"status": "error", "error": "No pending request for this device"},
                status=404,
            )
        if not pending.request_id or not pending.poll_secret_hash:
            return web.json_response(
                {
                    "status": "error",
                    "error": "Agent must create a fresh connection request",
                    "error_code": "POLL_SECRET_MISSING",
                },
                status=409,
            )
        pending_metadata = pending.request_metadata if isinstance(pending.request_metadata, dict) else {}
        device = await DevicesRepo(session).get_by_device_id(device_id, include_deleted=True)
        fingerprint_allowed, fingerprint_verdict = await _validate_device_fingerprint_or_block(
            device=device,
            metadata=pending_metadata,
        )
        if not fingerprint_allowed:
            await repo.touch_pending_request(
                device_id,
                metadata_patch={
                    "reason": "device_fingerprint_mismatch",
                    "error_code": DEVICE_FINGERPRINT_MISMATCH_CODE,
                    "fingerprint_verdict": fingerprint_verdict or {},
                },
            )
            await session.commit()
            await write_agent_runtime_audit(
                device_id=device_id,
                event_type="device_fingerprint_mismatch",
                severity="critical",
                source="connection_request_admin",
                actor_id=request["auth_context"].actor_id if request.get("auth_context") else None,
                actor_role=request["auth_context"].actor_role if request.get("auth_context") else None,
                details_json={"fingerprint_verdict": fingerprint_verdict or {}},
            )
            return web.json_response(
                _fingerprint_mismatch_response_payload(verdict=fingerprint_verdict),
                status=409,
            )
        await _remember_device_fingerprint(DevicesRepo(session), device_id=device_id, metadata=pending_metadata)
        await repo.set_approved(device_id, request_id=pending.request_id)
        await session.commit()

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
